"""
Veille passive — pool de contenu pré-collecté (migration 011).

Root cause du besoin (audit 2026-07-14) : chaque "Lancer un cycle" relançait
un balayage complet en direct de toutes les sources, même quand des
informations fraîches du jour existaient déjà. Ce module fait tourner une
collecte planifiée toutes les 2h (core/scheduler.py), source par source,
JAMAIS mélangées entre elles, stockée dans `content_pool` — que le cycle
consomme en priorité (agent/nodes/scraper.py) avant tout scraping en direct.

Verrouillage : partage core/pool_lock.py avec le chemin de scraping de
secours du cycle manuel, pour qu'un job planifié et un cycle manuel ne
scrapent jamais les mêmes sources simultanément (cf. audit : pas de vrai
Redis disponible, verrou en mémoire de processus suffisant ici, même
philosophie que le verrou anti-doublon de cycle déjà en place).
"""
import difflib
import re
from typing import Optional

from core.logger import logger
from core.pool_lock import acquire_scrape_lock, release_scrape_lock
from db.connection import get_db
from sqlalchemy import text

_ACCENT_MAP = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
_KORA_LABELS = ["Politique", "Économie", "Société", "Sport", "Culture", "Sécurité", "International"]
_DEFAULT_DEDUP_THRESHOLD = 0.6


def _normalize_title(title: str) -> str:
    """Minuscules, sans accents ni ponctuation — UNIQUEMENT pour la comparaison
    de similarité inter-sources, jamais affiché ni utilisé comme contenu."""
    t = (title or "").lower().translate(_ACCENT_MAP)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _domain_of(url: str) -> str:
    try:
        return url.split("/")[2].replace("www.", "").lower()
    except IndexError:
        return ""


async def _get_setting(key: str, default: str) -> str:
    try:
        async with get_db() as db:
            result = await db.execute(text("SELECT value FROM app_settings WHERE key = :key"), {"key": key})
            row = result.mappings().first()
        return row["value"] if row else default
    except Exception:
        return default


async def _get_dedup_threshold() -> float:
    raw = await _get_setting("pool_dedup_threshold", str(_DEFAULT_DEDUP_THRESHOLD))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_DEDUP_THRESHOLD


async def _classify_label(title: str, content: str) -> str:
    """
    Classification légère (un seul appel LLM court, reasoning_effort=low)
    pour assigner un libellé éditorial cohérent avec le mapping WordPress
    déjà en place (wp_categories.kora_label) — pas la sélection complète du
    cycle, juste assez pour trier/étiqueter le pool.
    """
    from core.llm_router import llm_router
    prompt = (
        f"Titre : {title}\nExtrait : {(content or '')[:500]}\n\n"
        f"Choisis EXACTEMENT un libellé parmi cette liste, sans rien ajouter : "
        f"{', '.join(_KORA_LABELS)}."
    )
    try:
        response = await llm_router.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=20, reasoning_effort="low",
        )
        raw = (response.choices[0].message.content or "").strip()
        for label in _KORA_LABELS:
            if label.lower() in raw.lower():
                return label
    except Exception as e:
        logger.warning("pool_classification_failed", error=str(e))
    return "Société"


async def _classify_and_dedup_today() -> dict:
    """
    Passe de classification + déduplication inter-sources sur les éléments
    du jour. Algorithme de dédup documenté (audit du 2026-07-14, task
    "conception algorithmique") :
    - Normalisation du titre (minuscules, sans accents/ponctuation).
    - Comparaison par paire via difflib.SequenceMatcher.ratio() (stdlib,
      aucune dépendance ajoutée) — UNIQUEMENT entre éléments de SOURCES
      DIFFÉRENTES (source_name distinct) collectés le MÊME jour.
    - Seuil configurable (app_settings.pool_dedup_threshold, défaut 0.6) :
      au-delà, l'élément le plus récent est LIÉ (duplicate_of) au premier
      trouvé — jamais fusionné ni supprimé, les deux lignes restent
      consultables et traçables à leur source d'origine.
    - Un élément déjà marqué comme doublon d'un autre n'est jamais lui-même
      utilisé comme cible de liaison (évite les chaînes A->B->C).
    """
    threshold = await _get_dedup_threshold()
    async with get_db() as db:
        result = await db.execute(text("""
            SELECT id, source_name, title, title_norm, content, kora_label, duplicate_of
            FROM content_pool WHERE collection_date = CURRENT_DATE ORDER BY collected_at
        """))
        rows = [dict(r) for r in result.mappings().all()]

    dedup_count = 0
    for i, item in enumerate(rows):
        if item["kora_label"] is None:
            label = await _classify_label(item["title"], item["content"])
            async with get_db() as db:
                await db.execute(
                    text("UPDATE content_pool SET kora_label = :label WHERE id = :id"),
                    {"label": label, "id": item["id"]},
                )
            item["kora_label"] = label

        if item["duplicate_of"] is not None:
            continue
        for other in rows[:i]:
            if other["source_name"] == item["source_name"] or other["duplicate_of"] is not None:
                continue
            ratio = difflib.SequenceMatcher(None, item["title_norm"], other["title_norm"]).ratio()
            if ratio >= threshold:
                async with get_db() as db:
                    await db.execute(
                        text("UPDATE content_pool SET duplicate_of = :other WHERE id = :id"),
                        {"other": other["id"], "id": item["id"]},
                    )
                dedup_count += 1
                logger.info(
                    "pool_duplicate_linked",
                    item_source=item["source_name"], item_title=item["title"],
                    linked_to_source=other["source_name"], linked_to_title=other["title"],
                    similarity_ratio=round(ratio, 3),
                )
                break

    return {"classified": len(rows), "duplicates_linked": dedup_count}


async def _create_job_row(trigger: str) -> str:
    async with get_db() as db:
        result = await db.execute(
            text("INSERT INTO pool_jobs (trigger) VALUES (:trigger) RETURNING id"),
            {"trigger": trigger},
        )
        row = result.mappings().first()
    return str(row["id"])


async def _finish_job_row(job_id: str, **fields):
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    async with get_db() as db:
        await db.execute(
            text(f"UPDATE pool_jobs SET {set_clause}, finished_at = now() WHERE id = :job_id"),
            {**fields, "job_id": job_id},
        )


async def run_pooling_job(trigger: str = "scheduled") -> dict:
    """
    Balaie chaque source individuellement (jamais mélangées), stocke chaque
    élément avec sa provenance explicite dans content_pool, puis classe et
    déduplique les éléments du jour. Verrouillé contre le chemin de
    scraping de secours du cycle manuel (core/pool_lock.py).
    """
    from integrations.tavily_client import tavily_client
    from agent.nodes.scraper import _fetch_content, _strip_boilerplate_prefix, _load_sources_from_db

    job_id = await _create_job_row(trigger)
    logger.info("pool_job_started", job_id=job_id, trigger=trigger)

    await acquire_scrape_lock(f"pooling:{trigger}")
    sources_scanned = 0
    items_collected = 0
    try:
        sources = await _load_sources_from_db()
        for source in sources:
            sources_scanned += 1
            source_url = source["url"]
            try:
                results = await tavily_client.search(
                    f"site:{_domain_of(source_url)} actualité Guinée",
                    max_results=4 if source["level"] == 1 else 2,
                    topic="news", days=1,
                )
            except Exception as e:
                logger.warning("pool_source_search_failed", source=source_url, error=str(e))
                continue

            # Chaque source traitée isolément — jamais de résultats mélangés
            # entre sources différentes à cette étape.
            for r in results:
                url = r.get("url", "")
                if not url:
                    continue
                title = r.get("title", "")
                try:
                    content = await _fetch_content(url)
                    content = _strip_boilerplate_prefix(content, title)
                except Exception as e:
                    logger.warning("pool_item_scrape_failed", url=url, error=str(e))
                    content = r.get("content", "")

                async with get_db() as db:
                    try:
                        result = await db.execute(
                            text("""
                                INSERT INTO content_pool (source_url, source_name, title, content, title_norm)
                                VALUES (:url, :source_name, :title, :content, :title_norm)
                                ON CONFLICT (source_url, collection_date) DO NOTHING
                                RETURNING id
                            """),
                            {
                                "url": url,
                                "source_name": _domain_of(url),
                                "title": title,
                                "content": content,
                                "title_norm": _normalize_title(title),
                            },
                        )
                        if result.mappings().first():
                            items_collected += 1
                    except Exception as e:
                        logger.warning("pool_item_insert_failed", url=url, error=str(e))

        dedup_result = await _classify_and_dedup_today()
        await _finish_job_row(
            job_id, status="completed",
            sources_scanned=sources_scanned, items_collected=items_collected,
            duplicates_linked=dedup_result["duplicates_linked"],
        )
        logger.info(
            "pool_job_completed", job_id=job_id, trigger=trigger,
            sources_scanned=sources_scanned, items_collected=items_collected,
            duplicates_linked=dedup_result["duplicates_linked"],
        )
        return {
            "job_id": job_id, "sources_scanned": sources_scanned,
            "items_collected": items_collected, "duplicates_linked": dedup_result["duplicates_linked"],
        }
    except Exception as e:
        await _finish_job_row(job_id, status="failed", error=str(e)[:500])
        logger.error("pool_job_failed", job_id=job_id, trigger=trigger, error=str(e))
        raise
    finally:
        release_scrape_lock()


async def consume_pool_today() -> list[dict]:
    """
    Consulté par le SCRAPE node (agent/nodes/scraper.py) avant tout
    scraping en direct. Ne renvoie QUE les éléments primaires (jamais un
    doublon lié — celui-ci est rattaché à son primaire via
    aggregated_sources, cf. writer.py) du jour courant, disponibles.
    Marque immédiatement les éléments renvoyés comme 'used' — un élément
    consommé une fois ne peut jamais être re-servi à un cycle suivant.
    """
    async with get_db() as db:
        primaries = await db.execute(text("""
            SELECT id, source_url, source_name, title, content, kora_label
            FROM content_pool
            WHERE collection_date = CURRENT_DATE AND status = 'available' AND duplicate_of IS NULL
            ORDER BY collected_at
        """))
        primary_rows = [dict(r) for r in primaries.mappings().all()]

        items = []
        for p in primary_rows:
            dups = await db.execute(text("""
                SELECT source_url, source_name, title, content
                FROM content_pool
                WHERE duplicate_of = :pid AND collection_date = CURRENT_DATE AND status = 'available'
            """), {"pid": p["id"]})
            aggregated = [dict(d) for d in dups.mappings().all()]

            items.append({
                "pool_id": p["id"],
                "url": p["source_url"],
                "source": p["source_name"],
                "title": p["title"],
                "content": p["content"],
                "markdown_content": p["content"],
                "kora_label": p["kora_label"],
                "aggregated_sources": [
                    {"url": d["source_url"], "source": d["source_name"], "title": d["title"], "content": d["content"]}
                    for d in aggregated
                ],
            })

        if items:
            # Marque le primaire ET tous ses doublons liés comme consommés.
            all_ids = [p["id"] for p in primary_rows]
            for p in primary_rows:
                dup_ids = await db.execute(
                    text("SELECT id FROM content_pool WHERE duplicate_of = :pid"), {"pid": p["id"]}
                )
                all_ids.extend(r["id"] for r in dup_ids.mappings().all())
            await db.execute(
                text("UPDATE content_pool SET status = 'used', used_at = now() WHERE id = ANY(:ids)"),
                {"ids": all_ids},
            )

    logger.info("pool_consumed", count=len(items))
    return items
