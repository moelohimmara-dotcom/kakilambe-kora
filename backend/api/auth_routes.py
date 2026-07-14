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

from core.config import settings

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
    secret: str


# ── Editorial login ───────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, response: Response):
    admin_email = getattr(settings, "ADMIN_EMAIL", "mistermarcket@gmail.com")
    expected_key = settings.ADMIN_SECRET_KEY

    if not expected_key:
        return JSONResponse({"detail": "Auth not configured"}, status_code=500)

    email_ok = body.email.strip().lower() == admin_email.strip().lower()
    # .strip() sur le mot de passe : même correctif que la route Next.js
    # équivalente (frontend/app/api/auth/login/route.ts) — un espace ajouté
    # par un clavier mobile/auto-remplissage est invisible dans un champ
    # masqué et faisait échouer une comparaison stricte.
    pass_ok  = body.password.strip() == expected_key.strip()

    if not email_ok or not pass_ok:
        return JSONResponse({"detail": "Identifiants incorrects"}, status_code=401)

    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=expected_key,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
        path="/",
        max_age=COOKIE_MAX_AGE,
    )
    return resp


@router.delete("/login")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# ── Admin login ───────────────────────────────────────────────────────────────

@router.post("/admin")
async def admin_login(body: AdminLoginRequest):
    expected = settings.ADMIN_SECRET_KEY
    if not expected or body.secret.strip() != expected.strip():
        return JSONResponse({"error": "Accès refusé"}, status_code=401)

    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        key=ADMIN_COOKIE,
        value=expected,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
        path="/",
        max_age=COOKIE_MAX_AGE,
    )
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
    if session and len(session) >= 8:
        role = "admin" if admin else "editor"
        return {"authenticated": True, "role": role}
    return JSONResponse({"authenticated": False}, status_code=401)
