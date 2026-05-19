import ast
import json
from pathlib import Path

import build_now_vs_hold_queue_posture as posture
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_build_now_vs_hold_queue_posture import main as export_main


FIXED_NOW = "2026-05-18T22:00:00+00:00"


def _write(path: Path, text: str = "# fixture\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _fixture_repo(root: Path) -> None:
    fixtures = {
        "generated/read_models/chief_status_rail.json": {
            "schema_version": "chief_status_rail_v0",
            "rail_status": "completed_visibility_planning_only",
        },
        "generated/read_models/chief_role_capability_segmentation_map.json": {
            "schema_version": "chief_role_capability_segmentation_map_v0",
        },
        "generated/read_models/repo_a_known_rail_completion_map.json": {
            "schema_version": "repo_a_known_rail_completion_map_v0",
        },
        "generated/read_models/repo_b_remaining_capability_delta_map.json": {
            "schema_version": "repo_b_remaining_capability_delta_map_v0",
            "repo_b_reference_only": True,
        },
        "generated/read_models/intent_router.json": {
            "schema_version": "intent_router_read_model_v0",
            "counts_by_agent": {"chief": 2},
            "runtime_authority": False,
            "tool_execution_allowed": False,
        },
        "generated/read_models/work_board.json": {
            "schema_version": "work_board_read_model_v0",
            "counts_by_agent": {"chief": 3},
            "latest_cards": [
                {
                    "card_id": "card_routed",
                    "title": "Intent: Chief, organize Markdown files.",
                    "summary": "Draft an advisory plan; do not move files.",
                    "board_column": "routed",
                    "agent_id": "chief",
                    "lane_id": "system_orchestration",
                    "intent_category": "markdown_reorg_request",
                    "world_hint": "operations",
                    "execution_allowed": False,
                    "approval_required": True,
                    "next_safe_move": "Draft an advisory reorg plan.",
                },
                {
                    "card_id": "card_unknown",
                    "title": "Intent: Hermes, synthesize current posture.",
                    "summary": "Ask the operator for a clearer target.",
                    "board_column": "needs_review",
                    "agent_id": "hermes",
                    "lane_id": "advisory_synthesis",
                    "intent_category": "unknown_review",
                    "world_hint": "unknown",
                    "execution_allowed": False,
                    "approval_required": True,
                    "next_safe_move": "Ask the operator for a clearer target.",
                },
            ],
        },
        "generated/read_models/agent_work_packets.json": {
            "schema_version": "agent_work_packets_read_model_v0",
            "counts_by_agent": {"chief": 1},
            "packets": [
                {
                    "packet_id": "packet_ready",
                    "goal": "Propose a Markdown organization plan without moving files.",
                    "status": "draft",
                    "routed_agent_id": "chief",
                    "routed_lane_id": "system_orchestration",
                    "intent_category": "markdown_reorg_request",
                    "world_hint": "operations",
                    "execution_allowed": False,
                    "approval_required": True,
                }
            ],
        },
        "generated/read_models/dropped_intents.json": {
            "schema_version": "dropped_intents_read_model_v0",
            "counts_by_agent": {"chief": 4},
            "top_unresolved_items": [
                {
                    "dropped_intent_id": "drop_context",
                    "title": "Recent File Context Resolver",
                    "short_summary": "Resolve requests like that new file using metadata.",
                    "current_status": "unresolved",
                    "agent_hint": "chief",
                    "lane_hint": "system_orchestration",
                    "intent_category": "file_context_request",
                    "world_hint": "operations",
                    "approval_required": True,
                    "suggested_next_question": "Build recent-file context resolution?",
                    "evidence_basis": "missing context",
                },
                {
                    "dropped_intent_id": "drop_proof",
                    "title": "Mission Control action request writing",
                    "short_summary": "Prepare an operator action request with approval proof.",
                    "current_status": "unresolved",
                    "agent_hint": "chief",
                    "lane_hint": "system_orchestration",
                    "intent_category": "operator_action_request",
                    "world_hint": "operations",
                    "approval_required": True,
                    "suggested_next_question": "Capture proof first?",
                    "evidence_basis": "needs proof",
                },
            ],
            "deferred_items": [
                {
                    "dropped_intent_id": "drop_hold",
                    "title": "Project Capsule Real Template Workflow",
                    "short_summary": "Promote synthetic capsule later.",
                    "current_status": "deferred",
                    "agent_hint": "chief",
                    "lane_hint": "system_orchestration",
                    "intent_category": "project_capsule_request",
                    "world_hint": "business_development",
                    "approval_required": True,
                    "suggested_next_question": "Do this later?",
                    "evidence_basis": "deferred",
                },
                {
                    "dropped_intent_id": "drop_security",
                    "title": "Planner/builder autonomous repair loop",
                    "short_summary": "Start self-repair builder automation later.",
                    "current_status": "deferred",
                    "agent_hint": "chief",
                    "lane_hint": "system_orchestration",
                    "intent_category": "automation_request",
                    "world_hint": "build",
                    "approval_required": True,
                    "suggested_next_question": "Future security threshold only.",
                    "evidence_basis": "planner/builder autonomous repair",
                },
            ],
            "unknown_review_items": [
                {
                    "dropped_intent_id": "drop_unknown",
                    "title": "Unknown old Chief memory",
                    "short_summary": "Needs operator review.",
                    "current_status": "unknown_review",
                    "agent_hint": "chief",
                    "lane_hint": "system_orchestration",
                    "intent_category": "unknown_review",
                    "world_hint": "unknown",
                    "approval_required": True,
                    "suggested_next_question": "What is this?",
                    "evidence_basis": "operator memory review",
                }
            ],
            "built_items": [],
        },
        "generated/read_models/operator_actions.json": {
            "schema_version": "operator_actions_read_model_v0",
            "runtime_activation_allowed": False,
            "arbitrary_shell_allowed": False,
        },
    }
    for rel, payload in fixtures.items():
        _write(root / rel, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return posture.build_build_now_vs_hold_queue_posture(repo_root=repo, generated_at=FIXED_NOW)


def test_chief_status_precondition_is_checked_and_satisfied(tmp_path):
    payload = _build(tmp_path)

    assert payload["chief_status_precondition"]["satisfied"] is True
    assert payload["chief_status_precondition"]["schema_version"] == "chief_status_rail_v0"
    assert payload["posture_scope"] == "visibility_routing_work_packet_posture_only"


def test_build_now_posture_is_not_execution_authority(tmp_path):
    payload = _build(tmp_path)

    assert payload["build_now_is_execution_authority"] is False
    assert payload["safe_work_packet_posture"]["work_packet_execution_authority"] is False
    assert payload["safe_work_packet_posture"]["agent_activation_allowed"] is False
    assert payload["safe_work_packet_posture"]["tool_execution_allowed"] is False


def test_classifies_build_now_hold_context_proof_blocked_and_unknown(tmp_path):
    payload = _build(tmp_path)
    counts = payload["classification_counts"]

    assert counts["BUILD_NOW_READY"] >= 1
    assert counts["HOLD_FOR_RIGHT_TIME"] >= 1
    assert counts["NEEDS_CONTEXT"] >= 1
    assert counts["NEEDS_PROOF"] >= 1
    assert counts["BLOCKED_SECURITY_THRESHOLD"] >= 1
    assert counts["UNKNOWN_FAIL_CLOSED"] >= 1


def test_hold_for_later_preserves_intent_without_pretending_readiness(tmp_path):
    payload = _build(tmp_path)
    hold = payload["items_by_category"]["HOLD_FOR_RIGHT_TIME"][0]

    assert payload["hold_for_later_preserves_intent_without_readiness"] is True
    assert hold["can_become_work_packet"] is False
    assert hold["build_now_is_execution_authority"] is False


def test_blocked_authority_items_fail_closed_and_security_threshold_future(tmp_path):
    payload = _build(tmp_path)
    blocked = payload["items_by_category"]["BLOCKED_SECURITY_THRESHOLD"][0]

    assert blocked["posture_category"] == "BLOCKED_SECURITY_THRESHOLD"
    assert payload["security_threshold_posture"] == "future_not_current"
    assert payload["security_pass_started"] is False
    assert payload["unknown_items_fail_closed"] is True


def test_no_build_planner_repair_shell_or_repo_b_execution_occurs(tmp_path):
    payload = _build(tmp_path)

    for key, expected in posture.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["planner_builder_automation_activated"] is False
    assert payload["repair_fix_loop_activated"] is False
    assert payload["arbitrary_shell_allowed"] is False
    assert payload["repo_b_code_executed"] is False


def test_eli5_summary_and_next_lanes_are_bounded_non_live(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "enough safe context" in eli5["how_openclaw_decides_build_now_vs_hold"]
    assert "blocked" in eli5["what_is_blocked_on_purpose"]
    assert len(eli5["next_1_to_3_sensible_lanes"]) == 3
    assert payload["recommended_next_lanes_all_gate_pass"] is True
    for item in payload["future_lane_recommendations"]:
        gate = item["post_preflight_batch_gate_evaluation"]
        assert gate["gate_status"] == "pass"
        assert gate["runtime_authority_added"] is False
        assert gate["send_or_submit_authority_added"] is False


def test_export_writes_valid_json_and_operator_output(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    exit_code = export_main(["--repo-root", str(repo), "--export-root", "generated/read_models", "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((repo / "generated/read_models" / posture.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "Build Now Vs Hold Queue Posture" in operator_text
    assert "ELI5 Summary" in operator_text
    assert (repo / "generated/read_models" / posture.OPERATOR_EXPORT_NAME).is_file()
    assert payload["chief_status_precondition"]["satisfied"] is True


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    posture.export_build_now_vs_hold_queue_posture(repo_root=repo, export_root="generated/read_models", generated_at=FIXED_NOW)
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))
    assert posture.JSON_EXPORT_NAME in expected
    assert posture.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_execute_shell_network_or_import_runtime_modules():
    source_files = [
        Path("build_now_vs_hold_queue_posture.py"),
        Path("scripts/export_build_now_vs_hold_queue_posture.py"),
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
        "import chief_",
        "from chief_",
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
        assert not any(name.startswith("chief_") or name.startswith("cassandra_") for name in imported)
