"""
NŒUD 5 — publish_wordpress
Publie l'article validé sur WordPress via REST API v2.
Met à jour Supabase : status PUBLISHED + wp_url.
Upstash queue : délai 2h avant prochain article.
"""
from agent.state import KoraState
from core.logger import logger


async def _update_db(db_id: str, status: str, wp_url: str = ""):
    """Met à jour le statut de l'article en base. Extracté pour faciliter les mocks."""
    if not db_id or db_id == "unknown":
        return
    try:
        from db.connection import get_db
        async with get_db() as db:
            if status == "PUBLISHED" and wp_url:
                await db.execute(
                    "UPDATE articles SET status='PUBLISHED', wp_url=:url, published_at=now() WHERE id=:id",
                    {"url": wp_url, "id": db_id},
                )
            else:
                await db.execute(
                    "UPDATE articles SET status=:s WHERE id=:id",
                    {"s": status, "id": db_id},
                )
    except Exception as e:
        logger.warning("publisher_db_update_failed", status=status, error=str(e))


async def run(state: KoraState) -> KoraState:
    article = state.get("generated_article")
    if not article:
        logger.warning("publisher_no_article", cycle_id=state["cycle_id"])
        idx = state.get("article_index", 0)
        return {**state, "article_index": idx + 1}

    db_id = article.get("db_id", "")
    logger.info("node_publisher_start", cycle_id=state["cycle_id"], db_id=db_id)

    await _update_db(db_id, "PENDING_REVIEW")

    try:
        from integrations.wordpress_client import wp_client

        wp_url = await wp_client.publish_post(article)

        await _update_db(db_id, "PUBLISHED", wp_url)

        published_count = state.get("published_count", 0) + 1
        idx = state.get("article_index", 0)

        logger.info(
            "node_publisher_done",
            cycle_id=state["cycle_id"],
            wp_url=wp_url,
            published_count=published_count,
        )

        await _queue_delay()

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

        idx = state.get("article_index", 0)
        return {
            **state,
            "errors": errors,
            "article_index": idx + 1,
            "generated_article": None,
        }


async def _queue_delay():
    """Enqueue un délai 2h via Upstash. Si Redis indisponible, no-op."""
    try:
        from core.config import settings
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        # On enregistre le timestamp du dernier publish
        import time
        await r.set("kora:last_publish_ts", int(time.time()), ex=7200)
        await r.aclose()
    except Exception:
        pass  # délai non critique
