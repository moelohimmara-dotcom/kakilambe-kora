"""
Routes FastAPI — Webhooks entrants
POST /api/webhooks/qstash/publish-article : QStash déclenche la publication
WordPress différée d'un article, avec vérification de signature obligatoire.
"""
import json
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import text

from core.config import settings
from core.logger import logger
from db.connection import get_db

router = APIRouter()


@router.post("/qstash/publish-article")
async def qstash_publish_article(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("Upstash-Signature", "")

    from integrations.qstash_client import qstash_client
    destination_url = f"{settings.APP_BASE_URL.rstrip('/')}/api/webhooks/qstash/publish-article"

    if not qstash_client.verify_signature(raw_body.decode("utf-8"), signature, destination_url):
        raise HTTPException(status_code=401, detail="Invalid QStash signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    article_id = payload.get("article_id")
    if not article_id:
        raise HTTPException(status_code=400, detail="article_id manquant")

    logger.info("qstash_webhook_received", article_id=article_id)

    async with get_db() as db:
        result = await db.execute(
            text("SELECT * FROM articles WHERE id = :id"), {"id": article_id}
        )
        row = result.mappings().first()

    if not row:
        # Article introuvable (supprimé entre-temps) — 200 pour éviter que
        # QStash ne retente indéfiniment un message qui ne pourra jamais réussir.
        logger.warning("qstash_article_not_found", article_id=article_id)
        return {"status": "skipped", "reason": "article not found"}

    article = dict(row)
    if article.get("status") == "PUBLISHED":
        return {"status": "skipped", "reason": "already published"}

    try:
        from integrations.wordpress_client import wp_client
        wp_url = await wp_client.publish_post(article)
        async with get_db() as db:
            await db.execute(
                text("UPDATE articles SET status='PUBLISHED', wp_url=:url, published_at=now() WHERE id=:id"),
                {"url": wp_url, "id": article_id},
            )
        logger.info("qstash_publish_success", article_id=article_id, wp_url=wp_url)
        return {"status": "published", "wp_url": wp_url}

    except Exception as e:
        logger.error("qstash_publish_failed", article_id=article_id, error=str(e))
        async with get_db() as db:
            await db.execute(
                text("UPDATE articles SET status='FAILED' WHERE id=:id"),
                {"id": article_id},
            )
        # 500 → QStash retente automatiquement selon sa politique de retry.
        raise HTTPException(status_code=500, detail=f"Publish failed: {e}")
