import ast
import json
from pathlib import Path

import capital_hilton_coupa_execution_path as execution_path
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_capital_hilton_coupa_execution_path import main as export_main


FIXED_NOW = "2026-05-17T21:00:00+00:00"


def _write_two_invoice_workflow(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "capital_hilton_two_invoice_workflow_v0",
                "status_summary": {
                    "base_invoice_workflow_preserved": True,
                    "hilton_coupa_overlay_modeled": True,
                    "coupa_payment_invoice_modeled": True,
                    "excel_companion_invoice_modeled": True,
                    "po_budget_context_modeled": True,
                    "protected_evidence_slots_modeled": True,
                    "hilton_two_invoice_flow_generalized_to_all_clients": False,
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
    return execution_path.build_capital_hilton_coupa_execution_path(
        two_invoice_workflow_path=_write_two_invoice_workflow(tmp_path / "two_invoice.json"),
        generated_at=FIXED_NOW,
    )


def test_end_to_end_hilton_path_phases_and_gates_are_modeled(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == execution_path.SCHEMA_VERSION
    assert payload["status_summary"]["end_to_end_hilton_workflow_modeled"] is True
    assert payload["execution_phase_ids"] == list(execution_path.EXECUTION_PHASE_IDS)
    assert payload["required_gate_ids"] == list(execution_path.REQUIRED_GATE_IDS)
    assert payload["readiness_summary"]["execution_ready_now"] is False
    assert payload["readiness_summary"]["modeled_not_enabled"] is True


def test_base_invoice_workflow_remains_simple_and_overlay_is_hilton_only(tmp_path):
    payload = _build(tmp_path)
    base = payload["base_invoice_workflow"]
    overlay = payload["client_specific_invoice_overlay"]
    policy = payload["overlay_adapter_policy"]

    assert base["workflow_id"] == "base_invoice_workflow"
    assert base["simple_default_preserved"] is True
    assert base["assumes_coupa"] is False
    assert base["assumes_two_invoices"] is False
    assert base["assumes_two_guardian_approvals"] is False
    assert overlay["overlay_id"] == "hilton_coupa_supplier_portal"
    assert overlay["overlay_scope"] == "Capital Hilton / Hilton only"
    assert overlay["applies_to_all_clients"] is False
    assert overlay["generalized_to_all_clients"] is False
    assert policy["default_invoice_architecture"] == "simple_base_invoice_workflow"
    assert policy["client_specific_complexity_extension"] == "overlay_or_adapter_only"
    assert policy["hilton_complexity_becomes_default"] is False
    assert "protected_sensitive_data_requirements" in policy["future_client_specific_overlays_should_reuse"]
    assert "base invoice workflow" in policy["migration_rule"]
    assert payload["status_summary"]["hilton_overlay_scoped_only_to_hilton"] is True


def test_cassandra_is_intake_not_executor_and_roles_are_explicit(tmp_path):
    payload = _build(tmp_path)
    actors = {item["actor_id"]: item for item in payload["actors_and_roles"]}

    assert actors["cassandra"]["role"] == "telegram_intake_and_outward_comms_participant"
    assert actors["cassandra"]["executor"] is False
    assert actors["cassandra"]["can_send_now"] is False
    assert actors["local_mac_execution_agent"]["executor"] == "future_blocked"
    assert actors["protected_secret_pii_broker"]["executor"] == "future_blocked"
    assert payload["status_summary"]["cassandra_modeled_as_intake_not_executor"] is True


def test_two_guardian_approvals_are_distinct_and_start_does_not_authorize_send(tmp_path):
    payload = _build(tmp_path)
    approvals = {item["approval_request_id"]: item for item in payload["guardian_approval_requests"]}

    assert set(approvals) == {"start_workflow_approval", "send_email_with_invoice_approval"}
    start = approvals["start_workflow_approval"]
    send = approvals["send_email_with_invoice_approval"]
    assert start["authorizes_workflow_start"] is True
    assert start["authorizes_email_send"] is False
    assert start["authorizes_final_external_communication"] is False
    assert start["authorizes_coupa_submit"] is False
    assert send["authorizes_email_send"] is True
    assert send["approval_scope"] == "specific_draft_email_and_attachment_only"
    assert send["authorizes_general_send"] is False
    assert send["creates_general_send_authority"] is False


def test_send_approval_is_blocked_until_coupa_proof_and_excel_match_exist(tmp_path):
    payload = _build(tmp_path)
    send = next(
        item
        for item in payload["guardian_approval_requests"]
        if item["approval_request_id"] == "send_email_with_invoice_approval"
    )
    preconditions = payload["send_approval_preconditions"]

    assert send["available_now"] is False
    assert send["requires_coupa_invoice_proof_in_sqlite"] is True
    assert send["requires_excel_match_proof"] is True
    assert preconditions["send_approval_blocked_until_coupa_proof_exists"] is True
    assert preconditions["send_approval_blocked_until_excel_match_verified"] is True
    assert preconditions["general_send_authority_created"] is False


def test_protected_broker_is_future_blocked_and_raw_secrets_or_pii_are_not_stored(tmp_path):
    payload = _build(tmp_path)
    protected = payload["protected_sensitive_data_requirements"]
    text = json.dumps(payload).lower()

    assert protected["protected_secret_pii_broker_modeled"] is True
    assert protected["active_now"] is False
    assert protected["raw_values_stored_in_repo_or_read_models"] is False
    assert all(item["raw_value_stored"] is False for item in protected["protected_value_classes"])
    assert payload["raw_secret_or_pii_stored"] is False
    assert "@hilton.com" not in text
    assert "1009 smithville" not in text
    assert "password is" not in text
    assert "token=" not in text


def test_proof_artifacts_include_coupa_excel_guardian_email_and_payment_chain(tmp_path):
    payload = _build(tmp_path)
    artifacts = {item["artifact_id"]: item for item in payload["proof_artifacts"]}

    assert "start_approval_receipt" in artifacts
    assert "coupa_invoice_proof_download_reference" in artifacts
    assert "excel_invoice_artifact_reference" in artifacts
    assert "coupa_vs_excel_match_proof" in artifacts
    assert "cassandra_email_draft_record" in artifacts
    assert "guardian_send_approval_receipt" in artifacts
    assert "email_send_receipt_future_only" in artifacts
    assert "payment_expectation_record" in artifacts
    assert artifacts["money_ledger_payment_match"]["artifact_status"] == "future_required_for_paid_status"
    assert artifacts["check_deposit_proof_protected_artifact"]["protected"] is True


def test_no_execution_send_submit_spreadsheet_browser_or_runtime_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in execution_path.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["boundaries"][key] is expected
    assert payload["coupa_browser_automation_enabled"] is False
    assert payload["coupa_submit_enabled"] is False
    assert payload["email_send_enabled"] is False
    assert payload["spreadsheet_write_enabled"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False


def test_export_writes_valid_json_operator_and_cli_outputs(tmp_path, capsys):
    two_invoice_path = _write_two_invoice_workflow(tmp_path / "two_invoice.json")
    export_root = tmp_path / "read_models"

    result = execution_path.export_capital_hilton_coupa_execution_path(
        two_invoice_workflow_path=two_invoice_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / execution_path.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / execution_path.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.end_to_end_hilton_workflow_modeled is True
    assert payload["status_summary"]["guardian_start_approval_modeled"] is True
    assert "Capital Hilton Coupa Execution Path Contract" in operator_text
    assert "specific draft email and attachment" in operator_text
    assert export_main(
        [
            "--two-invoice-workflow-json",
            str(two_invoice_path),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == execution_path.SCHEMA_VERSION


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    execution_path.export_capital_hilton_coupa_execution_path(
        two_invoice_workflow_path=_write_two_invoice_workflow(tmp_path / "two_invoice.json"),
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert execution_path.JSON_EXPORT_NAME in expected
    assert execution_path.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_execute_repo_b_send_submit_browser_spreadsheet_or_subprocess():
    source_files = [
        Path("capital_hilton_coupa_execution_path.py"),
        Path("scripts/export_capital_hilton_coupa_execution_path.py"),
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

    tree = ast.parse(Path("capital_hilton_coupa_execution_path.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
