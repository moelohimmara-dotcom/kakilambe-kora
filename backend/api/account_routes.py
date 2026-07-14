"""
Routes de compte utilisateur — remplace le bloc "Éditeur / kakilambe.com"
en dur de la sidebar par de vraies données persistées (migration 010).

GET   /api/account/me            → profil du compte connecté (nom, email, thème, rôle)
PATCH /api/account/profile       → modifier le nom affiché
POST  /api/account/credentials   → modifier email et/ou mot de passe (mot de passe actuel requis)
PATCH /api/account/theme         → modifier le thème ('light' | 'dark')

GET   /api/account/admin/users        → (rôle admin) liste tous les comptes
PATCH /api/account/admin/users/{id}   → (rôle admin) modifier nom/thème/email d'un compte donné
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from core.logger import logger
from core.security import hash_password, verify_password, verify_session_token
from db.connection import get_db

router = APIRouter()

SESSION_COOKIE = "kora_session"
ADMIN_COOKIE   = "kora_admin_token"


async def _current_user(request: Request) -> Optional[dict]:
    """
    Résout l'utilisateur courant à partir du jeton de session (éditorial OU
    admin — les deux cookies portent le même format signé depuis la
    migration 010). Retourne None si aucun jeton valide, plutôt que de lever
    une exception — chaque route décide elle-même du code HTTP à renvoyer.
    """
    token = request.cookies.get(SESSION_COOKIE) or request.cookies.get(ADMIN_COOKIE)
    if not token:
        return None
    payload = verify_session_token(token)
    if not payload:
        return None

    async with get_db() as db:
        result = await db.execute(
            text("SELECT id, email, display_name, theme, role FROM users WHERE id = :id"),
            {"id": payload["sub"]},
        )
        row = result.mappings().first()
        return dict(row) if row else None


def _serialize(user: dict) -> dict:
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "display_name": user["display_name"],
        "theme": user["theme"],
        "role": user["role"],
    }


# ── Profil du compte connecté ─────────────────────────────────────────────────

@router.get("/me")
async def get_me(request: Request):
    user = await _current_user(request)
    if not user:
        return JSONResponse({"detail": "Non authentifié"}, status_code=401)
    return _serialize(user)


class ProfileUpdate(BaseModel):
    display_name: str


@router.patch("/profile")
async def update_profile(body: ProfileUpdate, request: Request):
    user = await _current_user(request)
    if not user:
        return JSONResponse({"detail": "Non authentifié"}, status_code=401)

    display_name = body.display_name.strip()
    if not display_name or len(display_name) > 80:
        return JSONResponse({"detail": "Nom invalide (1 à 80 caractères)"}, status_code=400)

    async with get_db() as db:
        await db.execute(
            text("UPDATE users SET display_name = :name, updated_at = now() WHERE id = :id"),
            {"name": display_name, "id": user["id"]},
        )
    logger.info("account_profile_updated", user_id=str(user["id"]))
    return {"ok": True, "display_name": display_name}


# ── Identifiants (email / mot de passe) ───────────────────────────────────────

class CredentialsUpdate(BaseModel):
    current_password: str
    new_email: Optional[str] = None
    new_password: Optional[str] = None


@router.post("/credentials")
async def update_credentials(body: CredentialsUpdate, request: Request):
    user = await _current_user(request)
    if not user:
        return JSONResponse({"detail": "Non authentifié"}, status_code=401)

    async with get_db() as db:
        result = await db.execute(
            text("SELECT password_hash FROM users WHERE id = :id"), {"id": user["id"]}
        )
        row = result.mappings().first()

    # Confirmation obligatoire du mot de passe ACTUEL avant tout changement
    # d'identifiants — exigence explicite de sécurité, jamais contournable.
    if not row or not verify_password(body.current_password, row["password_hash"]):
        return JSONResponse({"detail": "Mot de passe actuel incorrect"}, status_code=401)

    if not body.new_email and not body.new_password:
        return JSONResponse({"detail": "Aucun changement fourni"}, status_code=400)

    updates = {}
    if body.new_email:
        new_email = body.new_email.strip().lower()
        if "@" not in new_email:
            return JSONResponse({"detail": "Email invalide"}, status_code=400)
        updates["email"] = new_email
    if body.new_password:
        if len(body.new_password) < 8:
            return JSONResponse({"detail": "Le mot de passe doit faire au moins 8 caractères"}, status_code=400)
        # Hashé ici, jamais stocké ni journalisé en clair — le mot de passe
        # en clair ne quitte jamais cette fonction après ce point.
        updates["password_hash"] = hash_password(body.new_password)

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    async with get_db() as db:
        try:
            await db.execute(
                text(f"UPDATE users SET {set_clause}, updated_at = now() WHERE id = :id"),
                {**updates, "id": user["id"]},
            )
        except Exception as e:
            # Contrainte UNIQUE(email) — ne JAMAIS journaliser le mot de
            # passe fourni, seulement l'email en conflit.
            logger.warning("account_credentials_update_failed", user_id=str(user["id"]), error=str(e)[:200])
            return JSONResponse({"detail": "Cet email est déjà utilisé"}, status_code=409)

    logger.info(
        "account_credentials_updated",
        user_id=str(user["id"]),
        email_changed=bool(body.new_email),
        password_changed=bool(body.new_password),
    )
    return {"ok": True, "email": updates.get("email", user["email"])}


# ── Thème ─────────────────────────────────────────────────────────────────────

class ThemeUpdate(BaseModel):
    theme: str


@router.patch("/theme")
async def update_theme(body: ThemeUpdate, request: Request):
    user = await _current_user(request)
    if not user:
        return JSONResponse({"detail": "Non authentifié"}, status_code=401)
    if body.theme not in ("light", "dark"):
        return JSONResponse({"detail": "Thème invalide"}, status_code=400)

    async with get_db() as db:
        await db.execute(
            text("UPDATE users SET theme = :theme, updated_at = now() WHERE id = :id"),
            {"theme": body.theme, "id": user["id"]},
        )
    return {"ok": True, "theme": body.theme}


# ── Supervision admin ──────────────────────────────────────────────────────────
# Permet à un compte admin de consulter/modifier les réglages (nom, thème,
# email) d'un utilisateur donné — jamais le mot de passe en clair, jamais un
# accès qui contourne le hash bcrypt.

@router.get("/admin/users")
async def admin_list_users(request: Request):
    user = await _current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"detail": "Accès refusé"}, status_code=403)

    async with get_db() as db:
        result = await db.execute(
            text("SELECT id, email, display_name, theme, role, created_at, updated_at FROM users ORDER BY created_at")
        )
        rows = result.mappings().all()
    return {"users": [
        {**_serialize(dict(r)), "created_at": r["created_at"].isoformat(), "updated_at": r["updated_at"].isoformat()}
        for r in rows
    ]}


class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = None
    theme: Optional[str] = None
    email: Optional[str] = None


@router.patch("/admin/users/{user_id}")
async def admin_update_user(user_id: str, body: AdminUserUpdate, request: Request):
    requester = await _current_user(request)
    if not requester or requester["role"] != "admin":
        return JSONResponse({"detail": "Accès refusé"}, status_code=403)

    updates = {}
    if body.display_name is not None:
        updates["display_name"] = body.display_name.strip()
    if body.theme is not None:
        if body.theme not in ("light", "dark"):
            return JSONResponse({"detail": "Thème invalide"}, status_code=400)
        updates["theme"] = body.theme
    if body.email is not None:
        updates["email"] = body.email.strip().lower()

    if not updates:
        return JSONResponse({"detail": "Aucun changement fourni"}, status_code=400)

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    async with get_db() as db:
        result = await db.execute(
            text(f"UPDATE users SET {set_clause}, updated_at = now() WHERE id = :id RETURNING id"),
            {**updates, "id": user_id},
        )
        if not result.mappings().first():
            return JSONResponse({"detail": "Utilisateur introuvable"}, status_code=404)

    logger.info("account_admin_updated_user", admin_id=str(requester["id"]), target_user_id=user_id)
    return {"ok": True}
