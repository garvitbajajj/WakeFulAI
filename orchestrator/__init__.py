from .graph import orchestrator_graph
from .agent import OrchestratorState

async def run_orchestrator(sites: list[dict] = None) -> dict:
    """
    Runs the orchestrator LangGraph state machine.
    If 'sites' is provided, it processes only those sites.
    Otherwise, it fetches all active sites from the database.
    """
    initial_state = {
        "sites": sites or [],
        "current_site": None,
        "planned_flow": [],
        "browser_result": None,
        "monitor_result": None,
        "run_complete": False
    }
    return await orchestrator_graph.ainvoke(initial_state)

__all__ = ["orchestrator_graph", "run_orchestrator", "OrchestratorState"]
