"""
NŒUD 4 — generate_image
Génère une image via pollinations.ai (gratuit, sans clé) à partir du prompt
de l'article. Upload sur WordPress Media API → récupère l'ID média.

generate_and_upload_image() est extrait pour être réutilisé par l'endpoint
de régénération HITL (api/article_routes.py) sans dupliquer la logique.
"""
from agent.state import KoraState
from core.logger import logger
from db.connection import get_db
from sqlalchemy import text


async def _save_db_update(db_id: str, image_url: str, wp_media_id: int):
    if not db_id or db_id == "unknown":
        return
    try:
        async with get_db() as db:
            await db.execute(
                text("UPDATE articles SET image_url=:url, wp_media_id=:mid WHERE id=:id"),
                {"url": image_url, "mid": wp_media_id, "id": db_id},
            )
    except Exception as e:
        logger.warning("illustrator_db_update_failed", error=str(e))


def _slugify(titre: str) -> str:
    slug = (titre or "kora-article")[:40].lower()
    slug = slug.encode("ascii", "ignore").decode("ascii")
    return "".join(c if c.isalnum() else "-" for c in slug)


async def generate_and_upload_image(image_prompt: str, titre: str) -> tuple[str, int, str]:
    """
    Génère une image et l'upload sur WordPress. Retourne (image_url, wp_media_id, wp_image_src).
    Lève une exception si la génération ou l'upload échoue — laisse l'appelant décider
    du repli (le nœud graphe dégrade proprement, l'endpoint HITL renvoie une erreur claire).
    """
    from integrations.image_gen_client import image_gen_client
    image_url = await image_gen_client.generate(image_prompt)
    if not image_url:
        raise RuntimeError("Génération d'image vide (pollinations.ai)")

    from integrations.wordpress_client import wp_client
    wp_media_id, wp_image_src = await wp_client.upload_media(
        image_url,
        f"{_slugify(titre)}.jpg",
        alt_text=(titre or "")[:80],
    )
    return image_url, wp_media_id, wp_image_src


async def run(state: KoraState) -> KoraState:
    article = state.get("generated_article")
    if not article:
        logger.warning("illustrator_no_article", cycle_id=state["cycle_id"])
        return state

    image_prompt = article.get("image_prompt", "")
    db_id = article.get("db_id", "")

    logger.info("node_illustrator_start", cycle_id=state["cycle_id"], db_id=db_id)

    try:
        image_url, wp_media_id, wp_image_src = await generate_and_upload_image(
            image_prompt, article.get("titre", "")
        )

        await _save_db_update(db_id, image_url, wp_media_id)

        logger.info(
            "node_illustrator_done",
            cycle_id=state["cycle_id"],
            image_url=image_url,
            wp_media_id=wp_media_id,
            wp_image_src=wp_image_src,
        )

        updated_article = {**article, "wp_media_id": wp_media_id, "wp_image_src": wp_image_src or image_url}
        return {**state, "image_url": image_url, "wp_media_id": wp_media_id, "generated_article": updated_article}

    except Exception as e:
        logger.error("node_illustrator_failed", cycle_id=state["cycle_id"], error=str(e))
        errors = list(state.get("errors", []))
        errors.append(f"Illustrator: {e}")
        return {**state, "image_url": None, "wp_media_id": None, "errors": errors}
