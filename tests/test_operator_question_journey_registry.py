import ast
import json
import sqlite3
from pathlib import Path

import operator_question_journey_registry as registry
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_question_journey_registry import main as export_main


FIXED_NOW = "2026-05-21T02:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "mission_control_design_memory_inventory.json": {
            "schema_version": "mission_control_design_memory_inventory_v0",
            "read_model_id": "mission_control_design_memory_inventory",
            "theme_count": 20,
        },
        "operator_mission_priority_helm_declutter.json": {
            "schema_version": "operator_mission_priority_helm_declutter_v0",
            "read_model_id": "operator_mission_priority_helm_declutter",
        },
        "steel_thread_lane_template_registry.json": {
            "schema_version": "steel_thread_lane_template_registry_v0",
            "read_model_id": "steel_thread_lane_template_registry",
            "template_type_count": 8,
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
            "contract_status": "deterministic_metadata_only_package_compiler_boundary_hardened",
            "package_type_count": 10,
        },
        "system_health_lights_taxonomy.json": {
            "schema_version": "system_health_lights_taxonomy_v0",
            "read_model_id": "system_health_lights_taxonomy",
            "current_light_states": {"check_engine": "WARNING", "check_transmission": "ON"},
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "read_model_id": "operator_workbench_actor_host_registry",
            "host_count": 8,
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)
    _write_text(root / "operator_question_response.py", "# static question response fixture\n")


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return registry.build_operator_question_journey_registry(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _journey(payload: dict, journey_id: str) -> dict:
    return next(item for item in payload["journeys"] if item["journey_id"] == journey_id)


def test_registry_is_deterministic_and_bounded(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert registry.stable_json(first) == registry.stable_json(second)
    assert first["schema_version"] == registry.SCHEMA_VERSION
    assert first["read_model_id"] == "operator_question_journey_registry"
    assert first["contract_status"] == "deterministic_metadata_only_operator_question_journey_registry"
    assert first["purpose"].startswith("Capture bounded operator questions")
    assert first["journey_count"] >= 11
    assert first["broad_private_chat_ingested"] is False
    assert first["raw_private_content_inspected"] is False
    assert first["runtime_authority_added"] is False


def test_vocabularies_and_required_classifications_are_present(tmp_path):
    payload = _build(tmp_path)

    assert payload["source_type_vocab"] == list(registry.SOURCE_TYPES)
    assert payload["journey_classification_vocab"] == list(registry.JOURNEY_CLASSIFICATIONS)
    assert payload["status_vocab"] == list(registry.JOURNEY_STATUSES)
    assert payload["affected_system_area_vocab"] == list(registry.AFFECTED_SYSTEM_AREAS)
    classifications = payload["journey_ids_by_classification"]
    for classification in [
        "question",
        "objection",
        "correction",
        "doctrine_candidate",
        "promoted_doctrine",
        "known_unknown",
        "taste_signal",
    ]:
        assert classifications[classification]


def test_journey_records_have_required_shape(tmp_path):
    payload = _build(tmp_path)
    required = {
        "journey_id",
        "source_type",
        "journey_classification",
        "question_or_objection",
        "response_or_prior_framing",
        "correction_or_refinement",
        "resulting_doctrine_candidate",
        "confidence",
        "status",
        "affected_system_area",
        "why_it_matters",
        "safe_next_move",
        "promotion_rule",
        "proof_required_before_promotion",
        "what_not_to_claim_yet",
    }

    for journey in payload["journeys"]:
        assert required <= set(journey)
        assert journey["source_type"] in registry.SOURCE_TYPES
        assert journey["journey_classification"] in registry.JOURNEY_CLASSIFICATIONS
        assert journey["status"] in registry.JOURNEY_STATUSES
        assert journey["confidence"] in registry.CONFIDENCE_STATES
        assert journey["affected_system_area"]
        assert set(journey["affected_system_area"]) <= set(registry.AFFECTED_SYSTEM_AREAS)
        assert journey["operator_context_is_bounded_summary"] is True
        assert journey["raw_private_chat_body_stored"] is False
        assert journey["live_authority_added"] is False


def test_examples_from_operator_context_are_captured(tmp_path):
    payload = _build(tmp_path)
    expected = {
        "check_engine_light_visibility",
        "helm_clutter_objection",
        "nested_lanes_backend_not_ui_tree",
        "actor_model_agent_character_split",
        "deterministic_package_generation",
        "tell_system_whats_missing_button",
        "check_transmission_not_check_engine",
        "doom_space_station_visual_metaphor",
        "operator_system_above_operating_systems",
        "avoid_developer_tool_power_user_requirement",
    }

    assert expected <= {journey["journey_id"] for journey in payload["journeys"]}
    assert _journey(payload, "check_engine_light_visibility")["question_or_objection"] == "I don't see a check engine light."
    assert _journey(payload, "helm_clutter_objection")["journey_classification"] == "objection"
    assert _journey(payload, "actor_model_agent_character_split")["affected_system_area"] == [
        "package_compiler",
        "actor_router",
        "operator_workbenches",
    ]
    assert _journey(payload, "check_transmission_not_check_engine")["affected_system_area"] == [
        "health_lights",
        "bridge_sync",
        "helm_front_door",
    ]


def test_promoted_doctrine_links_to_existing_read_models(tmp_path):
    payload = _build(tmp_path)
    promoted = {item["journey_id"]: item["read_model_refs"] for item in payload["promoted_doctrine_links"]}

    assert "check_engine_light_visibility" in promoted
    assert "generated/read_models/system_health_lights_taxonomy.json" in promoted["check_engine_light_visibility"]
    assert "helm_clutter_objection" in promoted
    assert "generated/read_models/operator_mission_priority_helm_declutter.json" in promoted["helm_clutter_objection"]
    assert "operator_system_above_operating_systems" in promoted
    assert "generated/read_models/operator_workbench_actor_host_registry.json" in promoted["operator_system_above_operating_systems"]


def test_candidates_and_known_unknowns_are_not_overclaimed(tmp_path):
    payload = _build(tmp_path)

    assert "tell_system_whats_missing_button" in payload["doctrine_candidates"]
    assert "doom_space_station_visual_metaphor" in payload["doctrine_candidates"]
    assert "prior_question_answer_source_artifacts_missing" in payload["known_unknowns_and_memory_comparison_needs"]
    doom = _journey(payload, "doom_space_station_visual_metaphor")
    assert doom["status"] == "needs_source_artifact"
    assert "Do not claim this is source-backed" in doom["what_not_to_claim_yet"]
    source_missing = _journey(payload, "prior_question_answer_source_artifacts_missing")
    assert source_missing["source_type"] == "memory_comparison_needed"
    assert source_missing["journey_classification"] == "known_unknown"


def test_design_memory_and_mac_ui_next_links_are_explicit(tmp_path):
    payload = _build(tmp_path)

    assert "helm_clutter_objection" in payload["design_memory_links"]
    assert "doom_space_station_visual_metaphor" in payload["design_memory_links"]
    assert "check_engine_light_visibility" in payload["mac_ui_next_influences"]
    assert "tell_system_whats_missing_button" in payload["mac_ui_next_influences"]
    assert payload["promotion_policy"]["operator_question_is_not_automatically_truth"] is True
    assert payload["promotion_policy"]["memory_comparison_without_source_status"] == "needs_source_artifact"


def test_source_state_summary_and_machine_proof_are_bounded(tmp_path):
    payload = _build(tmp_path)

    assert payload["source_state_summary"]["package_compiler_boundary_hardened"] is True
    assert payload["source_state_summary"]["design_memory_theme_count"] == 20
    assert payload["source_state_summary"]["workbench_host_count"] == 8
    assert payload["machine_proof"]["source_read_models_present"]["mission_control_design_memory_inventory"] is True
    assert payload["machine_proof"]["source_read_models_present"]["operator_question_response"] is False
    for source in payload["machine_proof"]["source_read_models"]:
        assert source["raw_body_exported"] is False
        assert source["raw_private_content_read"] is False
        assert source["broad_private_chat_ingested"] is False
        assert source["executed_or_dispatched"] is False


def test_operator_output_answers_required_questions(tmp_path):
    output = registry.format_operator_question_journey_registry(_build(tmp_path))

    for heading in [
        "Operator Question Journey Registry v0",
        "Why Questions Matter",
        "Captured Journeys",
        "Doctrine Candidates",
        "Promoted Doctrine Links",
        "Known Unknowns / Memory Comparison",
        "Linked To Design Memory",
        "Mac UI Next Influences",
        "What Not To Overclaim",
        "Authority Boundary",
        "Next Safe Lane",
    ]:
        assert heading in output
    assert "no broad private chat ingestion" in output
    assert "check_transmission_not_check_engine" in output


def test_missing_sources_remain_unavailable_without_failure(tmp_path):
    repo = tmp_path / "repo_a"
    payload = registry.build_operator_question_journey_registry(repo_root=repo, generated_at=FIXED_NOW)

    assert payload["source_state_summary"]["available_sources"]["mission_control_design_memory_inventory"] is False
    assert payload["machine_proof"]["source_read_models_present"]["package_compiler_contract"] is False
    assert payload["journey_count"] >= 11
    assert payload["broad_private_chat_ingested"] is False


def test_sqlite_receipt_is_metadata_only_and_idempotent(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "question_journey_receipts.sqlite"

    receipt_id = registry.record_operator_question_journey_registry_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = registry.record_operator_question_journey_registry_receipt(
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
    assert payload_json["raw_private_chat_bodies_stored"] is False
    assert payload_json["raw_private_file_bodies_stored"] is False
    assert payload_json["credentials_stored"] is False
    assert payload_json["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = registry.export_operator_question_journey_registry(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == registry.SCHEMA_VERSION
    assert result.journey_count >= 11
    assert result.sqlite_receipt_supported is True
    assert result.broad_private_chat_ingested is False
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))
    assert "operator_question_journey_registry.json" in expected
    assert "operator_question_journey_registry_OPERATOR.md" in expected

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == registry.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Operator Question Journey Registry v0" in output


def test_no_live_model_agent_tool_browser_private_ingestion_or_c_drive_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in registry.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["external_model_apis_called"] is False
    assert payload["agents_activated"] is False
    assert payload["browser_oauth_or_account_access_enabled"] is False
    assert payload["broad_private_chat_ingested"] is False
    assert payload["chatgpt_history_ingested"] is False
    assert payload["raw_private_content_inspected"] is False
    assert payload["c_drive_artifact_written"] is False
    assert payload["runtime_authority_added"] is False


def test_source_does_not_import_live_execution_account_or_broad_file_mechanisms():
    source_files = [
        Path("operator_question_journey_registry.py"),
        Path("scripts/export_operator_question_journey_registry.py"),
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
    source = Path("operator_question_journey_registry.py").read_text(encoding="utf-8")
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
