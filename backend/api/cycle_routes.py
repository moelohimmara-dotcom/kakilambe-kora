"""
Routes FastAPI — Cycles
GET  /api/cycles         → liste paginée des cycles en base
GET  /api/cycles/{id}    → détail d'un cycle
"""
from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from typing import Optional

from db.connection import get_db

router = APIRouter()


_LIST_COLUMNS = (
    "id, mode, status, articles_collected, articles_selected, "
    "articles_published, articles_rejected, started_at, completed_at"
)


@router.get("")
async def list_cycles(page: int = 1, limit: int = 20, status: Optional[str] = None):
    offset = (page - 1) * limit
    async with get_db() as db:
        if status:
            result = await db.execute(
                text(f"""
                    SELECT {_LIST_COLUMNS}
                    FROM cycles
                    WHERE status = :status
                    ORDER BY started_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"status": status, "limit": limit, "offset": offset},
            )
            count = await db.execute(
                text("SELECT COUNT(*) FROM cycles WHERE status = :status"),
                {"status": status},
            )
        else:
            result = await db.execute(
                text(f"""
                    SELECT {_LIST_COLUMNS}
                    FROM cycles
                    ORDER BY started_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": limit, "offset": offset},
            )
            count = await db.execute(text("SELECT COUNT(*) FROM cycles"))

        rows = result.mappings().all()
        total = count.scalar() or 0

    return {"items": [jsonable_encoder(dict(r)) for r in rows], "total": total, "page": page}


@router.get("/stats")
async def cycles_stats():
    """
    Agrégats réels sur TOUS les cycles en base — /history calculait ces
    totaux (publiés/échoués/taux de succès) uniquement à partir des 20
    cycles les plus récents renvoyés par GET /api/cycles (page 1), ce qui
    les faisait diverger du total réel dès qu'il existait plus de 20 cycles.
    Doit rester déclaré AVANT /{cycle_id} pour ne pas être capturé comme un
    id de cycle par cette route générique.
    """
    async with get_db() as db:
        result = await db.execute(
            text("""
                SELECT
                    COUNT(*) AS total_cycles,
                    COALESCE(SUM(articles_published), 0) AS total_published,
                    COUNT(*) FILTER (WHERE status = 'FAILED') AS total_failed,
                    COUNT(*) FILTER (WHERE status = 'COMPLETED') AS total_completed,
                    COUNT(*) FILTER (WHERE status IN ('RUNNING', 'PAUSED')) AS total_running
                FROM cycles
            """)
        )
        row = result.mappings().first()

    total_cycles = row["total_cycles"] or 0
    success_rate = round((row["total_completed"] / total_cycles) * 100, 1) if total_cycles else 0

    return {
        "total_cycles": total_cycles,
        "total_published": int(row["total_published"]),
        "total_failed": int(row["total_failed"]),
        "total_completed": int(row["total_completed"]),
        "total_running": int(row["total_running"]),
        "success_rate": success_rate,
    }


@router.get("/{cycle_id}")
async def get_cycle(cycle_id: str):
    async with get_db() as db:
        result = await db.execute(
            text("SELECT * FROM cycles WHERE id = :id"),
            {"id": cycle_id},
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Cycle non trouvé")
    return jsonable_encoder(dict(row))
