import ast
import json
from pathlib import Path

import cassandra_email_calendar_capability_reconciliation as recon
from scripts.export_cassandra_email_calendar_capability_reconciliation import main as export_main

FIXED_NOW = "2026-05-18T12:00:00+00:00"


def _by_id(payload):
    return {item["capability_id"]: item for item in payload["classification_map"]}


def test_reconciliation_is_deterministic_and_review_only():
    first = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    second = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    assert recon.stable_json(first) == recon.stable_json(second)
    assert first["schema_version"] == recon.SCHEMA_VERSION
    assert first["status"] == "reconciled_review_only_no_live_authority"
    assert first["read_model_only"] is True
    assert first["audit_only"] is True


def test_existing_capabilities_are_classified_for_bridge_or_block():
    payload = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    by_id = _by_id(payload)
    assert by_id["cassandra_metadata_email_triage"]["classification"] == "KEEP_AND_BRIDGE"
    assert by_id["cassandra_outreach_draft_era"]["classification"] == "KEEP_AS_REFERENCE"
    assert by_id["cassandra_brain_email_calendar_intents"]["classification"] == "KEEP_AS_REFERENCE"
    assert by_id["google_access_broker_email_calendar_surface"]["classification"] == "UNSAFE_OR_BLOCKED"
    assert by_id["cassandra_send_status_dry_run"]["classification"] == "KEEP_AND_BRIDGE"
    assert by_id["guardian_specific_approval_contracts"]["classification"] == "KEEP_AND_BRIDGE"


def test_no_live_gmail_calendar_oauth_send_or_mutation_authority_is_enabled():
    payload = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    assert payload["live_gmail_read_enabled"] is False
    assert payload["live_calendar_read_enabled"] is False
    assert payload["gmail_draft_creation_enabled"] is False
    assert payload["email_send_enabled"] is False
    assert payload["calendar_mutation_enabled"] is False
    assert payload["oauth_or_credentials_accessed"] is False
    assert payload["browser_automation_added"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["approval_authority_added"] is False


def test_repo_b_is_reference_only_and_not_executed():
    payload = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    repo_b = payload["searched_locations"]["repo_b"]
    by_id = _by_id(payload)
    assert repo_b["inspection_status"] == "not_inspected_repo_a_sufficient"
    assert repo_b["reference_only_if_future_lane_needs_it"] is True
    assert repo_b["executed"] is False
    assert repo_b["imported"] is False
    assert payload["repo_b_executed"] is False
    assert by_id["repo_b_runtime_reference"]["safe_reuse_path"].startswith("Leave uninspected")


def test_calendar_cleanup_is_not_started_generically():
    payload = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    calendar = payload["calendar_policy"]
    assert calendar["generic_cleanup_started"] is False
    assert calendar["normalization_allowed_only_when_workflow_needs_context"] is True
    assert calendar["live_calendar_access_enabled"] is False
    assert payload["generic_calendar_cleanup_started"] is False
    assert "generic_calendar_cleanup" in payload["blocked_until_future_gated_lane"]


def test_approval_remains_specific_action_scoped_and_execution_is_later():
    payload = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    phases = {item["phase"]: item for item in payload["safe_forward_path"]}
    assert phases["operator_intent"]["allowed_now"] is True
    assert phases["governed_intake"]["allowed_now"] is True
    assert phases["draft_review_packet"]["allowed_now"] is True
    assert phases["guardian_approval_request"]["allowed_now"] is False
    assert phases["specific_approval_receipt"]["allowed_now"] is False
    assert phases["gated_send_or_calendar_action"]["allowed_now"] is False
    assert payload["approval_policy"]["approval_scope"] == "specific_draft_or_calendar_action_only"
    assert payload["approval_policy"]["blanket_approval_allowed"] is False
    assert payload["approval_policy"]["cassandra_executor"] is False


def test_output_distinguishes_draft_review_approval_and_execution():
    payload = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    phases = [item["phase"] for item in payload["safe_forward_path"]]
    assert phases == [
        "operator_intent",
        "governed_intake",
        "facts_context_read_models",
        "draft_review_packet",
        "guardian_approval_request",
        "specific_approval_receipt",
        "gated_send_or_calendar_action",
    ]
    assert payload["receipt_proof_status"]["draft_review_approval_execution_distinguished"] is True


def test_unknown_capability_fails_closed():
    payload = recon.build_cassandra_email_calendar_capability_reconciliation(generated_at=FIXED_NOW)
    unknown = _by_id(payload)["unknown_email_calendar_capability"]
    assert unknown["classification"] == "UNKNOWN_NEEDS_REVIEW"
    assert "Fails closed" in unknown["steel_thread_fit"]
    assert payload["approval_policy"]["fail_closed_when_identity_scope_or_authority_unclear"] is True


def test_export_writes_json_operator_and_cli(tmp_path, capsys):
    result = recon.export_cassandra_email_calendar_capability_reconciliation(repo_root=tmp_path, export_root="generated/read_models", generated_at=FIXED_NOW)
    json_path = tmp_path / "generated/read_models" / recon.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated/read_models" / recon.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert result.status == "reconciled_review_only_no_live_authority"
    assert payload["receipt_proof_status"]["live_gmail_calendar_authority_enabled"] is False
    assert "Cassandra Email + Calendar Capability Reconciliation v0" in operator
    assert "Live Gmail/calendar/send/calendar mutation authority enabled: `false`" in operator
    assert export_main(["--repo-root", str(tmp_path), "--export-root", "generated/read_models", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "reconciled_review_only_no_live_authority"


def test_source_does_not_import_or_call_forbidden_live_authority():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "cassandra_email_calendar_capability_reconciliation.py",
            "scripts/export_cassandra_email_calendar_capability_reconciliation.py",
        ]
    )
    forbidden_tokens = [
        "google_access_broker import",
        "broker_call(",
        "smtplib",
        "imaplib",
        "poplib",
        "import oauth",
        "oauthlib",
        "subprocess",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "webbrowser",
        "selenium",
        "playwright",
        "repo_b_runtime_authority_added\": true",
        "email_send_enabled\": true",
        "calendar_mutation_enabled\": true",
    ]
    for token in forbidden_tokens:
        assert token not in source


def test_write_calls_are_limited_to_generated_read_model_exports():
    tree = ast.parse(Path("cassandra_email_calendar_capability_reconciliation.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]
    assert len(write_calls) == 2
