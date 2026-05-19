import ast
import json
from pathlib import Path

import cassandra_email_calendar_delta_detangle as detangle
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_cassandra_email_calendar_delta_detangle import main as export_main


FIXED_NOW = "2026-05-19T04:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "cassandra_email_calendar_capability_reconciliation.json": {
            "schema_version": "cassandra_email_calendar_capability_reconciliation_v0",
            "status": "reconciled_review_only_no_live_authority",
            "blocked_until_future_gated_lane": ["live_gmail_read", "google_calendar_read", "oauth_or_credential_access"],
            "calendar_policy": {"generic_cleanup_started": False, "live_calendar_access_enabled": False},
        },
        "cassandra_draft_review_packet.json": {
            "schema_version": "cassandra_draft_review_packet_v0",
            "packet_status": "review_only_blocked_before_send",
            "gmail_draft_created": False,
            "email_sent": False,
        },
        "cassandra_send_status_dry_run.json": {
            "schema_version": "cassandra_send_status_dry_run_v0",
            "telegram_send_triggered": False,
            "gmail_or_email_send_triggered": False,
        },
        "cassandra_governed_review_packet_request_proof.json": {
            "schema_version": "cassandra_governed_review_packet_request_proof_v0",
            "review_only": True,
        },
        "guardian_draft_approval_request_contract.json": {
            "schema_version": "guardian_draft_approval_request_contract_v0",
            "current_availability_status": "blocked_unavailable_missing_prerequisites",
            "gmail_draft_created": False,
        },
        "protected_access_broker_concept.json": {
            "schema_version": "protected_access_broker_concept_v0",
            "live_access_blocked": True,
        },
        "protected_evidence_reference_receipt.json": {
            "schema_version": "protected_evidence_reference_receipt_v0",
            "receipt_records": [],
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "current_availability_status": "protected_access_blocked_now",
        },
        "capability_skill_registry_metadata_delta.json": {
            "schema_version": "capability_skill_registry_metadata_delta_v0",
            "registry_delta_status": "metadata_only_capability_skill_registry_delta",
            "repo_b_code_executed": False,
        },
        "repo_b_remaining_capability_delta_map.json": {
            "schema_version": "repo_b_remaining_capability_delta_map_v0",
            "repo_b_reference_only": True,
            "repo_b_code_executed": False,
        },
        "tool_inventory.json": {"read_model_version": "local_tool_inventory_read_model_v0"},
        "tool_intake.json": {"read_model_version": "tool_intake_read_model_v0"},
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    root = tmp_path / "repo_a"
    _fixture_repo(root)
    return detangle.build_cassandra_email_calendar_delta_detangle(repo_root=root, generated_at=FIXED_NOW)


def _surface(payload: dict, surface_id: str) -> dict:
    return next(item for item in payload["detangled_surfaces"] if item["surface_id"] == surface_id)


def test_detangle_read_model_is_deterministic_and_classification_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert detangle.stable_json(first) == detangle.stable_json(second)
    assert first["schema_version"] == detangle.SCHEMA_VERSION
    assert first["detangle_status"] == "classification_only_no_live_authority"
    assert first["classification_only"] is True
    assert first["repo_b_filesystem_inspected"] is False
    assert first["repo_b_code_executed"] is False


def test_surfaces_are_classified_into_review_notification_live_calendar_and_fail_closed(tmp_path):
    payload = _build(tmp_path)
    surfaces = {item["surface_id"]: item for item in payload["detangled_surfaces"]}

    assert surfaces["governed_cassandra_review_packet_path"]["primary_classification"] == "GOVERNED_REVIEW_PACKET_READY"
    assert surfaces["cassandra_draft_preview_packet"]["primary_classification"] == "DRAFT_PREVIEW_ONLY"
    assert surfaces["telegram_operator_notification_path"]["primary_classification"] == "TELEGRAM_NOTIFICATION_SEPARATE"
    assert surfaces["gmail_live_account_access"]["primary_classification"] == "LIVE_GMAIL_BLOCKED"
    assert surfaces["email_send_and_gmail_draft_creation"]["primary_classification"] == "EMAIL_SEND_BLOCKED"
    assert surfaces["calendar_discovery_understanding"]["primary_classification"] == "CALENDAR_DISCOVERY_BLOCKED"
    assert surfaces["calendar_normalization_future"]["primary_classification"] == "CALENDAR_NORMALIZATION_FUTURE"
    assert surfaces["oauth_credential_tool_browser_bridges"]["primary_classification"] == "OAUTH_CREDENTIAL_BLOCKED"
    assert surfaces["legacy_repo_b_email_calendar_delta"]["primary_classification"] == "LEGACY_REFERENCE_ONLY"
    assert surfaces["unknown_email_calendar_surface"]["primary_classification"] == "UNKNOWN_FAIL_CLOSED"


def test_no_live_gmail_calendar_oauth_drafts_sends_or_calendar_mutations_are_enabled(tmp_path):
    payload = _build(tmp_path)

    assert payload["live_gmail_access_enabled"] is False
    assert payload["live_google_calendar_access_enabled"] is False
    assert payload["live_apple_calendar_access_enabled"] is False
    assert payload["oauth_or_credentials_accessed"] is False
    assert payload["gmail_draft_created"] is False
    assert payload["email_send_triggered"] is False
    assert payload["calendar_mutation_triggered"] is False
    assert payload["browser_automation_added"] is False
    assert payload["tools_enabled"] is False
    assert payload["agents_activated"] is False


def test_telegram_notification_behavior_is_separate_and_unchanged(tmp_path):
    payload = _build(tmp_path)
    telegram = _surface(payload, "telegram_operator_notification_path")
    boundary = payload["mission_control_vs_telegram_boundary"]

    assert telegram["primary_classification"] == "TELEGRAM_NOTIFICATION_SEPARATE"
    assert telegram["telegram_notification_separate"] is True
    assert telegram["live_behavior_changed_now"] is False
    assert payload["telegram_notification_behavior_changed"] is False
    assert payload["telegram_send_triggered"] is False
    assert boundary["mission_control_visibility_is_read_model_mirror"] is True
    assert boundary["telegram_operator_notification_is_separate_path"] is True
    assert boundary["telegram_behavior_changed_by_this_lane"] is False


def test_calendar_cleanup_and_normalization_remain_future(tmp_path):
    payload = _build(tmp_path)
    calendar = payload["calendar_operator_context"]
    discovery = _surface(payload, "calendar_discovery_understanding")
    normalization = _surface(payload, "calendar_normalization_future")

    assert calendar["google_apple_calendar_merged_context_recorded"] is True
    assert calendar["mac_calendar_confusing_context_recorded"] is True
    assert calendar["generic_calendar_cleanup_started"] is False
    assert calendar["calendar_normalization_allowed_now"] is False
    assert discovery["primary_classification"] == "CALENDAR_DISCOVERY_BLOCKED"
    assert normalization["primary_classification"] == "CALENDAR_NORMALIZATION_FUTURE"
    assert "CALENDAR_NORMALIZATION_FUTURE" in discovery["classifications"]


def test_protected_access_and_security_threshold_are_required_for_live_surfaces(tmp_path):
    payload = _build(tmp_path)

    for surface_id in [
        "gmail_live_account_access",
        "email_send_and_gmail_draft_creation",
        "calendar_discovery_understanding",
        "oauth_credential_tool_browser_bridges",
    ]:
        surface = _surface(payload, surface_id)
        assert surface["protected_access_gate_applies"] is True
        assert surface["security_threshold_required"] is True
        assert "PROTECTED_ACCESS_REQUIRED" in surface["classifications"]
        assert "SECURITY_THRESHOLD_REQUIRED" in surface["classifications"]


def test_unknown_email_calendar_capability_fails_closed(tmp_path):
    payload = _build(tmp_path)
    unknown = _surface(payload, "unknown_email_calendar_surface")

    assert unknown["primary_classification"] == "UNKNOWN_FAIL_CLOSED"
    assert unknown["unknown_fails_closed"] is True
    assert unknown["governed_now"] is False
    assert unknown["live_behavior_changed_now"] is False


def test_eli5_summary_exists_and_distinguishes_visibility_from_telegram(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "Cassandra can safely represent review-only packets" in eli5["what_cassandra_can_safely_represent_now"]
    assert "Gmail" in eli5["what_email_calendar_parts_are_blocked"]
    assert "Telegram draft preview behavior is separate from Mission Control visibility" in eli5["telegram_vs_mission_control"]
    assert "Calendar cleanup is not happening yet" in eli5["calendar_cleanup_not_happening_yet"]
    assert len(eli5["next_1_to_3_sensible_lanes"]) == 3


def test_repo_b_is_used_only_through_existing_delta_read_model(tmp_path):
    payload = _build(tmp_path)
    source = next(item for item in payload["source_read_models"] if item["key"] == "repo_b_remaining_capability_delta_map")

    assert source["present"] is True
    assert source["repo_b_delta_read_model_used"] is True
    assert source["repo_b_filesystem_inspected"] is False
    assert source["repo_b_code_executed"] is False
    assert payload["repo_b_delta_handling"]["repo_b_filesystem_inspected"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = detangle.export_cassandra_email_calendar_delta_detangle(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == detangle.SCHEMA_VERSION
    assert result.runtime_authority_added is False
    assert result.send_or_submit_authority_added is False
    assert (repo / "generated/read_models/cassandra_email_calendar_delta_detangle.json").is_file()
    assert (repo / "generated/read_models/cassandra_email_calendar_delta_detangle_OPERATOR.md").is_file()
    assert "cassandra_email_calendar_delta_detangle.json" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == detangle.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Cassandra Email Calendar Delta Detangle v0" in output
    assert "Live Gmail/calendar/OAuth/send/draft authority: `false`" in output


def test_source_does_not_import_or_call_live_account_or_execution_mechanisms():
    source = Path("cassandra_email_calendar_delta_detangle.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "subprocess" not in imports
    assert "requests" not in imports
    assert "httpx" not in imports
    assert "google_access_broker" not in imports
    assert "smtplib" not in imports
    assert "imaplib" not in imports
    assert "webbrowser" not in imports
    assert "selenium" not in imports
    assert "playwright" not in imports
    assert "/home/openclaw_external/openclaw-runtime" not in source


def test_write_calls_are_limited_to_generated_read_model_exports():
    tree = ast.parse(Path("cassandra_email_calendar_delta_detangle.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
