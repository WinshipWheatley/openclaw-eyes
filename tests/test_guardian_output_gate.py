import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import guardian_output_gate as gate


def _safe_payload(**overrides):
    payload = {
        "source_request_id": "guardian_output_gate_test_request",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "client_ref": "capital_hilton",
        "response_author": "CASSANDRA",
        "selected_model_backend": "GPT",
        "allowed_tools_plugins": ("draft_readback_only",),
        "headline": "Draft ready",
        "one_line_answer": "Review language is ready.",
        "eliwinship": "Draft review language is ready. Send authority remains locked.",
        "next_action": "Next: review the draft.",
        "readback_files": ("generated/read_models/guardian_output_gate.json",),
    }
    payload.update(overrides)
    return payload


def test_safe_role_response_validates_without_live_authority():
    result = gate.validate_response_payload(_safe_payload())

    assert result["validation_result"]["verdict"] == gate.VALIDATED
    assert result["validation_result"]["output_publish_allowed"] is True
    assert result["machine_proof"]["guardian_output_gate_used"] is True
    assert result["machine_proof"]["model_call_performed"] is False
    assert result["machine_proof"]["agent_dispatch_performed"] is False
    assert result["machine_proof"]["worker_dispatch_performed"] is False
    assert result["machine_proof"]["workflow_execution_performed"] is False
    assert result["machine_proof"]["send_submit_performed"] is False
    assert result["machine_proof"]["all_live_authority_false"] is True


def test_completion_claim_with_proof_refs_validates_without_authority():
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Invoice workflow completed",
            eliwinship="I completed the local readback and updated the review packet.",
            next_action="Next: review the proof refs.",
            proof_refs=("generated/read_models/capital_hilton_invoice_operator_run_status.json",),
            readback_files=(),
        )
    )

    assert result["validation_result"]["verdict"] == gate.VALIDATED
    assert result["validation_result"]["output_publish_allowed"] is True
    assert set(result["validation_result"]["forbidden_claims"]) >= {"completed", "updated"}
    assert result["validation_result"]["blocked_reasons"] == ()
    assert result["machine_proof"]["send_submit_performed"] is False
    assert result["machine_proof"]["all_live_authority_false"] is True


def test_proof_refs_do_not_authorize_send_submit_or_money_claims():
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Invoice sent",
            eliwinship="I sent the invoice, submitted it, and marked it paid.",
            next_action="Next: wait for payment.",
            proof_refs=("generated/read_models/capital_hilton_invoice_operator_run_status.json",),
            readback_files=(),
        )
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_FORBIDDEN_CLAIM
    assert result["validation_result"]["output_publish_allowed"] is False
    assert {"sent", "submitted", "paid"}.issubset(set(result["validation_result"]["forbidden_claims"]))


def test_completion_claim_without_proof_refs_is_blocked():
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Invoice sent",
            eliwinship="I sent the invoice and posted the ledger.",
            next_action="Next: wait for payment.",
            readback_files=(),
        )
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_FORBIDDEN_CLAIM
    assert result["validation_result"]["output_publish_allowed"] is False
    assert "sent" in result["validation_result"]["forbidden_claims"]
    assert "posted" in result["validation_result"]["forbidden_claims"]


@pytest.mark.parametrize(
    ("text", "claim"),
    [
        ("I sent it, but unverified.", "sent"),
        ("Sent, pending approval.", "sent"),
        ("Submitted subject to final confirmation.", "submitted"),
        ("Unverified sent confirmation.", "sent"),
        ("Conditional submitted status.", "submitted"),
    ],
)
def test_hedged_completion_claims_are_blocked(text, claim):
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Hedged completion",
            eliwinship=text,
            next_action="Next: require proof before saying it happened.",
            readback_files=(),
        )
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_FORBIDDEN_CLAIM
    assert result["validation_result"]["output_publish_allowed"] is False
    assert claim in result["validation_result"]["forbidden_claims"]


def test_completion_claim_with_readback_file_only_is_still_blocked():
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Invoice sent",
            eliwinship="I sent the invoice.",
            next_action="Next: wait for payment.",
        )
    )

    assert result["role_response_candidate"]["proof_refs"] == ()
    assert result["validation_result"]["verdict"] == gate.BLOCKED_FORBIDDEN_CLAIM
    assert result["validation_result"]["output_publish_allowed"] is False
    assert "sent" in result["validation_result"]["forbidden_claims"]


def test_prior_sentence_negation_does_not_clear_later_completion_claim():
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Blocked then sent",
            eliwinship="Sending remains blocked. I sent the invoice.",
            next_action="Next: wait for payment.",
            readback_files=(),
        )
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_FORBIDDEN_CLAIM
    assert result["validation_result"]["output_publish_allowed"] is False
    assert result["validation_result"]["forbidden_claims"] == ("sent",)


def test_subject_clause_boundary_does_not_clear_later_completion_claim():
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Mixed status",
            eliwinship="I did not mark the invoice paid and I updated the readback.",
            next_action="Next: review the readback.",
            readback_files=(),
        )
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_FORBIDDEN_CLAIM
    assert result["validation_result"]["output_publish_allowed"] is False
    assert result["validation_result"]["forbidden_claims"] == ("updated",)


def test_negative_contractions_do_not_create_completion_claims():
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Not complete",
            eliwinship="I haven't completed the workflow and I wasn't authorized to approve it.",
            next_action="Next: keep SEND_HOLD active.",
            readback_files=(),
        )
    )

    assert result["validation_result"]["verdict"] == gate.VALIDATED
    assert result["validation_result"]["forbidden_claims"] == ()
    assert result["validation_result"]["output_publish_allowed"] is True


def test_reference_mutation_claim_without_receipt_is_blocked():
    result = gate.validate_response_payload(
        _safe_payload(
            headline="Workbook updated",
            eliwinship="I removed the test workbook and replaced it with the real one.",
            next_action="Next: continue.",
        )
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_FORBIDDEN_CLAIM
    assert result["validation_result"]["output_publish_allowed"] is False
    assert {"removed", "replaced"}.issubset(set(result["validation_result"]["forbidden_claims"]))


def test_requested_external_action_is_blocked():
    result = gate.validate_response_payload(
        _safe_payload(requested_external_actions=("email_send",), eliwinship="Please send this now.")
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_AUTHORITY
    assert result["validation_result"]["external_action_allowed"] is False
    assert "email_send" in result["validation_result"]["forbidden_actions"]


def test_requested_unallowlisted_tool_is_blocked():
    result = gate.validate_response_payload(
        _safe_payload(requested_tool_calls=("gmail_send",), allowed_tools_plugins=("draft_readback_only",))
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_FORBIDDEN_TOOL
    assert "gmail_send" in result["validation_result"]["forbidden_tools"]


def test_authority_request_fails_closed():
    result = gate.validate_response_payload(
        _safe_payload(detail_disclosure={"authority_requested": {"email_send": True}})
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_AUTHORITY
    assert all(value is False for value in result["validation_result"]["authority_granted"].values())


def test_abstract_credential_ref_wording_is_not_treated_as_secret_leakage():
    result = gate.validate_response_payload(
        _safe_payload(
            response_author="CHIEF",
            eliwinship="The protected credential ref is missing. Actual credential value: EXAMPLE_VALUE.",
        )
    )

    assert result["validation_result"]["verdict"] == gate.BLOCKED_LEAKAGE
    assert "credential value" in result["validation_result"]["leakage_hits"]

    safe_result = gate.validate_response_payload(
        _safe_payload(
            response_author="CHIEF",
            eliwinship="The protected credential ref is missing. Nothing can send or submit yet.",
        )
    )
    assert safe_result["validation_result"]["verdict"] == gate.VALIDATED


@pytest.mark.parametrize(
    ("text", "hit"),
    [
        ("API key abc123xyz", "api key"),
        ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "bearer token"),
        ("client_secret={secret}", "client_secret"),
    ],
)
def test_common_api_credentials_are_blocked_as_leakage(text, hit):
    result = gate.validate_response_payload(_safe_payload(response_author="CHIEF", eliwinship=text))

    assert result["validation_result"]["verdict"] == gate.BLOCKED_LEAKAGE
    assert hit in result["validation_result"]["leakage_hits"]


def test_abstract_api_key_reference_is_not_secret_leakage():
    result = gate.validate_response_payload(
        _safe_payload(response_author="CHIEF", eliwinship="The API key reference is missing from the safe config.")
    )

    assert result["validation_result"]["verdict"] == gate.VALIDATED
    assert "api key" not in result["validation_result"]["leakage_hits"]


def test_exported_readmodel_parses(tmp_path):
    payload = gate.build_payload(generated_at="2026-05-26T00:00:00+00:00")
    json_path, operator_path = gate.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == gate.READ_MODEL_ID
    assert parsed["machine_proof"]["safe_example_validated"] is True
    assert parsed["machine_proof"]["rogue_example_blocked"] is True
    assert parsed["machine_proof"]["all_live_authority_false"] is True
    assert "One shared output gate" in operator_path.read_text(encoding="utf-8")
