from loguru import logger
from browser_agent.agent import execute_browser_plan
from monitor_agent.agent import run_monitor_agent

# These tools can be directly utilized within our orchestrator nodes or by LangChain agents if expanded.
async def run_browser_automation(site: dict, steps: list[dict]) -> dict:
    logger.info(f"Triggering browser automation tool for {site['name']}")
    return await execute_browser_plan(steps, site["id"])

async def run_http_monitor(site: dict) -> dict:
    logger.info(f"Triggering monitor health tool for {site['name']}")
    return await run_monitor_agent(site)
