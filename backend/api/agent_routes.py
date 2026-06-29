"""
Routes FastAPI — Agent KORA
POST /api/agent/run       → Lance un cycle
GET  /api/agent/status    → État du cycle en cours
GET  /api/agent/stream    → SSE : logs temps réel
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
from core.config import settings

router = APIRouter()

# ── Store cycles en mémoire (Redis comme source de vérité en prod) ────────────
# { cycle_id: { status, mode, article_index, published_count, errors, ... } }
_cycles: dict = {}


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
        from agent.graph import kora_graph
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

    asyncio.create_task(_run())
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
    """SSE : émet les logs structurés en temps réel via Redis pub/sub."""

    async def event_generator():
        channel = f"kora:logs:{cycle_id}" if cycle_id else "kora:logs"
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL)
            pubsub = r.pubsub()
            await pubsub.subscribe(channel)

            yield _sse_event({"event": "connected", "channel": channel})

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    yield _sse_event(json.loads(message["data"]))

                # Heartbeat toutes les 10s pour garder la connexion
                await asyncio.sleep(0.5)

        except Exception:
            # Fallback sans Redis : polling de l'état en mémoire
            last_sent = 0
            while True:
                if cycle_id and cycle_id in _cycles:
                    cycle = _cycles[cycle_id]
                    current_count = cycle.get("published_count", 0)
                    if current_count != last_sent:
                        last_sent = current_count
                        yield _sse_event({
                            "level": "INFO",
                            "event": f"{current_count} article(s) publié(s)",
                            "status": cycle["status"],
                        })
                yield _sse_event({"event": "heartbeat"})
                await asyncio.sleep(5)

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
        from agent.graph import kora_graph
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
    """Publie un log sur Redis et dans le logger structuré."""
    payload = {"cycle_id": cycle_id[:8], "level": level, "event": event}
    logger.info("cycle_event", **payload)
    try:
        import redis as redis_sync
        r = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
        r.publish("kora:logs", json.dumps(payload))
        r.publish(f"kora:logs:{cycle_id}", json.dumps(payload))
        r.close()
    except Exception:
        pass


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
