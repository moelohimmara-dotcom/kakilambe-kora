"""
Diffusion en direct (pub/sub en mémoire) de TOUS les logs structurés du
système vers d'éventuels abonnés SSE — cf. GET /stream/logs (main.py).

Root cause du manque (audit 2026-07-15) : /api/agent/stream existait déjà
(core/cycle_events.py) mais est scoped à un seul cycle_id — un flux global
tous-événements-confondus (veille, cycles, scraping, LLM, publication)
n'existait nulle part. Plutôt que de dupliquer la file d'attente par
cycle_id, ce module s'accroche directement à core/logger.py (StructuredLogger
._emit) : CHAQUE appel logger.info/warning/error/debug de tout le backend
passe automatiquement par ici, sans qu'aucun module appelant n'ait besoin
de le savoir ou d'être modifié.
"""
import asyncio
from typing import List

_subscribers: List[asyncio.Queue] = []
_QUEUE_MAXSIZE = 500


def broadcast(record: dict) -> None:
    """
    Appelé de façon synchrone depuis core/logger.py à chaque log — ne doit
    JAMAIS bloquer ni lever d'exception (un abonné lent ou déconnecté ne
    doit jamais impacter le reste du système). File bornée : un abonné qui
    ne consomme pas assez vite perd les plus anciennes lignes plutôt que de
    faire grossir la mémoire indéfiniment.
    """
    for q in list(_subscribers):
        try:
            if q.full():
                q.get_nowait()
            q.put_nowait(record)
        except Exception:
            pass


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)


def subscriber_count() -> int:
    return len(_subscribers)
