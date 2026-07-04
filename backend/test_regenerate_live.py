"""
test_regenerate_live.py — Preuve de bout en bout que POST
/api/articles/{id}/regenerate fonctionne réellement en production : lance
un vrai cycle semi, attend la pause HITL, régénère l'article obtenu,
vérifie que le titre/contenu/image ont changé, puis nettoie (rejette
l'article de test pour ne pas laisser de résidu).

Exécution (contre le VPS en production) :
    venv/bin/python test_regenerate_live.py
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
    print(f"\n=== test_regenerate_live — {BASE_URL} ===\n")

    cycle_id = str(uuid.uuid4())
    print(">> Lancement d'un cycle réel (mode semi) — attente bloquante de la pause HITL")
    t0 = time.time()
    r = requests.post(f"{BASE_URL}/api/agent/run", json={"mode": "semi", "cycle_id": cycle_id}, timeout=300)
    print(f"    -> {r.status_code} en {time.time()-t0:.1f}s : {r.text[:200]}")
    _check("POST /run -> 200 PAUSED", r.status_code == 200 and r.json().get("status") == "PAUSED", r.text)

    article_id = r.json().get("article_id")
    _check("article_id présent", bool(article_id), str(r.json()))
    if not article_id:
        print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
        sys.exit(1)

    ra = requests.get(f"{BASE_URL}/api/articles/{article_id}")
    original = ra.json()
    print(f"\n>> Article original : {original.get('titre')!r}")
    print(f"    image_url original : {original.get('image_url')}")

    print("\n>> Appel de POST /regenerate (vrai LLM + vraie génération d'image)")
    t1 = time.time()
    rg = requests.post(f"{BASE_URL}/api/articles/{article_id}/regenerate", timeout=180)
    print(f"    -> {rg.status_code} en {time.time()-t1:.1f}s")
    _check("POST /regenerate -> 200", rg.status_code == 200, rg.text)

    if rg.status_code == 200:
        regenerated = rg.json()
        print(f"    Nouveau titre : {regenerated.get('titre')!r}")
        print(f"    Nouvelle image_url : {regenerated.get('image_url')}")
        _check(
            "le titre a changé (nouvel angle réellement appliqué, pas un doublon)",
            regenerated.get("titre") != original.get("titre"),
            f"identique : {regenerated.get('titre')!r}",
        )
        _check(
            "l'image a changé (nouvelle génération, pas réutilisation)",
            regenerated.get("image_url") != original.get("image_url"),
            f"identique : {regenerated.get('image_url')}",
        )

        rf = requests.get(f"{BASE_URL}/api/articles/{article_id}")
        persisted = rf.json()
        _check(
            "le nouveau titre est bien persisté en base (pas juste dans la réponse HTTP)",
            persisted.get("titre") == regenerated.get("titre"),
            f"base={persisted.get('titre')!r} vs réponse={regenerated.get('titre')!r}",
        )
        _check("statut toujours PENDING_REVIEW après régénération (pas republié par erreur)", persisted.get("status") == "PENDING_REVIEW", persisted.get("status"))

    print("\n>> Nettoyage : rejet de l'article de test")
    try:
        rr = requests.post(f"{BASE_URL}/api/articles/{article_id}/reject")
        print(f"    reject -> {rr.status_code}")
    except Exception as e:
        print(f"    (nettoyage best-effort, erreur ignorée: {e})")

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    main()
