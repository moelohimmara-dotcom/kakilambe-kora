from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
import ssl

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
engine = create_async_engine(
    _url or "postgresql+asyncpg://localhost/placeholder",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args={"ssl": _ssl_ctx},
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
