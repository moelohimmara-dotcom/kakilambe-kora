"""
test_scheduler_mode.py — Preuve que le cycle programmé (cron) respecte
désormais le réglage de publication du dashboard au lieu de forcer "auto".

Partie A (unitaire, DB mockée) : _get_configured_mode() résout le mode
correctement (auto si auto_publish_enabled=true, semi sinon, semi si la DB
échoue).

Partie B (intégration réelle, LLM + DB) : force le mode semi et invoque
kora_graph_semi exactement comme le scheduler le fait, puis vérifie que le
graphe s'interrompt avant publication — 0 article publié, article(s) en
PENDING_REVIEW, aucune URL WordPress, rien envoyé au site live.

Exécution (sur le VPS où vivent les clés API/DB) :
    venv/bin/python test_scheduler_mode.py
"""
import asyncio
import sys
import os
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

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


def _fake_db(row):
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


async def part_a_unit():
    print("\n>> Partie A — décision du mode (unitaire)\n")
    import core.scheduler as scheduler

    with patch("db.connection.get_db", _fake_db({"value": "true"})):
        mode = await scheduler._get_configured_mode()
    _check("auto_publish_enabled='true' → mode 'auto'", mode == "auto", f"got {mode}")

    with patch("db.connection.get_db", _fake_db({"value": "False"})):
        mode = await scheduler._get_configured_mode()
    _check("auto_publish_enabled='False' → mode 'semi'", mode == "semi", f"got {mode}")

    with patch("db.connection.get_db", _fake_db(None)):
        mode = await scheduler._get_configured_mode()
    _check("clé absente → mode 'semi' (défaut sûr)", mode == "semi", f"got {mode}")

    @asynccontextmanager
    async def _broken():
        raise RuntimeError("DB down")
        yield  # pragma: no cover

    with patch("db.connection.get_db", _broken):
        mode = await scheduler._get_configured_mode()
    _check("panne DB → mode 'semi' (repli de sécurité)", mode == "semi", f"got {mode}")


async def part_b_integration():
    print("\n>> Partie B — cycle semi réel : interruption avant publication\n")
    from agent.graph import kora_graph_semi
    from db.connection import get_db
    from sqlalchemy import text

    # cycle_id DOIT être un UUID valide : articles.cycle_id est de type UUID
    # en base (le vrai scheduler passe toujours str(uuid.uuid4())).
    cycle_id = str(uuid.uuid4())

    result = await kora_graph_semi.ainvoke(
        {"mode": "semi", "cycle_id": cycle_id, "published_count": 0, "errors": [],
         "hitl_approved": False, "raw_sources": [], "selected_articles": [],
         "current_article": None, "generated_article": None,
         "image_url": None, "wp_media_id": None, "wp_post_id": None,
         "article_index": 0},
        config={"configurable": {"thread_id": cycle_id}},
    )

    published = result.get("published_count", 0) if result else 0
    _check("published_count == 0 (rien publié en semi)", published == 0, f"got {published}")

    async with get_db() as db:
        r = await db.execute(
            text("SELECT status, wp_url FROM articles WHERE cycle_id = :cid"),
            {"cid": cycle_id},
        )
        rows = r.mappings().all()

    _check("au moins un article créé par le cycle", len(rows) >= 1, f"got {len(rows)}")
    _check(
        "tous les articles en PENDING_REVIEW (aucun PUBLISHED)",
        all(row["status"] == "PENDING_REVIEW" for row in rows),
        f"statuts: {[row['status'] for row in rows]}",
    )
    _check(
        "aucune URL WordPress (rien envoyé au site live)",
        all(not row["wp_url"] for row in rows),
        f"wp_urls: {[row['wp_url'] for row in rows]}",
    )


async def main():
    print("\n=== test_scheduler_mode — respect du réglage de publication par le cron ===")
    await part_a_unit()
    await part_b_integration()
    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
