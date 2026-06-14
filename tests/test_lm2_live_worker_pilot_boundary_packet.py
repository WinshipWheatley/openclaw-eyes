import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm2_live_worker_pilot_boundary_packet as boundary
import proof_bundle_builder as bundles
import proof_to_response_runtime as runtime
import proof_to_response_schema_adapter as schema_adapter


FIXED_NOW = "2026-06-08T10:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / bundles.FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME, {"status": bundles.FRESHNESS_TRACE_READY_STATUS})
    _write_json(root / bundles.REDACTION_STATUS_JSON_EXPORT_NAME, {"status": bundles.REDACTION_READY_STATUS})
    _write_json(root / "context_freshness_decision_trace_gate.json", {"status": "CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY"})
    _write_json(root / schema_adapter.STATUS_JSON_EXPORT_NAME, {"status": schema_adapter.READY_STATUS})
    _write_json(root / runtime.STATUS_JSON_EXPORT_NAME, {"status": runtime.READY_STATUS})
    _write_json(root / "local_model_selection_for_proof_response.json", {"status": "LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY"})
    _write_json(root / "local_lm_proof_response_retry_operator_approval.json", {"status": "LOCAL_LM_PROOF_RESPONSE_RETRY_OPERATOR_APPROVAL_READY"})
    _write_json(root / "goldilocks_gate_calibration.json", {"status": "GOLDILOCKS_GATE_CALIBRATION_READY"})
    _write_json(root / "universal_receipt_envelope_status.json", {"status": "UNIVERSAL_RECEIPT_ENVELOPE_READY"})
    _write_json(root / "operator_controller_protocol.json", {"status": "OPERATOR_CONTROLLER_PROTOCOL_READY"})
    return root


def _read_model(tmp_path: Path) -> dict:
    return boundary.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "lm2_boundary.sqlite",
        generated_at=FIXED_NOW,
    )


def _packet(read_model: dict) -> dict:
    return read_model["boundary_packet"]


def _receipt_refs(read_model: dict) -> set[str]:
    refs = set()
    for phase in ("before", "during", "after"):
        refs.update(read_model["required_receipts"][phase])
    return refs


def test_packet_is_pending_operator_review(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)

    assert read_model["status"] == boundary.READY_STATUS
    assert packet["status"] == "pending_operator_review"
    assert read_model["packet_status"] == "pending_operator_review"
    assert read_model["machine_proof"]["review_only"] is True


def test_invocation_allowed_false(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)

    assert packet["invocation_allowed"] is False
    assert read_model["invocation_allowed"] is False
    assert packet["authority_boundary"]["invocation_allowed"] is False
    assert packet["authority_boundary"]["model_invocation_allowed"] is False


def test_worker_spawn_allowed_false(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)

    assert packet["worker_spawn_allowed"] is False
    assert read_model["worker_spawn_allowed"] is False
    assert packet["authority_boundary"]["worker_spawn_allowed"] is False
    assert packet["implementation_boundary"]["worker_spawn_performed"] is False


def test_proof_bundle_allowed_false(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)

    assert packet["proof_bundle_allowed"] is False
    assert read_model["proof_bundle_allowed"] is False
    assert packet["authority_boundary"]["proof_bundle_allowed"] is False
    assert packet["implementation_boundary"]["proof_bundle_sent"] is False


def test_tool_authority_false(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["authority_boundary"]["tool_authority"] is False
    assert packet["authority_boundary"]["tool_execution_allowed"] is False
    assert packet["implementation_boundary"]["tool_execution_performed"] is False
    assert packet["worker_capabilities"]["model_tool_access"] is False


def test_business_action_authority_false(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["authority_boundary"]["business_action_authority"] is False
    assert packet["authority_boundary"]["business_action_allowed"] is False
    assert packet["implementation_boundary"]["ledger_mutation_performed"] is False
    assert packet["implementation_boundary"]["paid_marking_performed"] is False


def test_external_provider_false(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["authority_boundary"]["external_provider_connect_allowed"] is False
    assert packet["implementation_boundary"]["external_provider_used"] is False
    assert packet["worker_capabilities"]["external_provider_allowed"] is False


def test_exactly_one_pilot_lane_finance_capital_hilton(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)

    assert read_model["lane"] == "finance/capital_hilton"
    assert packet["pilot_scope"]["lane"] == "finance/capital_hilton"
    assert packet["pilot_scope"]["world_ref"] == "finance"
    assert packet["pilot_scope"]["thread_ref"] == "capital_hilton"
    assert packet["pilot_scope"]["attempt_limit"] == 1


def test_all_required_receipts_listed(tmp_path):
    read_model = _read_model(tmp_path)
    refs = _receipt_refs(read_model)

    for receipt in boundary.RECEIPTS_REQUIRED_BEFORE + boundary.RECEIPTS_REQUIRED_DURING + boundary.RECEIPTS_REQUIRED_AFTER:
        assert receipt in refs
    assert "operator_approval_receipt" in read_model["required_receipts"]["before"]
    assert "worker_started_receipt" in read_model["required_receipts"]["during"]
    assert "verifier_pass_fail_receipt" in read_model["required_receipts"]["after"]
    assert "no_business_action_receipt" in read_model["required_receipts"]["after"]


def test_stop_conditions_include_required_blocks(tmp_path):
    packet = _packet(_read_model(tmp_path))
    stops = set(packet["stop_conditions"])

    assert "model_returns_non_json" in stops
    assert "model_claims_paid_sent_submitted_or_executed" in stops
    assert "model_promises_protected_action" in stops
    assert "context_freshness_stale_superseded_or_unknown" in stops
    assert "model_attempts_tool_use" in stops
    assert "model_exceeds_one_attempt" in stops


def test_worker_input_forbids_private_and_authority_fields(tmp_path):
    worker_input = _packet(_read_model(tmp_path))["worker_package_input"]
    forbidden = set(worker_input["forbidden"])

    assert "raw_financial_proof" in forbidden
    assert "bank_or_account_details" in forbidden
    assert "credentials_or_tokens" in forbidden
    assert "operator_device_session_verification_secrets" in forbidden
    assert "raw_ocr_or_artifact_text" in forbidden
    assert "workbook_bodies" in forbidden
    assert "email_bodies" in forbidden
    assert "ledger_bodies" in forbidden
    assert "authority_granted_fields" in forbidden


def test_worker_capabilities_stop_at_boundary(tmp_path):
    capabilities = _packet(_read_model(tmp_path))["worker_capabilities"]

    assert capabilities["allowed"] == [
        "read_provided_redacted_proof_bundle",
        "draft_one_json_proof_to_response_candidate",
        "return_candidate_to_verifier",
        "stop",
    ]
    assert "file_system_mutation" in capabilities["forbidden"]
    assert "shell_commands" in capabilities["forbidden"]
    assert "repeated_invocations" in capabilities["forbidden"]


def test_expected_response_is_payment_watch_text(tmp_path):
    expected = _packet(_read_model(tmp_path))["expected_response"]

    assert expected["headline"] == "Payment evidence needed"
    assert "Coupa is processing" in expected["body"]
    assert "can't mark this paid" in expected["body"]
    assert "ledger stays untouched" in expected["body"]
    assert expected["next_step"] == "Attach payment evidence."


def test_operator_decision_options_are_review_only(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["operator_decision_options"] == [
        "approve_one_time_lm2_worker_pilot",
        "request_more_detail",
        "reject_for_now",
    ]
    assert packet["invocation_allowed"] is False
    assert packet["worker_spawn_allowed"] is False


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert boundary.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_wiki_and_sqlite(tmp_path):
    sqlite_path = tmp_path / "system_knowledge" / "lm2_boundary.sqlite"
    result = boundary.export_lm2_live_worker_pilot_boundary_packet(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "LM2 Live Worker Pilot Boundary Packet.md",
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")
    with sqlite3.connect(sqlite_path) as conn:
        sqlite_count = conn.execute("SELECT COUNT(*) FROM lm2_worker_pilot_boundary_receipts").fetchone()[0]

    assert result["status"] == boundary.READY_STATUS
    assert result["packet_status"] == "pending_operator_review"
    assert result["invocation_allowed"] == "false"
    assert result["worker_spawn_allowed"] == "false"
    assert result["proof_bundle_allowed"] == "false"
    assert local == bridge
    assert sqlite_count == len(local["required_receipt_rows"])
    assert sqlite_count == local["sqlite_row_count"]
    assert boundary.unsafe_true_grants(local) == []
    assert wiki.startswith("# LM2 Live Worker Pilot Boundary Packet")
