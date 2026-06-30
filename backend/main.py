from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time

from core.config import settings

# Filtre uvicorn : supprime le bruit des sondes non authentifiées sur /api/auth/me
class _AuthMeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ("GET /api/auth/me" in msg and "401" in msg)

logging.getLogger("uvicorn.access").addFilter(_AuthMeFilter())
from core.scheduler import start_scheduler, scheduler
from api.agent_routes import router as agent_router
from api.auth_routes import router as auth_router
from api.chat_routes import router as chat_router
from api.article_routes import router as article_router
from api.provider_routes import router as provider_router
from api.settings_routes import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="KORA API",
    description="GuinéePress Intelligence — Backend KORA",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(round(time.time() - start, 4))
    return response

app.include_router(auth_router,     prefix="/api/auth",     tags=["auth"])
app.include_router(agent_router,    prefix="/api/agent",    tags=["agent"])
app.include_router(chat_router,     prefix="/api/chat",     tags=["chat"])
app.include_router(article_router,  prefix="/api/articles", tags=["articles"])
app.include_router(provider_router, prefix="/api/providers",tags=["providers"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "kora-api", "version": "1.0.0"}

@app.get("/health/db", tags=["system"])
async def health_db():
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/health/database", tags=["system"])
async def health_database():
    return await health_db()

@app.get("/health/redis", tags=["system"])
async def health_redis():
    try:
        import redis.asyncio as aioredis
        url = settings.REDIS_URL
        if not url:
            return {"status": "error", "detail": "REDIS_URL not configured"}
        r = aioredis.from_url(url, socket_timeout=3)
        await r.ping()
        await r.aclose()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/health/wordpress", tags=["system"])
async def health_wordpress():
    try:
        import httpx, base64
        token = base64.b64encode(f"{settings.WP_USERNAME}:{settings.WP_APP_PASSWORD}".encode()).decode()
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{settings.WP_BASE_URL}/wp-json/wp/v2/posts?per_page=1",
                                 headers={"Authorization": f"Basic {token}"})
        if r.status_code < 400:
            return {"status": "ok"}
        return {"status": "error", "detail": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/health/providers/{provider}", tags=["system"])
async def health_provider(provider: str):
    keys = {
        "groq": settings.GROQ_API_KEY,
        "gemini": settings.GEMINI_API_KEY,
        "cerebras": settings.CEREBRAS_API_KEY,
        "openrouter": settings.OPENROUTER_API_KEY,
    }
    key = keys.get(provider.lower(), "")
    if not key:
        return {"status": "error", "detail": f"{provider} API key not configured"}
    return {"status": "ok", "provider": provider}

@app.get("/health/tavily", tags=["system"])
async def health_tavily():
    if not settings.TAVILY_API_KEY:
        return {"status": "error", "detail": "TAVILY_API_KEY not configured"}
    try:
        from integrations.tavily_client import tavily_client
        results = await tavily_client.search("Guinée Conakry actualité", max_results=2)
        return {"status": "ok", "detail": f"Tavily live: {len(results)} results"}
    except Exception as e:
        return {"status": "error", "detail": f"Tavily failed: {e}"}

@app.get("/health/fal", tags=["system"])
async def health_fal():
    if not settings.IMAGE_GEN_API_KEY:
        return {"status": "error", "detail": "IMAGE_GEN_API_KEY not configured"}
    return {"status": "ok", "detail": "fal.ai key present"}
