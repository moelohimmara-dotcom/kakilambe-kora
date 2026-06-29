"""
Graphe LangGraph KORA — GuinéePress Intelligence

Architecture :
  scrape_sources → select_articles → [boucle article]
                                          write_article → generate_image
                                              ↓ (si semi) interrupt avant publish
                                          publish_wordpress ←── resume() HITL
                                              ↓
                                     [article suivant ou fin]
                                          send_report → END

Le mode "semi" interrompt AVANT publish_wordpress sur CHAQUE article.
Le mode "auto" publie directement.
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import KoraState
from agent.nodes import scraper, selector, writer, illustrator, publisher, reporter
from core.logger import logger


# ── Fonctions routage ─────────────────────────────────────────────────────────

def _route_after_select(state: KoraState) -> str:
    """Après sélection : articles disponibles → write_article, sinon rapport."""
    if state.get("selected_articles"):
        return "write_article"
    return "send_report"


def _route_after_image(state: KoraState) -> str:
    """
    Après génération image :
    - mode semi + article prêt → interrupt (publish est configuré comme interrupt_before)
    - mode auto → publish directement
    - pas d'article → next_or_report
    """
    if not state.get("generated_article"):
        return "next_or_report"
    if state.get("mode") == "semi":
        return "publish_wordpress"   # le graph s'interrompt avant ce nœud (interrupt_before)
    return "publish_wordpress"


def _route_after_publish(state: KoraState) -> str:
    """Après publication d'un article : article suivant ou rapport final."""
    idx = state.get("article_index", 0)
    selected = state.get("selected_articles", [])
    if idx < len(selected):
        return "write_article"
    return "send_report"


def _route_after_write(state: KoraState) -> str:
    """Après rédaction : article généré → image, erreur → article suivant."""
    if state.get("generated_article"):
        return "generate_image"
    # Erreur de rédaction : passe au suivant
    return "_check_next"


def _check_next(state: KoraState) -> str:
    """Vérifie s'il reste des articles à traiter."""
    idx = state.get("article_index", 0)
    selected = state.get("selected_articles", [])
    if idx < len(selected):
        return "write_article"
    return "send_report"


# ── Nœud check_next (wrapper pour routeur conditionnel) ──────────────────────

async def _check_next_node(state: KoraState) -> KoraState:
    """Nœud passthrough utilisé comme point de décision."""
    return state


# ── Construction du graphe ────────────────────────────────────────────────────

def build_kora_graph():
    graph = StateGraph(KoraState)

    # Enregistrement des nœuds
    graph.add_node("scrape_sources",    scraper.run)
    graph.add_node("select_articles",   selector.run)
    graph.add_node("write_article",     writer.run)
    graph.add_node("generate_image",    illustrator.run)
    graph.add_node("publish_wordpress", publisher.run)
    graph.add_node("send_report",       reporter.run)
    graph.add_node("_check_next",       _check_next_node)

    # Point d'entrée
    graph.set_entry_point("scrape_sources")

    # Arête 1 : scrape → select
    graph.add_edge("scrape_sources", "select_articles")

    # Arête 2 : select → write ou rapport (si 0 article sélectionné)
    graph.add_conditional_edges(
        "select_articles",
        _route_after_select,
        {
            "write_article": "write_article",
            "send_report":   "send_report",
        },
    )

    # Arête 3 : write → image ou check_next (si erreur)
    graph.add_conditional_edges(
        "write_article",
        _route_after_write,
        {
            "generate_image": "generate_image",
            "_check_next":    "_check_next",
        },
    )

    # Arête 4 : image → publish (interrupt_before en mode semi est géré à la compilation)
    graph.add_conditional_edges(
        "generate_image",
        _route_after_image,
        {
            "publish_wordpress": "publish_wordpress",
            "next_or_report":    "_check_next",
        },
    )

    # Arête 5 : publish → article suivant ou rapport
    graph.add_conditional_edges(
        "publish_wordpress",
        _route_after_publish,
        {
            "write_article": "write_article",
            "send_report":   "send_report",
        },
    )

    # Arête 6 : check_next → write ou rapport
    graph.add_conditional_edges(
        "_check_next",
        _check_next,
        {
            "write_article": "write_article",
            "send_report":   "send_report",
        },
    )

    # Arête 7 : rapport → END
    graph.add_edge("send_report", END)

    # Compilation avec :
    # - MemorySaver : permet le resume après interruption HITL
    # - interrupt_before=["publish_wordpress"] : pause avant chaque publication en mode semi
    compiled = graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["publish_wordpress"],
    )

    logger.info("kora_graph_compiled")
    return compiled


kora_graph = build_kora_graph()
