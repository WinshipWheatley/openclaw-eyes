import ast
import json
from pathlib import Path

import capital_hilton_coupa_start_approval_packet as packet
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_capital_hilton_coupa_start_approval_packet import main as export_main


FIXED_NOW = "2026-05-17T23:05:00+00:00"


def _write_execution_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "capital_hilton_coupa_execution_path_v0",
                "overlay_scope": "Capital Hilton / Hilton only",
                "status_summary": {
                    "guardian_start_approval_modeled": True,
                    "guardian_send_approval_modeled": True,
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


def _build(tmp_path: Path) -> dict:
    return packet.build_capital_hilton_coupa_start_approval_packet(
        execution_path_json=_write_execution_path(tmp_path / "execution_path.json"),
        generated_at=FIXED_NOW,
    )


def test_start_approval_packet_is_deterministic(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert packet.stable_json(first) == packet.stable_json(second)
    assert first["schema_version"] == packet.SCHEMA_VERSION
    assert first["approval_type"] == "start_workflow_approval"
    assert first["workflow"] == "capital_hilton_coupa_supplier_portal_invoice"
    assert first["packet_status"] == "review_only_spec_not_dispatched"
    assert first["canonical_approval_payload_validation"]["valid"] is True


def test_start_approval_authorizes_only_preparation_scope(tmp_path):
    payload = _build(tmp_path)
    scope = payload["authorization_scope"]

    assert "begin governed workflow preparation" in scope["what_start_approval_authorizes"]
    assert "verify current Capital Hilton facts/read-models" in scope["what_start_approval_authorizes"]
    assert scope["preparation_scope_only"] is True
    assert scope["external_action_authorized"] is False
    assert scope["send_approval_created"] is False
    assert scope["runtime_authority_created"] is False


def test_start_approval_does_not_authorize_coupa_browser_credentials_email_or_spreadsheet(tmp_path):
    payload = _build(tmp_path)
    blocked = set(payload["blocked_authorities"])

    assert "Coupa submit" in blocked
    assert "browser automation" in blocked
    assert "credential/PII access" in blocked
    assert "Excel or spreadsheet write" in blocked
    assert "email send" in blocked
    assert "payment status change" in blocked
    assert payload["coupa_submit_enabled"] is False
    assert payload["coupa_browser_automation_enabled"] is False
    assert payload["credential_or_pii_access_enabled"] is False
    assert payload["email_send_enabled"] is False
    assert payload["spreadsheet_write_enabled"] is False


def test_downstream_gates_remain_required_after_start_packet(tmp_path):
    payload = _build(tmp_path)
    gates = {item["gate_id"]: item for item in payload["required_downstream_gates"]}

    assert set(gates) == set(packet.DOWNSTREAM_GATE_IDS)
    assert gates["credential_pii_access_gate"]["satisfied_now"] is False
    assert gates["browser_automation_scope_gate"]["authority_granted_by_start_approval"] is False
    assert gates["coupa_submit_gate"]["authority_granted_by_start_approval"] is False
    assert gates["coupa_invoice_proof_capture_gate"]["required_after_start_approval"] is True
    assert gates["excel_companion_invoice_generation_match_gate"]["required_after_start_approval"] is True
    assert gates["guardian_send_approval_gate"]["required_after_start_approval"] is True
    assert gates["money_ledger_payment_verification_gate"]["required_after_start_approval"] is True


def test_guardian_send_approval_remains_separate_and_blocked(tmp_path):
    payload = _build(tmp_path)
    relationship = payload["guardian_send_approval_relationship"]

    assert relationship["separate_packet_required"] is True
    assert relationship["start_approval_does_not_authorize_send"] is True
    assert relationship["send_approval_currently_available"] is False
    assert relationship["send_approval_blocked_until_coupa_proof_exists"] is True
    assert relationship["send_approval_blocked_until_excel_match_verified"] is True


def test_existing_cassandra_guardian_email_approval_machinery_is_inspected_not_rebuilt(tmp_path):
    payload = _build(tmp_path)
    discovery = payload["existing_email_approval_machinery_discovery"]
    surface_paths = {item["path"] for item in discovery["surfaces"]}

    assert discovery["existing_cassandra_guardian_email_approval_inspected"] is True
    assert discovery["machinery_found"] is True
    assert discovery["existing_machinery_rebuilt_in_this_lane"] is False
    assert discovery["later_send_approval_should_reuse_or_detangle_existing_pattern"] is True
    assert discovery["start_approval_remains_separate_from_later_send_approval"] is True
    assert "templates/agent/guardian_approval_request_packet_template.json" in surface_paths
    assert "templates/agent/cassandra_outreach_draft_packet_template.json" in surface_paths
    assert "cassandra_outreach.py" in surface_paths
    assert "chief_guardian_sender.py" in surface_paths
    assert payload["status_summary"]["rebuild_existing_email_approval_machinery"] is False


def test_reusable_approval_pattern_is_advisory_read_model_only(tmp_path):
    payload = _build(tmp_path)
    pattern = payload["reusable_approval_pattern"]

    assert pattern["pattern_id"] == "guardian_external_workflow_start_approval_packet"
    assert pattern["reusable_later"] is True
    assert pattern["approval_packet_not_execution_packet"] is True
    assert "approval_type" in pattern["required_fields"]
    assert "authority_boundary" in pattern["required_fields"]
    assert payload["approval_request_persisted"] is False
    assert payload["start_approval_executable"] is False


def test_no_raw_secrets_pii_or_authority_are_stored_or_added(tmp_path):
    payload = _build(tmp_path)
    text = json.dumps(payload).lower()

    assert payload["raw_secret_or_pii_stored"] is False
    assert payload["guardian_message_sent"] is False
    assert payload["telegram_send_triggered"] is False
    assert payload["gmail_or_email_send_triggered"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["approval_authority_added"] is False
    assert "@hilton.com" not in text
    assert "1009 smithville" not in text
    assert "password is" not in text
    assert "token=" not in text


def test_no_authority_flags_are_exposed_at_top_level_and_boundary(tmp_path):
    payload = _build(tmp_path)

    for key, expected in packet.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["boundaries"][key] is expected
        assert payload["authority_boundary"]["no_authority_flags"][key] is expected


def test_export_writes_valid_json_operator_and_cli_outputs(tmp_path, capsys):
    execution_path = _write_execution_path(tmp_path / "execution_path.json")
    export_root = tmp_path / "read_models"

    result = packet.export_capital_hilton_coupa_start_approval_packet(
        execution_path_json=execution_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / packet.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / packet.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.start_approval_packet_modeled is True
    assert result.start_approval_executable is False
    assert payload["status_summary"]["start_approval_packet_modeled"] is True
    assert "Capital Hilton Coupa Start Approval Packet" in operator_text
    assert "Start approval remains separate from send approval" in operator_text
    assert export_main(
        [
            "--execution-path-json",
            str(execution_path),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == packet.SCHEMA_VERSION


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    packet.export_capital_hilton_coupa_start_approval_packet(
        execution_path_json=_write_execution_path(tmp_path / "execution_path.json"),
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert packet.JSON_EXPORT_NAME in expected
    assert packet.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_send_execute_import_repo_b_or_touch_browser_spreadsheet():
    source_files = [
        Path("capital_hilton_coupa_start_approval_packet.py"),
        Path("scripts/export_capital_hilton_coupa_start_approval_packet.py"),
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

    tree = ast.parse(Path("capital_hilton_coupa_start_approval_packet.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
