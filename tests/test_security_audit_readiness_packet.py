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
    assert first["contract_status"] == "deterministic_security_audit_readiness_pass_1_metadata_only"
    assert first["machine_proof"]["pass_2_included"] is False
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
    assert stable["next_map_bundle_refresh_requirement"] == "Next stable-map refresh should include Security Audit Readiness Packet Pass 1 summary."
    assert stable["safe_summary_for_next_refresh"]["security_approval_granted"] is False
    assert stable["safe_summary_for_next_refresh"]["live_authority_added"] is False


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
    assert "ELI5 Summary" in operator
    assert "Map-To-Terrain Provenance" in operator
    assert "Operator Answer Capture" in operator
    assert "Helm Issue Focus Mode" in operator
    assert "security_approval_granted" in operator
