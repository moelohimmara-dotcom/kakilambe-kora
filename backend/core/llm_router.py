"""
KoraLLMRouter — fallback chain groq → cerebras → openrouter
State persistence : in-memory (sync) + Supabase provider_states (async)
Pas de Redis requis.
"""
import litellm
import json
from datetime import datetime, timedelta
from typing import Optional

from core.config import settings
from core.logger import logger

litellm.set_verbose = False

PROVIDER_CONFIG = {
    "groq": {
        "primary_model": "groq/llama-3.3-70b-versatile",
        "fallback_model": "groq/llama-3.1-8b-instant",
        # Limite réelle du compte Groq observée en production (erreur 429 :
        # "Limit 100000 ... on tokens per day (TPD)") — 500_000 était une valeur
        # inventée, jamais atteinte, qui empêchait la bascule proactive avant
        # que Groq ne renvoie lui-même l'erreur.
        "daily_token_limit": 100_000,
        "rpm_limit": 30,
        "api_key_env": "GROQ_API_KEY",
    },
    "cerebras": {
        # "cerebras/llama3.3-70b" renvoyait une 404 en production — pas une
        # erreur de nommage : Cerebras a retiré Llama 3.3 70B de son offre
        # publique (vérifié sur inference-docs.cerebras.ai/models/overview,
        # 2026-07-02). Catalogue production actuel : gpt-oss-120b uniquement.
        # Ce provider était donc mort en silence depuis le début du projet ;
        # la chaîne de repli retombait directement sur openrouter (8B, plus
        # faible) à chaque fois que groq était indisponible.
        "primary_model": "cerebras/gpt-oss-120b",
        "daily_token_limit": 200_000,
        "rpm_limit": 30,
        "api_key_env": "CEREBRAS_API_KEY",
    },
    "openrouter": {
        "primary_model": "openrouter/meta-llama/llama-3.1-8b-instruct",
        "daily_token_limit": None,
        "rpm_limit": 20,
        "api_key_env": "OPENROUTER_API_KEY",
    },
}

PROVIDER_ORDER = ["groq", "cerebras", "openrouter"]


class KoraLLMRouter:
    def __init__(self):
        # Cache mémoire — source de vérité pendant l'exécution
        self._cache: dict[str, dict] = {}

    # ── State defaults ───────────────────────────────────────────────────────

    def _default_state(self) -> dict:
        return {
            "status": "ACTIVE",
            "tokens_used_today": 0,
            "requests_today": 0,
            "rate_limited_until": None,
            "exhausted_until": None,
        }

    # ── Sync in-memory access (utilisé pendant les cycles) ───────────────────

    def get_provider_state(self, provider: str) -> dict:
        return dict(self._cache.get(provider, self._default_state()))

    def set_provider_state(self, provider: str, state: dict):
        self._cache[provider] = dict(state)

    def get_all_provider_states(self) -> dict:
        return {p: self.get_provider_state(p) for p in PROVIDER_ORDER}

    def override_provider_status(self, provider: str, status: str):
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Unknown provider: {provider}")
        state = self.get_provider_state(provider)
        state["status"] = status
        self.set_provider_state(provider, state)

    def reset_all_providers(self):
        for provider in PROVIDER_ORDER:
            self.set_provider_state(provider, self._default_state())

    # ── Supabase persistence ─────────────────────────────────────────────────

    async def load_from_db(self):
        """Charge les états depuis Supabase au démarrage de l'app."""
        try:
            from db.connection import get_db
            from sqlalchemy import text
            async with get_db() as db:
                result = await db.execute(text(
                    "SELECT provider, status, tokens_used_today, requests_today, "
                    "last_error, rate_limited_until, exhausted_until "
                    "FROM provider_states"
                ))
                rows = result.mappings().all()
            for row in rows:
                self._cache[row["provider"]] = {
                    "status": row["status"] or "ACTIVE",
                    "tokens_used_today": row["tokens_used_today"] or 0,
                    "requests_today": row["requests_today"] or 0,
                    "rate_limited_until": (
                        row["rate_limited_until"].isoformat()
                        if row["rate_limited_until"] else None
                    ),
                    "exhausted_until": (
                        row["exhausted_until"].isoformat()
                        if row["exhausted_until"] else None
                    ),
                    "last_error": row["last_error"],
                }
            logger.info("provider_states_loaded", count=len(rows))
        except Exception as e:
            logger.warning("provider_states_load_failed", error=str(e))

    async def persist_to_db(self, provider: str, state: dict):
        """Persiste un état provider dans Supabase (upsert)."""
        try:
            from db.connection import get_db
            from sqlalchemy import text
            from datetime import datetime as _dt

            def _parse_ts(val):
                """Convertit une string ISO en datetime (asyncpg attend un objet datetime)."""
                if val is None:
                    return None
                if isinstance(val, _dt):
                    return val
                try:
                    return _dt.fromisoformat(val)
                except (ValueError, TypeError):
                    return None

            async with get_db() as db:
                await db.execute(text("""
                    INSERT INTO provider_states
                        (provider, status, tokens_used_today, requests_today,
                         last_error, rate_limited_until, exhausted_until, updated_at)
                    VALUES
                        (:provider, :status, :tokens, :requests,
                         :last_error, :rate_limited_until, :exhausted_until, now())
                    ON CONFLICT (provider) DO UPDATE SET
                        status              = EXCLUDED.status,
                        tokens_used_today   = EXCLUDED.tokens_used_today,
                        requests_today      = EXCLUDED.requests_today,
                        last_error          = EXCLUDED.last_error,
                        rate_limited_until  = EXCLUDED.rate_limited_until,
                        exhausted_until     = EXCLUDED.exhausted_until,
                        updated_at          = now()
                """), {
                    "provider":            provider,
                    "status":              state.get("status", "ACTIVE"),
                    "tokens":              state.get("tokens_used_today", 0),
                    "requests":            state.get("requests_today", 0),
                    "last_error":          state.get("last_error"),
                    "rate_limited_until":  _parse_ts(state.get("rate_limited_until")),
                    "exhausted_until":     _parse_ts(state.get("exhausted_until")),
                })
        except Exception as e:
            logger.warning("provider_state_persist_failed", provider=provider, error=str(e))

    async def persist_all_to_db(self):
        """Persiste tous les états en base (utilisé par reset)."""
        for provider, state in self._cache.items():
            await self.persist_to_db(provider, state)

    # ── Active provider selection ────────────────────────────────────────────

    def get_active_provider(self) -> Optional[str]:
        for provider in PROVIDER_ORDER:
            state = self.get_provider_state(provider)
            status = state.get("status", "ACTIVE")

            if status == "ACTIVE":
                limit = PROVIDER_CONFIG[provider]["daily_token_limit"]
                if limit and state.get("tokens_used_today", 0) >= limit:
                    state["status"] = "EXHAUSTED"
                    self.set_provider_state(provider, state)
                    continue
                return provider

            elif status in ("RATE_LIMITED", "OFFLINE"):
                limited_until = state.get("rate_limited_until")
                if limited_until and datetime.utcnow().isoformat() > limited_until:
                    state["status"] = "ACTIVE"
                    state["rate_limited_until"] = None
                    self.set_provider_state(provider, state)
                    return provider

        return None

    def _attempt_order(self) -> list[str]:
        """
        Ordre d'essai pour un appel complet : le meilleur candidat actif d'abord
        (get_active_provider, qui saute déjà les providers RATE_LIMITED/OFFLINE
        dont la fenêtre n'est pas expirée), puis tous les autres providers en
        secours, y compris ceux marqués indisponibles — un état en cache peut
        être périmé, et un essai raté est peu coûteux face au risque de laisser
        l'utilisateur sans réponse du tout.
        """
        order = []
        active = self.get_active_provider()
        if active:
            order.append(active)
        for p in PROVIDER_ORDER:
            if p not in order:
                order.append(p)
        return order

    # ── Marquage d'état par type d'échec ─────────────────────────────────────

    async def _mark_rate_limited(self, provider: str):
        state = self.get_provider_state(provider)
        state["status"] = "RATE_LIMITED"
        state["rate_limited_until"] = (datetime.utcnow() + timedelta(seconds=60)).isoformat()
        self.set_provider_state(provider, state)
        await self.persist_to_db(provider, state)
        logger.warning("rate_limited", provider=provider)

    async def _mark_exhausted(self, provider: str, error: Exception):
        state = self.get_provider_state(provider)
        state["status"] = "EXHAUSTED"
        state["last_error"] = str(error)[:200]
        self.set_provider_state(provider, state)
        await self.persist_to_db(provider, state)
        logger.error("llm_model_not_found", provider=provider, error=str(error)[:200])

    async def _mark_offline(self, provider: str, error: Exception):
        state = self.get_provider_state(provider)
        state["status"] = "OFFLINE"
        state["rate_limited_until"] = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        state["last_error"] = str(error)[:200]
        self.set_provider_state(provider, state)
        await self.persist_to_db(provider, state)
        logger.error("llm_error", provider=provider, error=str(error)[:200])

    async def _mark_success(self, provider: str, usage=None):
        state = self.get_provider_state(provider)
        if usage:
            state["tokens_used_today"] += getattr(usage, "total_tokens", 0)
        state["requests_today"] += 1
        self.set_provider_state(provider, state)
        await self.persist_to_db(provider, state)

    async def _handle_failure(self, provider: str, error: Exception):
        """Marque l'état du provider en échec et retourne True si on doit tenter le suivant."""
        if isinstance(error, litellm.RateLimitError):
            await self._mark_rate_limited(provider)
            return True
        if isinstance(error, litellm.NotFoundError):
            await self._mark_exhausted(provider, error)
            return True
        if isinstance(error, litellm.ContextWindowExceededError):
            # Pas un problème de provider — un autre modèle ne résoudra rien
            # de façon fiable pour la même conversation trop longue.
            logger.warning("context_exceeded", provider=provider)
            return False
        await self._mark_offline(provider, error)
        return True

    # ── LLM completion avec bascule explicite entre providers ────────────────
    # litellm.acompletion(fallbacks=[...]) s'est montré non fiable en streaming
    # (l'erreur 429 surgit lors de la CONSOMMATION du générateur, pas au moment
    # du `await`, donc le fallback interne de litellm ne se déclenche jamais) —
    # remplacé par une boucle Python explicite, testable et déterministe.

    async def complete(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        response_format=None,
        tools: Optional[list] = None,
        tool_choice=None,
        reasoning_effort: Optional[str] = None,
    ):
        self._set_litellm_keys()
        providers = self._attempt_order()
        if not providers:
            raise RuntimeError("All LLM providers exhausted or offline")

        if stream:
            return self._stream_with_fallback(
                providers, messages, temperature, max_tokens, response_format, tools, tool_choice, reasoning_effort
            )
        return await self._complete_with_fallback(
            providers, messages, temperature, max_tokens, response_format, tools, tool_choice, reasoning_effort
        )

    def _build_params(self, provider: str, messages, temperature, max_tokens, stream, response_format, tools, tool_choice, reasoning_effort=None) -> dict:
        params = {
            "model": PROVIDER_CONFIG[provider]["primary_model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice or "auto"
        # gpt-oss-120b (Cerebras) est un modèle de raisonnement : ses tokens de
        # "réflexion" interne (completion_tokens_details.reasoning_tokens) sont
        # décomptés du même budget max_tokens que la réponse finale, et leur
        # volume est imprévisible (664 à 2849 tokens observés sur un MÊME prompt
        # répété) — root cause confirmée le 2026-07-14 des échecs "Unterminated
        # string" et du contenu tronqué/vide (finish_reason="length" avant même
        # le début du JSON de réponse). reasoning_effort="low" ramène ce
        # surcoût à ~130-230 tokens de façon stable, laissant le budget dispo
        # pour un corps de 800-1200 mots. Uniquement supporté par les modèles
        # de raisonnement (gpt-oss) — ignoré silencieusement par les autres
        # providers si jamais transmis (litellm ne bronche pas sur un param
        # inconnu pour la plupart des backends OpenAI-compatibles).
        if reasoning_effort and "gpt-oss" in PROVIDER_CONFIG[provider]["primary_model"]:
            params["reasoning_effort"] = reasoning_effort
        return params

    async def _complete_with_fallback(
        self, providers: list[str], messages, temperature, max_tokens, response_format, tools, tool_choice, reasoning_effort=None
    ):
        last_err = None
        for provider in providers:
            params = self._build_params(provider, messages, temperature, max_tokens, False, response_format, tools, tool_choice, reasoning_effort)
            try:
                response = await litellm.acompletion(**params)
                await self._mark_success(provider, getattr(response, "usage", None))
                logger.info(
                    "llm_success", provider=provider, model=params["model"],
                    tokens=getattr(getattr(response, "usage", None), "total_tokens", 0),
                )
                return response
            except Exception as e:
                last_err = e
                should_continue = await self._handle_failure(provider, e)
                if not should_continue:
                    raise
        raise RuntimeError(f"All LLM providers failed. Dernière erreur ({providers[-1]}): {last_err}")

    async def _stream_with_fallback(
        self, providers: list[str], messages, temperature, max_tokens, response_format, tools, tool_choice, reasoning_effort=None
    ):
        """
        Générateur async : tente chaque provider, en tamponnant les chunks SANS
        rien céder à l'appelant tant qu'aucun contenu réel n'a été reçu.

        Un seul "premier chunk" ne suffit pas : certains providers (Gemini
        notamment) renvoient un chunk initial vide/métadonnée avant que l'échec
        réel (ex. clé API invalide) ne survienne sur un chunk suivant. Tant que
        rien n'a été cédé au client, un échec à n'importe quel stade du
        tampon reste invisible et permet de basculer vers le provider suivant.
        Une fois qu'un chunk avec du contenu réel arrive, on s'engage : on cède
        tout le tampon puis on continue de streamer normalement.
        """
        last_err = None
        for provider in providers:
            params = self._build_params(provider, messages, temperature, max_tokens, True, response_format, tools, tool_choice, reasoning_effort)
            buffered = []
            try:
                response = await litellm.acompletion(**params)
                stream_iter = response.__aiter__()
                async for chunk in stream_iter:
                    buffered.append(chunk)
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and getattr(delta, "content", None):
                        break
                else:
                    # Flux terminé sans qu'aucun chunk n'ait de contenu réel —
                    # complétion vide légitime (pas un échec à retenter).
                    await self._mark_success(provider)
                    for c in buffered:
                        yield c
                    return
            except Exception as e:
                last_err = e
                should_continue = await self._handle_failure(provider, e)
                if not should_continue:
                    raise
                continue

            await self._mark_success(provider)
            logger.info("llm_success", provider=provider, model=params["model"], streaming=True)
            for c in buffered:
                yield c
            async for chunk in stream_iter:
                yield chunk
            return

        raise RuntimeError(f"All LLM providers failed (streaming). Dernière erreur ({providers[-1]}): {last_err}")

    def _set_litellm_keys(self):
        if settings.GROQ_API_KEY:
            litellm.groq_key = settings.GROQ_API_KEY
        if settings.CEREBRAS_API_KEY:
            litellm.cerebras_key = settings.CEREBRAS_API_KEY
        if settings.OPENROUTER_API_KEY:
            litellm.openrouter_key = settings.OPENROUTER_API_KEY


# Singleton
llm_router = KoraLLMRouter()
