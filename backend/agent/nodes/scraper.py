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


def _domain_of(url: str) -> str:
    try:
        return url.split("/")[2].replace("www.", "").lower()
    except IndexError:
        return ""


async def _load_sources_from_db() -> list[dict]:
    """Charge les sources actives depuis rss_sources, avec leur niveau (1=Guinée, 2=Panafricain)."""
    try:
        async with get_db() as db:
            result = await db.execute(
                text("SELECT url, source_level FROM rss_sources WHERE is_active = true ORDER BY source_level, name")
            )
            rows = result.mappings().all()
        return [{"url": r["url"], "level": r["source_level"]} for r in rows if r["url"]]
    except Exception as e:
        logger.warning("scraper_db_sources_failed", error=str(e))
        return []


async def _persist_raw_feeds(batch_id: str, articles: list[dict]) -> None:
    """
    Journalise le lot brut ingéré dans raw_feeds — traçabilité de chaque
    cycle et base pour un futur dédoublonnage inter-cycles. Best-effort :
    une panne d'écriture ici ne doit jamais faire échouer le cycle.
    """
    if not articles:
        return
    try:
        async with get_db() as db:
            for a in articles:
                await db.execute(
                    text("""
                        INSERT INTO raw_feeds (batch_id, source_url, source_name, title, content)
                        VALUES (:batch_id, :source_url, :source_name, :title, :content)
                    """),
                    {
                        "batch_id": batch_id,
                        "source_url": a.get("url", ""),
                        "source_name": _domain_of(a.get("url", "")),
                        "title": (a.get("title") or "")[:500],
                        "content": (a.get("markdown_content") or a.get("content", ""))[:5000],
                    },
                )
    except Exception as e:
        logger.warning("scraper_raw_feeds_persist_failed", batch_id=batch_id, error=str(e))

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

    # 1a. Sources réelles depuis la DB — Niveau 1 (Guinée) sondé plus large
    # que Niveau 2 (Panafricain), conformément à la priorité éditoriale
    # appliquée ensuite par le selector (filtre de pertinence strict sur N2).
    db_sources = await _load_sources_from_db()
    if db_sources:
        logger.info(
            "scraper_using_db_sources",
            count=len(db_sources),
            level1=sum(1 for s in db_sources if s["level"] == 1),
            level2=sum(1 for s in db_sources if s["level"] == 2),
        )
        for source in db_sources:
            url = source["url"]
            max_results = 4 if source["level"] == 1 else 2
            try:
                results = await tavily_client.search(
                    f"site:{_domain_of(url)} actualité Guinée",
                    max_results=max_results,
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

    await _persist_raw_feeds(state["cycle_id"], valid)

    logger.info(
        "node_scraper_done",
        cycle_id=state["cycle_id"],
        total_found=len(all_results),
        unique=len(unique),
        valid=len(valid),
    )

    return {**state, "raw_sources": valid}
