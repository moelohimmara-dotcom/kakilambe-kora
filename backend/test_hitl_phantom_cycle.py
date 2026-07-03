"""
test_hitl_phantom_cycle.py — Preuve que la carte HITL "article en attente"
ne reste plus affichée indéfiniment une fois l'article réellement résolu.

Contexte du bug (rapporté par l'utilisateur) : `_get_active_cycle_from_db()`
et `_get_cycle_from_db()` retournaient un cycle PAUSED en base pour toujours,
même après que son article ait été approuvé/rejeté/supprimé directement via
la page Articles (qui ne touche jamais `cycles.status`). Le frontend, qui
interroge /status avec le cycle_id stocké en localStorage, affichait donc
indéfiniment "article en attente" pour un article qui n'existait déjà plus.

Ce test :
1. Crée un cycle PAUSED en base sans aucun article PENDING_REVIEW associé
   (simule un cycle dont l'article a déjà été traité ailleurs).
2. Vérifie que GET /api/agent/status?cycle_id=<ce cycle> ne renvoie PLUS
   PAUSED (donc le frontend n'affiche plus la carte).
3. Vérifie que GET /api/agent/status (sans cycle_id, chemin de reprise de
   session après redémarrage backend) ignore aussi ce cycle fantôme.
4. Contre-preuve : un cycle PAUSED avec un article PENDING_REVIEW réel est
   toujours correctement rapporté comme actif (pas de faux négatif).

Exécution (sur le VPS où vivent les identifiants DB) :
    venv/bin/python test_hitl_phantom_cycle.py
"""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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


async def main():
    from db.connection import get_db
    from sqlalchemy import text
    import requests

    BASE_URL = "http://127.0.0.1:8000"
    phantom_id = str(uuid.uuid4())
    real_id = str(uuid.uuid4())

    print("\n=== test_hitl_phantom_cycle ===\n")

    async with get_db() as db:
        # Cycle fantôme : PAUSED en base, aucun article PENDING_REVIEW.
        await db.execute(
            text("""
                INSERT INTO cycles (id, status, mode, started_at, articles_published,
                                     articles_collected, articles_selected, articles_rejected)
                VALUES (:id, 'PAUSED', 'semi', now(), 0, 0, 0, 0)
            """),
            {"id": phantom_id},
        )
        await db.execute(
            text("""
                INSERT INTO articles (id, cycle_id, titre, corps, status, created_at)
                VALUES (:aid, :cid, 'Article fantôme (déjà résolu)', 'x', 'PUBLISHED', now())
            """),
            {"aid": str(uuid.uuid4()), "cid": phantom_id},
        )

        # Cycle réel : PAUSED avec un article PENDING_REVIEW encore en attente.
        await db.execute(
            text("""
                INSERT INTO cycles (id, status, mode, started_at, articles_published,
                                     articles_collected, articles_selected, articles_rejected)
                VALUES (:id, 'PAUSED', 'semi', now(), 0, 0, 0, 0)
            """),
            {"id": real_id},
        )
        await db.execute(
            text("""
                INSERT INTO articles (id, cycle_id, titre, corps, status, created_at)
                VALUES (:aid, :cid, 'Article réellement en attente', 'x', 'PENDING_REVIEW', now())
            """),
            {"aid": str(uuid.uuid4()), "cid": real_id},
        )

    try:
        print(">> Cas 1 : cycle fantôme (article déjà résolu ailleurs)")
        r = requests.get(f"{BASE_URL}/api/agent/status", params={"cycle_id": phantom_id})
        _check("GET /status -> 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
        status = r.json().get("status")
        _check(
            "status != PAUSED (la carte HITL doit disparaître)",
            status != "PAUSED",
            f"got status={status}",
        )

        print("\n>> Cas 2 : cycle réel (article encore PENDING_REVIEW)")
        r = requests.get(f"{BASE_URL}/api/agent/status", params={"cycle_id": real_id})
        _check("GET /status -> 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
        status = r.json().get("status")
        _check(
            "status == PAUSED (la carte HITL doit rester visible — pas de faux négatif)",
            status == "PAUSED",
            f"got status={status}",
        )

    finally:
        async with get_db() as db:
            await db.execute(text("DELETE FROM articles WHERE cycle_id IN (:a, :b)"), {"a": phantom_id, "b": real_id})
            await db.execute(text("DELETE FROM cycles WHERE id IN (:a, :b)"), {"a": phantom_id, "b": real_id})

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
