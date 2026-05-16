import ast
import inspect
import json
from pathlib import Path

import bundle_blueprint_planner as planner
from scripts.export_bundle_blueprint_planner_read_model import main as export_main
from scripts.plan_bundle_blueprint import main as plan_main


def test_invoice_receivables_maps_to_conservative_finance_bundle():
    manifest = planner.plan_bundle_blueprint(
        pain_point="I need help tracking invoices and receivables",
        target_context="company",
    )
    selected = {item["module_id"] for item in manifest["selected_modules"]}

    assert {"project_capsule_bundle_blueprint", "report_bridge_sanitized_summary"} <= selected
    assert "finance_receivables_packet" in manifest["missing_modules"]
    assert manifest["sensitive_data_policy"]["local_only_required"] is True
    assert manifest["sensitive_data_policy"]["core_receives_private_content"] is False
    assert manifest["github_packaging_allowed"] is False
    assert manifest["deployment_allowed"] is False
    assert manifest["runtime_authority"] is False


def test_album_progress_maps_to_niles_album_matrix():
    manifest = planner.plan_bundle_blueprint(
        pain_point="I need a system to track album progress",
        target_context="personal",
    )

    assert [item["module_id"] for item in manifest["selected_modules"]] == ["niles_album_matrix"]
    assert manifest["selected_modules"][0]["runtime_authority"] is False


def test_safe_email_approval_maps_to_guardian_and_draft_intake():
    manifest = planner.plan_bundle_blueprint(
        pain_point="I need safe approval before emails go out",
        target_context="friend",
    )
    selected = {item["module_id"] for item in manifest["selected_modules"]}

    assert {"guardian_hitl_gate", "cassandra_clara_fact_intake"} <= selected
    assert manifest["send_allowed"] is False
    assert manifest["sensitive_data_policy"]["needs_operator_review"] is True


def test_client_safe_report_without_private_files_uses_report_bridge_policy():
    manifest = planner.plan_bundle_blueprint(
        pain_point="I need a client-safe status report without exposing private files",
        target_context="client",
    )
    selected = {item["module_id"] for item in manifest["selected_modules"]}

    assert "report_bridge_sanitized_summary" in selected
    assert manifest["report_bridge_policy"]["raw_content_allowed"] is False
    assert manifest["report_bridge_policy"]["client_private_content_allowed"] is False
    assert "client_or_sensitive_data_stays_local" in manifest["local_only_requirements"]


def test_next_best_coding_lane_blocks_runner_registry():
    manifest = planner.plan_bundle_blueprint(
        pain_point="I need the system to pick the next best coding lane",
        target_context="internal_test",
    )

    assert {item["module_id"] for item in manifest["selected_modules"]} == {"hermes_next_lane_advisory"}
    assert {item["module_id"] for item in manifest["blocked_modules"]} == {"planner_runner_registry"}
    assert manifest["blocked_modules"][0]["blocked_reason"] == "module_status_blocked"


def test_scripts_and_read_model_export_work(tmp_path, capsys):
    export_root = tmp_path / "read_models"

    plan_exit = plan_main(
        [
            "--pain-point",
            "I need a client-safe status report without exposing private files",
            "--target-context",
            "client",
            "--format",
            "json",
        ]
    )
    manifest = json.loads(capsys.readouterr().out)
    assert plan_exit == 0
    assert manifest["target_context"] == "client"
    assert "pain_point_hash" in manifest
    assert "pain_point" not in manifest

    export_exit = export_main(["--export-root", str(export_root), "--format", "operator"])
    assert export_exit == 0
    assert "Bundle Blueprint Planner Read-Model v0" in capsys.readouterr().out
    payload = json.loads((export_root / "bundle_blueprint_planner.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "bundle_blueprint_planner_read_model_v0"
    assert payload["github_packaging_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["runtime_authority"] is False


def test_bundle_blueprint_sources_have_no_external_runtime_or_shell_behavior():
    source_files = [
        Path("bundle_blueprint_planner.py"),
        Path("scripts/plan_bundle_blueprint.py"),
        Path("scripts/export_bundle_blueprint_planner_read_model.py"),
    ]
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "git clone",
        "git push",
        "docker run",
        "ollama run",
        "send_message",
        "smtp",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text

    tree = ast.parse(inspect.getsource(planner))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
