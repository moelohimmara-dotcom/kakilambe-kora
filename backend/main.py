from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from core.config import settings
from api.agent_routes import router as agent_router
from api.chat_routes import router as chat_router
from api.article_routes import router as article_router
from api.provider_routes import router as provider_router
from api.settings_routes import router as settings_router

app = FastAPI(
    title="KORA API",
    description="GuinéePress Intelligence — Backend KORA",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
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
    """Test database connectivity — returns real error if any."""
    try:
        from db.connection import get_db
        async with get_db() as db:
            await db.execute("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from core.logger import logger
    logger.error("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(status_code=500, content={"detail": str(exc)})
