from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from db.connection import get_db
from core.logger import logger

router = APIRouter()


class ArticlePatch(BaseModel):
    titre: Optional[str] = None
    chapeau: Optional[str] = None
    corps: Optional[str] = None
    meta_description: Optional[str] = None


@router.get("")
async def list_articles(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
):
    offset = (page - 1) * limit
    async with get_db() as db:
        if status:
            result = await db.execute(
                text("""
                    SELECT id, titre, chapeau, status, origin, source_nom,
                           created_at, published_at, wp_url,
                           array_length(string_to_array(corps, ' '), 1) AS word_count
                    FROM articles
                    WHERE status = :status
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"status": status, "limit": limit, "offset": offset},
            )
            count_result = await db.execute(
                text("SELECT COUNT(*) FROM articles WHERE status = :status"),
                {"status": status},
            )
        else:
            result = await db.execute(
                text("""
                    SELECT id, titre, chapeau, status, origin, source_nom,
                           created_at, published_at, wp_url,
                           array_length(string_to_array(corps, ' '), 1) AS word_count
                    FROM articles
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": limit, "offset": offset},
            )
            count_result = await db.execute(text("SELECT COUNT(*) FROM articles"))

        rows = result.mappings().all()
        total = count_result.scalar()

    return {"items": [dict(r) for r in rows], "total": total, "page": page}


@router.get("/{article_id}")
async def get_article(article_id: str):
    async with get_db() as db:
        result = await db.execute(
            text("SELECT * FROM articles WHERE id = :id"),
            {"id": article_id},
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return dict(row)


@router.patch("/{article_id}")
async def update_article(article_id: str, body: ArticlePatch):
    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = article_id

    async with get_db() as db:
        await db.execute(
            text(f"UPDATE articles SET {set_clause} WHERE id = :id"),
            fields,
        )
    return {"updated": True}


@router.post("/{article_id}/approve")
async def approve_article(article_id: str):
    async with get_db() as db:
        result = await db.execute(
            text("SELECT * FROM articles WHERE id = :id"),
            {"id": article_id},
        )
        row = result.mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Article not found")

        await db.execute(
            text("UPDATE articles SET status = 'PUBLISHED', published_at = now() WHERE id = :id"),
            {"id": article_id},
        )

    import asyncio
    asyncio.create_task(_publish_to_wp(dict(row)))
    logger.info("article_approved", article_id=article_id)
    return {"status": "PUBLISHED", "article_id": article_id}


async def _publish_to_wp(article: dict):
    from integrations.wordpress_client import wp_client
    try:
        wp_url = await wp_client.publish_post(article)
        async with get_db() as db:
            await db.execute(
                text("UPDATE articles SET wp_url = :url WHERE id = :id"),
                {"url": wp_url, "id": article["id"]},
            )
        logger.info("wp_published", article_id=article["id"], url=wp_url)
    except Exception as e:
        logger.error("wp_publish_failed", article_id=article["id"], error=str(e))
        async with get_db() as db:
            await db.execute(
                text("UPDATE articles SET status = 'FAILED' WHERE id = :id"),
                {"id": article["id"]},
            )


@router.post("/{article_id}/regenerate-image")
async def regenerate_image(article_id: str):
    """
    Régénère l'illustration d'un article avant publication (HITL) — l'utilisateur
    peut demander une nouvelle image depuis l'éditeur si celle générée automatiquement
    ne convient pas. Ne fonctionne que sur un article pas encore publié.
    """
    async with get_db() as db:
        result = await db.execute(
            text("SELECT id, titre, image_prompt, status FROM articles WHERE id = :id"),
            {"id": article_id},
        )
        row = result.mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    if row["status"] == "PUBLISHED":
        raise HTTPException(status_code=400, detail="Article déjà publié — image non modifiable")

    from agent.nodes.illustrator import generate_and_upload_image
    try:
        image_url, wp_media_id, wp_image_src = await generate_and_upload_image(
            row["image_prompt"] or f"Journalistic photo for article: {row['titre']}",
            row["titre"],
        )
    except Exception as e:
        logger.error("regenerate_image_failed", article_id=article_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Échec de la régénération d'image : {e}")

    async with get_db() as db:
        await db.execute(
            text("UPDATE articles SET image_url = :url, wp_media_id = :mid WHERE id = :id"),
            {"url": wp_image_src or image_url, "mid": wp_media_id, "id": article_id},
        )

    logger.info("image_regenerated", article_id=article_id, wp_media_id=wp_media_id)
    return {"image_url": wp_image_src or image_url, "wp_media_id": wp_media_id}


@router.post("/{article_id}/reject")
async def reject_article(article_id: str):
    async with get_db() as db:
        result = await db.execute(
            text("SELECT id FROM articles WHERE id = :id"),
            {"id": article_id},
        )
        if not result.mappings().first():
            raise HTTPException(status_code=404, detail="Article not found")
        await db.execute(
            text("UPDATE articles SET status = 'REJECTED' WHERE id = :id"),
            {"id": article_id},
        )
    return {"status": "REJECTED", "article_id": article_id}


@router.delete("/{article_id}")
async def delete_article(article_id: str):
    async with get_db() as db:
        result = await db.execute(
            text("SELECT id FROM articles WHERE id = :id"),
            {"id": article_id},
        )
        if not result.mappings().first():
            raise HTTPException(status_code=404, detail="Article not found")
        await db.execute(
            text("DELETE FROM articles WHERE id = :id"),
            {"id": article_id},
        )
    return {"deleted": True}
