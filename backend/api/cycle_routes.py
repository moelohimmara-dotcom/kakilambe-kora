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
