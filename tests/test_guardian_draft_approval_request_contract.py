import ast
import json
from pathlib import Path

import guardian_draft_approval_request_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_guardian_draft_approval_request_contract import main as export_main


FIXED_NOW = "2026-05-18T15:00:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _draft_packet(path: Path, *, review_only: bool = True, gmail_draft_created: bool = False) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "cassandra_draft_review_packet_v0",
            "packet_kind": "cassandra_email_draft_review_packet",
            "packet_status": "review_only_blocked_before_send",
            "workflow_id": contract.WORKFLOW_ID,
            "workflow_name": contract.WORKFLOW_NAME,
            "draft_id": "cass_draft_review_fixture",
            "draft_status": "proposed_review_packet_not_gmail_draft",
            "review_only": review_only,
            "gmail_draft_created": gmail_draft_created,
            "email_sent": False,
        },
    )


def _send_gate(
    path: Path,
    *,
    available: bool = False,
    proof_present: bool = False,
    draft_and_attachment_present: bool = False,
) -> Path:
    evidence = {
        "coupa_invoice_proof_exists": proof_present,
        "coupa_invoice_proof_references_expected_po_invoice_context": proof_present,
        "excel_companion_invoice_artifact_exists": proof_present,
        "excel_companion_invoice_verified_to_match_coupa": proof_present,
        "cassandra_email_draft_exists": draft_and_attachment_present,
        "attachment_reference_exists": draft_and_attachment_present,
        "draft_identity_hash_reference_exists": draft_and_attachment_present,
        "attachment_identity_hash_reference_exists": draft_and_attachment_present,
        "no_unresolved_critical_blockers": available,
        "guardian_start_approval_recorded_or_required_upstream": True,
    }
    failure_reasons = []
    if not proof_present:
        failure_reasons.extend(
            [
                "missing_coupa_invoice_proof",
                "missing_coupa_expected_po_invoice_context_reference",
                "missing_excel_companion_invoice",
                "missing_excel_match_proof",
            ]
        )
    if not draft_and_attachment_present:
        failure_reasons.extend(
            [
                "missing_email_draft",
                "missing_attachment_reference",
                "missing_draft_identity_hash_reference",
                "missing_attachment_identity_hash_reference",
            ]
        )
    if not available:
        failure_reasons.append("unresolved_critical_blockers")
    return _write_json(
        path,
        {
            "schema_version": "capital_hilton_send_approval_gate_v0",
            "approval_type": "send_email_with_invoice_approval",
            "current_approval_availability_state": "available_for_guardian_send_approval"
            if available
            else "unavailable_missing_coupa_invoice_proof",
            "prerequisite_evidence_status": evidence,
            "blocker_status": {
                "approval_request_available_now": available,
                "failure_reasons": failure_reasons,
                "send_execution_available_now": False,
            },
            "upstream_start_approval_context": {
                "start_approval_separate_from_send_approval": True,
                "start_approval_authorizes_send": False,
            },
            "guardian_message_sent": False,
            "email_send_enabled": False,
        },
    )


def _guardian_dna(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "guardian_responsibility_dna_audit_v0",
            "guardian_role_summary": "Guardian is not an executor.",
            "approval_request_receipt_execution_taxonomy": {
                "review_packet": "visible proposal",
                "approval_request": "specific immutable action scope",
                "approval_receipt": "decision evidence",
                "execution": "future separately gated action path",
            },
        },
    )


def _start_approval(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "capital_hilton_coupa_start_approval_packet_v0",
            "approval_type": "start_workflow_approval",
        },
    )


def _build(tmp_path: Path, *, available: bool = False, proof_present: bool = False, draft_and_attachment_present: bool = False) -> dict:
    return contract.build_guardian_draft_approval_request_contract(
        draft_packet_json=_draft_packet(tmp_path / "draft.json"),
        send_gate_json=_send_gate(
            tmp_path / "send_gate.json",
            available=available,
            proof_present=proof_present,
            draft_and_attachment_present=draft_and_attachment_present,
        ),
        guardian_dna_json=_guardian_dna(tmp_path / "guardian_dna.json"),
        start_approval_json=_start_approval(tmp_path / "start.json"),
        generated_at=FIXED_NOW,
    )


def test_contract_is_deterministic_and_uses_canonical_shape(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["contract_kind"] == "guardian_draft_final_send_approval_request_contract"
    assert first["payload_hash_requirement"]["canonical_approval_payload_validation"]["valid"] is True
    assert set(contract.CANONICAL_PAYLOAD_REQUIRED_FIELDS).issubset(
        first["payload_hash_requirement"]["canonical_approval_payload_template"]
    )


def test_current_capital_hilton_state_is_blocked_while_proof_is_missing(tmp_path):
    payload = _build(tmp_path)

    assert payload["current_availability_status"] == contract.BLOCKED_STATUS
    assert payload["approval_request_available_now"] is False
    assert payload["status_summary"]["approval_request_created"] is False
    assert "missing_coupa_invoice_proof" in {item["blocker_id"] for item in payload["blockers"]}
    proof_status = {item["proof_key"]: item["present_now"] for item in payload["required_proof_references"]}
    assert proof_status["coupa_invoice_proof_exists"] is False
    assert proof_status["excel_companion_invoice_verified_to_match_coupa"] is False


def test_available_state_requires_proof_draft_attachment_and_clear_send_gate(tmp_path):
    payload = _build(
        tmp_path,
        available=True,
        proof_present=True,
        draft_and_attachment_present=True,
    )

    assert payload["current_availability_status"] == contract.AVAILABLE_STATUS
    assert payload["approval_request_available_now"] is True
    assert payload["blockers"] == []
    assert payload["payload_hash_requirement"]["usable_for_live_request_now"] is True
    assert payload["execution_enabled"] is False
    assert payload["approval_request_created"] is False


def test_ambiguous_or_live_draft_state_fails_closed_as_impossible(tmp_path):
    payload = contract.build_guardian_draft_approval_request_contract(
        draft_packet_json=_draft_packet(tmp_path / "draft.json", gmail_draft_created=True),
        send_gate_json=_send_gate(tmp_path / "send_gate.json"),
        guardian_dna_json=_guardian_dna(tmp_path / "guardian_dna.json"),
        start_approval_json=_start_approval(tmp_path / "start.json"),
        generated_at=FIXED_NOW,
    )

    assert payload["current_availability_status"] == contract.IMPOSSIBLE_STATUS
    assert payload["approval_request_available_now"] is False
    assert "draft_packet_has_live_external_action_state" in {item["blocker_id"] for item in payload["blockers"]}


def test_start_approval_and_final_send_approval_remain_distinct(tmp_path):
    payload = _build(tmp_path)
    relationship = payload["start_approval_relationship"]

    assert relationship["start_approval_distinct_from_final_send_approval"] is True
    assert relationship["start_approval_authorizes_send"] is False
    assert relationship["final_send_requires_separate_guardian_request"] is True
    assert relationship["start_approval_reused_as_send_approval"] is False


def test_review_request_receipt_and_execution_are_distinct(tmp_path):
    payload = _build(tmp_path)
    separation = payload["request_receipt_execution_separation"]

    assert "Cassandra draft review packet" in separation["review_packet"]
    assert "Future specific immutable Guardian request" in separation["approval_request"]
    assert "Future exact operator decision evidence" in separation["approval_receipt"]
    assert "Future separately gated send path" in separation["execution"]
    assert separation["approval_request_created_in_this_lane"] is False
    assert separation["approval_receipt_created_in_this_lane"] is False
    assert separation["execution_enabled_in_this_lane"] is False


def test_approval_scope_is_specific_and_excludes_generic_authority(tmp_path):
    payload = _build(tmp_path)
    scope = payload["approval_scope"]
    excluded = set(payload["explicitly_excluded_authorities"])

    assert scope["specific_action_scoped"] is True
    assert scope["specific_draft_required"] is True
    assert scope["specific_attachment_required"] is True
    assert scope["generic_approval_authority_allowed"] is False
    assert scope["general_email_authority_allowed"] is False
    assert "Gmail draft creation" in excluded
    assert "email send" in excluded
    assert "generic approval authority" in excluded
    assert "general runtime authority" in excluded


def test_future_receipt_type_is_required_but_no_receipt_is_created(tmp_path):
    payload = _build(tmp_path)
    receipts = payload["future_receipt_requirements"]

    assert receipts["required_future_approval_receipt_type"] == "guardian_final_send_approval_decision_receipt_v0"
    assert receipts["approval_receipt_required_before_execution"] is True
    assert receipts["receipt_created_now"] is False
    assert payload["approval_receipt_created"] is False


def test_no_send_notification_gmail_execution_or_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in contract.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["authority_boundary"][key] is expected
        assert payload["boundaries"][key] is expected
    assert payload["guardian_message_sent"] is False
    assert payload["telegram_send_triggered"] is False
    assert payload["gmail_draft_created"] is False
    assert payload["email_send_enabled"] is False
    assert payload["execution_enabled"] is False


def test_export_writes_valid_json_operator_and_cli_outputs(tmp_path, capsys):
    export_root = tmp_path / "generated/read_models"
    result = contract.export_guardian_draft_approval_request_contract(
        repo_root=tmp_path,
        export_root="generated/read_models",
        draft_packet_json=_draft_packet(tmp_path / "draft.json"),
        send_gate_json=_send_gate(tmp_path / "send_gate.json"),
        guardian_dna_json=_guardian_dna(tmp_path / "guardian_dna.json"),
        start_approval_json=_start_approval(tmp_path / "start.json"),
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.approval_request_available_now is False
    assert payload["status_summary"]["approval_request_created"] is False
    assert "Guardian Draft Approval Request Contract" in operator
    assert "Approval request created: `false`" in operator
    assert export_main(
        [
            "--repo-root",
            str(tmp_path),
            "--export-root",
            "generated/read_models",
            "--draft-packet-json",
            str(tmp_path / "draft.json"),
            "--send-gate-json",
            str(tmp_path / "send_gate.json"),
            "--guardian-dna-json",
            str(tmp_path / "guardian_dna.json"),
            "--start-approval-json",
            str(tmp_path / "start.json"),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == contract.SCHEMA_VERSION


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated/read_models"
    contract.export_guardian_draft_approval_request_contract(
        repo_root=tmp_path,
        export_root="generated/read_models",
        draft_packet_json=_draft_packet(tmp_path / "draft.json"),
        send_gate_json=_send_gate(tmp_path / "send_gate.json"),
        guardian_dna_json=_guardian_dna(tmp_path / "guardian_dna.json"),
        start_approval_json=_start_approval(tmp_path / "start.json"),
        generated_at=FIXED_NOW,
    )
    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_send_execute_import_repo_b_or_touch_external_surfaces():
    source_files = [
        Path("guardian_draft_approval_request_contract.py"),
        Path("scripts/export_guardian_draft_approval_request_contract.py"),
    ]
    forbidden = [
        "/home/openclaw_external/openclaw-runtime",
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "send_message",
        "reply_text",
        "smtplib",
        "imaplib",
        "oauthlib",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
        "shell=True",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token.lower() not in text

    tree = ast.parse(Path("guardian_draft_approval_request_contract.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
