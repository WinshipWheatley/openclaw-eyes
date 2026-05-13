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

try:
    from scripts.record_artifact_checkpoint_receipts import (
        MODULE_ATLAS_ARTIFACT_PATHS,
        MODULE_ATLAS_BOOTSTRAP_COMMAND,
    )
except ImportError:
    from record_artifact_checkpoint_receipts import (
        MODULE_ATLAS_ARTIFACT_PATHS,
        MODULE_ATLAS_BOOTSTRAP_COMMAND,
    )

try:
    from scripts.build_source_inventory import build_inventory, format_operator_inventory
except ImportError:
    from build_source_inventory import build_inventory, format_operator_inventory

CONTEXT_GATE_SCRIPTS = (
    ("Promotion Gate", "accepted_context_promotion_gate_v0", "scripts/promote_accepted_context.py"),
    ("Safe Extraction", "safe_body_extraction_v0", "scripts/extract_accepted_sources.py"),
    ("Source Cards", "source_cards_v0", "scripts/build_source_cards.py"),
    ("Working Packets", "accepted_working_context_packets_v0", "scripts/build_working_context_packets.py"),
    ("Retrieval Gate", "agent_context_retrieval_gate_v0", "scripts/query_context_packets.py"),
    ("Activation Gate", "runtime_module_activation_gate_v0", "scripts/check_runtime_activation_gate.py"),
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
            WHERE event_type IN ('test_proof_receipt', 'action_intent_gate_receipt', 'approval_log_entry', 'approval_request_record', 'outreach_email_draft_receipt', 'truth_packet_decision_receipt')
            ORDER BY ts DESC LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()

        proofs = []
        strongest_clean = None
        for ts, etype, summ_raw in rows:
            display_ts = ts.replace('T', ' ')[:16]

            if etype == 'truth_packet_decision_receipt':
                # Format: YYYY-MM-DD HH:MM [TRUTH_DECISION] [SQLITE_VERIFIED] summ_raw (Audit Only)
                formatted = f"[TRUTH_DECISION] [SQLITE_VERIFIED] {summ_raw} (Audit Only)"
                proofs.append(f"{display_ts} {formatted}")
                if len(proofs) >= limit:
                    break
                continue

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


def _status_display(value):
    if value is None:
        return "unknown"
    return str(value).replace("_", "-")


def format_artifact_checkpoint_receipt(ts, packet_json_safe):
    try:
        packet = json.loads(packet_json_safe or "{}")
    except Exception:
        packet = {}

    artifact_path = packet.get("artifact_path", "unknown")
    artifact_status = _status_display(packet.get("artifact_status"))
    authority_status = _status_display(packet.get("authority_status"))
    sqlite_meaning = _status_display(packet.get("sqlite_meaning"))
    runtime_activation = "true" if packet.get("runtime_activation") is True else "false"
    display_ts = ts.replace('T', ' ')[:16]
    return (
        f"| `{artifact_path}` | {display_ts} | recorded `{artifact_status}` | "
        f"`authority={authority_status}`; `runtime_activation={runtime_activation}`; "
        f"`sqlite={sqlite_meaning}`; `body=not-ingested` |"
    )


def get_artifact_checkpoint_receipts(limit=20, db_path=None, artifact_paths=None):
    """
    Fetch generic artifact_checkpoint receipts from the ledger.
    Reads receipt metadata only from events/packets; artifact bodies are not read.
    """
    db_path = db_path or ".openclaw/business_ops/ledger.sqlite"
    if not os.path.exists(db_path):
        return []

    artifact_path_set = set(artifact_paths or [])
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.ts, p.packet_json_safe
            FROM events e
            JOIN packets p ON p.event_id = e.event_id
            WHERE e.event_type = 'artifact_checkpoint'
            ORDER BY e.ts DESC
            LIMIT 100
        """)
        rows = cursor.fetchall()
        conn.close()
    except Exception:
        return []

    receipts = []
    seen_paths = set()
    for ts, packet_json_safe in rows:
        try:
            packet = json.loads(packet_json_safe or "{}")
        except Exception:
            packet = {}
        artifact_path = packet.get("artifact_path")
        if artifact_path_set and artifact_path not in artifact_path_set:
            continue
        if artifact_path in seen_paths:
            continue
        receipts.append(format_artifact_checkpoint_receipt(ts, packet_json_safe))
        seen_paths.add(artifact_path)
        if len(receipts) >= limit:
            break

    return receipts


def format_module_atlas_artifact_checkpoint_section(
    artifact_checkpoints,
    expected_total=None,
    bootstrap_command=MODULE_ATLAS_BOOTSTRAP_COMMAND,
):
    expected_total = expected_total if expected_total is not None else len(artifact_checkpoints)
    recorded_total = len(artifact_checkpoints)
    missing_total = max(expected_total - recorded_total, 0)

    if recorded_total == 0:
        evidence = (
            f"no local Module Atlas checkpoint receipts found for {expected_total} "
            "committed docs/code artifacts."
        )
        next_safe_move = f"run `{bootstrap_command}` to record metadata-only checkpoints."
    elif missing_total:
        evidence = (
            f"{recorded_total}/{expected_total} committed Module Atlas docs/code artifacts "
            "have metadata-only SQLite checkpoint receipts."
        )
        next_safe_move = f"run `{bootstrap_command}` to fill missing metadata-only checkpoints."
    else:
        evidence = "committed docs/code artifacts have metadata-only SQLite checkpoint receipts."
        next_safe_move = "review docs/tests/receipts; runtime activation still requires a separate approved lane."

    lines = [
        "",
        "### Module Atlas Artifact Checkpoints",
        f"**Evidence:** {evidence}",
        "**Boundary:** recorded checkpoint only; not runtime authority. No full Markdown/code body is ingested.",
        "**Blocked:** no module, agent, broker, customer deployment, or runtime behavior is activated or authorized by these receipts.",
        f"**Next safe move:** {next_safe_move}",
    ]

    if artifact_checkpoints:
        lines.extend(
            [
                "",
                "| Artifact | Receipt Time | Checkpoint | Authority Boundary |",
                "| --- | --- | --- | --- |",
            ]
        )
        lines.extend(artifact_checkpoints)

    return lines


def get_source_inventory_operator_status():
    """Build the bounded metadata-only source inventory operator read model."""
    return format_operator_inventory(build_inventory())


def format_source_inventory_section(source_inventory_operator_status):
    if not source_inventory_operator_status:
        return []

    return [
        "",
        "## 3. Source Inventory",
        *source_inventory_operator_status.splitlines(),
    ]


def get_context_gates_operator_status():
    """Build a compact status for deterministic context substrate gates."""
    gates = [
        {
            "label": label,
            "version": version,
            "path": path,
            "available": os.path.exists(path),
        }
        for label, version, path in CONTEXT_GATE_SCRIPTS
    ]
    available = sum(1 for gate in gates if gate["available"])
    gate_text = "; ".join(
        f"{gate['label']}=`{gate['version']}`" for gate in gates if gate["available"]
    ) or "none"
    missing_text = "; ".join(
        f"`{gate['path']}`" for gate in gates if not gate["available"]
    ) or "none"

    lines = [
        "Accepted Context Substrate Gates v0",
        "",
        "Evidence:",
        f"- {available}/{len(gates)} deterministic backend/read-model gates are available as local scripts.",
        f"- Available gates: {gate_text}.",
        "- Gate chain preserves separate states: metadata captured, promoted, extracted, summarized, packetized, retrieved, and activation-blocked.",
        "",
        "Boundary:",
        "- Generated status reports gate availability only; it does not promote, extract, summarize, packetize, retrieve, or activate context.",
        "- Generated status performs `body_ingested=false` for this section and does not read extraction artifacts or raw source bodies.",
        "- SQLite behavior is unchanged; `runtime_authority=false`; activation remains a blocked readiness contract.",
        "",
        "Blocked:",
        f"- Missing gate scripts: {missing_text}.",
        "- Full repo scans, hard-drive scans, secrets/private/legal/tax/CPA/AppData/log access, broad RAG, vector DB, and raw body retrieval remain blocked.",
        "- No agents, modules, brokers, customer deployment, external tools, live runtime health checks, or runtime behavior are activated.",
        "",
        "Next safe move:",
        "- Use the gates in order on explicit allowlisted records with a promotion reason; keep runtime/module activation in the blocked readiness lane.",
    ]
    return "\n".join(lines)


def format_context_gates_section(context_gates_operator_status):
    if not context_gates_operator_status:
        return []

    return [
        "",
        "## 4. Context Gates",
        *context_gates_operator_status.splitlines(),
    ]


def format_helm_state_operator_status(read_model):
    """Format compact Helm State status for generated operator output."""
    helm_state = read_model["helm_state"]
    strategic_gravity = read_model["strategic_gravity"]
    activation_gate = read_model["activation_gate"]
    worlds = read_model["worlds"]
    agent_presence = read_model["agent_presence"]

    lines = [
        "Helm State Read-Model v0",
        "",
        "Evidence:",
        (
            f"- Emitted state: `{helm_state['state']}` ({helm_state['state_family']}) "
            f"- {helm_state['meaning']}"
        ),
        (
            "- Authority flags: `runtime_authority=false`; "
            "`activation_allowed=false`; `backend_execution=false`."
        ),
        (
            "- Dynamic records: "
            f"`worlds={worlds}`; `agent_presence={agent_presence}`; "
            f"`strategic_gravity.supported={str(strategic_gravity['supported']).lower()}` "
            f"(`{strategic_gravity['reason']}`)."
        ),
        (
            f"- Runtime activation gate remains `{activation_gate['gate_state']}` "
            "with activation blocked."
        ),
        "",
        "Boundary:",
        "- Helm State v0 is a deterministic read-model for inspection, not runtime control.",
        "- It does not claim live runtime health, active agents, dynamic worlds, strategic gravity scoring, or peripheral HUD state.",
        "- It does not promote, extract, summarize, packetize, retrieve, activate context, or write SQLite.",
        "",
        "Blocked:",
        "- Runtime/module activation, backend execution, agent activation, broker wiring, customer deployment, external tools, and runtime mutation remain blocked.",
        "- Dynamic worlds, agent presence records, and strategic gravity scoring remain `not_yet_implemented` backend records.",
        "",
        "Next safe move:",
        f"- {read_model['next_safe_move']}",
    ]
    return "\n".join(lines)


def get_helm_state_operator_status():
    """Build compact Helm State status without recursively checking generated status."""
    try:
        from scripts.build_helm_state import build_helm_state
    except ImportError:
        from build_helm_state import build_helm_state

    return format_helm_state_operator_status(
        build_helm_state(run_generated_status_check=False)
    )


def format_helm_state_section(helm_state_operator_status):
    if not helm_state_operator_status:
        return []

    return [
        "",
        "## 5. Helm State",
        *helm_state_operator_status.splitlines(),
    ]


def get_world_domain_registry_operator_status():
    """Build compact World / Domain Registry status from the deterministic registry."""
    try:
        from scripts.build_world_domain_registry import (
            build_world_domain_registry,
            format_operator_world_domain_registry,
        )
    except ImportError:
        from build_world_domain_registry import (
            build_world_domain_registry,
            format_operator_world_domain_registry,
        )

    return format_operator_world_domain_registry(build_world_domain_registry())


def format_world_domain_registry_section(world_domain_registry_operator_status):
    if not world_domain_registry_operator_status:
        return []

    return [
        "",
        "## 6. World / Domain Registry",
        *world_domain_registry_operator_status.splitlines(),
    ]


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

    artifact_checkpoints = snapshot.get('artifact_checkpoint_receipts')
    if artifact_checkpoints is not None:
        lines.extend(
            format_module_atlas_artifact_checkpoint_section(
                artifact_checkpoints,
                expected_total=snapshot.get('artifact_checkpoint_expected_total'),
                bootstrap_command=snapshot.get(
                    'artifact_checkpoint_bootstrap_command',
                    MODULE_ATLAS_BOOTSTRAP_COMMAND,
                ),
            )
        )

    lines.extend(
        format_source_inventory_section(
            snapshot.get('source_inventory_operator_status')
        )
    )

    lines.extend(
        format_context_gates_section(
            snapshot.get('context_gates_operator_status')
        )
    )

    lines.extend(
        format_helm_state_section(
            snapshot.get('helm_state_operator_status')
        )
    )

    lines.extend(
        format_world_domain_registry_section(
            snapshot.get('world_domain_registry_operator_status')
        )
    )

    # Section 7: Truth Substrate Summary
    lines.extend([
        "",
        "## 7. Truth Substrate Summary",
        "Registry-governed canonical facts and source documents.",
    ])

    truth = snapshot.get("truth_substrate", {"status": "unavailable"})
    if truth["status"] == "available":
        m = truth["metrics"]
        f = m["facts"]
        r = m["registry"]
        rd = m["readiness"]
        gp = m.get("gateway_posture", {})
        dr = m.get("decision_receipts", {})
        lines.extend([
            f"- **Facts**: {f['total']} ({f['by_truth_status'].get('doctrine_reference', 0)} doctrine, {f['by_truth_status'].get('historical_checkpoint', 0)} historical)",
        ])
        if dr and dr.get("total", 0) > 0:
            lines.append(f"- **Truth Decision Receipts**: {dr['total']} recorded ({dr['by_status'].get('MODEL_ALLOWED_VERIFIED', 0)} VERIFIED, {dr['by_status'].get('MODEL_ALLOWED_UNCERTAIN', 0)} UNCERTAIN, {dr['by_status'].get('MODEL_BLOCKED', 0)} BLOCKED)")
        
        if gp:
            lines.extend([
                f"- **Candidate Truth Posture**: {gp.get('verified_candidate_facts', 0)} VERIFIED, {gp.get('uncertain_candidate_facts', 0)} UNCERTAIN, {gp.get('blocked_sources_count', 0)} BLOCKED sources",
                f"- **Runtime Authority**: {gp.get('runtime_authority', False)}",
            ])
        lines.extend([
            f"- **Coverage**: {r['present_sources']}/{r['total_sources']} SOURCE_REGISTRY documents",
            f"- **Readiness**: {rd['result']}",
            "",
            "> Truth substrate status is read-only, a read-model of candidate posture. Truth status describes candidate verification posture, not live runtime health, agent authority, or terminal gateway decisions.",
        ])
    else:
        lines.append(f"- Status: UNAVAILABLE ({truth.get('reason', 'unknown')})")

    lines.extend([
        "",
        "## 8. Active Lane & Doctrine",
        snapshot['active_lane'],
        "",
        "## 9. Tool & Surface Boundaries",
        "### Allowed Tools",
        snapshot['allowed_tools'],
        "",
        "### Forbidden Surfaces",
        snapshot['forbidden_surfaces'],
        "",
        "## 10. North Star",
        snapshot['north_star'],
        "",
        "## 11. Safety & Staleness",
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
    snapshot['artifact_checkpoint_receipts'] = get_artifact_checkpoint_receipts(
        artifact_paths=MODULE_ATLAS_ARTIFACT_PATHS
    )
    snapshot['artifact_checkpoint_expected_total'] = len(MODULE_ATLAS_ARTIFACT_PATHS)
    snapshot['artifact_checkpoint_bootstrap_command'] = MODULE_ATLAS_BOOTSTRAP_COMMAND
    snapshot['source_inventory_operator_status'] = get_source_inventory_operator_status()
    snapshot['context_gates_operator_status'] = get_context_gates_operator_status()
    snapshot['helm_state_operator_status'] = get_helm_state_operator_status()
    snapshot['world_domain_registry_operator_status'] = get_world_domain_registry_operator_status()

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
        print("")
        print(current_state_md)

if __name__ == "__main__":
    main()
