import ast
import json
from pathlib import Path

import openclaw_estate_node_registry as registry
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_openclaw_estate_node_registry import main as export_main


FIXED_NOW = "2026-05-17T22:15:00+00:00"


def _nodes_by_id(payload: dict) -> dict[str, dict]:
    return {node["node_id"]: node for node in payload["nodes"]}


def test_registry_is_deterministic_and_contains_required_fields():
    first = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    second = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)

    assert registry.stable_json(first) == registry.stable_json(second)
    assert first["schema_version"] == registry.READ_MODEL_VERSION
    assert first["contract_schema_version"] == registry.SCHEMA_VERSION
    assert first["node_count"] >= 10
    for node in first["nodes"]:
        for field in registry.REQUIRED_NODE_FIELDS:
            assert field in node
        assert node["runtime_authority"] is False
        assert node["send_or_submit_authority"] is False
        assert node["deployment_authority"] is False


def test_repo_a_is_canonical_backend_authority_only():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    repo_a = _nodes_by_id(payload)["repo_a_pc_wsl_backend"]

    assert repo_a["known_paths"][0]["path"] == "/home/openclaw"
    assert repo_a["canonicality"] == "canonical_current_backend"
    assert repo_a["authority_level"] == "canonical_backend_read_model_contract_test_authority"
    assert repo_a["active_authority"] is True
    assert "SQLite/read-model work" in repo_a["suited_work"]
    assert "Mac/Xcode UI builds" in repo_a["blocked_work"]
    assert payload["status_summary"]["repo_a_canonical_backend_modeled"] is True


def test_repo_b_is_reference_only_and_not_runtime_authority():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    repo_b = _nodes_by_id(payload)["repo_b_pc_wsl_reference"]

    assert repo_b["known_paths"][0]["path"] == "/home/openclaw_external/openclaw-runtime"
    assert repo_b["authority_level"] == "reference_evidence_only"
    assert repo_b["canonicality"] == "not_canonical_pre_split_capability_tree"
    assert repo_b["repo_b_runtime_authority"] is False
    assert "blind execution" in repo_b["blocked_work"]
    assert repo_b["allowed_access_patterns"][0]["boundary"] == "do_not_import_or_execute"
    assert payload["status_summary"]["repo_b_reference_only_modeled"] is True
    assert payload["repo_b_runtime_authority_added"] is False


def test_mac_mission_control_repo_is_app_surface_only():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    mac_app = _nodes_by_id(payload)["mac_mission_control_xcode_repo"]

    assert "OpenClaw Mission Controle" in mac_app["known_paths"][0]["path"]
    assert mac_app["authority_level"] == "app_surface_only"
    assert mac_app["canonicality"] == "non_canonical_backend_consumer"
    assert "SwiftUI/Xcode app work" in mac_app["suited_work"]
    assert "backend authority" in mac_app["blocked_work"]
    assert "SQLite truth mutation" in mac_app["blocked_work"]
    assert payload["status_summary"]["mac_mission_control_app_surface_modeled"] is True


def test_mac_mirror_is_read_only_visibility_not_truth():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    mirror = _nodes_by_id(payload)["mac_generated_read_model_mirror"]

    assert mirror["known_paths"][0]["path"] == "/Users/hwinshipwheatley/openclaw_generated_read_models"
    assert mirror["authority_level"] == "mirrored_visibility_only"
    assert mirror["canonicality"] == "mirror_not_truth"
    assert "Mission Control read-only consumption" in mirror["suited_work"]
    assert "source-of-truth edits" in mirror["blocked_work"]
    assert mirror["allowed_access_patterns"][0]["boundary"] == "mirror_visibility_not_canonical_truth"


def test_e_drive_shuttle_is_transport_not_manual_copy_authority():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    shuttle = _nodes_by_id(payload)["shared_e_drive_shuttle"]
    paths = {item["path"] for item in shuttle["known_paths"]}

    assert "/mnt/e/openclaw" in paths
    assert "/Volumes/openclaw_e" in paths
    assert shuttle["authority_level"] == "transport_proof_surface"
    assert shuttle["canonicality"] == "transport_not_truth"
    assert "arbitrary manual copy as primary fix" in shuttle["blocked_work"]
    assert shuttle["allowed_access_patterns"][0]["boundary"] == "transport_only_not_canonical_truth"


def test_mac_planner_builder_node_is_non_canonical_until_promoted():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    planner = _nodes_by_id(payload)["mac_openclaw_planner_builder_harness"]

    assert planner["authority_level"] == "non_canonical_candidate"
    assert planner["canonicality"] == "candidate_non_canonical_unless_promoted"
    assert planner["known_paths"][0]["status"] == "unknown_not_discovered_in_this_lane"
    assert "ungated browser/Coupa/desktop automation" in planner["blocked_work"]
    assert "operator approval" in planner["promotion_required_for_authority"]
    assert payload["status_summary"]["mac_planner_builder_node_modeled"] is True


def test_ssh_policy_allows_scoped_dev_access_but_not_authority_escalation():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    policy = payload["machine_access_policy"]

    assert policy["ssh_between_mac_and_pc_wsl"] == "allowed_for_scoped_development_workflows"
    assert policy["ssh_availability_should_be_treated_as_normal_blocker"] is False
    assert policy["ssh_grants_task_authority"] is False
    assert policy["ssh_grants_runtime_authority"] is False
    assert policy["correct_node_workspace_still_required"] is True
    assert policy["repo_b_executable_because_reachable"] is False
    assert policy["configured_in_this_lane"] is False


def test_wrong_environment_guidance_can_be_derived_from_registry():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    guidance = {item["work_kind"]: item for item in payload["wrong_environment_guidance"]}

    assert guidance["pc_wsl_backend_contract_read_model_tests"]["recommended_node_id"] == "repo_a_pc_wsl_backend"
    assert guidance["mission_control_xcode_app_surface"]["recommended_node_id"] == "mac_mission_control_xcode_repo"
    assert guidance["mac_browser_coupa_desktop_automation"]["recommended_node_id"] == "mac_openclaw_planner_builder_harness"
    assert guidance["repo_b_capability_reference"]["recommended_node_id"] == "repo_b_pc_wsl_reference"
    assert guidance["read_model_sync_transport"]["recommended_node_id"] == "shared_e_drive_shuttle"
    assert all(item["authority_escalation_allowed"] is False for item in guidance.values())


def test_future_nodes_do_not_gain_active_authority_by_being_listed():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)
    nodes = _nodes_by_id(payload)
    future_ids = set(payload["future_or_planned_nodes"])

    assert {
        "mac_studio_future_workstation",
        "mac_laptop_future_execution_node",
        "ipad_iphone_operator_surface_future",
        "client_friend_company_node_future",
    }.issubset(future_ids)
    for node_id in future_ids:
        node = nodes[node_id]
        assert node["active_authority"] is False
        assert node["runtime_authority"] is False
        assert node["send_or_submit_authority"] is False
        assert node["deployment_authority"] is False
    assert payload["status_summary"]["future_nodes_active_authority_granted"] is False


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    export_root = tmp_path / "generated" / "read_models"

    result = registry.export_openclaw_estate_node_registry(
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / registry.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / registry.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.repo_a_canonical_backend_modeled is True
    assert payload["status_summary"]["ssh_scoped_dev_access_policy_modeled"] is True
    assert "OpenClaw Estate Node Registry" in operator_text
    assert "Repo B remains reference-only" in operator_text
    assert export_main(["--export-root", str(export_root), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == registry.READ_MODEL_VERSION


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    registry.export_openclaw_estate_node_registry(export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert registry.JSON_EXPORT_NAME in expected
    assert registry.OPERATOR_EXPORT_NAME in expected


def test_no_runtime_send_submit_browser_deployment_or_repo_b_execution_authority_is_added():
    payload = registry.build_openclaw_estate_node_registry(generated_at=FIXED_NOW)

    for key, expected in registry.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["browser_automation_authority_added"] is False
    assert payload["customer_deployment_authority_added"] is False
    assert payload["repo_b_executed"] is False


def test_source_does_not_execute_services_repo_b_send_browser_or_subprocess():
    source_files = [
        Path("openclaw_estate_node_registry.py"),
        Path("scripts/export_openclaw_estate_node_registry.py"),
    ]
    forbidden = [
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
        "systemctl",
        "launchctl",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text

    tree = ast.parse(Path("openclaw_estate_node_registry.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
