"""
NŒUD 3 — write_article
Rédige un article complet via LiteLLM + validation Pydantic (ArticleKORA).
Output JSON structuré : titre + chapeau + corps + SEO.
Identité éditoriale KORA : neutre, factuel, structure BBC Afrique / New York Times.
La catégorie WordPress est résolue de façon déterministe en Python (cf. _resolve_category_id),
pas devinée par le LLM — évite une mauvaise catégorisation sur le site live.
"""
import json
from agent.state import KoraState
from agent.state import ArticleKORA
from core.llm_router import llm_router
from core.logger import logger
from db.connection import get_db
from sqlalchemy import text

_WRITE_PROMPT = """Tu es KORA, journaliste IA expert de kakilambe.com, site d'actualité guinéen.
Style éditorial : BBC News Afrique / New York Times. Neutre, factuel, accessible. Langue : FRANÇAIS.
Tu n'as aucune ligne politique — tu ne favorises ni ne défavorises un parti, un gouvernement ou un acteur.

SOURCE(S) À TRAITER :
{sources_section}

Rédige un article complet pour kakilambe.com.

RÈGLES STRUCTURELLES STRICTES :
1. TITRE : maximum 70 caractères. Formule QUESTION directe, CITATION choc, CHIFFRE clé ou CONTRASTE.
   Contient toujours un repère géographique (Guinée, Conakry, ville, région...).
2. CHAPEAU : 2 à 4 phrases d'accroche (style NYT). Plonge dans une scène, expose une tension ou
   frappe avec un chiffre — ne résume pas l'article, donne envie de le lire.
3. CORPS EN STRATES (6 paragraphes maximum) :
   - Faits bruts (qui, quoi, où, quand)
   - Le pourquoi / comment
   - Citations directes ("a déclaré", "a affirmé", uniquement si présentes dans les sources)
   - Contexte historique ou factuel
   - Enjeux et conséquences, chiffrés si possible
   - Perspective ouverte, sans opinion ni jugement personnel
4. SOUS-TITRES : insère un sous-titre clair (format Markdown ##) environ tous les 150 mots.
5. Si plusieurs sources : croise les informations, enrichis l'angle, ne répète pas.
6. Pas de plagiat : reformule, contextualise, ajoute de la valeur.

INTERDITS ABSOLUS :
- Adjectifs non factuels ("magnifique", "terrible", "courageux"...)
- Expressions floues ("beaucoup de personnes", "de nombreux observateurs")
- Voix passive excessive, répétitions
- Toute affirmation sans source dans le matériel fourni
- ANTI-HALLUCINATION : ne cite que des faits présents dans les sources fournies. N'invente jamais.

CATÉGORIE : choisis exactement un libellé parmi
["Politique", "Économie", "Société", "Sport", "Culture", "Sécurité", "International"].

Réponds UNIQUEMENT en JSON valide, format exact :
{{
  "titre": "...",
  "chapeau": "...",
  "corps": "...",
  "meta_description": "... (max 155 caractères)",
  "mots_cles": ["mot1", "mot2", "mot3", "mot4", "mot5"],
  "categorie_label": "Politique",
  "source_url": "{url_principale}",
  "source_nom": "{source_nom}",
  "image_prompt": "Photorealistic wide-angle editorial photograph of... (en anglais, descriptif, sans texte ni logo)"
}}
"""

# ── Résolution de la catégorie WordPress ──────────────────────────────────────
# Source de vérité : table wp_categories (synchronisée depuis l'API WordPress
# réelle via /api/settings/wp-categories/sync, mappée aux 7 libellés dans
# Settings → Catégories). Repli sur les IDs codés en dur si la DB est
# indisponible ou si aucune catégorie n'est encore mappée — mieux vaut une
# catégorie par défaut correcte qu'un cycle bloqué sur une panne secondaire.
_CATEGORY_MAP_FALLBACK = {
    "politique": 4,
    "economie":  5,
}
_DEFAULT_CATEGORY_ID = 44
_ACCENT_MAP = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


async def _resolve_category_id(label: str) -> int:
    if not label:
        return _DEFAULT_CATEGORY_ID
    try:
        async with get_db() as db:
            result = await db.execute(
                text("SELECT wp_id FROM wp_categories WHERE kora_label = :label LIMIT 1"),
                {"label": label},
            )
            row = result.mappings().first()
        if row:
            return row["wp_id"]
    except Exception as e:
        logger.warning("category_db_lookup_failed", label=label, error=str(e))

    normalized = label.strip().lower().translate(_ACCENT_MAP)
    return _CATEGORY_MAP_FALLBACK.get(normalized, _DEFAULT_CATEGORY_ID)

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

            # Validation Pydantic — catégorie résolue en Python, jamais devinée par le LLM
            category_id = await _resolve_category_id(data.get("categorie_label", ""))
            article_obj = ArticleKORA(
                titre=data.get("titre", titre)[:70],
                chapeau=data.get("chapeau", ""),
                corps=data.get("corps", ""),
                meta_description=data.get("meta_description", "")[:155],
                mots_cles=data.get("mots_cles", [])[:5],
                categorie_wp_id=category_id,
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
