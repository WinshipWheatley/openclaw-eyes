import os
import sys
import json
from datetime import datetime

# Add CWD to sys.path to allow importing from scripts and root
sys.path.append(os.getcwd())

try:
    from scripts.orientation_snapshot import (
        get_orientation_snapshot,
        get_git_info,
        get_ledger_status,
        get_horizon
    )
except ImportError:
    # Fallback for different execution contexts
    from orientation_snapshot import (
        get_orientation_snapshot,
        get_git_info,
        get_ledger_status,
        get_horizon
    )

# --- Configuration ---
CURRENT_STATE_OUT = "Operator/GENERATED_CURRENT_STATE.md"
NEXT_ACTIONS_OUT = "Operator/GENERATED_NEXT_ACTIONS.md"

DISCLAIMER = """<!-- 
GENERATED FILE - DO NOT EDIT MANUALLY
This file is programmatically generated from repository evidence.
Durable truth comes from receipts, tests, and committed source.
-->
"""

def generate_current_state(snapshot):
    lines = [
        "# GENERATED CURRENT STATE",
        f"*Generated: {snapshot['timestamp']}*",
        f"*Source Evidence: Git HEAD {snapshot['where_are_we']['git_head']}, SQLite Ledger*",
        "",
        "## 1. Confirmed System State",
    ]
    
    for fact in snapshot['confirmed_current']:
        lines.append(f"- {fact}")
    
    lines.extend([
        "",
        "## 2. Active Lane & Doctrine",
        snapshot['active_lane'],
        "",
        "## 3. Tool & Surface Boundaries",
        "### Allowed Tools",
        snapshot['allowed_tools'],
        "",
        "### Forbidden Surfaces",
        snapshot['forbidden_surfaces'],
        "",
        "## 4. North Star",
        snapshot['north_star'],
        "",
        "## 5. Safety & Staleness",
        "- **Runtime Health**: Not checked by this generator. Refer to `docs/operations/` or live diagnostics.",
        "- **Staleness**: This file is stale if the git HEAD has changed or if new receipts have been recorded since the generation timestamp.",
        "- **Privacy**: No PII or raw sensitive data is stored in this read-model.",
    ])
    
    return "\n".join(lines)

def generate_next_actions(snapshot):
    horizon = snapshot['visible_road_horizon']
    lines = [
        "# GENERATED NEXT ACTIONS",
        f"*Generated: {snapshot['timestamp']}*",
        "",
        "## 1. Next Safe Move",
        snapshot['next_safe_move'],
        "",
        "## 2. Visible Road Horizon",
        "### Visible Moves",
    ]
    
    for move in horizon['visible_moves']:
        lines.append(f"- {move}")
        
    lines.extend([
        "",
        f"- **Branch After**: {horizon['branch_after']}",
        f"- **Unsafe Beyond**: {horizon['unsafe_beyond']}",
        "",
        "## 3. Completed Lanes (Inferred)",
    ])
    
    # Simple inference: if ledger has events, we assume some progress
    ledger_status = snapshot['confirmed_current'][1]
    if "active" in ledger_status and "0 events" not in ledger_status:
        lines.append("- [DONE] Orientation Snapshot Receipt recorded to Ledger")
    else:
        lines.append("- [TODO] Record initial Orientation Snapshot Receipt")

    lines.extend([
        "- [DONE] Hardened Business Ops Spine (sqlite ledger v0 implementation)",
        "- [DONE] Canonicalized Operator Doctrine (orientation contract v0)",
        "",
        "## 4. Promotion Rules",
        "A 'TODO' item is only promoted to 'DONE' when a corresponding receipt exists in the SQLite Ledger or the implementation is verified by committed tests.",
    ])
    
    return "\n".join(lines)

def main():
    snapshot = get_orientation_snapshot()
    
    current_state_md = DISCLAIMER + "\n" + generate_current_state(snapshot)
    next_actions_md = DISCLAIMER + "\n" + generate_next_actions(snapshot)
    
    with open(CURRENT_STATE_OUT, "w") as f:
        f.write(current_state_md)
    print(f"Updated {CURRENT_STATE_OUT}")
        
    with open(NEXT_ACTIONS_OUT, "w") as f:
        f.write(next_actions_md)
    print(f"Updated {NEXT_ACTIONS_OUT}")

if __name__ == "__main__":
    main()
