"""
test_qstash_integration.py — Validation de l'envoi de messages vers Upstash QStash.

Contrainte d'environnement : le SDK officiel `qstash` ne peut pas être installé
dans ce sandbox (interception SSL du proxy réseau local empêche pip d'atteindre
PyPI). Ce script utilise donc l'API REST QStash directement via httpx pour
prouver l'envoi réel — le SDK sera installé normalement lors du build
DigitalOcean (environnement sans cette restriction).

Usage : QSTASH_TOKEN=... python test_qstash_integration.py [destination_url]
"""
import os
import sys
import json
import httpx

QSTASH_TOKEN = os.environ.get("QSTASH_TOKEN", "")
QSTASH_BASE = os.environ.get("QSTASH_URL", "https://qstash.upstash.io")
QSTASH_PUBLISH_URL = f"{QSTASH_BASE.rstrip('/')}/v2/publish/"

# Destination par défaut : httpbin echo, pour prouver l'envoi QStash lui-même
# indépendamment de l'état de déploiement du webhook KORA.
DESTINATION = sys.argv[1] if len(sys.argv) > 1 else "https://httpbin.org/post"


def main() -> int:
    if not QSTASH_TOKEN:
        print("❌ QSTASH_TOKEN non défini dans l'environnement.")
        return 1

    print(f"→ POST {QSTASH_PUBLISH_URL}{DESTINATION}")
    print(f"→ Corps : test message factice KORA/QStash\n")

    try:
        r = httpx.post(
            f"{QSTASH_PUBLISH_URL}{DESTINATION}",
            headers={
                "Authorization": f"Bearer {QSTASH_TOKEN}",
                "Content-Type": "application/json",
                "Upstash-Delay": "5s",
            },
            json={"source": "test_qstash_integration.py", "purpose": "validation KORA"},
            timeout=20,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Échec de l'envoi vers QStash : {e}")
        return 1

    data = r.json()
    print("── Réponse QStash ─────────────────────────────────────────")
    print(json.dumps(data, indent=2))
    print("──────────────────────────────────────────────────────────\n")

    message_id = data.get("messageId")
    if not message_id:
        print("❌ ÉCHEC : pas de messageId dans la réponse — le message n'a probablement pas été accepté.")
        return 1

    print(f"✅ SUCCÈS : message accepté par QStash, messageId={message_id}")
    print("   Vérifie le dashboard Upstash (onglet Messages/Logs) pour confirmer la réception.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
