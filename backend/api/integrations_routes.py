"""
Registre générique d'intégrations (migration 012) — remplace le tableau
figé côté frontend + les vérifications ad-hoc dispersées. Toute nouvelle
intégration (MCP server, API, futur LLM) s'ajoute par une simple ligne
(POST /api/integrations), jamais en modifiant le code d'orchestration, de
verrouillage, de failover LLM ou de veille déjà en place.

Contrat générique attendu de health_endpoint : {"status": "ok"|"error", "detail"?: str}
— c'est déjà la convention de TOUTES les routes /health/* existantes
(main.py), donc aucune d'elles n'a eu besoin d'être modifiée pour rejoindre
le registre.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional
import httpx
import asyncio

from core.logger import logger
from core.admin_auth import require_admin
from db.connection import get_db

router = APIRouter()

_KINDS = ("llm", "api", "mcp", "other")


async def _check_health(health_endpoint: str) -> dict:
    """
    Vérificateur GÉNÉRIQUE unique — fonctionne pour n'importe quelle
    intégration respectant le contrat {"status": ..., "detail"?: ...}, sans
    connaître la nature de l'intégration. C'est ce qui rend le registre
    ouvert à l'extension : aucun nouveau "cas spécial" à coder ici pour
    chaque nouvel outil.
    """
    base = "http://127.0.0.1:8000"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base}{health_endpoint}")
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        return {
            "status": body.get("status", "ok" if r.status_code < 400 else "error"),
            "detail": body.get("detail", ""),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)[:200]}


@router.get("")
async def list_integrations(request: Request):
    await require_admin(request)
    async with get_db() as db:
        result = await db.execute(text(
            "SELECT id, key, label, kind, description, health_endpoint, is_active, created_at "
            "FROM integrations ORDER BY created_at"
        ))
        rows = [dict(r) for r in result.mappings().all()]

    checks = await asyncio.gather(*[_check_health(r["health_endpoint"]) for r in rows])
    return {
        "integrations": [
            {
                "id": str(r["id"]), "key": r["key"], "label": r["label"], "kind": r["kind"],
                "description": r["description"], "health_endpoint": r["health_endpoint"],
                "is_active": r["is_active"], "created_at": r["created_at"].isoformat(),
                "status": check["status"], "detail": check["detail"],
            }
            for r, check in zip(rows, checks)
        ]
    }


class IntegrationCreate(BaseModel):
    key: str
    label: str
    kind: str
    description: Optional[str] = None
    health_endpoint: str


@router.post("")
async def create_integration(body: IntegrationCreate, request: Request):
    user = await require_admin(request)
    if body.kind not in _KINDS:
        raise HTTPException(status_code=400, detail=f"kind doit être l'un de {_KINDS}")

    async with get_db() as db:
        try:
            result = await db.execute(
                text("""
                    INSERT INTO integrations (key, label, kind, description, health_endpoint)
                    VALUES (:key, :label, :kind, :description, :health_endpoint)
                    RETURNING id
                """),
                {
                    "key": body.key.strip().lower(), "label": body.label.strip(),
                    "kind": body.kind, "description": body.description,
                    "health_endpoint": body.health_endpoint.strip(),
                },
            )
            row = result.mappings().first()
        except Exception as e:
            raise HTTPException(status_code=409, detail=f"Clé déjà utilisée ou invalide : {e}")

    logger.info("integration_registered", admin_id=str(user["id"]), key=body.key, kind=body.kind)
    return {"ok": True, "id": str(row["id"])}


@router.delete("/{integration_id}")
async def delete_integration(integration_id: str, request: Request):
    user = await require_admin(request)
    async with get_db() as db:
        result = await db.execute(
            text("DELETE FROM integrations WHERE id = :id RETURNING key"), {"id": integration_id}
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Intégration introuvable")

    logger.info("integration_removed", admin_id=str(user["id"]), key=row["key"])
    return {"ok": True}
