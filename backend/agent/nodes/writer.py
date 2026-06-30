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

SOURCE(S) À TRAITER :
{sources_section}

Rédige un article complet pour kakilambe.com.

RÈGLES ABSOLUES :
- Titre accrocheur (formule QUESTION / CITATION / CHIFFRE / CONTRASTE)
- Chapeau (lead) : 2-3 phrases résumant l'essentiel, ton neutre
- Corps : 4 à 5 paragraphes, 600-900 mots, style journalistique
- Si plusieurs sources : croise les informations, enrichis l'angle, ne répète pas
- Pas de plagiat : reformule, contextualise, ajoute de la valeur
- Perspective guinéenne / africaine quand possible
- Méta-description SEO : max 155 caractères
- ANTI-HALLUCINATION : ne cite que des faits présents dans les sources fournies

Réponds UNIQUEMENT en JSON valide, format exact :
{{
  "titre": "...",
  "chapeau": "...",
  "corps": "...",
  "meta_description": "...",
  "mots_cles": ["mot1", "mot2", "mot3", "mot4", "mot5"],
  "categorie_wp_id": 1,
  "source_url": "{url_principale}",
  "source_nom": "{source_nom}",
  "image_prompt": "Detailed prompt for AI image generation describing the article scene"
}}
"""

def _build_sources_section(article: dict) -> tuple[str, str, str]:
    """Retourne (sources_section, url_principale, source_nom)."""
    extra = article.get("aggregated_sources", [])
    url = article.get("url", "")
    contenu = (article.get("markdown_content") or article.get("content", ""))[:3000]
    titre = article.get("title", "")
    source_nom = article.get("source", url.split("/")[2] if url else "Source inconnue")

    if not extra:
        section = (
            f"Titre original : {titre}\n"
            f"URL source : {url}\n"
            f"Contenu source :\n---\n{contenu}\n---"
        )
        return section, url, source_nom

    # Article agrégé : plusieurs sources
    parts = [
        f"SOURCE PRINCIPALE\nTitre : {titre}\nURL : {url}\nContenu :\n---\n{contenu}\n---"
    ]
    for i, s in enumerate(extra[:3], 1):
        s_contenu = (s.get("markdown_content") or s.get("content", ""))[:1500]
        parts.append(
            f"SOURCE COMPLÉMENTAIRE {i}\nTitre : {s.get('title','')}\n"
            f"URL : {s.get('url','')}\nContenu :\n---\n{s_contenu}\n---"
        )
    return "\n\n".join(parts), url, source_nom

_MAX_RETRIES = 2


async def _write_with_retry(article: dict) -> ArticleKORA:
    sources_section, url, source_nom = _build_sources_section(article)
    titre = article.get("title", "Article sans titre")

    prompt = _WRITE_PROMPT.format(
        sources_section=sources_section,
        url_principale=url,
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

        # Persiste en base — PENDING_REVIEW en semi (attente HITL), DRAFT en auto
        article_dict = article_obj.model_dump()
        db_id = await _save_to_db(article_dict, state["cycle_id"], state.get("mode", "semi"))
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


async def _save_to_db(article: dict, cycle_id: str, mode: str = "semi") -> str:
    """Persiste l'article en base.

    Semi : PENDING_REVIEW (bloqué avant WordPress, attend HITL).
    Auto : DRAFT (pipeline continue immédiatement vers WordPress).
    """
    status = "PENDING_REVIEW" if mode == "semi" else "DRAFT"
    origin = "AGENT_AUTO" if mode == "auto" else "AGENT_SEMI"
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            result = await db.execute(
                text("""
                INSERT INTO articles (
                    titre, chapeau, corps, meta_description, mots_cles,
                    categorie_id, source_url, source_nom, image_prompt,
                    status, origin, cycle_id
                ) VALUES (
                    :titre, :chapeau, :corps, :meta_description, :mots_cles,
                    :categorie_id, :source_url, :source_nom, :image_prompt,
                    :status, :origin, :cycle_id
                ) RETURNING id
                """),
                {
                    "titre":           article["titre"],
                    "chapeau":         article["chapeau"],
                    "corps":           article["corps"],
                    "meta_description":article["meta_description"],
                    "mots_cles":       article.get("mots_cles", []),
                    "categorie_id":    article.get("categorie_wp_id", 1),
                    "source_url":      article["source_url"],
                    "source_nom":      article["source_nom"],
                    "image_prompt":    article["image_prompt"],
                    "status":          status,
                    "origin":          origin,
                    "cycle_id":        cycle_id,
                },
            )
            return str(result.scalar())
    except Exception as e:
        from core.logger import logger
        logger.error("db_save_failed", error=str(e))
        return "unknown"
