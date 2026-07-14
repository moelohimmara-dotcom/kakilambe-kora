"""
Verrou anti-collision entre le job de veille planifié (toutes les 2h,
core/scheduler.py) et le scraping de secours déclenché par un cycle manuel
(agent/nodes/scraper.py) — les deux processus ne doivent JAMAIS scraper les
mêmes sources en même temps.

Root cause de ce choix d'implémentation (audit 2026-07-14) : le badge
"Redis: OK" affiché sur /system est un artefact — GET /health/redis
(backend/main.py) renvoie un "ok" en dur sans connexion réelle, Redis ayant
été explicitement retiré de l'architecture (cf. commentaire dans
db/migrations/001_init.sql) au profit de Supabase. Impossible donc de
réutiliser un vrai verrou distribué Redis. Le verrou anti-doublon de cycle
déjà construit (api/agent_routes.py, _find_running_cycle_id) tourne
lui-même en mémoire de PROCESSUS (un seul worker uvicorn) — ce module
applique exactement la même philosophie : un verrou en mémoire suffit ici
car le scheduler APScheduler et les requêtes FastAPI partagent le même
process Python, donc le même event loop asyncio.
"""
import asyncio
from typing import Optional

from core.logger import logger

_scrape_lock = asyncio.Lock()
_lock_holder: Optional[str] = None


async def acquire_scrape_lock(holder: str) -> None:
    """
    Bloque jusqu'à obtention du verrou — pas de contournement par timeout :
    un scraping dure ~15-30s, attendre est toujours préférable à laisser
    deux processus scraper la même source simultanément.
    """
    global _lock_holder
    if _scrape_lock.locked():
        logger.info("scrape_lock_contention", requested_by=holder, held_by=_lock_holder)
    await _scrape_lock.acquire()
    _lock_holder = holder
    logger.info("scrape_lock_acquired", holder=holder)


def release_scrape_lock() -> None:
    global _lock_holder
    holder = _lock_holder
    _lock_holder = None
    if _scrape_lock.locked():
        _scrape_lock.release()
    logger.info("scrape_lock_released", holder=holder)


def scrape_lock_status() -> dict:
    return {"locked": _scrape_lock.locked(), "holder": _lock_holder}
