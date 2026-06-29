"""
Test de fallback LLM : épuisement quota Groq → bascule sur Gemini.

Stratégie : on injecte un état Redis simulé sans vrai Redis
en patchant KoraLLMRouter.get_provider_state / set_provider_state.

Exécution :
    python -m pytest backend/tests/test_fallback_llm.py -v
    python backend/tests/test_fallback_llm.py
"""
import asyncio
import sys
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_state(status: str, tokens_used: int = 0) -> dict:
    return {
        "status": status,
        "tokens_used_today": tokens_used,
        "requests_today": 0,
        "rate_limited_until": None,
        "exhausted_until": None,
    }


def _mock_provider_store(initial: dict) -> tuple:
    """Renvoie (get_fn, set_fn, store_dict) pour patcher le router."""
    store: dict = dict(initial)

    def get_fn(provider: str) -> dict:
        return store.get(provider, _make_state("ACTIVE"))

    def set_fn(provider: str, state: dict):
        store[provider] = state

    return get_fn, set_fn, store


# ── Tests ──────────────────────────────────────────────────────────────────────

async def test_groq_exhausted_fallback_to_gemini():
    """
    Scénario :
      - Groq EXHAUSTED (tokens_used_today >= daily_token_limit)
      - Gemini ACTIVE
    Attendu : get_active_provider() retourne 'gemini'
    """
    from core.llm_router import KoraLLMRouter, PROVIDER_CONFIG

    router = KoraLLMRouter.__new__(KoraLLMRouter)

    groq_limit = PROVIDER_CONFIG["groq"]["daily_token_limit"]
    initial = {
        "groq":       _make_state("ACTIVE",    tokens_used=groq_limit),   # quota plein
        "gemini":     _make_state("ACTIVE",    tokens_used=0),
        "cerebras":   _make_state("ACTIVE",    tokens_used=0),
        "openrouter": _make_state("ACTIVE",    tokens_used=0),
    }
    get_fn, set_fn, store = _mock_provider_store(initial)

    with patch.object(KoraLLMRouter, "get_provider_state", side_effect=get_fn):
        with patch.object(KoraLLMRouter, "set_provider_state", side_effect=set_fn):
            active = router.get_active_provider()

    assert active == "gemini", f"Attendu 'gemini', reçu '{active}'"
    assert store["groq"]["status"] == "EXHAUSTED"
    print("  [OK] Groq EXHAUSTED -> fallback gemini OK")


async def test_groq_rate_limited_fallback_to_gemini():
    """
    Scénario :
      - Groq RATE_LIMITED avec expiration dans le passé (devrait se réactiver)
      Mais si expiration dans le futur → skip → Gemini
    """
    from core.llm_router import KoraLLMRouter
    from datetime import datetime, timedelta

    router = KoraLLMRouter.__new__(KoraLLMRouter)

    future = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    initial = {
        "groq": {
            "status": "RATE_LIMITED",
            "tokens_used_today": 0,
            "requests_today": 0,
            "rate_limited_until": future,  # encore actif
            "exhausted_until": None,
        },
        "gemini":     _make_state("ACTIVE"),
        "cerebras":   _make_state("ACTIVE"),
        "openrouter": _make_state("ACTIVE"),
    }
    get_fn, set_fn, _ = _mock_provider_store(initial)

    with patch.object(KoraLLMRouter, "get_provider_state", side_effect=get_fn):
        with patch.object(KoraLLMRouter, "set_provider_state", side_effect=set_fn):
            active = router.get_active_provider()

    assert active == "gemini", f"Attendu 'gemini', reçu '{active}'"
    print("  [OK] Groq RATE_LIMITED (futur) -> fallback gemini OK")


async def test_all_providers_exhausted():
    """
    Scénario : tous les providers OFFLINE/EXHAUSTED → None
    """
    from core.llm_router import KoraLLMRouter, PROVIDER_CONFIG

    router = KoraLLMRouter.__new__(KoraLLMRouter)

    initial = {
        "groq":       _make_state("EXHAUSTED"),
        "gemini":     _make_state("EXHAUSTED"),
        "cerebras":   _make_state("OFFLINE"),
        "openrouter": _make_state("OFFLINE"),
    }
    get_fn, set_fn, _ = _mock_provider_store(initial)

    with patch.object(KoraLLMRouter, "get_provider_state", side_effect=get_fn):
        with patch.object(KoraLLMRouter, "set_provider_state", side_effect=set_fn):
            active = router.get_active_provider()

    assert active is None, f"Attendu None, reçu '{active}'"
    print("  [OK] Tous providers épuisés -> None OK")


async def test_complete_with_groq_exhausted_calls_gemini():
    """
    Test end-to-end du fallback dans router.complete() :
    Groq est EXHAUSTED dans le store → litellm appelé avec le modèle gemini.
    """
    from core.llm_router import KoraLLMRouter, PROVIDER_CONFIG

    router = KoraLLMRouter.__new__(KoraLLMRouter)

    groq_limit = PROVIDER_CONFIG["groq"]["daily_token_limit"]
    initial = {
        "groq":       _make_state("ACTIVE", tokens_used=groq_limit),
        "gemini":     _make_state("ACTIVE"),
        "cerebras":   _make_state("ACTIVE"),
        "openrouter": _make_state("ACTIVE"),
    }
    get_fn, set_fn, _ = _mock_provider_store(initial)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Réponse test"
    mock_response.usage = MagicMock(total_tokens=200, prompt_tokens=50, completion_tokens=150)

    messages = [{"role": "user", "content": "Bonjour KORA"}]
    called_model: list[str] = []

    async def mock_litellm_complete(**kwargs):
        called_model.append(kwargs.get("model", ""))
        return mock_response

    with patch.object(KoraLLMRouter, "get_provider_state", side_effect=get_fn):
        with patch.object(KoraLLMRouter, "set_provider_state", side_effect=set_fn):
            with patch("core.llm_router.litellm.acompletion", side_effect=mock_litellm_complete):
                result = await router.complete(messages=messages)

    assert result is not None
    assert len(called_model) == 1
    gemini_model = PROVIDER_CONFIG["gemini"]["primary_model"]
    assert called_model[0] == gemini_model, (
        f"Attendu appel à '{gemini_model}', reçu '{called_model[0]}'"
    )
    print(f"  [OK] Groq épuisé -> litellm appelé avec {called_model[0]}")


async def test_token_accounting_after_completion():
    """
    Après un appel réussi, les tokens sont comptabilisés dans le store provider.
    """
    from core.llm_router import KoraLLMRouter

    router = KoraLLMRouter.__new__(KoraLLMRouter)

    initial = {
        "groq":       _make_state("ACTIVE", tokens_used=0),
        "gemini":     _make_state("ACTIVE"),
        "cerebras":   _make_state("ACTIVE"),
        "openrouter": _make_state("ACTIVE"),
    }
    get_fn, set_fn, store = _mock_provider_store(initial)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "OK"
    mock_response.usage = MagicMock(total_tokens=350)

    with patch.object(KoraLLMRouter, "get_provider_state", side_effect=get_fn):
        with patch.object(KoraLLMRouter, "set_provider_state", side_effect=set_fn):
            with patch("core.llm_router.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
                await router.complete(messages=[{"role": "user", "content": "test"}])

    assert store["groq"]["tokens_used_today"] == 350, (
        f"Attendu 350 tokens, reçu {store['groq']['tokens_used_today']}"
    )
    print(f"  [OK] Comptabilisation tokens : {store['groq']['tokens_used_today']} tokens Groq")


# ── Runner ─────────────────────────────────────────────────────────────────────

async def main():
    sep = "=" * 60
    print(f"\n{sep}")
    print("  KORA -- Tests Fallback LLM (Phase 7)")
    print(f"{sep}\n")

    tests = [
        ("Groq EXHAUSTED -> fallback Gemini",          test_groq_exhausted_fallback_to_gemini),
        ("Groq RATE_LIMITED (futur) -> fallback Gemini", test_groq_rate_limited_fallback_to_gemini),
        ("Tous providers épuisés -> None",              test_all_providers_exhausted),
        ("complete() appelle Gemini si Groq épuisé",    test_complete_with_groq_exhausted_calls_gemini),
        ("Comptabilisation tokens après appel",         test_token_accounting_after_completion),
    ]

    passed = failed = 0
    for name, fn in tests:
        print(f">> {name}")
        try:
            await fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            import traceback; traceback.print_exc()
            failed += 1
        print()

    print("=" * 60)
    print(f"  Resultat : {passed}/{passed+failed} tests passes")
    if failed == 0:
        print("  [OK] Fallback LLM valide -- Groq->Gemini->Cerebras->OpenRouter")
    else:
        print(f"  [FAIL] {failed} test(s) echoue(s)")
    print("=" * 60 + "\n")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
