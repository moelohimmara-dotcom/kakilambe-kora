"""
Garde d'authentification admin partagée — extraite de api/pool_routes.py
(audit 2026-07-15) pour éviter de dupliquer cette vérification dans chaque
nouveau routeur admin (ex. api/integrations_routes.py). Root cause du
besoin : aucune route backend ne portait de garde d'auth au niveau FastAPI
avant la migration 010 (l'auth /system reposait uniquement sur le
middleware Next.js frontal) — chaque route admin ajoutée depuis réutilise
cette même fonction plutôt que de réimplémenter sa propre vérification.
"""
from fastapi import Request, HTTPException
from sqlalchemy import text

from core.security import verify_session_token
from db.connection import get_db

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
