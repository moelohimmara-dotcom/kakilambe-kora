"""
Primitives de sécurité pour les comptes utilisateurs réels (migration
2026-07-14, cf. db/migrations/010_users_table.sql).

Root cause du besoin : l'ancien système comparait le cookie de session
directement à ADMIN_SECRET_KEY (une variable d'environnement statique) — un
changement de mot de passe en base n'aurait donc jamais pu être revalidé
nulle part (le middleware Next.js ne relit jamais la DB). Remplacé par un
jeton signé (HS256, format JWT standard) qui encode l'identité de
l'utilisateur — vérifiable par simple signature, sans appel DB, y compris
depuis l'Edge Runtime du middleware frontend (cf. frontend/middleware.ts).

Implémenté en stdlib pur (hmac/hashlib/base64/json) plutôt qu'avec PyJWT :
évite une dépendance supplémentaire pour un format de jeton volontairement
minimal (3 claims : sub, role, exp).
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Optional

import bcrypt

from core.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Hash malformé (ne devrait jamais arriver en usage normal) — jamais
        # lever d'exception sur une vérification de mot de passe, refuser.
        return False


def _jwt_secret() -> bytes:
    # Repli sur ADMIN_SECRET_KEY pour continuité si SESSION_JWT_SECRET n'est
    # pas encore configuré — utilisé ici UNIQUEMENT comme clé de signature
    # HMAC, jamais comme mot de passe comparé directement (c'était l'ancien
    # anti-pattern : ce fichier l'élimine, il ne le reproduit pas).
    secret = getattr(settings, "SESSION_JWT_SECRET", "") or settings.ADMIN_SECRET_KEY
    return secret.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_session_token(user_id: str, role: str, expires_in: int = 60 * 60 * 8) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "role": role, "exp": int(time.time()) + expires_in}

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    signature = hmac.new(_jwt_secret(), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_session_token(token: str) -> Optional[dict]:
    """Retourne le payload {sub, role, exp} si le jeton est valide et non expiré, sinon None."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        return None

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(_jwt_secret(), signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _b64url_decode(signature_b64)
    except Exception:
        return None

    if not hmac.compare_digest(expected_sig, actual_sig):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None

    if payload.get("exp", 0) < time.time():
        return None

    return payload
