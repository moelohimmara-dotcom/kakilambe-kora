"""
NŒUD 4 — generate_image
Génère une image via pollinations.ai (gratuit, sans clé) à partir du prompt
de l'article. Upload sur WordPress Media API → récupère l'ID média.

generate_and_upload_image() est extrait pour être réutilisé par l'endpoint
de régénération HITL (api/article_routes.py) sans dupliquer la logique.
"""
from typing import Optional

from agent.state import KoraState
from core.cycle_events import emit_log
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


async def generate_and_upload_image(image_prompt: str, titre: str) -> tuple[str, Optional[int], Optional[str]]:
    """
    Génère une image et l'upload sur WordPress. Retourne (image_url, wp_media_id, wp_image_src).
    Lève une exception SEULEMENT si la génération pollinations.ai échoue —
    c'est la seule étape sans laquelle il n'y a rien à montrer à l'éditeur.

    Incident réel (cycle du 2026-07-14) : un wp_url mal configuré
    ("kakilambe.com" sans schéma) faisait échouer l'upload WordPress
    (httpx: "Request URL is missing an 'http://' or 'https://' protocol"),
    et le code précédent laissait cette exception remonter jusqu'à run(),
    qui jetait alors AUSSI l'image_url pollinations pourtant déjà générée
    avec succès — l'éditeur se retrouvait sans aucune image alors qu'une
    existait. L'upload WordPress est maintenant isolé : son échec dégrade
    (pas de wp_media_id/wp_image_src, l'éditeur peut réessayer plus tard
    depuis /articles) sans perdre l'image déjà obtenue.
    """
    from integrations.image_gen_client import image_gen_client
    image_url = await image_gen_client.generate(image_prompt)
    if not image_url:
        raise RuntimeError("Génération d'image vide (pollinations.ai)")

    try:
        from integrations.wordpress_client import wp_client
        wp_media_id, wp_image_src = await wp_client.upload_media(
            image_url,
            f"{_slugify(titre)}.jpg",
            alt_text=(titre or "")[:80],
        )
    except Exception as e:
        logger.warning("illustrator_wp_upload_failed", error=str(e))
        wp_media_id, wp_image_src = None, None

    return image_url, wp_media_id, wp_image_src


async def run(state: KoraState) -> KoraState:
    article = state.get("generated_article")
    if not article:
        logger.warning("illustrator_no_article", cycle_id=state["cycle_id"])
        return state

    image_prompt = article.get("image_prompt", "")
    db_id = article.get("db_id", "")

    logger.info("node_illustrator_start", cycle_id=state["cycle_id"], db_id=db_id)
    emit_log(state["cycle_id"], "INFO", "Génération de l'image d'illustration…")

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
        if wp_media_id:
            emit_log(state["cycle_id"], "INFO", "Image générée et envoyée sur WordPress")
        else:
            emit_log(state["cycle_id"], "WARN", "Image générée (envoi WordPress à réessayer)")

        updated_article = {**article, "wp_media_id": wp_media_id, "wp_image_src": wp_image_src or image_url}
        return {**state, "image_url": image_url, "wp_media_id": wp_media_id, "generated_article": updated_article}

    except Exception as e:
        logger.error("node_illustrator_failed", cycle_id=state["cycle_id"], error=str(e))
        emit_log(state["cycle_id"], "WARN", "Échec de la génération d'image — l'article reste valide sans illustration")
        errors = list(state.get("errors", []))
        errors.append(f"Illustrator: {e}")
        return {**state, "image_url": None, "wp_media_id": None, "errors": errors}
