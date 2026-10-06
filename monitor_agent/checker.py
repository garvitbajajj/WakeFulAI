import time
import httpx
import math
from loguru import logger
from db import db_client

async def perform_health_check(url: str, site_id: str) -> dict:
    """
    Performs an HTTP GET request to check uptime and latency.
    Also queries past runs to compute Z-score anomaly detection.
    """
    start_time = time.time()
    status_code = None
    response_size = 0
    error_message = None
    status = "success"

    logger.info(f"Triggering health check GET to {url}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            latency_ms = int(response.elapsed.total_seconds() * 1000)
            status_code = response.status_code
            response_size = len(response.content)

            if not (200 <= status_code < 300):
                status = "anomaly"
                error_message = f"Non-2xx status code received: {status_code}"
            elif latency_ms > 5000:
                status = "anomaly"
                error_message = f"High latency: {latency_ms}ms (threshold 5000ms)"

    except httpx.RequestError as exc:
        latency_ms = int((time.time() - start_time) * 1000)
        status = "anomaly"
        error_message = f"HTTP Request failed: {str(exc)}"
        logger.error(f"HTTP check request error for site {site_id}: {exc}")

    # Check Z-score anomaly over last 10 monitor runs if request itself succeeded
    is_zscore_anomaly = False
    if status == "success":
        try:
            recent_runs = db_client.get_recent_runs(site_id=site_id, limit=10)
            # Filter runs for 'monitor' type
            monitor_runs = [r for r in recent_runs if r.get("agent_type") == "monitor" and r.get("status") == "success"]
            
            if len(monitor_runs) >= 5:
                latencies = [r["latency_ms"] for r in monitor_runs]
                mean = sum(latencies) / len(latencies)
                variance = sum((x - mean) ** 2 for x in latencies) / len(latencies)
                std_dev = math.sqrt(variance)
                
                if std_dev > 0:
                    z_score = (latency_ms - mean) / std_dev
                    # Trigger if latency is > 2 standard deviations AND latency is significantly high (> 1000ms)
                    # to prevent alerting on small fluctuations like 150ms vs 100ms average
                    if z_score > 2.0 and latency_ms > 1000:
                        is_zscore_anomaly = True
                        status = "anomaly"
                        error_message = f"Latency anomaly detected: {latency_ms}ms (Z-score: {z_score:.2f}, Rolling Mean: {mean:.1f}ms, Std Dev: {std_dev:.1f}ms)"
                        logger.warning(f"Z-score anomaly detected for site {site_id}: {error_message}")
        except Exception as db_err:
            logger.error(f"Error checking rolling latency anomaly: {db_err}")

    return {
        "status": status,
        "latency_ms": latency_ms,
        "status_code": status_code,
        "response_size": response_size,
        "error_message": error_message,
        "is_zscore_anomaly": is_zscore_anomaly
    }
