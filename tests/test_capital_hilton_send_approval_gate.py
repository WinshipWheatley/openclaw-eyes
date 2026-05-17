import ast
import json
from pathlib import Path

import capital_hilton_send_approval_gate as gate
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_capital_hilton_send_approval_gate import main as export_main


FIXED_NOW = "2026-05-17T22:40:00+00:00"


def _write_execution_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "capital_hilton_coupa_execution_path_v0",
                "overlay_scope": "Capital Hilton / Hilton only",
                "status_summary": {
                    "send_approval_blocked_until_coupa_proof_exists": True,
                    "send_approval_blocked_until_excel_match_verified": True,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_start_approval(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "capital_hilton_coupa_start_approval_packet_v0",
                "approval_type": "start_workflow_approval",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_power_stage(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "operator_sovereignty_power_stage_gate_read_model_v0",
                "current_power_stage": {
                    "current_power_stage_id": "stage_1_visibility_read_model_review_packet"
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _build(tmp_path: Path, evidence: dict[str, bool] | None = None) -> dict:
    return gate.build_capital_hilton_send_approval_gate(
        execution_path_json=_write_execution_path(tmp_path / "execution.json"),
        start_approval_json=_write_start_approval(tmp_path / "start.json"),
        power_stage_json=_write_power_stage(tmp_path / "power.json"),
        prerequisite_evidence=evidence,
        generated_at=FIXED_NOW,
    )


def test_send_approval_spec_is_deterministic(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert gate.stable_json(first) == gate.stable_json(second)
    assert first["schema_version"] == gate.SCHEMA_VERSION
    assert first["approval_type"] == "send_email_with_invoice_approval"
    assert first["workflow"] == gate.WORKFLOW_ID
    assert first["packet_status"] == "review_only_spec_not_dispatched"
    assert first["canonical_approval_payload_validation"]["valid"] is True


def test_generic_final_send_approval_contract_exists_and_is_reused(tmp_path):
    payload = _build(tmp_path)
    contract = payload["generic_final_send_approval_contract"]

    assert contract["contract_id"] == gate.GENERIC_CONTRACT_ID
    assert contract["reusable_for_future_outward_email_workflows"] is True
    assert "draft_identity" in contract["required_fields"]
    assert "attachment_identity" in contract["required_fields"]
    assert "prerequisite_evidence" in contract["required_fields"]
    assert payload["generic_final_send_approval_contract_added"] is True
    assert payload["post_preflight_batch_gate_result"]["gate_status"] == "pass"


def test_send_approval_is_unavailable_without_coupa_invoice_proof(tmp_path):
    payload = _build(tmp_path)

    assert payload["current_approval_availability_state"] == "unavailable_missing_coupa_invoice_proof"
    assert "missing_coupa_invoice_proof" in payload["blocker_status"]["failure_reasons"]
    assert payload["status_summary"]["send_approval_blocked_until_coupa_proof_exists"] is True


def test_send_approval_is_unavailable_without_excel_match_proof(tmp_path):
    evidence = {
        "coupa_invoice_proof_exists": True,
        "coupa_invoice_proof_references_expected_po_invoice_context": True,
        "excel_companion_invoice_artifact_exists": True,
        "excel_companion_invoice_verified_to_match_coupa": False,
    }
    payload = _build(tmp_path, evidence=evidence)

    assert payload["current_approval_availability_state"] == "unavailable_missing_excel_match_proof"
    assert "missing_excel_match_proof" in payload["blocker_status"]["failure_reasons"]
    assert payload["status_summary"]["send_approval_blocked_until_excel_match_verified"] is True


def test_send_approval_is_unavailable_without_specific_draft_and_attachment(tmp_path):
    evidence = {
        "coupa_invoice_proof_exists": True,
        "coupa_invoice_proof_references_expected_po_invoice_context": True,
        "excel_companion_invoice_artifact_exists": True,
        "excel_companion_invoice_verified_to_match_coupa": True,
        "cassandra_email_draft_exists": False,
        "attachment_reference_exists": False,
        "no_unresolved_critical_blockers": True,
    }
    payload = _build(tmp_path, evidence=evidence)

    assert payload["current_approval_availability_state"] == "unavailable_missing_email_draft"
    assert "missing_email_draft" in payload["blocker_status"]["failure_reasons"]
    assert "missing_attachment_reference" in payload["blocker_status"]["failure_reasons"]
    assert payload["draft_identity"]["draft_present_now"] is False
    assert payload["attachment_identity"]["attachment_present_now"] is False


def test_send_approval_is_specific_to_one_draft_and_one_attachment(tmp_path):
    payload = _build(tmp_path)

    assert payload["target_action"]["specific_to_draft_and_attachment"] is True
    assert payload["approval_scope"]["specific_to_one_draft_and_one_attachment"] is True
    assert payload["approval_scope"]["creates_general_email_authority"] is False
    assert payload["canonical_approval_payload_candidate"]["action_class"] == "email_send"
    assert payload["canonical_approval_payload_candidate"]["explicit_authorized_packet_ref"]


def test_available_state_can_be_modeled_without_executable_send_authority(tmp_path):
    payload = _build(tmp_path, evidence={key: True for key in gate.PREREQUISITE_KEYS})

    assert payload["current_approval_availability_state"] == "available_for_guardian_send_approval"
    assert payload["blocker_status"]["approval_request_available_now"] is True
    assert payload["blocker_status"]["send_execution_available_now"] is False
    assert payload["send_approval_executable"] is False
    assert payload["authority_boundary"]["send_execution_requires_future_stage_4_controls"] is True


def test_send_approval_does_not_authorize_coupa_browser_credentials_spreadsheet_payment_or_runtime(tmp_path):
    payload = _build(tmp_path)
    blocked = set(payload["explicitly_blocked_authorities"])

    assert "Coupa submit" in blocked
    assert "browser automation" in blocked
    assert "credential/PII access" in blocked
    assert "spreadsheet writes" in blocked
    assert "payment status change" in blocked
    assert "general email authority" in blocked
    assert "general runtime authority" in blocked
    assert payload["email_send_enabled"] is False
    assert payload["coupa_browser_automation_enabled"] is False
    assert payload["coupa_submit_enabled"] is False
    assert payload["spreadsheet_write_enabled"] is False
    assert payload["credential_or_pii_access_enabled"] is False
    assert payload["runtime_authority_added"] is False


def test_guardian_start_approval_remains_distinct_from_send_approval(tmp_path):
    payload = _build(tmp_path)
    relationship = payload["guardian_start_approval_relationship"]

    assert relationship["start_approval_distinct_from_send_approval"] is True
    assert relationship["start_approval_does_not_authorize_send"] is True
    assert relationship["start_approval_required_upstream"] is True
    assert payload["upstream_start_approval_context"]["start_approval_authorizes_send"] is False


def test_existing_cassandra_guardian_machinery_is_inspected_not_rebuilt_or_activated(tmp_path):
    payload = _build(tmp_path)
    discovery = payload["existing_email_approval_machinery_discovery"]
    surface_paths = {item["path"] for item in discovery["surfaces"]}

    assert discovery["existing_cassandra_guardian_email_approval_inspected"] is True
    assert discovery["machinery_found"] is True
    assert discovery["existing_machinery_rebuilt_in_this_lane"] is False
    assert discovery["existing_machinery_activated_in_this_lane"] is False
    assert discovery["later_send_approval_should_reuse_or_detangle_existing_pattern"] is True
    assert "cassandra_outreach.py" in surface_paths
    assert "chief_guardian_sender.py" in surface_paths
    assert "templates/agent/cassandra_outreach_draft_packet_template.json" in surface_paths


def test_no_raw_secrets_pii_or_authority_are_stored_or_added(tmp_path):
    payload = _build(tmp_path)
    text = json.dumps(payload).lower()

    for key, expected in gate.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["boundaries"][key] is expected
        assert payload["authority_boundary"]["no_authority_flags"][key] is expected
    assert "@hilton.com" not in text
    assert "1009 smithville" not in text
    assert "password is" not in text
    assert "token=" not in text


def test_export_writes_valid_json_operator_and_cli_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    result = gate.export_capital_hilton_send_approval_gate(
        execution_path_json=_write_execution_path(tmp_path / "execution.json"),
        start_approval_json=_write_start_approval(tmp_path / "start.json"),
        power_stage_json=_write_power_stage(tmp_path / "power.json"),
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / gate.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / gate.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.send_approval_packet_modeled is True
    assert result.generic_final_send_approval_contract_added is True
    assert result.send_approval_executable is False
    assert payload["status_summary"]["send_approval_packet_modeled"] is True
    assert "Capital Hilton Send Approval Gate" in operator_text
    assert export_main(
        [
            "--execution-path-json",
            str(tmp_path / "execution.json"),
            "--start-approval-json",
            str(tmp_path / "start.json"),
            "--power-stage-json",
            str(tmp_path / "power.json"),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == gate.SCHEMA_VERSION


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    gate.export_capital_hilton_send_approval_gate(
        execution_path_json=_write_execution_path(tmp_path / "execution.json"),
        start_approval_json=_write_start_approval(tmp_path / "start.json"),
        power_stage_json=_write_power_stage(tmp_path / "power.json"),
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert gate.JSON_EXPORT_NAME in expected
    assert gate.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_send_execute_import_repo_b_or_touch_browser_spreadsheet():
    source_files = [
        Path("capital_hilton_send_approval_gate.py"),
        Path("scripts/export_capital_hilton_send_approval_gate.py"),
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
        "shell=True",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text

    tree = ast.parse(Path("capital_hilton_send_approval_gate.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
