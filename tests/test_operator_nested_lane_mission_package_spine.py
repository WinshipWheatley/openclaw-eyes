import ast
import json
import sqlite3
from pathlib import Path

import operator_nested_lane_mission_package_spine as spine
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_nested_lane_mission_package_spine import main as export_main


FIXED_NOW = "2026-05-19T18:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "awareness_gap_items_are_button_ready": True,
            "package_preview_only": True,
        },
        "capability_skill_registry_metadata_delta.json": {
            "schema_version": "capability_skill_registry_metadata_delta_v0",
            "metadata_only_registry": True,
        },
        "agent_work_packets.json": {
            "schema_version": "agent_work_packets_read_model_v0",
            "execution_allowed": False,
        },
        "operator_actions.json": {
            "schema_version": "operator_actions_read_model_v0",
            "runtime_activation_allowed": False,
        },
        "intent_router.json": {
            "schema_version": "intent_router_read_model_v0",
            "runtime_authority": False,
        },
        "work_board.json": {
            "schema_version": "work_board_read_model_v0",
            "direct_execution_allowed": False,
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)
    (read_models / "operator_awareness_agent_package_spine_OPERATOR.md").write_text(
        "# Operator Awareness\n",
        encoding="utf-8",
    )


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return spine.build_operator_nested_lane_mission_package_spine(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _lane(payload: dict, lane_id: str) -> dict:
    return next(lane for lane in payload["nested_lanes"] if lane["lane_id"] == lane_id)


def test_nested_lane_spine_is_deterministic_and_extends_existing_awareness_spine(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert spine.stable_json(first) == spine.stable_json(second)
    assert first["schema_version"] == spine.SCHEMA_VERSION
    assert first["spine_status"] == "deterministic_nested_lane_mission_package_contract_only"
    assert first["relationship_to_existing_spine"]["extends_existing_operator_awareness_spine"] is True
    assert first["relationship_to_existing_spine"]["does_not_replace_or_duplicate_gap_item_spine"] is True
    assert first["machine_proof"]["parent_awareness_spine_present"] is True


def test_top_system_awareness_lane_and_expected_sublanes_are_represented(tmp_path):
    payload = _build(tmp_path)
    top = payload["top_level_system_awareness_discovery_lane"]
    sublanes = set(payload["current_or_expected_sublanes"])

    assert top["lane_id"] == "system_awareness_discovery"
    assert top["lane_kind"] == "TOP_LEVEL_SYSTEM_DISCOVERY"
    assert "Winship" in " ".join(top["needs_winship_memory_comparison"])
    assert sublanes >= {
        "chief",
        "cassandra",
        "guardian",
        "niles",
        "hermes",
        "repo_b_leftovers",
        "mission_control_design_memory",
        "capital_hilton",
        "struna",
        "cue_parser_brain_dump_parser",
        "tool_plugin_registry",
        "model_router",
        "future_domain_workflow_lanes",
    }


def test_each_sublane_exposes_required_awareness_and_quieting_fields(tmp_path):
    payload = _build(tmp_path)
    required = set(payload["sublane_exposure_contract"]["each_sublane_should_eventually_expose"])

    assert required == set(spine.DEFAULT_SUBLANE_EXPOSURE_FIELDS)
    for lane in payload["nested_lanes"]:
        assert required <= set(lane["must_expose"])
        assert "known" in lane
        assert "partly_known" in lane
        assert "known_unknown" in lane
        assert "not_discovered" in lane
        assert "needs_winship_memory_comparison" in lane
        assert "blocked_not_authorized" in lane
        assert lane["safe_next_detour"]
        assert lane["what_would_make_lane_quiet"]
        assert lane["package_preview_available_not_dispatchable"] is lane["package_available"]
        assert lane["operator_memory_is_truth"] is False


def test_developer_mode_quiet_helm_and_domain_catalog_are_durable(tmp_path):
    payload = _build(tmp_path)
    helm = payload["helm_mode_contract"]
    catalog = payload["domain_world_catalog"]

    assert helm["current_mode"] == "DEVELOPER_MODE_BUILD_MODE"
    assert helm["developer_mode_build_mode"]["helm_is_noisy"] is True
    assert helm["quiet_operational_helm"]["helm_is_noisy"] is False
    assert "FULL_TRUST_DISPLAY_QUIET" in helm["quiet_operational_helm"]["confidence_display_policy"]
    assert "music/art" in catalog["domain_worlds_current_or_expected"]
    assert "gardening" in catalog["domain_worlds_current_or_expected"]
    assert catalog["world_entry_posture"]["actual_live_workspace_launch_now"] is False


def test_lane_attention_and_check_engine_are_distinct(tmp_path):
    payload = _build(tmp_path)
    contract = payload["check_engine_vs_lane_attention_contract"]
    niles = _lane(payload, "niles")
    guardian = _lane(payload, "guardian")

    assert contract["mission_control_should_not_conflate_attention_with_malfunction"] is True
    assert contract["lane_attention_flag"]["is_system_malfunction"] is False
    assert contract["check_engine_state"]["becomes"] == "Chief diagnostic/package problem"
    assert niles["lane_attention_flag"] == "NEEDS_CONTEXT"
    assert niles["check_engine_state"] == "NO_CHECK_ENGINE"
    assert niles["lane_attention_is_system_malfunction"] is False
    assert guardian["lane_attention_flag"] == "QUIET"


def test_actor_model_agent_character_and_candidate_models_are_metadata_only(tmp_path):
    payload = _build(tmp_path)
    doctrine = payload["actor_model_agent_character_doctrine"]

    assert doctrine["actor_model_definition"] == "The language model is the actor."
    assert "character/persona" in doctrine["agent_character_definition"]
    assert "script" in doctrine["package_definition"]
    labels = {item["label"] for item in doctrine["candidate_model_actor_labels"]}
    assert labels == set(spine.CANDIDATE_MODEL_ACTOR_LABELS)
    for item in doctrine["candidate_model_actor_labels"]:
        assert item["status"] == "candidate_label_only"
        assert item["live_integration_available"] is False
        assert item["api_key_or_endpoint_reference"] is None
        assert item["model_call_allowed"] is False
        assert item["unavailable_or_unknown_fails_closed"] is True


def test_mission_package_and_router_capture_deterministic_requirements(tmp_path):
    payload = _build(tmp_path)
    package = payload["mission_package_contract"]
    router = payload["deterministic_router_package_builder_requirements"]

    assert tuple(package["package_template_fields"]) == spine.MISSION_PACKAGE_FIELDS
    body = package["package_body_placeholder"]
    assert body["actor_model_candidate"] == "metadata_only_candidate_label_or_UNKNOWN_FAIL_CLOSED"
    assert "raw private content" in body["context_excluded"]
    assert "plugin wiring" in body["plugins_capabilities_forbidden"]
    assert body["security_clearance"] == "metadata_review_only_no_runtime_authority"
    assert package["package_hash_or_deterministic_placeholder"].startswith("sha256:")
    assert package["model_call_allowed"] is False
    assert package["agent_activation_allowed"] is False
    assert router["model_must_not_decide_own_authority_context_plugins_clearance_or_lane"] is True
    assert router["unknown_actor_or_missing_context"]["confidence_posture"] == "UNKNOWN_FAIL_CLOSED"


def test_confidence_detours_and_chat_workspace_launch_are_future_gated(tmp_path):
    payload = _build(tmp_path)
    confidence = payload["confidence_detour_contract"]
    launch = payload["chat_workspace_launch_posture"]

    assert confidence["below_deterministic_confidence"]["show_why_missing"] is True
    assert confidence["full_deterministic_trust"]["confidence_ui_should_mostly_disappear"] is True
    assert any(item["detour"] == "Capital Hilton Protected Proof Metadata Population" for item in confidence["safe_detour_examples"])
    assert any(item["lane_id"] == "repo_b_leftovers" and item["non_live"] is True for item in confidence["lane_confidence_repair"])
    assert launch["future_gated"] is True
    assert launch["live_chat_created_now"] is False
    assert launch["workspace_opened_now"] is False
    assert launch["launch_authority_added"] is False
    assert "create a live chat" in launch["must_not_do"]


def test_operator_doctrine_metadata_is_summary_only_not_raw_prompt_or_archive_ingest(tmp_path):
    payload = _build(tmp_path)
    doctrine = payload["operator_provided_design_doctrine_metadata"]

    assert doctrine["doctrine_id"] == spine.SCHEMA_VERSION
    assert doctrine["raw_operator_prompt_stored"] is False
    assert doctrine["broad_chat_or_design_archive_ingested"] is False
    assert doctrine["summary_only"] is True
    assert doctrine["summary_hash"].startswith("sha256:")
    assert payload["raw_design_archive_ingested"] is False
    assert payload["private_raw_content_inspected"] is False


def test_sqlite_doctrine_receipt_uses_existing_metadata_only_ledger_pattern(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "doctrine_receipts.sqlite"

    receipt_id = spine.record_operator_nested_lane_mission_package_doctrine_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = spine.record_operator_nested_lane_mission_package_doctrine_receipt(
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
    assert len(packets) == 1
    packet = json.loads(packets[0][0])
    assert packet["receipt_type"] == "generated_status"
    assert packet["authority_status"] == "generated_status_only"
    assert packet["sqlite_meaning"] == "receipt_record_only"
    assert packet["runtime_activation"] is False
    assert packet["execution_authority"] == 0
    payload_json = packet["payload_json"]
    assert payload_json["contract_id"] == spine.SCHEMA_VERSION
    assert payload_json["metadata_only"] is True
    assert payload_json["raw_prompt_stored"] is False
    assert payload_json["raw_chat_or_design_archive_body_stored"] is False
    assert packet["full_markdown_body_stored"] is False
    packet_text = json.dumps(packet, sort_keys=True)
    assert "raw_markdown" not in packet_text


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = spine.export_operator_nested_lane_mission_package_spine(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == spine.SCHEMA_VERSION
    assert result.nested_lane_count >= 14
    assert result.sqlite_receipt_supported is True
    assert result.runtime_authority_added is False
    assert "operator_nested_lane_mission_package_spine.json" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )
    assert "operator_nested_lane_mission_package_spine_OPERATOR.md" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == spine.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Operator Awareness Nested Lane + Mission Package Spine v0" in output
    assert "Check-engine becomes a Chief diagnostic/package problem" in output
    assert "Raw prompt/chat/design archive bodies are not stored" in output


def test_no_model_tool_agent_browser_oauth_credential_send_runtime_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in spine.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["candidate_models_are_live_integrations"] is False
    assert payload["plugins_wired"] is False
    assert payload["live_chat_created"] is False
    assert payload["repo_b_filesystem_inspected"] is False
    assert payload["runtime_authority_added"] is False


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("operator_nested_lane_mission_package_spine.py"),
        Path("scripts/export_operator_nested_lane_mission_package_spine.py"),
    ]
    forbidden_import_roots = {
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
    }
    for path in source_files:
        source = path.read_text(encoding="utf-8")
        assert "/home/openclaw_external/openclaw-runtime" not in source
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
    tree = ast.parse(Path("operator_nested_lane_mission_package_spine.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
