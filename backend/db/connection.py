from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from core.config import settings

# Convert postgres:// → postgresql+asyncpg://
_url = settings.DATABASE_URL
if _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql+asyncpg://", 1)

# Lazy init — ne pas crasher si DATABASE_URL est vide au démarrage
engine = create_async_engine(
    _url or "postgresql+asyncpg://localhost/placeholder",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=settings.DEBUG,
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
