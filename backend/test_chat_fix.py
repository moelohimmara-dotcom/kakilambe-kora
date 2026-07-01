"""
test_chat_fix.py — Validation de la bascule automatique de providers LLM
(incident : litellm.RateLimitError 429 Groq non intercepté sur /api/chat/stream).

Contrainte d'environnement identique à test_chat_rag.py : aucune clé API
locale — validation contre l'instance déployée (seul endroit avec les vraies
clés Groq/Gemini/Cerebras/OpenRouter).

Usage : python test_chat_fix.py [base_url]
"""
import sys
import time
import json
import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "https://kora-582m5.ondigitalocean.app"
QUESTION = "Résume les dernières nouvelles de Guinée"
_MAX_ATTEMPTS = 3

_ERROR_MARKERS = ["RateLimitError", "litellm.", "GroqException", "error_code", "429"]


def _get_providers():
    r = httpx.get(f"{BASE_URL}/api/providers", timeout=15)
    r.raise_for_status()
    return r.json()


def _stream_chat(message: str) -> tuple[str, list[str]]:
    """Consomme le SSE /api/chat/stream et retourne (texte assemblé, erreurs SSE brutes)."""
    session_id = "test-chat-fix-script"
    url = f"{BASE_URL}/api/chat/stream"
    params = {"session_id": session_id, "message": message}

    accumulated = ""
    errors = []
    with httpx.Client(timeout=90) as client:
        with client.stream("GET", url, params=params) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "token" in data:
                    accumulated += data["token"]
                if "error" in data:
                    errors.append(data["error"])
    return accumulated, errors


def main() -> int:
    print("── État des providers avant test ─────────────────────────────")
    try:
        providers = _get_providers()
        for p in providers:
            print(f"  {p['name']:<12} status={p['status']:<14} tokens_used={p['tokens_used_today']}")
    except Exception as e:
        print(f"  (impossible de lire /api/providers : {e})")
    print()

    print(f"→ GET {BASE_URL}/api/chat/stream")
    print(f"→ Message : {QUESTION!r}\n")

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            content, sse_errors = _stream_chat(QUESTION)
        except Exception as e:
            print(f"  (tentative {attempt}/{_MAX_ATTEMPTS} — requête HTTP échouée : {e})")
            if attempt < _MAX_ATTEMPTS:
                time.sleep(4)
                continue
            print("❌ ÉCHEC : requête HTTP impossible après plusieurs tentatives.")
            return 1

        print("── Réponse assemblée ──────────────────────────────────────")
        print(content[:1500])
        print("───────────────────────────────────────────────────────────\n")

        if sse_errors:
            print(f"❌ ÉCHEC : le flux SSE contient une erreur : {sse_errors}")
            hit = [m for m in _ERROR_MARKERS if any(m in e for e in sse_errors)]
            if hit:
                print(f"   Marqueurs d'erreur brute litellm/provider détectés : {hit}")
                print("   → La bascule vers un provider de secours n'a PAS empêché l'erreur de remonter.")
            if attempt < _MAX_ATTEMPTS:
                print(f"   Nouvelle tentative ({attempt+1}/{_MAX_ATTEMPTS})...")
                time.sleep(4)
                continue
            return 1

        if not content.strip():
            print("❌ ÉCHEC : réponse vide, aucun token reçu.")
            if attempt < _MAX_ATTEMPTS:
                time.sleep(4)
                continue
            return 1

        print("✅ SUCCÈS : réponse textuelle fluide reçue, aucune erreur 429/litellm dans le flux SSE.")
        print("\n── État des providers après test ─────────────────────────────")
        try:
            for p in _get_providers():
                print(f"  {p['name']:<12} status={p['status']:<14} tokens_used={p['tokens_used_today']}")
        except Exception:
            pass
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
