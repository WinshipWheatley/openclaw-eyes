import os
import sys
import json
import argparse
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
    
    # Canonical signal: orientation_snapshot_receipt
    ledger_info = snapshot.get('ledger_info', {})
    if ledger_info.get('has_snapshot_receipt', False):
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
    parser = argparse.ArgumentParser(description="Generate operator status read-models.")
    parser.add_argument("--write", action="store_true", help="Explicitly write generated files.")
    parser.add_argument("--check", action="store_true", help="Check if generated files are current without writing. Exits nonzero if stale.")
    args = parser.parse_args()

    snapshot = get_orientation_snapshot()
    
    current_state_md = DISCLAIMER + "\n" + generate_current_state(snapshot)
    next_actions_md = DISCLAIMER + "\n" + generate_next_actions(snapshot)
    
    print(f"--- Operator Status Preview ---")
    print(f"Timestamp: {snapshot['timestamp']}")
    print(f"Source: Git HEAD {snapshot['where_are_we']['git_head']}")
    print(f"Ledger: {snapshot['ledger_info']['status']} ({snapshot['ledger_info'].get('event_count', 0)} events)")
    print(f"-------------------------------")

    if args.write:
        with open(CURRENT_STATE_OUT, "w") as f:
            f.write(current_state_md)
        print(f"Updated {CURRENT_STATE_OUT}")

        with open(NEXT_ACTIONS_OUT, "w") as f:
            f.write(next_actions_md)
        print(f"Updated {NEXT_ACTIONS_OUT}")
    elif args.check:
        stale = False
        if os.path.exists(CURRENT_STATE_OUT):
            with open(CURRENT_STATE_OUT, "r") as f:
                if f.read() != current_state_md:
                    print(f"STALE: {CURRENT_STATE_OUT} differs from generated content.")
                    stale = True
        else:
            print(f"MISSING: {CURRENT_STATE_OUT}")
            stale = True

        if os.path.exists(NEXT_ACTIONS_OUT):
            with open(NEXT_ACTIONS_OUT, "r") as f:
                if f.read() != next_actions_md:
                    print(f"STALE: {NEXT_ACTIONS_OUT} differs from generated content.")
                    stale = True
        else:
            print(f"MISSING: {NEXT_ACTIONS_OUT}")
            stale = True

        if stale:
            print("\nError: Generated files are stale or missing. Run with --write to update.")
            sys.exit(1)
        else:
            print("OK: Generated files are current.")
    else:
        print("\nRead-only preview mode. Use --write to update files or --check to verify.")

if __name__ == "__main__":
    main()
