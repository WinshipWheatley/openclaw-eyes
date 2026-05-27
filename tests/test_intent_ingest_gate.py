import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import intent_ingest_gate as gate
import lm_intent_proposal_contract
import machine_intent_candidate_validator as validator


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _candidate(**overrides):
    data = {
        "intent_id": "intent_ingest_test_candidate",
        "source_request_id": "intent_ingest_test_request",
        "original_operator_text": "What is blocking Capital Hilton?",
        "inferred_intent_type": "ANSWER_STATUS",
        "requested_action": "Answer current workflow status from safe read-models.",
        "target_workflow_ref": "capital_hilton_invoice_workflow",
        "target_world_ref": "finance",
        "target_folder_ref": "capital_hilton",
        "target_thread_ref": "thread_ref:finance_capital_hilton",
        "target_agent_role": "CHIEF",
        "target_worker_type": "PC_CODEX",
        "confidence": "HIGH",
        "ambiguity_status": "UNAMBIGUOUS",
        "required_clarification": "",
        "referenced_next_action": "",
        "evidence_refs_used": (),
        "context_refs_used": ("tenant_scope:fixture_business_ops",),
        "source_refs_used": (),
        "missing_requirements": (),
        "forbidden_assumptions": (),
        "authority_requested": {"send_submit": False, "external_action": False},
        "authority_granted": {"send_submit": False, "external_action": False},
        "validation_required": True,
        "next_safe_move": "Validate before ingesting.",
        "target_world_ref": "finance",
    }
    data.update(overrides)
    return validator.MachineIntentCandidate(**data)


def _package(**overrides):
    raw = {
        "request_id": "intent_ingest_test_request",
        "operator_message": "What is blocking Capital Hilton?",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
    }
    raw.update(overrides.pop("raw_request", {}))
    payload = lm_intent_proposal_contract.build_payload(raw, generated_at=FIXED_NOW)
    payload["proposal_package"].update(overrides)
    return payload


def test_valid_low_risk_status_intent_is_accepted():
    result = gate.ingest_intent_proposal(_candidate(), package_payload=_package())

    assert result["outcome"] == gate.ACCEPTED_INTENT
    assert result["validation_verdict"] == "VALIDATED_INTENT"
    assert result["accepted_intent"]["intent_type"] == "ANSWER_STATUS"
    assert result["accepted_intent"]["target_agent_role"] == "CHIEF"
    assert result["accepted_intent"]["workflow_ref"] == "capital_hilton_invoice_workflow"
    assert not any(result["accepted_intent"]["authority_granted"].values())
    assert result["trace"]["capability_checked"] is True


def test_ambiguous_intent_returns_needs_clarification():
    candidate = _candidate(
        intent_id="ambiguous_next",
        original_operator_text="next",
        inferred_intent_type="CONTINUE_CURRENT_WORKFLOW",
        requested_action="Continue whatever this means.",
        target_workflow_ref="unknown",
        confidence="MEDIUM",
        ambiguity_status="AMBIGUOUS",
        required_clarification="Which workflow should OpenClaw continue?",
    )

    result = gate.ingest_intent_proposal(candidate, package_payload=_package(workflow_ref="unknown"))

    assert result["outcome"] == gate.NEEDS_CLARIFICATION
    assert result["clarification_request"]["question"] == "Which workflow should OpenClaw continue?"
    assert result["accepted_intent"] is None


def test_unsupported_capability_is_rejected_without_execution():
    candidate = _candidate(
        intent_id="unsupported_capability",
        inferred_intent_type="LEVITATE_INVOICE",
        requested_action="Use the levitation adapter.",
        original_operator_text="levitate this invoice",
    )

    result = gate.ingest_intent_proposal(candidate, package_payload=_package())

    assert result["outcome"] == gate.UNSUPPORTED_CAPABILITY
    assert result["missing_capabilities"]
    assert result["accepted_intent"] is None


def test_send_submit_ledger_post_is_blocked_by_authority():
    candidate = _candidate(
        intent_id="blocked_send_submit",
        inferred_intent_type="REQUEST_APPROVAL",
        requested_action="Send the invoice and post ledger revenue.",
        original_operator_text="yo Cassandra send that invoice to CH and post it",
        target_agent_role="CASSANDRA",
    )

    result = gate.ingest_intent_proposal(candidate, package_payload=_package())

    assert result["outcome"] == gate.BLOCKED_AUTHORITY
    assert result["authority_block"]
    assert "send" in result["authority_block"]["blocked_authority"]
    assert any("post ledger" in item or "ledger" in item for item in result["authority_block"]["blocked_authority"])
    assert not any(result["authority_block"]["authority_granted"].values())


def test_lm1_cannot_grant_itself_authority():
    candidate = _candidate(
        intent_id="self_granted_authority",
        authority_granted={"send_submit": True, "external_action": False},
    )

    result = gate.ingest_intent_proposal(candidate, package_payload=_package())

    assert result["outcome"] == gate.BLOCKED_AUTHORITY
    assert "send_submit" in result["authority_block"]["blocked_authority"]


def test_cross_client_scope_mismatch_is_parked():
    result = gate.ingest_intent_proposal(_candidate(), package_payload=_package(client_ref="st_annes"))

    assert result["outcome"] == gate.NEEDS_CONTEXT
    assert "CROSS_CLIENT_SCOPE_MISMATCH" in result["blocker_reasons"]
    assert result["accepted_intent"] is None


def test_missing_source_request_id_is_blocked_for_context():
    candidate = _candidate(intent_id="missing_source", source_request_id="")

    result = gate.ingest_intent_proposal(candidate, package_payload={})

    assert result["outcome"] == gate.NEEDS_CONTEXT
    assert "MISSING_SOURCE_REQUEST_ID" in result["blocker_reasons"]
    assert "source_request_id" in result["missing_items"]


def test_delete_from_openclaw_becomes_reference_supersession_not_physical_delete():
    candidate = _candidate(
        intent_id="supersede_workbook_reference",
        inferred_intent_type="ATTACH_SOURCE_REF",
        original_operator_text="The file I just gave you is the actual workbook. Delete the other one from OpenClaw.",
        requested_action="Use newest workbook and delete the other one from OpenClaw.",
        source_refs_used=("local_artifact_reference:newest_capital_hilton_workbook",),
    )

    result = gate.ingest_intent_proposal(candidate, package_payload=_package())

    assert result["outcome"] == gate.ACCEPTED_INTENT
    assert result["accepted_intent"]["safe_action_type"] == "SUPERSEDE_ACTIVE_REFERENCE_NOT_PHYSICAL_DELETE"
    assert "do not delete any file from disk" in result["accepted_intent"]["requested_action"].lower()
    assert result["authority_block"] is None


def test_unknown_messy_phrase_does_not_become_accepted_without_context():
    candidate = _candidate(
        intent_id="messy_unknown",
        original_operator_text="do the weird thing with that stuff",
        inferred_intent_type="UNKNOWN_FAIL_CLOSED",
        requested_action="unknown",
        target_workflow_ref="unknown",
        confidence="LOW",
        ambiguity_status="MISSING_CONTEXT",
    )

    result = gate.ingest_intent_proposal(candidate, package_payload=_package(workflow_ref="unknown"))

    assert result["outcome"] == gate.LOW_CONFIDENCE
    assert result["accepted_intent"] is None


def test_exported_readmodel_parses(tmp_path):
    payload = gate.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = gate.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == gate.READ_MODEL_ID
    assert parsed["machine_proof"]["accepted_example_is_accepted"] is True
    assert parsed["machine_proof"]["blocked_example_is_blocked"] is True
    assert parsed["machine_proof"]["all_live_authority_false"] is True
    assert "Gate 2 accepts" in operator_path.read_text(encoding="utf-8")
