import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import intent_ingest_gate
import machine_intent_candidate_validator as validator
import role_package_gate as gate


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _candidate(
    *,
    intent_id: str,
    source_request_id: str,
    intent_type: str,
    action: str,
    role: str = "CHIEF",
    world_ref: str = "finance",
    workflow_ref: str = "capital_hilton_invoice_workflow",
):
    return validator.MachineIntentCandidate(
        intent_id=intent_id,
        source_request_id=source_request_id,
        original_operator_text=action,
        inferred_intent_type=intent_type,
        target_world_ref=world_ref,
        target_folder_ref="capital_hilton",
        target_thread_ref="thread_ref:finance_capital_hilton",
        target_workflow_ref=workflow_ref,
        target_agent_role=role,
        target_worker_type="PC_CODEX",
        requested_action=action,
        referenced_next_action="",
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=("generated/read_models/openclaw_response_for_mac.json",),
        context_refs_used=("tenant_scope:fixture_business_ops",),
        source_refs_used=(),
        missing_requirements=(),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False},
        authority_granted={"send_submit": False, "external_action": False},
        validation_required=True,
        next_safe_move="Validate before packaging.",
    )


def _accepted(
    *,
    intent_type: str,
    action: str,
    role: str,
    source_request_id: str = "role_package_test_request",
    workflow_ref: str = "capital_hilton_invoice_workflow",
):
    candidate = _candidate(
        intent_id=f"candidate_{intent_type.lower()}_{role.lower()}",
        source_request_id=source_request_id,
        intent_type=intent_type,
        action=action,
        role=role,
        workflow_ref=workflow_ref,
    )
    result = intent_ingest_gate.ingest_intent_proposal(candidate)
    assert result["outcome"] == intent_ingest_gate.ACCEPTED_INTENT
    return result


def test_accepted_chief_status_intent_compiles_chief_package():
    result = gate.compile_role_package(
        _accepted(intent_type="ANSWER_STATUS", action="Show me what is blocking Capital Hilton.", role="CHIEF")
    )
    readback = gate.build_package_readback(result)

    package = result["role_execution_package"]
    assert result["package_status"] == gate.PACKAGE_COMPILED
    assert package["role_identity"] == "CHIEF"
    assert package["actor_label"] == "Chief"
    assert package["output_destination"]["destination_type"] == "MISSION_CONTROL_SCOPED_RESPONSE"
    assert package["ready_for_gate_4"] is True
    assert package["lm2_call_allowed"] is False
    assert readback["operator_message"] == "OpenClaw can prepare a Chief status response."
    assert readback["gate4_readiness_state"] == "READY_FOR_GUARDIAN_OUTPUT_GATE"
    assert readback["lm2_call_allowed"] is False


def test_cassandra_comms_draft_package_has_no_send_authority():
    result = gate.compile_role_package(
        _accepted(intent_type="PREPARE_DRAFT", action="Prep the email draft for review.", role="CASSANDRA")
    )
    package = result["role_execution_package"]
    readback = gate.build_package_readback(result)

    assert package["role_identity"] == "CASSANDRA"
    assert package["tool_policy"]["allowed_tools"] == ()
    assert "send_email" in package["tool_policy"]["forbidden_actions"]
    assert package["authority_policy"]["send_submit_authority_granted"] is False
    assert package["authority_policy"]["external_action_authority_granted"] is False
    assert "cannot send anything" in readback["operator_message"]


def test_finance_invoice_prep_compiles_cassandra_clara_style_package_without_ledger_authority():
    result = gate.compile_role_package(
        _accepted(
            intent_type="CAPTURE_MISSING_INPUT",
            action="Prepare the Capital Hilton invoice facts for review.",
            role="CASSANDRA",
        )
    )
    package = result["role_execution_package"]

    assert package["role_identity"] == "CASSANDRA_CLARA"
    assert package["actor_label"] == "Cassandra/Clara"
    assert "post_ledger_entry" in package["tool_policy"]["forbidden_actions"]
    assert package["authority_policy"]["tool_authority_granted"] is False


def test_package_includes_source_request_and_output_destination():
    result = gate.compile_role_package(
        _accepted(
            intent_type="ANSWER_STATUS",
            action="Show status.",
            role="CHIEF",
            source_request_id="source_request_123",
        )
    )
    package = result["role_execution_package"]

    assert package["source_request_id"] == "source_request_123"
    assert package["output_destination"]["source_request_id"] == "source_request_123"
    assert package["output_destination"]["gate_4_ref"] == "guardian_output_gate"
    assert package["tokenization_applied"] is True
    assert package["raw_values_included"] is False
    assert package["model_may_see_raw_values"] is False
    assert package["token_vault_ref"] == "generated/read_models/token_vault_status.json"


def test_forbidden_tools_and_actions_are_explicit():
    result = gate.compile_role_package(
        _accepted(intent_type="ANSWER_STATUS", action="Show status.", role="CHIEF")
    )
    policy = result["role_execution_package"]["tool_policy"]

    assert "gmail" in policy["forbidden_tools"]
    assert "coupa" in policy["forbidden_tools"]
    assert "workflow_runner" in policy["forbidden_tools"]
    assert "send_email" in policy["forbidden_actions"]
    assert "execute_workflow" in policy["forbidden_actions"]


def test_no_package_can_include_send_submit_or_tool_authority_without_receipts():
    result = gate.compile_role_package(
        _accepted(intent_type="PREPARE_DRAFT", action="Prep a draft for review.", role="CASSANDRA")
    )
    package = result["role_execution_package"]

    assert package["tool_policy"]["allowed_tools"] == ()
    assert package["authority_policy"]["required_receipts_before_tools"]
    assert package["authority_policy"]["tool_authority_granted"] is False
    assert package["authority_policy"]["send_submit_authority_granted"] is False
    assert not any(package["authority_policy"]["authority_boundary"].values())


def test_low_confidence_or_blocked_gate2_result_does_not_compile_execution_package():
    blocked = {
        "ingest_result_id": "blocked_gate2_result",
        "outcome": intent_ingest_gate.LOW_CONFIDENCE,
        "source_request_id": "blocked_request",
        "source_candidate_ref": "blocked_candidate",
        "accepted_intent": None,
    }

    result = gate.compile_role_package(blocked)

    assert result["package_status"] == gate.PACKAGE_NOT_COMPILED
    assert result["role_execution_package"] is None
    readback = gate.build_package_readback(result)
    assert readback["gate4_readiness_state"] == "NOT_READY_FOR_GATE_4"
    assert readback["model_router_result"]["selected_model_class"] == "NO_SAFE_MODEL"


def test_package_output_is_ready_for_gate4_validation_later():
    result = gate.compile_role_package(
        _accepted(intent_type="ANSWER_STATUS", action="Show status.", role="CHIEF")
    )
    package = result["role_execution_package"]

    assert package["output_contract_ref"] == "guardian_output_gate_v0"
    assert package["ready_for_gate_4"] is True
    assert result["authority_boundary"]["live_lm2_call_allowed"] is False


def test_exported_readmodel_parses(tmp_path):
    payload = gate.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = gate.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == gate.READ_MODEL_ID
    assert parsed["machine_proof"]["chief_package_compiled"] is True
    assert parsed["machine_proof"]["blocked_gate2_not_compiled"] is True
    assert parsed["machine_proof"]["package_readback_operator_visible"] is True
    assert parsed["machine_proof"]["package_readback_gate4_ready"] is True
    assert parsed["machine_proof"]["package_readback_model_router_present"] is True
    assert parsed["machine_proof"]["all_live_authority_false"] is True
    assert "Gate 3 compiles" in operator_path.read_text(encoding="utf-8")
