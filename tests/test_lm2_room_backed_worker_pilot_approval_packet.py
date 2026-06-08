import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm2_live_worker_pilot_boundary_packet as boundary
import lm2_room_backed_worker_pilot_approval_packet as approval


FIXED_NOW = "2026-06-08T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    for spec in approval.PRECONDITIONS.values():
        _write_json(root / spec["filename"], {"status": spec["accepted_statuses"][0]})
    return root


def _read_model(tmp_path: Path) -> dict:
    return approval.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def test_packet_is_pending_operator_review(tmp_path):
    read_model = _read_model(tmp_path)
    packet = read_model["approval_packet"]

    assert read_model["status"] == approval.READY_STATUS
    assert read_model["packet_status"] == "pending_operator_review"
    assert packet["status"] == "pending_operator_review"
    assert packet["approval_packet_id"] == approval.APPROVAL_PACKET_ID
    assert "This packet is not approval." in packet["rules"]
    assert "This packet does not run LM2." in packet["rules"]


def test_invocation_worker_spawn_and_proof_bundle_false(tmp_path):
    read_model = _read_model(tmp_path)
    packet = read_model["approval_packet"]

    assert packet["invocation_allowed"] is False
    assert packet["worker_spawn_allowed"] is False
    assert packet["proof_bundle_allowed"] is False
    assert read_model["machine_proof"]["invocation_disallowed"] is True
    assert read_model["machine_proof"]["worker_spawn_disallowed"] is True
    assert read_model["machine_proof"]["proof_bundle_disallowed"] is True


def test_project_room_refs_are_present(tmp_path):
    packet = _read_model(tmp_path)["approval_packet"]

    for ref in (
        "project_room_ref",
        "source_inventory_ref",
        "conflict_log_ref",
        "missing_context_ref",
        "duplicate_report_ref",
        "decision_trace_ref",
        "freshness_gate_ref",
        "compaction_policy_ref",
        "redacted_proof_bundle_ref",
        "authority_boundary_ref",
        "receipt_requirement_ref",
    ):
        assert packet[ref]
    assert packet["project_room_ref"] == "finance_capital_hilton_payment_watch"


def test_source_conflict_missing_context_and_decision_trace_refs_present(tmp_path):
    packet = _read_model(tmp_path)["approval_packet"]

    assert packet["source_inventory_ref"] == "source_inventory:finance_capital_hilton_payment_watch"
    assert packet["conflict_log_ref"] == "conflict_log:finance_capital_hilton_payment_watch"
    assert packet["missing_context_ref"] == "missing_context:finance_payment_evidence"
    assert packet["duplicate_report_ref"] == "version_family:finance_payment_watch"
    assert packet["decision_trace_ref"] == "decision_trace:finance_capital_hilton_payment_watch"


def test_lm2_forbidden_inputs_include_required_private_material(tmp_path):
    forbidden = set(_read_model(tmp_path)["approval_packet"]["must_not_receive"])

    assert "raw_financial_proof" in forbidden
    assert "credentials_or_tokens" in forbidden
    assert "operator_device_session_verification_secrets" in forbidden
    assert "raw_ocr_or_artifact_text" in forbidden
    assert "workbook_email_or_ledger_bodies" in forbidden
    assert "stale_source_as_current_truth" in forbidden
    assert "authority_granted_fields" in forbidden
    assert "duplicate_versions_as_equal_evidence" in forbidden
    assert "missing_context_as_permission_to_invent" in forbidden


def test_tool_business_and_action_authority_remain_false(tmp_path):
    read_model = _read_model(tmp_path)
    authority = read_model["approval_packet"]["authority_boundary"]

    assert authority["tool_authority"] is False
    assert authority["tool_authority_allowed"] is False
    assert authority["business_action_authority"] is False
    assert authority["business_action_allowed"] is False
    assert authority["email_send_allowed"] is False
    assert authority["coupa_allowed"] is False
    assert authority["ledger_mutation_allowed"] is False
    assert authority["workbook_mutation_allowed"] is False
    assert authority["pdf_export_allowed"] is False
    assert authority["paid_marking_allowed"] is False
    assert read_model["machine_proof"]["tool_authority_false"] is True
    assert read_model["machine_proof"]["business_action_authority_false"] is True


def test_stop_conditions_include_required_blocks(tmp_path):
    stop_conditions = set(_read_model(tmp_path)["approval_packet"]["stop_conditions"])

    assert "freshness_stale_superseded_or_unknown" in stop_conditions
    assert "model_returns_non_json" in stop_conditions
    assert "model_claims_paid_sent_submitted_or_executed" in stop_conditions
    assert "model_promises_protected_action" in stop_conditions
    assert "model_attempts_tool_use" in stop_conditions
    assert "model_exceeds_one_attempt" in stop_conditions


def test_operator_decision_options_are_review_only(tmp_path):
    options = _read_model(tmp_path)["approval_packet"]["operator_decision_options"]

    assert options == list(boundary.ROOM_BACKED_OPERATOR_DECISION_OPTIONS)
    assert "approve_one_time_room_backed_lm2_worker_pilot" in options
    assert "request_more_detail" in options
    assert "reject_for_now" in options
    assert "invoke_lm2" not in options
    assert "spawn_worker" not in options


def test_expected_worker_output_target_matches_payment_watch_contract(tmp_path):
    expected = _read_model(tmp_path)["approval_packet"]["expected_worker_output_target"]

    assert expected == boundary.ROOM_BACKED_EXPECTED_RESPONSE
    assert expected["headline"] == "Payment evidence needed"
    assert "paid_false" in expected["claimed_facts"]
    assert expected["requested_controls"] == ["attach_proof"]


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert approval.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = approval.export_lm2_room_backed_worker_pilot_approval_packet(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "LM2 Room Backed Worker Pilot Approval Packet.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == approval.READY_STATUS
    assert local == bridge
    assert approval.unsafe_true_grants(local) == []
    assert wiki.startswith("# LM2 Room Backed Worker Pilot Approval Packet")
