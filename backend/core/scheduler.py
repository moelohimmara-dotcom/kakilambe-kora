from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from core.config import settings
from core.logger import logger

scheduler = AsyncIOScheduler()


async def _run_kora_cycle():
    from agent.graph import kora_graph_auto
    import uuid

    cycle_id = str(uuid.uuid4())
    logger.info("scheduled_cycle_start", cycle_id=cycle_id, mode="auto")
    try:
        config = {"configurable": {"thread_id": cycle_id}}
        await kora_graph_auto.ainvoke(
            {"mode": "auto", "cycle_id": cycle_id, "published_count": 0, "errors": [],
             "hitl_approved": False, "raw_sources": [], "selected_articles": [],
             "current_article": None, "generated_article": None,
             "image_url": None, "wp_media_id": None, "wp_post_id": None,
             "article_index": 0},
            config=config,
        )
        logger.info("scheduled_cycle_complete", cycle_id=cycle_id)
    except Exception as e:
        logger.error("scheduled_cycle_failed", cycle_id=cycle_id, error=str(e))


def start_scheduler():
    tz = pytz.timezone(settings.CYCLE_TIMEZONE)
    scheduler.add_job(
        _run_kora_cycle,
        CronTrigger(hour=settings.CYCLE_HOUR, minute=0, timezone=tz),
        id="kora_daily_cycle",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.start()
    logger.info(
        "scheduler_started",
        hour=settings.CYCLE_HOUR,
        timezone=settings.CYCLE_TIMEZONE,
    )
