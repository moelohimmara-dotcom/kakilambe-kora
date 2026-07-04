"""
test_agent_cancel_live.py — Mesure réelle de la latence d'annulation d'un
cycle EN COURS D'EXÉCUTION (pas déjà en pause) et vérifie l'absence de
ligne orpheline dans `articles` (le cycle est annulé pendant le scraping,
donc avant toute écriture d'article — cf. writer.py:_save_to_db appelé
seulement après rédaction complète).

Exécution (contre le VPS en production) :
    venv/bin/python test_agent_cancel_live.py
"""
import time
import uuid
import sys
import threading
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
    print(f"\n=== test_agent_cancel_live — {BASE_URL} ===\n")

    cycle_id = str(uuid.uuid4())
    run_result = {}

    def _run_blocking_call():
        try:
            r = requests.post(
                f"{BASE_URL}/api/agent/run",
                json={"mode": "semi", "cycle_id": cycle_id},
                timeout=300,
            )
            run_result["status_code"] = r.status_code
            run_result["body"] = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
        except Exception as e:
            run_result["error"] = str(e)

    print(">> Lancement du cycle en arrière-plan (thread séparé, requête bloquante réelle)")
    t = threading.Thread(target=_run_blocking_call, daemon=True)
    t.start()

    print(">> Attente de 4s pour laisser le scraping démarrer réellement (appels Tavily en vol)")
    time.sleep(4)

    print(">> Annulation pendant le scraping actif")
    t0 = time.time()
    rc = requests.post(f"{BASE_URL}/api/agent/cancel/{cycle_id}", timeout=10)
    cancel_elapsed = time.time() - t0
    print(f"    cancel -> {rc.status_code} en {cancel_elapsed*1000:.0f}ms : {rc.text}")

    _check("POST /cancel répond rapidement (<2s, objectif <500ms réseau+DB)", cancel_elapsed < 2, f"{cancel_elapsed:.2f}s")
    _check("POST /cancel -> 200", rc.status_code == 200, f"got {rc.status_code}")

    print(">> Attente de la fin du thread /run (doit se terminer vite après l'annulation, pas tourner 2-3 min)")
    t.join(timeout=15)
    _check("Le thread /run s'est terminé rapidement après cancel (<15s), pas resté bloqué en arrière-plan", not t.is_alive(), "thread encore actif après 15s")
    print(f"    /run a répondu : {run_result}")

    print("\n>> Vérification base : aucune ligne articles orpheline pour ce cycle_id (annulé avant rédaction)")
    ra = requests.get(f"{BASE_URL}/api/articles", params={"page": 1})
    items = ra.json().get("items", [])
    orphan = [a for a in items if a.get("cycle_id") == cycle_id]
    _check("Aucun article créé pour ce cycle annulé pendant le scraping", len(orphan) == 0, f"trouvé {len(orphan)} article(s) — inattendu")

    print(f"\n>> Vérification finale du statut du cycle")
    rs = requests.get(f"{BASE_URL}/api/agent/status", params={"cycle_id": cycle_id})
    print(f"    status={rs.json()}")
    _check("status final == CANCELLED", rs.json().get("status") == "CANCELLED", f"got {rs.json().get('status')}")

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    main()
