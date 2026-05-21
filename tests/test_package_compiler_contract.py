import ast
import json
import sqlite3
from pathlib import Path

import package_compiler_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_package_compiler_contract import main as export_main


FIXED_NOW = "2026-05-21T00:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "steel_thread_lane_template_registry.json": {
            "schema_version": "steel_thread_lane_template_registry_v0",
            "template_type_count": 8,
            "template_types": ["helm_lane", "check_light_lane", "package_preview_lane"],
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "host_count": 8,
            "actor_routing_summary": {
                "registered_host_ids": [
                    "pc_wsl_repo_a",
                    "codex_vscode_mac_codex_desktop",
                    "antigravity_gemini_flash_high",
                    "gpt_5_5_chatgpt_orchestrator",
                ]
            },
        },
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "package_preview_only": True,
        },
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "package_preview_only": True,
        },
        "agent_work_packets.json": {
            "schema_version": "agent_work_packets_read_model_v0",
            "mode": "agent_work_packets_planning_only",
            "execution_allowed": False,
        },
        "system_health_lights_taxonomy.json": {
            "schema_version": "system_health_lights_taxonomy_v0",
            "current_light_states": {"check_transmission": "ON"},
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return contract.build_package_compiler_contract(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _sample(payload: dict, package_id: str) -> dict:
    return next(item for item in payload["sample_package_outlines"] if item["package_id"] == package_id)


def _safe_sample(tmp_path: Path) -> dict:
    return _sample(_build(tmp_path), "sample_check_transmission_diagnostic_package")


def _blocker_codes(result: dict) -> set[str]:
    return {item["blocker_code"] for item in result["blockers"]}


def test_contract_is_deterministic_and_companion_to_existing_packet_models(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "package_compiler_contract"
    assert first["contract_status"] == "deterministic_metadata_only_package_compiler_boundary_hardened"
    assert first["relationship_to_existing_contracts"]["does_not_replace_agent_work_packets"] is True
    assert first["relationship_to_existing_contracts"]["does_not_replace_awareness_or_nested_package_spines"] is True
    assert first["relationship_to_existing_contracts"]["does_not_replace_workbench_registry"] is True
    assert first["machine_proof"]["source_read_models_present"]["steel_thread_lane_template_registry"] is True
    assert first["machine_proof"]["source_read_models_present"]["operator_workbench_actor_host_registry"] is True


def test_package_schema_contains_required_fields(tmp_path):
    payload = _build(tmp_path)
    fields = payload["package_schema"]["fields"]

    assert fields == list(contract.PACKAGE_SCHEMA_FIELDS)
    for required in [
        "package_id",
        "source_lane_type",
        "steel_thread_template_id",
        "target_workbench_or_actor_host",
        "actor_model_candidate",
        "agent_character",
        "allowed_workspace_roots",
        "workspace_scope",
        "allowed_capabilities",
        "forbidden_capabilities",
        "clearance_level",
        "authority_level",
        "authority_boundary",
        "autonomy_level",
        "validation_requirements",
        "required_schema_checks",
        "required_hash_or_manifest_checks",
        "required_receipts",
        "confidence_state",
        "detour_options",
        "current_availability",
        "credential_policy",
        "storage_policy",
        "c_drive_policy",
        "no_go_data_policy",
        "human_confirmation_required",
    ]:
        assert required in fields
    assert payload["package_schema"]["actor_does_not_self_assign_authority"] is True
    assert payload["package_schema"]["unknown_required_field_fails_closed"] is True


def test_boundary_validation_contract_defines_explicit_enums_and_blockers(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["boundary_validation_contract"]

    assert boundary["contract_name"] == "BoundaryValidationContract"
    for structure in [
        "BoundaryValidationContract",
        "PackageCompileTimeBlocker",
        "CapabilityGrant",
        "WorkspaceScope",
        "AuthorityLevel",
        "ClearanceLevel",
        "ValidationRequirement",
        "ReceiptRequirement",
        "FailureStopCondition",
    ]:
        assert structure in boundary["structures_defined"]
    assert boundary["authority_level_enum"] == list(contract.AUTHORITY_LEVELS)
    assert boundary["clearance_level_enum"] == list(contract.CLEARANCE_LEVELS)
    assert boundary["autonomy_level_enum"] == list(contract.AUTONOMY_LEVELS)
    assert boundary["capability_class_enum"] == list(contract.CAPABILITY_CLASSES)
    assert "pc_c_drive_write" in boundary["blocked_by_default_capabilities"]
    assert "model_call" in boundary["blocked_by_default_capabilities"]
    assert "browser" in boundary["blocked_by_default_capabilities"]
    assert "oauth" in boundary["blocked_by_default_capabilities"]
    assert boundary["natural_language_claims_establish_authority"] is False
    assert boundary["actor_or_model_may_expand_own_authority"] is False
    blocker_codes = {item["blocker_code"] for item in boundary["compile_time_blockers"]}
    assert "path_outside_allowed_roots" in blocker_codes
    assert "success_claim_without_deterministic_validation" in blocker_codes
    assert "future_gated_action_made_active" in blocker_codes


def test_package_types_are_defined_without_runtime_authority(tmp_path):
    payload = _build(tmp_path)

    assert [item["package_type"] for item in payload["package_types"]] == [
        "check_light_diagnostic_package",
        "helm_lane_awareness_package",
        "world_lane_work_package",
        "design_memory_discovery_package",
        "bridge_sync_diagnostic_package",
        "workbench_actor_review_package",
        "code_implementation_package",
        "verification_review_package",
        "tell_system_whats_missing_package",
        "confidence_detour_package",
    ]
    for item in payload["package_types"]:
        assert item["runtime_authority_added"] is False
        assert item["launch_allowed_now"] is False
        assert item["dispatch_allowed_now"] is False
        assert item["steel_thread_template_id"] in contract.STEEL_THREAD_TEMPLATE_IDS


def test_deterministic_and_lm_assisted_fields_are_separated(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["deterministic_vs_lm_assisted_generation"]

    assert set(boundary["deterministic_required_fields"]) == set(contract.DETERMINISTIC_REQUIRED_FIELDS)
    assert "authority_boundary" in boundary["deterministic_required_fields"]
    assert "authority_level" in boundary["deterministic_required_fields"]
    assert "clearance_level" in boundary["deterministic_required_fields"]
    assert "allowed_workspace_roots" in boundary["deterministic_required_fields"]
    assert "required_schema_checks" in boundary["deterministic_required_fields"]
    assert "allowed_plugins_or_capabilities" in boundary["deterministic_required_fields"]
    assert "proof_requirements" in boundary["deterministic_required_fields"]
    assert "operator_eli5" in boundary["lm_assisted_allowed_fields_early"]
    assert "prompt_prose" in boundary["lm_assisted_allowed_fields_early"]
    assert boundary["lm_must_not_add_authority_tools_paths_secrets_plugins_or_execution_steps"] is True
    assert boundary["unknown_or_unavailable_actor_fails_closed"] is True


def test_actor_workbench_routing_hooks_reference_registry_and_fail_closed(tmp_path):
    payload = _build(tmp_path)
    routing = payload["actor_workbench_routing_hooks"]

    assert routing["source_registry"] == "operator_workbench_actor_host_registry"
    assert routing["model_is_actor_agent_is_character_package_is_script"] is True
    assert routing["system_decides_authority_before_launch"] is True
    assert routing["unknown_actor_or_host"]["routing"] == "fail_closed"
    assert routing["registered_host_ids_from_source"][:4] == [
        "pc_wsl_repo_a",
        "codex_vscode_mac_codex_desktop",
        "antigravity_gemini_flash_high",
        "gpt_5_5_chatgpt_orchestrator",
    ]


def test_confidence_detour_and_current_authority_are_preview_only(tmp_path):
    payload = _build(tmp_path)
    confidence = payload["confidence_detour_behavior"]
    authority = payload["current_authority_state"]

    assert confidence["below_deterministic"]["show_confidence_issue"] is True
    assert confidence["deterministic_or_full_trust"]["hide_confidence_score"] is True
    assert confidence["job_failure"]["reset_confidence"] is True
    assert confidence["no_confidence_theater_when_proof_is_deterministic"] is True
    assert authority["package_generation_now"] == ["preview_only", "copy_export_only", "future_gated"]
    assert authority["live_launch_allowed_now"] is False
    assert authority["model_agent_tool_call_from_app_allowed_now"] is False
    assert authority["send_submit_approval_runtime_allowed_now"] is False


def test_sample_packages_are_non_executing_and_button_ready(tmp_path):
    payload = _build(tmp_path)

    assert len(payload["sample_package_outlines"]) == 3
    check = _sample(payload, "sample_check_transmission_diagnostic_package")
    codex = _sample(payload, "sample_mission_control_ui_implementation_package_for_codex")
    anti = _sample(payload, "sample_antigravity_verification_review_package")

    assert check["package_type"] == "bridge_sync_diagnostic_package"
    assert check["agent_character"] == "Chief with Mirror Trust posture"
    assert codex["target_workbench_or_actor_host"] == "codex_vscode_mac_codex_desktop"
    assert codex["current_availability"] == "preview_only"
    assert anti["actor_model_candidate"] == "Gemini 3.5 Flash High candidate label only"
    for sample in payload["sample_package_outlines"]:
        assert sample["sample_only"] is True
        assert sample["dispatch_allowed_now"] is False
        assert sample["authority_boundary"]["runtime_authority_added"] is False
        assert sample["authority_boundary"]["model_or_agent_call_allowed"] is False
        assert sample["authority_level"] == "preview_only"
        assert sample["autonomy_level"] == "L0_preview_package_only"
        assert sample["allowed_capabilities"] == ["file_read"]
        assert "pc_c_drive_write" in sample["forbidden_capabilities"]
        assert contract.validate_package_boundary(sample)["valid"] is True
        assert sample["human_confirmation_required"] is True
        assert "receipt_requirements" in sample


def test_package_referencing_path_outside_allowed_roots_is_invalid(tmp_path):
    package = _safe_sample(tmp_path)
    package["workspace_scope"] = {
        **package["workspace_scope"],
        "path_refs": ["../outside_repo/private_note.md"],
    }

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    assert "path_outside_allowed_roots" in _blocker_codes(result)


def test_package_requesting_forbidden_capability_is_invalid(tmp_path):
    package = _safe_sample(tmp_path)
    package["capabilities_requested"] = ["file_read", "browser"]

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    assert "capability_not_allowed" in _blocker_codes(result)
    assert "forbidden_capability_requested" in _blocker_codes(result)
    assert "active_external_or_write_capability_requested" in _blocker_codes(result)


def test_package_requesting_pc_c_drive_write_is_invalid(tmp_path):
    package = _safe_sample(tmp_path)
    package["capabilities_requested"] = ["file_read", "pc_c_drive_write"]

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    assert "pc_system_drive_write_requested" in _blocker_codes(result)


def test_package_with_active_model_agent_browser_oauth_or_send_authority_is_invalid(tmp_path):
    package = _safe_sample(tmp_path)
    package["capabilities_requested"] = ["file_read", "model_call", "agent_call", "oauth", "email_send"]
    package["dispatch_allowed_now"] = True
    package["future_gate_required"] = True

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    codes = _blocker_codes(result)
    assert "active_external_or_write_capability_requested" in codes
    assert "future_gated_action_made_active" in codes


def test_package_missing_required_receipt_or_proof_validation_is_invalid(tmp_path):
    package = _safe_sample(tmp_path)
    package["required_receipts"] = []
    package["required_schema_checks"] = []
    package["required_file_existence_checks"] = []
    package["required_hash_or_manifest_checks"] = []
    package["required_test_results"] = []
    package["required_exit_codes"] = []
    package["validation_requirements"] = []

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    assert "missing_receipt_or_proof" in _blocker_codes(result)


def test_package_claiming_success_without_deterministic_validation_is_invalid(tmp_path):
    package = _safe_sample(tmp_path)
    package["claimed_success_state"] = "deterministic_success"
    package["success_validation"] = {
        "deterministic_success_claimed": True,
        "deterministic_proof_methods": [],
    }

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    assert "success_claim_without_deterministic_validation" in _blocker_codes(result)


def test_package_cannot_escalate_clearance_beyond_registry_default(tmp_path):
    package = _safe_sample(tmp_path)
    package["registry_default_clearance_level"] = "internal_operator_safe"
    package["clearance_level"] = "protected_context_required"

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    assert "clearance_escalates_registry_default" in _blocker_codes(result)


def test_package_cannot_convert_future_gated_action_into_active_action(tmp_path):
    package = _safe_sample(tmp_path)
    package["future_gated_actions"] = ["launch_workbench"]
    package["active_actions"] = ["launch_workbench"]
    package["launch_allowed_now"] = True
    package["future_gate_required"] = True

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    assert "future_gated_action_made_active" in _blocker_codes(result)


def test_actor_model_cannot_self_assign_authority_tools_or_workspace(tmp_path):
    package = _safe_sample(tmp_path)
    package["actor_may_self_assign_authority"] = True
    package["model_decides_tools"] = True

    result = contract.validate_package_boundary(package)

    assert result["valid"] is False
    assert "actor_self_assigned_authority" in _blocker_codes(result)


def test_preview_only_package_can_carry_context_refs_proof_refs_and_detours_without_live_authority(tmp_path):
    package = _safe_sample(tmp_path)
    result = contract.validate_package_boundary(package)

    assert result["valid"] is True
    assert package["current_availability"] == "preview_only"
    assert package["context_included"]
    assert package["evidence_refs"]
    assert package["read_model_refs"]
    assert package["detour_options"]
    assert package["dispatch_allowed_now"] is False
    assert package["launch_allowed_now"] is False
    assert package["authority_boundary"]["runtime_authority_added"] is False


def test_operator_output_answers_required_questions(tmp_path):
    output = contract.format_package_compiler_contract(_build(tmp_path))

    for heading in [
        "Package Compiler Contract v0",
        "What Is A Package?",
        "How Packages Are Compiled",
        "Deterministic Fields",
        "Boundary Validation",
        "Compile-Time Blockers",
        "Blocked By Default",
        "Safe Preview Package",
        "Invalid Package Conditions",
        "LM-Assisted Fields",
        "Package Types",
        "Actor / Workbench Routing",
        "Preview Only Now",
        "Future-Gated",
        "Authority Boundary",
        "Sample Packages",
        "What Mission Control Can Render",
        "Next Safe Lane",
    ]:
        assert heading in output


def test_missing_sources_are_unavailable_without_inventing_facts(tmp_path):
    repo = tmp_path / "repo_a"
    payload = contract.build_package_compiler_contract(repo_root=repo, generated_at=FIXED_NOW)

    assert payload["machine_proof"]["source_read_models_present"]["steel_thread_lane_template_registry"] is False
    assert payload["source_state_summary"]["operator_workbench_actor_host_registry"]["available"] is False
    assert payload["unknown_or_missing_source_policy"]["do_not_invent_source_facts"] is True
    assert payload["unknown_or_missing_source_policy"]["static_contract_still_renders"] is True
    assert payload["actor_workbench_routing_hooks"]["unknown_actor_or_host"]["routing"] == "fail_closed"


def test_sqlite_receipt_is_metadata_only_and_idempotent(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "package_contract_receipts.sqlite"

    receipt_id = contract.record_package_compiler_contract_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = contract.record_package_compiler_contract_receipt(
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
    assert payload_json["contract_id"] == contract.SCHEMA_VERSION
    assert payload_json["metadata_only"] is True
    assert payload_json["raw_logs_stored"] is False
    assert payload_json["credentials_stored"] is False
    assert payload_json["raw_private_file_bodies_stored"] is False
    assert payload_json["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = contract.export_package_compiler_contract(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == contract.SCHEMA_VERSION
    assert result.package_type_count == 10
    assert result.sample_package_count == 3
    assert result.sqlite_receipt_supported is True
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))
    assert "package_compiler_contract.json" in expected
    assert "package_compiler_contract_OPERATOR.md" in expected

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == contract.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Package Compiler Contract v0" in output


def test_no_live_model_agent_tool_browser_or_c_drive_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in contract.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["external_model_apis_called"] is False
    assert payload["agents_activated"] is False
    assert payload["tool_or_plugin_execution_authority_added"] is False
    assert payload["browser_oauth_or_account_access_enabled"] is False
    assert payload["c_drive_artifact_written"] is False
    assert payload["runtime_authority_added"] is False


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("package_compiler_contract.py"),
        Path("scripts/export_package_compiler_contract.py"),
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
        "shutil",
    }
    forbidden_text = [
        "/mnt/c/",
        "C:",
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


def test_write_calls_are_limited_to_generated_read_model_exports():
    source = Path("package_compiler_contract.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
    assert "out_dir = _rooted(export_root, repo_root=root)" in source
