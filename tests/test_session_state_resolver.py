import json
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import session_state_resolver as resolver
from scripts.export_session_state_resolver import main as export_main


FIXED_NOW = "2026-05-26T01:00:00+00:00"
FIXED_CREATED_AT = "2026-05-26T00:45:41+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _terminal_response(
    *,
    source_request_id: str = "capital_hilton_invoice_status_catchup",
    workflow_ref: str = "capital_hilton_invoice_workflow",
    created_at: str = FIXED_CREATED_AT,
) -> dict:
    return {
        "schema_version": "openclaw_request_processor_v0",
        "read_model_id": "openclaw_response_for_mac",
        "generated_at": created_at,
        "created_at": created_at,
        "source_request_id": source_request_id,
        "workflow_ref": workflow_ref,
        "request_type": "CHAT",
        "internal_status": "RESPONSE_READY",
        "terminal": True,
        "headline": "Capital Hilton invoice is blocked",
        "operator_headline": "Capital Hilton invoice workflow is not ready yet",
        "primary_blocker": "Missing confirmed Coupa PO/reference",
        "next_action": "Next: Confirm the Coupa PO/reference.",
        "response_author": "CHIEF",
        "missing_items_short": ["Confirmed Coupa PO/reference"],
        "readback_files": ["generated/read_models/capital_hilton_invoice_operator_readback.json"],
        "detail_disclosure": {
            "request_classification": {
                "selected_rail": "capital_hilton_invoice_operator_readback",
            },
        },
        "authority_boundary": dict(resolver.AUTHORITY_BOUNDARY),
    }


def _heartbeat(*, workflow_ref: str = "capital_hilton_invoice_workflow") -> dict:
    return {
        "schema_version": "openclaw_request_response_service_v1",
        "processing_heartbeat_id": "processing_heartbeat_fixture",
        "source_request_id": "heartbeat_only_request",
        "workflow_ref": workflow_ref,
        "routing_status": "PROCESSING_ON_PC",
        "processing_status": "REQUEST_PROCESSING",
        "operator_headline": "OpenClaw is checking local rails",
        "operator_message": "OpenClaw picked this up and is checking the local rails.",
        "next_safe_move": "Keep waiting for the terminal response.",
        "created_at": FIXED_CREATED_AT,
        "terminal": False,
        "authority_boundary": dict(resolver.AUTHORITY_BOUNDARY),
    }


def test_required_models_exist_with_required_fields():
    assert tuple(field.name for field in fields(resolver.ActiveSessionState)) == (
        "session_state_id",
        "source",
        "tenant_scope",
        "client_scope",
        "active_world_ref",
        "active_folder_ref",
        "active_thread_ref",
        "active_workflow_ref",
        "latest_source_request_id",
        "latest_response_ref",
        "latest_terminal",
        "latest_headline",
        "latest_next_action",
        "latest_primary_blocker",
        "latest_response_author",
        "latest_intent_type",
        "current_blockers",
        "missing_items",
        "safe_readmodel_refs",
        "ambiguity_status",
        "stale_status",
        "authority_boundary",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(resolver.SessionStateResolver)) == (
        "resolver_id",
        "source_policy",
        "freshness_policy",
        "terminal_response_policy",
        "heartbeat_policy",
        "tenant_scope_policy",
        "ambiguity_policy",
        "authority_boundary",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(resolver.SessionStateBlocker)) == (
        "blocker_id",
        "blocker_type",
        "condition",
        "severity",
        "elioperator_warning",
        "fail_closed",
        "next_safe_move",
    )


def test_session_resolver_reads_latest_terminal_response_and_next_action(tmp_path):
    _write_json(tmp_path / "openclaw_response_for_mac.json", _terminal_response())
    _write_json(tmp_path / "openclaw_processing_for_mac_latest.json", _heartbeat())

    state = resolver.default_resolver().resolve(export_root=tmp_path, now=FIXED_NOW)

    assert state.latest_terminal is True
    assert state.latest_headline == "Capital Hilton invoice is blocked"
    assert state.latest_next_action == "Next: Confirm the Coupa PO/reference."
    assert state.latest_primary_blocker == "Missing confirmed Coupa PO/reference"
    assert state.latest_response_author == "CHIEF"
    assert state.active_workflow_ref == "capital_hilton_invoice_workflow"
    assert state.tenant_scope == "tenant_scope:fixture_business_ops"
    assert state.client_scope == "client_scope:fixture_capital_hilton"
    assert state.ambiguity_status is False
    assert state.next_safe_move == "Next: Confirm the Coupa PO/reference."
    assert not any(state.authority_boundary.values())


def test_session_resolver_distinguishes_heartbeat_only_from_terminal(tmp_path):
    _write_json(tmp_path / "openclaw_processing_for_mac_latest.json", _heartbeat())

    state = resolver.default_resolver().resolve(export_root=tmp_path, now=FIXED_NOW)

    assert state.latest_terminal is False
    assert state.latest_response_ref.endswith("openclaw_processing_for_mac_latest.json")
    assert state.active_workflow_ref == "capital_hilton_invoice_workflow"
    assert state.next_safe_move == "Wait for a terminal response or retry the bounded request/response service."
    assert "HEARTBEAT_ONLY_NO_TERMINAL" in {blocker["blocker_type"] for blocker in state.current_blockers}


def test_no_active_context_asks_clarification_and_does_not_guess_workflow(tmp_path):
    state = resolver.default_resolver().resolve(export_root=tmp_path, now=FIXED_NOW)

    assert state.ambiguity_status is True
    assert state.active_workflow_ref == "UNKNOWN"
    assert state.latest_terminal is False
    assert state.next_safe_move == "Ask the operator which world/thread/workflow should receive the next intent."
    assert {"NO_LATEST_RESPONSE", "AMBIGUOUS_WORKFLOW_CONTEXT"}.issubset(
        {blocker["blocker_type"] for blocker in state.current_blockers}
    )


def test_multiple_active_contexts_are_ambiguous(tmp_path):
    first = _write_json(tmp_path / "response_one.json", _terminal_response(workflow_ref="capital_hilton_invoice_workflow"))
    second = _write_json(
        tmp_path / "response_two.json",
        _terminal_response(source_request_id="creative_status", workflow_ref="workflow:fixture:x32_source_refs"),
    )

    state = resolver.default_resolver().resolve(
        export_root=tmp_path,
        response_paths=(first, second),
        now=FIXED_NOW,
    )

    assert state.ambiguity_status is True
    assert state.active_workflow_ref == "UNKNOWN"
    assert "AMBIGUOUS_WORKFLOW_CONTEXT" in {blocker["blocker_type"] for blocker in state.current_blockers}


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    _write_json(tmp_path / "openclaw_response_for_mac.json", _terminal_response())

    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / resolver.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / resolver.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == resolver.READ_MODEL_ID
    assert summary["latest_next_action"] == "Next: Confirm the Coupa PO/reference."
    assert summary["all_live_authority_false"] is True
    assert payload["active_session_state"]["active_workflow_ref"] == "capital_hilton_invoice_workflow"
    assert "Session State Resolver" in operator
    assert "No raw private bodies" in operator


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    _write_json(tmp_path / "openclaw_response_for_mac.json", _terminal_response())
    payload = resolver.build_payload(export_root=tmp_path, generated_at=FIXED_NOW, now=FIXED_NOW)
    resolver.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())
    lowered = text.lower()

    forbidden_literals = (
        "actual secret",
        "credential value",
        "password value",
        "token value",
        "raw private body value",
        "private key value",
    )
    for literal in forbidden_literals:
        assert literal not in lowered
    assert payload["machine_proof"]["raw_body_ingestion_performed"] is False
    assert payload["machine_proof"]["credential_handling_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
