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
from api.account_routes import router as account_router
from api.article_routes import router as article_router
from api.cycle_routes import router as cycle_router
from api.provider_routes import router as provider_router
from api.settings_routes import router as settings_router
from api.webhook_routes import router as webhook_router
from api.pool_routes import router as pool_router
from api.integrations_routes import router as integrations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.llm_router import llm_router
    await llm_router.load_from_db()
    await start_scheduler()
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
app.include_router(account_router,  prefix="/api/account",  tags=["account"])
app.include_router(agent_router,    prefix="/api/agent",    tags=["agent"])
app.include_router(article_router,  prefix="/api/articles", tags=["articles"])
app.include_router(cycle_router,    prefix="/api/cycles",   tags=["cycles"])
app.include_router(provider_router, prefix="/api/providers",tags=["providers"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(webhook_router,  prefix="/api/webhooks", tags=["webhooks"])
app.include_router(pool_router,     prefix="/api/pool",     tags=["pool"])
app.include_router(integrations_router, prefix="/api/integrations", tags=["integrations"])

@app.get("/health", tags=["system"])
async def health():
    """
    Health check agrégé — le frontend attend {"status", "services": {db, wordpress, ...}}.
    """
    services: dict = {}

    # DB
    try:
        from db.connection import get_db
        from sqlalchemy import text as _text
        async with get_db() as _db:
            await _db.execute(_text("SELECT 1"))
        services["db"] = "ok"
    except Exception:
        services["db"] = "error"

    # WordPress
    try:
        import httpx as _httpx, base64 as _b64
        _tok = _b64.b64encode(f"{settings.WP_USERNAME}:{settings.WP_APP_PASSWORD}".encode()).decode()
        async with _httpx.AsyncClient(timeout=5) as _c:
            _r = await _c.get(
                f"{settings.WP_BASE_URL}/wp-json/wp/v2/posts?per_page=1",
                headers={"Authorization": f"Basic {_tok}"},
            )
        services["wordpress"] = "ok" if _r.status_code < 400 else "error"
    except Exception:
        services["wordpress"] = "error"

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return {"status": overall, "service": "kora-api", "version": "1.0.0", "services": services}

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
    """
    Root cause corrigée (audit 2026-07-15) : cette route renvoyait "ok" en
    dur sans la moindre connexion réelle, alors que Redis a été retiré de
    l'architecture (remplacé par Supabase provider_states, cf. commentaire
    migration 001). Le badge "Redis: OK" affiché sur /system dashboard
    était donc un mensonge fidèlement relayé par le frontend. Renvoie
    désormais "not_used" — statut honnête distinct de "ok"/"error", que le
    frontend affiche en gris neutre plutôt qu'en vert trompeur.
    """
    return {"status": "not_used", "detail": "Redis n'est pas utilisé dans cette architecture (remplacé par Supabase provider_states)"}


@app.get("/stream/logs", tags=["system"])
async def stream_logs():
    """
    Flux SSE global — TOUS les logs structurés du backend (veille passive,
    cycles, scraping, fournisseurs LLM avec bascules de fallback,
    publication WordPress), diffusés en temps réel dès qu'ils sont émis via
    core/logger.py (cf. core/log_stream.py). Contrairement à
    /api/agent/stream (core/cycle_events.py), scoped à un cycle_id unique,
    ce flux est global et ne nécessite aucun paramètre.
    """
    from fastapi.responses import StreamingResponse
    from core.log_stream import subscribe, unsubscribe
    import json as _json
    import asyncio as _asyncio

    async def event_generator():
        queue = subscribe()
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    record = await _asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {_json.dumps(record, ensure_ascii=False, default=str)}\n\n"
                except _asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

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

@app.get("/health/image_gen", tags=["system"])
async def health_image_gen():
    """Pollinations.ai — gratuit, sans clé API requise."""
    return {"status": "ok", "detail": "pollinations.ai (no API key required)"}

@app.get("/health/qstash", tags=["system"])
async def health_qstash():
    from integrations.qstash_client import qstash_client
    if not qstash_client.configured:
        return {"status": "error", "detail": "QSTASH_TOKEN not configured"}
    if not settings.QSTASH_CURRENT_SIGNING_KEY:
        return {"status": "error", "detail": "QSTASH_CURRENT_SIGNING_KEY not configured"}
    return {"status": "ok", "detail": "QStash token and signing key present"}
