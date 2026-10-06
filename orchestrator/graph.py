from langgraph.graph import StateGraph, END
from orchestrator.agent import OrchestratorState
from db import db_client
from orchestrator.planner import plan_browser_flow
from browser_agent.agent import execute_browser_plan
from monitor_agent.agent import run_monitor_agent
from loguru import logger

async def fetch_sites_node(state: OrchestratorState) -> dict:
    logger.info("Orchestrator Graph: fetch_sites_node executing")
    # If sites are already provided (e.g., manual trigger for a single site), keep them
    if state.get("sites"):
        logger.info(f"Using pre-configured list of {len(state['sites'])} site(s).")
        return {"run_complete": False}
        
    try:
        active_sites = db_client.get_active_sites()
        logger.info(f"Fetched {len(active_sites)} active site(s) from database.")
        return {"sites": active_sites, "run_complete": False}
    except Exception as e:
        logger.error(f"Failed to fetch sites from database: {e}")
        return {"sites": [], "run_complete": True}

async def plan_flow_node(state: OrchestratorState) -> dict:
    logger.info("Orchestrator Graph: plan_flow_node executing")
    sites = state.get("sites", [])
    if not sites:
        logger.info("No sites left to process. Setting run_complete=True.")
        return {"run_complete": True, "current_site": None}

    # Pop the first site to process
    current_site = sites[0]
    logger.info(f"Processing site: {current_site['name']} ({current_site['url']})")
    
    session_flow = current_site.get("session_flow", "")
    try:
        planned_steps = await plan_browser_flow(current_site["url"], session_flow)
    except Exception as e:
        logger.error(f"Planning failed for site {current_site['id']}: {e}")
        # Fallback to simple navigate
        planned_steps = [{"action": "navigate", "url": current_site["url"]}]

    return {
        "current_site": current_site,
        "planned_flow": planned_steps,
        "sites": sites[1:]  # Remaining sites
    }

async def dispatch_browser_node(state: OrchestratorState) -> dict:
    logger.info("Orchestrator Graph: dispatch_browser_node executing")
    site = state.get("current_site")
    steps = state.get("planned_flow", [])
    
    if not site:
        logger.warning("No active site in state. Skipping browser automation.")
        return {"browser_result": None}

    try:
        result = await execute_browser_plan(steps, site["id"])
        logger.info(f"Browser Agent finished. Status: {result['status']}, Latency: {result['latency_ms']}ms")
        return {"browser_result": result}
    except Exception as e:
        logger.error(f"Browser Agent crashed: {e}")
        return {
            "browser_result": {
                "status": "failure",
                "latency_ms": 0,
                "results": [f"Execution crashed: {e}"],
                "error_message": str(e),
                "screenshot_bytes": None
            }
        }

async def dispatch_monitor_node(state: OrchestratorState) -> dict:
    logger.info("Orchestrator Graph: dispatch_monitor_node executing")
    site = state.get("current_site")
    if not site:
        logger.warning("No active site in state. Skipping HTTP health check.")
        return {"monitor_result": None}

    try:
        result = await run_monitor_agent(site)
        logger.info(f"Monitor Agent finished. Status: {result['status']}, Latency: {result['latency_ms']}ms")
        return {"monitor_result": result}
    except Exception as e:
        logger.error(f"Monitor Agent crashed: {e}")
        return {
            "monitor_result": {
                "status": "failure",
                "latency_ms": 0,
                "error_message": str(e)
            }
        }

async def log_results_node(state: OrchestratorState) -> dict:
    logger.info("Orchestrator Graph: log_results_node executing")
    site = state.get("current_site")
    b_res = state.get("browser_result")
    m_res = state.get("monitor_result")
    
    if not site:
        return {}

    # 1. Log Browser Run results if available
    if b_res:
        notes = "Browser plan actions executed:\n" + "\n".join(b_res.get("results", []))
        if b_res.get("error_message"):
            notes += f"\nError: {b_res['error_message']}"
            
        screenshot_url = None
        if b_res.get("screenshot_bytes"):
            try:
                screenshot_url = db_client.upload_screenshot(site["id"], b_res["screenshot_bytes"])
            except Exception as e:
                logger.error(f"Failed to upload browser screenshot: {e}")

        try:
            db_client.log_run(
                site_id=site["id"],
                agent_type="browser",
                status=b_res["status"],
                latency_ms=b_res["latency_ms"],
                notes=notes,
                screenshot_url=screenshot_url
            )
            logger.info("Browser run logged to database.")
        except Exception as e:
            logger.error(f"Failed to log browser run: {e}")

    # Note: Monitor run is already logged inside monitor_agent/agent.py (run_monitor_agent).

    # 2. Log unified Orchestrator Run
    status = "success"
    if (b_res and b_res["status"] != "success") or (m_res and m_res["status"] != "success"):
        if (m_res and m_res["status"] == "anomaly") or (b_res and b_res["status"] == "anomaly"):
            status = "anomaly"
        else:
            status = "failure"

    orch_latency = (b_res.get("latency_ms", 0) if b_res else 0) + (m_res.get("latency_ms", 0) if m_res else 0)
    orch_notes = f"Orchestrator successfully processed site {site['name']}.\n"
    if b_res:
        orch_notes += f"Browser Flow Status: {b_res['status']} ({b_res['latency_ms']}ms).\n"
    if m_res:
        orch_notes += f"Monitor Uptime Status: {m_res['status']} ({m_res['latency_ms']}ms)."

    try:
        db_client.log_run(
            site_id=site["id"],
            agent_type="orchestrator",
            status=status,
            latency_ms=orch_latency,
            notes=orch_notes,
            screenshot_url=None
        )
        logger.info("Orchestrator unified run logged to database.")
    except Exception as e:
        logger.error(f"Failed to log orchestrator run: {e}")

    # Reset temp run vars in state for next loop iteration
    return {
        "current_site": None,
        "planned_flow": [],
        "browser_result": None,
        "monitor_result": None
    }

# Wire the graph
workflow = StateGraph(OrchestratorState)

workflow.add_node("fetch_sites", fetch_sites_node)
workflow.add_node("plan_flow", plan_flow_node)
workflow.add_node("dispatch_browser", dispatch_browser_node)
workflow.add_node("dispatch_monitor", dispatch_monitor_node)
workflow.add_node("log_results", log_results_node)

workflow.set_entry_point("fetch_sites")
workflow.add_edge("fetch_sites", "plan_flow")

def route_after_planning(state: OrchestratorState):
    if state.get("run_complete", False):
        return "end"
    return "continue"

workflow.add_conditional_edges(
    "plan_flow",
    route_after_planning,
    {
        "end": END,
        "continue": "dispatch_browser"
    }
)

workflow.add_edge("dispatch_browser", "dispatch_monitor")
workflow.add_edge("dispatch_monitor", "log_results")
workflow.add_edge("log_results", "plan_flow")

# Compile the runnable graph
orchestrator_graph = workflow.compile()
