import ast
import json
from pathlib import Path

import operator_sovereignty_power_stage_gate as gate
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_sovereignty_power_stage_gate import main as export_main


FIXED_NOW = "2026-05-17T21:30:00+00:00"


def _build() -> dict:
    return gate.build_operator_sovereignty_power_stage_gate(generated_at=FIXED_NOW)


def test_current_stage_is_classified_conservatively():
    payload = _build()
    current = payload["current_power_stage"]

    assert current["current_power_stage_classified"] is True
    assert current["current_power_stage_id"] == gate.CURRENT_POWER_STAGE_ID
    assert current["classification"] == "Stage 1 current; Stage 2 pieces modeled; Stages 3-5 blocked."
    assert current["no_executable_send_submit_browser_credential_authority"] is True
    assert current["do_not_overclaim"] is True

    stages = {stage["stage_id"]: stage for stage in payload["stages"]}
    assert stages[gate.CURRENT_POWER_STAGE_ID]["can_cross_into_stage"] is True
    assert stages["stage_2_approval_request_generation"]["current_status"] == "modeled_partial_not_crossed"
    assert stages["stage_2_approval_request_generation"]["can_cross_into_stage"] is False


def test_stage_1_controls_are_required_now():
    stages = {stage["stage_id"]: stage for stage in _build()["stages"]}
    stage_1 = stages[gate.CURRENT_POWER_STAGE_ID]

    for control in (
        "provenance_backed_read_models",
        "no_raw_secret_pii_in_normal_read_models",
        "authority_flags_on_review_packets",
        "sync_mirror_trust_surface",
        "wrong_environment_guidance",
        "review_only_labels",
    ):
        assert control in stage_1["required_controls"]
    assert stage_1["missing_controls"] == []


def test_stage_2_approval_packets_do_not_imply_execution_authority():
    payload = _build()
    stage_2 = {stage["stage_id"]: stage for stage in payload["stages"]}[
        "stage_2_approval_request_generation"
    ]

    assert stage_2["can_cross_into_stage"] is False
    assert "treat approval packets as executable by default" in stage_2["forbidden_capabilities"]
    assert "implicit authority escalation" in stage_2["forbidden_capabilities"]
    assert "receipt_logging_for_executable_approval_requests" in stage_2["missing_controls"]
    assert payload["higher_power_crossing_policy"][
        "stage_2_approval_packets_do_not_imply_execution_authority"
    ] is True


def test_stage_3_is_blocked_without_protected_pii_broker_controls():
    payload = _build()
    stage_3 = {stage["stage_id"]: stage for stage in payload["stages"]}[
        "stage_3_credential_pii_broker_browser_prep"
    ]

    assert stage_3["can_cross_into_stage"] is False
    assert "protected_local_only_credential_pii_broker_design" in stage_3["missing_controls"]
    assert "scoped_access_receipts" in stage_3["missing_controls"]
    assert payload["stage_3_blocked_without_protected_pii_broker_controls"] is True


def test_stage_4_is_blocked_without_hard_stop_and_tamper_controls():
    payload = _build()
    stage_4 = {stage["stage_id"]: stage for stage in payload["stages"]}[
        "stage_4_real_send_submit_browser_spreadsheet_execution"
    ]

    assert stage_4["can_cross_into_stage"] is False
    assert "hard_stop_containment_mechanisms" in stage_4["missing_controls"]
    assert "tamper_checks" in stage_4["missing_controls"]
    assert "operator_controlled_recovery" in stage_4["missing_controls"]
    assert payload["stage_4_blocked_without_hard_stop_and_tamper_controls"] is True


def test_stage_5_is_blocked_without_strong_recovery_authentication():
    payload = _build()
    stage_5 = {stage["stage_id"]: stage for stage in payload["stages"]}[
        "stage_5_client_deployment_remote_nodes_autonomous_repair"
    ]

    assert stage_5["can_cross_into_stage"] is False
    assert "stronger_authentication" in stage_5["missing_controls"]
    assert "out_of_band_recovery_for_severe_breaches" in stage_5["missing_controls"]
    assert "client_boundary_protections" in stage_5["missing_controls"]
    assert payload["stage_5_blocked_without_strong_recovery_authentication"] is True


def test_alert_model_reserves_red_for_severe_compromise_not_low_mismatch():
    alerts = _build()["alert_severity_model"]

    assert alerts["low_level_mismatch_triggers_red_alert"] is False
    assert alerts["red_alert_reserved_for_severe_compromise"] is True
    assert alerts["low"]["red_alert"] is False
    assert alerts["medium"]["red_alert"] is False
    assert alerts["high"]["red_alert"] is False
    assert alerts["red"]["red_alert"] is True
    assert "stale sync_health" in alerts["low"]["examples"]
    assert "loss of operator control" in alerts["red"]["examples"]


def test_watchdog_monitors_authority_surfaces_not_operator_private_life():
    scope = _build()["watchdog_scope"]

    assert scope["watchdog_monitors_authority_surfaces_not_operator_private_life"] is True
    assert "authority flags on packets and receipts" in scope["included_authority_surfaces"]
    assert "private operator behavior profiling" in scope["excluded_surveillance_surfaces"]
    assert "raw Telegram/Gmail/calendar body monitoring" in scope["excluded_surveillance_surfaces"]
    assert scope["private_content_read_required"] is False
    assert scope["raw_secret_or_pii_read_required"] is False
    assert scope["autonomous_self_repair_allowed"] is False


def test_no_authority_runtime_send_browser_credential_or_client_paths_added():
    payload = _build()

    for key, expected in gate.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["surveillance_capability_added"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["browser_automation_added"] is False
    assert payload["credential_or_pii_access_added"] is False
    assert payload["customer_deployment_authority_added"] is False


def test_generated_read_model_is_deterministic_and_exportable(tmp_path, capsys):
    first = gate.build_operator_sovereignty_power_stage_gate(generated_at=FIXED_NOW)
    second = gate.build_operator_sovereignty_power_stage_gate(generated_at=FIXED_NOW)
    assert gate.stable_json(first) == gate.stable_json(second)

    result = gate.export_operator_sovereignty_power_stage_gate(
        export_root=tmp_path,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((tmp_path / gate.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (tmp_path / gate.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.current_power_stage_classified is True
    assert payload["schema_version"] == gate.READ_MODEL_VERSION
    assert "Operator Sovereignty Power-Stage Gate" in operator_text
    assert export_main(["--export-root", str(tmp_path), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == gate.READ_MODEL_VERSION


def test_generated_files_are_safe_read_model_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    gate.export_operator_sovereignty_power_stage_gate(export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert gate.JSON_EXPORT_NAME in expected
    assert gate.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_execute_send_scan_private_or_import_repo_b():
    source_files = [
        Path("operator_sovereignty_power_stage_gate.py"),
        Path("scripts/export_operator_sovereignty_power_stage_gate.py"),
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
        ".chief.env",
        ".google-secrets",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text

    tree = ast.parse(Path("operator_sovereignty_power_stage_gate.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
