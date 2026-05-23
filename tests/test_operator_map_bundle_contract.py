import ast
import json
from pathlib import Path

import operator_map_bundle_contract as bundle
import chief_test_harness_cross_off_receipt_contract
import capital_hilton_protected_proof_intake
import capital_hilton_proof_metadata_packet
import operator_attention_promotion_contract
import package_preview_receipt_contract
import parked_autonomous_capital_pipeline_experiment
import post_security_governance_batch_manifest
import security_audit_readiness_packet
import security_delta_review_contract
import security_pass_contract
import tool_adapter_receipt_contract
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
        "capital_hilton_actionable_review_packet.json": {
            "schema_version": "capital_hilton_actionable_review_packet_v1",
            "read_model_id": "capital_hilton_actionable_review_packet",
            "invoice_facts": [
                {
                    "field_name": "invoice_attachment_output_path",
                    "value_text": "workbook metadata/reference mentioned; raw cells not read",
                    "evidence_status": "parsed_evidence_not_truth",
                }
            ],
        },
        "cassandra_governed_review_packet_request_proof.json": {
            "schema_version": "cassandra_governed_review_packet_request_proof_v1",
            "read_model_id": "cassandra_governed_review_packet_request_proof",
            "domain_fact_summary": {
                "completed_service_dates": ["2026-05-08", "2026-05-15"],
                "rate_or_amount_per_gig": "$400 per gig",
                "candidate_subtotal": "$800",
                "invoice_count_posture": "one invoice",
                "po_or_portal_gate_status": "must_confirm_po_and_credit_in_coupa_before_final_submission",
                "recipient_posture_review_only": True,
            },
        },
        "capital_hilton_coupa_execution_path.json": {
            "schema_version": "capital_hilton_coupa_execution_path_v0",
            "read_model_id": "capital_hilton_coupa_execution_path",
        },
        "capital_hilton_external_artifact_proof_capture.json": {
            "schema_version": "capital_hilton_external_artifact_proof_capture_v0",
            "read_model_id": "capital_hilton_external_artifact_proof_capture",
        },
        "agent_terrain_awareness_readback_contract.json": _terrain_awareness_payload(),
        "package_preview_receipt_contract.json": package_preview_receipt_contract.build_package_preview_receipt_contract(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
        "tool_adapter_receipt_contract.json": tool_adapter_receipt_contract.build_tool_adapter_receipt_contract(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)
    for relative_path in (
        "markdown_knowledge_atlas.py",
        "scripts/build_markdown_knowledge_atlas.py",
        "markdown_evidence_ingestion.py",
        "scripts/ingest_approved_markdown_evidence.py",
        "corpus_atlas.py",
    ):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture-only metadata capability marker\n", encoding="utf-8")
    _write_json(
        read_models / "capital_hilton_proof_metadata_packet.json",
        capital_hilton_proof_metadata_packet.build_capital_hilton_proof_metadata_packet(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
    _write_json(
        read_models / "security_audit_readiness_packet.json",
        security_audit_readiness_packet.build_security_audit_readiness_packet(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
    _write_json(
        read_models / "security_pass_contract.json",
        security_pass_contract.build_security_pass_contract(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
    _write_json(
        read_models / "post_security_governance_batch_manifest.json",
        post_security_governance_batch_manifest.build_post_security_governance_batch_manifest(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
    _write_json(
        read_models / "parked_autonomous_capital_pipeline_experiment.json",
        parked_autonomous_capital_pipeline_experiment.build_parked_autonomous_capital_pipeline_experiment(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
    _write_json(
        read_models / "security_delta_review_contract.json",
        security_delta_review_contract.build_security_delta_review_contract(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
    _write_json(
        read_models / "operator_attention_promotion_contract.json",
        operator_attention_promotion_contract.build_operator_attention_promotion_contract(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
    _write_json(
        read_models / "chief_test_harness_cross_off_receipt_contract.json",
        chief_test_harness_cross_off_receipt_contract.build_chief_test_harness_cross_off_receipt_contract(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
    _write_json(
        read_models / "capital_hilton_protected_proof_intake.json",
        capital_hilton_protected_proof_intake.build_capital_hilton_protected_proof_intake(
            repo_root=root,
            generated_at=FIXED_NOW,
        ),
    )
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


def test_map_snapshot_contains_package_preview_receipt_surface(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    surface = snapshot["package_preview_receipts"]
    cards = {card["package_id"]: card for card in surface["package_preview_cards"]}

    assert surface["present"] is True
    assert surface["primary_app_contract"] is True
    assert surface["individual_contract_read_model_remains_proof_detail"] is True
    assert surface["contract_id"] == "package_preview_receipt_contract"
    assert surface["contract_version"] == package_preview_receipt_contract.SCHEMA_VERSION
    assert surface["receipt_types_count"] == len(package_preview_receipt_contract.RECEIPT_TYPES)
    assert surface["preview_states_count"] == len(package_preview_receipt_contract.PREVIEW_STATES)
    assert surface["example_package_previews_count"] == 8
    assert "package_cassandra_capital_hilton_invoice_review" in cards
    assert "package_chief_check_engine_diagnostic" in cards
    assert "package_agentic_loop_classification" in cards
    capital = cards["package_cassandra_capital_hilton_invoice_review"]
    assert capital["package_title"] == "Cassandra Capital Hilton Invoice Review"
    assert capital["world_affinity"] == ["Finance"]
    assert capital["lane_destiny"]["target_world"] == "Finance"
    assert "Coupa protected proof metadata" in capital["missing_proof"]
    assert "coupa_adapter" in capital["blocked_actions"]
    assert surface["dispatch_authority_allowed"] is False
    assert surface["model_call_allowed"] is False
    assert surface["tool_execution_allowed"] is False
    assert surface["agent_activation_allowed"] is False
    assert surface["queue_execution_allowed"] is False
    assert surface["account_access_allowed"] is False
    assert surface["send_submit_approval_allowed"] is False
    assert surface["raw_body_included"] is False
    for card in cards.values():
        assert card["runtime_dispatch_allowed"] is False
        assert card["model_call_allowed"] is False
        assert card["tool_execution_allowed"] is False
        assert card["agent_activation_allowed"] is False
        assert card["send_submit_approval_allowed"] is False


def test_map_snapshot_contains_tool_adapter_receipt_surface(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    surface = snapshot["tool_adapter_receipts"]
    cards = {card["adapter_id"]: card for card in surface["adapter_receipt_cards"]}

    assert surface["present"] is True
    assert surface["primary_app_contract"] is True
    assert surface["individual_contract_read_model_remains_proof_detail"] is True
    assert surface["contract_id"] == "tool_adapter_receipt_contract"
    assert surface["contract_version"] == tool_adapter_receipt_contract.SCHEMA_VERSION
    assert surface["receipt_types_count"] == len(tool_adapter_receipt_contract.RECEIPT_TYPES)
    assert surface["receipt_states_count"] == len(tool_adapter_receipt_contract.RECEIPT_STATES)
    assert surface["capability_classes_count"] == len(tool_adapter_receipt_contract.CAPABILITY_CLASSES)
    assert surface["adapter_examples_count"] == 12
    assert surface["allowed_read_only_count"] == 1
    assert surface["preview_or_receipt_only_count"] == 3
    assert surface["blocked_or_future_gated_count"] == 8
    assert "stable_map_bundle_reader" in cards
    assert "cassandra_capital_hilton_invoice_proof_adapter" in cards
    assert "browser_oauth_adapter" in cards
    assert "gmail_calendar_adapter" in cards
    assert "coupa_adapter" in cards
    assert "telegram_adapter" in cards
    assert cards["stable_map_bundle_reader"]["capability_class_granted"] == "READ_METADATA"
    assert cards["cassandra_capital_hilton_invoice_proof_adapter"]["capability_class_blocked"] == "READ_REDACTED_CONTENT"
    assert "ACCOUNT_ACCESS_BLOCKED" in cards["coupa_adapter"]["blocked_reasons"]
    assert surface["live_tool_execution_allowed"] is False
    assert surface["network_allowed"] is False
    assert surface["account_access_allowed"] is False
    assert surface["browser_session_allowed"] is False
    assert surface["send_submit_approval_allowed"] is False
    assert surface["command_execution_allowed"] is False
    for card in cards.values():
        assert card["tool_execution_performed"] is False
        assert card["network_allowed"] is False
        assert card["account_access_allowed"] is False
        assert card["browser_session_allowed"] is False
        assert card["send_submit_approval_allowed"] is False
        assert card["command_execution_allowed"] is False
        assert card["model_call_performed"] is False
        assert card["agent_activation_performed"] is False
        assert card["queue_execution_performed"] is False


def test_map_snapshot_contains_capital_hilton_proof_metadata_summary(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    summary = snapshot["capital_hilton_proof_metadata"]
    facts = {fact["fact_id"]: fact for fact in summary["candidate_facts"]}
    proof = {item["proof_id"]: item for item in summary["proof_metadata_checklist"]}

    assert summary["present"] is True
    assert summary["primary_app_contract"] is True
    assert summary["individual_contract_read_model_remains_proof_detail"] is True
    assert summary["contract_id"] == "capital_hilton_proof_metadata_packet"
    assert summary["contract_version"] == capital_hilton_proof_metadata_packet.SCHEMA_VERSION
    assert summary["lane_id"] == "capital_hilton"
    assert summary["current_phase"] == "HELM_THRESHOLD_LANE"
    assert summary["target_world"] == "Finance"
    assert summary["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert summary["workflow_type"] == "invoice_review_and_proof_metadata"
    assert summary["missing_proof_count"] == 10
    assert summary["protected_proof_required"] is True
    assert summary["all_candidate_facts_marked_not_proven"] is True
    assert summary["operator_answers_become_memory_candidate_receipts_not_proof"] is True
    assert summary["finance_world_preview"]["preview_only"] is True
    assert summary["finance_world_preview"]["not_executable"] is True
    assert summary["finance_world_preview"]["no_coupa"] is True
    assert summary["finance_world_preview"]["no_invoice_generation"] is True
    assert facts["completed_performance_dates"]["current_value"] == ["2026-05-08", "2026-05-15"]
    assert facts["rate"]["current_value"] == "$400 per gig"
    assert facts["subtotal"]["current_value"] == "$800"
    assert facts["invoice_shape_one_invoice_posture"]["current_value"] == "one invoice"
    for fact in facts.values():
        assert fact["machine_proven"] is False
        assert fact["candidate_not_machine_proven"] is True
        assert fact["proof_missing"] is True
        assert fact["raw_body_included"] is False
    assert set(proof) == {
        "performance_date_proof_metadata",
        "rate_proof_metadata",
        "subtotal_proof_metadata",
        "coupa_po_or_payment_reference_metadata",
        "excel_workbook_reference_metadata",
        "invoice_source_card_metadata",
        "ap_recipient_route_metadata",
        "guardian_protected_access_gate_metadata",
        "operator_confirmation_metadata",
        "future_invoice_generation_receipt_requirement",
    }
    for item in proof.values():
        assert item["missing"] is True
        assert item["raw_body_blocked"] is True
    assert len(summary["operator_memory_questions"]) == 7
    assert {item["classification"] for item in summary["operator_memory_questions"]} <= {
        "memory_only_clarification",
        "proof_needed",
        "protected_proof_needed",
        "security_gate_needed",
        "world_transition_needed",
    }


def test_capital_hilton_authority_flags_are_false_in_stable_map(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    authority = snapshot["capital_hilton_proof_metadata"]["authority_boundary"]

    assert set(authority) == set(bundle.CAPITAL_HILTON_AUTHORITY_FLAG_FIELDS)
    assert all(value is False for value in authority.values())
    assert snapshot["capital_hilton_proof_metadata"]["raw_finance_body_included"] is False
    assert snapshot["capital_hilton_proof_metadata"]["credential_or_secret_included"] is False
    assert snapshot["capital_hilton_proof_metadata"]["live_execution_authority"] is False


def test_map_snapshot_contains_security_audit_readiness_summary(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    summary = snapshot["security_audit_readiness"]

    assert summary["present"] is True
    assert summary["primary_app_contract"] is True
    assert summary["individual_packet_read_model_remains_proof_detail"] is True
    assert summary["packet_id"] == "security_audit_readiness_packet"
    assert summary["schema_version"] == security_audit_readiness_packet.SCHEMA_VERSION
    assert summary["ready_for_security_pass"] is True
    assert summary["security_approval_granted"] is False
    assert summary["action_authority_granted"] is False
    assert summary["map_to_terrain_provenance_present"] is True
    assert summary["package_map_slice_rule_present"] is True
    assert summary["operator_answer_capture_present"] is True
    assert summary["question_quieting_model_present"] is True
    assert summary["shared_execution_paths_present"] is True
    assert summary["helm_issue_focus_mode_present"] is True
    assert summary["coverage_gap_registry_present"] is True
    assert summary["parked_breadcrumb_review_present"] is True
    assert summary["capital_hilton_security_readiness_present"] is True
    assert summary["all_authority_flags_false"] is True
    assert summary["zero_execution_authority_leaked"] is True
    assert summary["raw_private_bodies_excluded"] is True
    assert summary["credentials_and_account_access_blocked"] is True
    assert summary["hidden_automation_absent"] is True
    assert summary["source_read_model_ref"] == bundle.SECURITY_AUDIT_READINESS_READ_MODEL_PATH
    assert summary["source_operator_ref"] == "generated/read_models/security_audit_readiness_packet_OPERATOR.md"


def test_security_audit_readiness_nested_summaries_are_app_facing(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    summary = snapshot["security_audit_readiness"]
    provenance = summary["map_to_terrain_provenance_summary"]
    answer = summary["operator_answer_capture_summary"]
    shared = summary["shared_execution_path_summary"]
    focus = summary["helm_issue_focus_mode_summary"]
    coverage = summary["coverage_gap_summary"]
    parked = summary["parked_breadcrumb_summary"]
    capital = summary["capital_hilton_security_readiness_summary"]

    assert provenance["stable_map_is_source_truth"] is False
    assert provenance["stable_map_is_app_facing_reflection"] is True
    assert provenance["claims_require_source_or_candidate_status"] is True
    assert provenance["packages_use_map_slices_with_proof_refs"] is True
    assert provenance["candidate_claims_not_proof"] is True
    assert provenance["missing_proof_blocks_action"] is True

    assert answer["answer_capture_schema_present"] is True
    assert answer["operator_answers_are_memory_candidates"] is True
    assert answer["operator_answers_are_not_proof"] is True
    assert answer["question_quieting_states_count"] == len(security_audit_readiness_packet.QUESTION_STATES)
    assert "text" in answer["supported_answer_modalities"]
    assert answer["capture_is_preview_only"] is True
    assert answer["answer_popup_implemented"] is False

    assert shared["shared_execution_paths_count"] == 3
    assert shared["protected_finance_proof_metadata_intake_present"] is True
    assert shared["operator_memory_question_capture_present"] is True
    assert shared["stable_map_receipt_readback_present"] is True
    assert shared["shared_paths_are_non_executing"] is True
    assert shared["solving_once_can_update_multiple_lanes"] is True

    assert focus["focus_mode_defined"] is True
    assert focus["issue_focus_cards_count"] == 3
    assert focus["unrelated_cards_collapse_when_selected"] is True
    assert focus["proof_stays_behind_disclosure"] is True
    assert focus["no_live_controls"] is True
    assert focus["capital_hilton_focus_available"] is True
    assert focus["protected_finance_shared_focus_available"] is True

    assert coverage["coverage_gap_registry_present"] is True
    assert coverage["coverage_gap_records_count"] == 5
    assert coverage["markdown_document_terrain_present"] is True
    assert coverage["tagging_system_capability_present"] is True
    assert coverage["mission_control_visibility_gap_present"] is True
    assert coverage["operator_memory_gap_present"] is True
    assert coverage["repo_terrain_gap_present"] is True
    assert coverage["broad_markdown_scan_allowed"] is False
    assert coverage["file_moves_allowed"] is False
    assert coverage["repo_b_body_inspection_allowed"] is False

    assert parked["parked_breadcrumb_review_present"] is True
    assert parked["parked_breadcrumb_count"] == 15
    assert parked["auto_promotion_allowed"] is False
    assert parked["queue_creation_allowed"] is False
    assert parked["trigger_engine_allowed"] is False
    assert "Operator Attention Promotion Contract v0" in parked["known_highlighted_breadcrumbs"]
    assert "Operator Sleep Mode / Queue Priority Posture" in parked["known_highlighted_breadcrumbs"]
    assert "Compromise / Suspicion / Kill-Switch Posture" in parked["known_highlighted_breadcrumbs"]

    assert capital["current_phase"] == "HELM_THRESHOLD_LANE"
    assert capital["target_world"] == "Finance"
    assert capital["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert capital["missing_proof_count"] == 10
    assert capital["protected_proof_required"] is True
    assert capital["candidate_facts_proven"] is False
    assert capital["security_pass_complete"] is False
    assert capital["action_authority_granted"] is False
    assert capital["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
    assert capital["finance_world_preview_exists"] is True


def test_map_snapshot_contains_security_pass_summary(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    summary = snapshot["security_pass"]

    assert summary["present"] is True
    assert summary["primary_app_contract"] is True
    assert summary["individual_contract_read_model_remains_proof_detail"] is True
    assert summary["contract_id"] == "security_pass_contract"
    assert summary["schema_version"] == security_pass_contract.SCHEMA_VERSION
    assert summary["security_pass_completed"] is True
    assert summary["read_only_surfaces_approved"] is True
    assert summary["preview_surfaces_approved"] is True
    assert summary["metadata_only_surfaces_approved"] is True
    assert summary["worker_output_intake_metadata_approved"] is True
    assert summary["orphaned_capability_detection_approved"] is True
    assert summary["chief_reconciliation_metadata_approved"] is True
    assert summary["hermes_architecture_review_metadata_approved"] is True
    assert summary["trust_clearance_modeling_approved"] is True
    assert summary["action_authority_granted"] is False
    assert summary["runtime_execution_authority_granted"] is False
    assert summary["tool_execution_authority_granted"] is False
    assert summary["model_execution_authority_granted"] is False
    assert summary["queue_execution_authority_granted"] is False
    assert summary["account_authority_granted"] is False
    assert summary["send_submit_approval_authority_granted"] is False
    assert summary["chief_self_authorization_allowed"] is False
    assert summary["hermes_self_authorization_allowed"] is False
    assert summary["automatic_activation_allowed"] is False
    assert summary["automatic_cross_off_allowed"] is False
    assert summary["source_read_model_ref"] == bundle.SECURITY_PASS_CONTRACT_READ_MODEL_PATH
    assert summary["source_operator_ref"] == "generated/read_models/security_pass_contract_OPERATOR.md"
    assert summary["all_live_authority_false"] is True


def test_security_pass_nested_summaries_are_app_facing(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)
    summary = snapshot["security_pass"]
    surfaces = {item["surface_id"]: item for item in summary["surface_decision_summary"]}
    capital = summary["capital_hilton_security_pass_decision_summary"]
    markdown = summary["markdown_terrain_security_decision_summary"]
    worker = summary["worker_output_orphaned_capability_summary"]
    trust = summary["chief_hermes_trust_summary"]

    assert set(surfaces) == {
        "stable_map_bundle",
        "mission_control",
        "agent_council",
        "package_preview_tool_receipt",
        "finance_world_capital_hilton",
        "security_readiness_eliwinship",
        "evidence_drawer",
    }
    assert surfaces["stable_map_bundle"]["authority_summary"]["approval_status"] == "APPROVED_STABLE_MAP_SURFACE"
    for surface in surfaces.values():
        assert surface["authority_summary"]["action_authority_granted"] is False
        assert surface["authority_summary"]["runtime_execution_authority_granted"] is False
        assert surface["authority_summary"]["tool_execution_authority_granted"] is False
        assert surface["authority_summary"]["model_execution_authority_granted"] is False
        assert surface["authority_summary"]["account_authority_granted"] is False
        assert surface["authority_summary"]["send_submit_approval_authority_granted"] is False

    assert capital["current_phase"] == "HELM_THRESHOLD_LANE"
    assert capital["target_world"] == "Finance"
    assert capital["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert capital["missing_proof_count"] == 10
    assert capital["protected_proof_required"] is True
    assert capital["candidate_facts_proven"] is False
    assert capital["finance_world_preview_approved"] is True
    assert capital["proof_metadata_display_approved"] is True
    assert capital["operator_questions_display_approved"] is True
    assert capital["invoice_generation_allowed"] is False
    assert capital["coupa_access_allowed"] is False
    assert capital["browser_oauth_account_access_allowed"] is False
    assert capital["credential_handling_allowed"] is False
    assert capital["gmail_calendar_email_access_allowed"] is False
    assert capital["raw_excel_body_ingestion_allowed"] is False
    assert capital["raw_finance_body_ingestion_allowed"] is False
    assert capital["send_submit_approval_allowed"] is False
    assert capital["guardian_gate_required"] is True
    assert capital["operator_final_authority_required"] is True

    assert markdown["markdown_backend_ready"] is True
    assert markdown["markdown_knowledge_atlas_present"] is True
    assert markdown["approved_markdown_evidence_ingestion_present"] is True
    assert markdown["corpus_atlas_present"] is True
    assert markdown["metadata_readback_approved"] is True
    assert markdown["bounded_allowlisted_excerpt_metadata_approved"] is True
    assert markdown["broad_markdown_body_ingestion_allowed"] is False
    assert markdown["broad_doc_reorganization_allowed"] is False
    assert markdown["file_moves_deletes_renames_allowed"] is False
    assert markdown["vector_index_creation_allowed"] is False
    assert markdown["stale_doctrine_promotion_without_proof_allowed"] is False
    assert markdown["app_visibility_future_gap"] is True

    assert worker["worker_output_intake_metadata_approved"] is True
    assert worker["orphaned_capability_detection_approved"] is True
    assert worker["detected_capabilities_auto_activate"] is False
    assert worker["promotion_decisions_are_recommendations_only"] is True
    assert worker["markdown_knowledge_atlas_candidate_present"] is True
    assert worker["approved_markdown_evidence_ingestion_candidate_present"] is True
    assert worker["corpus_atlas_candidate_present"] is True
    assert worker["future_invoicing_audit_captured"] is True
    assert worker["future_invoicing_audit_status"] in {"PARKED", "BLOCKED"}
    assert worker["ledger_write_allowed"] is False
    assert worker["invoice_generation_allowed"] is False
    assert worker["email_dispatch_allowed"] is False

    assert trust["chief_reconciliation_metadata_approved"] is True
    assert trust["hermes_architecture_review_metadata_approved"] is True
    assert trust["trust_clearance_modeling_approved"] is True
    assert trust["full_trust_clearance_is_lm_confidence"] is False
    assert trust["full_trust_clearance_grants_authority_by_itself"] is False
    assert trust["below_full_trust_runs_unattended"] is False
    assert trust["chief_self_authorization_allowed"] is False
    assert trust["hermes_self_authorization_allowed"] is False
    assert trust["automatic_cross_off_allowed"] is False
    assert trust["cross_off_deletes_source_notes"] is False
    assert trust["trust_detours_present"] is True
    assert trust["operator_babysitting_reduction_goal_present"] is True


def test_map_snapshot_contains_post_security_governance_batch_summaries(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)

    batch = snapshot["post_security_governance_batch"]
    experiment = snapshot["parked_autonomous_capital_pipeline_experiment"]
    delta = snapshot["security_delta_review"]
    attention = snapshot["operator_attention_promotion"]
    chief = snapshot["chief_test_harness_cross_off"]

    assert batch["present"] is True
    assert batch["batch_id"] == "post_security_governance_batch_v0"
    assert batch["batch_status"] == "COMPLETE_PENDING_STABLE_MAP_IMPORT"
    assert batch["lane_count"] == 5
    assert set(batch["completed_lanes"]) >= {
        "parked_autonomous_capital_pipeline_experiment",
        "security_delta_review_contract",
        "operator_attention_promotion_contract",
        "chief_test_harness_cross_off_receipt_contract",
        "integrated_checkpoint_and_stable_map_refresh",
    }
    assert batch["next_expected_actor"] == "mac_map_import_agent"
    assert batch["authority_boundary"]["all_live_authority_false"] is True
    assert batch["action_authority_granted"] is False

    assert experiment["present"] is True
    assert experiment["status"] == "PARKED_HIGH_RISK_R_AND_D_EXPERIMENT"
    assert experiment["phase_count"] == 5
    assert experiment["all_authority_false"] is True
    assert experiment["future_gates_required"] is True
    assert experiment["token_concept_future_only"] is True
    assert experiment["stress_test_classification"] is True
    assert experiment["capital_spend_allowed"] is False
    assert experiment["account_creation_allowed"] is False
    assert experiment["financial_account_access_allowed"] is False
    assert experiment["network_operation_allowed"] is False
    assert experiment["model_call_allowed"] is False
    assert experiment["agent_activation_allowed"] is False
    assert experiment["tool_execution_allowed"] is False
    assert experiment["queue_execution_allowed"] is False

    assert delta["present"] is True
    assert delta["delta_classes_count"] == len(security_delta_review_contract.SECURITY_DELTA_CLASSES)
    assert delta["default_examples_count"] == 14
    assert "ACCOUNT_ACCESS_DELTA" in delta["repass_required_categories"]
    assert "FINANCIAL_AUTHORITY_DELTA" in delta["repass_required_categories"]
    assert "QUEUE_AUTONOMY_DELTA" in delta["repass_required_categories"]
    assert "RUNTIME_EXECUTION_DELTA" in delta["repass_required_categories"]
    assert delta["action_authority_granted"] is False
    assert delta["execution_authority_granted"] is False
    assert delta["auto_promotion_allowed"] is False
    assert delta["auto_queueing_allowed"] is False

    assert attention["present"] is True
    assert attention["promotion_lifecycle_present"] is True
    assert attention["quiet_helm_policy_present"] is True
    assert attention["shared_fix_path_handling_present"] is True
    assert attention["cue_candidates_executable"] is False
    assert attention["holding_cell_queued"] is False
    assert attention["operator_answers_are_memory_candidates_not_proof"] is True
    assert attention["new_authority_routes_to_security_delta_or_fail_closed"] is True
    assert attention["action_authority_granted"] is False
    assert attention["auto_promotion_allowed"] is False

    assert chief["present"] is True
    assert chief["test_harness_receipt_model_present"] is True
    assert chief["cross_off_rules_present"] is True
    assert chief["source_mutation_allowed"] is False
    assert chief["delete_source_allowed"] is False
    assert chief["automatic_cross_off_allowed"] is False
    assert chief["repair_requeue_recommendations_metadata_only"] is True
    assert chief["quiet_with_proof_model_present"] is True
    assert chief["action_authority_granted"] is False
    assert chief["chief_self_authorization_allowed"] is False
    assert chief["chief_repair_execution_allowed"] is False


def test_map_snapshot_contains_capital_hilton_protected_proof_intake_summary(tmp_path):
    _fixture_repo(tmp_path)
    snapshot = bundle.build_openclaw_map_snapshot(repo_root=tmp_path, generated_at=FIXED_NOW)

    proof_intake = snapshot["capital_hilton_protected_proof_intake"]

    assert proof_intake["present"] is True
    assert proof_intake["section_id"] == "capital_hilton_protected_proof_intake"
    assert proof_intake["target_world"] == "Finance"
    assert proof_intake["current_phase"] == "HELM_THRESHOLD_LANE"
    assert proof_intake["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert proof_intake["missing_proof_count"] == 10
    assert proof_intake["proof_items_count"] == 10
    assert proof_intake["protected_proof_required"] is True
    assert proof_intake["candidate_completed_dates"] == ["2026-05-08", "2026-05-15"]
    assert proof_intake["candidate_rate"] == "$400 per gig"
    assert proof_intake["candidate_subtotal"] == "$800"
    assert proof_intake["candidate_one_invoice_posture"] is True
    assert proof_intake["candidate_facts_proven"] is False
    assert proof_intake["action_authority_granted"] is False
    assert proof_intake["guardian_gates_count"] == 5
    assert proof_intake["operator_answer_candidates_count"] == 10
    assert proof_intake["protected_evidence_requirements_count"] == 6
    assert proof_intake["quieting_rules_count"] == 10
    assert proof_intake["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
    assert proof_intake["invoice_generation_allowed"] is False
    assert proof_intake["coupa_access_allowed"] is False
    assert proof_intake["browser_oauth_account_access_allowed"] is False
    assert proof_intake["gmail_calendar_email_access_allowed"] is False
    assert proof_intake["credential_handling_allowed"] is False
    assert proof_intake["send_submit_approval_allowed"] is False
    assert proof_intake["raw_finance_body_ingestion_allowed"] is False
    assert proof_intake["operator_answers_are_not_proof"] is True
    assert proof_intake["protected_references_metadata_only"] is True
    assert proof_intake["quieting_without_proof_allowed"] is False
    assert proof_intake["source_read_model_ref"] == "generated/read_models/capital_hilton_protected_proof_intake.json"
    assert proof_intake["source_operator_ref"] == "generated/read_models/capital_hilton_protected_proof_intake_OPERATOR.md"
    assert {item["proof_item_id"] for item in proof_intake["proof_item_summaries"]} == {
        "performance_date_2026_05_08_proof",
        "performance_date_2026_05_15_proof",
        "rate_400_per_gig_proof",
        "subtotal_800_proof",
        "one_invoice_posture_proof",
        "coupa_po_payment_reference_metadata",
        "excel_workbook_or_invoice_source_reference",
        "ap_recipient_route_metadata",
        "tax_vendor_handling_metadata",
        "future_invoice_generation_receipt_requirement",
    }


def test_post_security_governance_batch_integration_is_reflected_in_contract(tmp_path):
    payload = _build(tmp_path)

    assert payload["post_security_governance_batch_integration"]["summary_included_in_snapshot"] is True
    assert payload["post_security_governance_batch_integration"]["batch_status"] == "COMPLETE_PENDING_STABLE_MAP_IMPORT"
    assert payload["post_security_governance_batch_integration"]["all_live_authority_false"] is True
    assert payload["parked_autonomous_capital_pipeline_experiment_integration"]["summary_included_in_snapshot"] is True
    assert payload["parked_autonomous_capital_pipeline_experiment_integration"]["all_authority_false"] is True
    assert payload["security_delta_review_integration"]["summary_included_in_snapshot"] is True
    assert payload["security_delta_review_integration"]["action_authority_granted"] is False
    assert payload["operator_attention_promotion_integration"]["summary_included_in_snapshot"] is True
    assert payload["operator_attention_promotion_integration"]["cue_candidates_executable"] is False
    assert payload["operator_attention_promotion_integration"]["holding_cell_queued"] is False
    assert payload["chief_test_harness_cross_off_integration"]["summary_included_in_snapshot"] is True
    assert payload["chief_test_harness_cross_off_integration"]["source_mutation_allowed"] is False
    assert payload["chief_test_harness_cross_off_integration"]["delete_source_allowed"] is False
    assert payload["capital_hilton_protected_proof_intake_integration"]["summary_included_in_snapshot"] is True
    assert payload["capital_hilton_protected_proof_intake_integration"]["proof_items_count"] == 10
    assert payload["capital_hilton_protected_proof_intake_integration"]["missing_proof_count"] == 10
    assert payload["capital_hilton_protected_proof_intake_integration"]["protected_proof_required"] is True
    assert payload["capital_hilton_protected_proof_intake_integration"]["candidate_facts_proven"] is False
    assert payload["capital_hilton_protected_proof_intake_integration"]["action_authority_granted"] is False
    assert payload["capital_hilton_protected_proof_intake_integration"]["invoice_generation_allowed"] is False
    assert payload["capital_hilton_protected_proof_intake_integration"]["coupa_access_allowed"] is False
    assert payload["capital_hilton_protected_proof_intake_integration"]["send_submit_approval_allowed"] is False


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
    assert Path(summary["staged_bundle_path"]).is_dir()
    assert Path(summary["sync_request_marker_path"]).is_file()
    marker = json.loads(Path(summary["sync_request_marker_path"]).read_text(encoding="utf-8"))
    assert marker["schema_version"] == bundle.MAP_SYNC_REQUIRED_SCHEMA_VERSION
    assert marker["map_generation_id"] == summary["map_generation_id"]
    assert marker["bundle_hash"] == summary["bundle_hash"]
    assert marker["next_expected_actor"] == "mac_map_import_agent"
    assert marker["app_visible_current_claimed_by_pc"] is False
    assert marker["boundary"]["no_execution"] is True
    assert marker["boundary"]["no_credential"] is True
    assert marker["boundary"]["no_network"] is True
    for file_name in bundle.STABLE_APP_FACING_FILES:
        assert (Path(summary["staged_bundle_path"]) / file_name).is_file()
    expected = canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path)
    assert "operator_map_bundle_contract.json" in expected
    assert "openclaw_map_manifest.json" in expected
    assert "openclaw_map_snapshot.json" in expected
    operator_text = (export_root / "openclaw_map_OPERATOR.md").read_text(encoding="utf-8")
    assert "Raw generated read-models remain proof/detail" in operator_text
    assert "Agent Council / Dossier Summary" in operator_text
    assert "Cards available: `12`" in operator_text
    assert "Package Preview Receipt Summary" in operator_text
    assert "Example preview cards: `8`" in operator_text
    assert "Tool Adapter Receipt Summary" in operator_text
    assert "Adapter receipt cards: `12`" in operator_text
    assert "Capital Hilton Proof Metadata Summary" in operator_text
    assert "Missing proof count: `10`" in operator_text
    assert "Security Audit Readiness Summary" in operator_text
    assert "Ready for security pass: `true`" in operator_text
    assert "Security approval granted: `false`" in operator_text
    assert "Coverage gap records: `5`" in operator_text
    assert "Breadcrumbs reviewed: `15`" in operator_text
    assert "Security Pass Summary" in operator_text
    assert "Security pass completed: `true`" in operator_text
    assert "Worker output intake metadata approved: `true`" in operator_text
    assert "Chief reconciliation metadata approved: `true`" in operator_text
    assert "FULL_TRUST grants authority by itself: `false`" in operator_text
    assert "Post-Security Governance Batch Summary" in operator_text
    assert "Batch status: `COMPLETE_PENDING_STABLE_MAP_IMPORT`" in operator_text
    assert "Parked Capital R&D Experiment" in operator_text
    assert "Security Delta Review" in operator_text
    assert "Operator Attention Promotion" in operator_text
    assert "Chief Test Harness / Cross-Off" in operator_text
    assert "Cue candidates executable: `false`" in operator_text
    assert "Source deletion allowed: `false`" in operator_text


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
