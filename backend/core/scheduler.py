from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

from core.config import settings
from core.logger import logger

scheduler = AsyncIOScheduler()


async def _get_configured_mode() -> str:
    """
    Lit la préférence de publication en base pour décider si le cycle
    programmé publie de façon autonome ("auto") ou s'arrête pour validation
    humaine ("semi").

    Clé lue : `auto_publish_enabled` — c'est le SEUL réglage réellement
    écrit par le dashboard (toggle "Activer la publication automatique" de
    l'onglet WordPress). Le rapport d'audit proposait `semi_auto_mode`, mais
    cette clé n'a aucun contrôle dans l'UI : l'utilisateur ne peut jamais la
    changer, donc s'y fier reviendrait à ignorer son choix réel.

    Sécurité éditoriale : "semi" par défaut. Auto UNIQUEMENT si l'utilisateur
    l'a explicitement activé. Toute ambiguïté (clé absente, panne DB) →
    "semi", pour ne jamais publier à l'aveugle sur le site live.
    """
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            result = await db.execute(
                text("SELECT value FROM app_settings WHERE key = 'auto_publish_enabled'")
            )
            row = result.mappings().first()
        if row and row["value"] and str(row["value"]).strip().lower() == "true":
            return "auto"
    except Exception as e:
        logger.error("scheduler_mode_db_read_failed", error=str(e))
    return "semi"


async def _count_pending(cycle_id: str) -> int:
    """Articles produits par ce cycle en attente de validation (mode semi)."""
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            result = await db.execute(
                text("SELECT count(*) AS n FROM articles WHERE cycle_id = :cid AND status = 'PENDING_REVIEW'"),
                {"cid": cycle_id},
            )
            row = result.mappings().first()
        return int(row["n"]) if row else 0
    except Exception:
        return 0


async def _run_kora_cycle():
    from agent.graph import kora_graph_auto, kora_graph_semi
    from integrations.gmail_client import gmail_client
    import uuid

    cycle_id = str(uuid.uuid4())
    started_at = datetime.now(pytz.timezone(settings.CYCLE_TIMEZONE))

    # Décision dynamique — plus de mode "auto" codé en dur qui publiait sur
    # le site live quel que soit le réglage du dashboard.
    mode = await _get_configured_mode()
    kora_graph = kora_graph_auto if mode == "auto" else kora_graph_semi
    logger.info("scheduled_cycle_start", cycle_id=cycle_id, mode=mode)

    published = 0
    pending = 0
    errors = []

    try:
        config = {"configurable": {"thread_id": cycle_id}}
        result = await kora_graph.ainvoke(
            {"mode": mode, "cycle_id": cycle_id, "published_count": 0, "errors": [],
             "hitl_approved": False, "raw_sources": [], "selected_articles": [],
             "current_article": None, "generated_article": None,
             "image_url": None, "wp_media_id": None, "wp_post_id": None,
             "article_index": 0},
            config=config,
        )
        if result:
            published = result.get("published_count", 0)
            errors = result.get("errors", [])

        # En mode semi, le graphe s'interrompt avant publication : rien n'est
        # publié (published=0) mais des articles sont enregistrés en
        # PENDING_REVIEW — sans ce comptage, le rapport afficherait "0 article"
        # et ressemblerait à un cycle vide/échoué alors qu'il a bien travaillé.
        if mode == "semi":
            pending = await _count_pending(cycle_id)

        logger.info("scheduled_cycle_complete", cycle_id=cycle_id, mode=mode, published=published, pending=pending)
        await _send_report(gmail_client, cycle_id, started_at, published, errors, success=True, mode=mode, pending=pending)

    except Exception as e:
        errors.append(str(e))
        logger.error("scheduled_cycle_failed", cycle_id=cycle_id, error=str(e))
        await _send_report(gmail_client, cycle_id, started_at, published, errors, success=False, mode=mode, pending=pending)


async def _send_report(client, cycle_id, started_at, published, errors, success, mode="auto", pending=0):
    status_label = "✅ Succès" if success else "❌ Échec"
    color = "#22c55e" if success else "#ef4444"
    errors_html = "".join(f"<li style='color:#ef4444'>{e}</li>" for e in errors) or "<li>Aucune</li>"

    mode_label = "Semi-automatique (validation requise)" if mode == "semi" else "Automatique (publication directe)"

    # En semi, le chiffre qui compte est le nombre d'articles en attente de
    # validation ; en auto, c'est le nombre réellement publié.
    if mode == "semi":
        count_label = "Articles en attente de validation"
        count_value = pending
        count_color = "#f97316" if pending else "#6b7280"
    else:
        count_label = "Articles publiés"
        count_value = published
        count_color = color

    body = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <div style="background:#1a1a1a;padding:20px 24px;border-radius:8px 8px 0 0">
        <span style="color:#f97316;font-size:22px;font-weight:700">/KORA</span>
        <span style="color:#999;font-size:13px;margin-left:8px">GuinéePress Intelligence</span>
      </div>
      <div style="background:#ffffff;padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
        <h2 style="margin:0 0 16px;font-size:18px">Rapport de cycle — {status_label}</h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <tr><td style="padding:6px 0;color:#6b7280">Date</td>
              <td style="padding:6px 0;font-weight:600">{started_at.strftime('%d/%m/%Y %H:%M')} (Conakry)</td></tr>
          <tr><td style="padding:6px 0;color:#6b7280">Mode</td>
              <td style="padding:6px 0;font-weight:600">{mode_label}</td></tr>
          <tr><td style="padding:6px 0;color:#6b7280">Cycle ID</td>
              <td style="padding:6px 0;font-family:monospace;font-size:12px">{cycle_id[:8]}…</td></tr>
          <tr><td style="padding:6px 0;color:#6b7280">{count_label}</td>
              <td style="padding:6px 0;font-weight:700;font-size:20px;color:{count_color}">{count_value}</td></tr>
        </table>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0">
        <p style="margin:0 0 8px;color:#6b7280;font-size:13px">Erreurs :</p>
        <ul style="margin:0;padding-left:20px;font-size:13px">{errors_html}</ul>
        <div style="margin-top:20px">
          <a href="{settings.APP_BASE_URL}/dashboard"
             style="background:#f97316;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600">
            Ouvrir le tableau de bord →
          </a>
        </div>
      </div>
      <p style="text-align:center;color:#9ca3af;font-size:11px;margin-top:12px">kakilambe.com · KORA Phase 3</p>
    </div>
    """

    subject = f"[KORA] {status_label} — {count_value} {count_label.lower()} — {started_at.strftime('%d/%m/%Y')}"
    await client.send_report(subject=subject, body_html=body)


async def _get_configured_cycle_hour() -> int:
    """
    DB-first (app_settings.cycle_hour, modifiable depuis /settings) → variable
    d'environnement en repli. Même pattern que les identifiants WordPress
    (wordpress_client._get_credentials) — sans ça, le champ "Heure d'exécution
    du cycle" de l'UI n'aurait aucun effet réel sur la planification.
    """
    try:
        from db.connection import get_db
        from sqlalchemy import text
        async with get_db() as db:
            result = await db.execute(text("SELECT value FROM app_settings WHERE key = 'cycle_hour'"))
            row = result.mappings().first()
        if row and row["value"] is not None:
            return int(row["value"])
    except Exception as e:
        logger.warning("scheduler_cycle_hour_db_read_failed", error=str(e))
    return settings.CYCLE_HOUR


async def start_scheduler():
    tz = pytz.timezone(settings.CYCLE_TIMEZONE)
    hour = await _get_configured_cycle_hour()
    scheduler.add_job(
        _run_kora_cycle,
        CronTrigger(hour=hour, minute=0, timezone=tz),
        id="kora_daily_cycle",
        replace_existing=True,
        max_instances=1,
        # 5 minutes était trop court : un redémarrage du service (déploiement,
        # panne, mise à jour) tombant hors de cette fenêtre autour de l'heure
        # cible fait sauter silencieusement le cycle du jour entier — pas un
        # crash, juste une occasion manquée jusqu'au lendemain. Sur un VPS
        # auto-géré (redéploiements manuels fréquents), 1h de marge est plus
        # réaliste qu'un service managé qui ne redémarre presque jamais.
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        "scheduler_started",
        hour=hour,
        timezone=settings.CYCLE_TIMEZONE,
    )


def reschedule_cycle_hour(hour: int) -> None:
    """
    Reprogramme le cycle quotidien à chaud, sans redémarrer le service —
    appelé depuis PATCH /api/settings quand cycle_hour change. Best-effort :
    ne doit jamais faire échouer la sauvegarde des paramètres.
    """
    try:
        tz = pytz.timezone(settings.CYCLE_TIMEZONE)
        scheduler.reschedule_job("kora_daily_cycle", trigger=CronTrigger(hour=hour, minute=0, timezone=tz))
        logger.info("scheduler_rescheduled", hour=hour)
    except Exception as e:
        logger.warning("scheduler_reschedule_failed", hour=hour, error=str(e))
