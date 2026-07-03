"""
test_agent_run_blocking.py — Preuve que POST /api/agent/run est désormais
bloquant : la réponse HTTP n'arrive qu'une fois le cycle réellement à la
pause HITL, avec un article_id exploitable pour une redirection immédiate.

Exécution (contre le VPS en production, mode semi — jamais de publication
réelle) :
    venv/bin/python test_agent_run_blocking.py
"""
import time
import uuid
import sys
import requests

BASE_URL = "http://213.156.135.139"

_PASSED = 0
_FAILED = 0


def _check(name, ok, detail=""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} — {detail}")


def main():
    print(f"\n=== test_agent_run_blocking — {BASE_URL} ===\n")

    cycle_id = str(uuid.uuid4())
    print(f">> POST /api/agent/run (mode=semi, cycle_id={cycle_id[:8]}...) — attente bloquante")
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/agent/run",
        json={"mode": "semi", "cycle_id": cycle_id},
        timeout=300,
    )
    elapsed = time.time() - t0
    print(f"    -> réponse reçue après {elapsed:.1f}s")

    _check("POST /run -> 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
    data = r.json()
    print(f"    body: {data}")

    _check(
        "La requête a réellement bloqué (pas de retour quasi-instantané)",
        elapsed > 3,
        f"elapsed={elapsed:.1f}s — devrait refléter un vrai cycle (scraping+LLM), pas un aller-retour immédiat",
    )
    _check("status == PAUSED (interruption HITL avant publication)", data.get("status") == "PAUSED", f"got {data.get('status')}")
    article_id = data.get("article_id")
    _check("article_id présent dans la réponse", bool(article_id), f"got {article_id!r}")

    if article_id:
        print(f"\n>> Vérification de l'article {article_id} en base")
        ra = requests.get(f"{BASE_URL}/api/articles", params={"page": 1})
        items = ra.json().get("items", [])
        match = next((a for a in items if a.get("id") == article_id), None)
        _check("article_id correspond à un article réel en base", match is not None, f"non trouvé parmi {len(items)} articles récents")
        if match:
            _check(
                "article en PENDING_REVIEW (pas publié malgré le cycle terminé côté HTTP)",
                match.get("status") == "PENDING_REVIEW",
                f"got status={match.get('status')}",
            )
            print(f"    -> {match.get('titre')}")

    # Nettoyage : annule le cycle pour ne pas laisser d'article de test
    # traîner indéfiniment en PENDING_REVIEW.
    print(f"\n>> Nettoyage : annulation du cycle de test")
    try:
        rc = requests.post(f"{BASE_URL}/api/agent/cancel/{cycle_id}")
        print(f"    cancel -> {rc.status_code}: {rc.text}")
        if article_id:
            rr = requests.post(f"{BASE_URL}/api/articles/{article_id}/reject")
            print(f"    reject article -> {rr.status_code}")
    except Exception as e:
        print(f"    (nettoyage best-effort, erreur ignorée: {e})")

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    main()
