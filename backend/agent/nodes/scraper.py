"""
NŒUD 1 — scrape_sources
Collecte les articles depuis Tavily (recherche) + Firecrawl (contenu Markdown).
BrightData abandonné (décision explicite) : si Firecrawl échoue, l'article
retombe sur l'extrait brut déjà fourni par Tavily (cf. enrich()) plutôt que
sur un second scraper.
Cible : 20 articles collectés.

Périmètre strict (gouvernance éditoriale) :
- Focalisation exclusive sur les sources officielles configurées
  (rss_sources) — la requête de secours n'est utilisée QUE si aucune
  source active n'existe en base, jamais en complément de sources réelles.
- Fraîcheur Jour-J : Tavily interrogé avec topic="news" + days=1, et un
  second filtre défensif sur published_date écarte tout résultat non daté
  d'aujourd'hui quand cette information est disponible.
- Anti-duplication inter-cycles : toute URL déjà ingérée (raw_feeds, tous
  cycles confondus) ou déjà transformée en article (articles.source_url)
  est exclue avant même l'enrichissement — jamais retraitée.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List
from agent.state import KoraState
from core.cycle_events import emit_log
from core.logger import logger
from db.connection import get_db
from sqlalchemy import text


# Requête de secours — utilisée UNIQUEMENT si aucune source RSS active
# n'est configurée en base (sinon le cycle n'aurait tout simplement aucun
# candidat). Jamais lancée en complément de sources réelles configurées.
_FALLBACK_QUERIES = [
    "actualité Guinée Conakry aujourd'hui",
    "Guinea Conakry news today",
    "Afrique de l'Ouest dernières nouvelles",
]

_FRESHNESS_WINDOW = timedelta(hours=24)


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


async def _load_seen_urls() -> set:
    """
    URLs déjà exploitées lors d'un cycle précédent (raw_feeds, tous batch_id
    confondus) ou déjà transformées en article publié/rédigé (articles) —
    barrière anti-duplication inter-cycles. Best-effort : une panne ici ne
    doit jamais bloquer un cycle, au pire on retraite une source déjà vue.
    """
    try:
        async with get_db() as db:
            result = await db.execute(
                text("""
                    SELECT source_url AS url FROM raw_feeds WHERE source_url IS NOT NULL
                    UNION
                    SELECT source_url AS url FROM articles WHERE source_url IS NOT NULL
                """)
            )
            return {r["url"] for r in result.mappings().all() if r["url"]}
    except Exception as e:
        logger.warning("scraper_seen_urls_failed", error=str(e))
        return set()


def _is_fresh(result: dict) -> bool:
    """
    Écarte un résultat dont la date de publication Tavily (published_date,
    présent quand topic="news") est antérieure à la fenêtre Jour-J. Absence
    de date : on laisse passer (site: scoped queries sur médias africains
    n'exposent pas toujours ce champ) plutôt que de vider le pipeline sur une
    donnée manquante — le filtre serveur Tavily (days=1) reste la barrière
    principale, ceci n'est qu'une seconde couche défensive.
    """
    raw_date = result.get("published_date")
    if not raw_date:
        return True
    try:
        published = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - published) <= _FRESHNESS_WINDOW
    except (ValueError, AttributeError):
        return True


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
_SEARCH_CONCURRENCY = 4  # max requêtes Tavily simultanées — même palier que
                          # Firecrawl ci-dessus ; les recherches par source
                          # étaient auparavant enchaînées une par une avec
                          # `await` en boucle, ce qui ajoutait la latence de
                          # CHAQUE appel Tavily bout à bout (souvent 5 à 15
                          # sources) au temps total du cycle pour rien, cet
                          # appel n'ayant aucune dépendance entre sources.


async def _fetch_content(url: str) -> str:
    """
    Récupère le contenu Markdown d'une URL via Firecrawl. BrightData
    abandonné (décision explicite, identifiants proxy invalides en
    production) — en cas d'échec, enrich() retombe sur l'extrait Tavily déjà
    disponible plutôt que sur un second scraper.
    """
    from integrations.firecrawl_client import firecrawl_client

    content = await asyncio.wait_for(
        firecrawl_client.scrape(url), timeout=_SCRAPE_TIMEOUT
    )
    return content or ""


async def run(state: KoraState) -> KoraState:
    logger.info("node_scraper_start", cycle_id=state["cycle_id"])
    emit_log(state["cycle_id"], "INFO", "Recherche des dernières actualités sur les sources configurées…")

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
    else:
        logger.info("scraper_using_fallback_queries")

    # 1b. Requête de secours — SEULEMENT si aucune source officielle n'est
    # configurée (périmètre strict, cf. docstring du module). Plus de
    # complément systématique hors liste blanche quand des sources existent.
    queries = _FALLBACK_QUERIES if not db_sources else []

    # Recherches Tavily par source ET requêtes de secours dispatchées en
    # parallèle (bornées par un sémaphore, comme l'enrichissement Firecrawl
    # ci-dessous) — indépendantes les unes des autres, aucune raison de les
    # enchaîner séquentiellement. topic="news" + days=1 : filtre de fraîcheur
    # Jour-J appliqué nativement par Tavily (cf. tavily_client.search).
    search_semaphore = asyncio.Semaphore(_SEARCH_CONCURRENCY)

    async def _search_source(source: dict) -> list[dict]:
        url = source["url"]
        max_results = 4 if source["level"] == 1 else 2
        async with search_semaphore:
            try:
                return await tavily_client.search(
                    f"site:{_domain_of(url)} actualité Guinée",
                    max_results=max_results,
                    topic="news",
                    days=1,
                )
            except Exception as e:
                logger.warning("tavily_source_failed", url=url, error=str(e))
                return []

    async def _search_query(query: str) -> list[dict]:
        async with search_semaphore:
            try:
                return await tavily_client.search(query, max_results=5, topic="news", days=1)
            except Exception as e:
                logger.warning("tavily_query_failed", query=query, error=str(e))
                state["errors"].append(f"Tavily: {query} — {e}")
                return []

    search_results = await asyncio.gather(
        *[_search_source(s) for s in db_sources],
        *[_search_query(q) for q in queries],
    )
    for results in search_results:
        all_results.extend(results)

    # Filtre Jour-J défensif (seconde couche derrière days=1 côté Tavily)
    stale_count = sum(1 for r in all_results if not _is_fresh(r))
    all_results = [r for r in all_results if _is_fresh(r)]
    if stale_count:
        logger.info("scraper_stale_results_dropped", cycle_id=state["cycle_id"], count=stale_count)

    # Anti-duplication inter-cycles : exclut toute URL déjà ingérée
    # (raw_feeds, tous cycles) ou déjà transformée en article — jamais
    # retraitée deux fois.
    seen_urls = await _load_seen_urls()
    already_seen_count = sum(1 for r in all_results if r.get("url", "") in seen_urls)
    if already_seen_count:
        logger.info("scraper_already_seen_dropped", cycle_id=state["cycle_id"], count=already_seen_count)

    # Dédoublonnage par URL (au sein de ce cycle) + exclusion des URLs
    # historiques
    seen: set = set()
    unique: List[dict] = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen and url not in seen_urls:
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

    if unique:
        emit_log(
            state["cycle_id"], "INFO",
            f"{len(unique)} article(s) candidat(s) trouvé(s) — extraction du contenu complet…",
        )
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
    emit_log(state["cycle_id"], "INFO", f"{len(valid)} article(s) exploitable(s) collecté(s) — sélection en cours…")

    return {**state, "raw_sources": valid}
