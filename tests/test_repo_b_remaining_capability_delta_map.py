import ast
import json
from pathlib import Path

import repo_b_remaining_capability_delta_map as delta
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_repo_b_remaining_capability_delta_map import main as export_main


FIXED_NOW = "2026-05-18T20:00:00+00:00"


def _write(path: Path, text: str = "# fixture\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _repo_a_fixture(root: Path) -> Path:
    baseline = {
        "schema_version": "repo_a_known_rail_completion_map_v0",
        "known_rail_count": 14,
        "maturity_counts": {"READ_MODEL_VISIBLE": 5},
        "readiness_counts": {"live_workflow": 0, "visibility_only": 14},
        "security_pass_current": False,
    }
    baseline_path = root / "generated/read_models/repo_a_known_rail_completion_map.json"
    _write(baseline_path, json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    for rel in [
        "generated/read_models/cassandra_listener_governed_shadow.json",
        "generated/read_models/cassandra_draft_review_packet.json",
        "generated/read_models/cassandra_email_calendar_capability_reconciliation.json",
        "generated/read_models/guardian_draft_approval_request_contract.json",
        "generated/read_models/guardian_hitl_authority_reconciliation.json",
        "generated/read_models/guardian_hitl_sqlite_authority_contract.json",
        "generated/read_models/work_board.json",
        "generated/read_models/agent_work_packets.json",
        "generated/read_models/intent_router.json",
        "generated/read_models/dropped_intents.json",
        "generated/read_models/niles_album_review_packet.json",
        "generated/read_models/niles_album_evidence_intake_boundary.json",
        "generated/read_models/report_bridge.json",
        "generated/read_models/custom_build_module_detangling_contract.json",
        "generated/read_models/operator_sovereignty_power_stage_gate.json",
        "generated/read_models/sync_health.json",
        "generated/read_models/context_selection.json",
        "hermes_advisory_packet.py",
        "OPENCLAW_RUNTIME.md",
        "USER.md",
    ]:
        _write(root / rel, "{}\n" if rel.endswith(".json") else "# fixture\n")
    return baseline_path


def _repo_b_fixture(root: Path) -> Path:
    for rel in [
        "cassandra_listener.py",
        "cassandra_brain.py",
        "cassandra_outreach.py",
        "chief_email_brain.py",
        "chief_calendar_brain.py",
        "chief_router.py",
        "chief_queue_brain.py",
        "chief_approval_brain.py",
        "chief_guardian_listener.py",
        "builder_watcher.sh",
        "loop_supervisor.sh",
        "polish_loop/orchestrator.py",
        "polish_loop/pc_review_fallback.py",
        "queue_balancer.py",
        "queue_validator.py",
        "inbox_parser.py",
        "chief_album_brain.py",
        "chief_reporter_brain.py",
        "dashboard_gen.py",
        "google_access_broker.py",
        "google_access_policy.py",
        "pii_vault.py",
        "capability_registry.py",
        "skill_loader.py",
        "skill_vetter.py",
        "budget_tracker.py",
        "CLAUDE.md",
        ".claude/commands/cassandra.md",
        "private_token.json",
        "polish_loop/tasks/private-task.md",
    ]:
        _write(root / rel)
    return root


def _build(tmp_path: Path) -> dict:
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    baseline = _repo_a_fixture(repo_a)
    _repo_b_fixture(repo_b)
    return delta.build_repo_b_remaining_capability_delta_map(
        repo_a_root=repo_a,
        repo_b_root=repo_b,
        baseline_json=baseline,
        generated_at=FIXED_NOW,
    )


def test_repo_b_is_reference_only_and_no_body_execution_occurs(tmp_path):
    payload = _build(tmp_path)

    assert payload["repo_b_reference_only"] is True
    assert payload["repo_b_code_executed"] is False
    assert payload["repo_b_modules_imported"] is False
    assert payload["repo_b_inspection"]["body_read"] is False
    assert payload["repo_b_inspection"]["repo_b_code_executed"] is False
    assert payload["repo_b_inspection"]["skipped_sensitive_or_no_go_count"] >= 2
    inspected = "\n".join(payload["repo_b_inspection"]["representative_paths"])
    assert "private_token.json" not in inspected
    assert "polish_loop/tasks/private-task.md" not in inspected


def test_live_authority_remains_blocked():
    payload = delta.build_repo_b_remaining_capability_delta_map(generated_at=FIXED_NOW)

    for key, expected in delta.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["security_pass_current"] is False
    assert payload["live_execution_recommended"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False


def test_already_represented_missing_partial_unsafe_and_worth_classifications_are_present(tmp_path):
    payload = _build(tmp_path)
    counts = payload["classification_counts"]

    assert counts["ALREADY_REPRESENTED_IN_REPO_A"] >= 1
    assert counts["PARTIALLY_REPRESENTED_IN_REPO_A"] >= 1
    assert counts["MISSING_FROM_REPO_A"] >= 1
    assert counts["UNSAFE_OR_BLOCKED"] >= 1
    assert counts["WORTH_BRINGING_FORWARD"] >= 1
    by_id = {item["capability_id"]: item for item in payload["capability_delta_list"]}
    assert by_id["cassandra_core_listener_review"]["classification"] == "ALREADY_REPRESENTED_IN_REPO_A"
    assert by_id["planner_builder_automation_loops"]["classification"] == "UNSAFE_OR_BLOCKED"
    assert by_id["dropped_intent_task_queue_timing"]["classification"] == "WORTH_BRINGING_FORWARD"
    assert by_id["claude_command_notes"]["classification"] == "MISSING_FROM_REPO_A"


def test_unknowns_fail_closed_and_operator_memory_review_items_exist(tmp_path):
    payload = _build(tmp_path)
    by_id = {item["capability_id"]: item for item in payload["capability_delta_list"]}

    assert by_id["hermes_advisory_synthesis"]["classification"] == "UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW"
    assert payload["operator_memory_review_items"]
    hermes_gap = next(item for item in payload["remembered_but_not_proven_gaps"] if item["remembered_area"] == "Hermes status")
    assert hermes_gap["needs_operator_memory_review"] is True
    assert hermes_gap["status"] == "needs_operator_memory_review"


def test_eli5_summary_and_memory_gap_statuses_are_present(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]
    gap_names = {item["remembered_area"] for item in payload["remembered_but_not_proven_gaps"]}

    assert "Repo B still contains" in eli5["summary_text"]
    assert eli5["already_handled_or_represented"]
    assert eli5["partly_tracked"]
    assert eli5["may_need_bring_forward"]
    assert eli5["unsafe_old_or_blocked"]
    assert set(delta.REMEMBERED_GAPS).issubset(gap_names)


def test_recommendations_are_bounded_and_do_not_recommend_live_execution(tmp_path):
    payload = _build(tmp_path)
    recommendations = payload["future_lane_recommendations"]

    assert len(recommendations) == 3
    assert payload["recommended_next_lanes_all_gate_pass"] is True
    assert [item["lane_name"] for item in recommendations] == [
        "Chief Status Rail Completion v0",
        "Build Now Vs Hold Queue Posture v0",
        "Protected Access Broker Concept Delta v0",
    ]
    for item in recommendations:
        gate = item["post_preflight_batch_gate_evaluation"]
        assert gate["gate_status"] == "pass"
        assert gate["runtime_authority_added"] is False
        assert gate["send_or_submit_authority_added"] is False
        assert gate["customer_deployment_authority_added"] is False


def test_security_pass_remains_future_threshold_not_current(tmp_path):
    payload = _build(tmp_path)

    assert payload["baseline_repo_a"]["security_pass_current"] is False
    assert payload["security_pass_current"] is False
    assert payload["security_pass_posture"] == "future_threshold_not_current_delta_lane"
    assert payload["security_pass_started"] is False


def test_export_writes_valid_json_and_operator_packet(tmp_path, capsys):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    baseline = _repo_a_fixture(repo_a)
    _repo_b_fixture(repo_b)
    export_root = tmp_path / "repo_a/generated/read_models"

    exit_code = export_main(
        [
            "--repo-a-root",
            str(repo_a),
            "--repo-b-root",
            str(repo_b),
            "--baseline-json",
            str(baseline),
            "--export-root",
            "generated/read_models",
            "--format",
            "operator",
        ]
    )
    operator_text = capsys.readouterr().out
    payload = json.loads((export_root / delta.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert (export_root / delta.OPERATOR_EXPORT_NAME).is_file()
    assert "Repo B Remaining Capability Delta Map" in operator_text
    assert "ELI5 Summary" in operator_text
    assert payload["repo_b_code_executed"] is False
    assert payload["repo_b_reference_only"] is True


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    baseline = _repo_a_fixture(repo_a)
    _repo_b_fixture(repo_b)
    export_root = repo_a / "generated/read_models"

    delta.export_repo_b_remaining_capability_delta_map(
        repo_a_root=repo_a,
        repo_b_root=repo_b,
        baseline_json=baseline,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )
    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=repo_a))
    assert delta.JSON_EXPORT_NAME in expected
    assert delta.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_execute_shell_network_or_import_repo_b_modules():
    source_files = [
        Path("repo_b_remaining_capability_delta_map.py"),
        Path("scripts/export_repo_b_remaining_capability_delta_map.py"),
    ]
    forbidden_text = [
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "send_message",
        "smtplib",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
        "git clone",
        "docker run",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden_text:
            assert token not in text

    tree = ast.parse(Path("repo_b_remaining_capability_delta_map.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
    repo_b_module_names = {"cassandra_brain", "chief_router", "google_access_broker", "runner_registry"}
    assert imported.isdisjoint(repo_b_module_names)
