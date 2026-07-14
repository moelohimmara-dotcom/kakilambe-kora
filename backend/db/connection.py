from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
import ssl
import uuid

from core.config import settings

# Convert postgres:// → postgresql+asyncpg://
_url = settings.DATABASE_URL
if _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql+asyncpg://", 1)

# Strip sslmode param (psycopg2 syntax, not supported by asyncpg)
if _url and "sslmode=" in _url:
    import re
    _url = re.sub(r"[?&]sslmode=[^&]*", "", _url).rstrip("?")

# SSL context for Supabase (requires SSL)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# Lazy init — ne pas crasher si DATABASE_URL est vide au démarrage
#
# Incident résiduel (2026-07-14, après le premier correctif statement_cache_size
# + nom UUID) : InvalidSQLStatementNameError persistait encore sur certaines
# requêtes de premier plan (GET /api/articles), pas seulement en tâche de
# fond. Cause : le POOL DE CONNEXIONS de SQLAlchemy (pool_size=5) réutilise
# les mêmes objets de connexion asyncpg côté client À TRAVERS PLUSIEURS
# requêtes HTTP successives — mais PgBouncer (mode transaction) peut faire
# correspondre cet objet réutilisé à une connexion PHYSIQUE Postgres
# différente à chaque nouvelle transaction. Même avec un nom de prepared
# statement unique par appel, la combinaison pooling client + pooling
# PgBouncer côté serveur reste fragile.
#
# Correctif définitif documenté pour asyncpg+SQLAlchemy+PgBouncer en mode
# transaction : NullPool — désactive le pooling côté client, une connexion
# TCP/TLS fraîche est ouverte pour chaque emprunt puis fermée. C'est
# exactement l'architecture que PgBouncer est conçu pour absorber
# (multiplexage de nombreuses connexions client courtes sur peu de connexions
# serveur) — laisser SQLAlchemy pooler par-dessus était redondant et source
# de ce bug. Léger coût : une négociation TCP/TLS à chaque requête plutôt
# qu'une connexion réutilisée, acceptable pour le volume de cette
# application (usage mono-utilisateur).
engine = create_async_engine(
    _url or "postgresql+asyncpg://localhost/placeholder",
    poolclass=NullPool,
    echo=settings.DEBUG,
    connect_args={
        "ssl": _ssl_ctx,
        "statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
    },
) if _url else None

AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
) if engine else None


@asynccontextmanager
async def get_db():
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL non configurée — base de données indisponible")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
