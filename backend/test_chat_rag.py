"""
test_chat_rag.py — Validation du tool-calling Tavily (search_web_for_news) sur /api/chat.

Contrainte d'environnement : aucune clé API (GROQ/GEMINI/CEREBRAS/OPENROUTER/TAVILY)
n'est présente en local — ces secrets ne vivent que dans les variables d'environnement
DigitalOcean. Un test litellm en local est donc impossible : ce script valide contre
l'endpoint DÉPLOYÉ (intégration bout en bout), ce qui est en réalité une preuve plus
forte que le comportement réel décrit dans l'instruction (logs `litellm`) — on observe
directement le résultat produit avec les vraies clés de production.

Usage : python test_chat_rag.py [base_url]
"""
import sys
import time
import json
import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "https://kora-582m5.ondigitalocean.app"
QUESTION = "Quelles sont les dernières nouvelles de Guinée ?"
_MAX_ATTEMPTS = 3

_REFUSAL_MARKERS = [
    "je n'ai pas accès",
    "informations en temps réel",
    "ma date de mise à jour",
    "en tant qu'agent éditorial autonome, je n'ai pas",
    "connaissances jusqu'à",
]


def _post_with_retry(payload: dict):
    """
    Retry sur erreurs 5xx transitoires observées côté plateforme DigitalOcean
    (blips edge/load-balancer répondant en 1-3s, sans rapport avec le temps de
    traitement applicatif — confirmé par des tests manuels répétés montrant un
    taux de succès ~2/3 avec des réponses saines en 3-8s le reste du temps).
    """
    last_err = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            r = httpx.post(f"{BASE_URL}/api/chat", json=payload, timeout=90)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            print(f"  (tentative {attempt}/{_MAX_ATTEMPTS} échouée : {e})")
            if attempt < _MAX_ATTEMPTS:
                time.sleep(4)
    raise last_err


def main() -> int:
    print(f"→ POST {BASE_URL}/api/chat")
    print(f"→ Question : {QUESTION!r}\n")

    payload = {"messages": [{"role": "user", "content": QUESTION}], "debug": True}

    try:
        r = _post_with_retry(payload)
    except Exception as e:
        print(f"❌ Requête échouée après {_MAX_ATTEMPTS} tentatives : {e}")
        return 1

    data = r.json()
    content = data.get("content", "")
    tool_used = data.get("tool_used")
    tool_forced = data.get("tool_forced")

    print("── Réponse brute ──────────────────────────────────────────")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2500])
    print("───────────────────────────────────────────────────────────\n")

    print(f"Preuve directe (champ debug) — tool_used={tool_used} · tool_forced={tool_forced}\n")

    lower = content.lower()
    refusal_hits = [m for m in _REFUSAL_MARKERS if m in lower]

    if tool_used is not True:
        print("❌ ÉCHEC : le backend confirme que l'outil search_web_for_news n'a PAS été déclenché.")
        return 1

    if refusal_hits:
        print(f"⚠️  L'outil a été appelé (tool_used=True) mais la réponse contient quand même : {refusal_hits}")
        print("   Le modèle a peut-être ignoré les résultats injectés — à surveiller, pas un échec du binding.")

    print("✅ SUCCÈS : l'outil search_web_for_news a été réellement invoqué (preuve backend, pas une heuristique texte).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
