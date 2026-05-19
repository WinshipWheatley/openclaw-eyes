import ast
import json
from pathlib import Path

import chief_role_capability_segmentation_map as chief_map
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_chief_role_capability_segmentation_map import main as export_main


FIXED_NOW = "2026-05-18T20:00:00+00:00"


def _write(path: Path, text: str = "# fixture\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _fixture_repo(root: Path) -> tuple[Path, Path]:
    baseline = {
        "schema_version": "repo_a_known_rail_completion_map_v0",
        "known_rail_count": 14,
        "readiness_counts": {"live_workflow": 0},
        "security_pass_current": False,
        "rails": [
            {
                "rail_id": "chief_orchestration_work_packets",
                "rail_name": "Chief orchestration/planning/work packets",
                "maturity": "READ_MODEL_VISIBLE",
                "steel_thread_stage_reached": "work_board_and_agent_work_packets_visible",
                "authority_boundary": "read-model only",
            }
        ],
    }
    delta = {
        "schema_version": "repo_b_remaining_capability_delta_map_v0",
        "repo_b_reference_only": True,
        "capability_delta_list": [
            {
                "capability_id": "chief_orchestrator_planner_status",
                "classification": "PARTIALLY_REPRESENTED_IN_REPO_A",
                "short_description": "Chief status is partly represented.",
                "authority_risk": "high_if_legacy_chief_runtime_or_watchers_are_activated",
                "suggested_future_lane": "Chief Status Rail Completion v0",
                "reference_only": True,
                "repo_b_body_read": False,
                "repo_b_code_executed": False,
            },
            {
                "capability_id": "automatic_fix_repair_loops",
                "classification": "UNSAFE_OR_BLOCKED",
                "short_description": "Automatic repair remains blocked.",
                "authority_risk": "high_automatic_mutation_or_self_repair_if_enabled",
                "suggested_future_lane": "Automatic Repair Loop Contract Harvest v0",
                "reference_only": True,
                "repo_b_body_read": False,
                "repo_b_code_executed": False,
            },
        ],
    }
    baseline_path = _write(root / "generated/read_models/repo_a_known_rail_completion_map.json", json.dumps(baseline))
    delta_path = _write(root / "generated/read_models/repo_b_remaining_capability_delta_map.json", json.dumps(delta))
    for rel in [
        "agent_lane_registry.py",
        "work_board.py",
        "agent_work_packet.py",
        "intent_router.py",
        "operator_intent_core.py",
        "dropped_intent_registry.py",
        "chief_listener.py",
        "chief_router.py",
        "chief_session_manager.py",
        "chief_notify.py",
        "chief_sender.py",
        "chief_llm.py",
        "brain_dump_parser.py",
        "queue_balancer.py",
        "queue_validator.py",
        "module_registry.py",
        "capability_registry.py",
        "custom_build_module_detangling_contract.py",
        "polish_loop/orchestrator.py",
        "generated/read_models/work_board.json",
        "generated/read_models/agent_work_packets.json",
        "generated/read_models/intent_router.json",
        "generated/read_models/dropped_intents.json",
        "generated/read_models/active_machinery_high_risk_quarantine.json",
        "generated/read_models/active_machinery_block_later_guardrail.json",
        "generated/read_models/active_machinery_quarantine_decision_packet.json",
        "generated/read_models/operator_sovereignty_power_stage_gate.json",
        "generated/read_models/cassandra_email_calendar_capability_reconciliation.json",
        "generated/read_models/niles_album_review_packet.json",
        "generated/read_models/capital_hilton_actionable_review_packet.json",
        "generated/read_models/cassandra_draft_review_packet.json",
        "generated/read_models/sync_health.json",
        "tests/test_work_board.py",
        "tests/test_agent_work_packet.py",
        "tests/test_operator_intent_core.py",
    ]:
        _write(root / rel, "{}\n" if rel.endswith(".json") else "# fixture\n")
    return baseline_path, delta_path


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    baseline, delta = _fixture_repo(repo)
    return chief_map.build_chief_role_capability_segmentation_map(
        repo_root=repo,
        repo_a_baseline_json=baseline,
        repo_b_delta_json=delta,
        generated_at=FIXED_NOW,
    )


def test_path_b_used_when_chief_is_broad_or_ambiguous(tmp_path):
    payload = _build(tmp_path)

    assert payload["path_b_segmentation_map_used"] is True
    assert payload["path_a_smallest_status_rail_completed"] is False
    assert payload["chief_complete_as_one_rail_now"] is False
    assert payload["segmentation_required"] is True
    assert payload["chief_sub_area_count"] >= 10
    assert payload["classification_counts"]["SEGMENTATION_REQUIRED"] >= 1


def test_chief_not_modeled_as_executor_and_no_authority_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in chief_map.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["chief_modeled_as_executor"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["execution_authority_added"] is False
    assert payload["live_execution_recommended"] is False
    assert payload["unknown_authority_fails_closed"] is True


def test_role_claims_distinguish_proven_inferred_and_memory_guidance(tmp_path):
    payload = _build(tmp_path)

    assert payload["proven_current_repo_a_behavior"]
    assert payload["inferred_not_proven"]
    assert payload["operator_memory_or_repo_b_vault_map_guidance"]
    identity = next(item for item in payload["chief_sub_areas"] if item["sub_area_id"] == "chief_identity_role_boundaries")
    assert identity["proven_current_repo_a_behavior"]
    assert identity["inferred_role_from_filenames_or_contracts"]
    assert identity["operator_memory_guidance"]
    assert identity["needs_operator_memory_review"] is True


def test_work_packets_are_visibility_or_planning_not_execution(tmp_path):
    payload = _build(tmp_path)
    work_packets = next(item for item in payload["chief_sub_areas"] if item["sub_area_id"] == "chief_work_packets")

    assert payload["work_packets_are_visibility_review_planning_only"] is True
    assert work_packets["classification"] == "TESTED_SUPPORTING_CONTRACT"
    assert work_packets["chief_executor_authority"] is False
    assert "auto-execute" in work_packets["blocked_or_future_gated"]
    assert "agent activation" in work_packets["blocked_or_future_gated"]


def test_planner_builder_repair_telegram_and_llm_concepts_remain_blocked(tmp_path):
    payload = _build(tmp_path)
    by_id = {item["sub_area_id"]: item for item in payload["chief_sub_areas"]}

    assert by_id["planner_builder_coordination"]["classification"] == "UNSAFE_OR_BLOCKED"
    assert by_id["automatic_fix_repair_loop_concepts"]["classification"] == "UNSAFE_OR_BLOCKED"
    assert by_id["telegram_notification_concepts"]["classification"] == "UNSAFE_OR_BLOCKED"
    assert by_id["llm_ollama_service_concepts"]["classification"] == "UNSAFE_OR_BLOCKED"
    assert payload["old_automation_fix_loop_concepts_blocked"] is True
    assert payload["telegram_notification_concepts_non_live"] is True
    assert payload["llm_ollama_tool_concepts_non_live"] is True


def test_unknown_chief_authority_fails_closed_for_every_sub_area(tmp_path):
    payload = _build(tmp_path)

    assert all(item["unknown_authority_fails_closed"] is True for item in payload["chief_sub_areas"])
    assert all(item["live_runtime_authority"] is False for item in payload["chief_sub_areas"])
    assert all(item["chief_executor_authority"] is False for item in payload["chief_sub_areas"])


def test_eli5_summary_exists_and_is_plain(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "Repo A proves pieces of Chief" in eli5["summary_text"]
    assert eli5["can_chief_be_completed_as_one_rail_now"] is False
    assert "No live Telegram push" in eli5["cannot_do_yet"]
    assert eli5["next_1_to_3_chief_lanes"]


def test_recommendations_are_bounded_and_not_live_execution(tmp_path):
    payload = _build(tmp_path)

    assert payload["recommended_next_lanes_all_gate_pass"] is True
    assert [item["lane_name"] for item in payload["future_lane_recommendations"]] == [
        "Chief Status Rail Completion v0",
        "Build Now Vs Hold Queue Posture v0",
        "Chief Domain Overlap Segmentation Review v0",
    ]
    for item in payload["future_lane_recommendations"]:
        gate = item["post_preflight_batch_gate_evaluation"]
        assert gate["gate_status"] == "pass"
        assert gate["runtime_authority_added"] is False
        assert gate["send_or_submit_authority_added"] is False
        assert gate["customer_deployment_authority_added"] is False


def test_repo_b_is_not_reinspected_and_delta_read_model_is_reference_only(tmp_path):
    payload = _build(tmp_path)

    assert payload["repo_a_only_inspection"] is True
    assert payload["repo_b_filesystem_inspected"] is False
    assert payload["repo_b_delta_read_model_used"] is True
    assert payload["repo_b_delta_reference"]["repo_b_filesystem_reinspected_by_this_lane"] is False
    assert payload["repo_b_delta_reference"]["repo_b_reference_only"] is True


def test_export_writes_valid_json_and_operator_packet(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    baseline, delta = _fixture_repo(repo)

    exit_code = export_main(
        [
            "--repo-root",
            str(repo),
            "--repo-a-baseline-json",
            str(baseline),
            "--repo-b-delta-json",
            str(delta),
            "--export-root",
            "generated/read_models",
            "--format",
            "operator",
        ]
    )
    operator_text = capsys.readouterr().out
    payload = json.loads((repo / "generated/read_models" / chief_map.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert (repo / "generated/read_models" / chief_map.OPERATOR_EXPORT_NAME).is_file()
    assert "Chief Role + Capability Segmentation Map" in operator_text
    assert "ELI5 Summary" in operator_text
    assert payload["path_b_segmentation_map_used"] is True


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    repo = tmp_path / "repo_a"
    baseline, delta = _fixture_repo(repo)

    chief_map.export_chief_role_capability_segmentation_map(
        repo_root=repo,
        repo_a_baseline_json=baseline,
        repo_b_delta_json=delta,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))
    assert chief_map.JSON_EXPORT_NAME in expected
    assert chief_map.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_execute_shell_network_or_import_live_chief_modules():
    source_files = [
        Path("chief_role_capability_segmentation_map.py"),
        Path("scripts/export_chief_role_capability_segmentation_map.py"),
    ]
    forbidden_text = [
        "subprocess.",
        "os.system",
        "asyncio.",
        "requests.",
        "httpx.",
        "urllib.request",
        "ollama_call(",
        "ApplicationBuilder",
        "reply_text(",
        "send_message",
        "send_email",
        "import cassandra_",
        "from cassandra_",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_text:
            assert needle not in text
        tree = ast.parse(text)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert not any(
            (name.startswith("chief_") and name != "chief_role_capability_segmentation_map")
            or name.startswith("cassandra_")
            for name in imported
        )
