"""
NŒUD 3 — write_article
Rédige un article complet via LiteLLM + validation Pydantic (ArticleKORA).
Output JSON structuré : titre + chapeau + corps + SEO.
"""
import json
from agent.state import KoraState
from agent.state import ArticleKORA
from core.llm_router import llm_router
from core.logger import logger

_WRITE_PROMPT = """Tu es KORA, journaliste IA expert de kakilambe.com, site d'actualité guinéen.
Style : BBC News Afrique / France 24. Neutre, factuel, accessible. Langue : FRANÇAIS.

SOURCE À TRAITER :
Titre original : {titre}
URL source : {url}
Contenu source :
---
{contenu}
---

Rédige un article complet pour kakilambe.com.

RÈGLES ABSOLUES :
- Titre accrocheur (formule QUESTION / CITATION / CHIFFRE / CONTRASTE)
- Chapeau (lead) : 2-3 phrases résumant l'essentiel, ton neutre
- Corps : 4 à 5 paragraphes, 600-900 mots, style journalistique
- Pas de plagiat : reformule, contextualise, ajoute de la valeur
- Perspective guinéenne / africaine quand possible
- Méta-description SEO : max 155 caractères

Réponds UNIQUEMENT en JSON valide, format exact :
{{
  "titre": "...",
  "chapeau": "...",
  "corps": "...",
  "meta_description": "...",
  "mots_cles": ["mot1", "mot2", "mot3", "mot4", "mot5"],
  "categorie_wp_id": 1,
  "source_url": "{url}",
  "source_nom": "{source_nom}",
  "image_prompt": "Detailed prompt for AI image generation describing the article scene"
}}
"""

_MAX_RETRIES = 2


async def _write_with_retry(article: dict) -> ArticleKORA:
    contenu = (article.get("markdown_content") or article.get("content", ""))[:4000]
    url = article.get("url", "")
    titre = article.get("title", "Article sans titre")
    source_nom = article.get("source", url.split("/")[2] if url else "Source inconnue")

    prompt = _WRITE_PROMPT.format(
        titre=titre,
        url=url,
        contenu=contenu,
        source_nom=source_nom,
    )

    last_err = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await llm_router.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)

            # Validation Pydantic
            article_obj = ArticleKORA(
                titre=data.get("titre", titre),
                chapeau=data.get("chapeau", ""),
                corps=data.get("corps", ""),
                meta_description=data.get("meta_description", "")[:155],
                mots_cles=data.get("mots_cles", [])[:5],
                categorie_wp_id=int(data.get("categorie_wp_id", 1)),
                source_url=url,
                source_nom=source_nom,
                image_prompt=data.get("image_prompt", f"Journalistic photo for article: {titre}"),
            )
            return article_obj

        except Exception as e:
            last_err = e
            logger.warning("writer_retry", attempt=attempt, error=str(e))

    raise RuntimeError(f"Writer failed after {_MAX_RETRIES} retries: {last_err}")


async def run(state: KoraState) -> KoraState:
    selected = state.get("selected_articles", [])
    idx = state.get("article_index", 0)

    if idx >= len(selected):
        logger.info("writer_all_done", cycle_id=state["cycle_id"], total=idx)
        return {**state, "current_article": None}

    current = selected[idx]
    logger.info(
        "node_writer_start",
        cycle_id=state["cycle_id"],
        index=idx,
        titre=current.get("title", "?"),
    )

    try:
        article_obj = await _write_with_retry(current)

        # Persiste en base immédiatement (status DRAFT)
        article_dict = article_obj.model_dump()
        db_id = await _save_to_db(article_dict, state["cycle_id"])
        article_dict["db_id"] = db_id

        logger.info(
            "node_writer_done",
            cycle_id=state["cycle_id"],
            db_id=db_id,
            titre=article_obj.titre,
        )

        return {
            **state,
            "current_article": current,
            "generated_article": article_dict,
        }

    except Exception as e:
        logger.error("node_writer_failed", cycle_id=state["cycle_id"], error=str(e))
        errors = list(state.get("errors", []))
        errors.append(f"Writer[{idx}]: {e}")
        return {
            **state,
            "errors": errors,
            "current_article": None,
            "generated_article": None,
            "article_index": idx + 1,
        }


async def _save_to_db(article: dict, cycle_id: str) -> str:
    """Persiste l'article en base avec status DRAFT."""
    try:
        from db.connection import get_db
        async with get_db() as db:
            result = await db.execute(
                """
                INSERT INTO articles (
                    titre, chapeau, corps, meta_description, mots_cles,
                    categorie_id, source_url, source_nom, image_prompt,
                    status, origin, cycle_id
                ) VALUES (
                    :titre, :chapeau, :corps, :meta_description, :mots_cles,
                    :categorie_id, :source_url, :source_nom, :image_prompt,
                    'DRAFT', 'AGENT_SEMI', :cycle_id
                ) RETURNING id
                """,
                {
                    "titre": article["titre"],
                    "chapeau": article["chapeau"],
                    "corps": article["corps"],
                    "meta_description": article["meta_description"],
                    "mots_cles": article.get("mots_cles", []),
                    "categorie_id": article.get("categorie_wp_id", 1),
                    "source_url": article["source_url"],
                    "source_nom": article["source_nom"],
                    "image_prompt": article["image_prompt"],
                    "cycle_id": cycle_id,
                },
            )
            return str(result.scalar())
    except Exception as e:
        from core.logger import logger
        logger.error("db_save_failed", error=str(e))
        return "unknown"
