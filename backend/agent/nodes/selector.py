"""
NŒUD 2 — select_articles
Analyse éditoriale KORA : sélectionne 3 à 5 articles parmi les sources collectées.
Critères : pertinence Guinée/Afrique, originalité, potentiel d'audience.
"""
import json
from typing import List
from agent.state import KoraState
from core.llm_router import llm_router
from core.logger import logger

_SELECTION_PROMPT = """Tu es KORA, éditeur en chef de kakilambe.com, site d'actualité guinéen.

Voici {n} articles collectés depuis des sources d'actualité africaine.
Sélectionne entre 3 et 5 articles à rédiger pour notre audience guinéenne.

Critères de sélection (par ordre de priorité) :
1. Pertinence directe pour la Guinée ou l'Afrique de l'Ouest
2. Impact sur la vie quotidienne des lecteurs
3. Originalité (pas déjà traité récemment)
4. Potentiel d'engagement (politique, économie, société, sport)
5. Sources fiables

Articles disponibles :
{articles_summary}

Réponds UNIQUEMENT en JSON valide, format exact :
{{
  "selected_indices": [0, 2, 4],
  "reason": "Brève justification éditoriale"
}}

Les indices correspondent à la position dans la liste (commence à 0).
"""


async def run(state: KoraState) -> KoraState:
    raw = state["raw_sources"]
    logger.info("node_selector_start", cycle_id=state["cycle_id"], sources=len(raw))

    if not raw:
        logger.warning("node_selector_no_sources", cycle_id=state["cycle_id"])
        return {**state, "selected_articles": []}

    # Résumé compact pour le LLM (titre + URL + extrait 300 chars)
    summaries = []
    for i, a in enumerate(raw):
        content = (a.get("markdown_content") or a.get("content", ""))[:300]
        summaries.append(
            f"[{i}] Titre: {a.get('title', 'Sans titre')}\n"
            f"    URL: {a.get('url', '')}\n"
            f"    Extrait: {content.strip()}..."
        )

    prompt = _SELECTION_PROMPT.format(
        n=len(raw),
        articles_summary="\n\n".join(summaries),
    )

    try:
        response = await llm_router.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        indices: List[int] = data.get("selected_indices", [])
        reason = data.get("reason", "")

        # Validation des indices
        valid_indices = [i for i in indices if 0 <= i < len(raw)]
        if not valid_indices:
            valid_indices = list(range(min(3, len(raw))))

        selected = [raw[i] for i in valid_indices[:5]]
        logger.info(
            "node_selector_done",
            cycle_id=state["cycle_id"],
            selected=len(selected),
            reason=reason,
        )
        return {**state, "selected_articles": selected, "article_index": 0}

    except Exception as e:
        logger.error("node_selector_failed", error=str(e))
        # Fallback : prendre les 3 premiers
        fallback = raw[:3]
        state["errors"].append(f"Selector LLM error: {e}")
        return {**state, "selected_articles": fallback, "article_index": 0}
