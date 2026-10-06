from typing import TypedDict, Optional, List, Dict

class OrchestratorState(TypedDict):
    """
    Represents the state of the WakeFulAI Orchestrator.
    """
    sites: List[Dict]               # Remaining active sites to process
    current_site: Optional[Dict]    # The site currently being run
    planned_flow: List[Dict]        # Planned browser agent actions
    browser_result: Optional[Dict]  # Output metrics/status from browser agent run
    monitor_result: Optional[Dict]  # Output metrics/status from monitor agent run
    run_complete: bool              # Completion status flag
