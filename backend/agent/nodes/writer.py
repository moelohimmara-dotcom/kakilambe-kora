"""
NŒUD 3 — write_article
Rédige un article complet via LiteLLM + validation Pydantic (ArticleKORA).
Output JSON structuré : titre + chapeau + corps + SEO.
Identité éditoriale KORA : neutre, factuel, structure BBC Afrique / New York Times.
La catégorie WordPress est résolue de façon déterministe en Python (cf. _resolve_category_id),
pas devinée par le LLM — évite une mauvaise catégorisation sur le site live.
"""
import json
import random
import re
from agent.state import KoraState
from agent.state import ArticleKORA
from core.cycle_events import emit_log
from core.llm_router import llm_router
from core.logger import logger
from db.connection import get_db
from sqlalchemy import text

# Moteur de variabilité (gouvernance éditoriale, règle 5) : un cycle
# successif ne doit jamais lire comme un décalque du précédent. Un style
# d'accroche est tiré au hasard à chaque rédaction et injecté comme
# directive explicite — la règle des 5W (répondre à Qui/Quoi/Où/Quand) reste
# non négociable, seul l'ANGLE d'attaque des deux premières phrases varie.
_HOOK_STYLES = [
    "attaque par les faits bruts : la première phrase pose l'action et son "
    "acteur principal sans détour",
    "attaque par une citation clé si une déclaration directe figure dans les "
    "sources — sinon repli sur l'attaque par les faits",
    "attaque par mise en contexte macro (économique, sécuritaire ou "
    "politique) qui situe immédiatement l'événement dans son enjeu plus large",
]


def _domain_of(url: str) -> str:
    try:
        return url.split("/")[2].replace("www.", "").lower()
    except IndexError:
        return ""

_WRITE_PROMPT = """Tu es KORA, journaliste IA expert de kakilambe.com, site d'actualité guinéen.
Style éditorial : BBC News Africa. Ton factuel, chaleureux, direct — jamais universitaire, jamais scolaire.
Langue : FRANÇAIS. Tu n'as aucune ligne politique — tu ne favorises ni ne défavorises un parti, un gouvernement ou un acteur.

SOURCE(S) À TRAITER :
{sources_section}

Rédige un article complet pour kakilambe.com.

RÈGLES STRUCTURELLES STRICTES :
1. TITRE : maximum 70 caractères. ZÉRO clickbait — informatif, pas aguicheur. Verbe d'action conjugué
   au PRÉSENT (ex: "licencie", "annonce", "lance"), jamais d'infinitif ni de titre nominal creux.
   Contient toujours un repère géographique (Guinée, Conakry, ville, région...).
2. CHAPEAU — RÈGLE DES 5W : les DEUX premières phrases répondent impérativement à Qui ? Quoi ?
   Où ? Quand ? — sans détour, sans mise en scène qui retarde l'information. 2 à 4 phrases au total.
   Ne résume pas l'article, donne envie de le lire, mais l'essentiel factuel doit être là dès la
   première phrase.
   ANGLE D'ATTAQUE IMPOSÉ POUR CE CHAPEAU (varie à chaque article, ne jamais répéter le même
   enchaînement d'un cycle à l'autre) : {hook_style}. Cet angle ne dispense JAMAIS de répondre aux
   5W dans les deux premières phrases — il détermine seulement par quel bout entrer dans l'info.
3. CORPS — PYRAMIDE INVERSÉE, RYTHME MOBILE-FIRST, ULTRA-SCANNABLE :
   - Ordre de hiérarchie STRICT : l'essentiel de l'actualité en premier, les détails secondaires,
     le contexte historique et les perspectives plus larges en dernier — jamais l'inverse.
   - Paragraphes COURTS : 2 lignes maximum chacun. Une idée par phrase, une idée par paragraphe.
   - Phrases percutantes : Sujet + Verbe + Complément. Pas de phrases à rallonge.
   - Sous-titres dynamiques (Markdown ##) qui donnent envie de continuer à lire, environ tous les 150 mots.
     INTERDICTION ABSOLUE d'utiliser ces mots dans un sous-titre : "Introduction", "Contexte",
     "Conclusion", "Perspective(s)", "Enjeux", "Résumé". Modèle observé chez BBC Afrique (analyse
     d'article réel) : formule le sous-titre en QUESTION directe qui relance la curiosité ("Pourquoi ce
     projet change la donne ?", "Que risque le pays maintenant ?") ou en libellé d'entité court (nom
     d'un acteur, d'un lieu) quand la section traite spécifiquement de lui.
   - MISE EN FORME OBLIGATOIRE : chaque sous-titre et chaque paragraphe est séparé par un VRAI saut
     de ligne double (\\n\\n) dans la valeur JSON du champ "corps". INTERDIT de mettre un sous-titre
     et le paragraphe qui suit sur la même ligne, et INTERDIT de coller plusieurs paragraphes bout à
     bout séparés seulement par des points. Exemple de format EXACT attendu pour le champ "corps" :
     "## Premier sous-titre\\n\\nPremier paragraphe, deux lignes maximum.\\n\\n## Deuxième sous-titre\\n\\nDeuxième paragraphe, deux lignes maximum."
   - Angle SOLUTIONS JOURNALISM : bannis le ton misérabiliste. Mets en avant l'action concrète,
     l'innovation, la résilience, les initiatives locales — sans travestir les faits.
   - Objectivité absolue : ne livre que des faits bruts. Toute opinion doit être attribuée explicitement
     à son auteur via une citation directe ("a déclaré", uniquement si présente dans les sources) —
     jamais présentée comme un jugement de KORA.
   - Ne termine JAMAIS par un récapitulatif artificiel. La dernière phrase de l'article doit être un
     fait marquant, une perspective forte ou une citation de terrain — un point final, pas un résumé.
4. Si plusieurs sources : croise les informations, enrichis l'angle, ne répète pas.
5. Pas de plagiat : reformule, contextualise, ajoute de la valeur.
{sources_credit_instruction}

INTERDITS ABSOLUS — STYLE :
- Transitions scolaires interdites : "En conclusion", "En résumé", "Ainsi", "Il est important de
  rappeler", "En fin de compte", "Force est de constater" — et toute variante de ces formules.
- Mots interdits : révolutionnaire, crucial, indéniable, explorer, transcender, de nos jours,
  au cœur de, véritable thriller, catalyseur. Remplace tout adjectif gonflé par un fait ou un chiffre précis.
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
  "corps": "... (le corps se termine sur un fait/citation fort, PAS de signature dans ce champ — elle est ajoutée automatiquement)",
  "meta_description": "... (max 155 caractères)",
  "mots_cles": ["mot1", "mot2", "mot3", "mot4", "mot5"],
  "categorie_label": "Politique",
  "source_url": "{url_principale}",
  "source_nom": "{source_nom}",
  "image_prompt": "Photorealistic editorial photograph of... (en anglais, descriptif, sans texte ni logo). Décris systématiquement : le sujet/scène précis de CET article, un style photojournalisme, un éclairage cohérent avec l'ambiance du sujet (dramatique pour une actualité tendue, naturel et lumineux pour du positif), un angle de caméra qui sert le sujet (plongée, contre-plongée, plan large selon le contexte), des couleurs réalistes. Chaque article a un sujet différent : ce prompt doit être unique et ne jamais réutiliser une scène ou une composition déjà décrite pour un autre article."
}}
"""

# ── Signature de clôture ───────────────────────────────────────────────────
# Ajoutée en Python, pas laissée à la discrétion du LLM : une exigence "à la
# dernière ligne, exactement ce texte" n'est pas fiable si on compte
# uniquement sur le prompt (le LLM l'oublie, la reformule ou la place mal
# selon le provider de fallback utilisé). Idempotent — ne duplique jamais la
# signature si le modèle l'a quand même produite de lui-même.
_SIGNATURE = "*Par Kakilambe Kora Agent*"


def _append_signature(corps: str) -> str:
    stripped = corps.rstrip()
    if stripped.endswith(_SIGNATURE):
        return stripped
    return f"{stripped}\n\n{_SIGNATURE}"

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

# ── Contrôle de conformité éditoriale ──────────────────────────────────────
# Le prompt seul ne suffit pas à garantir le respect des règles (modèles de
# fallback moins obéissants, variance run-to-run) — ici on VÉRIFIE le texte
# réellement produit et on rejette la génération (retry) si elle ne respecte
# pas la charte, au lieu de publier un article non conforme en espérant que
# le prompt ait suffi.
# Regex plutôt qu'un simple "in blob" : un mot interdit au singulier ("crucial")
# ne bloquait pas ses déclinaisons ("cruciale", "cruciaux") — trouvé en audit
# réel sur un article publié où "cruciale" était passée au travers du filtre.
_BANNED_WORDS_RE = re.compile(
    r"\b(r[ée]volutionnaires?|crucial(?:e|s|es)?|ind[ée]niables?|explorer|transcender|catalyseurs?)\b",
    re.IGNORECASE,
)
_BANNED_EXPRESSIONS = (
    "de nos jours", "au cœur de", "véritable thriller",
)
_BANNED_TRANSITIONS = (
    "en conclusion", "en résumé", "ainsi,", "il est important de rappeler",
    "en fin de compte", "force est de constater", "pour conclure", "en définitive",
)
_VAGUE_OPENERS = (
    "dans un contexte", "il convient de noter", "de manière générale",
    "il est important de", "il faut savoir que", "il est à noter",
)
# Sous-titres scolaires — le prompt l'interdit déjà, mais rien ne vérifiait
# le contenu réel des "##" produits (trouvé en audit : "## Introduction",
# "## Perspective" passaient sans être détectés).
_BANNED_HEADERS = (
    "introduction", "contexte", "conclusion", "perspective", "perspectives",
    "enjeux", "résumé",
)


def _validate_style(chapeau: str, corps: str) -> list[str]:
    """Retourne la liste des violations trouvées — vide si l'article est conforme."""
    violations = []
    blob = f"{chapeau}\n{corps}".lower()

    for m in set(_BANNED_WORDS_RE.findall(blob)):
        violations.append(f"mot interdit (ou déclinaison) détecté : {m!r}")
    for e in _BANNED_EXPRESSIONS:
        if e in blob:
            violations.append(f"expression interdite détectée : {e!r}")
    for t in _BANNED_TRANSITIONS:
        if t in blob:
            violations.append(f"transition scolaire détectée : {t!r}")

    chapeau_start = chapeau.strip().lower()
    for opener in _VAGUE_OPENERS:
        if chapeau_start.startswith(opener):
            violations.append(f"chapeau démarre par une généralité floue : {opener!r} (règle des 5W non respectée)")

    for line in corps.split("\n"):
        line_clean = line.strip().lower()
        if line_clean.startswith("##"):
            header_text = line_clean.lstrip("#").strip()
            for banned in _BANNED_HEADERS:
                if banned in header_text:
                    violations.append(f"sous-titre générique/scolaire détecté : {header_text!r}")

    if "##" in corps and "\n\n" not in corps.rsplit(_SIGNATURE, 1)[0]:
        violations.append("sous-titres et paragraphes collés sans vrai saut de ligne")

    # Paragraphes de maximum 2 lignes — ~45 mots est un proxy raisonnable pour
    # 2 lignes sur mobile. Ignore les sous-titres (##) et la signature finale.
    body_without_signature = corps.rsplit(_SIGNATURE, 1)[0].strip()
    for block in body_without_signature.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        word_count = len(block.split())
        if word_count > 45:
            violations.append(
                f"paragraphe trop long ({word_count} mots, max ~45 pour 2 lignes) : {block[:60]!r}…"
            )

    return violations


_MAX_RETRIES = 2


async def _write_with_retry(article: dict) -> ArticleKORA:
    sources_section, url, source_nom = _build_sources_section(article)
    titre = article.get("title", "Article sans titre")

    # Créditation transparente des sources agrégées (règle de gouvernance
    # éditoriale n°4 : un article de synthèse cross-média doit nommer
    # explicitement chaque source ayant contribué, pas seulement les
    # paraphraser silencieusement).
    extras = article.get("aggregated_sources", [])
    if extras:
        credit_names = [source_nom] + [
            s.get("source") or _domain_of(s.get("url", "")) or "source complémentaire"
            for s in extras
        ]
        sources_credit_instruction = (
            "6. SOURCES MULTIPLES — CRÉDITATION OBLIGATOIRE : cet article synthétise "
            f"{len(credit_names)} sources ({', '.join(credit_names)}). Le chapeau ou le premier "
            "paragraphe du corps doit citer explicitement ces sources par leur nom, avec une formule "
            "de recoupement transparente (ex: \"Selon les recoupements de "
            f"{' et '.join(credit_names)}...\"). Jamais de synthèse silencieuse qui n'attribue rien."
        )
    else:
        sources_credit_instruction = ""

    prompt = _WRITE_PROMPT.format(
        sources_section=sources_section,
        url_principale=url,
        source_nom=source_nom,
        hook_style=random.choice(_HOOK_STYLES),
        sources_credit_instruction=sources_credit_instruction,
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

            chapeau = data.get("chapeau", "")
            corps_signed = _append_signature(data.get("corps", ""))

            violations = _validate_style(chapeau, corps_signed)
            if violations:
                logger.warning(
                    "writer_style_rejected",
                    attempt=attempt,
                    violations=violations,
                )
                raise ValueError(f"Article rejeté (non-conforme à la charte) : {'; '.join(violations)}")

            # Validation Pydantic — catégorie résolue en Python, jamais devinée par le LLM
            category_id = await _resolve_category_id(data.get("categorie_label", ""))
            article_obj = ArticleKORA(
                titre=data.get("titre", titre)[:70],
                chapeau=chapeau,
                corps=corps_signed,
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
    emit_log(state["cycle_id"], "INFO", f"Rédaction en cours : « {current.get('title', '?')} »")

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
        emit_log(state["cycle_id"], "INFO", f"Article rédigé : « {article_obj.titre} »")

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
