"""
Routes FastAPI — Agent KORA
POST /api/agent/run           → Lance un cycle
GET  /api/agent/status        → État du cycle en cours
GET  /api/agent/stream        → SSE : historique DB + logs temps réel
POST /api/agent/resume/{id}   → Reprend après validation HITL
POST /api/agent/cancel/{id}   → Kill switch : annule le cycle en cours
"""
import uuid
import json
import asyncio
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from core.logger import logger

router = APIRouter()

# ── Store cycles en mémoire ───────────────────────────────────────────────────
# { cycle_id: { status, mode, published_count, errors } }
_cycles: dict = {}

# ── Tâches asyncio en cours, pour le kill switch ──────────────────────────────
# { cycle_id: asyncio.Task } — permet d'annuler réellement l'exécution en vol,
# pas seulement de marquer un statut en base pendant que le graphe continue.
_running_tasks: dict[str, asyncio.Task] = {}

# ── Queues de logs SSE par cycle (asyncio, pas de Redis requis) ───────────────
# { cycle_id: asyncio.Queue }  — créée au lancement, nettoyée après 5 min
_log_queues: dict[str, asyncio.Queue] = {}

_SENTINEL = object()  # signal de fin de stream


class RunRequest(BaseModel):
    mode: str = "semi"   # "auto" | "semi"
    # Généré côté client (crypto.randomUUID()) plutôt que côté serveur : le
    # frontend a besoin de connaître le cycle_id AVANT que /run ne réponde
    # (la réponse est désormais bloquante jusqu'à la pause HITL ou la fin du
    # cycle, potentiellement 1 à 3 minutes) pour pouvoir exposer un bouton
    # "Annuler" fonctionnel pendant l'attente, via un appel HTTP séparé à
    # /cancel/{cycle_id}. Repli sur un UUID serveur si absent (rétrocompat).
    cycle_id: Optional[str] = None


# ── POST /run ─────────────────────────────────────────────────────────────────
# Bloquant par conception : la réponse HTTP n'est renvoyée qu'une fois le
# graphe LangGraph arrivé à la pause HITL (mode semi) ou complètement terminé
# (mode auto), afin que le frontend puisse rediriger instantanément vers
# l'article prêt dès réception de la réponse, sans polling intermédiaire.
# Le graphe tourne malgré tout dans une Task asyncio distincte (pas inline)
# pour deux raisons : (1) elle reste annulable via /cancel/{cycle_id} pendant
# l'attente, (2) si le client se déconnecte (coupure réseau, onglet fermé,
# timeout proxy) avant la fin, le cycle continue et reste normalement
# consultable via GET /status — aucune perte de travail contrairement à une
# exécution strictement inline dans le handler de requête.

@router.post("/run")
async def run_cycle(body: RunRequest):
    if body.mode not in ("auto", "semi"):
        raise HTTPException(status_code=400, detail="mode must be 'auto' or 'semi'")

    cycle_id = body.cycle_id or str(uuid.uuid4())

    # Enregistre le cycle en base
    await _persist_cycle(cycle_id, body.mode)

    initial_state = {
        "mode": body.mode,
        "cycle_id": cycle_id,
        "raw_sources": [],
        "selected_articles": [],
        "current_article": None,
        "generated_article": None,
        "image_url": None,
        "wp_media_id": None,
        "wp_post_id": None,
        "published_count": 0,
        "errors": [],
        "hitl_approved": False,
        "article_index": 0,
    }

    _cycles[cycle_id] = {
        "status": "RUNNING",
        "mode": body.mode,
        "published_count": 0,
        "errors": [],
    }

    config = {"configurable": {"thread_id": cycle_id}}

    async def _run():
        from agent.graph import kora_graph_semi, kora_graph_auto
        kora_graph = kora_graph_semi if body.mode == "semi" else kora_graph_auto
        # Chronométrage réel du cycle — scraping (API Tavily), sélection/
        # rédaction (LLM) et génération d'image (Fal.ai) sont des appels
        # réseau/inférence externes de plusieurs secondes chacun, pas des
        # inefficacités du code : ce log donne une mesure honnête plutôt
        # qu'une estimation, pour piloter de vraies décisions d'optimisation
        # au lieu d'un objectif de latence irréaliste.
        t0 = time.perf_counter()
        try:
            _emit_log(cycle_id, "INFO", f"Cycle {body.mode.upper()} démarré")
            result = await kora_graph.ainvoke(initial_state, config=config)
            elapsed = time.perf_counter() - t0
            _cycles[cycle_id]["elapsed_seconds"] = round(elapsed, 1)
            logger.info("cycle_timing", cycle_id=cycle_id, mode=body.mode, elapsed_seconds=round(elapsed, 1))

            if body.mode == "semi":
                # Root cause du bug "Article prêt mais introuvable" : mode
                # "semi" ne veut PAS dire "le graphe s'est interrompu". Si la
                # sélection ne retient aucun article (0 candidat pertinent)
                # ou si la rédaction échoue pour TOUS les articles
                # sélectionnés, le graphe route directement vers
                # send_report → END (cf. graph.py: _route_after_select,
                # _check_next) — interrupt_before=["publish_wordpress"] n'est
                # alors jamais atteint, ainvoke() revient normalement avec
                # generated_article=None. L'ancien code marquait quand même
                # le cycle PAUSED dans ce cas (confondant "mode semi" et
                # "graphe interrompu"), d'où un article_id structurellement
                # absent — pas un incident réseau/timeout comme le rapport le
                # supposait. Vérification fiable : interroger l'état réel du
                # graphe via aget_state().next, qui n'est non-vide QUE si
                # LangGraph a effectivement suspendu l'exécution avant un
                # nœud (ici publish_wordpress).
                snapshot = await kora_graph.aget_state(config)
                really_interrupted = bool(snapshot.next)

                if really_interrupted:
                    _cycles[cycle_id]["status"] = "PAUSED"
                    # article_id nécessaire au frontend pour rediriger
                    # directement vers /articles/{id} dès la réponse de
                    # /run — sans lui, la redirection instantanée demandée
                    # n'a pas de cible.
                    _cycles[cycle_id]["article_id"] = ((result or {}).get("generated_article") or {}).get("db_id")
                    _emit_log(cycle_id, "HITL", "Article prêt — en attente de validation humaine")
                    await _update_cycle_status(cycle_id, "PAUSED")
                else:
                    # Le graphe a réellement terminé (END) sans jamais
                    # produire d'article à valider — cycle honnêtement vide,
                    # pas une pause fantôme.
                    _cycles[cycle_id]["status"] = "COMPLETED"
                    _cycles[cycle_id]["article_id"] = None
                    _emit_log(cycle_id, "WARN", "Cycle terminé sans article produit (0 candidat retenu ou échec de rédaction)")
                    await _update_cycle_status(cycle_id, "COMPLETED")
                    _close_stream(cycle_id)
            else:
                _cycles[cycle_id]["status"] = "COMPLETED"
                _emit_log(cycle_id, "OK", "Cycle autonome complété")
                await _update_cycle_status(cycle_id, "COMPLETED")
                _close_stream(cycle_id)

            if result:
                _cycles[cycle_id]["published_count"] = result.get("published_count", 0)
                _cycles[cycle_id]["errors"] = result.get("errors", [])

        except asyncio.CancelledError:
            # Kill switch déclenché — noter le statut avant de laisser
            # l'annulation se propager normalement.
            _cycles[cycle_id]["status"] = "CANCELLED"
            _emit_log(cycle_id, "WARN", "Cycle annulé par l'utilisateur")
            await _update_cycle_status(cycle_id, "CANCELLED")
            _close_stream(cycle_id)
            raise

        except Exception as e:
            _cycles[cycle_id]["status"] = "FAILED"
            _cycles[cycle_id]["errors"].append(str(e))
            _emit_log(cycle_id, "ERROR", f"Cycle échoué : {e}")
            logger.error("cycle_run_failed", cycle_id=cycle_id, error=str(e))
            await _update_cycle_status(cycle_id, "FAILED")
            _close_stream(cycle_id)

        finally:
            _running_tasks.pop(cycle_id, None)

    _log_queues[cycle_id] = asyncio.Queue()
    task = asyncio.create_task(_run())
    _running_tasks[cycle_id] = task
    asyncio.create_task(_cleanup_queue(cycle_id, delay=300))
    logger.info("cycle_started", cycle_id=cycle_id, mode=body.mode)

    try:
        await task
    except asyncio.CancelledError:
        # _run() a déjà marqué le statut CANCELLED et propagé l'annulation
        # pour respecter la sémantique asyncio — on l'intercepte ici pour
        # renvoyer une réponse HTTP propre plutôt qu'une erreur 500, sans
        # annuler à son tour la requête /run elle-même (pas de re-raise).
        pass

    final = _cycles.get(cycle_id, {})
    status = final.get("status")

    if status == "PAUSED":
        return {
            "cycle_id": cycle_id,
            "status": "PAUSED",
            "mode": body.mode,
            "article_id": final.get("article_id"),
            "elapsed_seconds": final.get("elapsed_seconds"),
            "message": "Article prêt pour validation" if final.get("article_id") else "Cycle en pause, article introuvable automatiquement",
        }
    if status == "COMPLETED":
        return {
            "cycle_id": cycle_id,
            "status": "COMPLETED",
            "mode": body.mode,
            "published_count": final.get("published_count", 0),
            "elapsed_seconds": final.get("elapsed_seconds"),
        }
    if status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Cycle annulé")

    raise HTTPException(
        status_code=500,
        detail="; ".join(final.get("errors", [])) or "Échec du cycle",
    )


# ── GET /status ───────────────────────────────────────────────────────────────

def _normalize_db_cycle(row: dict) -> dict:
    """
    Le registre en mémoire (_cycles) et la table 'cycles' n'ont pas le même
    nom de clé pour l'identifiant (cycle_id vs id) ni les mêmes champs
    (published_count vs articles_published) — normalise pour que le frontend
    puisse traiter les deux chemins de réponse de façon uniforme.
    """
    return {
        "cycle_id": row.get("id"),
        "status": row.get("status"),
        "mode": row.get("mode"),
        "published_count": row.get("articles_published", 0),
        "errors": [],
        "articles_collected": row.get("articles_collected"),
        "articles_selected": row.get("articles_selected"),
        "articles_published": row.get("articles_published"),
        "articles_rejected": row.get("articles_rejected"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
    }


@router.get("/status")
async def get_status(cycle_id: Optional[str] = None):
    if cycle_id:
        cycle = _cycles.get(cycle_id)
        if not cycle:
            # Cherche en base
            db_cycle = await _get_cycle_from_db(cycle_id)
            if not db_cycle:
                raise HTTPException(status_code=404, detail="Cycle non trouvé")
            normalized = _normalize_db_cycle(db_cycle)
            # Un cycle PAUSED en base dont l'article a été résolu directement
            # via la page Articles (approuvé/rejeté/supprimé) reste PAUSED en
            # base pour toujours — sans ce garde-fou, le frontend (qui interroge
            # /status avec ce cycle_id précis, stocké en localStorage) affichait
            # indéfiniment "article en attente" pour un article qui n'existe
            # déjà plus. On force ici le statut vers COMPLETED pour signaler
            # au frontend qu'il n'y a plus rien à valider sur ce cycle.
            if normalized["status"] == "PAUSED" and not await _has_pending_article(cycle_id):
                normalized["status"] = "COMPLETED"
            return normalized
        return {"cycle_id": cycle_id, **cycle}

    if not _cycles:
        # Le registre en mémoire est vide (ex. redémarrage du backend) — la
        # reprise de session côté frontend a besoin de retrouver un cycle
        # RUNNING/PAUSED réel plutôt qu'un faux "IDLE" si la DB en a un.
        db_active = await _get_active_cycle_from_db()
        if db_active:
            return _normalize_db_cycle(db_active)
        return {"status": "IDLE", "active_cycles": 0, "message": "Aucun cycle en cours"}

    # Retourne le dernier cycle
    latest_id, latest = list(_cycles.items())[-1]
    running = sum(1 for c in _cycles.values() if c["status"] == "RUNNING")
    return {
        "cycle_id": latest_id,
        **latest,
        "active_cycles": running,
        "total_cycles": len(_cycles),
    }


# ── GET /stream (SSE) ─────────────────────────────────────────────────────────

@router.get("/stream")
async def stream_logs(cycle_id: Optional[str] = None):
    """
    SSE : rejoue d'abord l'historique récent persisté en base pour ce cycle
    (utile après un rafraîchissement de page ou une reconnexion), puis
    bascule sur le flux temps réel via asyncio Queue.
    """

    async def event_generator():
        queue = _log_queues.get(cycle_id) if cycle_id else None

        yield _sse_event({"event": "connected", "cycle_id": cycle_id})

        if cycle_id:
            history = await _get_cycle_logs_history(cycle_id)
            for entry in history:
                yield _sse_event({**entry, "replay": True})
            if history:
                yield _sse_event({"event": "history_end"})

        heartbeat_counter = 0
        while True:
            if queue is not None:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                    if msg is _SENTINEL:
                        yield _sse_event({"event": "done"})
                        break
                    yield _sse_event(msg)
                    continue
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(5)

            # Heartbeat toutes les 5s pour garder la connexion HTTP
            heartbeat_counter += 1
            yield _sse_event({"event": "heartbeat", "tick": heartbeat_counter})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── POST /resume/{cycle_id} ───────────────────────────────────────────────────

@router.post("/resume/{cycle_id}")
async def resume_cycle(cycle_id: str):
    """
    Reprend un cycle en pause après validation HITL.
    LangGraph reprend depuis le checkpoint MemorySaver.
    """
    cycle = _cycles.get(cycle_id)
    if not cycle:
        # Le registre en mémoire (_cycles) ET le checkpoint LangGraph
        # (MemorySaver, également en mémoire) sont perdus à chaque redémarrage
        # du backend. Si le cycle existe en base avec un statut PAUSED, c'est
        # exactement ce cas — un simple 404 générique laissait croire à un
        # bug de transmission d'ID, alors que la session HITL est simplement
        # irrécupérable après redémarrage. Message explicite pour orienter
        # vers la vraie solution (Articles → approuver/rejeter directement).
        db_cycle = await _get_cycle_from_db(cycle_id)
        if db_cycle and db_cycle.get("status") == "PAUSED" and await _has_pending_article(cycle_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ce cycle était en pause mais sa session a été perdue "
                    "(le backend a redémarré depuis sa mise en pause — le "
                    "checkpoint LangGraph est en mémoire, pas persistant). "
                    "Utilise la page Articles pour approuver ou rejeter "
                    "directement l'article en attente."
                ),
            )
        raise HTTPException(status_code=404, detail="Cycle non trouvé (ou déjà résolu — plus rien en attente)")
    if cycle.get("status") not in ("PAUSED",):
        raise HTTPException(
            status_code=400,
            detail=f"Cycle ne peut pas être repris (status: {cycle.get('status')})"
        )

    config = {"configurable": {"thread_id": cycle_id}}
    _cycles[cycle_id]["status"] = "RUNNING"

    async def _resume():
        from agent.graph import kora_graph_semi as kora_graph
        try:
            _emit_log(cycle_id, "HITL", "Validation humaine accordée — reprise de la publication")
            # Injecter l'approbation dans l'état via update
            await kora_graph.aupdate_state(
                config,
                {"hitl_approved": True},
                as_node="generate_image",
            )
            result = await kora_graph.ainvoke(None, config=config)

            if result:
                # Vérifie s'il reste des articles
                idx = result.get("article_index", 0)
                selected = result.get("selected_articles", [])
                if idx < len(selected):
                    new_status = "PAUSED"
                    _cycles[cycle_id]["status"] = new_status
                    # Bug réel trouvé en testant end-to-end : published_count
                    # n'était mis à jour QUE dans la branche COMPLETED — un
                    # article publié avant la pause pour le suivant restait
                    # invisible dans /status (published_count figé à 0) alors
                    # qu'il était bien réellement publié sur WordPress.
                    _cycles[cycle_id]["published_count"] = result.get("published_count", 0)
                    _emit_log(cycle_id, "HITL", f"Article suivant en attente ({idx+1}/{len(selected)})")
                else:
                    new_status = "COMPLETED"
                    _cycles[cycle_id]["status"] = new_status
                    _cycles[cycle_id]["published_count"] = result.get("published_count", 0)
                    _emit_log(cycle_id, "OK", "Tous les articles traités")
                    _close_stream(cycle_id)

            await _update_cycle_status(cycle_id, _cycles[cycle_id]["status"])

        except asyncio.CancelledError:
            _cycles[cycle_id]["status"] = "CANCELLED"
            _emit_log(cycle_id, "WARN", "Cycle annulé par l'utilisateur")
            await _update_cycle_status(cycle_id, "CANCELLED")
            _close_stream(cycle_id)
            raise

        except Exception as e:
            _cycles[cycle_id]["status"] = "FAILED"
            _emit_log(cycle_id, "ERROR", f"Erreur après reprise : {e}")
            logger.error("cycle_resume_failed", cycle_id=cycle_id, error=str(e))
            await _update_cycle_status(cycle_id, "FAILED")
            _close_stream(cycle_id)

        finally:
            _running_tasks.pop(cycle_id, None)

    _running_tasks[cycle_id] = asyncio.create_task(_resume())
    return {
        "cycle_id": cycle_id,
        "status": "RUNNING",
        "message": "Cycle repris — publication en cours",
    }


# ── POST /cancel/{cycle_id} — Kill switch ────────────────────────────────────

@router.post("/cancel/{cycle_id}")
async def cancel_cycle(cycle_id: str):
    """
    Annule un cycle RUNNING ou PAUSED. Annule réellement la tâche asyncio en
    vol (pas seulement un flag en base) — le graphe s'arrête au prochain
    point d'await, remonte asyncio.CancelledError, gérée dans _run()/_resume()
    pour enregistrer le statut CANCELLED avant que la tâche ne se termine.
    """
    cycle = _cycles.get(cycle_id)
    if not cycle:
        db_cycle = await _get_cycle_from_db(cycle_id)
        if not db_cycle:
            raise HTTPException(status_code=404, detail="Cycle non trouvé")
        if db_cycle.get("status") not in ("RUNNING", "PAUSED"):
            raise HTTPException(status_code=400, detail=f"Cycle déjà terminé (status: {db_cycle.get('status')})")
        # Cycle connu en DB mais pas en mémoire (ex. redémarrage backend) —
        # pas de tâche asyncio à annuler, on ne peut que marquer le statut.
        await _update_cycle_status(cycle_id, "CANCELLED")
        return {"cycle_id": cycle_id, "status": "CANCELLED", "message": "Cycle marqué annulé (aucune tâche active trouvée)"}

    if cycle.get("status") not in ("RUNNING", "PAUSED"):
        raise HTTPException(status_code=400, detail=f"Cycle déjà terminé (status: {cycle.get('status')})")

    task = _running_tasks.get(cycle_id)
    if task and not task.done():
        task.cancel()
    else:
        # Pas de tâche en vol (ex. cycle PAUSED en attente HITL, sans coroutine
        # active) — marquer directement le statut.
        _cycles[cycle_id]["status"] = "CANCELLED"
        _emit_log(cycle_id, "WARN", "Cycle annulé par l'utilisateur")
        await _update_cycle_status(cycle_id, "CANCELLED")
        _close_stream(cycle_id)

    logger.info("cycle_cancelled", cycle_id=cycle_id)
    return {"cycle_id": cycle_id, "status": "CANCELLED", "message": "Cycle annulé"}


# ── POST /reject/{cycle_id} ───────────────────────────────────────────────────

@router.post("/reject/{cycle_id}")
async def reject_current_article(cycle_id: str):
    """Rejette l'article en attente et passe au suivant."""
    cycle = _cycles.get(cycle_id)
    if not cycle:
        db_cycle = await _get_cycle_from_db(cycle_id)
        if db_cycle and db_cycle.get("status") == "PAUSED" and await _has_pending_article(cycle_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ce cycle était en pause mais sa session a été perdue "
                    "(le backend a redémarré). Utilise la page Articles pour "
                    "rejeter directement l'article en attente."
                ),
            )
        raise HTTPException(status_code=404, detail="Cycle non trouvé (ou déjà résolu — plus rien en attente)")
    if cycle.get("status") != "PAUSED":
        raise HTTPException(status_code=400, detail="Cycle non en pause")

    config = {"configurable": {"thread_id": cycle_id}}
    from agent.graph import kora_graph_semi

    try:
        snapshot = await kora_graph_semi.aget_state(config)
        if snapshot and snapshot.values:
            article = snapshot.values.get("generated_article")
            db_id = (article or {}).get("db_id", "")
            if db_id and db_id != "unknown":
                from db.connection import get_db
                async with get_db() as db:
                    await db.execute(
                        text("UPDATE articles SET status='REJECTED' WHERE id=:id"),
                        {"id": db_id},
                    )
            # Avance l'index pour passer à l'article suivant
            idx = snapshot.values.get("article_index", 0)
            await kora_graph_semi.aupdate_state(
                config,
                {"article_index": idx + 1, "generated_article": None, "hitl_approved": False},
                as_node="generate_image",
            )
    except Exception as e:
        logger.warning("reject_state_update_failed", error=str(e))

    # Reprend automatiquement avec le prochain article
    return await resume_cycle(cycle_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _emit_log(cycle_id: str, level: str, event: str):
    """
    Publie un log dans la queue SSE du cycle, dans le logger structuré, et le
    persiste en base (fire-and-forget) pour survivre à un redémarrage backend
    et permettre le replay d'historique à la connexion SSE.
    """
    payload = {"cycle_id": cycle_id[:8], "level": level, "event": event}
    logger.info("cycle_event", cycle_id=cycle_id[:8], msg=event)
    queue = _log_queues.get(cycle_id)
    if queue is not None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass
    asyncio.create_task(_persist_log(cycle_id, level, event))


def _close_stream(cycle_id: str):
    """Ferme proprement la queue SSE d'un cycle (envoie le sentinel de fin)."""
    q = _log_queues.get(cycle_id)
    if q:
        try:
            q.put_nowait(_SENTINEL)
        except asyncio.QueueFull:
            pass


async def _persist_log(cycle_id: str, level: str, event: str):
    try:
        from db.connection import get_db
        async with get_db() as db:
            await db.execute(
                text("INSERT INTO cycle_logs (cycle_id, level, event) VALUES (:cid, :level, :event)"),
                {"cid": cycle_id, "level": level, "event": event},
            )
    except Exception as e:
        logger.warning("persist_log_failed", cycle_id=cycle_id, error=str(e))


async def _get_cycle_logs_history(cycle_id: str, limit: int = 200) -> list[dict]:
    """Logs persistés pour ce cycle — rejoués en tête de flux SSE."""
    try:
        from db.connection import get_db
        async with get_db() as db:
            result = await db.execute(
                text("""
                    SELECT level, event, created_at FROM cycle_logs
                    WHERE cycle_id = :cid ORDER BY created_at ASC LIMIT :limit
                """),
                {"cid": cycle_id, "limit": limit},
            )
            rows = result.mappings().all()
        return [
            {"cycle_id": cycle_id[:8], "level": r["level"], "event": r["event"]}
            for r in rows
        ]
    except Exception as e:
        logger.warning("cycle_logs_history_failed", cycle_id=cycle_id, error=str(e))
        return []


async def _get_active_cycle_from_db() -> Optional[dict]:
    """
    Dernier cycle RUNNING/PAUSED en base — reprise de session après redémarrage
    backend.

    Root cause du bug "carte HITL fantôme" : un cycle PAUSED reste PAUSED en
    base pour toujours si son article est résolu (approuvé/rejeté/supprimé)
    directement via la page Articles ou via le fallback article-level, car ces
    chemins ne touchent jamais `cycles.status`. Sans la vérification ci-dessous,
    ce cycle orphelin est resservi indéfiniment par /status et le frontend
    affiche "article en attente" alors qu'il n'en reste plus aucun.
    Un cycle PAUSED n'est donc considéré actif que s'il a encore un article
    PENDING_REVIEW réel ; un cycle RUNNING est toujours en cours de traitement
    donc pas concerné par cette vérification.
    """
    try:
        from db.connection import get_db
        async with get_db() as db:
            result = await db.execute(
                text("""
                    SELECT * FROM cycles c
                    WHERE status IN ('RUNNING','PAUSED')
                      AND (
                        status = 'RUNNING'
                        OR EXISTS (
                            SELECT 1 FROM articles a
                            WHERE a.cycle_id = c.id AND a.status = 'PENDING_REVIEW'
                        )
                      )
                    ORDER BY started_at DESC LIMIT 1
                """)
            )
            row = result.mappings().first()
            return dict(row) if row else None
    except Exception as e:
        logger.warning("active_cycle_lookup_failed", error=str(e))
        return None


async def _cleanup_queue(cycle_id: str, delay: int = 300):
    """Envoie le sentinel de fin puis supprime la queue après `delay` secondes."""
    await asyncio.sleep(delay)
    if cycle_id in _log_queues:
        _close_stream(cycle_id)
        await asyncio.sleep(30)
        _log_queues.pop(cycle_id, None)


async def _persist_cycle(cycle_id: str, mode: str):
    try:
        from db.connection import get_db
        async with get_db() as db:
            await db.execute(
                text("INSERT INTO cycles (id, mode, status) VALUES (:id, :mode, 'RUNNING')"),
                {"id": cycle_id, "mode": mode},
            )
    except Exception as e:
        logger.warning("persist_cycle_failed", error=str(e))


async def _update_cycle_status(cycle_id: str, status: str):
    try:
        from db.connection import get_db
        async with get_db() as db:
            await db.execute(
                text("UPDATE cycles SET status=:s, completed_at=now() WHERE id=:id"),
                {"s": status, "id": cycle_id},
            )
    except Exception as e:
        logger.warning("update_cycle_failed", error=str(e))


async def _get_cycle_from_db(cycle_id: str) -> Optional[dict]:
    try:
        from db.connection import get_db
        async with get_db() as db:
            result = await db.execute(
                text("SELECT * FROM cycles WHERE id=:id"), {"id": cycle_id}
            )
            row = result.mappings().first()
            return dict(row) if row else None
    except Exception:
        return None


async def _has_pending_article(cycle_id: str) -> bool:
    """Existe-t-il encore un article PENDING_REVIEW réel pour ce cycle ?"""
    try:
        from db.connection import get_db
        async with get_db() as db:
            result = await db.execute(
                text("SELECT 1 FROM articles WHERE cycle_id=:cid AND status='PENDING_REVIEW' LIMIT 1"),
                {"cid": cycle_id},
            )
            return result.first() is not None
    except Exception as e:
        logger.warning("pending_article_check_failed", cycle_id=cycle_id, error=str(e))
        return True  # sûr par défaut : ne pas masquer un vrai cycle en attente sur panne DB
