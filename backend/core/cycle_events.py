"""
Événements de cycle temps réel (SSE) — extrait de api/agent_routes.py pour
être importable depuis les nœuds du pipeline (agent/nodes/*.py) sans créer de
dépendance circulaire (agent_routes.py importe déjà agent.graph, qui importe
les nœuds).

Avant cette extraction, emit_log() n'était appelé que depuis agent_routes.py
avec 3-4 messages génériques (début, pause HITL, fin) — jamais depuis les
nœuds eux-mêmes, qui ne font que logger.info() (structlog, jamais poussé au
flux SSE). Un cycle réel de 70+ secondes n'affichait donc au frontend qu'une
rotation de messages factices sans rapport avec l'avancement réel, pendant
que le vrai détail (scraping en cours, X articles retenus, rédaction...)
restait invisible dans les logs serveur uniquement.
"""
import asyncio
import json

from core.logger import logger

# { cycle_id: asyncio.Queue }
_log_queues: dict[str, asyncio.Queue] = {}

_SENTINEL = object()  # signal de fin de stream


def create_queue(cycle_id: str) -> asyncio.Queue:
    queue = asyncio.Queue()
    _log_queues[cycle_id] = queue
    return queue


def get_queue(cycle_id: str) -> "asyncio.Queue | None":
    return _log_queues.get(cycle_id)


def drop_queue(cycle_id: str) -> None:
    _log_queues.pop(cycle_id, None)


def emit_log(cycle_id: str, level: str, event: str) -> None:
    """
    Publie un log dans la queue SSE du cycle, dans le logger structuré, et le
    persiste en base (fire-and-forget) pour survivre à un redémarrage backend
    et permettre le replay d'historique à la connexion SSE.
    """
    payload = {"cycle_id": cycle_id[:8], "level": level, "event": event}
    logger.info("cycle_event", cycle_id=cycle_id[:8], msg=event)
    queue = _log_queues.get(cycle_id)
    if queue is not None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass
    asyncio.create_task(_persist_log(cycle_id, level, event))


def close_stream(cycle_id: str) -> None:
    """Ferme proprement la queue SSE d'un cycle (envoie le sentinel de fin)."""
    q = _log_queues.get(cycle_id)
    if q:
        try:
            q.put_nowait(_SENTINEL)
        except asyncio.QueueFull:
            pass


async def _persist_log(cycle_id: str, level: str, event: str) -> None:
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            await db.execute(
                text("INSERT INTO cycle_logs (cycle_id, level, event) VALUES (:cid, :level, :event)"),
                {"cid": cycle_id, "level": level, "event": event},
            )
    except Exception as e:
        logger.warning("persist_log_failed", cycle_id=cycle_id, error=str(e))


async def get_cycle_logs_history(cycle_id: str, limit: int = 200) -> list[dict]:
    """Logs persistés pour ce cycle — rejoués en tête de flux SSE."""
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            result = await db.execute(
                text("""
                    SELECT level, event, created_at FROM cycle_logs
                    WHERE cycle_id = :cid ORDER BY created_at ASC LIMIT :limit
                """),
                {"cid": cycle_id, "limit": limit},
            )
            rows = result.mappings().all()
        return [
            {"cycle_id": cycle_id[:8], "level": r["level"], "event": r["event"]}
            for r in rows
        ]
    except Exception as e:
        logger.warning("cycle_logs_history_failed", cycle_id=cycle_id, error=str(e))
        return []


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
