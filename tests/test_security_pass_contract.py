import json
from pathlib import Path

import security_pass_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_security_pass_contract import main as export_main


FIXED_NOW = "2026-05-22T15:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    for relative in contract.MARKDOWN_TERRAIN_SYSTEMS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n", encoding="utf-8")

    read_models = root / "generated" / "read_models"
    fixtures = {
        "openclaw_map_manifest.json": {
            "schema_version": "openclaw_map_manifest_v0",
            "read_model_id": "openclaw_map_manifest",
            "map_generation_id": "map_3cf7a1d5f26147ae993a",
            "bundle_hash": "sha256:3d59cfda37602e22a7cb02dab1afb899acb65fe043efadf032820d8f5bb7c1af",
        },
        "openclaw_map_snapshot.json": {
            "schema_version": "openclaw_map_snapshot_v0",
            "read_model_id": "openclaw_map_snapshot",
            "map_generation_id": "map_3cf7a1d5f26147ae993a",
            "security_audit_readiness": {
                "ready_for_security_pass": True,
                "security_approval_granted": False,
                "action_authority_granted": False,
                "coverage_gap_summary": {"coverage_gap_records_count": 5},
                "parked_breadcrumb_summary": {"parked_breadcrumb_count": 15},
            },
            "capital_hilton_proof_metadata": {
                "current_phase": "HELM_THRESHOLD_LANE",
                "target_world": "Finance",
                "lane_destiny": "MOVE_TO_WORLD_ACTION",
                "missing_proof": list(contract.CAPITAL_HILTON_PROOF_IDS),
                "missing_proof_count": 10,
                "protected_proof_required": True,
            },
            "package_preview_receipts": {"present": True},
            "tool_adapter_receipts": {"present": True},
            "agent_council": {"agent_dossier_cards_count": 12},
        },
        "sync_health.json": {
            "schema_version": "sync_health_v0",
            "app_visible_map_status": {
                "map_status": "map_current",
                "app_visible": True,
                "map_generation_id": "map_3cf7a1d5f26147ae993a",
                "bundle_hash": "sha256:3d59cfda37602e22a7cb02dab1afb899acb65fe043efadf032820d8f5bb7c1af",
            },
            "check_transmission_display": {"lamp_state": "QUIET"},
        },
        "security_audit_readiness_packet.json": {
            "schema_version": "security_audit_readiness_packet_v0_pass_2",
            "read_model_id": "security_audit_readiness_packet",
            "security_pass_readiness_criteria": {
                "ready_for_security_pass": True,
                "security_approval_granted": False,
                "action_authority_granted": False,
            },
        },
        "capital_hilton_proof_metadata_packet.json": {
            "schema_version": "capital_hilton_proof_metadata_packet_v0",
            "read_model_id": "capital_hilton_proof_metadata_packet",
            "machine_proof": {
                "missing_proof_count": 10,
                "protected_proof_required": True,
            },
        },
        "package_preview_receipt_contract.json": {"schema_version": "package_preview_receipt_contract_v0"},
        "tool_adapter_receipt_contract.json": {"schema_version": "tool_adapter_receipt_contract_v0"},
        "memory_candidate_receipt_contract.json": {"schema_version": "memory_candidate_receipt_contract_v0"},
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_security_pass_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _decisions(payload: dict) -> dict:
    return {item["decision_id"]: item for item in payload["surface_security_decisions"]}


def _actors(payload: dict) -> dict:
    return {item["actor_id"]: item for item in payload["agent_model_tool_security_decision"]["actors"]}


def _adapters(payload: dict) -> dict:
    return {item["adapter_id"]: item for item in payload["agent_model_tool_security_decision"]["tool_adapters"]}


def _worker_outputs(payload: dict) -> dict:
    return {item["worker_output_id"]: item for item in payload["worker_output_intake"]["records"]}


def _capabilities(payload: dict) -> dict:
    return {item["capability_id"]: item for item in payload["orphaned_capability_detection"]["candidates"]}


def _promotion_decisions(payload: dict) -> dict:
    return {item["capability_id"]: item for item in payload["orphaned_capability_promotion_decisions"]["decisions"]}


def test_contract_is_deterministic_and_pass_1_plus_pass_2_plus_pass_3_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "security_pass_contract"
    assert first["pass_id"] == "pass_1_core_security_decisions_authority_boundaries"
    assert first["pass_2_id"] == "pass_2_worker_output_intake_orphaned_capability_detection"
    assert first["pass_3_id"] == "pass_3_chief_hermes_full_trust_clearance"
    assert first["contract_status"] == "deterministic_security_pass_pass_1_plus_pass_2_plus_pass_3_metadata_only"
    assert first["machine_proof"]["map_generation_id"] == "map_3cf7a1d5f26147ae993a"
    assert first["machine_proof"]["app_visible_map_current"] is True
    assert first["machine_proof"]["check_transmission_quiet"] is True
    assert first["core_rule"]["built_thing_is_not_active_because_it_exists"] is True
    assert first["core_rule"]["worker_output_is_not_truth_by_itself"] is True
    assert first["core_rule"]["full_trust_clearance_is_not_lm_confidence"] is True
    assert first["core_rule"]["chief_and_hermes_cannot_self_authorize"] is True


def test_security_pass_output_approves_read_only_and_preview_without_action_authority(tmp_path):
    payload = _build(tmp_path)
    summary = payload["security_pass_output_summary"]

    assert payload["security_pass_completed"] is True
    assert summary["security_pass_completed"] is True
    assert summary["security_approval_granted_for_read_only_surfaces"] is True
    assert summary["security_approval_granted_for_preview_surfaces"] is True
    assert summary["security_approval_granted_for_metadata_only_surfaces"] is True
    assert summary["security_approval_granted_for_worker_output_intake_metadata"] is True
    assert summary["security_approval_granted_for_orphaned_capability_detection"] is True
    assert summary["security_approval_granted_for_chief_reconciliation_metadata"] is True
    assert summary["security_approval_granted_for_hermes_architecture_review_metadata"] is True
    assert summary["security_approval_granted_for_trust_clearance_modeling"] is True
    assert summary["security_approval_granted_for_execution"] is False
    assert summary["automatic_activation_of_detected_capabilities_allowed"] is False
    assert summary["automatic_cross_off_allowed"] is False
    assert summary["chief_self_authorization_allowed"] is False
    assert summary["hermes_self_authorization_allowed"] is False
    assert payload["action_authority_granted"] is False
    assert payload["runtime_execution_authority_granted"] is False
    assert payload["tool_execution_authority_granted"] is False
    assert payload["model_execution_authority_granted"] is False
    assert payload["queue_execution_authority_granted"] is False
    assert payload["account_authority_granted"] is False
    assert payload["send_submit_approval_authority_granted"] is False
    assert payload["core_rule"]["security_pass_approval_is_not_action_authority"] is True


def test_every_dangerous_authority_flag_remains_false(tmp_path):
    payload = _build(tmp_path)

    for key, expected in contract.NO_ACTION_AUTHORITY_FLAGS.items():
        if key == "operator_final_authority":
            assert payload[key] is True
        else:
            assert payload[key] is False
    assert payload["machine_proof"]["all_dangerous_authority_flags_false"] is True
    assert payload["machine_proof"]["network_git_sync_mac_app_mutation_authority_added"] is False


def test_decision_categories_schema_and_global_authority_matrix_are_explicit(tmp_path):
    payload = _build(tmp_path)
    matrix = payload["global_authority_matrix"]

    assert payload["security_decision_categories"] == list(contract.SECURITY_DECISION_CATEGORIES)
    assert payload["security_decision_schema"]["required_fields"] == list(contract.DECISION_REQUIRED_FIELDS)
    assert payload["security_decision_schema"]["unknown_or_missing_decision_result"] == "UNKNOWN_FAIL_CLOSED"
    for allowed in [
        "stable map display",
        "read-model display",
        "Markdown Knowledge Atlas metadata readback",
        "package preview display",
        "tool adapter receipt display",
        "Finance World preview",
        "Security Readiness display",
    ]:
        assert allowed in matrix["allowed_after_this_security_pass"]
    for blocked in [
        "live model calls",
        "model/API execution",
        "tool execution",
        "queue/autonomy execution",
        "browser/OAuth/account access",
        "Gmail/calendar/Coupa/Telegram access",
        "credentials/tokens/cookies/API keys",
        "send/submit/approval",
        "invoice generation",
        "ledger writes",
        "email dispatch",
        "raw finance/private body ingestion",
        "broad Markdown body ingestion",
        "Repo B execution",
        "file delete/move/cleanup/remount",
        "network operation",
        "automatic promotion",
        "automatic queueing",
        "automatic activation of detected capabilities",
        "automatic crossing off",
        "Chief/Hermes self-authorization",
        "external dependency adoption without review",
        "C-drive artifact writes",
    ]:
        assert blocked in matrix["still_blocked"]
    assert matrix["authority_flags"]["operator_final_authority"] is True
    assert matrix["authority_flags"]["tool_execution_allowed"] is False


def test_surface_security_decisions_cover_current_app_surfaces(tmp_path):
    decisions = _decisions(_build(tmp_path))

    assert set(decisions) == {
        "stable_map_bundle_read_only",
        "mission_control_mac_app_read_only",
        "agent_council_dossier_cards_preview",
        "package_preview_tool_receipt_surface",
        "finance_world_capital_hilton_preview",
        "security_readiness_eliwinship_surface",
        "evidence_drawer_proof_rows",
    }
    assert decisions["stable_map_bundle_read_only"]["approval_status"] == "APPROVED_STABLE_MAP_SURFACE"
    assert "source truth claim" in decisions["stable_map_bundle_read_only"]["blocked_posture"]
    assert decisions["mission_control_mac_app_read_only"]["approval_status"] == "APPROVED_READ_ONLY"
    assert "direct backend execution" in decisions["mission_control_mac_app_read_only"]["blocked_posture"]
    assert decisions["agent_council_dossier_cards_preview"]["approval_status"] == "APPROVED_PREVIEW_ONLY"
    assert "live chat" in decisions["agent_council_dossier_cards_preview"]["blocked_posture"]
    assert decisions["package_preview_tool_receipt_surface"]["approval_status"] == "APPROVED_PREVIEW_ONLY"
    assert "dispatch" in decisions["package_preview_tool_receipt_surface"]["blocked_posture"]
    assert decisions["finance_world_capital_hilton_preview"]["approval_status"] == "APPROVED_WORLD_PREVIEW"
    assert "invoice generation" in decisions["finance_world_capital_hilton_preview"]["blocked_posture"]
    assert decisions["security_readiness_eliwinship_surface"]["approval_status"] == "APPROVED_READ_ONLY"
    assert decisions["evidence_drawer_proof_rows"]["approval_status"] == "APPROVED_PROOF_DETAIL_ONLY"
    for decision in decisions.values():
        assert decision["authority_flags"]["runtime_execution_authority_granted"] is False
        assert decision["authority_flags"]["tool_execution_allowed"] is False


def test_capital_hilton_security_decision_approves_preview_and_blocks_execution(tmp_path):
    decision = _build(tmp_path)["capital_hilton_security_pass_decision"]

    assert decision["current_phase"] == "HELM_THRESHOLD_LANE"
    assert decision["target_world"] == "Finance"
    assert decision["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert decision["missing_proof_count"] == 10
    assert decision["protected_proof_required"] is True
    assert decision["candidate_facts_proven"] is False
    assert decision["finance_world_preview_exists"] is True
    assert decision["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
    assert decision["decision"]["finance_world_preview"] == "approved"
    assert decision["decision"]["candidate_facts_display"] == "approved_with_not_proven_label"
    assert decision["blocked"]["invoice_generation"] is True
    assert decision["blocked"]["coupa_access"] is True
    assert decision["blocked"]["credentials"] is True
    assert decision["blocked"]["excel_raw_body_ingestion"] is True
    assert decision["blocked"]["raw_finance_body_ingestion"] is True
    assert decision["blocked"]["send_submit_approval"] is True
    assert decision["required_gates"]["guardian_gate"] == "required_for_protected_proof_metadata"
    assert decision["required_gates"]["operator_final_authority"] == "required_for_future_action"


def test_markdown_terrain_decision_uses_existing_metadata_and_blocks_broad_body_or_file_mutation(tmp_path):
    decision = _build(tmp_path)["markdown_terrain_security_decision"]

    assert decision["markdown_backend_capability_status"] == "YES_READY"
    assert {item["path"] for item in decision["existing_systems"]} == set(contract.MARKDOWN_TERRAIN_SYSTEMS)
    assert all(item["present"] is True for item in decision["existing_systems"])
    assert all(item["authority_granted_by_presence"] is False for item in decision["existing_systems"])
    assert decision["safe_metadata_coverage"] == contract.MARKDOWN_METADATA_COUNTS
    assert decision["decision"]["metadata_only_markdown_atlas_readback"] == "approved"
    assert decision["decision"]["allowlisted_bounded_markdown_evidence_excerpts"] == "approved"
    assert decision["decision"]["app_visibility_for_markdown_terrain"] == "future_gated_visibility_gap_not_security_blocker"
    assert decision["blocked"]["broad_markdown_body_ingestion"] is True
    assert decision["blocked"]["broad_doc_reorganization"] is True
    assert decision["blocked"]["file_moves_deletes_renames"] is True
    assert decision["blocked"]["vector_index_creation"] is True
    assert decision["blocked"]["old_prompts_as_current_truth_unless_classified_proven"] is True
    assert decision["no_new_mapper_needed_now"] is True


def test_operator_answers_shared_paths_and_parked_breadcrumbs_remain_non_executing(tmp_path):
    payload = _build(tmp_path)
    answers = payload["operator_answer_capture_security_decision"]
    shared = payload["helm_focus_shared_path_security_decision"]
    parked = payload["parked_breadcrumb_security_decision"]

    assert answers["answer_schema"] == "approved"
    assert answers["future_capture_ui"] == "approved_as_capture_only_concept"
    assert answers["captured_answers"] == "Memory Candidate Receipts only"
    assert answers["operator_answers_as_proof"] == "blocked"
    assert answers["automatic_truth_promotion"] == "blocked"
    assert answers["automatic_lane_quieting_without_receipt_or_proof"] == "blocked"
    assert shared["helm_issue_focus_mode_model"] == "approved_for_read_only_ui"
    assert shared["shared_execution_paths"] == "approved_as_non_executing_consolidation"
    assert shared["blocked"]["live_execute_buttons"] is True
    assert shared["blocked"]["automatic_queueing_from_shared_path"] is True
    assert parked["parked_breadcrumb_review"] == "approved"
    assert parked["auto_promotion"] == "blocked"
    assert parked["queue_execution"] == "blocked"
    assert parked["holding_cell_creation"] == "future_gated_until_operator_attention_promotion_contract"


def test_worker_output_intake_is_metadata_only_and_does_not_activate_capabilities(tmp_path):
    payload = _build(tmp_path)
    intake = payload["worker_output_intake"]
    outputs = _worker_outputs(payload)

    assert intake["allowed_intake_statuses"] == list(contract.WORKER_OUTPUT_INTAKE_STATUSES)
    for field in contract.WORKER_OUTPUT_INTAKE_FIELDS:
        assert field in intake["required_fields"]
    assert intake["rules"]["worker_output_is_not_truth_by_itself"] is True
    assert intake["rules"]["worker_output_must_not_activate_anything"] is True
    assert intake["rules"]["worker_output_must_not_create_queue_tasks"] is True
    assert intake["rules"]["worker_output_must_not_mutate_source_files"] is True
    assert intake["rules"]["worker_output_intake_is_metadata_only"] is True
    assert set(outputs) == {"future_invoicing_state_machine_audit"}
    assert payload["machine_proof"]["worker_output_intake_metadata_approved"] is True
    assert payload["machine_proof"]["worker_output_intake_does_not_activate_capabilities"] is True


def test_orphaned_capability_detection_represents_defaults_without_execution(tmp_path):
    payload = _build(tmp_path)
    detection = payload["orphaned_capability_detection"]
    capabilities = _capabilities(payload)

    assert detection["allowed_capability_statuses"] == list(contract.ORPHANED_CAPABILITY_STATUSES)
    for field in contract.ORPHANED_CAPABILITY_FIELDS:
        assert field in detection["required_fields"]
    assert detection["core_doctrine"]["built_thing_is_not_active_because_it_exists"] is True
    assert detection["core_doctrine"]["activation_requires_receipted_classified_gated_trusted_surfaced"] is True
    assert detection["core_doctrine"]["detection_does_not_execute_capability"] is True
    assert detection["core_doctrine"]["detection_does_not_create_queue_tasks"] is True
    assert set(capabilities) == {
        "markdown_knowledge_atlas",
        "approved_markdown_evidence_ingestion",
        "corpus_atlas_engine",
        "security_audit_readiness_packet",
        "capital_hilton_proof_metadata_packet",
        "agent_council_dossier_surface",
        "package_preview_tool_receipt_surface",
    }
    markdown = capabilities["markdown_knowledge_atlas"]
    assert markdown["capability_status"] == "KNOWN_NOT_SURFACED"
    assert markdown["safe_to_use_pre_security"] is True
    assert "markdown_documents" in markdown["sqlite_table_refs"]
    assert "markdown_document_classifications" in markdown["sqlite_table_refs"]
    assert "broad Markdown body ingestion" in markdown["blocked_actions"]
    assert "file moves/deletes/renames" in markdown["blocked_actions"]
    assert "old docs as current truth without classification/proof" in markdown["blocked_actions"]
    readiness = capabilities["security_audit_readiness_packet"]
    assert readiness["capability_status"] == "KNOWN_AND_SURFACED"
    assert readiness["mission_control_visibility_status"] == "surfaced"
    assert payload["machine_proof"]["orphaned_capability_detection_approved"] is True
    assert payload["machine_proof"]["orphaned_capability_detection_does_not_execute_capabilities"] is True


def test_promotion_decisions_are_recommendations_only(tmp_path):
    payload = _build(tmp_path)
    promotion = payload["orphaned_capability_promotion_decisions"]
    decisions = _promotion_decisions(payload)

    assert promotion["allowed_decisions"] == list(contract.ORPHANED_CAPABILITY_PROMOTION_DECISIONS)
    for field in contract.ORPHANED_CAPABILITY_PROMOTION_FIELDS:
        assert field in promotion["required_fields"]
    assert promotion["rules"]["promotion_decisions_are_recommendations_only"] is True
    assert promotion["rules"]["must_not_trigger_file_edits"] is True
    assert promotion["rules"]["must_not_queue_tasks"] is True
    assert promotion["rules"]["must_not_activate_runtime"] is True
    assert promotion["rules"]["must_not_run_detected_capability"] is True
    assert promotion["rules"]["must_not_change_mission_control"] is True
    assert decisions["markdown_knowledge_atlas"]["decision"] == "PROMOTE_TO_STABLE_MAP"
    assert decisions["markdown_knowledge_atlas"]["action_authority_granted"] is False
    assert decisions["capital_hilton_proof_metadata_packet"]["guardian_gate_required"] is True
    assert payload["machine_proof"]["promotion_decisions_are_recommendations_only"] is True


def test_future_invoicing_audit_is_parked_blocked_stress_test_artifact(tmp_path):
    audit = _worker_outputs(_build(tmp_path))["future_invoicing_state_machine_audit"]

    assert audit["reported_status"] == "BLOCKED"
    assert audit["intake_status"] == "PARKED"
    assert audit["security_relevance"] == "high"
    assert audit["operator_review_required"] is False
    assert audit["security_review_required"] is True
    assert "Stage 1 ingestion/data validation is partially supported by existing contracts" in audit["test_results"]
    assert "Stage 2 ledger write/idempotency is blocked until future authority" in audit["test_results"]
    assert "Stage 3 pre-flight reconciliation is missing deterministic contract" in audit["test_results"]
    assert "Stage 4 contextual delivery/dispatch is blocked until future authority" in audit["test_results"]
    for ref in [
        "generated/read_models/capital_hilton_proof_metadata_packet.json",
        "generated/read_models/security_audit_readiness_packet.json",
        "generated/read_models/package_preview_receipt_contract.json",
        "generated/read_models/tool_adapter_receipt_contract.json",
    ]:
        assert ref in audit["receipt_refs"]
    for blocked in [
        "no ledger writes",
        "no email dispatch",
        "no Coupa/browser/account/credential authority",
        "no invoice generation",
        "no send/submit/approval",
    ]:
        assert blocked in audit["authority_claims"]
    assert audit["next_safe_move"] == "Preserve as future Finance/invoicing stress-test reference; do not implement active invoicing."


def test_future_invoicing_audit_does_not_authorize_finance_execution(tmp_path):
    payload = _build(tmp_path)

    assert payload["invoice_generation_allowed"] is False
    assert payload["ledger_write_allowed"] is False
    assert payload["email_dispatch_allowed"] is False
    assert payload["browser_oauth_account_access_allowed"] is False
    assert payload["credential_handling_allowed"] is False
    assert payload["gmail_calendar_coupa_telegram_access_allowed"] is False
    assert payload["send_submit_approval_allowed"] is False
    assert payload["machine_proof"]["future_invoicing_audit_status"] == "PARKED"
    assert payload["machine_proof"]["future_invoicing_audit_does_not_authorize_invoice_generation"] is True
    assert payload["machine_proof"]["future_invoicing_audit_does_not_authorize_ledger_writes"] is True
    assert payload["machine_proof"]["future_invoicing_audit_does_not_authorize_email_dispatch"] is True


def test_chief_and_hermes_roles_are_metadata_only_and_cannot_self_authorize(tmp_path):
    payload = _build(tmp_path)
    trust = payload["chief_hermes_trust_building_reconciliation"]
    chief = trust["chief_role"]
    hermes = trust["hermes_role"]

    assert trust["core_doctrine"]["currently_non_executing_until_deterministic_trust_is_earned"] is True
    assert trust["core_doctrine"]["full_trust_clearance_is_deterministic_not_lm_confidence"] is True
    assert chief["role_id"] == "chief_reconciliation_role"
    assert chief["can_self_authorize"] is False
    assert chief["current_authority"] == "metadata_review_reconciliation_recommendation_only"
    for blocked in ["live execution", "queue execution", "repair execution", "tool execution", "self-authorization", "automatic cross-off"]:
        assert blocked in chief["blocked_current_actions"]
    assert "explain what prevents FULL_TRUST_CLEARANCE" in chief["allowed_current_actions"]
    assert hermes["role_id"] == "hermes_architecture_review_role"
    assert hermes["can_self_authorize"] is False
    assert hermes["current_authority"] == "advisory_architecture_review_metadata_only"
    for blocked in ["execution authority", "external dependency adoption", "network/API/credential use", "self-authorization", "file mutation"]:
        assert blocked in hermes["blocked_current_actions"]
    for requirement in [
        "source trust review",
        "license review",
        "maintenance/activity review",
        "security risk review",
        "Operator approval before adoption",
        "no network/API/credential use unless later authorized",
    ]:
        assert requirement in hermes["external_dependency_review_requirements"]
    assert payload["machine_proof"]["chief_reconciliation_metadata_approved"] is True
    assert payload["machine_proof"]["hermes_architecture_review_metadata_approved"] is True
    assert payload["machine_proof"]["chief_can_self_authorize"] is False
    assert payload["machine_proof"]["hermes_can_self_authorize"] is False


def test_chief_hermes_guardian_operator_synergy_order_and_operator_final_authority(tmp_path):
    synergy = _build(tmp_path)["chief_hermes_guardian_operator_synergy"]

    assert synergy["chief_question"] == "Was the work done, tested, reconciled, and ready to cross off or requeue?"
    assert synergy["hermes_question"] == "Does this work fit the architecture, improve the system, avoid slop, and point toward the North Star?"
    assert synergy["guardian_question"] == "Is this safe, gated, redacted, quarantined, or blocked?"
    assert synergy["operator_question"] == "Do I approve this direction, authority, and risk?"
    assert synergy["decision_order"] == [
        "Chief reconciliation",
        "Hermes architecture review when architecture relevance is high",
        "Guardian safety gate when sensitive/protected/security-relevant",
        "Operator final decision where required",
    ]
    assert synergy["operator_final_authority"] is True


def test_full_trust_clearance_model_does_not_grant_authority_by_itself(tmp_path):
    payload = _build(tmp_path)
    model = payload["chief_hermes_trust_building_reconciliation"]["trust_clearance_model"]
    example = model["example_record"]

    assert model["trust_clearance_states"] == list(contract.TRUST_CLEARANCE_STATES)
    for field in contract.TRUST_CLEARANCE_REQUIRED_FIELDS:
        assert field in model["required_fields"]
    assert "FULL_TRUST_CLEARANCE" in model["trust_clearance_states"]
    assert model["rules"]["full_trust_clearance_is_not_lm_confidence_score"] is True
    assert model["rules"]["full_trust_clearance_does_not_itself_grant_execution_authority"] is True
    assert model["rules"]["unattended_execution_requires_full_trust_and_task_class_approval"] is True
    assert model["rules"]["below_full_trust_tasks_must_not_run_unattended"] is True
    assert example["trust_clearance_status"] == "HIGH_TRUST_NEEDS_OPERATOR"
    assert example["full_trust_clearance_eligible"] is False
    assert example["future_unattended_execution_eligible"] is False
    assert example["action_authority_granted"] is False
    assert payload["machine_proof"]["full_trust_clearance_grants_authority_by_itself"] is False
    assert payload["machine_proof"]["unattended_execution_requires_full_trust_and_task_class_approval"] is True
    assert payload["machine_proof"]["below_full_trust_tasks_can_run_unattended"] is False
    assert payload["machine_proof"]["trust_clearance_modeling_approved"] is True


def test_worker_and_orphan_records_include_reconciliation_trust_extensions(tmp_path):
    payload = _build(tmp_path)
    audit = _worker_outputs(payload)["future_invoicing_state_machine_audit"]
    capabilities = _capabilities(payload)

    for record in [audit, capabilities["markdown_knowledge_atlas"], capabilities["capital_hilton_proof_metadata_packet"]]:
        for field in [
            "chief_reconciliation_status",
            "chief_test_harness_required",
            "chief_recommendation",
            "hermes_architecture_review_required",
            "hermes_coherence_status",
            "hermes_recommendation",
            "guardian_gate_required",
            "operator_final_decision_required",
            "trust_clearance_status",
            "trust_clearance_blockers",
            "trust_building_detour",
            "full_trust_clearance_eligible",
            "completion_status",
            "cross_off_allowed",
            "requeue_required",
            "park_required",
            "quarantine_required",
        ]:
            assert field in record
    assert audit["chief_reconciliation_status"] == "PARKED_WITH_PROOF"
    assert audit["trust_clearance_status"] == "NO_TRUST"
    assert audit["cross_off_allowed"] is False
    assert audit["park_required"] is True
    assert capabilities["markdown_knowledge_atlas"]["chief_reconciliation_status"] == "BUILT_NOT_SURFACED"
    assert capabilities["markdown_knowledge_atlas"]["trust_clearance_status"] == "HIGH_TRUST_NEEDS_HERMES"
    assert capabilities["capital_hilton_proof_metadata_packet"]["guardian_gate_required"] is True


def test_completion_cross_off_rule_never_deletes_or_mutates_source_items(tmp_path):
    rule = _build(tmp_path)["completion_cross_off_rule"]

    assert "original task/source ref is known" in rule["cross_off_allowed_only_when"]
    assert "Chief reconciliation passes or marks sufficient proof" in rule["cross_off_allowed_only_when"]
    assert "delete original note" in rule["cross_off_must_not"]
    assert "mutate source Markdown" in rule["cross_off_must_not"]
    assert "remove cue source" in rule["cross_off_must_not"]
    assert "hide evidence" in rule["cross_off_must_not"]
    assert "happen automatically in this lane" in rule["cross_off_must_not"]
    assert "completion receipt" in rule["cross_off_should_create"]
    assert rule["automatic_cross_off_allowed"] is False
    assert rule["source_markdown_mutation_allowed"] is False


def test_trust_building_detours_cover_required_trust_gaps(tmp_path):
    detours = _build(tmp_path)["trust_building_detours"]

    for gap in [
        "missing proof",
        "missing tests",
        "missing receipt",
        "unclear source task",
        "ambiguous operator intent",
        "architecture review needed",
        "Guardian/security gate needed",
        "protected/sensitive material involved",
        "external dependency risk",
        "conflict with another lane",
        "stale terrain/map mismatch",
        "insufficient rollback/recovery path",
    ]:
        assert gap in detours["trust_gap_types"]
    for detour in [
        "add proof ref",
        "run bounded test",
        "create receipt",
        "classify source task",
        "ask operator one question",
        "request Hermes architecture review",
        "request Guardian safety review",
        "park until dependency exists",
        "merge with existing lane",
        "reject as obsolete",
    ]:
        assert detour in detours["smallest_safe_detours"]
    assert detours["below_full_trust_action"] == "detour_or_operator_assist_or_park_or_block_fail_closed"


def test_example_trust_reconciliation_records_cover_required_examples(tmp_path):
    records = {
        item["record_id"]: item
        for item in _build(tmp_path)["chief_hermes_trust_building_reconciliation"]["example_trust_reconciliation_records"]
    }

    assert set(records) == {
        "markdown_knowledge_atlas",
        "security_readiness_surface",
        "future_invoicing_state_machine_audit",
        "capital_hilton_finance_preview",
    }
    assert records["markdown_knowledge_atlas"]["trust_clearance_scope"] == "high for metadata readback, not execution"
    assert records["security_readiness_surface"]["trust_clearance_scope"] == "high for read-only display"
    assert records["future_invoicing_state_machine_audit"]["trust_clearance_status"] == "NO_TRUST"
    assert records["future_invoicing_state_machine_audit"]["execution_authority_granted"] is False
    assert records["capital_hilton_finance_preview"]["trust_clearance_scope"] == "preview-only"
    assert records["capital_hilton_finance_preview"]["execution_authority_granted"] is False


def test_agent_model_tool_decision_allows_display_but_blocks_activation_and_adapters(tmp_path):
    payload = _build(tmp_path)
    actors = _actors(payload)
    adapters = _adapters(payload)

    assert set(actors) == set(contract.ACTOR_IDS)
    for actor_id, actor in actors.items():
        assert actor["display_allowed"] is True
        assert actor["model_call_allowed"] is False
        assert actor["live_agent_activation_allowed"] is False
        assert actor["tool_use_allowed"] is False
        assert actor["self_authority_allowed"] is False
        assert actor["memory_write_allowed"] is False
        assert actor["operator_final_authority"] is (actor_id == "operator")
    assert adapters["stable_map_reader"]["posture"] == "read_only_approved"
    assert adapters["stable_map_reader"]["capability_granted"] == "READ_METADATA"
    assert adapters["package_preview_exporter"]["posture"] == "preview_receipt_metadata_approved"
    assert adapters["memory_candidate_receipt_writer"]["posture"] == "candidate_only_future_gated"
    assert adapters["codex_scoped_build_verifier"]["posture"] == "worker_prompt_only_not_openclaw_runtime"
    for blocked in [
        "browser_oauth_adapter",
        "gmail_calendar_adapter",
        "coupa_adapter",
        "telegram_adapter",
        "repo_b_planner_builder_adapter",
    ]:
        assert adapters[blocked]["capability_granted"] == "NONE"
        assert adapters[blocked]["tool_execution_allowed"] is False
        assert adapters[blocked]["network_allowed"] is False
        assert adapters[blocked]["account_access_allowed"] is False


def test_stable_map_integration_is_next_refresh_not_this_contract_lane(tmp_path):
    stable = _build(tmp_path)["stable_map_integration"]
    safe = stable["safe_summary_for_next_refresh"]

    assert stable["contract_generated_as_read_model"] is True
    assert stable["summary_included_in_stable_map_now"] is False
    assert stable["next_map_bundle_refresh_requirement"] == "Next stable-map refresh should include Security Pass Contract v0 Pass 1 + Pass 2 + Pass 3 summary."
    assert safe["security_pass_contract_id"] == "security_pass_contract"
    assert safe["security_pass_completed"] is True
    assert safe["read_only_surfaces_approved"] is True
    assert safe["preview_surfaces_approved"] is True
    assert safe["worker_output_intake_metadata_approved"] is True
    assert safe["orphaned_capability_detection_approved"] is True
    assert safe["chief_reconciliation_metadata_approved"] is True
    assert safe["hermes_architecture_review_metadata_approved"] is True
    assert safe["trust_clearance_modeling_approved"] is True
    assert safe["action_authority"] is False
    assert safe["automatic_cross_off_allowed"] is False
    assert safe["capital_hilton_preview_approved"] is True
    assert safe["capital_hilton_execution_blocked"] is True
    assert safe["markdown_terrain_metadata_approved"] is True
    assert safe["broad_markdown_body_blocked"] is True
    assert safe["future_invoicing_audit_parked"] is True
    assert safe["next_recommended_lane"] == "stable_map_refresh_security_pass_summary"


def test_export_script_writes_json_and_operator_outputs(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    assert export_main(["--repo-root", tmp_path.as_posix(), "--export-root", export_root.as_posix(), "--format", "summary"]) == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["decision_count"] == 7
    assert summary["security_pass_completed"] is True
    assert summary["read_only_surfaces_approved"] is True
    assert summary["preview_surfaces_approved"] is True
    assert summary["worker_output_intake_approved"] is True
    assert summary["orphaned_capability_detection_approved"] is True
    assert summary["chief_reconciliation_approved"] is True
    assert summary["hermes_architecture_review_approved"] is True
    assert summary["trust_clearance_modeling_approved"] is True
    assert summary["worker_output_count"] == 1
    assert summary["orphaned_capability_count"] == 7
    assert summary["action_authority_granted"] is False
    assert summary["live_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "security_pass_contract"
    assert payload["machine_proof"]["content_hash"].startswith("sha256:")
    assert "Security Pass Contract v0 Pass 1 + Pass 2 + Pass 3" in operator
    assert "ELIWINSHIP" in operator
    assert "Worker Output Intake" in operator
    assert "Future Invoicing Audit" in operator
    assert "FULL_TRUST_CLEARANCE" in operator
    assert "Chief" in operator
    assert "Hermes" in operator


def test_generated_outputs_are_safe_canonical_read_model_files(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    assert export_main(["--repo-root", tmp_path.as_posix(), "--export-root", export_root.as_posix(), "--format", "summary"]) == 0
    capsys.readouterr()

    expected = canonical_generated_read_model_expected_files(export_root, repo_root=tmp_path)
    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_contract_source_avoids_runtime_network_sync_and_destructive_patterns():
    source = Path(contract.__file__).read_text(encoding="utf-8").lower()

    for forbidden in [
        "subprocess",
        "os.system",
        "shell=true",
        "requests.",
        "httpx.",
        "urllib.request",
        ".unlink(",
        "shutil.rmtree",
        "shutil.move",
        "/mnt/" + "c/",
        "file:///" + "c:",
    ]:
        assert forbidden not in source
