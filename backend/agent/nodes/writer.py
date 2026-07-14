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

_WRITE_PROMPT = """{editorial_identity}

{length_requirement}

RAPPEL STRUCTUREL LIÉ À LA LONGUEUR : la règle "paragraphes de 2 lignes maximum"
ne veut PAS dire "article court" — elle veut dire BEAUCOUP de paragraphes courts.
Pour atteindre 800-1200 mots avec des paragraphes de 2 lignes, il faut EN MOYENNE
8 à 12 sous-titres (##), chacun suivi d'AU MOINS 2 à 3 paragraphes distincts (pas
un seul paragraphe par sous-titre). Avant de finaliser ta réponse, compte
mentalement les mots du champ "corps" : si le total est sous 800, ajoute une ou
plusieurs sections supplémentaires (contexte historique, comparaison régionale,
détail chiffré, réaction d'un acteur cité dans les sources) plutôt que de
livrer un article court.

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
3. CORPS — PYRAMIDE INVERSÉE, PROSE JOURNALISTIQUE FLUIDE (style BBC Afrique / RFI Afrique) :
   - Ordre de hiérarchie STRICT : l'essentiel de l'actualité en premier, les détails secondaires,
     le contexte historique et les perspectives plus larges en dernier — jamais l'inverse.
   - Paragraphes de 2 à 4 phrases qui s'ENCHAÎNENT logiquement : chaque paragraphe prolonge
     directement le précédent (une conséquence, une réaction, un chiffre, une précision qui répond
     à la question laissée par la phrase d'avant) — jamais des blocs juxtaposés sans lien narratif.
     Root cause d'un défaut de style constaté (audit 2026-07-14, article FGF) : un paragraphe limité
     à "2 lignes maximum" produit un effet haché, pas un vrai récit.
   - Sous-titres (Markdown ##) : usage MESURÉ, réservé aux vrais changements de sujet (un nouvel
     acteur qui entre en scène, le passage des faits immédiats au contexte, un changement d'échelle
     géographique) — JAMAIS un sous-titre par tranche fixe de mots. Pour 800-1200 mots, viser 3 à 5
     sous-titres maximum sur tout l'article, jamais plus. Forme : un LIBELLÉ COURT (nom d'acteur,
     de lieu, de thème) — JAMAIS une question, jamais une formule scolaire ("Introduction",
     "Contexte", "Conclusion", "Perspective(s)", "Enjeux", "Résumé"). Root cause d'un défaut
     constaté (audit 2026-07-14) : une consigne antérieure imposait un sous-titre-question toutes
     les ~150 mots, produisant un pattern Q&A répétitif et mécanique plutôt qu'un vrai récit.
   - Citations : intègre-les dans la phrase narrative elle-même ("X a affirmé que...", "selon X,
     ..."), jamais en bloc isolé détaché du paragraphe qui l'entoure.
   - MISE EN FORME OBLIGATOIRE : chaque sous-titre et chaque paragraphe est séparé par un VRAI saut
     de ligne double (\\n\\n) dans la valeur JSON du champ "corps". INTERDIT de mettre un sous-titre
     et le paragraphe qui suit sur la même ligne, et INTERDIT de coller plusieurs paragraphes bout à
     bout séparés seulement par des points. Exemple de format EXACT attendu pour le champ "corps" :
     "## Premier libellé\\n\\nPremier paragraphe de deux à quatre phrases qui s'enchaînent.\\n\\nDeuxième paragraphe qui prolonge directement le précédent."
   - INTERDICTION d'ajouter une section entière (ex. un paragraphe d'historique générique sans lien
     direct avec l'actualité du jour) dont le seul but est d'allonger le texte sans apporter un fait,
     un chiffre ou une citation nouveaux — chaque paragraphe doit faire progresser l'information.
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
  INTERDICTION ABSOLUE d'inventer un nom de personne, un titre/fonction, une citation ou une
  réaction (ex. "un responsable de club a déclaré...", "la FIFA a indiqué que...") qui ne figure
  PAS mot pour mot ou en substance dans le matériel SOURCE(S) À TRAITER ci-dessus — même pour
  "étoffer" une section avec plusieurs points de vue. Root cause d'un incident réel constaté
  (audit 2026-07-14, test de réécriture de l'article FGF) : un nom de personne et une citation
  entièrement fabriqués ont été ajoutés dans une section "Réactions" absente des sources. Si les
  sources ne donnent qu'UN seul point de vue (ex. un communiqué ministériel), l'article ne doit
  développer QUE ce point de vue — approfondir un fait déjà présent, jamais en inventer un second.

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
    # 3000 → 6000 : avec onlyMainContent=True (cf. firecrawl_client.py), le
    # contenu n'est plus pollué par la navigation du site, donc de vrais
    # articles longs peuvent légitimement dépasser 3000 caractères — les
    # tronquer prématurément privait le modèle de faits réels nécessaires
    # pour atteindre les 800-1200 mots exigés (KORA Éditeur).
    contenu = (article.get("markdown_content") or article.get("content", ""))[:6000]
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
_BANNED_HEADER_WORD_RE = re.compile(
    r"\b(?:introduction|contexte|conclusion|perspectives?|enjeux|résumé)\b",
    re.IGNORECASE,
)
_HEADER_LEADING_CONNECTOR_RE = re.compile(
    r"^(?:de la|du|des|de|pour|sur les|sur|quelles?|quels?)\s+", re.IGNORECASE
)


def _fix_generic_headers(corps: str) -> str:
    """
    Post-traitement DÉTERMINISTE (aucun appel LLM), pas une nouvelle tentative
    de génération. Root cause du 2026-07-14 (cycles 84f489e2, 766bbbc5) :
    même après ajout d'un retour correctif explicite dans la conversation
    (cf. le bloc `messages.append` dans _write_with_retry, qui liste les
    violations exactes après rejet), le modèle réintroduit presque
    systématiquement "Contexte...", "Perspectives...", "Conclusion..." en
    tête de sous-titre d'une tentative à l'autre (observé sur au moins 4
    cycles réels distincts) — l'instruction "n'utilise jamais ces mots"
    n'est pas fiable à 100% en génération libre, quel que soit le nombre de
    tentatives. Plutôt que de relancer indéfiniment (coût, latence, sans
    garantie de convergence dans le budget de _MAX_RETRIES), on retire
    mécaniquement le mot scolaire du sous-titre et on garde le reste, déjà
    factuel/spécifique dans tous les cas observés (ex. "Contexte historique
    de la transition guinéenne" → "Historique de la transition guinéenne").
    """
    lines = corps.split("\n")
    fixed_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("##"):
            fixed_lines.append(line)
            continue
        header_text = stripped.lstrip("#").strip()
        if not _BANNED_HEADER_WORD_RE.search(header_text):
            fixed_lines.append(line)
            continue
        cleaned = _BANNED_HEADER_WORD_RE.sub("", header_text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" :,-–—?")
        # Boucle car un titre peut chaîner deux connecteurs après suppression
        # du mot banni (ex. "quelle perspective pour l'avenir" -> "quelle  pour
        # l'avenir" après suppression -> il faut retirer "quelle" PUIS "pour").
        while True:
            new_cleaned = _HEADER_LEADING_CONNECTOR_RE.sub("", cleaned).strip(" :,-–—?")
            if new_cleaned == cleaned:
                break
            cleaned = new_cleaned
        if len(cleaned.split()) < 2:
            # Rien d'exploitable après suppression du mot banni — repli
            # neutre plutôt que de publier un sous-titre vide ou tronqué.
            cleaned = "Ce que l'on sait à ce stade"
        cleaned = cleaned[0].upper() + cleaned[1:]
        fixed_lines.append(f"## {cleaned}")
    return "\n".join(fixed_lines)


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

    # Paragraphes de 2 à 4 phrases qui s'enchaînent (style BBC Afrique/RFI
    # Afrique, cf. correction du 2026-07-14 sur le style Q&A/haché) — ~100
    # mots est un proxy raisonnable pour 4 phrases de longueur normale.
    # L'ancien seuil de 45 mots (~2 lignes) forçait un style haché ;
    # relevé pour permettre une prose fluide sans autoriser un pavé unique.
    body_without_signature = corps.rsplit(_SIGNATURE, 1)[0].strip()
    for block in body_without_signature.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        word_count = len(block.split())
        if word_count > 100:
            violations.append(
                f"paragraphe trop long ({word_count} mots, max ~100 pour 2 à 4 phrases) : {block[:60]!r}…"
            )

    # Garde-fou de longueur — en plus de l'instruction du prompt (KORA
    # Éditeur, 800-1200 mots), défense en profondeur si le LLM l'ignore
    # malgré tout : déclenche un retry plutôt que de publier un article
    # squelettique (cf. l'exemple "Forbes Afrique" à ~150 mots, root cause
    # du 2026-07-14 : prompt figé sans aucune exigence de longueur).
    total_words = len(body_without_signature.split())
    if total_words < 700:
        violations.append(
            f"corps trop court ({total_words} mots, minimum attendu ~800) — sources probablement sous-exploitées"
        )

    return violations


_MAX_RETRIES = 2

# Repli si la base est indisponible — ne doit jamais faire planter un cycle,
# mais volontairement proche des vraies valeurs en base pour que la
# dégradation reste discrète plutôt que de produire un article générique.
_FALLBACK_IDENTITY = (
    "Tu es KORA, journaliste IA expert de kakilambe.com, site d'actualité guinéen. "
    "Style éditorial : BBC News Africa. Ton factuel, chaleureux, direct — jamais "
    "universitaire, jamais scolaire. Langue : FRANÇAIS. Tu n'as aucune ligne "
    "politique — tu ne favorises ni ne défavorises un parti, un gouvernement ou un acteur."
)
_FALLBACK_LENGTH_REQUIREMENT = (
    "LONGUEUR OBLIGATOIRE : le champ \"corps\" doit compter entre 800 et 1200 mots. "
    "Si les sources fournies sont insuffisantes pour atteindre 800 mots, enrichis "
    "l'article en développant le contexte, les enjeux et les précisions factuelles "
    "cohérentes avec le sujet — sans jamais inventer de faits, chiffres, citations "
    "ou déclarations absents des sources."
)


async def _load_editorial_prompts() -> tuple[str, str]:
    """
    Root cause du bug "articles trop courts et génériques" (audit 2026-07-14) :
    _WRITE_PROMPT était un template figé en dur, totalement déconnecté de
    system_prompts — KORA Journaliste (identité éditoriale, verrouillé) et
    KORA Éditeur (règle des 800-1200 mots + enrichissement, configurable
    depuis /settings) n'étaient JAMAIS chargés ni injectés dans l'appel LLM
    réel de l'étape WRITE. Modifier ces prompts depuis l'UI n'avait donc
    strictement aucun effet sur les articles réellement produits.

    Charge maintenant les deux à chaud à chaque rédaction, pour que toute
    modification faite depuis /settings (via le mécanisme officiel de
    modification des prompts) s'applique immédiatement aux prochains cycles,
    sans redéploiement.
    """
    identity = _FALLBACK_IDENTITY
    length_requirement = _FALLBACK_LENGTH_REQUIREMENT
    try:
        async with get_db() as db:
            result = await db.execute(
                text("SELECT name, content FROM system_prompts WHERE name IN ('KORA Journaliste', 'KORA Éditeur')")
            )
            rows = {r["name"]: r["content"] for r in result.mappings().all()}
        if rows.get("KORA Journaliste"):
            identity = rows["KORA Journaliste"]
        if rows.get("KORA Éditeur"):
            length_requirement = (
                "DIRECTIVE ÉDITORIALE COMPLÉMENTAIRE (KORA Éditeur) :\n" + rows["KORA Éditeur"]
            )
    except Exception as e:
        logger.warning("writer_prompts_load_failed", error=str(e))
    return identity, length_requirement


_MIN_WORDS_BEFORE_EXPAND = 700


async def _expand_corps_if_short(corps: str, titre: str, length_requirement: str) -> str:
    """
    Passe d'édition RÉELLE (deuxième appel LLM dédié), pas une simple instruction
    ajoutée au prompt de rédaction. Root cause du 2026-07-14 (cycle 75254bed) :
    même avec un prompt de rédaction renforcé (rappel structurel, budget de
    tokens généreux, reasoning_effort réduit), le modèle livre systématiquement
    un corps de ~450-530 mots au premier jet — il traite "800-1200 mots" comme
    un objectif secondaire face aux contraintes de style (paragraphes courts,
    sous-titres fréquents). KORA Éditeur a justement été rédigé par l'utilisateur
    comme les instructions d'une PASSE D'ENRICHISSEMENT DÉDIÉE ("Si le texte
    fourni est plus court que 800 mots... enrichis-le") — jamais exécutée comme
    telle avant ce correctif, seulement diluée dans le prompt de rédaction.
    N'invoque un second appel que si nécessaire (économie de coût/latence).
    """
    word_count = len(corps.split())
    if word_count >= _MIN_WORDS_BEFORE_EXPAND:
        return corps

    editor_prompt = (
        f"{length_requirement}\n\n"
        f"ARTICLE ACTUEL (titre : {titre}) — {word_count} mots dans le champ corps ci-dessous :\n\n"
        f"{corps}\n\n"
        "Ta tâche : réponds UNIQUEMENT avec le texte complet et enrichi de ce corps "
        "(entre 800 et 1200 mots), sans JSON, sans commentaire, sans texte avant ou "
        "après. Conserve le format Markdown existant (sous-titres ## suivis d'un "
        "double saut de ligne). RÈGLES STRICTES À RESPECTER SUR LE TEXTE ENTIER "
        "(sections existantes ET nouvelles) :\n"
        "- Paragraphes de 2 à 4 phrases qui s'enchaînent logiquement (une conséquence, "
        "une réaction, un chiffre qui prolonge le paragraphe précédent) — jamais des "
        "blocs juxtaposés sans lien narratif, jamais un pavé unique non plus.\n"
        "- Sous-titres (##) : usage mesuré, 3 à 5 maximum sur tout l'article, JAMAIS "
        "sous forme de question, JAMAIS les mots suivants sous quelque forme que ce "
        "soit : \"Introduction\", \"Contexte\", \"Conclusion\", \"Perspective(s)\", "
        "\"Enjeux\", \"Résumé\" — un sous-titre est un libellé court (nom d'acteur, "
        "de lieu, de thème), jamais une question ni une formule scolaire.\n"
        "- Mots et expressions interdits : révolutionnaire, crucial(e), indéniable, "
        "explorer, transcender, de nos jours, au cœur de, véritable thriller, catalyseur.\n"
        "Pour atteindre la longueur requise, NE PAS ajouter de section générique "
        "déconnectée de l'actualité du jour (ex. un historique du secteur sans lien "
        "direct). Approfondis plutôt les faits DÉJÀ présents : développe une citation "
        "existante avec le reste de ce que dit la source, précise une chronologie, "
        "détaille un chiffre ou un mécanisme déjà mentionné — sans jamais inventer un "
        "fait, un chiffre ou une citation absents du texte actuel.\n"
        "- INTERDICTION ABSOLUE d'inventer un nom de personne, une fonction/titre, une "
        "citation ou une réaction (ex. \"un responsable de club a déclaré...\") pour "
        "étoffer une section — même en réécriture. Si le texte actuel ne comporte "
        "qu'un seul point de vue, l'article enrichi ne doit développer QUE ce point de "
        "vue."
    )
    try:
        response = await llm_router.complete(
            messages=[{"role": "user", "content": editor_prompt}],
            temperature=0.5,
            max_tokens=4000,
            reasoning_effort="low",
        )
        expanded = response.choices[0].message.content
        if expanded and len(expanded.split()) > word_count:
            return expanded.strip()
    except Exception as e:
        logger.warning("writer_expand_failed", error=str(e))
    return corps


async def _write_with_retry(article: dict) -> ArticleKORA:
    sources_section, url, source_nom = _build_sources_section(article)
    titre = article.get("title", "Article sans titre")
    editorial_identity, length_requirement = await _load_editorial_prompts()

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
        editorial_identity=editorial_identity,
        length_requirement=length_requirement,
        sources_section=sources_section,
        url_principale=url,
        source_nom=source_nom,
        hook_style=random.choice(_HOOK_STYLES),
        sources_credit_instruction=sources_credit_instruction,
    )

    last_err = None
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await llm_router.complete(
                messages=messages,
                temperature=0.7,
                # Root cause exacte confirmée le 2026-07-14 (cycle
                # 5e66765b) en rejouant le prompt réel en isolation contre
                # cerebras/gpt-oss-120b : c'est un modèle de RAISONNEMENT —
                # ses tokens de réflexion interne (usage.completion_tokens_
                # details.reasoning_tokens) sont décomptés du MÊME budget
                # max_tokens que la réponse. Sur un prompt identique répété,
                # ce coût variait de 664 à 2849 tokens (observé), engloutissant
                # parfois plus de 80% des 3500 tokens alloués AVANT que le
                # modèle ne commence à écrire le JSON de réponse — d'où,
                # selon les cas, un contenu tronqué ("Unterminated string"),
                # un corps rationné à ~460-500 mots, ou un content vide/None
                # (finish_reason="length" atteint pendant la phase de
                # raisonnement). reasoning_effort="low" (cf. core/llm_router.py)
                # ramène ce surcoût à ~130-230 tokens de façon stable ; le
                # budget est remonté à 6000 pour laisser une marge réelle à un
                # corps de 800-1200 mots + le reste du schéma JSON.
                max_tokens=6000,
                response_format={"type": "json_object"},
                reasoning_effort="low",
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)

            chapeau = data.get("chapeau", "")
            corps_expanded = await _expand_corps_if_short(
                data.get("corps", ""), data.get("titre", titre), length_requirement
            )
            corps_fixed_headers = _fix_generic_headers(corps_expanded)
            corps_signed = _append_signature(corps_fixed_headers)

            violations = _validate_style(chapeau, corps_signed)
            if violations:
                logger.warning(
                    "writer_style_rejected",
                    attempt=attempt,
                    violations=violations,
                )
                # Root cause du plafond de succès observé après le correctif de
                # longueur (cycle 84f489e2, 2026-07-14) : les 3 tentatives d'un
                # même article réutilisaient EXACTEMENT le même prompt initial
                # (aucune mémoire des violations précédentes) — de simples
                # re-tirages indépendants à temperature=0.7, sans corrélation
                # avec la raison réelle du rejet précédent. Le modèle répétait
                # donc souvent la même erreur (ex. sous-titre "Contexte de X")
                # d'une tentative à l'autre. On enrichit maintenant la
                # conversation avec la réponse rejetée + la liste exacte des
                # violations, pour que la tentative suivante corrige
                # spécifiquement ces points plutôt que de repartir à l'aveugle.
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        "Cette réponse a été REJETÉE pour non-conformité à la charte "
                        "éditoriale, pour les raisons précises suivantes :\n- "
                        + "\n- ".join(violations)
                        + "\n\nRenvoie le JSON complet corrigé (mêmes règles que "
                        "l'instruction initiale), en corrigeant SPÉCIFIQUEMENT ces "
                        "points — ne réintroduis aucune des violations listées "
                        "ci-dessus. Ne raccourcis pas le corps pour corriger un "
                        "sous-titre ou un paragraphe : reformule ou scinde "
                        "seulement les passages fautifs, en conservant les 800 à "
                        "1200 mots déjà exigés."
                    ),
                })
                raise ValueError(f"Article rejeté (non-conforme à la charte) : {'; '.join(violations)}")

            # Validation Pydantic — catégorie résolue en Python, jamais devinée par le LLM
            category_id = await _resolve_category_id(data.get("categorie_label", ""))
            # response.model est préfixé par le fournisseur (convention litellm,
            # ex. "groq/llama-3.3-70b-versatile") — jamais capturé avant ce fix,
            # articles.llm_provider_used/llm_model_used restaient NULL en base
            # malgré un vrai appel LLM réussi (visible seulement dans les logs).
            model_used = getattr(response, "model", "") or ""
            provider_used = model_used.split("/", 1)[0] if "/" in model_used else ""
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
                llm_provider_used=provider_used,
                llm_model_used=model_used,
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

        # Incident réel (cycle 8f4cc3d8, 2026-07-14) : _save_to_db() peut
        # échouer (panne DB transitoire) et renvoyer "unknown" sans jamais
        # lever d'exception (cf. son propre try/except). Avant ce fix, le
        # graphe continuait quand même vers illustrator/WordPress avec un
        # db_id fictif, gaspillant un appel Pollinations + upload WordPress
        # réels pour un article qui n'existe nulle part en base — puis
        # rapportait le cycle "PAUSED, prêt à valider" alors qu'il n'y avait
        # RIEN à valider. Traiter explicitement comme un échec d'écriture
        # empêche cette suite d'actions sur du vide.
        if db_id == "unknown":
            raise RuntimeError("Échec d'enregistrement de l'article en base — abandon avant génération d'image")

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
        emit_log(state["cycle_id"], "WARN", "Échec de rédaction pour cet article — passage au suivant")
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
                    llm_provider_used, llm_model_used,
                    status, origin, cycle_id
                ) VALUES (
                    :titre, :chapeau, :corps, :meta_description, :mots_cles,
                    :categorie_id, :source_url, :source_nom, :image_prompt,
                    :llm_provider_used, :llm_model_used,
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
                    "llm_provider_used": article.get("llm_provider_used") or None,
                    "llm_model_used":    article.get("llm_model_used") or None,
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
