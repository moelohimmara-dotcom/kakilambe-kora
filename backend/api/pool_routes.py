"""
Contrôle admin du système de veille passive (migration 011, agent/pool.py).

GET   /api/pool/status          → état courant (par source, par statut, dernier job)
POST  /api/pool/admin/run-now   → déclenche un cycle de veille hors planning
PATCH /api/pool/admin/settings  → fréquence de veille / seuil de dédup
POST  /api/pool/admin/reset     → vide le pool + réinitialise l'historique de jobs

Root cause du besoin d'un vrai contrôle admin (audit 2026-07-14) : aucune
route backend existante ne porte de garde d'authentification au niveau
FastAPI (le périmètre /system est protégé UNIQUEMENT par le middleware
Next.js en frontal). Une action aussi consécutive qu'un reset complet du
pool mérite mieux qu'un simple "protégé parce que non appelé ailleurs" —
require_admin() ci-dessous est une garde explicite, ajoutée seulement sur
ces routes (pas un refactor global de l'auth existante, hors périmètre de
cette tâche).
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from core.logger import logger
from core.security import verify_session_token
from db.connection import get_db

router = APIRouter()

ADMIN_COOKIE = "kora_admin_token"


async def require_admin(request: Request) -> dict:
    token = request.cookies.get(ADMIN_COOKIE)
    payload = verify_session_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Non authentifié")

    async with get_db() as db:
        result = await db.execute(text("SELECT id, role FROM users WHERE id = :id"), {"id": payload["sub"]})
        user = result.mappings().first()
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return dict(user)


@router.get("/status")
async def pool_status(request: Request):
    await require_admin(request)

    async with get_db() as db:
        by_source = await db.execute(text("""
            SELECT source_name,
                   count(*) FILTER (WHERE status = 'available') AS available,
                   count(*) FILTER (WHERE status = 'used') AS used,
                   count(*) FILTER (WHERE status = 'expired') AS expired
            FROM content_pool
            WHERE collection_date = CURRENT_DATE
            GROUP BY source_name ORDER BY source_name
        """))
        sources = [dict(r) for r in by_source.mappings().all()]

        last_job = await db.execute(text("""
            SELECT id, trigger, started_at, finished_at, sources_scanned,
                   items_collected, duplicates_linked, status, error
            FROM pool_jobs ORDER BY started_at DESC LIMIT 1
        """))
        job_row = last_job.mappings().first()

        recent_jobs = await db.execute(text("""
            SELECT trigger, started_at, finished_at, sources_scanned,
                   items_collected, duplicates_linked, status
            FROM pool_jobs ORDER BY started_at DESC LIMIT 10
        """))
        history = [dict(r) for r in recent_jobs.mappings().all()]

        settings_row = await db.execute(text(
            "SELECT key, value FROM app_settings WHERE key IN ('pool_interval_hours', 'pool_dedup_threshold')"
        ))
        settings_map = {r["key"]: r["value"] for r in settings_row.mappings().all()}

    def _iso(v):
        return v.isoformat() if v else None

    return {
        "sources": sources,
        "total_available": sum(s["available"] for s in sources),
        "total_used": sum(s["used"] for s in sources),
        "total_expired": sum(s["expired"] for s in sources),
        "last_job": {**dict(job_row), "started_at": _iso(job_row["started_at"]), "finished_at": _iso(job_row["finished_at"])} if job_row else None,
        "recent_jobs": [{**j, "started_at": _iso(j["started_at"]), "finished_at": _iso(j["finished_at"])} for j in history],
        "settings": {
            "pool_interval_hours": int(settings_map.get("pool_interval_hours", 2)),
            "pool_dedup_threshold": float(settings_map.get("pool_dedup_threshold", 0.6)),
        },
    }


@router.post("/admin/run-now")
async def pool_run_now(request: Request):
    await require_admin(request)
    from agent.pool import run_pooling_job
    try:
        result = await run_pooling_job(trigger="manual_admin")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Échec de la veille manuelle : {e}")
    return result


class PoolSettingsUpdate(BaseModel):
    pool_interval_hours: Optional[int] = None
    pool_dedup_threshold: Optional[float] = None


@router.patch("/admin/settings")
async def pool_update_settings(body: PoolSettingsUpdate, request: Request):
    await require_admin(request)

    if body.pool_interval_hours is not None and body.pool_interval_hours < 1:
        raise HTTPException(status_code=400, detail="La fréquence doit être d'au moins 1 heure")
    if body.pool_dedup_threshold is not None and not (0 < body.pool_dedup_threshold <= 1):
        raise HTTPException(status_code=400, detail="Le seuil de déduplication doit être entre 0 et 1")

    async with get_db() as db:
        if body.pool_interval_hours is not None:
            await db.execute(
                text("UPDATE app_settings SET value = :v, updated_at = now() WHERE key = 'pool_interval_hours'"),
                {"v": str(body.pool_interval_hours)},
            )
        if body.pool_dedup_threshold is not None:
            await db.execute(
                text("UPDATE app_settings SET value = :v, updated_at = now() WHERE key = 'pool_dedup_threshold'"),
                {"v": str(body.pool_dedup_threshold)},
            )

    if body.pool_interval_hours is not None:
        from core.scheduler import reschedule_pool_interval
        reschedule_pool_interval(body.pool_interval_hours)

    logger.info(
        "pool_settings_updated",
        pool_interval_hours=body.pool_interval_hours,
        pool_dedup_threshold=body.pool_dedup_threshold,
    )
    return {"ok": True}


@router.post("/admin/reset")
async def pool_reset(request: Request):
    """
    Vide entièrement le pool et l'historique de jobs — permet à un admin de
    repartir sur une base saine après un incident, sans accès DB direct
    (cf. exemple "comportement_attendu" de la demande initiale).
    """
    user = await require_admin(request)
    async with get_db() as db:
        deleted_pool = await db.execute(text("DELETE FROM content_pool RETURNING id"))
        pool_count = len(deleted_pool.mappings().all())
        deleted_jobs = await db.execute(text("DELETE FROM pool_jobs RETURNING id"))
        jobs_count = len(deleted_jobs.mappings().all())

    logger.warning(
        "pool_reset_by_admin",
        admin_id=str(user["id"]), pool_rows_deleted=pool_count, job_rows_deleted=jobs_count,
    )
    return {"ok": True, "pool_rows_deleted": pool_count, "job_rows_deleted": jobs_count}
