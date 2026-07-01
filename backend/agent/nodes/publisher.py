"""
NŒUD 5 — publish_wordpress
Publie l'article validé sur WordPress via REST API v2.
Met à jour Supabase : status PUBLISHED + wp_url.

Espacement des publications (QStash) : le premier article d'un cycle publie
immédiatement (chemin synchrone existant, éprouvé). Les suivants sont enfilés
via Upstash QStash avec un délai croissant (index * delay_between_posts) pour
éviter de publier plusieurs articles d'affilée sur WordPress — remplace
l'ancien `_queue_delay()` qui enregistrait un timestamp jamais exploité.
Si QStash n'est pas configuré ou échoue, repli automatique sur la publication
directe : un souci d'infrastructure secondaire ne doit jamais bloquer un cycle.
"""
from agent.state import KoraState
from core.logger import logger

_DEFAULT_DELAY_SECONDS = 120


async def _update_db(db_id: str, status: str, wp_url: str = ""):
    """Met à jour le statut de l'article en base. Extracté pour faciliter les mocks."""
    if not db_id or db_id == "unknown":
        return
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            if status == "PUBLISHED" and wp_url:
                await db.execute(
                    text("UPDATE articles SET status='PUBLISHED', wp_url=:url, published_at=now() WHERE id=:id"),
                    {"url": wp_url, "id": db_id},
                )
            else:
                await db.execute(
                    text("UPDATE articles SET status=:s WHERE id=:id"),
                    {"s": status, "id": db_id},
                )
    except Exception as e:
        logger.warning("publisher_db_update_failed", status=status, error=str(e))


async def _get_publish_delay_seconds() -> int:
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            result = await db.execute(
                text("SELECT value FROM app_settings WHERE key = 'delay_between_posts'")
            )
            row = result.mappings().first()
        return int(row["value"]) if row and row["value"] else _DEFAULT_DELAY_SECONDS
    except Exception:
        return _DEFAULT_DELAY_SECONDS


async def run(state: KoraState) -> KoraState:
    article = state.get("generated_article")
    if not article:
        logger.warning("publisher_no_article", cycle_id=state["cycle_id"])
        idx = state.get("article_index", 0)
        return {**state, "article_index": idx + 1}

    db_id = article.get("db_id", "")
    idx = state.get("article_index", 0)
    logger.info("node_publisher_start", cycle_id=state["cycle_id"], db_id=db_id, index=idx)

    await _update_db(db_id, "PENDING_REVIEW")

    delay_seconds = await _get_publish_delay_seconds()

    if idx == 0 or delay_seconds <= 0:
        return await _publish_now(state, article, db_id, idx)

    from integrations.qstash_client import qstash_client
    message_id = await qstash_client.publish_delayed(
        "/api/webhooks/qstash/publish-article",
        {"article_id": db_id},
        delay_seconds=idx * delay_seconds,
    )
    if message_id:
        logger.info(
            "node_publisher_queued",
            cycle_id=state["cycle_id"], db_id=db_id,
            delay=idx * delay_seconds, message_id=message_id,
        )
        return {
            **state,
            "article_index": idx + 1,
            "generated_article": None,
            "image_url": None,
            "wp_media_id": None,
        }

    logger.warning("node_publisher_qstash_fallback", cycle_id=state["cycle_id"], db_id=db_id)
    return await _publish_now(state, article, db_id, idx)


async def _publish_now(state: KoraState, article: dict, db_id: str, idx: int) -> KoraState:
    """Publication WordPress directe et synchrone — chemin historique éprouvé."""
    try:
        from integrations.wordpress_client import wp_client

        wp_url = await wp_client.publish_post(article)

        await _update_db(db_id, "PUBLISHED", wp_url)

        published_count = state.get("published_count", 0) + 1

        logger.info(
            "node_publisher_done",
            cycle_id=state["cycle_id"],
            wp_url=wp_url,
            published_count=published_count,
        )

        return {
            **state,
            "wp_post_id": None,
            "published_count": published_count,
            "article_index": idx + 1,
            "generated_article": None,
            "image_url": None,
            "wp_media_id": None,
        }

    except Exception as e:
        logger.error("node_publisher_failed", cycle_id=state["cycle_id"], error=str(e))
        errors = list(state.get("errors", []))
        errors.append(f"Publisher[{db_id}]: {e}")

        await _update_db(db_id, "FAILED")

        return {
            **state,
            "errors": errors,
            "article_index": idx + 1,
            "generated_article": None,
        }
