import json
from pathlib import Path

import capital_hilton_delivery_facts_capture_bridge as bridge
from scripts.export_capital_hilton_delivery_facts_capture_bridge import main as export_main


FIXED_NOW = "2026-05-24T20:00:00+00:00"


def _build() -> dict:
    return bridge.build_capital_hilton_delivery_facts_capture_bridge(generated_at=FIXED_NOW)


def test_required_models_exist():
    payload = _build()

    assert payload["schema_version"] == bridge.SCHEMA_VERSION
    assert payload["read_model_id"] == bridge.READ_MODEL_ID
    assert payload["machine_proof"]["po_coupa_capture_block_exists"] is True
    assert payload["machine_proof"]["ap_email_route_capture_block_exists"] is True
    assert payload["machine_proof"]["protected_evidence_reference_target_exists"] is True
    assert payload["machine_proof"]["delivery_facts_receipt_target_exists"] is True
    assert payload["machine_proof"]["delivery_facts_readiness_exists"] is True
    assert payload["model_schemas"]["delivery_facts_capture_bridge"]["required_fields"] == list(
        bridge.REQUIRED_BRIDGE_FIELDS
    )
    assert payload["model_schemas"]["po_coupa_capture_block"]["required_fields"] == list(
        bridge.REQUIRED_PO_BLOCK_FIELDS
    )
    assert payload["model_schemas"]["ap_email_route_capture_block"]["required_fields"] == list(
        bridge.REQUIRED_AP_BLOCK_FIELDS
    )
    assert payload["model_schemas"]["protected_evidence_reference_target"]["required_fields"] == list(
        bridge.REQUIRED_PROTECTED_REFERENCE_FIELDS
    )
    assert payload["model_schemas"]["delivery_facts_receipt_target"]["required_fields"] == list(
        bridge.REQUIRED_RECEIPT_TARGET_FIELDS
    )
    assert payload["model_schemas"]["delivery_facts_readiness"]["required_fields"] == list(
        bridge.REQUIRED_READINESS_FIELDS
    )


def test_current_state_uses_four_dates_and_1600_subtotal():
    payload = _build()
    state = payload["current_captured_invoice_state"]

    assert state["performance_dates"] == bridge.CAPTURED_DATES
    assert state["show_count"] == 4
    assert state["rate_per_show"]["amount"] == 400
    assert state["subtotal"]["amount"] == 1600
    assert state["external_action_performed"] is False


def test_po_coupa_capture_block_represents_needs_discovery():
    payload = _build()
    block = payload["po_coupa_capture_block"]

    assert block["block_id"] == "proof_po_reference"
    assert block["current_status"] == "NEEDS_DISCOVERY"
    assert "enter PO/reference" in block["allowed_operator_answers"]
    assert "prepare guided Coupa/AP discovery" in block["allowed_operator_answers"]
    assert "protected_coupa_po_screen_reference" in block["supported_capture_paths"]
    assert "confirmed PO/reference" in block["missing_fields"]
    assert block["receipt_target"] == "delivery_receipt_target_po_coupa_discovery_posture"
    assert block["guardian_review_required"] is True
    assert "NEEDS_DISCOVERY" in payload["model_schemas"]["po_coupa_capture_block"]["allowed_postures"]


def test_ap_email_route_candidate_requires_confirmation():
    payload = _build()
    block = payload["ap_email_route_capture_block"]
    candidates = {candidate["address"]: candidate for candidate in block["email_route_candidates"]}

    assert block["block_id"] == "ap_email_route"
    assert block["current_status"] == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
    assert block["confirmed_recipient"] is None
    assert block["proof_reference_required"] is True
    assert "Annette.Sunga@hilton.com" in candidates
    assert candidates["Annette.Sunga@hilton.com"]["candidate_status"] == "CANDIDATE_NEEDS_OPERATOR_CONFIRMATION"
    assert "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION" in payload["model_schemas"]["ap_email_route_capture_block"][
        "allowed_postures"
    ]


def test_protected_evidence_reference_targets_are_metadata_only():
    payload = _build()
    targets = {target["target_kind"]: target for target in payload["protected_evidence_reference_targets"]}

    coupa = targets["COUPA_PO_SCREEN_REFERENCE"]
    email_thread = targets["EMAIL_THREAD_REFERENCE"]
    source_card = targets["SOURCE_CARD_REFERENCE"]
    operator_text = targets["OPERATOR_TEXT_CONFIRMATION"]

    assert coupa["hash_required"] is True
    assert coupa["path_required_if_file"] is True
    assert coupa["redaction_required"] is True
    assert coupa["guardian_review_required"] is True
    assert coupa["normal_read_model_body_allowed"] is False
    assert email_thread["normal_read_model_body_allowed"] is False
    assert source_card["normal_read_model_body_allowed"] is False
    assert operator_text["normal_read_model_body_allowed"] is False
    assert payload["machine_proof"]["normal_read_model_excludes_protected_body_content"] is True
    assert payload["machine_proof"]["guardian_review_required_for_protected_evidence"] is True


def test_forbidden_material_blocks_credentials_cookies_tokens_and_bodies():
    payload = _build()
    serialized = json.dumps(payload, sort_keys=True).lower()
    targets = payload["protected_evidence_reference_targets"]

    for target in targets:
        forbidden = target["forbidden_material"]
        assert "credential fields" in forbidden
        assert "session cookies" in forbidden
        assert "access tokens" in forbidden
        assert "base64 payloads" in forbidden
        assert "email message contents" in forbidden
    assert payload["machine_proof"]["credentials_cookies_tokens_forbidden"] is True
    assert payload["machine_proof"]["credential_material_included"] is False
    assert payload["machine_proof"]["protected_body_content_included"] is False
    assert payload["machine_proof"]["raw_screenshot_or_email_body_included"] is False
    assert "raw" + "_private_body" not in serialized
    assert "oauth" + "_token" not in serialized


def test_receipt_targets_exist_but_do_not_write():
    payload = _build()
    targets = {target["receipt_type"]: target for target in payload["delivery_facts_receipt_targets"]}

    assert "DISCOVERY_REQUIRED_RECEIPT" in targets
    assert "OPERATOR_NO_PO_KNOWN_POSTURE" in targets
    assert "OPERATOR_COUPA_REQUIRED_UNKNOWN" in targets
    assert "OPERATOR_AP_EMAIL_ROUTE_CONFIRMATION" in targets
    assert "PROTECTED_EVIDENCE_REFERENCE_RECEIPT" in targets
    for target in targets.values():
        assert target["current_write_authority"] is False
        assert target["current_external_authority"] is False
    assert payload["writer_posture"]["actual_local_receipt_state_write_performed"] is False
    assert payload["writer_posture"]["existing_safe_writer_for_delivery_facts_found"] is False
    assert payload["machine_proof"]["current_write_flags_false"] is True


def test_delivery_readiness_remains_blocked_when_facts_missing():
    payload = _build()
    readiness = payload["delivery_facts_readiness"]

    assert readiness["po_coupa_status"] == "NEEDS_DISCOVERY"
    assert readiness["ap_email_route_status"] == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
    assert readiness["email_delivery_readiness"].startswith("BLOCKED")
    assert readiness["coupa_submission_readiness"].startswith("BLOCKED")
    assert readiness["approval_readiness"] == "BLOCKED_DELIVERY_FACTS_UNRESOLVED"
    assert "PO/Coupa/payment reference posture unresolved" in readiness["remaining_blockers"]
    assert payload["machine_proof"]["email_coupa_readiness_blocked_when_required_facts_missing"] is True


def test_required_examples_exist():
    payload = _build()
    examples = payload["examples"]

    assert payload["machine_proof"]["po_unknown_needs_discovery_example_exists"] is True
    assert payload["machine_proof"]["ap_route_candidate_confirmation_example_exists"] is True
    assert payload["machine_proof"]["protected_coupa_reference_example_exists"] is True
    assert payload["machine_proof"]["operator_text_confirmation_example_exists"] is True
    assert examples["po_unknown_needs_discovery"]["current_status"] == "NEEDS_DISCOVERY"
    assert examples["ap_email_route_candidate_needs_confirmation"]["candidate"] == "Annette.Sunga@hilton.com"
    assert examples["protected_coupa_screen_reference"]["normal_read_model_body_allowed"] is False
    assert examples["protected_coupa_screen_reference"]["guardian_review_required"] is True
    assert examples["operator_text_confirmation"]["external_send"] is False
    assert examples["delivery_readiness_after_facts_captured"]["if_po_or_ap_unresolved"] == "delivery remains blocked"


def test_authority_flags_keep_external_actions_false():
    payload = _build()
    boundary = payload["authority_boundary"]

    assert boundary["local_generated_read_models_allowed"] is True
    assert boundary["local_receipt_target_modeling_allowed"] is True
    assert boundary["protected_evidence_reference_modeling_allowed"] is True
    assert boundary["local_delivery_fact_write_allowed"] is False
    for key in [
        "browser_automation_allowed",
        "coupa_access_allowed",
        "credential_handling_allowed",
        "gmail_access_allowed",
        "email_send_allowed",
        "telegram_send_allowed",
        "approval_submission_allowed",
        "model_call_allowed",
        "agent_activation_allowed",
        "tool_execution_allowed",
        "queue_execution_allowed",
        "runtime_dispatch_allowed",
        "raw_body_ingestion_allowed",
        "network_operation_allowed",
    ]:
        assert boundary[key] is False
    assert boundary["all_external_authority_false"] is True
    assert payload["machine_proof"]["all_external_authority_false"] is True


def test_no_secrets_raw_bodies_or_c_drive_paths_in_payload():
    payload = _build()
    serialized = json.dumps(payload, sort_keys=True).lower()
    forbidden_terms = [
        "api" + "_key",
        "bear" + "er ",
        "pass" + "word:",
        "sec" + "ret:",
        "session" + "_cookie",
        (Path("/mnt") / "c").as_posix() + "/",
        "c" + ":\\",
    ]
    for forbidden in forbidden_terms:
        assert forbidden not in serialized
    assert "raw" + "_private_body" not in serialized


def test_relationships_reference_existing_rails_without_duplication():
    payload = _build()
    relationships = payload["relationship_to_existing_contracts"]

    assert "capital_hilton_invoice_delivery_steel_thread" in relationships
    assert "capital_hilton_invoice_artifact_generator" in relationships
    assert "capital_hilton_protected_proof_intake" in relationships
    assert "capital_hilton_coupa_po_retrieval_automation_candidate" in relationships
    assert "guided_capture_protected_evidence_path_contract" in relationships
    assert "mission_control_capture_request_intake" in relationships


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    result = bridge.export_capital_hilton_delivery_facts_capture_bridge(
        repo_root=Path.cwd(),
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / bridge.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / bridge.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.schema_version == bridge.SCHEMA_VERSION
    assert result.current_delivery_status == "ARTIFACT_PREVIEW_READY_DELIVERY_FACTS_BLOCKED"
    assert result.po_coupa_status == "NEEDS_DISCOVERY"
    assert result.ap_email_route_status == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
    assert result.external_authority_granted is False
    assert payload["delivery_facts_readiness"]["email_delivery_readiness"].startswith("BLOCKED")
    assert "Capital Hilton Delivery Facts Capture Bridge v0" in operator
    assert "No delivery-fact receipt/state write happened" in operator
    assert export_main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--export-root",
            str(export_root),
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["po_coupa_status"] == "NEEDS_DISCOVERY"
    assert summary["external_authority_granted"] is False


def test_source_does_not_import_network_runtime_send_or_browser_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "capital_hilton_delivery_facts_capture_bridge.py",
            "scripts/export_capital_hilton_delivery_facts_capture_bridge.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
