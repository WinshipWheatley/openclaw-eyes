import os
import sys
import json
import argparse
import sqlite3
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

try:
    from scripts.inspect_business_ops_ledger import format_test_proof_summary
except ImportError:
    try:
        from inspect_business_ops_ledger import format_test_proof_summary
    except ImportError:
        def format_test_proof_summary(summary_text):
            if not summary_text or not summary_text.strip().startswith('{'):
                return summary_text
            try:
                data = json.loads(summary_text)
                status = data.get("status", "unknown").upper()
                label = data.get("command_label", "unknown")
                exit_code = data.get("exit_code", "?")
                head = data.get("git_head", "unknown")[:8]
                dirty = str(data.get("git_dirty", "unknown")).lower()
                return f"{status} {label} exit={exit_code} head={head} dirty={dirty}"
            except:
                return summary_text

# --- Configuration ---
CURRENT_STATE_OUT = "Operator/GENERATED_CURRENT_STATE.md"
NEXT_ACTIONS_OUT = "Operator/GENERATED_NEXT_ACTIONS.md"

DISCLAIMER = """<!--
GENERATED FILE - DO NOT EDIT MANUALLY
This file is programmatically generated from repository evidence.
Durable truth comes from receipts, tests, and committed source.
-->
"""

def get_recent_proof_receipts(limit=5, db_path=None):
    """
    Fetch recent test_proof_receipt events from the ledger.
    Excludes 'generated_status_check' from the list to avoid self-invalidation,
    but considers it for the 'strongest_clean' summary.
    """
    db_path = db_path or ".openclaw/business_ops/ledger.sqlite"
    if not os.path.exists(db_path):
        return {"list": [], "strongest_clean": None}

    try:
        # Use URI for read-only to avoid any side-effects
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        # Fetch more than limit to allow filtering out meta-checks
        cursor.execute("""
            SELECT ts, event_type, operator_visible_summary
            FROM events
            WHERE event_type IN ('test_proof_receipt', 'action_intent_gate_receipt', 'approval_log_entry', 'approval_request_record', 'outreach_email_draft_receipt')
            ORDER BY ts DESC LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()

        proofs = []
        strongest_clean = None
        for ts, etype, summ_raw in rows:
            display_ts = ts.replace('T', ' ')[:16]

            if etype == 'action_intent_gate_receipt':
                # Format: YYYY-MM-DD HH:MM [GATE] [SQLITE_VERIFIED] summ_raw (No Execution)
                formatted = f"[GATE] [SQLITE_VERIFIED] {summ_raw} (No Execution)"
                proofs.append(f"{display_ts} {formatted}")
                if len(proofs) >= limit:
                    break
                continue

            if etype == 'approval_log_entry':
                # Format: YYYY-MM-DD HH:MM [APPROVAL_RECORD] [SQLITE_VERIFIED] summ_raw (No Execution)
                formatted = f"[APPROVAL_RECORD] [SQLITE_VERIFIED] {summ_raw} (No Execution)"
                proofs.append(f"{display_ts} {formatted}")
                if len(proofs) >= limit:
                    break
                continue

            if etype == 'approval_request_record':
                # Format: YYYY-MM-DD HH:MM [APPROVAL_REQUEST] [SQLITE_VERIFIED] summ_raw (No Decision/No Execution)
                formatted = f"[APPROVAL_REQUEST] [SQLITE_VERIFIED] {summ_raw} (No Decision/No Execution)"
                proofs.append(f"{display_ts} {formatted}")
                if len(proofs) >= limit:
                    break
                continue

            if etype == 'outreach_email_draft_receipt':
                # Format: YYYY-MM-DD HH:MM [OUTREACH_DRAFT] [SQLITE_VERIFIED] summ_raw
                formatted = f"[OUTREACH_DRAFT] [SQLITE_VERIFIED] {summ_raw}"
                proofs.append(f"{display_ts} {formatted}")
                if len(proofs) >= limit:
                    break
                continue

            if etype == 'pii_vault_record':
                # Format: YYYY-MM-DD HH:MM [PII_VAULT] [SQLITE_VERIFIED] summ_raw
                formatted = f"[PII_VAULT] [SQLITE_VERIFIED] {summ_raw}"
                proofs.append(f"{display_ts} {formatted}")
                if len(proofs) >= limit:
                    break
                continue

            # etype is 'test_proof_receipt'
            import re

            # Default values
            status = "UNKNOWN"
            label = "unknown"
            exit_code = "?"
            head = "unknown"
            is_dirty = False

            if summ_raw and summ_raw.strip().startswith('{'):
                try:
                    data = json.loads(summ_raw)
                    status = data.get("status", "unknown").upper()
                    label = data.get("command_label", "unknown")
                    exit_code = data.get("exit_code", "?")
                    head = data.get("git_head", "unknown")[:8]
                    is_dirty = data.get("git_dirty", False)
                except:
                    pass
            else:
                # Parse string: "PASS label exit=0 head=sha dirty=true"
                if "PASS" in summ_raw: status = "PASS"
                elif "FAIL" in summ_raw: status = "FAIL"

                label_match = re.search(r"(?:PASS|FAIL) (.*?) exit=", summ_raw)
                if label_match: label = label_match.group(1)
                else: label = summ_raw # Fallback

                exit_match = re.search(r"exit=(\d+)", summ_raw)
                if exit_match: exit_code = exit_match.group(1)

                head_match = re.search(r"head=(\w+)", summ_raw)
                if head_match: head = head_match.group(1)[:8]

                is_dirty = "dirty=true" in summ_raw

            # Track strongest clean proof (first PASS with dirty=false)
            if status == "PASS" and not is_dirty and not strongest_clean:
                strongest_clean = f"[{status}] {label} head={head}"

            # Filter out self-referential status checks for the LIST
            if label == "generated_status_check":
                continue

            # Format: YYYY-MM-DD HH:MM [PASS/FAIL] [DIRTY] label ...
            display_ts = ts.replace('T', ' ')[:16]
            dirty_marker = " [DIRTY]" if is_dirty else ""
            formatted = f"[{status}]{dirty_marker} {label} exit={exit_code} head={head}"

            proofs.append(f"{display_ts} {formatted}")

            if len(proofs) >= limit and strongest_clean:
                break

        return {"list": proofs, "strongest_clean": strongest_clean}
    except Exception:
        return {"list": [], "strongest_clean": None}

def generate_current_state(snapshot):
    lines = [
        "# GENERATED CURRENT STATE",
        "## 1. Confirmed System State",
    ]

    for fact in snapshot['confirmed_current']:
        lines.append(f"- {fact}")

    # Section 2: Recent Verification Receipts
    proofs = snapshot.get('recent_proofs', [])
    strongest = snapshot.get('strongest_clean_proof')
    lines.extend([
        "",
        "## 2. Recent Verification Receipts",
        "Deterministic evidence proofs from the ledger (excludes status self-checks).",
    ])

    if strongest:
        lines.append(f"Strongest recent clean proof: {strongest}")
        lines.append("")

    if proofs:
        for p in proofs:
            lines.append(f"- {p}")
    else:
        lines.append("- No recent verification receipts found.")

    # Section 3: Truth Substrate Summary
    lines.extend([
        "",
        "## 3. Truth Substrate Summary",
        "Registry-governed canonical facts and source documents.",
    ])

    truth = snapshot.get("truth_substrate", {"status": "unavailable"})
    if truth["status"] == "available":
        m = truth["metrics"]
        f = m["facts"]
        r = m["registry"]
        rd = m["readiness"]
        lines.extend([
            f"- **Facts**: {f['total']} ({f['by_truth_status'].get('doctrine_reference', 0)} doctrine, {f['by_truth_status'].get('historical_checkpoint', 0)} historical)",
            f"- **Coverage**: {r['present_sources']}/{r['total_sources']} SOURCE_REGISTRY documents",
            f"- **Readiness**: {rd['result']}",
            "",
            "> Truth substrate status is read-only. Truth status describes verification posture, not runtime health or agent authority.",
        ])
    else:
        lines.append(f"- Status: UNAVAILABLE ({truth.get('reason', 'unknown')})")

    lines.extend([
        "",
        "## 4. Active Lane & Doctrine",
        snapshot['active_lane'],
        "",
        "## 5. Tool & Surface Boundaries",
        "### Allowed Tools",
        snapshot['allowed_tools'],
        "",
        "### Forbidden Surfaces",
        snapshot['forbidden_surfaces'],
        "",
        "## 6. North Star",
        snapshot['north_star'],
        "",
        "## 7. Safety & Staleness",
        "- **Runtime Health**: Not checked by this generator. Refer to `docs/operations/` or live diagnostics.",
        "- **Staleness**: This file is stale if the git HEAD has changed or if confirmed facts (e.g. active lane, contract items) have been modified since the generation timestamp.",
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
    # Inject recent proofs into snapshot for the generator
    results = get_recent_proof_receipts()
    snapshot['recent_proofs'] = results['list']
    snapshot['strongest_clean_proof'] = results['strongest_clean']

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
