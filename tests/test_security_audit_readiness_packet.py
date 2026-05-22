import json
from pathlib import Path

import security_audit_readiness_packet as packet
from scripts.export_security_audit_readiness_packet import main as export_main


FIXED_NOW = "2026-05-22T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    candidate_facts = [
        {
            "fact_id": "completed_performance_dates",
            "display_name": "Completed performance date(s)",
            "current_value": ["2026-05-08", "2026-05-15"],
            "proof_status": "CANDIDATE_FACT_NOT_PROVEN",
            "machine_proven": False,
            "proof_ref": None,
            "source_reference": "generated/read_models/capital_hilton_proof_metadata_packet.json#capital_hilton_candidate_facts",
            "raw_body_included": False,
        },
        {
            "fact_id": "rate",
            "display_name": "Rate",
            "current_value": "$400 per gig",
            "proof_status": "CANDIDATE_FACT_NOT_PROVEN",
            "machine_proven": False,
            "proof_ref": None,
            "source_reference": "generated/read_models/capital_hilton_proof_metadata_packet.json#capital_hilton_candidate_facts",
            "raw_body_included": False,
        },
        {
            "fact_id": "subtotal",
            "display_name": "Subtotal",
            "current_value": "$800",
            "proof_status": "CANDIDATE_FACT_NOT_PROVEN",
            "machine_proven": False,
            "proof_ref": None,
            "source_reference": "generated/read_models/capital_hilton_proof_metadata_packet.json#capital_hilton_candidate_facts",
            "raw_body_included": False,
        },
        {
            "fact_id": "invoice_shape_one_invoice_posture",
            "display_name": "Invoice shape / one-invoice posture",
            "current_value": "one invoice for both dates",
            "proof_status": "CANDIDATE_FACT_NOT_PROVEN",
            "machine_proven": False,
            "proof_ref": None,
            "source_reference": "generated/read_models/capital_hilton_proof_metadata_packet.json#capital_hilton_candidate_facts",
            "raw_body_included": False,
        },
    ]
    missing_proof = list(packet.CAPITAL_HILTON_PROOF_IDS)
    questions = [
        {
            "question_id": "one_invoice_posture",
            "question": "Do you remember whether the Capital Hilton invoice should cover both 2026-05-08 and 2026-05-15 on one invoice?",
            "classification": "memory_only_clarification",
            "answer_becomes": "memory_candidate_receipt",
            "answer_is_machine_proof": False,
        },
        {
            "question_id": "rate_confirmation",
            "question": "Do you remember whether $400/gig is the correct rate for both dates?",
            "classification": "proof_needed",
            "answer_becomes": "memory_candidate_receipt",
            "answer_is_machine_proof": False,
        },
        {
            "question_id": "coupa_po_reference",
            "question": "Is there a Coupa PO number or payment reference that should exist?",
            "classification": "protected_proof_needed",
            "answer_becomes": "memory_candidate_receipt",
            "answer_is_machine_proof": False,
        },
        {
            "question_id": "proof_source_location",
            "question": "Is the proof source likely Coupa, Excel, email, a PDF, a calendar entry, or a packet already in OpenClaw?",
            "classification": "proof_needed",
            "answer_becomes": "memory_candidate_receipt",
            "answer_is_machine_proof": False,
        },
        {
            "question_id": "ap_route",
            "question": "Should the invoice go through Coupa only, email/AP contact, or another payment route?",
            "classification": "world_transition_needed",
            "answer_becomes": "memory_candidate_receipt",
            "answer_is_machine_proof": False,
        },
        {
            "question_id": "protected_material",
            "question": "Is there any protected client material that must be represented only as metadata?",
            "classification": "security_gate_needed",
            "answer_becomes": "memory_candidate_receipt",
            "answer_is_machine_proof": False,
        },
        {
            "question_id": "finance_world_ready",
            "question": "What would convince you the invoice is ready to move from helm threshold lane into Finance World action?",
            "classification": "world_transition_needed",
            "answer_becomes": "memory_candidate_receipt",
            "answer_is_machine_proof": False,
        },
    ]
    capital_summary = {
        "present": True,
        "current_phase": "HELM_THRESHOLD_LANE",
        "target_world": "Finance",
        "lane_destiny": "MOVE_TO_WORLD_ACTION",
        "missing_proof": missing_proof,
        "missing_proof_count": 10,
        "protected_proof_required": True,
        "all_candidate_facts_marked_not_proven": True,
        "candidate_facts": candidate_facts,
        "operator_memory_questions": questions,
        "finance_world_preview": {"preview_only": True, "target_world": "Finance", "not_executable": True},
        "authority_boundary": {
            "coupa_access_allowed": False,
            "browser_oauth_allowed": False,
            "credential_handling_allowed": False,
            "gmail_calendar_access_allowed": False,
            "excel_raw_body_ingestion_allowed": False,
            "raw_finance_body_ingestion_allowed": False,
            "invoice_generation_allowed": False,
            "send_submit_approval_allowed": False,
            "account_access_allowed": False,
            "model_call_allowed": False,
            "agent_activation_allowed": False,
            "tool_execution_allowed": False,
            "queue_execution_allowed": False,
            "runtime_dispatch_allowed": False,
        },
    }
    fixtures = {
        "openclaw_map_manifest.json": {
            "schema_version": "openclaw_map_manifest_v0",
            "read_model_id": "openclaw_map_manifest",
            "map_generation_id": "map_fbda77b8af4e9c796c03",
            "bundle_hash": "sha256:d54194ee82f05e41724f26bb3def93f048f4552e6ff40914cfdf6227445bdb39",
        },
        "openclaw_map_snapshot.json": {
            "schema_version": "openclaw_map_snapshot_v0",
            "read_model_id": "openclaw_map_snapshot",
            "map_generation_id": "map_fbda77b8af4e9c796c03",
            "capital_hilton_proof_metadata": capital_summary,
            "package_preview_receipts": {"present": True},
            "agent_council": {"agent_dossier_cards_count": 12},
        },
        "capital_hilton_proof_metadata_packet.json": {
            "schema_version": "capital_hilton_proof_metadata_packet_v0",
            "read_model_id": "capital_hilton_proof_metadata_packet",
            "capital_hilton_candidate_facts": candidate_facts,
            "operator_memory_questions": questions,
            "missing_proof_checklist": missing_proof,
            "machine_proof": {
                "missing_proof_count": 10,
                "protected_proof_required": True,
                "all_candidate_facts_not_machine_proven": True,
            },
        },
        "package_preview_receipt_contract.json": {"schema_version": "package_preview_receipt_contract_v0"},
        "tool_adapter_receipt_contract.json": {"schema_version": "tool_adapter_receipt_contract_v0"},
        "model_selection_receipt_contract.json": {"schema_version": "model_selection_receipt_contract_v0"},
        "memory_candidate_receipt_contract.json": {"schema_version": "memory_candidate_receipt_contract_v0"},
        "agent_memory_scope_contract.json": {"schema_version": "agent_memory_scope_contract_v0"},
        "agent_terrain_awareness_readback_contract.json": {"schema_version": "agent_terrain_awareness_readback_contract_v0"},
        "operator_threshold_map_contract.json": {"schema_version": "operator_threshold_map_contract_v0"},
        "sync_health.json": {"schema_version": "sync_health_v0", "app_visible_map_status": {"map_status": "map_current"}},
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return packet.build_security_audit_readiness_packet(repo_root=tmp_path, generated_at=FIXED_NOW)


def _shared_paths(payload: dict) -> dict:
    return {item["shared_execution_path_id"]: item for item in payload["shared_execution_paths"]}


def test_packet_generation_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert packet.stable_json(first) == packet.stable_json(second)
    assert first["schema_version"] == packet.SCHEMA_VERSION
    assert first["read_model_id"] == "security_audit_readiness_packet"
    assert first["pass_id"] == "pass_1_active_helm_readiness"
    assert first["pass_2_id"] == "pass_2_passive_audit_structures"
    assert first["contract_status"] == "deterministic_security_audit_readiness_pass_1_plus_pass_2_metadata_only"
    assert first["machine_proof"]["pass_1_structures_preserved"] is True
    assert first["machine_proof"]["pass_2_included"] is True
    assert first["machine_proof"]["mission_control_app_code_touched"] is False


def test_every_dangerous_authority_flag_is_false_and_operator_authority_remains_final(tmp_path):
    payload = _build(tmp_path)

    for key, value in packet.NO_AUTHORITY_FLAGS.items():
        if key == "operator_final_authority":
            assert payload[key] is True
        else:
            assert payload[key] is False
    assert payload["security_approval_granted"] is False
    assert payload["machine_proof"]["security_approval_granted"] is False
    assert payload["machine_proof"]["all_dangerous_authority_flags_false"] is True
    assert payload["machine_proof"]["security_readiness_is_not_action_readiness"] is True


def test_map_to_terrain_provenance_keeps_capital_hilton_claims_candidate(tmp_path):
    payload = _build(tmp_path)
    claims = {item["claim_id"]: item for item in payload["map_to_terrain_provenance"]}

    assert claims["capital_hilton_completed_performance_dates"]["verification_status"] == "CANDIDATE"
    assert claims["capital_hilton_rate"]["verification_status"] == "CANDIDATE"
    assert claims["capital_hilton_subtotal"]["verification_status"] == "CANDIDATE"
    assert claims["capital_hilton_one_invoice_posture"]["verification_status"] == "CANDIDATE"
    assert claims["capital_hilton_completed_performance_dates"]["proof_metadata_refs"] == []
    assert claims["capital_hilton_completed_performance_dates"]["missing_proof"] == ["performance_date_proof_metadata"]
    assert payload["map_to_terrain_rule"]["stable_map_is_app_facing_reflection_not_source_truth"] is True
    assert payload["map_to_terrain_rule"]["claims_without_provenance_must_not_render_as_proven"] is True
    assert payload["map_to_terrain_rule"]["capital_hilton_required_result"]["missing_proof_count"] == 10
    assert payload["map_to_terrain_rule"]["capital_hilton_required_result"]["protected_proof_required"] is True


def test_package_map_slice_carries_source_refs_and_excludes_blocked_context(tmp_path):
    rule = _build(tmp_path)["package_map_slice_rule"]

    assert rule["map_slice_ref"] == "openclaw_map_snapshot.capital_hilton_proof_metadata"
    assert "generated/read_models/capital_hilton_proof_metadata_packet.json" in rule["source_read_model_refs"]
    assert "generated/read_models/package_preview_receipt_contract.json" in rule["source_read_model_refs"]
    assert "stable_map_current_but_not_source_truth" == rule["freshness_status"]
    assert "dates" in rule["candidate_claims"]
    assert "send/submit/approval authority" in rule["excluded_context"]
    assert "credentials/tokens/cookies/API keys" in rule["excluded_context"]
    assert rule["authority_boundary"]["send_submit_approval_allowed"] is False


def test_operator_answers_are_memory_candidates_not_proof(tmp_path):
    payload = _build(tmp_path)
    answers = payload["operator_answer_capture_contract"]

    assert len(answers) == 7
    assert set(payload["allowed_answer_modalities"]) == set(packet.ANSWER_MODALITIES)
    assert set(payload["question_classes"]) == set(packet.QUESTION_CLASSES)
    for answer in answers:
        assert answer["memory_candidate_receipt_required"] is True
        assert answer["proof_required_after_answer"] is True
        assert "does not become machine proof" in answer["what_happens_when_answered"]
        assert answer["status"] == "UNANSWERED"
    assert payload["question_quieting_rule"]["question_states"] == list(packet.QUESTION_STATES)
    assert "proof gaps stay visible" in payload["question_quieting_rule"]["active_helm_removal_rule"]


def test_shared_execution_path_consolidates_capital_hilton_protected_finance_proof(tmp_path):
    paths = _shared_paths(_build(tmp_path))
    protected = paths["protected_finance_proof_metadata_intake"]

    assert set(paths) == {
        "protected_finance_proof_metadata_intake",
        "operator_memory_question_capture",
        "stable_map_receipt_readback",
    }
    assert "capital_hilton" in protected["linked_lanes"]
    assert "Finance" in protected["linked_worlds"]
    assert protected["required_proof"] == list(packet.CAPITAL_HILTON_PROOF_IDS)
    assert "Guardian protected access gate" in protected["required_gates"]
    assert protected["authority_boundary"]["coupa_access_allowed"] is False
    assert "Coupa access" in protected["blocked_actions"]
    assert "Capital Hilton security-readiness posture" in protected["what_solving_this_updates"]


def test_helm_issue_focus_mode_exists_without_live_action_controls(tmp_path):
    payload = _build(tmp_path)
    focus_modes = {item["issue_focus_id"]: item for item in payload["helm_issue_focus_modes"]}
    capital = focus_modes["focus_capital_hilton_missing_proof"]

    assert len(focus_modes) == 3
    assert capital["issue_type"] == "PROOF_GAP_ISSUE"
    assert capital["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
    assert "missing proof checklist" in capital["visible_when_selected"]
    assert "live dispatch controls" in capital["hidden_when_selected"]
    assert "tool execution controls" in capital["hidden_when_selected"]
    assert "send/submit/approval controls" in capital["hidden_when_selected"]
    assert "protected proof metadata intake" in capital["future_gated_actions"]


def test_helm_world_boundary_avoids_developer_domain_bifurcation(tmp_path):
    boundary = _build(tmp_path)["helm_world_responsibility_boundary"]

    assert "system health" in boundary["helm_owns"]
    assert "proof gaps" in boundary["helm_owns"]
    assert "domain context" in boundary["worlds_own"]
    assert "eventual domain work after security gates" in boundary["worlds_own"]
    assert "10 missing proof items" in boundary["capital_hilton_helm_owns"]
    assert "Capital Hilton preview" in boundary["finance_world_may_show"]
    assert boundary["authority_boundary"]["runtime_dispatch_allowed"] is False


def test_capital_hilton_security_readiness_is_not_action_readiness(tmp_path):
    payload = _build(tmp_path)
    readiness = payload["capital_hilton_security_readiness"]

    assert readiness["missing_proof_count"] == 10
    assert readiness["protected_proof_required"] is True
    assert readiness["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
    assert readiness["candidate_facts_proven"] is False
    assert readiness["finance_world_preview_exists"] is True
    assert readiness["security_pass_complete"] is False
    assert readiness["action_authority_granted"] is False
    assert "security approval not granted" in readiness["what_blocks_action_readiness"]
    assert payload["capital_hilton_current_stable_map_posture"]["candidate_facts_are_not_machine_proven"] is True


def test_no_raw_private_bodies_credentials_or_app_changes_are_included(tmp_path):
    payload = _build(tmp_path)
    rendered = packet.stable_json(payload).lower()

    assert payload["machine_proof"]["raw_private_body_included"] is False
    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["mission_control_app_changes_included"] is False
    assert payload["mac_sync_or_import_triggered"] is False
    assert payload["repo_b_body_inspection_allowed"] is False
    assert "raw_secret_value" not in rendered
    assert ("api" + "_key=") not in rendered


def test_stable_map_integration_is_standalone_until_refresh(tmp_path):
    stable = _build(tmp_path)["stable_map_integration"]

    assert stable["contract_generated_as_read_model"] is True
    assert stable["summary_included_in_stable_map_now"] is False
    assert stable["next_map_bundle_refresh_requirement"] == "Next stable-map refresh should include Security Audit Readiness Packet Pass 1 + Pass 2 summary."
    assert stable["safe_summary_for_next_refresh"]["security_approval_granted"] is False
    assert stable["safe_summary_for_next_refresh"]["live_authority_added"] is False
    assert stable["safe_summary_for_next_refresh"]["coverage_gap_records"] == 5
    assert stable["safe_summary_for_next_refresh"]["parked_breadcrumb_records"] == 15
    assert stable["safe_summary_for_next_refresh"]["ready_for_security_pass"] is True


def test_coverage_gap_registry_records_passive_unmapped_terrain(tmp_path):
    registry = _build(tmp_path)["coverage_gap_unmapped_terrain_registry"]
    records = {item["coverage_item_id"]: item for item in registry["records"]}

    assert set(records) == {
        "markdown_document_terrain",
        "tagging_system_capability",
        "mission_control_visibility_gap",
        "operator_memory_gap",
        "repo_terrain_gap",
    }
    assert registry["coverage_statuses"] == list(packet.COVERAGE_STATUSES)
    assert registry["safety_rule"]["tagging_implemented"] is False
    assert registry["safety_rule"]["markdown_files_organized"] is False
    assert registry["safety_rule"]["broad_directory_scan_performed"] is False
    assert registry["safety_rule"]["file_move_delete_rewrite_allowed"] is False
    assert registry["safety_rule"]["raw_body_inspection_allowed"] is False
    assert registry["safety_rule"]["repo_b_mutation_allowed"] is False

    markdown = records["markdown_document_terrain"]
    assert markdown["current_mapping_status"] == "IN_TERRAIN_NOT_CLASSIFIED"
    assert markdown["example_only"] is True
    assert markdown["classification_needed"] is True
    assert markdown["promotion_needed"] is False
    assert "do not move files or inspect broad bodies" in markdown["recommended_next_detour"]
    assert markdown["what_would_make_it_mapped"].startswith("A source-card")

    tagging = records["tagging_system_capability"]
    assert tagging["current_mapping_status"] == "NEEDS_SOURCE_CARD"
    assert tagging["proof_status"] == "needs_source_card"
    visibility = records["mission_control_visibility_gap"]
    assert visibility["current_mapping_status"] == "IN_READ_MODEL_NOT_IN_APP"
    assert visibility["app_surface_needed"] is True
    operator_memory = records["operator_memory_gap"]
    assert operator_memory["current_mapping_status"] == "OPERATOR_REPORTED_NOT_PROVEN"
    assert operator_memory["proof_status"] == "memory_candidate_not_proof"
    repo_gap = records["repo_terrain_gap"]
    assert repo_gap["current_mapping_status"] == "IN_TERRAIN_NOT_CLASSIFIED"
    assert "no broad Repo B body inspection" in repo_gap["recommended_next_detour"]


def test_parked_breadcrumb_review_preserves_all_known_breadcrumbs_without_execution(tmp_path):
    review = _build(tmp_path)["parked_breadcrumb_review"]
    records = {item["breadcrumb_id"]: item for item in review["records"]}

    assert set(records) == set(packet.PARKED_BREADCRUMB_IDS)
    assert len(records) == 15
    assert review["review_states"] == list(packet.PARKED_BREADCRUMB_REVIEW_STATES)
    assert review["safety_rule"]["schedules_created"] is False
    assert review["safety_rule"]["queue_tasks_created"] is False
    assert review["safety_rule"]["background_jobs_created"] is False
    assert review["safety_rule"]["trigger_engine_created"] is False
    assert review["safety_rule"]["auto_promotion_allowed"] is False
    assert review["safety_rule"]["execution_authority_created"] is False
    for record in records.values():
        assert record["status"] in packet.PARKED_BREADCRUMB_REVIEW_STATES
        assert record["queue_or_trigger_created"] is False
        assert record["auto_promotion_allowed"] is False
        assert record["execution_authority_created"] is False
        assert record["still_relevant"] is True

    assert records["operator_attention_promotion_contract_v0"]["status"] == "PROMOTE_TO_SECURITY_AUDIT_ITEM"
    assert records["operator_sleep_mode_queue_priority_posture"]["status"] == "KEEP_PARKED"
    assert records["chief_test_harness_receipt"]["relevance_phase"] == "during_security_pass"
    assert records["world_graduation_rules"]["status"] == "MERGE_WITH_EXISTING_LANE"
    assert records["compromise_suspicion_kill_switch_posture"]["status"] == "PROMOTE_TO_SECURITY_AUDIT_ITEM"


def test_security_pass_readiness_criteria_are_present_without_action_readiness(tmp_path):
    criteria = _build(tmp_path)["security_pass_readiness_criteria"]

    assert criteria["all_stable_map_claims_have_provenance_or_candidate_status"] is True
    assert criteria["all_packages_enforce_map_slice_rules"] is True
    assert criteria["all_active_questions_linked_to_lanes"] is True
    assert criteria["operator_answer_capture_schema_present"] is True
    assert criteria["question_quieting_model_present"] is True
    assert criteria["shared_execution_paths_present"] is True
    assert criteria["helm_issue_focus_mode_present"] is True
    assert criteria["coverage_gap_registry_present"] is True
    assert criteria["parked_breadcrumb_review_present"] is True
    assert criteria["all_authority_flags_strictly_false"] is True
    assert criteria["zero_execution_authority_leaked"] is True
    assert criteria["raw_private_bodies_excluded"] is True
    assert criteria["credentials_and_account_access_blocked"] is True
    assert criteria["guardian_operator_gates_identified"] is True
    assert criteria["hidden_automation_absent"] is True
    assert criteria["ready_for_security_pass"] is True
    assert criteria["security_pass_readiness_is_not_action_readiness"] is True
    assert criteria["security_approval_granted"] is False
    assert criteria["action_authority_granted"] is False
    assert "Coupa access" in criteria["remaining_action_blockers"]


def test_worker_policy_breadcrumb_preserves_bounded_subagent_policy_without_automation(tmp_path):
    payload = _build(tmp_path)
    policies = payload["worker_policy_breadcrumbs"]
    records = {item["policy_id"]: item for item in policies["records"]}
    policy = records["bounded_subagent_use_policy"]

    assert policy["display_name"] == "Bounded Subagent Use Policy"
    assert policy["status"] == "ACTIVE_PROMPTING_POLICY_NOT_IMPLEMENTATION"
    assert "read-only codebase/schema inspection" in policy["allowed_subagent_uses"]
    assert "overlapping writes" in policy["disallowed_subagent_uses"]
    assert "authority decisions" in policy["disallowed_subagent_uses"]
    assert "One main worker owns the final patch" in policy["owner_rule"]
    assert policy["current_task_rule"] == "No subagents are authorized or used for this receipt/readback lane."
    assert policy["not_authorized"]["subagents_launched"] is False
    assert policy["not_authorized"]["subagent_implementation_created"] is False
    assert policy["not_authorized"]["automation_created"] is False
    assert policy["not_authorized"]["queue_behavior_created"] is False
    assert policy["not_authorized"]["tool_model_agent_authority_granted"] is False
    assert policy["not_authorized"]["current_task_execution_changed"] is False


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    _fixture_repo(tmp_path)

    result = export_main(["--repo-root", tmp_path.as_posix(), "--export-root", "generated/read_models", "--format", "summary"])

    assert result == 0
    exported_json = tmp_path / "generated" / "read_models" / packet.JSON_EXPORT_NAME
    exported_md = tmp_path / "generated" / "read_models" / packet.OPERATOR_EXPORT_NAME
    payload = json.loads(exported_json.read_text(encoding="utf-8"))
    operator = exported_md.read_text(encoding="utf-8")
    assert payload["schema_version"] == packet.SCHEMA_VERSION
    assert payload["capital_hilton_security_readiness"]["missing_proof_count"] == 10
    assert payload["coverage_gap_unmapped_terrain_registry"]["records"]
    assert len(payload["parked_breadcrumb_review"]["records"]) == 15
    assert payload["security_pass_readiness_criteria"]["ready_for_security_pass"] is True
    assert "ELI5 Summary" in operator
    assert "ELIWINSHIP / operator-native orientation" in operator
    assert "Map-To-Terrain Provenance" in operator
    assert "Operator Answer Capture" in operator
    assert "Helm Issue Focus Mode" in operator
    assert "Coverage Gap / Unmapped Terrain" in operator
    assert "Parked Breadcrumb Review" in operator
    assert "Worker Policy Breadcrumbs" in operator
    assert "Bounded Subagent Use Policy" in operator
    assert "Security Pass Readiness Criteria" in operator
    assert "security_approval_granted" in operator
