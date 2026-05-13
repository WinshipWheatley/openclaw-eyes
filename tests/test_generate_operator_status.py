import os
import pytest
import sys
import sqlite3
from unittest.mock import patch, MagicMock
from scripts.generate_operator_status import (
    MODULE_ATLAS_ARTIFACT_PATHS,
    MODULE_ATLAS_BOOTSTRAP_COMMAND,
    generate_current_state,
    generate_next_actions,
    get_source_inventory_operator_status,
)

SOURCE_INVENTORY_STATUS = """Bounded Source Inventory v0

Evidence:
- 13 explicit allowlisted source records are known as metadata-only context.
- Records carry path, type, size, Git status when available, sensitivity label, authority label, and inclusion reason.
- Source groups: operator_status_script=1, validation_test=1.
- Body ingest is `false` for every record.

Boundary:
- Inventory is allowlist-only; it does not scan the whole repo or hard drives.
- `body_ingested=false`; SQLite is untouched; records are source metadata, not source bodies.
- Authority labels describe documentation/receipt/validation posture only; they do not grant runtime authority.

Blocked:
- 8 no-go boundary examples are represented without stat, scan, or body read.
- Secrets, private data, legal, tax, CPA/finance, AppData, and runtime logs remain outside source inventory.
- Blocked examples: `.chief.env`; `.google-secrets/`; `Private/`.
- No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated.

Next safe move:
- Use `--format json` as metadata-only agent context; promote any body access or accepted working context in a separate approved lane."""


def _extract_section(output, header):
    lines = output.splitlines()
    start = lines.index(header)
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


@pytest.fixture
def mock_snapshot():
    return {
        "timestamp": "2026-05-10T10:00:00",
        "where_are_we": {
            "git_head": "0de27a6f",
            "git_branch": "main",
            "git_status": "Clean"
        },
        "ledger_info": {
            "status": "active",
            "event_count": 2,
            "has_snapshot_receipt": True
        },
        "confirmed_current": [
            "Git HEAD: 0de27a6 feat(operator)",
            "Ledger Status: active",
            "Active Handoff: context"
        ],
        "recent_proofs": [
            "2026-05-10 09:00 [PASS] static_contract_check exit=0 head=0de27a6f",
            "2026-05-10 09:05 [GATE] [SQLITE_VERIFIED] GATE PASS for agent.action_intent_packet (No Execution)",
            "2026-05-10 09:10 [APPROVAL_RECORD] [SQLITE_VERIFIED] APPROVED: Approved outreach to Bob (No Execution)",
            "2026-05-10 09:15 [APPROVAL_REQUEST] [SQLITE_VERIFIED] Requesting approval for album creation (No Decision/No Execution)",
            "2026-05-10 09:20 [PII_VAULT] [SQLITE_VERIFIED] Vault reference recorded for: test (Redacted Metadata Only)"
        ],
        "strongest_clean_proof": "[PASS] static_contract_check head=0de27a6f",
        "active_lane": "Hardening the spine.",
        "allowed_tools": "Reading files.",
        "forbidden_surfaces": "Secrets.",
        "north_star": "Lighter life.",
        "truth_substrate": {
            "status": "available",
            "metrics": {
                "facts": {"total": 83, "by_truth_status": {"doctrine_reference": 71, "historical_checkpoint": 12}},
                "registry": {"total_sources": 9, "present_sources": 9},
                "readiness": {"result": "READY"}
            }
        },
        "next_safe_move": "Next move.",
        "visible_road_horizon": {
            "visible_moves": ["Move 1", "Move 2"],
            "branch_after": "Proof",
            "unsafe_beyond": "Unsafe"
        },
        "source_inventory_operator_status": SOURCE_INVENTORY_STATUS,
    }

def test_generate_current_state(mock_snapshot):
    output = generate_current_state(mock_snapshot)
    assert "# GENERATED CURRENT STATE" in output
    # Volatile timestamp should NOT be in the output string
    assert "2026-05-10T10:00:00" not in output
    # The snapshot's head SHA (0de27a6f) is now allowed IF it appears in a proof
    assert "static_contract_check" in output
    assert "0de27a6f" in output
    assert "Hardening the spine." in output
    assert "Lighter life." in output
    assert "Runtime Health" in output
    assert "## 2. Recent Verification Receipts" in output
    assert "Strongest recent clean proof: [PASS] static_contract_check head=0de27a6f" in output
    assert "[PASS]" in output
    assert "2026-05-10 09:00" in output
    assert "[GATE] [SQLITE_VERIFIED] GATE PASS for agent.action_intent_packet (No Execution)" in output
    assert "[APPROVAL_RECORD] [SQLITE_VERIFIED] APPROVED: Approved outreach to Bob (No Execution)" in output
    assert "[APPROVAL_REQUEST] [SQLITE_VERIFIED] Requesting approval for album creation (No Decision/No Execution)" in output
    assert "[PII_VAULT] [SQLITE_VERIFIED] Vault reference recorded for: test (Redacted Metadata Only)" in output

    # Truth Substrate Summary check
    assert "## 4. Truth Substrate Summary" in output
    assert "**Facts**: 83 (71 doctrine, 12 historical)" in output
    assert "**Coverage**: 9/9 SOURCE_REGISTRY documents" in output
    assert "READY" in output
    assert "Truth substrate status is read-only" in output
    assert "SECRET_FACT_TEXT" not in output

    # Ensure lines are safe and do not imply execution/completion
    for keyword in ["GATE", "APPROVAL_RECORD", "APPROVAL_REQUEST"]:
        lines = [line for line in output.splitlines() if keyword in line]
        assert len(lines) > 0
        line = lines[0].lower()
        for word in ["executed", "completed", "success", "done"]:
            # 'approved' is allowed in the summary text for APPROVAL_RECORD but not as a status label
            # However, for safety, we check if it implies 'executed'
            assert word not in line, f"Misleading word '{word}' found in {keyword} receipt line: {line}"


def test_generate_current_state_includes_source_inventory_section(mock_snapshot):
    output = generate_current_state(mock_snapshot)
    section = _extract_section(output, "## 3. Source Inventory")

    assert "Bounded Source Inventory v0" in section
    assert "Evidence:" in section
    assert "Boundary:" in section
    assert "Blocked:" in section
    assert "Next safe move:" in section
    assert section.index("Evidence:") < section.index("Boundary:")
    assert section.index("Boundary:") < section.index("Blocked:")
    assert section.index("Blocked:") < section.index("Next safe move:")
    assert "metadata-only context" in section
    assert "allowlist-only" in section
    assert "`body_ingested=false`" in section
    assert "source metadata, not source bodies" in section
    assert "do not grant runtime authority" in section
    assert "No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated." in section
    assert "[SOURCE_INVENTORY]" not in section
    assert '"records"' not in section

    section_lower = section.lower()
    for forbidden_claim in [
        "runtime ready",
        "runtime-ready",
        "module active",
        "modules active",
        "agent wired",
        "broker connected",
        "customer deployment active",
        "live runtime health",
    ]:
        assert forbidden_claim not in section_lower


def test_source_inventory_status_uses_existing_metadata_only_read_model():
    output = get_source_inventory_operator_status()

    assert "Bounded Source Inventory v0" in output
    assert "metadata-only context" in output
    assert "`body_ingested=false`" in output
    assert "SQLite is untouched" in output
    assert "No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated." in output


def test_generate_current_state_no_proofs(mock_snapshot):
    mock_snapshot["recent_proofs"] = []
    mock_snapshot["strongest_clean_proof"] = None
    output = generate_current_state(mock_snapshot)
    assert "## 2. Recent Verification Receipts" in output
    assert "No recent verification receipts found." in output
    assert "Strongest recent clean proof" not in output

def test_generate_current_state_missing_module_atlas_receipts_is_operator_readable(mock_snapshot):
    mock_snapshot["artifact_checkpoint_receipts"] = []
    mock_snapshot["artifact_checkpoint_expected_total"] = len(MODULE_ATLAS_ARTIFACT_PATHS)
    mock_snapshot["artifact_checkpoint_bootstrap_command"] = MODULE_ATLAS_BOOTSTRAP_COMMAND

    output = generate_current_state(mock_snapshot)

    assert "### Module Atlas Artifact Checkpoints" in output
    assert "no local Module Atlas checkpoint receipts found for 6 committed docs/code artifacts" in output
    assert f"run `{MODULE_ATLAS_BOOTSTRAP_COMMAND}`" in output
    assert "recorded checkpoint only; not runtime authority" in output
    assert "No full Markdown/code body is ingested" in output
    assert "| Artifact | Receipt Time | Checkpoint | Authority Boundary |" not in output
    output_lower = output.lower()
    for phrase in [
        "runtime ready",
        "module active",
        "broker connected",
        "agent wired",
        "customer deployment active",
    ]:
        assert phrase not in output_lower

def test_generate_next_actions(mock_snapshot):
    output = generate_next_actions(mock_snapshot)
    assert "# GENERATED NEXT ACTIONS" in output
    assert "Next move." in output
    assert "Move 1" in output
    assert "Move 2" in output
    assert "[DONE] Orientation Snapshot Receipt recorded to Ledger" in output
    assert "Unsafe" in output

def test_generate_next_actions_no_receipt(mock_snapshot):
    mock_snapshot["ledger_info"]["has_snapshot_receipt"] = False
    output = generate_next_actions(mock_snapshot)
    assert "[TODO] Record initial Orientation Snapshot Receipt" in output

@patch("scripts.generate_operator_status.get_source_inventory_operator_status")
@patch("scripts.generate_operator_status.get_artifact_checkpoint_receipts")
@patch("scripts.generate_operator_status.get_recent_proof_receipts")
@patch("scripts.generate_operator_status.get_orientation_snapshot")
@patch("scripts.generate_operator_status.open", new_callable=MagicMock)
@patch("argparse.ArgumentParser.parse_args")
def test_main_write(mock_args, mock_open, mock_get, mock_get_proofs, mock_get_artifacts, mock_get_source_inventory, mock_snapshot):
    from scripts.generate_operator_status import main
    mock_get.return_value = mock_snapshot
    mock_get_proofs.return_value = {"list": mock_snapshot["recent_proofs"], "strongest_clean": mock_snapshot["strongest_clean_proof"]}
    mock_get_artifacts.return_value = []
    mock_get_source_inventory.return_value = SOURCE_INVENTORY_STATUS
    mock_args.return_value = MagicMock(write=True, check=False)

    main()

    assert mock_open.call_count == 2
    mock_open.assert_any_call("Operator/GENERATED_CURRENT_STATE.md", "w")
    mock_open.assert_any_call("Operator/GENERATED_NEXT_ACTIONS.md", "w")

def test_get_recent_receipts_integration(tmp_path):
    from scripts.generate_operator_status import get_recent_proof_receipts
    from business_ops_ledger import (
        init_business_ops_ledger,
        append_event,
        record_action_intent_gate_receipt,
        record_approval_log_entry,
        record_approval_request_record
    )

    db_path = str(tmp_path / "test_visibility.sqlite")
    init_business_ops_ledger(db_path)

    # Record a test proof
    append_event(
        event_id="tpr_1",
        event_type="test_proof_receipt",
        actor="test_actor",
        operator_visible_summary="PASS test_cmd exit=0 head=abc1234 dirty=false",
        db_path=db_path
    )

    # Record a gate receipt
    record_action_intent_gate_receipt(
        packet_id="p-456",
        packet_type="agent.action_intent_packet",
        gate_result="PASS",
        evaluation_summary="GATE PASS for agent.action_intent_packet",
        db_path=db_path
    )

    # Record an approval log entry
    record_approval_log_entry(
        packet_id="p-789",
        packet_type="chief.approval_decision_packet",
        approval_verdict="APPROVED",
        approval_summary="Approved outreach to Bob",
        approver_name="Chief",
        db_path=db_path
    )

    # Record an approval request record
    record_approval_request_record(
        packet_id="p-101",
        packet_type="guardian.approval_request_packet",
        approval_id="app-123",
        approval_request_summary="Requesting approval for album creation",
        requester_agent="Chief",
        db_path=db_path
    )

    # No need to patch os.path.exists or sqlite3.connect anymore
    results = get_recent_proof_receipts(limit=5, db_path=db_path)

    proofs = results["list"]
    assert len(proofs) == 4

    # Verify the gate receipt is formatted correctly
    gate_entry = [p for p in proofs if "GATE PASS" in p][0]
    assert "[GATE] [SQLITE_VERIFIED]" in gate_entry
    assert "(No Execution)" in gate_entry
    assert "GATE PASS for agent.action_intent_packet" in gate_entry

    # Verify the approval record is formatted correctly
    approval_entry = [p for p in proofs if "Approved outreach to Bob" in p][0]
    assert "[APPROVAL_RECORD] [SQLITE_VERIFIED]" in approval_entry
    assert "(No Execution)" in approval_entry
    assert "APPROVED: Approved outreach to Bob" in approval_entry

    # Verify the approval request is formatted correctly
    request_entry = [p for p in proofs if "Requesting approval for album creation" in p][0]
    assert "[APPROVAL_REQUEST] [SQLITE_VERIFIED]" in request_entry
    assert "(No Decision/No Execution)" in request_entry
    assert "Requesting approval for album creation" in request_entry

    # Verify the test proof is still there
    proof_entry = [p for p in proofs if "[PASS]" in p and "test_cmd" in p][0]
    assert "exit=0" in proof_entry
    assert "abc1234" in proof_entry

@patch("scripts.generate_operator_status.get_source_inventory_operator_status")
@patch("scripts.generate_operator_status.get_artifact_checkpoint_receipts")
@patch("scripts.generate_operator_status.get_recent_proof_receipts")
@patch("scripts.generate_operator_status.get_orientation_snapshot")
@patch("os.path.exists")
@patch("scripts.generate_operator_status.open", new_callable=MagicMock)
@patch("argparse.ArgumentParser.parse_args")
def test_main_check_ok(mock_args, mock_open, mock_exists, mock_get, mock_get_proofs, mock_get_artifacts, mock_get_source_inventory, mock_snapshot):
    from scripts.generate_operator_status import main, generate_current_state, generate_next_actions, DISCLAIMER
    mock_get.return_value = mock_snapshot
    mock_get_proofs.return_value = {"list": mock_snapshot["recent_proofs"], "strongest_clean": mock_snapshot["strongest_clean_proof"]}
    mock_get_artifacts.return_value = []
    mock_get_source_inventory.return_value = SOURCE_INVENTORY_STATUS
    mock_args.return_value = MagicMock(write=False, check=True)
    mock_exists.return_value = True

    # Ensure snapshot has the proofs for comparison
    snapshot_with_proofs = mock_snapshot.copy()
    snapshot_with_proofs["recent_proofs"] = mock_snapshot["recent_proofs"]
    snapshot_with_proofs["strongest_clean_proof"] = mock_snapshot["strongest_clean_proof"]
    snapshot_with_proofs["artifact_checkpoint_receipts"] = []
    snapshot_with_proofs["artifact_checkpoint_expected_total"] = len(MODULE_ATLAS_ARTIFACT_PATHS)
    snapshot_with_proofs["artifact_checkpoint_bootstrap_command"] = MODULE_ATLAS_BOOTSTRAP_COMMAND

    curr_content = DISCLAIMER + "\n" + generate_current_state(snapshot_with_proofs)
    next_content = DISCLAIMER + "\n" + generate_next_actions(snapshot_with_proofs)

    # Mock reading the files
    mock_open.return_value.__enter__.return_value.read.side_effect = [curr_content, next_content]

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_not_called()

@patch("scripts.generate_operator_status.get_source_inventory_operator_status")
@patch("scripts.generate_operator_status.get_artifact_checkpoint_receipts")
@patch("scripts.generate_operator_status.get_recent_proof_receipts")
@patch("scripts.generate_operator_status.get_orientation_snapshot")
@patch("os.path.exists")
@patch("scripts.generate_operator_status.open", new_callable=MagicMock)
@patch("argparse.ArgumentParser.parse_args")
def test_main_check_stale(mock_args, mock_open, mock_exists, mock_get, mock_get_proofs, mock_get_artifacts, mock_get_source_inventory, mock_snapshot):
    from scripts.generate_operator_status import main
    mock_get.return_value = mock_snapshot
    mock_get_proofs.return_value = {"list": mock_snapshot["recent_proofs"], "strongest_clean": mock_snapshot["strongest_clean_proof"]}
    mock_get_artifacts.return_value = []
    mock_get_source_inventory.return_value = SOURCE_INVENTORY_STATUS
    mock_args.return_value = MagicMock(write=False, check=True)
    mock_exists.return_value = True

    # Mock reading different content
    mock_open.return_value.__enter__.return_value.read.return_value = "stale content"

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_called_with(1)
