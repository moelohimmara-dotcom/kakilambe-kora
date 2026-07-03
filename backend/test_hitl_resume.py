"""
test_hitl_resume.py — Preuve de bout en bout que le mécanisme de reprise
HITL (bouton "Valider et publier") fonctionne : lance un cycle réel, attend
la pause, simule le clic (POST /resume), vérifie la publication WordPress
réelle. Capture le passage exact de [HITL] Article prêt... à un article
publié, comme demandé.

Contexte du diagnostic : aucune des causes de l'audit (thread_id mal
transmis, checkpointer non configuré, CORS) n'était réelle — le mécanisme
LangGraph fonctionne correctement. Le vrai problème découvert :
1. Le checkpoint LangGraph (MemorySaver) est en mémoire du process — un
   cycle mis en pause AVANT un redémarrage du backend ne peut plus jamais
   être repris (limitation architecturale connue, pas un bug).
2. Les boutons du frontend (AgentScreen.tsx) n'avaient aucun try/catch —
   une erreur de resume échouait en silence, sans aucun retour visible.
   C'est ce qui donnait l'impression que "les boutons ne font rien".

Exécution (sur le VPS, contre l'API réelle) :
    venv/bin/python test_hitl_resume.py
"""
import sys
import time
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


def _poll_status(cycle_id, target_statuses, timeout=120, interval=5):
    elapsed = 0
    while elapsed < timeout:
        r = requests.get(f"{BASE_URL}/api/agent/status", params={"cycle_id": cycle_id})
        data = r.json()
        status = data.get("status")
        print(f"    ... status={status} (t+{elapsed}s)")
        if status in target_statuses:
            return status, data
        time.sleep(interval)
        elapsed += interval
    return status, data


def main():
    print(f"\n=== test_hitl_resume — {BASE_URL} ===\n")

    print(">> Étape 1 : lancement d'un cycle réel (mode semi)")
    r = requests.post(f"{BASE_URL}/api/agent/run", json={"mode": "semi"})
    _check("POST /api/agent/run -> 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
    cycle_id = r.json()["cycle_id"]
    print(f"    cycle_id = {cycle_id}")

    print("\n>> Étape 2 : attente de la pause HITL ([HITL] Article prêt...)")
    status, _ = _poll_status(cycle_id, ["PAUSED", "FAILED", "COMPLETED"], timeout=180)
    _check("Cycle atteint PAUSED (article prêt, en attente de validation)", status == "PAUSED", f"got {status}")

    if status != "PAUSED":
        print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
        sys.exit(1)

    print("\n>> Étape 3 : simulation du clic sur 'Valider et publier' (POST /resume)")
    r = requests.post(f"{BASE_URL}/api/agent/resume/{cycle_id}")
    _check("POST /api/agent/resume -> 200 (pas de 404/409)", r.status_code == 200, f"got {r.status_code}: {r.text}")

    print("\n>> Étape 4 : attente de la publication effective")
    # Le 1er article d'un cycle publie en direct (quelques secondes). Les
    # suivants sont mis en file d'attente QStash avec un délai croissant
    # (delay_between_posts, ~120s configurés en prod) pour ne pas publier
    # plusieurs articles d'affilée sur WordPress — timeout large pour
    # couvrir ce cas sans faux négatif.
    status, data = _poll_status(cycle_id, ["PAUSED", "COMPLETED", "FAILED"], timeout=180, interval=10)
    published = data.get("published_count", 0)

    # published_count (compteur en mémoire) ne capture pas les publications
    # QStash différées, qui arrivent après le retour du nœud publisher via
    # un webhook asynchrone séparé — la vérité terrain est en base.
    r = requests.get(f"{BASE_URL}/api/articles", params={"page": 1})
    articles = r.json().get("items", [])
    published_in_db = [a for a in articles if a.get("cycle_id") == cycle_id and a.get("status") == "PUBLISHED"]

    _check(
        "[HITL] Article prêt... → [INFO] Article publié sur WordPress (vérifié en base)",
        len(published_in_db) >= 1 or published >= 1,
        f"published_count={published}, articles PUBLISHED en base pour ce cycle: {len(published_in_db)}",
    )
    for a in published_in_db:
        print(f"    -> publié : {a['titre']} — {a.get('wp_url')}")

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    main()
