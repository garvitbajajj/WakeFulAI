import asyncio
import sys
import time
import traceback
from loguru import logger
from .session import session_manager
from . import actions

def _run_on_proactor_loop(coro):
    loop = asyncio.ProactorEventLoop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

async def execute_browser_plan(steps: list[dict], site_id: str) -> dict:
    # Playwright spawns a driver subprocess, which on Windows needs a ProactorEventLoop.
    # uvicorn --reload runs a SelectorEventLoop there, so give the session its own loop in a thread.
    if sys.platform == "win32" and not isinstance(asyncio.get_running_loop(), asyncio.ProactorEventLoop):
        return await asyncio.to_thread(_run_on_proactor_loop, _execute_browser_plan(steps, site_id))
    return await _execute_browser_plan(steps, site_id)

async def _execute_browser_plan(steps: list[dict], site_id: str) -> dict:
    """
    Executes a list of planned actions sequentially on a headless browser.
    Each step should be a dict like:
    - {"action": "navigate", "url": "..."}
    - {"action": "click", "selector": "..."}
    - {"action": "fill", "selector": "...", "value": "..."}
    - {"action": "scroll", "direction": "down|up", "amount": 500}
    - {"action": "screenshot"}
    """
    start_time = time.time()
    results = []
    status = "success"
    error_message = None
    screenshot_bytes = None

    logger.info(f"Starting browser plan execution for site {site_id} with {len(steps)} steps")

    try:
        async with session_manager.get_page() as page:
            for i, step in enumerate(steps):
                action = step.get("action", "").lower()
                logger.info(f"Executing step {i+1}/{len(steps)}: {action}")
                
                try:
                    if action == "navigate":
                        url = step["url"]
                        res = await actions.navigate(page, url)
                        results.append(res)
                    elif action == "click":
                        selector = step["selector"]
                        res = await actions.click(page, selector)
                        results.append(res)
                    elif action == "fill" or action == "fill_form":
                        selector = step["selector"]
                        value = step["value"]
                        res = await actions.fill_form(page, selector, value)
                        results.append(res)
                    elif action == "scroll":
                        direction = step.get("direction", "down")
                        amount = int(step.get("amount", 500))
                        res = await actions.scroll(page, direction, amount)
                        results.append(res)
                    elif action == "screenshot":
                        screenshot_bytes = await actions.screenshot(page)
                        results.append("Captured custom screenshot")
                    else:
                        logger.warning(f"Unknown action: {action}")
                        results.append(f"Skipped unknown action: {action}")
                except Exception as step_error:
                    logger.error(f"Step {i+1} failed: {step_error}")
                    status = "failure"
                    error_message = f"Step {i+1} ({action}) failed: {str(step_error)}"
                    results.append(f"Failed: {error_message}")
                    
                    # Capture screenshot at point of failure
                    try:
                        screenshot_bytes = await actions.screenshot(page)
                        results.append("Captured error screenshot")
                    except Exception as s_err:
                        logger.error(f"Failed to capture error screenshot: {s_err}")
                    break

            # If no manual screenshot was captured, capture one at the end of successful flow
            if screenshot_bytes is None and status == "success":
                try:
                    screenshot_bytes = await actions.screenshot(page)
                except Exception as s_err:
                    logger.error(f"Failed to capture final screenshot: {s_err}")

    except Exception as run_error:
        status = "failure"
        error_message = f"Browser session crashed: {type(run_error).__name__}: {run_error}"
        logger.error(f"Browser crash: {traceback.format_exc()}")
        results.append(error_message)

    latency_ms = int((time.time() - start_time) * 1000)
    
    return {
        "status": status,
        "latency_ms": latency_ms,
        "results": results,
        "error_message": error_message,
        "screenshot_bytes": screenshot_bytes
    }
