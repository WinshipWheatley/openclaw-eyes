import json
from pathlib import Path

import capital_hilton_guardian_review_packet as guardian
from scripts.export_capital_hilton_guardian_review_packet import main as export_main


FIXED_NOW = "2026-05-23T14:30:00+00:00"


EXPECTED_PACKET_IDS = {
    "protected_finance_metadata_review_packet",
    "coupa_reference_metadata_review_packet",
    "ap_route_metadata_review_packet",
    "tax_vendor_payment_handling_review_packet",
    "future_invoice_generation_review_packet",
}


def _build(*, protected_placeholder_present: bool = False) -> dict:
    return guardian.build_capital_hilton_guardian_review_packet(
        generated_at=FIXED_NOW,
        protected_placeholder_present=protected_placeholder_present,
    )


def _packets(payload: dict) -> dict:
    return {packet["guardian_packet_id"]: packet for packet in payload["guardian_review_packets"]}


def test_contract_is_deterministic_and_metadata_only():
    first = _build()
    second = _build()

    assert guardian.stable_json(first) == guardian.stable_json(second)
    assert first["schema_version"] == guardian.SCHEMA_VERSION
    assert first["read_model_id"] == guardian.READ_MODEL_ID
    assert first["contract_status"] == "deterministic_guardian_review_packet_metadata_only"
    assert first["guardian_rule_summary"]["guardian_may_review_metadata_posture_only"] is True
    assert first["guardian_rule_summary"]["guardian_may_approve_invoice_generation"] is False
    assert first["guardian_rule_summary"]["guardian_may_approve_send_submit"] is False
    assert first["guardian_rule_summary"]["guardian_may_access_accounts"] is False
    assert first["guardian_rule_summary"]["guardian_may_read_raw_bodies"] is False


def test_default_guardian_packets_exist_and_link_expected_proof_items():
    payload = _build()
    packets = _packets(payload)

    assert set(packets) == EXPECTED_PACKET_IDS
    assert payload["machine_proof"]["default_guardian_packet_count"] == 5
    protected = packets["protected_finance_metadata_review_packet"]
    assert list(protected["linked_proof_item_ids"]) == [
        "performance_date_2026_05_08_proof",
        "performance_date_2026_05_15_proof",
        "rate_400_per_gig_proof",
        "subtotal_800_proof",
        "one_invoice_posture_proof",
    ]
    assert list(packets["coupa_reference_metadata_review_packet"]["linked_proof_item_ids"]) == [
        "coupa_po_payment_reference_metadata"
    ]
    assert list(packets["ap_route_metadata_review_packet"]["linked_proof_item_ids"]) == [
        "ap_recipient_route_metadata"
    ]
    assert list(packets["tax_vendor_payment_handling_review_packet"]["linked_proof_item_ids"]) == [
        "tax_vendor_handling_metadata"
    ]
    assert list(packets["future_invoice_generation_review_packet"]["linked_proof_item_ids"]) == [
        "future_invoice_generation_receipt_requirement"
    ]


def test_review_statuses_and_sensitivity_classes_exist():
    payload = _build()

    assert set(payload["review_statuses"]) == set(guardian.REVIEW_STATUSES)
    assert set(payload["sensitivity_classes"]) == set(guardian.SENSITIVITY_CLASSES)
    for status in [
        "NOT_READY_FOR_GUARDIAN",
        "READY_FOR_GUARDIAN_REVIEW",
        "GUARDIAN_REVIEW_REQUIRED",
        "GUARDIAN_METADATA_ALLOWED",
        "GUARDIAN_METADATA_REJECTED",
        "GUARDIAN_QUARANTINED",
        "OPERATOR_ESCALATION_REQUIRED",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert status in payload["review_statuses"]
    for sensitivity_class in [
        "PROTECTED_FINANCE_METADATA",
        "COUPA_REFERENCE_METADATA",
        "AP_ROUTE_METADATA",
        "TAX_VENDOR_PAYMENT_METADATA",
        "FUTURE_INVOICE_GENERATION_METADATA",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert sensitivity_class in payload["sensitivity_classes"]
    assert payload["machine_proof"]["allowed_review_statuses_exist"] is True
    assert payload["machine_proof"]["sensitivity_classes_exist"] is True


def test_allowed_inputs_are_metadata_only_and_blocked_inputs_cover_sensitive_material():
    payload = _build()

    for allowed in [
        "proof item id",
        "answer candidate receipt ref",
        "protected placeholder ref",
        "source-card ref",
        "receipt ref",
        "hash/ref placeholder",
        "redacted metadata label",
        "operator-provided description as memory candidate",
    ]:
        assert allowed in payload["allowed_inputs"]
    for blocked in [
        "raw Excel body",
        "raw PDF body",
        "raw email body",
        "raw finance/private body",
        "Coupa login/session/browser data",
        "OAuth/session cookies",
        "credentials/API keys/tokens",
        "live account reads",
    ]:
        assert blocked in payload["blocked_inputs"]
    for packet in payload["guardian_review_packets"]:
        assert list(packet["allowed_inputs"]) == list(guardian.ALLOWED_INPUTS)
        assert list(packet["blocked_inputs"]) == list(guardian.BLOCKED_INPUTS)
    assert payload["machine_proof"]["allowed_inputs_metadata_only"] is True
    assert payload["machine_proof"]["blocked_inputs_include_raw_bodies_credentials_and_account_material"] is True


def test_allowed_outputs_are_review_outcomes_and_blocked_outputs_cover_action_authority():
    payload = _build()

    assert set(payload["allowed_outputs"]) == set(guardian.ALLOWED_OUTPUTS)
    assert "METADATA_PROMOTION_ALLOWED" in payload["allowed_outputs"]
    assert "QUARANTINE_REQUIRED" in payload["allowed_outputs"]
    for blocked in [
        "invoice generation approval",
        "send/submit approval",
        "Coupa access approval",
        "browser/account approval",
        "email dispatch approval",
        "credential handling approval",
        "raw body extraction approval",
        "ledger write approval",
        "runtime/tool/model/agent/queue approval",
    ]:
        assert blocked in payload["blocked_outputs"]
    for packet in payload["guardian_review_packets"]:
        assert list(packet["allowed_outputs"]) == list(guardian.ALLOWED_OUTPUTS)
        assert list(packet["blocked_outputs"]) == list(guardian.BLOCKED_OUTPUTS)
        assert packet["can_approve_action"] is False
        assert packet["can_access_accounts"] is False
        assert packet["can_read_raw_bodies"] is False
    assert payload["machine_proof"]["allowed_outputs_metadata_review_only"] is True
    assert payload["machine_proof"]["blocked_outputs_include_action_authority"] is True


def test_quarantine_triggers_exist():
    payload = _build()

    for trigger in [
        "credential exposure",
        "raw body attached or referenced as readable",
        "Coupa/browser/session material appears",
        "bank/check/remit data not properly protected",
        "source ref conflicts with proof item",
        "authority overclaim",
        "unknown sensitive surface",
        "missing source/proof refs",
        "malformed receipt",
        "unredacted private/customer material",
        "worker report claims action authority",
    ]:
        assert trigger in payload["quarantine_triggers"]
    assert payload["machine_proof"]["quarantine_triggers_exist"] is True


def test_guardian_cannot_approve_action_access_accounts_or_read_raw_bodies():
    payload = _build()
    boundary = payload["authority_boundary"]

    for key, value in guardian.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is False
        assert boundary[key] is False
    assert boundary["all_authority_flags_false"] is True
    assert boundary["guardian_can_approve_invoice_generation"] is False
    assert boundary["guardian_can_approve_send_submit"] is False
    assert boundary["guardian_can_access_coupa"] is False
    assert boundary["guardian_can_access_browser_oauth"] is False
    assert boundary["guardian_can_access_gmail_calendar_email"] is False
    assert boundary["guardian_can_read_raw_excel_body"] is False
    assert boundary["guardian_can_read_raw_pdf_body"] is False
    assert boundary["guardian_can_read_raw_email_body"] is False
    assert boundary["guardian_can_read_raw_finance_body"] is False
    assert boundary["model_call_allowed"] is False
    assert boundary["agent_activation_allowed"] is False
    assert boundary["tool_execution_allowed"] is False
    assert boundary["queue_execution_allowed"] is False
    assert boundary["runtime_dispatch_allowed"] is False
    assert payload["machine_proof"]["guardian_cannot_approve_invoice_generation"] is True
    assert payload["machine_proof"]["guardian_cannot_approve_send_submit"] is True
    assert payload["machine_proof"]["guardian_cannot_access_accounts"] is True
    assert payload["machine_proof"]["guardian_cannot_read_raw_bodies"] is True


def test_prior_lane_refs_are_represented_with_placeholder_pending_when_missing():
    payload = _build(protected_placeholder_present=False)
    linkage = payload["relationship_to_prior_lanes"]

    assert linkage["capital_hilton_answer_candidate_receipt"]["read_model_ref"] == (
        guardian.ANSWER_CANDIDATE_READ_MODEL_REF
    )
    assert linkage["capital_hilton_protected_reference_placeholder"]["read_model_ref"] == (
        guardian.PROTECTED_PLACEHOLDER_READ_MODEL_REF
    )
    assert linkage["capital_hilton_protected_reference_placeholder"]["status"] == "NOT_OBSERVED_OR_PENDING"
    assert linkage["protected_evidence_reference_receipt"]["read_model_ref"] == (
        guardian.PROTECTED_EVIDENCE_RECEIPT_REF
    )
    for packet in payload["guardian_review_packets"]:
        assert packet["linked_answer_candidate_refs"]
        assert packet["linked_protected_placeholder_refs"]
        assert all(ref.startswith("NOT_OBSERVED_OR_PENDING:") for ref in packet["linked_protected_placeholder_refs"])
    assert payload["machine_proof"]["prior_lane_refs_represented"] is True


def test_no_credentials_or_raw_private_bodies_are_included():
    payload = _build()
    text = guardian.stable_json(payload)

    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["machine_proof"]["raw_private_body_included"] is False
    assert "sk-" not in text
    assert "AKIA" not in text
    assert "BEGIN " + "PRIVATE KEY" not in text


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    result = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            "generated/read_models",
            "--format",
            "summary",
        ]
    )

    assert result == 0
    json_path = tmp_path / "generated" / "read_models" / guardian.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / guardian.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == guardian.SCHEMA_VERSION
    assert payload["machine_proof"]["default_guardian_packet_count"] == 5
    assert "ELIWINSHIP Summary" in operator
    assert "What Guardian Cannot Do" in operator
    assert "Next Backend Batch Lane" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("capital_hilton_guardian_review_packet.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
    ]:
        assert token not in text
