from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
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
# statement_cache_size=0 : le pooler Supabase (port 6543) tourne PgBouncer en
# mode transaction — les connexions physiques sont recyclées entre requêtes
# HTTP, donc les prepared statements qu'asyncpg met en cache côté client
# pointent vers des statements qui n'existent plus sur la connexion physique
# recyclée (asyncpg.exceptions.InvalidSQLStatementNameError: prepared
# statement "__asyncpg_stmt_fe__" does not exist).
#
# statement_cache_size=0 seul ne suffit pas : asyncpg nomme alors ses PREPARE
# via un compteur (__asyncpg_stmt_N__) qui peut entrer en collision avec un
# nom déjà préparé par UNE AUTRE session logique sur la même connexion
# physique recyclée par PgBouncer (DuplicatePreparedStatementError). Un nom
# généré par UUID à chaque appel élimine toute collision entre sessions.
engine = create_async_engine(
    _url or "postgresql+asyncpg://localhost/placeholder",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
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
