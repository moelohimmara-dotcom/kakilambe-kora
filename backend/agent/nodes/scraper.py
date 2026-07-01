"""
NŒUD 1 — scrape_sources
Collecte les articles depuis Tavily (recherche) + Firecrawl (contenu Markdown).
Fallback BrightData si Firecrawl échoue.
Cible : 20 articles collectés.
"""
import asyncio
from typing import List
from agent.state import KoraState
from core.logger import logger
from db.connection import get_db
from sqlalchemy import text


# Requêtes de secours si aucune source RSS n'est configurée en base
_FALLBACK_QUERIES = [
    "actualité Guinée Conakry aujourd'hui",
    "Guinea Conakry news today",
    "Afrique de l'Ouest dernières nouvelles",
]


async def _load_sources_from_db() -> list[str]:
    """Charge les URLs RSS actives depuis la table rss_sources."""
    try:
        async with get_db() as db:
            result = await db.execute(
                text("SELECT url FROM rss_sources WHERE is_active = true ORDER BY name")
            )
            rows = result.mappings().all()
        urls = [r["url"] for r in rows if r["url"]]
        return urls
    except Exception as e:
        logger.warning("scraper_db_sources_failed", error=str(e))
        return []

_MAX_ARTICLES = 8      # réduit pour free tier (mémoire 512MB)
_SCRAPE_TIMEOUT = 15   # secondes par URL
_ENRICH_CONCURRENCY = 4  # max requêtes Firecrawl simultanées


async def _fetch_content(url: str) -> str:
    """Récupère le contenu Markdown d'une URL via Firecrawl, fallback BrightData."""
    from integrations.firecrawl_client import firecrawl_client
    from integrations.brightdata_client import brightdata_client

    content = await asyncio.wait_for(
        firecrawl_client.scrape(url), timeout=_SCRAPE_TIMEOUT
    )
    if content and len(content.strip()) > 200:
        return content

    # Fallback BrightData
    logger.warning("firecrawl_fallback", url=url)
    html = await asyncio.wait_for(
        brightdata_client.fetch(url), timeout=_SCRAPE_TIMEOUT
    )
    return html or ""


async def run(state: KoraState) -> KoraState:
    logger.info("node_scraper_start", cycle_id=state["cycle_id"])

    from integrations.tavily_client import tavily_client

    all_results: List[dict] = []

    # 1a. Sources RSS depuis la DB (si configurées)
    db_sources = await _load_sources_from_db()
    if db_sources:
        logger.info("scraper_using_db_sources", count=len(db_sources))
        for url in db_sources:
            try:
                results = await tavily_client.search(
                    f"site:{url.split('/')[2]} actualité Guinée",
                    max_results=4,
                )
                all_results.extend(results)
            except Exception as e:
                logger.warning("tavily_source_failed", url=url, error=str(e))
    else:
        logger.info("scraper_using_fallback_queries")

    # 1b. Requêtes de secours (toujours exécutées pour compléter le volume)
    queries = _FALLBACK_QUERIES if not db_sources else _FALLBACK_QUERIES[:1]
    for query in queries:
        try:
            results = await tavily_client.search(query, max_results=5)
            all_results.extend(results)
        except Exception as e:
            logger.warning("tavily_query_failed", query=query, error=str(e))
            state["errors"].append(f"Tavily: {query} — {e}")

    # Dédoublonnage par URL
    seen: set = set()
    unique: List[dict] = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)

    unique = unique[:_MAX_ARTICLES]

    # 2. Enrichissement Markdown via Firecrawl (niveau 2 : contenu complet)
    async def enrich(article: dict) -> dict:
        url = article.get("url", "")
        if not url:
            return article
        try:
            content = await _fetch_content(url)
            article["markdown_content"] = content
        except asyncio.TimeoutError:
            logger.warning("scrape_timeout", url=url)
            article["markdown_content"] = article.get("content", "")
        except Exception as e:
            logger.warning("scrape_error", url=url, error=str(e))
            article["markdown_content"] = article.get("content", "")
        return article

    # Enrichissement séquentiel par batch pour limiter la consommation mémoire
    semaphore = asyncio.Semaphore(_ENRICH_CONCURRENCY)

    async def enrich_limited(article: dict) -> dict:
        async with semaphore:
            return await enrich(article)

    enriched = await asyncio.gather(*[enrich_limited(a) for a in unique])

    # Filtre : garder uniquement les articles avec contenu substantiel
    valid = [
        a for a in enriched
        if len((a.get("markdown_content") or a.get("content", "")).strip()) > 300
    ]

    logger.info(
        "node_scraper_done",
        cycle_id=state["cycle_id"],
        total_found=len(all_results),
        unique=len(unique),
        valid=len(valid),
    )

    return {**state, "raw_sources": valid}
