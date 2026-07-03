from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

from core.config import settings
from core.logger import logger

scheduler = AsyncIOScheduler()


async def _run_kora_cycle():
    from agent.graph import kora_graph_auto
    from integrations.gmail_client import gmail_client
    import uuid

    cycle_id = str(uuid.uuid4())
    started_at = datetime.now(pytz.timezone(settings.CYCLE_TIMEZONE))
    logger.info("scheduled_cycle_start", cycle_id=cycle_id, mode="auto")

    published = 0
    errors = []

    try:
        config = {"configurable": {"thread_id": cycle_id}}
        result = await kora_graph_auto.ainvoke(
            {"mode": "auto", "cycle_id": cycle_id, "published_count": 0, "errors": [],
             "hitl_approved": False, "raw_sources": [], "selected_articles": [],
             "current_article": None, "generated_article": None,
             "image_url": None, "wp_media_id": None, "wp_post_id": None,
             "article_index": 0},
            config=config,
        )
        if result:
            published = result.get("published_count", 0)
            errors = result.get("errors", [])

        logger.info("scheduled_cycle_complete", cycle_id=cycle_id, published=published)
        await _send_report(gmail_client, cycle_id, started_at, published, errors, success=True)

    except Exception as e:
        errors.append(str(e))
        logger.error("scheduled_cycle_failed", cycle_id=cycle_id, error=str(e))
        await _send_report(gmail_client, cycle_id, started_at, published, errors, success=False)


async def _send_report(client, cycle_id, started_at, published, errors, success):
    status_label = "✅ Succès" if success else "❌ Échec"
    color = "#22c55e" if success else "#ef4444"
    errors_html = "".join(f"<li style='color:#ef4444'>{e}</li>" for e in errors) or "<li>Aucune</li>"

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
          <tr><td style="padding:6px 0;color:#6b7280">Cycle ID</td>
              <td style="padding:6px 0;font-family:monospace;font-size:12px">{cycle_id[:8]}…</td></tr>
          <tr><td style="padding:6px 0;color:#6b7280">Articles publiés</td>
              <td style="padding:6px 0;font-weight:700;font-size:20px;color:{color}">{published}</td></tr>
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

    subject = f"[KORA] {status_label} — {published} article(s) — {started_at.strftime('%d/%m/%Y')}"
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
