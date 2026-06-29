"""
NŒUD 4 — generate_image
Génère une image via Fal.ai à partir du prompt de l'article.
Upload sur WordPress Media API → récupère l'ID média.
"""
from agent.state import KoraState
from core.logger import logger


async def _save_db_update(db_id: str, image_url: str, wp_media_id: int):
    if not db_id or db_id == "unknown":
        return
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            await db.execute(
                text("UPDATE articles SET image_url=:url, wp_media_id=:mid WHERE id=:id"),
                {"url": image_url, "mid": wp_media_id, "id": db_id},
            )
    except Exception as e:
        logger.warning("illustrator_db_update_failed", error=str(e))


async def run(state: KoraState) -> KoraState:
    article = state.get("generated_article")
    if not article:
        logger.warning("illustrator_no_article", cycle_id=state["cycle_id"])
        return state

    image_prompt = article.get("image_prompt", "")
    db_id = article.get("db_id", "")

    logger.info("node_illustrator_start", cycle_id=state["cycle_id"], db_id=db_id)

    try:
        # 1. Génération image
        from integrations.image_gen_client import image_gen_client
        image_url = await image_gen_client.generate(image_prompt)

        if not image_url:
            logger.warning("image_gen_empty", cycle_id=state["cycle_id"])
            return {**state, "image_url": None, "wp_media_id": None}

        # 2. Upload WordPress Media
        from integrations.wordpress_client import wp_client
        titre_slug = article.get("titre", "kora-article")[:40].lower()
        titre_slug = titre_slug.encode("ascii", "ignore").decode("ascii")
        titre_slug = "".join(c if c.isalnum() else "-" for c in titre_slug)
        titre_clean = article.get("titre", "")[:80]
        wp_media_id, wp_image_src = await wp_client.upload_media(
            image_url,
            f"{titre_slug}.jpg",
            alt_text=titre_clean,
        )

        # 3. Mise à jour en base
        await _save_db_update(db_id, image_url, wp_media_id)

        logger.info(
            "node_illustrator_done",
            cycle_id=state["cycle_id"],
            image_url=image_url,
            wp_media_id=wp_media_id,
            wp_image_src=wp_image_src,
        )

        # Mettre à jour l'article généré avec l'ID média et l'URL WP de l'image
        updated_article = {**article, "wp_media_id": wp_media_id, "wp_image_src": wp_image_src or image_url}
        return {**state, "image_url": image_url, "wp_media_id": wp_media_id, "generated_article": updated_article}

    except Exception as e:
        logger.error("node_illustrator_failed", cycle_id=state["cycle_id"], error=str(e))
        errors = list(state.get("errors", []))
        errors.append(f"Illustrator: {e}")
        return {**state, "image_url": None, "wp_media_id": None, "errors": errors}
