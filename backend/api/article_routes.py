from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from db.connection import get_db
from core.logger import logger

router = APIRouter()

_MOIS_FR_ABBREV = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]


def _format_date_fr(d) -> str:
    return f"{d.day} {_MOIS_FR_ABBREV[d.month - 1]} {d.year}"


def _compute_date_label(source_published_at) -> dict:
    """
    Label relatif Aujourd'hui/Hier/date exacte, calculé côté backend à
    partir de la SEULE date réelle de la source (jamais created_at,
    l'horodatage d'écriture de KORA) — comparaison en UTC, qui correspond
    au fuseau de référence de l'app (Guinée/Conakry = UTC+0, sans heure
    d'été, cf. contrainte explicite). Recalculé à chaque requête : se
    resynchronise donc naturellement chaque jour, sans tâche de fond.
    Si aucune date source fiable n'existe (source_published_at NULL),
    renvoie explicitement "date non confirmée" plutôt que de fabriquer une
    valeur à partir d'un horodatage qui n'est pas celui de la publication.
    """
    if source_published_at is None:
        return {"date_label": "Date non confirmée", "date_confirmed": False}

    today = datetime.now(timezone.utc).date()
    d = source_published_at.date() if hasattr(source_published_at, "date") else source_published_at
    delta_days = (today - d).days

    if delta_days == 0:
        label = "Aujourd'hui"
    elif delta_days == 1:
        label = "Hier"
    else:
        label = _format_date_fr(d)

    return {"date_label": label, "date_confirmed": True}


def _with_date_label(row: dict) -> dict:
    row = dict(row)
    row.update(_compute_date_label(row.get("source_published_at")))
    return row


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
                           created_at, published_at, source_published_at, wp_url, image_url,
                           mots_cles, categorie_id, cycle_id,
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
                           created_at, published_at, source_published_at, wp_url, image_url,
                           mots_cles, categorie_id, cycle_id,
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

    return {"items": [_with_date_label(r) for r in rows], "total": total, "page": page}


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
    return _with_date_label(row)


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


@router.post("/{article_id}/regenerate")
async def regenerate_article(article_id: str):
    """
    Boucle de régénération HITL : réécrit intégralement l'article (nouvel
    angle d'accroche, nouvelle image) à partir du contenu source d'origine,
    sans jamais republier l'ancienne version tant que l'utilisateur n'a pas
    validé. Ne fonctionne que sur un article pas encore publié.

    Le contenu source brut n'est pas conservé dans `articles` (seule l'URL
    l'est) — reconstruit ici depuis `raw_feeds` (même cycle_id/batch_id +
    même source_url), où il est journalisé au moment du scraping original.
    """
    async with get_db() as db:
        result = await db.execute(
            text("""
                SELECT id, titre, source_url, source_nom, cycle_id, status
                FROM articles WHERE id = :id
            """),
            {"id": article_id},
        )
        row = result.mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    if row["status"] == "PUBLISHED":
        raise HTTPException(status_code=400, detail="Article déjà publié — non régénérable")

    async with get_db() as db:
        raw = await db.execute(
            text("""
                SELECT title, content, published_at FROM raw_feeds
                WHERE batch_id = :cycle_id AND source_url = :source_url
                LIMIT 1
            """),
            {"cycle_id": row["cycle_id"], "source_url": row["source_url"]},
        )
        raw_row = raw.mappings().first()

    if not raw_row:
        raise HTTPException(
            status_code=409,
            detail="Contenu source original introuvable (raw_feeds) — régénération impossible pour cet article",
        )

    source_article = {
        "title": raw_row["title"],
        "url": row["source_url"],
        "content": raw_row["content"] or "",
        "source": row["source_nom"],
        "aggregated_sources": [],  # non reconstitué — régénération mono-source
        # Date réelle de la source, journalisée au scraping original — la
        # régénération ne doit jamais la perdre ni la redéduire à froid.
        "published_at": raw_row["published_at"],
    }

    from agent.nodes.writer import _write_with_retry
    from agent.nodes.illustrator import generate_and_upload_image

    try:
        rewritten = await _write_with_retry(source_article)
    except Exception as e:
        logger.error("article_regenerate_write_failed", article_id=article_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Échec de la réécriture : {e}")

    try:
        image_url, wp_media_id, wp_image_src = await generate_and_upload_image(
            rewritten.image_prompt, rewritten.titre
        )
    except Exception as e:
        logger.warning("article_regenerate_image_failed", article_id=article_id, error=str(e))
        image_url, wp_media_id, wp_image_src = None, None, None

    async with get_db() as db:
        await db.execute(
            text("""
                UPDATE articles SET
                    titre = :titre, chapeau = :chapeau, corps = :corps,
                    meta_description = :meta_description, mots_cles = :mots_cles,
                    categorie_id = :categorie_id, image_prompt = :image_prompt,
                    image_url = COALESCE(:image_url, image_url),
                    wp_media_id = COALESCE(:wp_media_id, wp_media_id)
                WHERE id = :id
            """),
            {
                "titre": rewritten.titre,
                "chapeau": rewritten.chapeau,
                "corps": rewritten.corps,
                "meta_description": rewritten.meta_description,
                "mots_cles": rewritten.mots_cles,
                "categorie_id": rewritten.categorie_wp_id,
                "image_prompt": rewritten.image_prompt,
                "image_url": wp_image_src or image_url,
                "wp_media_id": wp_media_id,
                "id": article_id,
            },
        )

    logger.info("article_regenerated", article_id=article_id)
    return {
        "id": article_id,
        "titre": rewritten.titre,
        "chapeau": rewritten.chapeau,
        "corps": rewritten.corps,
        "image_url": wp_image_src or image_url,
    }


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
