import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_action_payloads as payloads
import openclaw_request_processor as processor
import openclaw_request_router as router


FIXED_NOW = "2026-06-03T21:00:00+00:00"
LOCAL_PATH = ROOT / "generated/read_models/operator_action_payloads.json"
BRIDGE_PATH = Path("/mnt/e/openclaw/generated/read_models/operator_action_payloads.json")


def _payload() -> dict:
    return payloads.build_operator_action_payloads(generated_at=FIXED_NOW)


def _actions(payload: dict) -> list[dict]:
    return payload["action_payloads"]


def _find(payload: dict, *, action_id: str | None = None, label: str | None = None, action_type: str | None = None) -> dict:
    for action in _actions(payload):
        if action_id is not None and action["action_id"] != action_id:
            continue
        if label is not None and action["label"] != label:
            continue
        if action_type is not None and action["action_type"] != action_type:
            continue
        return action
    raise AssertionError(f"action not found: {action_id=} {label=} {action_type=}")


def _walk_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)


def _workbook_registration_request(path: Path) -> dict:
    request = {
        "request_type": "WORKBOOK_REGISTRATION_REQUEST_V0",
        "kind": "WORKBOOK_REGISTRATION_REQUEST",
        "request_id": "mission_control_workbook_registration_request_fixture",
        "idempotency_key": "workbook_registration_fixture",
        "payload_hash": "fixture_hash_workbook_registration",
        "created_at": FIXED_NOW,
        "source_surface": "mission_control",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "selected_local_path": "/Users/operator/Documents/Capital Hilton invoice workbook.xlsx",
        "authority_boundary": dict(payloads.AUTHORITY_BOUNDARY),
    }
    path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return request


def test_every_action_payload_has_required_render_fields_and_boundary():
    payload = _payload()

    assert payload["schema_version"] == payloads.SCHEMA_VERSION
    assert payload["status"] == payloads.READY_STATUS
    assert payload["action_payloads"]
    for action in _actions(payload):
        assert action["label"]
        assert action["action_type"] in payloads.ACTION_TYPES
        assert isinstance(action["enabled"], bool)
        assert isinstance(action["safe_to_render_button"], bool)
        assert action["business_action"] is False
        assert isinstance(action["payload"], dict)
        assert isinstance(action["proof_refs"], list)
        assert set(payloads.AUTHORITY_BOUNDARY) <= set(action["authority_boundary"])
        assert all(value is False for value in action["authority_boundary"].values())


def test_check_engine_action_routes_to_chief_diagnostic_with_no_repair_authority():
    action = _find(_payload(), action_id="chief_diagnostic.open")

    assert action["label"] == "Open Chief diagnostic"
    assert action["action_type"] == "navigate"
    assert action["target_world_ref"] == "system"
    assert action["target_thread_ref"] == "chief_diagnostic"
    assert action["payload"]["payload_ref"] == "generated/read_models/chief_check_engine_diagnostic_package.json"
    assert action["payload"]["environment_posture_ref"] == "generated/read_models/chief_check_engine_environment_posture.json"
    assert action["payload"]["repair_authority"] is False
    assert action["authority_boundary"]["repair_authority_allowed"] is False


def test_review_packet_open_and_decision_payloads_have_no_merge_or_push_authority():
    payload = _payload()
    open_action = _find(payload, label="Open review packet", action_type="navigate")
    decision_labels = {
        action["label"]
        for action in _actions(payload)
        if action["action_type"] == "review_decision"
    }

    assert open_action["target_world_ref"] == "build"
    assert open_action["payload"]["review_packet_id"].startswith("review_packet:")
    assert open_action["payload"]["merge_allowed"] is False
    assert open_action["payload"]["push_allowed"] is False
    assert open_action["authority_boundary"]["merge_allowed"] is False
    assert open_action["authority_boundary"]["push_allowed"] is False
    assert {"Approve for record", "Request rework", "Mark informational"} <= decision_labels
    for action in _actions(payload):
        if action["action_type"] == "review_decision":
            assert action["payload"]["request_type"] == "WORKROOM_REVIEW_DECISION_REQUEST_V0"
            assert action["payload"]["review_packet_id"].startswith("review_packet:")
            assert action["payload"]["merge_allowed"] is False
            assert action["payload"]["push_allowed"] is False
            assert action["payload"]["business_action_allowed"] is False


def test_business_development_followup_stages_draft_package_only_without_send():
    action = _find(_payload(), action_id="capital_hilton.proposal.stage_followup")

    assert action["label"] == "Stage proposal follow-up"
    assert action["action_type"] == "stage_package_request"
    assert action["target_world_ref"] == "business_development"
    assert action["target_thread_ref"] == "capital_hilton"
    assert action["payload"]["request_type"] == "WORKFLOW_PACKAGE_REQUEST_V0"
    assert action["payload"]["target_agent_refs"] == ["cassandra", "clara"]
    assert action["payload"]["email_send_allowed"] is False
    assert action["authority_boundary"]["email_send_allowed"] is False


def test_payment_proof_attach_action_is_enabled_and_does_not_mutate_ledger():
    payload = _payload()
    action = _find(payload, action_id="capital_hilton.payment.record_proof")
    fallback = _find(payload, action_id="capital_hilton.payment.open_finance")

    assert action["action_type"] == "record_payment_proof_intake"
    assert action["enabled"] is True
    assert action["label"] == "Attach payment evidence"
    assert action["controller_event_type"] == "attach_proof"
    assert action["control_scope"] == "lane"
    assert action["text_response_preferred"] is True
    assert action["payload"]["artifact_required"] is True
    assert action["payload"]["ledger_mutation_allowed"] is False
    assert action["payload"]["ledger_posting_allowed"] is False
    assert action["authority_boundary"]["ledger_posting_allowed"] is False
    assert fallback["label"] == "Open Finance / Capital Hilton"
    assert fallback["action_type"] == "navigate"


def test_capital_hilton_payment_watch_has_lane_level_text_controls():
    payload = _payload()
    ask = _find(payload, action_id="capital_hilton.payment.ask_why")
    advance = _find(payload, action_id="capital_hilton.payment.advance_objective")
    attach = _find(payload, action_id="capital_hilton.payment.record_proof")

    assert ask["action_type"] == "system_question"
    assert ask["controller_event_type"] == "ask_why"
    assert advance["action_type"] == "objective_advancement"
    assert advance["controller_event_type"] == "advance_objective"
    assert advance["payload"]["next_safe_controller_event"] == "attach_proof"
    assert attach["controller_event_type"] == "attach_proof"
    for action in (ask, advance, attach):
        assert action["target_world_ref"] == "finance"
        assert action["target_thread_ref"] == "capital_hilton"
        assert action["control_scope"] == "lane"
        assert action["text_response_preferred"] is True
        assert action["business_action"] is False
        assert all(value is False for value in action["authority_boundary"].values())


def test_workbook_registration_payload_and_explicit_request_processor_route(tmp_path, capsys):
    payload = _payload()
    action = _find(payload, action_id="client_invoice_workbook.register")
    request_path = tmp_path / "mission_control_workbook_registration_request_fixture.json"
    request = _workbook_registration_request(request_path)
    export_root = tmp_path / "read_models"

    assert action["label"] == "Register workbook"
    assert action["action_type"] == "workbook_registration"
    assert action["payload"]["request_type"] == "WORKBOOK_REGISTRATION_REQUEST_V0"
    assert action["payload"]["source_surface"] == "mission_control"
    assert action["payload"]["workbook_body_read_allowed"] is False
    assert action["payload"]["spreadsheet_cell_read_allowed"] is False

    envelope, decision = router.route_request(
        request,
        source_request_filename=request_path.name,
        filename_request_family="WORKBOOK_REGISTRATION_REQUEST",
    )
    assert envelope.request_kind == "WORKBOOK_REGISTRATION_REQUEST"
    assert request["request_type"] == "WORKBOOK_REGISTRATION_REQUEST_V0"
    assert decision.route_status == "ROUTE_MATCHED"
    assert decision.selected_handler_id == "client_invoice_workbook_registry.register_workbook"

    assert processor.main(
        [
            "--file",
            str(request_path),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    response = json.loads(capsys.readouterr().out)
    registry_payload = json.loads((export_root / "client_invoice_workbook_registry.json").read_text(encoding="utf-8"))

    assert response["response_kind"] == "CLIENT_INVOICE_WORKBOOK_REGISTRATION"
    assert response["request_type"] == "WORKBOOK_REGISTRATION_REQUEST"
    assert response["terminal"] is True
    assert response["detail_disclosure"]["client_invoice_workbook_registry"]["registration_readback"]["status"] == "WORKBOOK_REFERENCE_CAPTURED"
    assert response["machine_proof"]["workbook_body_read_performed"] is False
    assert response["machine_proof"]["spreadsheet_cell_read_performed"] is False
    assert registry_payload["registration_request"]["local_path_ref"].startswith("path_ref:metadata_request:")
    assert registry_payload["machine_proof"]["workbook_body_read_performed"] is False


def test_guardian_gate_actions_are_explain_open_or_stage_only():
    payload = _payload()
    guardian_actions = [action for action in _actions(payload) if action["action_id"].startswith("guardian_gate.")]
    by_gate: dict[str, set[str]] = {}

    assert guardian_actions
    for action in guardian_actions:
        assert action["action_type"] in {"explain_gate", "navigate", "stage_package_request"}
        assert action["business_action"] is False
        assert action["authority_boundary"]["email_send_allowed"] is False
        assert action["authority_boundary"]["portal_submit_allowed"] is False
        assert action["authority_boundary"]["ledger_posting_allowed"] is False
        gate_ref = action["payload"]["gate_ref"]
        by_gate.setdefault(gate_ref, set()).add(action["action_type"])
    for gate_ref, action_types in by_gate.items():
        assert {"explain_gate", "navigate"} <= action_types, gate_ref


def test_suggested_helm_questions_all_have_system_question_payloads():
    payload = _payload()
    question_actions = [action for action in _actions(payload) if action["action_id"].startswith("helm_question.")]
    surface = json.loads((ROOT / "generated/read_models/helm_actionability_surface.json").read_text(encoding="utf-8"))

    assert len(question_actions) == len(surface["suggested_questions"])
    for action in question_actions:
        assert action["action_type"] == "system_question"
        assert action["payload"]["question_text"]
        assert action["payload"]["precomputed_answer_ref"]
        assert action["payload"]["target_lane"]["target_world_ref"]
        assert action["payload"]["target_lane"]["target_thread_ref"]


def test_generated_action_payloads_json_parse_and_bridge_match():
    local = json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
    bridge = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))

    assert local == bridge
    assert local["schema_version"] == payloads.SCHEMA_VERSION
    assert local["status"] == payloads.READY_STATUS
    assert local["action_payload_count"] == len(local["action_payloads"])


def test_unsafe_true_grant_scan_clean():
    payload = _payload()
    unsafe_hits = [
        key
        for key, value in _walk_values(payload)
        if key in payloads.UNSAFE_TRUE_KEYS and value is True
    ]

    assert unsafe_hits == []
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True
