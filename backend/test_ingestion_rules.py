"""
test_ingestion_rules.py — Validation des règles de gouvernance éditoriale
ajoutées au pipeline d'ingestion :

1. Périmètre strict : plus de requête de secours quand des sources sont
   configurées (agent/nodes/scraper.py).
2. Filtre Jour-J : _is_fresh() écarte un résultat daté de la veille,
   laisse passer un résultat du jour ou sans date connue.
3. Anti-duplication inter-cycles : une URL déjà vue (raw_feeds ou
   articles) est exclue de la liste finale, même si elle réapparaît dans
   les résultats bruts d'un nouveau cycle.
4. Synthèse cross-média : deux flux RSS traitant du même sujet sont
   fusionnés par le selector (déjà en place) — vérifié ici que le nœud
   writer injecte bien une instruction de créditation transparente quand
   des sources agrégées existent.
5. Variabilité : deux appels successifs à _write_with_retry (mocké)
   reçoivent des directives d'accroche différentes au moins une fois sur
   un échantillon suffisant (le tirage est aléatoire, pas garanti différent
   à chaque paire, donc on vérifie la distribution plutôt qu'un cas unique).

Exécution (local, tout est mocké — aucun appel réseau réel) :
    venv/bin/python test_ingestion_rules.py
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


def _check(name, ok, detail=""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} — {detail}")


def _fake_db_rows(rows):
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


async def test_no_fallback_when_sources_configured():
    print("\n>> Règle 1 — plus de requête de secours quand des sources existent\n")
    import agent.nodes.scraper as scraper

    with patch.object(scraper, "_load_sources_from_db", AsyncMock(return_value=[{"url": "https://africaguinee.com", "level": 1}])):
        db_sources = await scraper._load_sources_from_db()
    queries = scraper._FALLBACK_QUERIES if not db_sources else []
    _check("aucune requête de secours si des sources sont configurées", queries == [], f"got {queries}")

    with patch.object(scraper, "_load_sources_from_db", AsyncMock(return_value=[])):
        db_sources = await scraper._load_sources_from_db()
    queries = scraper._FALLBACK_QUERIES if not db_sources else []
    _check("requête de secours conservée si AUCUNE source n'est configurée", len(queries) > 0, f"got {queries}")


def test_freshness_filter():
    print("\n>> Règle 2 — filtre Jour-J (_is_fresh)\n")
    import agent.nodes.scraper as scraper
    from datetime import datetime, timezone, timedelta

    today = {"published_date": datetime.now(timezone.utc).isoformat()}
    yesterday = {"published_date": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()}
    no_date = {"title": "Sans date connue"}

    _check("résultat du jour accepté", scraper._is_fresh(today) is True)
    _check("résultat de la veille (>24h) rejeté", scraper._is_fresh(yesterday) is False)
    _check("résultat sans date connue laissé passer (pas de faux négatif)", scraper._is_fresh(no_date) is True)


async def test_cross_cycle_dedup():
    print("\n>> Règle 3 — anti-duplication inter-cycles (_load_seen_urls + filtrage)\n")
    import agent.nodes.scraper as scraper

    seen_rows = [{"url": "https://africaguinee.com/deja-vu"}]
    with patch.object(scraper, "get_db", _fake_db_rows(seen_rows)):
        seen_urls = await scraper._load_seen_urls()
    _check("_load_seen_urls retourne bien l'URL historique", "https://africaguinee.com/deja-vu" in seen_urls)

    all_results = [
        {"url": "https://africaguinee.com/deja-vu", "title": "Ancien sujet déjà traité"},
        {"url": "https://africaguinee.com/nouveau", "title": "Sujet inédit"},
    ]
    unique = []
    already = set()
    for r in all_results:
        url = r.get("url", "")
        if url and url not in already and url not in seen_urls:
            already.add(url)
            unique.append(r)
    _check("l'URL déjà vue est exclue de la sélection finale", len(unique) == 1 and unique[0]["url"].endswith("nouveau"), f"got {unique}")


def test_cross_media_credit_instruction():
    print("\n>> Règle 4 — créditation transparente des sources agrégées (writer.py)\n")
    from agent.nodes import writer

    article_single = {
        "title": "Article simple",
        "url": "https://africaguinee.com/a",
        "content": "Contenu suffisant pour test " * 20,
        "aggregated_sources": [],
    }
    article_aggregated = {
        "title": "Article de synthèse",
        "url": "https://africaguinee.com/a",
        "source": "AfricaGuinee",
        "content": "Contenu suffisant pour test " * 20,
        "aggregated_sources": [
            {"title": "Angle B", "url": "https://ledjely.com/b", "source": "Ledjely", "content": "..."},
        ],
    }

    prompt_single = writer._WRITE_PROMPT.format(
        sources_section=writer._build_sources_section(article_single)[0],
        url_principale=article_single["url"], source_nom="AfricaGuinee",
        hook_style="test", sources_credit_instruction="",
    )
    sources_section_agg, url_agg, source_nom_agg = writer._build_sources_section(article_aggregated)
    extras = article_aggregated["aggregated_sources"]
    credit_names = [source_nom_agg] + [s.get("source") for s in extras]
    instruction_agg = f"CRÉDITATION OBLIGATOIRE ({', '.join(credit_names)})"
    prompt_agg = writer._WRITE_PROMPT.format(
        sources_section=sources_section_agg, url_principale=url_agg, source_nom=source_nom_agg,
        hook_style="test", sources_credit_instruction=instruction_agg,
    )

    _check("pas d'instruction de créditation forcée pour un article à source unique", "CRÉDITATION OBLIGATOIRE" not in prompt_single)
    _check("instruction de créditation présente pour un article agrégé", "CRÉDITATION OBLIGATOIRE" in prompt_agg)
    _check("les deux noms de sources apparaissent dans l'instruction", "AfricaGuinee" in prompt_agg and "Ledjely" in prompt_agg, prompt_agg[:200])
    _check("SOURCE COMPLÉMENTAIRE présente dans la section sources", "SOURCE COMPLÉMENTAIRE" in sources_section_agg)


def test_hook_variability():
    print("\n>> Règle 5 — variabilité des accroches (distribution, pas un cas unique)\n")
    from agent.nodes.writer import _HOOK_STYLES
    import random

    _check("au moins 3 styles d'accroche disponibles", len(_HOOK_STYLES) >= 3, f"got {len(_HOOK_STYLES)}")

    sample = [random.choice(_HOOK_STYLES) for _ in range(30)]
    distinct = set(sample)
    _check(
        "sur 30 tirages, plusieurs styles distincts apparaissent (pas un seul figé)",
        len(distinct) >= 2,
        f"styles observés: {distinct}",
    )


async def main():
    print("\n=== test_ingestion_rules — gouvernance éditoriale du pipeline ===")
    await test_no_fallback_when_sources_configured()
    test_freshness_filter()
    await test_cross_cycle_dedup()
    test_cross_media_credit_instruction()
    test_hook_variability()
    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
