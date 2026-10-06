import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from orchestrator import run_orchestrator
from loguru import logger

scheduler = AsyncIOScheduler()

async def trigger_scheduler_job():
    logger.info("Scheduler: Starting scheduled run for all active sites...")
    try:
        await run_orchestrator()
        logger.info("Scheduler: Scheduled run completed successfully.")
    except Exception as e:
        logger.error(f"Scheduler: Scheduled run encountered error: {e}")

def start_scheduler():
    interval_minutes = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))
    logger.info(f"Scheduler: Starting APScheduler. Running orchestrator every {interval_minutes} minutes.")
    
    # Check if job already exists before adding
    if not scheduler.get_job("main_orchestrator_job"):
        scheduler.add_job(
            trigger_scheduler_job,
            trigger="interval",
            minutes=interval_minutes,
            id="main_orchestrator_job",
            replace_existing=True
        )
    
    if not scheduler.running:
        scheduler.start()

def stop_scheduler():
    logger.info("Scheduler: Stopping APScheduler...")
    if scheduler.running:
        scheduler.shutdown()
