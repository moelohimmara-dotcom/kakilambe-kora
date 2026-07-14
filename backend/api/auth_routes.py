"""
Auth routes — session cookie-based authentication for KORA dashboard.
POST /api/auth/login    → validate credentials, set kora_session cookie
DELETE /api/auth/login  → clear session cookie
POST /api/auth/admin    → validate admin secret, set kora_admin_token cookie
DELETE /api/auth/admin  → clear admin cookie
GET  /api/auth/me       → check current session
"""
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from core.config import settings
from core.security import verify_password, create_session_token, verify_session_token
from db.connection import get_db

router = APIRouter()

SESSION_COOKIE  = "kora_session"
ADMIN_COOKIE    = "kora_admin_token"
COOKIE_MAX_AGE  = 60 * 60 * 8   # 8 h

# Un cookie Secure n'est envoyé par le navigateur que sur une connexion HTTPS
# (RFC 6265) — le forcer à True alors que APP_BASE_URL est en http:// (VPS
# sans domaine/certificat pour l'instant) fait que le navigateur accepte le
# login (200 OK) mais rejette silencieusement le cookie, donc /me échoue
# ensuite. Dérivé de APP_BASE_URL : redevient True automatiquement dès que
# l'app tourne en HTTPS (domaine + Let's Encrypt), sans y retoucher.
_COOKIE_SECURE = settings.APP_BASE_URL.strip().lower().startswith("https://")


class LoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginRequest(BaseModel):
    # Conservé "secret" pour rétrocompatibilité du contrat API frontend —
    # accepte en réalité un mot de passe de compte utilisateur réel
    # (root cause de l'ancien design : secret d'env comparé directement,
    # remplacé depuis la migration 010 par une vraie vérification bcrypt
    # contre la table `users`).
    email: str = ""
    secret: str


async def _get_user_by_email(email: str) -> dict | None:
    async with get_db() as db:
        result = await db.execute(
            text("SELECT id, email, password_hash, display_name, theme, role FROM users WHERE email = :email"),
            {"email": email.strip().lower()},
        )
        row = result.mappings().first()
        return dict(row) if row else None


def _set_session_cookie(resp: Response, cookie_name: str, user_id: str, role: str):
    token = create_session_token(str(user_id), role, expires_in=COOKIE_MAX_AGE)
    resp.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
        path="/",
        max_age=COOKIE_MAX_AGE,
    )


# ── Editorial login ───────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, response: Response):
    user = await _get_user_by_email(body.email)
    # .strip() sur le mot de passe : un espace ajouté par un clavier
    # mobile/auto-remplissage est invisible dans un champ masqué et faisait
    # échouer une comparaison stricte dans l'ancien système — conservé ici.
    if not user or not verify_password(body.password.strip(), user["password_hash"]):
        return JSONResponse({"detail": "Identifiants incorrects"}, status_code=401)

    resp = JSONResponse({"ok": True})
    _set_session_cookie(resp, SESSION_COOKIE, user["id"], user["role"])
    return resp


@router.delete("/login")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# ── Admin login ───────────────────────────────────────────────────────────────

@router.post("/admin")
async def admin_login(body: AdminLoginRequest, request: Request):
    # L'ancien formulaire /system/login n'envoie qu'un "secret", pas d'email
    # — un seul compte admin existe à ce jour (migration 010), donc on
    # retombe sur ADMIN_EMAIL pour identifier CE compte si aucun email
    # n'est fourni, plutôt que de casser le formulaire existant.
    email = body.email or settings.ADMIN_EMAIL
    user = await _get_user_by_email(email)
    if not user or user["role"] != "admin" or not verify_password(body.secret.strip(), user["password_hash"]):
        return JSONResponse({"error": "Accès refusé"}, status_code=401)

    resp = JSONResponse({"ok": True})
    _set_session_cookie(resp, ADMIN_COOKIE, user["id"], user["role"])
    return resp


@router.delete("/admin")
async def admin_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(ADMIN_COOKIE, path="/")
    return resp


# ── Session check ─────────────────────────────────────────────────────────────

@router.get("/me")
async def me(request: Request):
    session = request.cookies.get(SESSION_COOKIE)
    admin   = request.cookies.get(ADMIN_COOKIE)

    payload = verify_session_token(session) if session else None
    admin_payload = verify_session_token(admin) if admin else None

    if payload:
        role = "admin" if admin_payload else payload.get("role", "editor")
        return {"authenticated": True, "role": role, "user_id": payload.get("sub")}
    return JSONResponse({"authenticated": False}, status_code=401)
