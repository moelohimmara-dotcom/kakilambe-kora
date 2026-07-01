"""
test_v3_phase2.py — Validation locale du Plan V3 Phase 2 (kill switch,
persistance des logs, normalisation de /status).

Exécution : python test_v3_phase2.py
"""
import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(__file__))

_PASSED = 0
_FAILED = 0


def _check(name: str, ok: bool, detail: str = ""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} — {detail}")


async def test_normalize_db_cycle():
    """La normalisation aligne les deux formes de réponse de /status."""
    import api.agent_routes as agent_routes

    db_row = {
        "id": "abc-123", "status": "PAUSED", "mode": "semi",
        "articles_collected": 5, "articles_selected": 3, "articles_published": 1,
        "articles_rejected": 0, "started_at": "2026-07-01T00:00:00", "completed_at": None,
    }
    normalized = agent_routes._normalize_db_cycle(db_row)
    _check(
        "_normalize_db_cycle: cycle_id présent (pas 'id')",
        normalized["cycle_id"] == "abc-123",
    )
    _check(
        "_normalize_db_cycle: published_count aligné sur articles_published",
        normalized["published_count"] == 1,
    )
    _check(
        "_normalize_db_cycle: status préservé",
        normalized["status"] == "PAUSED",
    )


async def test_kill_switch_cancels_real_task():
    """
    Preuve que le kill switch annule une VRAIE tâche asyncio en vol, pas
    seulement un flag DB pendant que le graphe continuerait silencieusement.
    """
    import api.agent_routes as agent_routes

    cycle_id = "test-cancel-001"
    agent_routes._cycles[cycle_id] = {"status": "RUNNING", "mode": "auto", "published_count": 0, "errors": []}
    agent_routes._log_queues[cycle_id] = asyncio.Queue()

    work_started = asyncio.Event()

    async def _fake_long_running_cycle():
        work_started.set()
        try:
            await asyncio.sleep(999)  # simule un cycle bloqué en plein travail
        except asyncio.CancelledError:
            agent_routes._cycles[cycle_id]["status"] = "CANCELLED"
            raise
        finally:
            agent_routes._running_tasks.pop(cycle_id, None)

    with patch("api.agent_routes._update_cycle_status", new_callable=AsyncMock):
        task = asyncio.create_task(_fake_long_running_cycle())
        agent_routes._running_tasks[cycle_id] = task
        await work_started.wait()

        _check("kill_switch: la tâche est bien enregistrée et en cours", not task.done())

        # Appelle le VRAI endpoint cancel_cycle()
        result = await agent_routes.cancel_cycle(cycle_id)

        # Laisse la CancelledError se propager dans la tâche annulée
        try:
            await task
        except asyncio.CancelledError:
            pass

    _check("kill_switch: endpoint renvoie status=CANCELLED", result["status"] == "CANCELLED")
    _check(
        "kill_switch: la tâche annulée a réellement mis à jour le statut en mémoire",
        agent_routes._cycles[cycle_id]["status"] == "CANCELLED",
    )
    _check(
        "kill_switch: la tâche est retirée du registre après annulation",
        cycle_id not in agent_routes._running_tasks,
    )

    # Nettoyage
    agent_routes._cycles.pop(cycle_id, None)
    agent_routes._log_queues.pop(cycle_id, None)


async def test_cancel_already_terminal_cycle_rejected():
    """Un cycle déjà terminé ne peut pas être annulé (400, pas de comportement silencieux)."""
    import api.agent_routes as agent_routes
    from fastapi import HTTPException

    cycle_id = "test-cancel-002"
    agent_routes._cycles[cycle_id] = {"status": "COMPLETED", "mode": "auto", "published_count": 3, "errors": []}

    raised = False
    try:
        await agent_routes.cancel_cycle(cycle_id)
    except HTTPException as e:
        raised = e.status_code == 400

    _check("kill_switch: annuler un cycle COMPLETED lève une 400 (pas un faux succès)", raised)
    agent_routes._cycles.pop(cycle_id, None)


async def test_emit_log_persists_to_db():
    """_emit_log() enfile bien une tâche de persistance en base (fire-and-forget)."""
    import api.agent_routes as agent_routes

    with patch("api.agent_routes._persist_log", new_callable=AsyncMock) as mock_persist:
        agent_routes._emit_log("cycle-xyz", "INFO", "Test event")
        await asyncio.sleep(0)  # laisse le create_task s'exécuter
        mock_persist.assert_called_once_with("cycle-xyz", "INFO", "Test event")

    _check("_emit_log: persistance DB déclenchée avec les bons paramètres", True)


async def main():
    print("=" * 60)
    print("  KORA V3 — Phase 2 (kill switch, logs, reprise de session)")
    print("=" * 60)
    print("\n>> Normalisation /status")
    await test_normalize_db_cycle()
    print("\n>> Kill switch")
    await test_kill_switch_cancels_real_task()
    await test_cancel_already_terminal_cycle_rejected()
    print("\n>> Persistance des logs")
    await test_emit_log_persists_to_db()

    print("\n" + "=" * 60)
    print(f"  Resultat : {_PASSED}/{_PASSED + _FAILED} tests passes")
    print("  [OK] Validation locale reussie" if _FAILED == 0 else f"  [FAIL] {_FAILED} test(s) echoue(s)")
    print("=" * 60)
    return 0 if _FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
