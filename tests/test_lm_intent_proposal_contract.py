import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm_intent_proposal_contract as proposal_contract
from scripts.export_lm_intent_proposal_contract import main as export_main


FIXED_NOW = "2026-05-26T21:40:00+00:00"


def _raw_request() -> dict:
    return {
        "request_id": "mission_control_chat_request_freeform_unknown",
        "operator_message": "make the blue thing less weird after lunch",
        "sanitized_message_summary": "operator freeform request",
        "world_ref": "finance",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "client_ref": "capital_hilton",
    }


def _candidate(source_request_id: str, *, authority_true: bool = False) -> dict:
    authority = {
        "workflow_run": False,
        "agent_dispatch": False,
        "worker_dispatch": False,
        "external_action": False,
        "send_submit": authority_true,
        "approval_execution": False,
        "candidate_promotion": False,
        "credential_handling": False,
        "raw_body_ingestion": False,
        "file_mutation": False,
    }
    return {
        "intent_id": "intent_candidate:fixture_lm_proposal",
        "source_request_id": source_request_id,
        "original_operator_text": "yo send that invoice to CH",
        "inferred_intent_type": "REQUEST_APPROVAL",
        "target_world_ref": "world_ref:finance",
        "target_folder_ref": "folder_ref:capital_hilton",
        "target_thread_ref": "thread_ref:current",
        "target_workflow_ref": "capital_hilton_invoice_workflow",
        "target_agent_role": "GUARDIAN",
        "target_worker_type": "PC_CODEX",
        "requested_action": "send invoice",
        "referenced_next_action": "Next: prepare a reviewable send packet.",
        "confidence": "HIGH",
        "ambiguity_status": "UNAMBIGUOUS",
        "required_clarification": "",
        "evidence_refs_used": (),
        "context_refs_used": ("finance", "capital_hilton", "capital_hilton_invoice_workflow"),
        "source_refs_used": (),
        "missing_requirements": ("MISSING_APPROVAL",),
        "forbidden_assumptions": ("casual send language grants authority",),
        "authority_requested": authority,
        "authority_granted": authority,
        "validation_required": True,
        "next_safe_move": "Validate before any action.",
    }


def test_proposal_package_is_safe_and_schema_bound(tmp_path):
    payload = proposal_contract.build_payload(
        _raw_request(),
        request_filename="mission_control_chat_request_unknown.json",
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )

    package = payload["proposal_package"]
    assert payload["proposal_readback"]["status"] == "PROPOSAL_PACKAGE_CREATED"
    assert package["source_request_id"] == "mission_control_chat_request_freeform_unknown"
    assert package["intended_use"] == proposal_contract.INTENDED_USE
    assert "MachineIntentCandidate" not in package["operator_text"]
    assert "authority_granted" in package["allowed_output_schema"]
    assert package["required_candidate_defaults"]["validation_required"] is True
    assert not any(package["authority_boundary"].values())
    assert payload["machine_proof"]["model_call_performed"] is False
    assert payload["machine_proof"]["workflow_execution_performed"] is False
    assert payload["machine_proof"]["send_submit_performed"] is False
    assert payload["machine_proof"]["raw_body_ingestion_performed"] is False


def test_malicious_proposed_candidate_is_blocked_by_validator(tmp_path):
    package_payload = proposal_contract.build_payload(_raw_request(), export_root=tmp_path, generated_at=FIXED_NOW)
    result = proposal_contract.validate_proposed_candidate(
        _candidate(package_payload["proposal_package"]["source_request_id"], authority_true=True),
        package_payload=package_payload,
    )

    assert result["proposal_validation_receipt"]["status"] == "PROPOSAL_BLOCKED_BY_VALIDATOR"
    assert result["validation_result"]["verdict"] == "BLOCKED_BY_AUTHORITY"
    assert not any(result["validation_result"]["authority_granted"].values())
    assert result["proposal_validation_receipt"]["model_call_performed"] is False
    assert result["proposal_validation_receipt"]["execution_performed"] is False


def test_export_writes_parseable_readmodel_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / proposal_contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / proposal_contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == proposal_contract.READ_MODEL_ID
    assert summary["model_call_performed"] is False
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert "no model call" in operator.lower()
