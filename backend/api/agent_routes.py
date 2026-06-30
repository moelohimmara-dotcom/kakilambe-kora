"""
Routes FastAPI — Agent KORA
POST /api/agent/run       → Lance un cycle
GET  /api/agent/status    → État du cycle en cours
GET  /api/agent/stream    → SSE : logs temps réel (asyncio Queue, sans Redis)
POST /api/agent/resume/{cycle_id} → Reprend après validation HITL
"""
import uuid
import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from core.logger import logger

router = APIRouter()

# ── Store cycles en mémoire ───────────────────────────────────────────────────
# { cycle_id: { status, mode, published_count, errors } }
_cycles: dict = {}

# ── Queues de logs SSE par cycle (asyncio, pas de Redis requis) ───────────────
# { cycle_id: asyncio.Queue }  — créée au lancement, nettoyée après 5 min
_log_queues: dict[str, asyncio.Queue] = {}

_SENTINEL = object()  # signal de fin de stream


class RunRequest(BaseModel):
    mode: str = "semi"   # "auto" | "semi"


# ── POST /run ─────────────────────────────────────────────────────────────────

@router.post("/run")
async def run_cycle(body: RunRequest):
    if body.mode not in ("auto", "semi"):
        raise HTTPException(status_code=400, detail="mode must be 'auto' or 'semi'")

    cycle_id = str(uuid.uuid4())

    # Enregistre le cycle en base
    await _persist_cycle(cycle_id, body.mode)

    initial_state = {
        "mode": body.mode,
        "cycle_id": cycle_id,
        "raw_sources": [],
        "selected_articles": [],
        "current_article": None,
        "generated_article": None,
        "image_url": None,
        "wp_media_id": None,
        "wp_post_id": None,
        "published_count": 0,
        "errors": [],
        "hitl_approved": False,
        "article_index": 0,
    }

    _cycles[cycle_id] = {
        "status": "RUNNING",
        "mode": body.mode,
        "published_count": 0,
        "errors": [],
    }

    config = {"configurable": {"thread_id": cycle_id}}

    async def _run():
        from agent.graph import kora_graph_semi, kora_graph_auto
        kora_graph = kora_graph_semi if body.mode == "semi" else kora_graph_auto
        try:
            _emit_log(cycle_id, "INFO", f"Cycle {body.mode.upper()} démarré")
            result = await kora_graph.ainvoke(initial_state, config=config)

            if body.mode == "semi":
                _cycles[cycle_id]["status"] = "PAUSED"
                _emit_log(cycle_id, "HITL", "En attente de validation humaine")
            else:
                _cycles[cycle_id]["status"] = "COMPLETED"
                _emit_log(cycle_id, "OK", "Cycle complété")

            if result:
                _cycles[cycle_id]["published_count"] = result.get("published_count", 0)
                _cycles[cycle_id]["errors"] = result.get("errors", [])

        except Exception as e:
            _cycles[cycle_id]["status"] = "FAILED"
            _cycles[cycle_id]["errors"].append(str(e))
            _emit_log(cycle_id, "ERROR", f"Cycle échoué : {e}")
            logger.error("cycle_run_failed", cycle_id=cycle_id, error=str(e))
            await _update_cycle_status(cycle_id, "FAILED")

    _log_queues[cycle_id] = asyncio.Queue()
    asyncio.create_task(_run())
    asyncio.create_task(_cleanup_queue(cycle_id, delay=300))
    logger.info("cycle_started", cycle_id=cycle_id, mode=body.mode)

    return {
        "cycle_id": cycle_id,
        "status": "RUNNING",
        "mode": body.mode,
        "message": "Cycle lancé. Utilisez /status ou /stream pour suivre l'avancement.",
    }


# ── GET /status ───────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status(cycle_id: Optional[str] = None):
    if cycle_id:
        cycle = _cycles.get(cycle_id)
        if not cycle:
            # Cherche en base
            db_cycle = await _get_cycle_from_db(cycle_id)
            if not db_cycle:
                raise HTTPException(status_code=404, detail="Cycle non trouvé")
            return db_cycle
        return {"cycle_id": cycle_id, **cycle}

    if not _cycles:
        return {"status": "IDLE", "active_cycles": 0, "message": "Aucun cycle en cours"}

    # Retourne le dernier cycle
    latest_id, latest = list(_cycles.items())[-1]
    running = sum(1 for c in _cycles.values() if c["status"] == "RUNNING")
    return {
        "cycle_id": latest_id,
        **latest,
        "active_cycles": running,
        "total_cycles": len(_cycles),
    }


# ── GET /stream (SSE) ─────────────────────────────────────────────────────────

@router.get("/stream")
async def stream_logs(cycle_id: Optional[str] = None):
    """SSE : émet les logs structurés en temps réel via asyncio Queue (sans Redis)."""

    async def event_generator():
        queue = _log_queues.get(cycle_id) if cycle_id else None

        yield _sse_event({"event": "connected", "cycle_id": cycle_id})

        heartbeat_counter = 0
        while True:
            if queue is not None:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                    if msg is _SENTINEL:
                        yield _sse_event({"event": "done"})
                        break
                    yield _sse_event(msg)
                    continue
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(5)

            # Heartbeat toutes les 5s pour garder la connexion HTTP
            heartbeat_counter += 1
            yield _sse_event({"event": "heartbeat", "tick": heartbeat_counter})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── POST /resume/{cycle_id} ───────────────────────────────────────────────────

@router.post("/resume/{cycle_id}")
async def resume_cycle(cycle_id: str):
    """
    Reprend un cycle en pause après validation HITL.
    LangGraph reprend depuis le checkpoint MemorySaver.
    """
    cycle = _cycles.get(cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle non trouvé")
    if cycle.get("status") not in ("PAUSED",):
        raise HTTPException(
            status_code=400,
            detail=f"Cycle ne peut pas être repris (status: {cycle.get('status')})"
        )

    config = {"configurable": {"thread_id": cycle_id}}
    _cycles[cycle_id]["status"] = "RUNNING"

    async def _resume():
        from agent.graph import kora_graph_semi as kora_graph
        try:
            _emit_log(cycle_id, "HITL", "Validation humaine accordée — reprise de la publication")
            # Injecter l'approbation dans l'état via update
            await kora_graph.aupdate_state(
                config,
                {"hitl_approved": True},
                as_node="generate_image",
            )
            result = await kora_graph.ainvoke(None, config=config)

            if result:
                # Vérifie s'il reste des articles
                idx = result.get("article_index", 0)
                selected = result.get("selected_articles", [])
                if idx < len(selected):
                    _cycles[cycle_id]["status"] = "PAUSED"
                    _emit_log(cycle_id, "HITL", f"Article suivant en attente ({idx+1}/{len(selected)})")
                else:
                    _cycles[cycle_id]["status"] = "COMPLETED"
                    _cycles[cycle_id]["published_count"] = result.get("published_count", 0)
                    _emit_log(cycle_id, "OK", "Tous les articles traités")

            await _update_cycle_status(cycle_id, _cycles[cycle_id]["status"])

        except Exception as e:
            _cycles[cycle_id]["status"] = "FAILED"
            _emit_log(cycle_id, "ERROR", f"Erreur après reprise : {e}")
            logger.error("cycle_resume_failed", cycle_id=cycle_id, error=str(e))

    asyncio.create_task(_resume())
    return {
        "cycle_id": cycle_id,
        "status": "RUNNING",
        "message": "Cycle repris — publication en cours",
    }


# ── POST /reject/{cycle_id} ───────────────────────────────────────────────────

@router.post("/reject/{cycle_id}")
async def reject_current_article(cycle_id: str):
    """Rejette l'article en attente et passe au suivant."""
    cycle = _cycles.get(cycle_id)
    if not cycle or cycle.get("status") != "PAUSED":
        raise HTTPException(status_code=400, detail="Cycle non en pause")

    config = {"configurable": {"thread_id": cycle_id}}
    from agent.graph import kora_graph

    try:
        snapshot = await kora_graph.aget_state(config)
        if snapshot and snapshot.values:
            article = snapshot.values.get("generated_article")
            db_id = (article or {}).get("db_id", "")
            if db_id and db_id != "unknown":
                from db.connection import get_db
                async with get_db() as db:
                    await db.execute(
                        text("UPDATE articles SET status='REJECTED' WHERE id=:id"),
                        {"id": db_id},
                    )
            # Avance l'index pour passer à l'article suivant
            idx = snapshot.values.get("article_index", 0)
            await kora_graph.aupdate_state(
                config,
                {"article_index": idx + 1, "generated_article": None, "hitl_approved": False},
                as_node="generate_image",
            )
    except Exception as e:
        logger.warning("reject_state_update_failed", error=str(e))

    # Reprend automatiquement avec le prochain article
    return await resume_cycle(cycle_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _emit_log(cycle_id: str, level: str, event: str):
    """Publie un log dans la queue SSE du cycle et dans le logger structuré."""
    payload = {"cycle_id": cycle_id[:8], "level": level, "event": event}
    logger.info("cycle_event", cycle_id=cycle_id[:8], msg=event)
    queue = _log_queues.get(cycle_id)
    if queue is not None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass


async def _cleanup_queue(cycle_id: str, delay: int = 300):
    """Envoie le sentinel de fin puis supprime la queue après `delay` secondes."""
    await asyncio.sleep(delay)
    queue = _log_queues.get(cycle_id)
    if queue is not None:
        try:
            queue.put_nowait(_SENTINEL)
        except asyncio.QueueFull:
            pass
        await asyncio.sleep(30)
        _log_queues.pop(cycle_id, None)


async def _persist_cycle(cycle_id: str, mode: str):
    try:
        from db.connection import get_db
        async with get_db() as db:
            await db.execute(
                text("INSERT INTO cycles (id, mode, status) VALUES (:id, :mode, 'RUNNING')"),
                {"id": cycle_id, "mode": mode},
            )
    except Exception as e:
        logger.warning("persist_cycle_failed", error=str(e))


async def _update_cycle_status(cycle_id: str, status: str):
    try:
        from db.connection import get_db
        async with get_db() as db:
            await db.execute(
                text("UPDATE cycles SET status=:s, completed_at=now() WHERE id=:id"),
                {"s": status, "id": cycle_id},
            )
    except Exception as e:
        logger.warning("update_cycle_failed", error=str(e))


async def _get_cycle_from_db(cycle_id: str) -> Optional[dict]:
    try:
        from db.connection import get_db
        async with get_db() as db:
            result = await db.execute(
                text("SELECT * FROM cycles WHERE id=:id"), {"id": cycle_id}
            )
            row = result.mappings().first()
            return dict(row) if row else None
    except Exception:
        return None
