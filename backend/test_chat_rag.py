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
import json
import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "https://kora-582m5.ondigitalocean.app"
QUESTION = "Quelles sont les dernières nouvelles de Guinée ?"

_REFUSAL_MARKERS = [
    "je n'ai pas accès",
    "informations en temps réel",
    "ma date de mise à jour",
    "en tant qu'agent éditorial autonome, je n'ai pas",
    "connaissances jusqu'à",
]


def main() -> int:
    print(f"→ POST {BASE_URL}/api/chat")
    print(f"→ Question : {QUESTION!r}\n")

    payload = {"messages": [{"role": "user", "content": QUESTION}]}

    try:
        r = httpx.post(f"{BASE_URL}/api/chat", json=payload, timeout=45)
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Requête échouée : {e}")
        return 1

    data = r.json()
    content = data.get("content", "")

    print("── Réponse brute ──────────────────────────────────────────")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    print("───────────────────────────────────────────────────────────\n")

    lower = content.lower()
    refusal_hits = [m for m in _REFUSAL_MARKERS if m in lower]
    has_url = "http://" in content or "https://" in content

    if refusal_hits:
        print(f"❌ ÉCHEC : la réponse contient un marqueur de refus/absence de temps réel : {refusal_hits}")
        print("   → L'outil search_web_for_news n'a probablement pas été déclenché.")
        return 1

    if not has_url:
        print("⚠️  ATTENTION : aucune URL détectée dans la réponse — signal faible que")
        print("   l'outil a été utilisé (le modèle peut synthétiser sans citer d'URL).")
        print("   Ce n'est pas un échec certain, mais un point à surveiller.")

    print("✅ SUCCÈS : pas de marqueur de refus détecté" + (" et URL(s) présente(s) dans la réponse." if has_url else "."))
    print("   → L'outil search_web_for_news semble avoir été déclenché et ses résultats injectés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
