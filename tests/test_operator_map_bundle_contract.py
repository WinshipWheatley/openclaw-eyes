import ast
import json
from pathlib import Path

import operator_map_bundle_contract as bundle
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_map_bundle import main as export_main


FIXED_NOW = "2026-05-21T19:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dossier_card(agent_id: str, display_name: str, card_type: str, agent_class: str) -> dict:
    portrait_status = "OPERATOR_PROVIDED_REFERENCE" if agent_id == "cassandra" else "NEEDS_APPROVED_ASSET"
    return {
        "agent_id": agent_id,
        "display_name": display_name,
        "card_type": card_type,
        "agent_class": agent_class,
        "visual_archetype": (
            "classy cyberpunk executive analyst; calm, sharp, protected finance/comms intelligence posture"
            if agent_id == "cassandra"
            else "premium executive dossier card"
        ),
        "portrait_asset_status": portrait_status,
        "portrait_asset_ref": {
            "approved_asset_needed_before_render": True,
            "image_embedded": False,
            "raw_image_body_stored": False,
            "repo_asset_path": None,
            "source_note": "metadata only",
        },
        "portrait_raw_image_stored": False,
        "tagline": f"{display_name} dossier",
        "plain_english_role": f"{display_name} readback role.",
        "domains": ["Operations"],
        "strengths": ["readback", "classification"],
        "known_capabilities": ["known deterministic role"],
        "partly_known_capabilities": ["future package handling"],
        "known_unknowns": ["proof needs review"],
        "not_discovered": [f"{display_name} proof packet"],
        "current_allowed_actions": ["preview", "readback"],
        "current_blocked_actions": ["live activation", "tool execution", "credentials"],
        "future_eligible_actions": ["future-gated review"],
        "authority_boundary": "read-only preview only",
        "permissions_summary": "No live authority.",
        "memory_scope_summary": "Metadata refs only.",
        "tool_adapter_summary": "No live tools.",
        "model_selection_summary": "blocked_no_model now.",
        "package_types_supported": ["readback_package"],
        "package_preview_available": agent_id in {"cassandra", "chief", "guardian"},
        "required_gates": ["operator_preview"],
        "required_receipts": ["future_receipt"],
        "operator_questions": [
            {
                "question_id": f"{agent_id}_001",
                "prompt": f"What should {display_name} compare against memory?",
                "classification": "memory_only_clarification",
                "operator_answer_becomes": "memory_candidate_not_machine_proof",
                "execution_authority_created": False,
            }
        ],
        "safe_next_detour": "Classify missing proof.",
        "lane_destiny": {
            "resolution_route": "POST_SECURITY_AUTONOMY_CANDIDATE"
            if card_type == "system_loop_component"
            else "SECURITY_AUDIT_REQUIRED",
            "target_world": "Finance" if agent_id == "cassandra" else None,
            "helm_after_resolution": "keep as proof/detail",
        },
        "quiet_condition": "Proof classified and future gates explicit.",
        "world_affinity": ["Finance"] if agent_id == "cassandra" else [],
        "relationship_to_other_agents": ["Operator final authority"],
        "mission_control_display_guidance": "Render as dossier, no live controls.",
        "live_activation_allowed": False,
        "raw_private_context_allowed": False,
    }


def _terrain_awareness_payload() -> dict:
    cards = [
        _dossier_card("cassandra", "Cassandra", "agent_persona", "finance_comms_cassandra"),
        _dossier_card("chief", "Chief", "agent_persona", "diagnostic_chief"),
        _dossier_card("guardian", "Guardian", "agent_persona", "protected_access_guardian"),
        _dossier_card("hermes", "Hermes", "agent_persona", "architecture_hermes"),
        _dossier_card("niles", "Niles", "agent_persona", "creative_niles"),
        _dossier_card("struna", "Struna", "project_lane", "music_project_struna"),
        _dossier_card("agentic_loop", "Agentic Loop", "system_loop_component", "system_loop_component"),
        _dossier_card(
            "cue_parser_brain_dump_parser",
            "Cue Parser / Brain Dump Parser",
            "system_loop_component",
            "system_loop_component",
        ),
        _dossier_card(
            "repo_b_planner_builder_orchestrator",
            "Repo B Planner / Builder / Orchestrator",
            "system_loop_component",
            "system_loop_component",
        ),
        _dossier_card("package_compiler", "Package Compiler", "registry_component", "package_compiler_component"),
        _dossier_card("model_router", "Model Router", "registry_component", "model_router_component"),
        _dossier_card("tool_plugin_registry", "Tool / Plugin Registry", "registry_component", "tool_registry_component"),
    ]
    return {
        "schema_version": "agent_terrain_awareness_readback_contract_v0",
        "read_model_id": "agent_terrain_awareness_readback_contract",
        "agent_dossier_cards": cards,
        "agent_council_dossier_summary": {
            "summary_id": "agent_council_dossier_summary",
            "cards_count": len(cards),
            "featured_agents": ["cassandra", "chief", "guardian", "hermes", "niles", "struna"],
            "system_component_cards": [
                "agentic_loop",
                "cue_parser_brain_dump_parser",
                "repo_b_planner_builder_orchestrator",
                "package_compiler",
                "model_router",
                "tool_plugin_registry",
            ],
            "allowed_interactions": ["Inspect Dossier", "Show Package Preview"],
            "forbidden_interactions": ["live chat launch", "agent activation", "tool execution"],
            "mission_control_may_render": ["one featured selected card", "roster rail or carousel"],
        },
    }


def _fixture_repo(root: Path) -> Path:
    read_models = root / "generated" / "read_models"
    threshold = {
        "schema_version": "operator_threshold_map_contract_v0",
        "read_model_id": "operator_threshold_map_contract",
        "threshold_state_vocab": ["READY_FOR_SECURITY_AUDIT", "NEEDS_PROOF"],
        "resolution_route_vocab": ["MOVE_TO_WORLD_ACTION", "QUIET_BACKEND_RESOLVED"],
        "lane_inventory": [
            {
                "lane_id": "capital_hilton",
                "display_name": "Capital Hilton Invoice Lane",
                "readiness_state": "NEEDS_PROOF",
                "safe_next_move": "Capture approved protected proof metadata.",
                "missing_proof": ["approved Coupa proof metadata"],
                "operator_memory_is_proof": False,
                "lane_destiny": {
                    "resolution_route": "MOVE_TO_WORLD_ACTION",
                    "target_world": "Finance",
                    "live_dispatch_allowed_now": False,
                },
            },
            {
                "lane_id": "system_awareness_discovery",
                "display_name": "System Awareness / Discovery",
                "readiness_state": "READY_FOR_SECURITY_AUDIT",
                "safe_next_move": "Review known, partly known, unknown, and undiscovered terrain.",
                "missing_proof": [],
                "operator_memory_is_proof": False,
                "lane_destiny": {
                    "resolution_route": "REQUEUE_FOR_SYSTEM_BUILD",
                    "target_world": None,
                    "live_dispatch_allowed_now": False,
                },
            },
        ],
        "cue_autonomy_placement": {"status": "post_threshold_post_security_candidate"},
        "second_steel_thread_system_awareness_discovery": {
            "operator_memory_rule": {
                "may": "identify missing terrain",
                "may_not": "become proof by itself",
            }
        },
        "check_transmission_source_truth_note": {
            "app_visible_interpretation": "current sync proof controls Check Transmission"
        },
    }
    fixtures = {
        "sync_health.json": {
            "schema_version": "sync_health_read_model_v0",
            "read_model_id": "sync_health",
            "canonical_expected": 218,
            "observed": 218,
            "missing_expected": 0,
            "hash_mismatch": 0,
            "sync_lifecycle_state": "trusted_current",
            "mirror_status": "ok",
            "display_status": "current",
            "operator_action_required": False,
        },
        "system_health_lights_taxonomy.json": {
            "schema_version": "system_health_lights_taxonomy_v0",
            "read_model_id": "system_health_lights_taxonomy",
            "current_light_states": {"check_transmission": "QUIET"},
            "check_transmission_summary": {"current_status": "QUIET"},
        },
        "operator_threshold_map_contract.json": threshold,
        "operator_mission_priority_helm_declutter.json": {
            "schema_version": "operator_mission_priority_helm_declutter_v0",
            "read_model_id": "operator_mission_priority_helm_declutter",
            "current_mission": {"mission_id": "mission_control_app_finish_sprint"},
            "helm_mode": "DEVELOPER_MODE_BUILD_MODE",
            "target_future_mode": "quiet_operational_helm",
            "current_priority_ranking": ["stable map bundle"],
        },
        "world_domain_registry.json": {
            "read_model_version": "world_domain_registry_v0",
            "world_count": 2,
            "worlds": [
                {"world_id": "finance", "display_name": "Finance", "runtime_authority": False},
                {"world_id": "music_art", "display_name": "Music / Art", "runtime_authority": False},
            ],
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
            "current_authority_state": {"default": "preview_only"},
            "boundary_validation_contract": {"authority_drift_allowed": False},
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "read_model_id": "operator_workbench_actor_host_registry",
        },
        "steel_thread_lane_template_registry.json": {
            "schema_version": "steel_thread_lane_template_registry_v0",
            "read_model_id": "steel_thread_lane_template_registry",
        },
        "agent_terrain_awareness_readback_contract.json": _terrain_awareness_payload(),
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)
    return read_models


def _build(root: Path) -> dict:
    _fixture_repo(root)
    return bundle.build_operator_map_bundle_contract(
        repo_root=root,
        generated_at=FIXED_NOW,
        pc_transfer_root=root / "mnt_e" / "openclaw",
    )


def test_map_bundle_contract_is_metadata_only_and_defines_stable_app_paths(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == bundle.CONTRACT_SCHEMA_VERSION
    assert payload["read_model_id"] == "operator_map_bundle_contract"
    assert payload["strategic_correction"]["mac_mission_control_consumes_stable_map_snapshot"] is True
    assert payload["stable_app_facing_file_set"] == list(bundle.STABLE_APP_FACING_FILES)
    assert payload["app_facing_paths_do_not_change_when_new_raw_read_model_added"] is True
    assert payload["map_manifest"]["stable_app_facing_paths"]["mac_local_snapshot"].endswith(
        "openclaw_map_snapshot.json"
    )
    assert payload["runtime_activation_allowed"] is False
    assert payload["agent_activation_allowed"] is False
    assert payload["pc_c_drive_artifact_write_allowed"] is False


def test_adding_raw_read_model_changes_raw_count_but_not_app_facing_paths(tmp_path):
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    _fixture_repo(repo_a)
    _fixture_repo(repo_b)
    _write_json(
        repo_b / "generated" / "read_models" / "new_future_lane.json",
        {"schema_version": "new_future_lane_v0", "read_model_id": "new_future_lane"},
    )

    snapshot_a = bundle.build_openclaw_map_snapshot(repo_root=repo_a, generated_at=FIXED_NOW)
    manifest_a = bundle.build_openclaw_map_manifest(
        snapshot=snapshot_a,
        repo_root=repo_a,
        generated_at=FIXED_NOW,
    )
    snapshot_b = bundle.build_openclaw_map_snapshot(repo_root=repo_b, generated_at=FIXED_NOW)
    manifest_b = bundle.build_openclaw_map_manifest(
        snapshot=snapshot_b,
        repo_root=repo_b,
        generated_at=FIXED_NOW,
    )

    assert snapshot_a["mission_control_front_door_contract"]["stable_app_facing_files"] == snapshot_b[
        "mission_control_front_door_contract"
    ]["stable_app_facing_files"]
    assert manifest_b["canonical_read_model_count"] == manifest_a["canonical_read_model_count"] + 1
    assert manifest_b["stable_app_facing_paths"] == manifest_a["stable_app_facing_paths"]


def test_map_snapshot_contains_threshold_capital_hilton_and_system_awareness(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)

    threshold = snapshot["threshold_map"]
    capital = threshold["capital_hilton_finance_destiny"]
    awareness = threshold["system_awareness_discovery_steel_thread"]

    assert threshold["present"] is True
    assert capital["resolution_route"] == "MOVE_TO_WORLD_ACTION"
    assert capital["target_world"] == "Finance"
    assert capital["live_dispatch_allowed_now"] is False
    assert awareness["lane_id"] == "system_awareness_discovery"
    assert awareness["readiness_state"] == "READY_FOR_SECURITY_AUDIT"
    assert threshold["cue_autonomy_placement"]["status"] == "post_threshold_post_security_candidate"


def test_map_snapshot_contains_agent_council_dossier_cards(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    council = snapshot["agent_council"]
    cards = council["agent_dossier_cards"]
    cards_by_id = {card["agent_id"]: card for card in cards}

    assert council["present"] is True
    assert council["agent_dossier_cards_count"] == 12
    assert len(cards) == 12
    assert council["featured_agents"] == ["cassandra", "chief", "guardian", "hermes", "niles", "struna"]
    assert council["system_loop_cards_present"] is True
    assert council["agent_persona_cards_present"] is True
    assert council["cassandra_card_present"] is True
    assert council["preview_only"] is True
    assert council["live_agent_activation_allowed"] is False
    assert council["live_chat_launch_allowed"] is False
    assert council["model_launch_allowed"] is False
    assert council["tool_execution_allowed"] is False
    assert council["image_body_embedded"] is False
    assert council["cassandra_image_body_embedded"] is False
    assert cards_by_id["cassandra"]["portrait_asset_status"] == "OPERATOR_PROVIDED_REFERENCE"
    assert cards_by_id["cassandra"]["portrait_asset_ref"]["raw_image_body_stored"] is False
    assert '"raw_image_body":' not in bundle.stable_json(council)


def test_agent_council_card_fields_are_app_facing_without_raw_contract_dependency(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    card = next(
        card for card in snapshot["agent_council"]["agent_dossier_cards"] if card["agent_id"] == "cassandra"
    )

    for field in bundle.AGENT_DOSSIER_CARD_FIELDS:
        assert field in card
    assert snapshot["agent_council"]["primary_app_contract"] is True
    assert snapshot["agent_council"]["individual_terrain_read_model_remains_proof_detail"] is True
    assert "agent_terrain_awareness_readback_contract.json" not in snapshot[
        "mission_control_front_door_contract"
    ]["stable_app_facing_files"]


def test_bundle_hash_changes_when_map_content_changes(tmp_path):
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    _fixture_repo(repo_a)
    _fixture_repo(repo_b)
    threshold_path = repo_b / "generated" / "read_models" / "operator_threshold_map_contract.json"
    threshold = json.loads(threshold_path.read_text(encoding="utf-8"))
    threshold["lane_inventory"][0]["missing_proof"].append("approved Excel proof metadata")
    _write_json(threshold_path, threshold)

    snapshot_a = bundle.build_openclaw_map_snapshot(repo_root=repo_a, generated_at=FIXED_NOW)
    manifest_a = bundle.build_openclaw_map_manifest(
        snapshot=snapshot_a,
        repo_root=repo_a,
        generated_at=FIXED_NOW,
    )
    snapshot_b = bundle.build_openclaw_map_snapshot(repo_root=repo_b, generated_at=FIXED_NOW)
    manifest_b = bundle.build_openclaw_map_manifest(
        snapshot=snapshot_b,
        repo_root=repo_b,
        generated_at=FIXED_NOW,
    )

    assert snapshot_a["snapshot_hash"] != snapshot_b["snapshot_hash"]
    assert manifest_a["bundle_hash"] != manifest_b["bundle_hash"]


def test_mac_receipt_validation_by_generation_and_hash(tmp_path):
    payload = _build(tmp_path)
    manifest = payload["map_manifest"]
    valid_receipt = {
        "schema_version": bundle.MAP_RECEIPT_SCHEMA_VERSION,
        "map_generation_id": manifest["map_generation_id"],
        "bundle_hash": manifest["bundle_hash"],
        "mac_imported_at": FIXED_NOW,
        "local_mirror_path": "/Users/hwinshipwheatley/openclaw_generated_read_models",
        "parse_passed": True,
        "missing_files": [],
        "hash_mismatch": [],
        "app_visible": True,
    }

    assert bundle.validate_map_receipt(
        valid_receipt,
        expected_generation_id=manifest["map_generation_id"],
        expected_bundle_hash=manifest["bundle_hash"],
    )["status"] == "map_current"
    assert bundle.validate_map_receipt(
        None,
        expected_generation_id=manifest["map_generation_id"],
        expected_bundle_hash=manifest["bundle_hash"],
    )["status"] == "map_missing_from_mac"
    wrong_hash = {**valid_receipt, "bundle_hash": "sha256:wrong"}
    assert bundle.validate_map_receipt(
        wrong_hash,
        expected_generation_id=manifest["map_generation_id"],
        expected_bundle_hash=manifest["bundle_hash"],
    )["status"] == "map_hash_mismatch"


def test_no_raw_private_bodies_credentials_or_live_authority(tmp_path):
    payload = _build(tmp_path)
    text = bundle.stable_json(payload)

    assert payload["raw_private_bodies_included"] is False
    assert payload["credentials_included"] is False
    assert payload["secrets_included"] is False
    assert payload["external_model_api_allowed"] is False
    assert payload["model_execution_allowed"] is False
    assert payload["planner_builder_queue_allowed"] is False
    assert "credential_value" not in text
    assert "access_token" not in text


def test_export_script_writes_contract_and_stable_map_files(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    exit_code = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            export_root.as_posix(),
            "--pc-transfer-root",
            (tmp_path / "mnt_e" / "openclaw").as_posix(),
            "--format",
            "summary",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["schema_version"] == bundle.CONTRACT_SCHEMA_VERSION
    assert (export_root / "operator_map_bundle_contract.json").is_file()
    assert (export_root / "operator_map_bundle_contract_OPERATOR.md").is_file()
    assert (export_root / "openclaw_map_manifest.json").is_file()
    assert (export_root / "openclaw_map_snapshot.json").is_file()
    assert (export_root / "openclaw_map_OPERATOR.md").is_file()
    expected = canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path)
    assert "operator_map_bundle_contract.json" in expected
    assert "openclaw_map_manifest.json" in expected
    assert "openclaw_map_snapshot.json" in expected
    operator_text = (export_root / "openclaw_map_OPERATOR.md").read_text(encoding="utf-8")
    assert "Raw generated read-models remain proof/detail" in operator_text
    assert "Agent Council / Dossier Summary" in operator_text
    assert "Cards available: `12`" in operator_text


def test_only_stable_openclaw_map_manifest_is_allowed_through_manifest_filter(tmp_path):
    read_models = _fixture_repo(tmp_path)
    _write_json(read_models / "openclaw_map_manifest.json", {"schema_version": "openclaw_map_manifest_v0"})
    _write_json(read_models / "mac_generated_read_models_manifest.json", {"unsafe": "mirror manifest"})
    _write_json(read_models / "read_models_manifest.json", {"unsafe": "generic manifest"})

    expected = set(canonical_generated_read_model_expected_files(source_root=read_models, repo_root=tmp_path))

    assert "openclaw_map_manifest.json" in expected
    assert "mac_generated_read_models_manifest.json" not in expected
    assert "read_models_manifest.json" not in expected


def test_module_does_not_import_runtime_or_network_execution_tools():
    tree = ast.parse(Path("operator_map_bundle_contract.py").read_text(encoding="utf-8"))
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert "subprocess" not in imported_modules
    assert "requests" not in imported_modules
    assert "httpx" not in imported_modules
    assert "webbrowser" not in imported_modules
