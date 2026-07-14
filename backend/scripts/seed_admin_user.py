"""
Seed ponctuel : migre le compte unique actuel (ADMIN_EMAIL / ADMIN_SECRET_KEY,
jusqu'ici comparés en clair contre des variables d'environnement) vers un
vrai enregistrement dans la table `users`, mot de passe hashé via bcrypt.

Idempotent : si un utilisateur avec cet email existe déjà, ne fait rien.
Ne journalise et n'affiche jamais le mot de passe en clair.
"""
import asyncio
import bcrypt

from core.config import settings
from db.connection import get_db
from sqlalchemy import text


async def main():
    if not settings.ADMIN_SECRET_KEY:
        print("ADMIN_SECRET_KEY non configuré — rien à seeder.")
        return

    email = settings.ADMIN_EMAIL.strip().lower()
    password_hash = bcrypt.hashpw(
        settings.ADMIN_SECRET_KEY.strip().encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    async with get_db() as db:
        existing = await db.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": email}
        )
        if existing.mappings().first():
            print(f"Utilisateur {email} existe déjà — aucune action.")
            return

        await db.execute(
            text("""
                INSERT INTO users (email, password_hash, display_name, role)
                VALUES (:email, :password_hash, :display_name, 'admin')
            """),
            {"email": email, "password_hash": password_hash, "display_name": "Éditeur"},
        )
    print(f"Utilisateur {email} créé (role=admin).")


if __name__ == "__main__":
    asyncio.run(main())
