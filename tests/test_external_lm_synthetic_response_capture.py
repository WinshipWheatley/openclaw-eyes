import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_synthetic_response_capture as capture

FIXED_NOW = "2026-06-07T15:00:00+00:00"


def _valid_response(**overrides):
    payload = {
        "headline": "Payment evidence needed",
        "body": "Payment evidence is missing. The processor says processing, and the ledger stays untouched.",
        "next_step": "Attach payment evidence.",
        "missing_input": ["payment_evidence"],
        "can_do_now": ["Hold payment watch", "Ask for payment proof"],
        "cannot_do_yet": ["paid marking", "ledger mutation", "submit", "send"],
        "claimed_facts": list(capture.synthetic_packet.CANONICAL_SYNTHETIC_FACT_IDS),
        "requested_controls": ["Attach payment evidence"],
        "uncertainty_notes": [],
    }
    payload.update(overrides)
    return payload


def _capture(payload):
    return capture.capture_manual_synthetic_response(json.dumps(payload), generated_at=FIXED_NOW)


def _unsafe_true_grants(value, path="$"):
    found = []
    unsafe = set(capture.UNSAFE_TRUE_KEYS) | {"paid", "sent", "submitted", "authority_granted"}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_grants(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_grants(child, f"{path}[{index}]"))
    return found


def test_valid_synthetic_external_response_passes():
    result = _capture(_valid_response())

    assert result["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_PASS
    assert result["verifier_pass"] is True
    assert result["adapter_result"]["parse_status"] == "PARSED"
    assert result["business_truth_status"] == "SYNTHETIC_ONLY_NOT_FINANCE_TRUTH"
    assert result["published_as_real_business_truth"] is False
    assert result["synthetic_response_only"] is True
    assert result["failure_reasons"] == []
    assert not _unsafe_true_grants(result)


def test_previously_pasted_synthetic_response_now_passes():
    result = _capture(
        _valid_response(
            body="Payment evidence is missing. The processor is still processing, and the ledger stays untouched.",
            can_do_now=["Hold payment watch", "Wait for payment evidence"],
            cannot_do_yet=["Mark paid", "Update the ledger", "Submit anything", "Send anything"],
        )
    )

    assert result["adapter_result"]["parse_status"] == "PARSED"
    assert result["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_PASS
    assert result["verifier_pass"] is True
    assert result["failure_reasons"] == []
    assert result["adapted_candidate"]["claimed_facts"] == list(capture.synthetic_packet.CANONICAL_SYNTHETIC_FACT_IDS)


def test_non_json_response_fails():
    result = capture.capture_manual_synthetic_response(
        "Payment evidence is missing; attach proof.",
        generated_at=FIXED_NOW,
    )

    assert result["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_FAIL
    assert result["verifier_pass"] is False
    assert result["adapter_result"]["parse_status"] == "PARSE_ERROR"
    assert any(reason.startswith("adapter:json_parse_error") for reason in result["failure_reasons"])


def test_paid_claim_fails():
    result = _capture(
        _valid_response(
            body="Payment evidence is missing. The invoice is paid and the ledger stays untouched.",
        )
    )

    assert result["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_FAIL
    assert any("unsupported_completion_claim:is paid" in reason for reason in result["failure_reasons"])
    assert result["published_as_real_business_truth"] is False


def test_send_submit_ledger_claim_fails():
    result = _capture(
        _valid_response(
            body="Payment evidence is missing. I sent the notice, submitted it, and ledger updated.",
        )
    )

    assert result["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_FAIL
    reasons = "\n".join(result["failure_reasons"])
    assert "unsupported_completion_claim" in reasons
    assert "sent" in reasons or "submitted" in reasons or "ledger updated" in reasons


def test_private_or_real_proof_field_is_schema_blocked():
    payload = _valid_response(private_proof="real bank screenshot")
    result = _capture(payload)

    assert result["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_FAIL
    assert result["verifier_pass"] is False
    assert result["adapter_result"]["parse_status"] == "SCHEMA_ERROR"
    assert "adapter:unknown_field:private_proof" in result["failure_reasons"]
    assert result["published_as_real_business_truth"] is False


def test_protected_action_promise_fails():
    result = _capture(
        _valid_response(
            body="Payment evidence is missing. I will update the ledger after this.",
        )
    )

    assert result["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_FAIL
    assert any("protected_action_promise:ledger_mutation" in reason for reason in result["failure_reasons"])


def test_machine_contract_jargon_fails():
    result = _capture(
        _valid_response(
            body="The dynamic card read model says payment evidence is missing and the ledger stays untouched.",
        )
    )

    assert result["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_FAIL
    assert any("machine_contract_jargon" in reason for reason in result["failure_reasons"])


def test_no_authority_grants():
    result = _capture(_valid_response())
    contract = capture.build_contract_read_model(generated_at=FIXED_NOW)

    assert result["authority_boundary"]["external_lm_allowed"] is False
    assert result["authority_boundary"]["business_action_allowed"] is False
    assert result["authority_boundary"]["ledger_mutation_allowed"] is False
    assert result["authority_boundary"]["paid_marking_allowed"] is False
    assert result["machine_proof"]["external_llm_invoked"] is False
    assert result["machine_proof"]["business_action_performed"] is False
    assert not _unsafe_true_grants(result)
    assert not _unsafe_true_grants(contract)


def test_contract_documents_manual_capture_and_no_private_proof():
    contract = capture.build_contract_read_model(generated_at=FIXED_NOW)

    assert contract["status"] == capture.READY_STATUS
    assert contract["contract"]["input"] == "manual_pasted_synthetic_response_text"
    assert contract["contract"]["output"] == "verifier_pass_or_verifier_fail_receipt"
    assert contract["rules"]["no_private_proof_allowed"] is True
    assert contract["rules"]["never_publish_as_real_business_truth"] is True
    assert contract["rules"]["never_treat_synthetic_response_as_finance_truth"] is True
    assert contract["sample_capture"]["capture_status"] == capture.CAPTURE_STATUS_VERIFIER_PASS


def test_export_json_bridge_equality_and_unsafe_scan(tmp_path):
    result = capture.export_response_capture_contract(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "External LM Synthetic Response Capture.md",
        generated_at=FIXED_NOW,
    )

    assert result["status"] == capture.READY_STATUS
    local = json.loads(Path(result["contract_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_contract_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert not _unsafe_true_grants(local)
    assert Path(result["wiki_path"]).exists()
