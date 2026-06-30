"""
NŒUD 2 — select_articles
Deux passes LLM :
  1. Sélection éditoriale (3-5 articles les plus pertinents)
  2. Déduplication sémantique + agrégation convergente
     → Les sujets couverts par plusieurs sources sont fusionnés en un article enrichi.

Priorisation des sources (déterministe, pas laissée au jugement seul du LLM) :
  Niveau 1 — domaines actifs dans la table rss_sources (sources guinéennes vérifiées par l'utilisateur)
  Niveau 2 — médias panafricains/internationaux de référence (liste fixe ci-dessous)
  Niveau 3 — tout le reste
Note : pas de règle ".gn" — les médias guinéens réels (africaguinee.com, ledjely.com...)
utilisent des domaines .com, pas l'extension .gn.
"""
import json
from typing import List
from agent.state import KoraState
from core.llm_router import llm_router
from core.logger import logger

_PANAFRICAN_DOMAINS = {
    "jeuneafrique.com", "rfi.fr", "bbc.com", "bbc.co.uk", "africanews.com",
    "lemonde.fr", "apanews.net", "afrik.com", "voaafrique.com", "dw.com",
}

_GUINEA_KEYWORDS = (
    "guinee", "guinée", "guinea", "conakry", "kankan", "labe", "nzerekore",
    "mamou", "kindia", "boke", "faranah", "kissidougou", "siguiri",
)

_ACCENT_MAP = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _domain_of(url: str) -> str:
    try:
        return url.split("/")[2].replace("www.", "").lower()
    except IndexError:
        return ""


async def _load_trusted_domains() -> set:
    """Domaines actifs dans rss_sources — sources Niveau 1, curées par l'utilisateur."""
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            result = await db.execute(text("SELECT url FROM rss_sources WHERE is_active = true"))
            rows = result.mappings().all()
        return {_domain_of(r["url"]) for r in rows if r["url"]}
    except Exception as e:
        logger.warning("selector_trusted_domains_failed", error=str(e))
        return set()


def _source_tier(domain: str, trusted: set) -> int:
    if domain in trusted:
        return 1
    if domain in _PANAFRICAN_DOMAINS:
        return 2
    return 3


def _is_guinea_relevant(article: dict) -> bool:
    blob = f"{article.get('title','')} {article.get('content','') or article.get('markdown_content','')}"
    blob = blob.lower().translate(_ACCENT_MAP)
    return any(kw.translate(_ACCENT_MAP) in blob for kw in _GUINEA_KEYWORDS)

# ── Passe 1 : Sélection éditoriale ───────────────────────────────────────────

_SELECTION_PROMPT = """Tu es KORA, éditeur en chef de kakilambe.com, site d'actualité guinéen.

Voici {n} articles collectés depuis des sources d'actualité africaine.
Sélectionne entre 3 et 5 articles à rédiger pour notre audience guinéenne.

Critères de sélection (par ordre de priorité) :
1. Niveau 1 (sources guinéennes vérifiées) prioritaires sur Niveau 2 (médias panafricains),
   eux-mêmes prioritaires sur Niveau 3 (à ne retenir que si la pertinence Guinée est forte).
2. Pertinence directe pour la Guinée ou l'Afrique de l'Ouest
3. Impact sur la vie quotidienne des lecteurs
4. Originalité et valeur informationnelle
5. Potentiel d'engagement (politique, économie, société, sport)

Articles disponibles :
{articles_summary}

Réponds UNIQUEMENT en JSON valide :
{{
  "selected_indices": [0, 2, 4],
  "reason": "Brève justification éditoriale"
}}

Les indices correspondent à la position dans la liste (commence à 0).
"""

# ── Passe 2 : Déduplication + agrégation ─────────────────────────────────────

_DEDUP_PROMPT = """Tu es un algorithme de clustering éditorial pour kakilambe.com.

Voici {n} articles sélectionnés. Certains traitent du même événement depuis des angles différents.
Ta mission :
1. Regrouper les articles qui couvrent le MÊME événement ou sujet principal.
2. Pour chaque groupe de 2+ articles sur le même sujet, les fusionner en UN seul article enrichi
   (le premier de la liste = source principale, les autres = sources complémentaires).
3. Les articles uniques (pas de doublon) passent tels quels.

Articles :
{articles_summary}

Réponds UNIQUEMENT en JSON valide :
{{
  "clusters": [
    {{
      "primary_index": 0,
      "complementary_indices": [2, 4],
      "topic": "Description en 1 phrase du sujet commun"
    }},
    {{
      "primary_index": 1,
      "complementary_indices": [],
      "topic": "Sujet unique"
    }}
  ],
  "dedup_summary": "Ce qui a été fusionné et pourquoi"
}}

RÈGLES :
- primary_index : indice de l'article avec le contenu le plus complet.
- complementary_indices : vide [] si aucun doublon.
- Ne fusionne que les articles sur le MÊME événement précis (pas seulement le même thème général).
"""


async def run(state: KoraState) -> KoraState:
    raw = state["raw_sources"]
    logger.info("node_selector_start", cycle_id=state["cycle_id"], sources=len(raw))

    if not raw:
        logger.warning("node_selector_no_sources", cycle_id=state["cycle_id"])
        return {**state, "selected_articles": []}

    # ── Classification des sources (déterministe) ─────────────────────────────
    trusted_domains = await _load_trusted_domains()
    for a in raw:
        a["_domain"] = _domain_of(a.get("url", ""))
        a["_tier"] = _source_tier(a["_domain"], trusted_domains)

    # Filtre de pertinence : ne garde les sources Niveau 3 que si elles mentionnent
    # explicitement la Guinée. N'écrase jamais la liste si le filtre la viderait
    # entièrement (sécurité — évite un cycle sans aucun article).
    filtered = [a for a in raw if a["_tier"] <= 2 or _is_guinea_relevant(a)]
    if filtered:
        raw = filtered
    else:
        logger.warning("selector_relevance_filter_empty_fallback", cycle_id=state["cycle_id"])

    # ── Passe 1 : Sélection éditoriale ────────────────────────────────────────
    summaries = []
    for i, a in enumerate(raw):
        content = (a.get("markdown_content") or a.get("content", ""))[:300]
        summaries.append(
            f"[{i}] Niveau {a.get('_tier', 3)} · Titre: {a.get('title', 'Sans titre')}\n"
            f"    URL: {a.get('url', '')}\n"
            f"    Extrait: {content.strip()}..."
        )

    try:
        resp = await llm_router.complete(
            messages=[{"role": "user", "content": _SELECTION_PROMPT.format(
                n=len(raw),
                articles_summary="\n\n".join(summaries),
            )}],
            temperature=0.3,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        indices: List[int] = data.get("selected_indices", [])
        valid_indices = [i for i in indices if 0 <= i < len(raw)]
        if not valid_indices:
            valid_indices = list(range(min(3, len(raw))))
        selected = [raw[i] for i in valid_indices[:5]]
        logger.info(
            "node_selector_pass1_done",
            cycle_id=state["cycle_id"],
            selected=len(selected),
            reason=data.get("reason", ""),
        )
    except Exception as e:
        logger.error("node_selector_pass1_failed", error=str(e))
        selected = raw[:3]
        state["errors"].append(f"Selector LLM error (pass1): {e}")

    # ── Passe 2 : Déduplication sémantique + agrégation ───────────────────────
    if len(selected) < 2:
        # Pas assez d'articles pour dédupliquer
        return {**state, "selected_articles": selected, "article_index": 0}

    dedup_summaries = []
    for i, a in enumerate(selected):
        content = (a.get("markdown_content") or a.get("content", ""))[:250]
        dedup_summaries.append(
            f"[{i}] Titre: {a.get('title', 'Sans titre')}\n"
            f"    URL: {a.get('url', '')}\n"
            f"    Extrait: {content.strip()}..."
        )

    try:
        resp2 = await llm_router.complete(
            messages=[{"role": "user", "content": _DEDUP_PROMPT.format(
                n=len(selected),
                articles_summary="\n\n".join(dedup_summaries),
            )}],
            temperature=0.1,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        clusters = json.loads(resp2.choices[0].message.content).get("clusters", [])
        dedup_summary = json.loads(resp2.choices[0].message.content).get("dedup_summary", "")

        aggregated = _build_aggregated_articles(selected, clusters)

        logger.info(
            "node_selector_pass2_done",
            cycle_id=state["cycle_id"],
            before=len(selected),
            after=len(aggregated),
            dedup_summary=dedup_summary,
        )
        return {**state, "selected_articles": aggregated, "article_index": 0}

    except Exception as e:
        logger.warning("node_selector_pass2_failed_fallback", error=str(e))
        # Fallback : pas de déduplication, on garde les sélectionnés bruts
        return {**state, "selected_articles": selected, "article_index": 0}


def _build_aggregated_articles(selected: List[dict], clusters: list) -> List[dict]:
    """
    Construit la liste finale d'articles à partir des clusters LLM.
    Les sources complémentaires sont attachées sous la clé 'aggregated_sources'.
    """
    result = []
    processed = set()

    for cluster in clusters:
        primary_idx = cluster.get("primary_index")
        complementary_idxs = cluster.get("complementary_indices", [])

        if primary_idx is None or primary_idx >= len(selected):
            continue
        if primary_idx in processed:
            continue

        primary = dict(selected[primary_idx])
        processed.add(primary_idx)

        # Attache les sources complémentaires valides
        extras = []
        for cidx in complementary_idxs:
            if 0 <= cidx < len(selected) and cidx not in processed:
                extras.append(selected[cidx])
                processed.add(cidx)

        if extras:
            primary["aggregated_sources"] = extras
            primary["is_aggregated"] = True
            topic = cluster.get("topic", "")
            if topic:
                primary["aggregation_topic"] = topic
        else:
            primary["aggregated_sources"] = []
            primary["is_aggregated"] = False

        result.append(primary)

    # Sécurité : ajouter les articles non couverts par aucun cluster
    for i, a in enumerate(selected):
        if i not in processed:
            art = dict(a)
            art["aggregated_sources"] = []
            art["is_aggregated"] = False
            result.append(art)

    return result
