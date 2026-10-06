import os
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from orchestrator import run_orchestrator
from db import db_client
from loguru import logger

scheduler = AsyncIOScheduler()

DEFAULT_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))

# ponytail: last-run times live in memory, so every site runs once right after a restart.
# Persist them (or read the latest agent_runs row) if that burst matters.
_last_run: dict[str, float] = {}

def get_due_sites(sites: list[dict], now: float) -> list[dict]:
    """Sites whose own check_interval_minutes has elapsed since their last scheduled run."""
    return [
        s for s in sites
        if now - _last_run.get(s["id"], float("-inf")) >= (s.get("check_interval_minutes") or DEFAULT_INTERVAL_MINUTES) * 60
    ]

async def trigger_scheduler_job():
    now = time.monotonic()
    due = get_due_sites(db_client.get_active_sites(), now)
    if not due:
        return
    logger.info(f"Scheduler: {len(due)} site(s) due, starting orchestrator run...")
    for site in due:
        _last_run[site["id"]] = now
    try:
        await run_orchestrator(sites=due)
        logger.info("Scheduler: Scheduled run completed successfully.")
    except Exception as e:
        logger.error(f"Scheduler: Scheduled run encountered error: {e}")

def start_scheduler():
    logger.info(f"Scheduler: Starting APScheduler. Checking every minute for due sites (default interval {DEFAULT_INTERVAL_MINUTES} min).")

    # Tick every minute; each site is only run when its own interval has elapsed
    if not scheduler.get_job("main_orchestrator_job"):
        scheduler.add_job(
            trigger_scheduler_job,
            trigger="interval",
            minutes=1,
            id="main_orchestrator_job",
            replace_existing=True
        )

    if not scheduler.running:
        scheduler.start()

def stop_scheduler():
    logger.info("Scheduler: Stopping APScheduler...")
    if scheduler.running:
        scheduler.shutdown()
