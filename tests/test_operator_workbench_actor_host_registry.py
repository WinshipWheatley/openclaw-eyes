import ast
import json
import sqlite3
from pathlib import Path

import operator_workbench_actor_host_registry as registry
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_workbench_actor_host_registry import main as export_main


FIXED_NOW = "2026-05-20T20:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "mission_package_contract": {"package_template_fields": ["actor_model_candidate"]},
            "chat_workspace_launch_posture": {"future_gated": True},
        },
        "capability_skill_registry_metadata_delta.json": {
            "schema_version": "capability_skill_registry_metadata_delta_v0",
            "metadata_only_registry": True,
        },
        "system_health_lights_taxonomy.json": {
            "schema_version": "system_health_lights_taxonomy_v0",
            "current_light_states": {"check_transmission": "QUIET", "brake_parking_brake": "ON_NORMAL"},
        },
        "sync_health.json": {
            "schema_version": "sync_health_read_model_v0",
            "canonical_expected": 204,
            "observed": 204,
            "missing_expected": 0,
            "hash_mismatch": 0,
            "sync_lifecycle_state": "trusted_current",
        },
        "work_board.json": {
            "schema_version": "work_board_read_model_v0",
            "direct_execution_allowed": False,
        },
        "operator_actions.json": {
            "schema_version": "operator_actions_read_model_v0",
            "runtime_activation_allowed": False,
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return registry.build_operator_workbench_actor_host_registry(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _host(payload: dict, host_id: str) -> dict:
    return next(host for host in payload["hosts"] if host["host_id"] == host_id)


def test_registry_is_deterministic_and_references_existing_spines(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert registry.stable_json(first) == registry.stable_json(second)
    assert first["schema_version"] == registry.SCHEMA_VERSION
    assert first["read_model_id"] == "operator_workbench_actor_host_registry"
    assert first["registry_status"] == "deterministic_metadata_only_workbench_actor_host_registry"
    assert first["relationship_to_existing_contracts"]["does_not_replace_nested_lane_spine"] is True
    assert first["relationship_to_existing_contracts"]["does_not_replace_capability_registry"] is True
    assert first["machine_proof"]["source_read_models_present"]["operator_nested_lane_mission_package_spine"] is True
    assert first["machine_proof"]["source_read_models_present"]["system_health_lights_taxonomy"] is True


def test_required_workbenches_and_categories_are_registered(tmp_path):
    payload = _build(tmp_path)
    host_ids = {host["host_id"] for host in payload["hosts"]}

    assert host_ids >= {
        "pc_wsl_repo_a",
        "mac_mission_control_app",
        "codex_vscode_mac_codex_desktop",
        "antigravity_gemini_flash_high",
        "gpt_5_5_chatgpt_orchestrator",
        "xcode_xcodebuild",
        "terminal_shell",
        "vscode_agents_remote_ahp_candidate",
    }
    assert _host(payload, "pc_wsl_repo_a")["category"] == "canonical_repo"
    assert _host(payload, "mac_mission_control_app")["category"] == "helm_app"
    assert _host(payload, "antigravity_gemini_flash_high")["category"] == "fast_planner_verifier"
    assert _host(payload, "vscode_agents_remote_ahp_candidate")["category"] == "agent_host_candidate"


def test_autonomy_levels_are_defined_and_defaults_are_conservative(tmp_path):
    payload = _build(tmp_path)

    assert [level["level_id"] for level in payload["autonomy_level_progression"]] == [
        "L0",
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
    ]
    codex = _host(payload, "codex_vscode_mac_codex_desktop")
    antigravity = _host(payload, "antigravity_gemini_flash_high")
    mac_app = _host(payload, "mac_mission_control_app")
    terminal = _host(payload, "terminal_shell")
    candidate = _host(payload, "vscode_agents_remote_ahp_candidate")

    assert codex["allowed_autonomy_level_now"] == "L2_SCOPED_READ_WRITE_EXPLICIT_PROMPT"
    assert "scoped file edits" in codex["best_roles"]
    assert antigravity["allowed_autonomy_level_now"] == "L2_SCOPED_READ_WRITE_EXPLICIT_LANE"
    assert antigravity["first_time_or_ambiguous_lane_default"] == "sandbox_or_read_only"
    assert mac_app["allowed_autonomy_level_now"] == "L1_DISPLAY_AND_EXISTING_MARKER_WRITE_ONLY"
    assert terminal["allowed_autonomy_level_now"] == "L1_EXPLICIT_SCOPED_COMMANDS_ONLY"
    assert candidate["current_status"] == "candidate"
    assert candidate["allowed_autonomy_level_now"] == "L0_PREVIEW_PACKAGE_ONLY"
    assert candidate["future_gated_until_intake"] is True


def test_host_records_have_package_receipt_proof_and_boundary_fields(tmp_path):
    payload = _build(tmp_path)
    required_fields = set(payload["host_record_contract"]["required_fields"])

    for host in payload["hosts"]:
        assert required_fields <= set(host)
        assert host["package_input_shape"]["metadata_only"] is True
        assert host["package_input_shape"]["live_launch_now"] is False
        assert host["expected_receipt_shape"]["receipt_required_before_ingest"] is True
        assert host["proof_requirements"]
        assert host["forbidden_actions"]
        assert host["credential_policy"]["credentials_stored_or_requested"] is False
        assert host["storage_policy"]["openclaw_artifacts_on_c_drive_allowed"] is False
        assert host["authority_boundary"]["runtime_authority_added"] is False
        assert host["authority_boundary"]["model_call_made"] is False
        assert host["authority_boundary"]["send_submit_approval_authority_added"] is False


def test_actor_routing_and_prompting_doctrine_are_metadata_only(tmp_path):
    payload = _build(tmp_path)
    routing = payload["actor_routing_summary"]

    assert routing["model_is_actor_agent_is_character_package_is_script"] is True
    assert routing["system_decides_authority_before_launch"] is True
    assert routing["package_generation_target"] == "deterministic_package_builder_over_time"
    assert routing["external_model_apis_called"] is False
    assert routing["browser_oauth_or_account_integrations_enabled"] is False
    assert routing["domain_to_likely_host_examples"]["canonical_backend_contracts"] == ["pc_wsl_repo_a"]
    assert routing["domain_to_likely_host_examples"]["mac_app_build_validation"] == [
        "codex_vscode_mac_codex_desktop",
        "xcode_xcodebuild",
    ]
    assert "clear lane" in _host(payload, "antigravity_gemini_flash_high")["notes_for_prompting"]
    assert "receipt" in _host(payload, "antigravity_gemini_flash_high")["notes_for_prompting"]


def test_operator_output_answers_required_questions(tmp_path):
    payload = _build(tmp_path)
    output = registry.format_operator_workbench_actor_host_registry(payload)

    assert "Operator Workbench / Actor Host Registry v0" in output
    assert "PC/WSL Repo A" in output
    assert "Antigravity CLI/Desktop with Gemini 3.5 Flash High" in output
    assert "Usable Now" in output
    assert "Candidate / Future-Gated" in output
    assert "Current Safe Autonomy" in output
    assert "Proof / Receipt Expectations" in output
    assert "How This Helps Winship" in output
    assert "No live integration, agent launch, model call, browser/OAuth, send, submit, approval, or runtime authority is added" in output


def test_sqlite_receipt_is_metadata_only_and_non_executing(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "workbench_actor_host_receipts.sqlite"

    receipt_id = registry.record_operator_workbench_actor_host_registry_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = registry.record_operator_workbench_actor_host_registry_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )

    assert receipt_id
    assert second_receipt_id == receipt_id

    conn = sqlite3.connect(db_path)
    try:
        events = conn.execute("SELECT event_type, raw_sensitive_data_stored, replay_safe FROM events").fetchall()
        packets = conn.execute("SELECT packet_json_safe FROM packets").fetchall()
    finally:
        conn.close()

    assert events == [("generated_status", 0, 1)]
    packet = json.loads(packets[0][0])
    assert packet["receipt_type"] == "generated_status"
    assert packet["authority_status"] == "generated_status_only"
    assert packet["runtime_activation"] is False
    assert packet["execution_authority"] == 0
    payload_json = packet["payload_json"]
    assert payload_json["contract_id"] == registry.SCHEMA_VERSION
    assert payload_json["metadata_only"] is True
    assert payload_json["host_count"] >= 8
    assert payload_json["raw_tool_outputs_stored"] is False
    assert payload_json["credentials_stored"] is False
    assert payload_json["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = registry.export_operator_workbench_actor_host_registry(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == registry.SCHEMA_VERSION
    assert result.host_count >= 8
    assert result.sqlite_receipt_supported is True
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    assert "operator_workbench_actor_host_registry.json" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )
    assert "operator_workbench_actor_host_registry_OPERATOR.md" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == registry.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Operator Workbench / Actor Host Registry v0" in output
    assert "Current Safe Autonomy" in output


def test_no_live_agent_model_tool_browser_or_c_drive_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in registry.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["model_calls_made"] is False
    assert payload["agents_activated"] is False
    assert payload["browser_oauth_or_account_access_enabled"] is False
    assert payload["c_drive_artifact_written"] is False
    assert payload["execution_authority_added"] is False


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("operator_workbench_actor_host_registry.py"),
        Path("scripts/export_operator_workbench_actor_host_registry.py"),
    ]
    forbidden_import_roots = {
        "os",
        "subprocess",
        "requests",
        "httpx",
        "urllib",
        "smtplib",
        "imaplib",
        "webbrowser",
        "selenium",
        "playwright",
        "google_access_broker",
        "cassandra_brain",
        "chief_router",
        "shutil",
    }
    forbidden_text = [
        "/mnt/c/",
        "C:\\\\",
        "unlink(",
        "rmdir(",
        "rmtree(",
        "os.system",
        "send_message",
        "send_email",
        "ApplicationBuilder",
        "oauth_accessed=True",
        "credentials.json",
        "token.json",
        "subprocess.",
    ]
    for path in source_files:
        source = path.read_text(encoding="utf-8")
        for needle in forbidden_text:
            assert needle not in source
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not (imports | modules) & forbidden_import_roots


def test_write_calls_are_limited_to_generated_read_model_exports_and_not_c_drive():
    source = Path("operator_workbench_actor_host_registry.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
    assert "c_drive_artifact_written=True" not in source
    assert "out_dir = _rooted(export_root, repo_root=root)" in source
