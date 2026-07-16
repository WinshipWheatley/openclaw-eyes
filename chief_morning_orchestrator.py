"""
chief_morning_orchestrator.py

Orchestrates the refresh of Guardian-layer artifacts and the Chief Morning Synthesis.
This ensures Cassandra always has fresh inputs for the morning briefing.

Guardian order:
1. Ops Actions Context (via Ops Reporter)
2. Nightly Polish Log (via CEO Briefing)
3. System Health Report (via Reporter)
4. Chief Morning Synthesis
"""

import os
from datetime import datetime

def refresh_morning_artifacts() -> bool:
    """
    Triggers a sequential refresh of all morning-layer artifacts.
    Returns True if all stages completed without fatal error.
    """
    print("[morning_orchestrator] Starting morning artifact refresh...", flush=True)
    
    try:
        # 1. Ops Actions Context
        import chief_ops_reporter as ops
        print("[morning_orchestrator] Refreshing Ops Actions Context...", flush=True)
        ops.write_ops_actions_artifact()
        
        # 2. Nightly Polish Log
        import chief_ceo_briefing as ceo
        print("[morning_orchestrator] Refreshing Nightly Polish Log...", flush=True)
        ceo.refresh_nightly_polish_artifact()
        
        # 3. System Health Report
        import chief_reporter_brain as reporter
        print("[morning_orchestrator] Refreshing System Health Report...", flush=True)
        reporter.refresh_report_artifact(task_class="cassandra_scheduled_brief")
        
        # 4. Chief Morning Synthesis
        import chief_morning_synthesis as synthesis
        print("[morning_orchestrator] Writing Chief Morning Synthesis...", flush=True)
        synthesis.write_chief_morning_synthesis()
        
        print("[morning_orchestrator] Morning artifact refresh complete.", flush=True)
        return True
        
    except Exception as e:
        print(f"[morning_orchestrator] error during refresh: {e}", flush=True)
        return False

if __name__ == "__main__":
    refresh_morning_artifacts()
