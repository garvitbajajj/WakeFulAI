from loguru import logger
from .checker import perform_health_check
from .alerter import trigger_anomaly_alert
from db import db_client

async def run_monitor_agent(site: dict) -> dict:
    """
    Executes a health check on the site, logs it, and alerts if there is an anomaly.
    """
    site_id = site["id"]
    url = site["url"]
    
    logger.info(f"Monitor Agent: Running health check for {site['name']} ({url})")
    
    # Run the check
    check_result = await perform_health_check(url, site_id)
    
    status = check_result["status"]
    latency_ms = check_result["latency_ms"]
    error_message = check_result["error_message"]
    
    notes = f"HTTP check returned status code {check_result['status_code']}. Response size: {check_result['response_size']} bytes."
    if error_message:
        notes += f" Error: {error_message}"

    # Log agent run to db
    try:
        db_client.log_run(
            site_id=site_id,
            agent_type="monitor",
            status=status,
            latency_ms=latency_ms,
            notes=notes,
            screenshot_url=None
        )
        logger.info(f"Monitor Agent: Logged health check run with status '{status}'")
    except Exception as e:
        logger.error(f"Monitor Agent: Failed to log run to db: {e}")

    # If anomaly, trigger alerts
    if status == "anomaly":
        await trigger_anomaly_alert(site, latency_ms, error_message)

    return check_result
