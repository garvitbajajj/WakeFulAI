import os
import httpx
from datetime import datetime
from loguru import logger
from db import db_client

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

async def trigger_anomaly_alert(site: dict, latency_ms: int, error_message: str):
    """
    Inserts a row into the anomalies table and triggers webhook alerts (e.g., Slack).
    """
    site_id = site["id"]
    site_name = site["name"]
    site_url = site["url"]

    logger.warning(f"Triggering anomaly alerts for site: {site_name} ({site_url})")

    # 1. Log anomaly to database
    try:
        db_client.log_anomaly(site_id=site_id, latency_ms=latency_ms, error_message=error_message)
        logger.info("Anomaly successfully logged to database.")
    except Exception as db_err:
        logger.error(f"Failed to log anomaly to db: {db_err}")

    # 2. Trigger webhook (Slack format) if configured
    if not WEBHOOK_URL or "mock-webhook" in WEBHOOK_URL:
        logger.info(f"Webhook URL not configured or mock. Skipping webhook POST. Payload: Site: {site_name}, Error: {error_message}")
        return

    payload = {
        "text": (
            f"🚨 *WakeFulAI Anomaly Alert* 🚨\n"
            f"*Site Name:* {site_name}\n"
            f"*URL:* {site_url}\n"
            f"*Latency:* {latency_ms}ms\n"
            f"*Error Details:* `{error_message}`\n"
            f"*Timestamp:* {datetime.utcnow().isoformat()}Z"
        )
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(WEBHOOK_URL, json=payload, timeout=5.0)
            if response.status_code >= 200 and response.status_code < 300:
                logger.info("Webhook alert sent successfully.")
            else:
                logger.error(f"Webhook alert returned status: {response.status_code}")
    except Exception as webhook_err:
        logger.error(f"Failed to send webhook alert: {webhook_err}")
