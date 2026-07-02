"""
test_v3_sourcing.py — Validation locale du Plan V3 Phase 2 (sources réelles
à deux niveaux, ingestion par lots raw_feeds).

Exécution : python test_v3_sourcing.py
"""
import asyncio
import sys
import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_PASSED = 0
_FAILED = 0


def _check(name: str, ok: bool, detail: str = ""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} — {detail}")


def _fake_db_recording():
    """Simule get_db() et enregistre chaque appel execute() pour inspection."""
    calls = []
    session = AsyncMock()

    async def _record(stmt, params=None):
        calls.append((str(stmt), params))
        result = MagicMock()
        result.mappings.return_value.all.return_value = []
        result.scalar.return_value = None
        return result

    session.execute = AsyncMock(side_effect=_record)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, calls


def test_selector_tier_from_db_levels():
    """_source_tier lit le niveau réel (1 ou 2) depuis rss_sources, pas un set codé en dur."""
    import agent.nodes.selector as selector

    tiers = {"guineenews.org": 1, "africanews.com": 2}
    _check(
        "selector._source_tier: niveau 1 (Guinée) reconnu",
        selector._source_tier("guineenews.org", tiers) == 1,
    )
    _check(
        "selector._source_tier: niveau 2 (panafricain) reconnu",
        selector._source_tier("africanews.com", tiers) == 2,
    )
    _check(
        "selector._source_tier: domaine inconnu -> niveau 3 par défaut",
        selector._source_tier("lemonde.fr", tiers) == 3,
    )


def test_selector_strict_filter_applies_to_level2():
    """
    Changement clé de la Phase 2 : le filtre de pertinence Guinée strict
    s'applique désormais aussi au Niveau 2 (panafricain), pas seulement au
    Niveau 3. Seul le Niveau 1 (Guinée, curé) passe sans condition.
    """
    import agent.nodes.selector as selector

    guinea_article = {"title": "Conakry annonce une réforme", "content": ""}
    off_topic_article = {"title": "Résultats sportifs en Europe", "content": "Un match à Madrid"}

    _check(
        "selector._is_guinea_relevant: détecte un contenu Guinée réel",
        selector._is_guinea_relevant(guinea_article) is True,
    )
    _check(
        "selector._is_guinea_relevant: rejette un contenu hors-sujet",
        selector._is_guinea_relevant(off_topic_article) is False,
    )

    # Reproduit la logique de filtrage réelle de run() : tier <= 1 ou pertinent
    raw = [
        {**guinea_article, "_tier": 1, "url": "https://guineenews.org/a"},       # N1, passe toujours
        {**off_topic_article, "_tier": 2, "url": "https://africanews.com/b"},    # N2 hors-sujet, filtré
        {**guinea_article, "_tier": 2, "url": "https://africanews.com/c"},       # N2 pertinent, passe
    ]
    filtered = [a for a in raw if a["_tier"] <= 1 or selector._is_guinea_relevant(a)]
    _check(
        "selector: filtre strict retire l'article N2 hors-sujet",
        len(filtered) == 2 and all(a["url"] != "https://africanews.com/b" for a in filtered),
        f"got {[a['url'] for a in filtered]}",
    )


async def test_scraper_load_sources_returns_levels():
    """_load_sources_from_db renvoie le niveau de chaque source, pas seulement l'URL."""
    import agent.nodes.scraper as scraper

    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = [
        {"url": "https://guineenews.org/feed/", "source_level": 1},
        {"url": "https://africanews.com/feed/", "source_level": 2},
    ]
    session.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def _ctx():
        yield session

    with patch("agent.nodes.scraper.get_db", _ctx):
        sources = await scraper._load_sources_from_db()

    _check(
        "scraper._load_sources_from_db: renvoie url + level pour chaque source",
        sources == [
            {"url": "https://guineenews.org/feed/", "level": 1},
            {"url": "https://africanews.com/feed/", "level": 2},
        ],
        f"got {sources}",
    )


def test_scraper_domain_of():
    import agent.nodes.scraper as scraper

    _check(
        "scraper._domain_of: extrait le domaine sans www.",
        scraper._domain_of("https://www.guineenews.org/feed/") == "guineenews.org",
    )


async def test_scraper_persist_raw_feeds_inserts_batch():
    """_persist_raw_feeds insère chaque article avec le batch_id = cycle_id."""
    import agent.nodes.scraper as scraper

    ctx, calls = _fake_db_recording()
    articles = [
        {"url": "https://guineenews.org/a", "title": "Titre A", "content": "Contenu A"},
        {"url": "https://africanews.com/b", "title": "Titre B", "markdown_content": "Contenu B"},
    ]
    with patch("agent.nodes.scraper.get_db", ctx):
        await scraper._persist_raw_feeds("cycle-abc", articles)

    _check(
        "scraper._persist_raw_feeds: une insertion par article",
        len(calls) == 2,
        f"got {len(calls)} calls",
    )
    _check(
        "scraper._persist_raw_feeds: batch_id = cycle_id transmis",
        all(c[1]["batch_id"] == "cycle-abc" for c in calls),
    )


async def test_scraper_persist_raw_feeds_survives_db_failure():
    """Une panne DB pendant la persistance raw_feeds ne doit jamais faire échouer le cycle."""
    import agent.nodes.scraper as scraper

    @asynccontextmanager
    async def _broken_db():
        raise RuntimeError("DB down")
        yield  # pragma: no cover

    with patch("agent.nodes.scraper.get_db", _broken_db):
        await scraper._persist_raw_feeds("cycle-abc", [{"url": "https://x.com/a", "title": "t"}])
    _check("scraper._persist_raw_feeds: best-effort, ne lève pas d'exception", True)


async def test_selector_mark_processed_uses_batch_and_urls():
    import agent.nodes.selector as selector

    ctx, calls = _fake_db_recording()
    with patch("agent.nodes.selector.get_db", ctx):
        await selector._mark_raw_feeds_processed("cycle-xyz", ["https://a.com/1", "https://b.com/2"])

    _check(
        "selector._mark_raw_feeds_processed: UPDATE émis avec batch_id + urls",
        len(calls) == 1 and calls[0][1]["batch_id"] == "cycle-xyz" and calls[0][1]["urls"] == ["https://a.com/1", "https://b.com/2"],
        f"got {calls}",
    )


async def test_selector_mark_processed_noop_on_empty_list():
    import agent.nodes.selector as selector

    ctx, calls = _fake_db_recording()
    with patch("agent.nodes.selector.get_db", ctx):
        await selector._mark_raw_feeds_processed("cycle-xyz", [])
    _check(
        "selector._mark_raw_feeds_processed: aucune requête si la liste est vide",
        len(calls) == 0,
    )


async def main():
    print("\n=== test_v3_sourcing — Sources réelles à deux niveaux + ingestion par lots ===\n")
    test_selector_tier_from_db_levels()
    test_selector_strict_filter_applies_to_level2()
    await test_scraper_load_sources_returns_levels()
    test_scraper_domain_of()
    await test_scraper_persist_raw_feeds_inserts_batch()
    await test_scraper_persist_raw_feeds_survives_db_failure()
    await test_selector_mark_processed_uses_batch_and_urls()
    await test_selector_mark_processed_noop_on_empty_list()

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    if _FAILED:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
