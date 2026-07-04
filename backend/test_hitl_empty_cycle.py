"""
test_hitl_empty_cycle.py — Preuve de la root cause du bug "Article prêt mais
introuvable" : quand aucun article n'est sélectionné (0 candidat pertinent),
le graphe LangGraph route directement vers send_report → END SANS jamais
atteindre interrupt_before=["publish_wordpress"], même en mode semi.

Confirme que aget_state(config).next est bien vide dans ce cas — c'est
exactement la condition que api/agent_routes.py vérifie désormais pour
distinguer une vraie interruption HITL d'une fin de graphe normale à vide
(avant le correctif, le code marquait PAUSED dans les deux cas).

Exécution (sur le VPS, où vivent les clés API/DB) :
    venv/bin/python test_hitl_empty_cycle.py
"""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_PASSED = 0
_FAILED = 0


def _check(name, ok, detail=""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} — {detail}")


async def main():
    print("\n=== test_hitl_empty_cycle — 0 article sélectionné, mode semi ===\n")
    from agent.graph import kora_graph_semi

    cycle_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": cycle_id}}

    # État déjà passé la sélection, avec 0 article retenu — simule
    # exactement le cas réel (scraping infructueux ou sélecteur strict).
    initial_state = {
        "mode": "semi", "cycle_id": cycle_id, "raw_sources": [],
        "selected_articles": [],  # <-- le coeur du scénario
        "current_article": None, "generated_article": None,
        "image_url": None, "wp_media_id": None, "wp_post_id": None,
        "published_count": 0, "errors": [], "hitl_approved": False,
        "article_index": 0,
    }

    print(">> Invocation du graphe avec selected_articles=[] (simule 0 candidat pertinent)")
    result = await kora_graph_semi.ainvoke(initial_state, config=config)

    snapshot = await kora_graph_semi.aget_state(config)
    really_interrupted = bool(snapshot.next)

    print(f"    result.generated_article = {result.get('generated_article') if result else None}")
    print(f"    snapshot.next = {snapshot.next!r}")

    _check(
        "le graphe N'EST PAS interrompu (aget_state().next vide) malgré le mode semi",
        not really_interrupted,
        f"snapshot.next={snapshot.next!r} — si non vide, la root cause supposée est fausse",
    )
    _check(
        "generated_article reste None (aucun article produit)",
        not (result or {}).get("generated_article"),
        str((result or {}).get("generated_article")),
    )

    print(
        "\n>> Conclusion : avant le correctif, api/agent_routes.py aurait marqué ce cycle "
        "PAUSED avec article_id=None (bug reproduit) ; après le correctif, il est "
        "marqué COMPLETED avec published_count=0 (comportement honnête).\n"
    )

    print(f"{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
