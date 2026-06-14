import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_proof_response_retry_approval_packet as packet


FIXED_NOW = "2026-06-07T23:00:00+00:00"


def _model():
    return packet.build_retry_approval_packet(generated_at=FIXED_NOW)


def _unsafe_true_grants(value, path="$"):
    unsafe = set(packet.UNSAFE_TRUE_KEYS) | {"paid", "sent", "submitted", "authority_granted"}
    found = []
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


def test_packet_is_ready_but_pending_review():
    model = _model()

    assert model["status"] == packet.READY_STATUS
    assert model["packet"]["status"] == packet.PACKET_STATUS
    assert model["packet"]["status"] == "pending_operator_review"
    assert model["packet"]["runtime"] == "ollama"
    assert model["packet"]["model"] == "qwen3:8b-q4_K_M"
    assert model["packet"]["lane"] == "finance/capital_hilton"
    assert model["packet"]["question"] == "What should I do here?"


def test_invocation_and_proof_bundle_not_allowed_yet():
    model = _model()
    approval_packet = model["packet"]

    assert approval_packet["invocation_allowed"] is False
    assert approval_packet["proof_bundle_allowed"] is False
    assert model["authority_boundary"]["invocation_allowed"] is False
    assert model["authority_boundary"]["proof_bundle_allowed"] is False
    assert model["machine_proof"]["invocation_allowed"] is False
    assert model["machine_proof"]["proof_bundle_allowed"] is False


def test_prior_failure_recorded_as_non_json():
    model = _model()

    assert model["packet"]["prior_attempt_result"] == "failed_non_json"
    assert model["prior_attempt"]["prior_attempt_result"] == "failed_non_json"
    assert model["prior_attempt"]["source_failure_type"] == "non_json_structurally_invalid_empty_candidate"
    assert model["prior_attempt"]["non_json"] is True
    assert model["prior_attempt"]["structurally_invalid"] is True


def test_schema_adapter_verifier_and_fallback_are_mandatory():
    model = _model()
    approval_packet = model["packet"]

    assert approval_packet["retry_reason"] == "schema_adapter_now_ready"
    assert approval_packet["required_prompt_mode"] == "json_only"
    assert approval_packet["required_valid_example"] is True
    assert approval_packet["schema_adapter_required"] is True
    assert approval_packet["verifier_required"] is True
    assert approval_packet["fallback_required"] is True
    assert model["retry_rationale"]["schema_adapter_ready"] is True
    assert model["retry_rationale"]["json_only_prompt_contract_ready"] is True
    assert model["retry_rationale"]["comparison_recommended_next_test"] == "retry_local_with_schema_adapter"


def test_protected_actions_blocked():
    model = _model()
    approval_packet = model["packet"]

    assert "email_send" in approval_packet["forbidden_actions"]
    assert "submit" in approval_packet["forbidden_actions"]
    assert "ledger_mutation" in approval_packet["forbidden_actions"]
    assert "paid_marking" in approval_packet["forbidden_actions"]
    assert "worker_spawn" in approval_packet["forbidden_actions"]
    assert approval_packet["boundary"]["browser_gmail_coupa_allowed"] is False
    assert approval_packet["boundary"]["ledger_workbook_pdf_paid_mutation_allowed"] is False
    assert model["authority_boundary"]["protected_actions_allowed"] is False
    assert model["machine_proof"]["protected_actions_blocked"] is True


def test_decision_options_are_review_only():
    model = _model()

    assert model["packet"]["decision_options"] == [
        "approve_one_time_local_lm_retry_with_schema_adapter",
        "request_more_detail",
        "choose_different_model",
        "reject_for_now",
    ]
    assert model["packet"]["one_retry_attempt_only_if_later_approved"] is True
    assert "operator_approval_receipt" in model["packet"]["required_receipts_before_retry"]


def test_no_unsafe_true_grants():
    model = _model()

    assert model["implementation_boundary"]["model_invocation_performed"] is False
    assert model["implementation_boundary"]["local_model_runtime_connected"] is False
    assert model["implementation_boundary"]["prompt_sent"] is False
    assert model["implementation_boundary"]["proof_bundle_sent"] is False
    assert model["implementation_boundary"]["business_action_performed"] is False
    assert not _unsafe_true_grants(model)


def test_export_json_bridge_equality_and_unsafe_scan(tmp_path):
    result = packet.export_retry_approval_packet(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Proof Response Retry Approval Packet.md",
        generated_at=FIXED_NOW,
    )

    assert result["status"] == packet.READY_STATUS
    local = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert not _unsafe_true_grants(local)
    assert Path(result["wiki_path"]).exists()
