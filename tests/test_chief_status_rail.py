import ast
import json
from pathlib import Path

import chief_status_rail as status_rail
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_chief_status_rail import main as export_main


FIXED_NOW = "2026-05-18T21:00:00+00:00"


def _write(path: Path, text: str = "# fixture\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _fixture_repo(root: Path) -> None:
    segmentation = {
        "schema_version": "chief_role_capability_segmentation_map_v0",
        "repo_b_delta_read_model_used": True,
        "chief_sub_areas": [
            {
                "sub_area_id": "chief_work_packets",
                "display_name": "Chief work packets",
                "classification": "TESTED_SUPPORTING_CONTRACT",
                "claim_level": "proven_control_plane_artifact",
                "authority_boundary": "Work packets are review/planning artifacts.",
                "next_safe_lane": "Chief Status Rail Completion v0",
                "needs_operator_memory_review": False,
                "operator_memory_guidance": [],
            },
            {
                "sub_area_id": "chief_status_posture",
                "display_name": "Chief status posture",
                "classification": "PARTIALLY_REPRESENTED",
                "claim_level": "partially_proven_read_model_gap",
                "authority_boundary": "Status visibility only.",
                "next_safe_lane": "Chief Status Rail Completion v0",
                "needs_operator_memory_review": False,
                "operator_memory_guidance": ["Chief may have been where real work flowed."],
            },
            {
                "sub_area_id": "chief_identity_role_boundaries",
                "display_name": "Chief identity / role / boundaries",
                "classification": "SEGMENTATION_REQUIRED",
                "claim_level": "proven_partial_inferred_broad",
                "authority_boundary": "Executor authority fails closed.",
                "next_safe_lane": "Chief Status Rail Completion v0",
                "needs_operator_memory_review": True,
                "operator_memory_guidance": ["Older memory suggests Chief was broader."],
            },
            {
                "sub_area_id": "telegram_notification_concepts",
                "display_name": "Telegram / notification concepts",
                "classification": "UNSAFE_OR_BLOCKED",
                "claim_level": "legacy_live_adjacency_blocked",
                "authority_boundary": "No live Chief Telegram notification.",
                "next_safe_lane": "Chief Notification Boundary Review v0",
                "needs_operator_memory_review": False,
                "operator_memory_guidance": ["Older memory mentions chief_notify.py."],
            },
        ],
    }
    work_board = {
        "schema_version": "work_board_read_model_v0",
        "counts_by_agent": {"chief": 5, "cassandra": 1},
        "counts_by_column": {"routed": 3, "needs_review": 2},
        "direct_execution_allowed": False,
        "agent_activation_allowed": False,
        "model_call_allowed": False,
        "tool_execution_allowed": False,
    }
    packets = {
        "schema_version": "agent_work_packets_read_model_v0",
        "counts_by_agent": {"chief": 2},
        "counts_by_status": {"draft": 2},
        "execution_allowed": False,
        "agent_activation_allowed": False,
        "model_call_allowed": False,
        "tool_execution_allowed": False,
    }
    router = {
        "schema_version": "intent_router_read_model_v0",
        "counts_by_agent": {"chief": 4},
        "counts_by_category": {"markdown_reorg_request": 2},
        "direct_execution_allowed": False,
        "runtime_authority": False,
        "model_execution_allowed": False,
        "tool_execution_allowed": False,
        "source_posture": {"telegram": "metadata_only", "cli": "request_only"},
    }
    dropped = {
        "schema_version": "dropped_intents_read_model_v0",
        "counts_by_agent": {"chief": 3},
        "counts_by_status": {"deferred": 2, "unresolved": 1},
        "notification_allowed": False,
        "autonomous_prompting_allowed": False,
        "model_call_allowed": False,
        "raw_private_scan_allowed": False,
    }
    fixtures = {
        "generated/read_models/chief_role_capability_segmentation_map.json": segmentation,
        "generated/read_models/work_board.json": work_board,
        "generated/read_models/agent_work_packets.json": packets,
        "generated/read_models/intent_router.json": router,
        "generated/read_models/dropped_intents.json": dropped,
    }
    for rel, payload in fixtures.items():
        _write(root / rel, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return status_rail.build_chief_status_rail(repo_root=repo, generated_at=FIXED_NOW)


def test_chief_status_represents_current_proven_role(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == status_rail.SCHEMA_VERSION
    assert payload["rail_status"] == "completed_visibility_planning_only"
    assert payload["chief_current_status"] == "safe_status_read_model_only"
    assert payload["chief_current_proven_role"]["executor"] is False
    assert "request-only coordination" in payload["chief_current_proven_role"]["role_summary"]


def test_status_surfaces_and_inputs_are_visible_without_execution(tmp_path):
    payload = _build(tmp_path)
    surfaces = payload["work_packet_status_surfaces_available"]

    assert surfaces["chief_card_count"] == 5
    assert surfaces["chief_packet_count"] == 2
    assert surfaces["chief_route_count"] == 4
    assert surfaces["chief_dropped_intent_count"] == 3
    assert payload["visible_status_signals"]["work_board"]["direct_execution_allowed"] is False
    assert payload["visible_status_signals"]["agent_work_packets"]["execution_allowed"] is False
    assert payload["visible_status_signals"]["intent_router"]["runtime_authority"] is False


def test_chief_is_not_modeled_as_executor_and_no_authority_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in status_rail.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["chief_modeled_as_executor"] is False
    assert payload["unknown_chief_authority_fails_closed"] is True
    assert payload["live_execution_recommended"] is False


def test_status_does_not_activate_planner_builder_repair_telegram_llm_or_shell(tmp_path):
    payload = _build(tmp_path)
    blocked = payload["explicitly_blocked"]

    assert blocked["planner_builder_automation"] is True
    assert blocked["repair_fix_loops"] is True
    assert blocked["telegram_notification_or_send"] is True
    assert blocked["llm_or_ollama_calls"] is True
    assert blocked["tool_execution"] is True
    assert blocked["arbitrary_shell"] is True
    assert payload["planner_builder_automation_activated"] is False
    assert payload["repair_fix_loop_activated"] is False
    assert payload["telegram_send_triggered"] is False
    assert payload["llm_ollama_called"] is False


def test_status_distinguishes_proven_inferred_memory_and_blocked(tmp_path):
    payload = _build(tmp_path)
    model = payload["status_category_model"]

    assert model["proven"]
    assert model["partially_represented"]
    assert model["inferred_not_proven"]
    assert model["operator_memory_only"]
    assert model["unsafe_blocked"]
    assert "Chief as a broader central orchestration spine" in payload["inferred_but_not_proven"]


def test_work_packets_are_visibility_planning_artifacts_not_execution_authority(tmp_path):
    payload = _build(tmp_path)

    assert payload["work_packets_are_visibility_review_planning_only"] is True
    packet_substrate = next(
        item for item in payload["current_chief_related_substrates"] if item["substrate"] == "agent_work_packets"
    )
    assert packet_substrate["authority"] == "packet_draft_only"


def test_eli5_summary_exists_and_next_lane_is_bounded_non_live(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]
    next_lane = payload["next_safe_chief_lane"]

    assert "Chief is currently a safe coordination/status rail" in eli5["here_is_what_chief_currently_is"]
    assert "not a live executor" in eli5["here_is_what_chief_is_not_yet"]
    assert next_lane["lane_name"] == "Build Now Vs Hold Queue Posture v0"
    assert next_lane["gate_status"] == "pass"
    assert next_lane["non_live"] is True
    assert next_lane["no_queue_execution"] is True


def test_export_writes_valid_json_and_operator_output(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    exit_code = export_main(["--repo-root", str(repo), "--export-root", "generated/read_models", "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((repo / "generated/read_models" / status_rail.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "Chief Status Rail" in operator_text
    assert "ELI5 Summary" in operator_text
    assert (repo / "generated/read_models" / status_rail.OPERATOR_EXPORT_NAME).is_file()
    assert payload["chief_current_status"] == "safe_status_read_model_only"


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    status_rail.export_chief_status_rail(repo_root=repo, export_root="generated/read_models", generated_at=FIXED_NOW)
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))
    assert status_rail.JSON_EXPORT_NAME in expected
    assert status_rail.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_execute_shell_network_or_import_live_chief_modules():
    source_files = [
        Path("chief_status_rail.py"),
        Path("scripts/export_chief_status_rail.py"),
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
            (name.startswith("chief_") and name != "chief_status_rail")
            or name.startswith("cassandra_")
            for name in imported
        )
