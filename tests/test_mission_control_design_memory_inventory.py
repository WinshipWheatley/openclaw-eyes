import ast
import json
import sqlite3
from pathlib import Path

import mission_control_design_memory_inventory as inventory
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_mission_control_design_memory_inventory import main as export_main


FIXED_NOW = "2026-05-21T01:15:00+00:00"


def _write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    _write_text(
        root / "Operator/01_NORTH_STAR_AND_TASTE.md",
        "OpenClaw is for operators. The operator keeps authority. Software should feel human, local-first, and durable.\n",
    )
    _write_text(
        root / "Operator/05_ORIENTATION_CONTRACT.md",
        "Mission Control should orient the operator and avoid dashboard sprawl.\n",
    )
    _write_text(
        root / "Operator/GENERATED_CURRENT_STATE.md",
        "World status and strategic gravity are not implemented yet. Registered worlds come from the registry.\n",
    )
    _write_text(
        root / "docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md",
        "Read-only Mission Control fixtures. Do not collapse proof, approval, execution, and result into one object.\n",
    )
    _write_text(
        root / "docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
        "The first screen should feel like a calm cockpit / personal command desk. It is not a chatbot or generic SaaS dashboard. Worlds are destinations, not clutter. Knowledge context is not a RAG search box.\n",
    )
    _write_text(
        root / "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
        "Taste: studio console, evidence drawer, chart table. Vibe tests include cockpit_not_chatbot and studio_console_not_saas. Anti-vibe tests include startup_dashboard and wall_of_status_chips.\n",
    )
    _write_text(
        root / "docs/planning/launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md",
        "Sound is off by default and tied only to visible state transitions. No hidden-worker audio.\n",
    )

    read_models = root / "generated/read_models"
    fixtures = {
        "operator_mission_priority_helm_declutter.json": {
            "schema_version": "operator_mission_priority_helm_declutter_v0",
            "helm_mode": {"mode": "DEVELOPER_MODE_BUILD_MODE"},
            "target_future_mode": "QUIET_OPERATIONAL_HELM",
        },
        "steel_thread_lane_template_registry.json": {
            "schema_version": "steel_thread_lane_template_registry_v0",
            "template_type_count": 8,
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "package_type_count": 10,
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "host_count": 8,
        },
        "system_health_lights_taxonomy.json": {
            "schema_version": "system_health_lights_taxonomy_v0",
            "current_light_states": {"check_engine": "ON", "check_transmission": "QUIET"},
        },
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "lane_count": 14,
        },
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "package_preview_only": True,
        },
        "world_domain_registry.json": {
            "schema_version": "world_domain_registry_v0",
            "worlds": [
                {"world_id": "music_art"},
                {"world_id": "finance"},
                {"world_id": "operations"},
                {"world_id": "security"},
                {"world_id": "build"},
                {"world_id": "research"},
                {"world_id": "communications"},
                {"world_id": "business_development"},
            ],
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return inventory.build_mission_control_design_memory_inventory(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _theme(payload: dict, theme_id: str) -> dict:
    return next(item for item in payload["themes"] if item["theme_id"] == theme_id)


def test_inventory_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert inventory.stable_json(first) == inventory.stable_json(second)
    assert first["schema_version"] == inventory.SCHEMA_VERSION
    assert first["read_model_id"] == "mission_control_design_memory_inventory"
    assert first["contract_status"] == "deterministic_metadata_only_design_memory_inventory"
    assert first["inventory_scope"]["approved_source_scope"] == "narrow Repo A source docs and existing generated read-models only"
    assert first["inventory_scope"]["broad_private_chat_ingested"] is False
    assert first["inventory_scope"]["operator_memory_treated_as_truth"] is False
    assert first["theme_count"] >= 18


def test_classification_vocab_and_theme_shape_cover_design_memory_states(tmp_path):
    payload = _build(tmp_path)

    assert payload["classification_vocab"] == list(inventory.CLASSIFICATIONS)
    assert payload["affects_vocab"] == list(inventory.AFFECTS_KEYS)
    for classification in [
        "known_and_tracked",
        "partly_known",
        "known_unknown",
        "not_yet_discovered",
        "needs_winship_memory_comparison",
        "candidate_future_sqlite_promotion",
        "blocked_or_not_authorized",
        "safe_next_source_to_inspect",
    ]:
        assert payload["classifications_summary"][classification]

    required = {
        "theme_id",
        "title",
        "classification",
        "summary",
        "source_refs",
        "confidence",
        "why_it_matters",
        "affects",
        "current_gap",
        "safe_next_move",
        "what_not_to_build_from_this_yet",
    }
    for theme in payload["themes"]:
        assert required <= set(theme)
        assert set(theme["affects"]) == set(inventory.AFFECTS_KEYS)
        assert theme["confidence"] in inventory.CONFIDENCE_STATES
        assert theme["source_refs"]
        assert theme["runtime_authority_added"] is False


def test_known_doctrine_is_source_backed(tmp_path):
    payload = _build(tmp_path)

    helm = _theme(payload, "mission_control_as_helm_not_chatbot_dashboard")
    worlds = _theme(payload, "worlds_are_domain_destinations")
    steel = _theme(payload, "steel_thread_everywhere")
    check = _theme(payload, "check_lights_are_distinct_from_lanes")
    controls = _theme(payload, "operator_controls_preview_before_authority")

    assert helm["classification"] == "known_and_tracked"
    assert "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md" in helm["source_refs"]
    assert worlds["classification"] == "known_and_tracked"
    assert "generated/read_models/world_domain_registry.json" in worlds["source_refs"]
    assert steel["classification"] == "known_and_tracked"
    assert check["classification"] == "known_and_tracked"
    assert controls["classification"] == "known_and_tracked"
    assert controls["affects"]["operator_controls"] is True


def test_missing_memory_is_represented_without_becoming_truth(tmp_path):
    payload = _build(tmp_path)

    doom = _theme(payload, "spaceship_doom_space_station_reference_needs_source")
    likes = _theme(payload, "software_likes_dislikes_inventory_missing")
    gardening = _theme(payload, "gardening_future_world_not_registered")

    assert doom["classification"] == "needs_winship_memory_comparison"
    assert doom["operator_memory_is_not_treated_as_fact"] is True
    assert payload["source_state_summary"]["doom_or_space_station_reference_found"] is False
    assert "No approved Repo A source found" in doom["current_gap"]
    assert likes["classification"] == "needs_winship_memory_comparison"
    assert payload["source_state_summary"]["software_likes_dislikes_reference_found"] is False
    assert gardening["classification"] == "known_unknown"
    assert payload["source_state_summary"]["gardening_registered"] is False
    assert payload["operator_memory_policy"]["operator_memory_is_not_canonical_truth_by_itself"] is True


def test_source_records_are_bounded_and_do_not_export_raw_bodies(tmp_path):
    payload = _build(tmp_path)

    source_docs = payload["source_refs"]["source_docs"]
    assert {source["key"] for source in source_docs} == {source.key for source in inventory.SOURCE_DOCS}
    for source in source_docs:
        assert source["present"] is True
        assert source["approved_repo_a_source"] is True
        assert source["raw_private_content_read"] is False
        assert source["raw_body_exported"] is False
        assert source["broad_private_chat_ingested"] is False
        assert source["sha256"].startswith("sha256:")

    read_models = payload["source_refs"]["source_read_models"]
    assert {source["key"] for source in read_models} == {source.key for source in inventory.SOURCE_READ_MODELS}
    assert payload["machine_proof"]["source_read_models_present"]["package_compiler_contract"] is True
    assert payload["machine_proof"]["source_read_models_present"]["operator_workbench_actor_host_registry"] is True


def test_recommended_ui_guidance_and_future_promotions_are_safe(tmp_path):
    payload = _build(tmp_path)

    guidance_ids = {item["guidance_id"] for item in payload["recommended_mac_ui_guidance"]}
    assert "front_door_operator_first" in guidance_ids
    assert "proof_drawers_not_card_wall" in guidance_ids
    assert "source_missing_is_not_false" in guidance_ids
    promotion_ids = {item["promotion_id"] for item in payload["candidate_future_sqlite_promotions"]}
    assert "mission_control_design_doctrine_fact_set" in promotion_ids
    assert "winship_taste_reference_index" in promotion_ids
    for item in payload["candidate_future_sqlite_promotions"]:
        assert "raw" in item["forbidden_payload"]
        assert item["status"] in {"future_gated", "needs_winship_memory_comparison"}


def test_operator_output_answers_required_questions(tmp_path):
    output = inventory.format_mission_control_design_memory_inventory(_build(tmp_path))

    for heading in [
        "Mission Control Design Memory Inventory v0",
        "Already Captured",
        "Partly Captured",
        "Missing / Memory Comparison",
        "Future SQLite Promotions",
        "Mac UI Finish Guidance",
        "What Should Not Be Built Yet",
        "Source Bounds",
        "Next Safe Lane",
    ]:
        assert heading in output
    assert "Broad private chat ingested: `false`." in output
    assert "Missing memories should become Winship memory comparison needs, not facts." in output


def test_missing_sources_are_classified_as_unavailable_without_runtime_failure(tmp_path):
    repo = tmp_path / "repo_a"
    payload = inventory.build_mission_control_design_memory_inventory(repo_root=repo, generated_at=FIXED_NOW)

    assert payload["source_state_summary"]["read_model_availability"]["world_domain_registry"] is False
    assert payload["machine_proof"]["source_docs_present"]["taste_and_atmosphere_spec"] is False
    assert payload["source_state_summary"]["doom_or_space_station_reference_found"] is False
    assert payload["theme_count"] >= 18
    assert payload["operator_memory_policy"]["do_not_mark_unfound_sources_false"] is True
    assert payload["raw_private_content_inspected"] is False


def test_sqlite_receipt_is_metadata_only_and_idempotent(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "design_memory_receipts.sqlite"

    receipt_id = inventory.record_mission_control_design_memory_inventory_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = inventory.record_mission_control_design_memory_inventory_receipt(
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
    assert payload_json["contract_id"] == inventory.SCHEMA_VERSION
    assert payload_json["metadata_only"] is True
    assert payload_json["source_bodies_stored"] is False
    assert payload_json["raw_private_chat_bodies_stored"] is False
    assert payload_json["raw_private_file_bodies_stored"] is False
    assert payload_json["credentials_stored"] is False
    assert payload_json["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = inventory.export_mission_control_design_memory_inventory(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == inventory.SCHEMA_VERSION
    assert result.theme_count >= 18
    assert result.sqlite_receipt_supported is True
    assert result.broad_private_chat_ingested is False
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))
    assert "mission_control_design_memory_inventory.json" in expected
    assert "mission_control_design_memory_inventory_OPERATOR.md" in expected

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == inventory.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Mission Control Design Memory Inventory v0" in output


def test_no_live_model_agent_tool_browser_private_ingestion_or_c_drive_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in inventory.NO_AUTHORITY_FLAGS.items():
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
        Path("mission_control_design_memory_inventory.py"),
        Path("scripts/export_mission_control_design_memory_inventory.py"),
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
    source = Path("mission_control_design_memory_inventory.py").read_text(encoding="utf-8")
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
