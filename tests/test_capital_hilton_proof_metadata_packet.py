import json
from pathlib import Path

import capital_hilton_proof_metadata_packet as packet
from scripts.export_capital_hilton_proof_metadata_packet import main as export_main


FIXED_NOW = "2026-05-22T06:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "capital_hilton_actionable_review_packet.json": {
            "schema_version": "capital_hilton_actionable_review_packet_v1",
            "read_model_id": "capital_hilton_actionable_review_packet",
            "domain_fact_summary": {
                "completed_service_dates": ["2026-05-08", "2026-05-15"],
                "rate_or_amount_per_gig": "$400 per gig",
                "candidate_subtotal": "$800 for the two completed governed service-date facts",
                "invoice_count_posture": "one invoice for 2026-05-15 and 2026-05-08",
                "po_or_portal_gate_status": "must_confirm_po_and_credit_in_coupa_before_final_submission",
                "recipient_posture_review_only": True,
            },
            "invoice_facts": [
                {
                    "field_name": "invoice_attachment_output_path",
                    "value_text": "workbook reference metadata only; no spreadsheet cells read",
                    "evidence_status": "parsed_evidence_not_truth",
                }
            ],
        },
        "cassandra_governed_review_packet_request_proof.json": {
            "schema_version": "cassandra_governed_review_packet_request_proof_v0",
            "read_model_id": "cassandra_governed_review_packet_request_proof",
        },
        "capital_hilton_coupa_execution_path.json": {
            "schema_version": "capital_hilton_coupa_execution_path_v0",
            "read_model_id": "capital_hilton_coupa_execution_path",
        },
        "capital_hilton_external_artifact_proof_capture.json": {
            "schema_version": "capital_hilton_external_artifact_proof_capture_v0",
            "read_model_id": "capital_hilton_external_artifact_proof_capture",
        },
        "agent_identity_actor_router_contract.json": {"schema_version": "agent_identity_actor_router_contract_v0"},
        "agent_package_preview_contract.json": {"schema_version": "agent_package_preview_contract_v0"},
        "package_preview_receipt_contract.json": {"schema_version": "package_preview_receipt_contract_v0"},
        "model_selection_receipt_contract.json": {"schema_version": "model_selection_receipt_contract_v0"},
        "tool_adapter_receipt_contract.json": {"schema_version": "tool_adapter_receipt_contract_v0"},
        "memory_candidate_receipt_contract.json": {"schema_version": "memory_candidate_receipt_contract_v0"},
        "agent_memory_scope_contract.json": {"schema_version": "agent_memory_scope_contract_v0"},
        "tool_protocol_adapter_registry_contract.json": {"schema_version": "tool_protocol_adapter_registry_contract_v0"},
        "agent_terrain_awareness_readback_contract.json": {"schema_version": "agent_terrain_awareness_readback_contract_v0"},
        "openclaw_map_manifest.json": {"schema_version": "openclaw_map_manifest_v0"},
        "operator_threshold_map_contract.json": {"schema_version": "operator_threshold_map_contract_v0"},
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return packet.build_capital_hilton_proof_metadata_packet(repo_root=tmp_path, generated_at=FIXED_NOW)


def _facts(payload: dict) -> dict:
    return {item["fact_id"]: item for item in payload["capital_hilton_candidate_facts"]}


def _proof_records(payload: dict) -> dict:
    return {item["proof_metadata_id"]: item for item in payload["required_proof_metadata"]}


def test_packet_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert packet.stable_json(first) == packet.stable_json(second)
    assert first["schema_version"] == packet.SCHEMA_VERSION
    assert first["read_model_id"] == "capital_hilton_proof_metadata_packet"
    assert first["contract_status"] == "deterministic_capital_hilton_proof_metadata_only"
    assert first["coupa_access_allowed"] is False
    assert first["browser_oauth_allowed"] is False
    assert first["credential_handling_allowed"] is False
    assert first["gmail_calendar_access_allowed"] is False
    assert first["excel_raw_body_ingestion_allowed"] is False
    assert first["raw_finance_body_ingestion_allowed"] is False
    assert first["invoice_generation_allowed"] is False
    assert first["send_submit_approval_allowed"] is False
    assert first["model_call_allowed"] is False
    assert first["tool_execution_allowed"] is False
    assert first["agent_activation_allowed"] is False
    assert first["operator_final_authority"] is True
    assert first["machine_proof"]["all_authority_flags_false_except_operator_final"] is True


def test_lane_fact_posture_keeps_capital_hilton_in_helm_until_proof_and_gates(tmp_path):
    payload = _build(tmp_path)
    lane = payload["capital_hilton_lane_fact_posture"]

    assert lane["lane_id"] == "capital_hilton"
    assert lane["current_phase"] == "HELM_THRESHOLD_LANE"
    assert lane["target_world"] == "Finance"
    assert lane["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert lane["workflow_type"] == "invoice_review_and_proof_metadata"
    assert lane["security_audit_readiness"] == "not_ready_until_missing_proof_metadata_and_gates_are_defined"
    assert lane["finance_world_action_readiness"] == "not_actionable_until_security_audit_and_proof_metadata_pass"
    assert "PO/Coupa/payment reference" in lane["known_unknown"]
    assert "Guardian-approved protected proof metadata" in lane["not_discovered"]
    assert payload["finance_world_transition_policy"]["transition_allowed_now"] is False
    assert payload["finance_world_transition_policy"]["target_lane_state"] == "FINANCE_WORLD_ACTIONABLE_LANE"


def test_candidate_dates_rate_and_subtotal_are_not_marked_proven_without_proof_refs(tmp_path):
    facts = _facts(_build(tmp_path))

    assert facts["completed_performance_dates"]["current_value"] == ["2026-05-08", "2026-05-15"]
    assert facts["rate"]["current_value"] == "$400 per gig"
    assert facts["subtotal"]["current_value"] == "$800 for the two completed governed service-date facts"
    assert facts["invoice_shape_one_invoice_posture"]["current_value"] == "one invoice for 2026-05-15 and 2026-05-08"
    for fact_id in ["completed_performance_dates", "rate", "subtotal", "invoice_shape_one_invoice_posture"]:
        assert facts[fact_id]["proof_category"] == "CANDIDATE_FACT"
        assert facts[fact_id]["proof_status"] == "CANDIDATE_FACT_NOT_PROVEN"
        assert facts[fact_id]["machine_proven"] is False
        assert facts[fact_id]["raw_body_included"] is False
        assert facts[fact_id]["operator_confirmation_required"] is True
    assert facts["po_coupa_reference"]["protected_proof_required"] is True
    assert facts["service_performance_description"]["current_status"] == "missing_proof"


def test_required_proof_metadata_records_cover_finance_steel_thread(tmp_path):
    payload = _build(tmp_path)
    records = _proof_records(payload)

    assert set(records) == {
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
    for record in records.values():
        assert record["current_proof_present"] is False
        assert record["raw_body_included"] is False
        assert "raw body ingestion" in record["blocked_now"]
    assert records["coupa_po_or_payment_reference_metadata"]["protected_proof_required"] is True
    assert records["excel_workbook_reference_metadata"]["raw_body_policy"] == "raw Excel body and workbook parsing blocked"
    assert records["guardian_protected_access_gate_metadata"]["guardian_gate_required"] is True
    assert records["operator_confirmation_metadata"]["source_expectation"] == "Memory Candidate Receipt, not machine proof by itself"
    assert records["future_invoice_generation_receipt_requirement"]["required_for_finance_world_action"] is True
    assert payload["machine_proof"]["protected_proof_required"] is True
    assert payload["machine_proof"]["missing_proof_count"] == len(records)


def test_actor_package_adapter_binding_is_preview_only_and_future_gated(tmp_path):
    binding = _build(tmp_path)["actor_package_adapter_binding"]
    actors = {item["actor_id"]: item for item in binding["actors_personas"]}
    adapters = {item["adapter_id"]: item for item in binding["tool_adapter_posture"]}

    assert actors["cassandra"]["role"] == "finance/comms/AP preview and packet review"
    assert "Coupa access" in actors["cassandra"]["current_blocked"]
    assert "raw Gmail/calendar bodies" in actors["cassandra"]["current_blocked"]
    assert actors["guardian"]["role"] == "protected proof / redaction / access gate"
    assert actors["operator_winship"]["role"] == "final action authority and memory clarification"
    assert actors["finance_world"]["current_blocked"] == ["invoice execution before proof and security audit"]
    assert "package_preview_receipt_contract" in binding["package_references"]
    assert "model_selection_receipt_contract" in binding["package_references"]
    assert "memory_candidate_receipt_contract" in binding["package_references"]
    assert "tool_adapter_receipt_contract" in binding["package_references"]
    assert adapters["cassandra_capital_hilton_invoice_proof_adapter"]["posture"] == "future_gated"
    assert adapters["coupa_adapter"]["current_authority"] is False
    assert adapters["excel_workbook_proof_adapter"]["posture"] == "metadata_candidate_only"
    assert adapters["package_preview_exporter"]["posture"] == "preview_only"
    assert adapters["stable_map_reader"]["posture"] == "read_only"


def test_operator_questions_are_memory_candidates_not_proof(tmp_path):
    questions = _build(tmp_path)["operator_memory_questions"]
    classifications = {item["classification"] for item in questions}

    assert len(questions) == 7
    assert classifications <= set(packet.OPERATOR_QUESTION_CLASSIFICATIONS)
    assert "memory_only_clarification" in classifications
    assert "proof_needed" in classifications
    assert "protected_proof_needed" in classifications
    assert "security_gate_needed" in classifications
    assert "world_transition_needed" in classifications
    assert all(question["answer_becomes"] == "memory_candidate_receipt" for question in questions)
    assert all(question["answer_is_machine_proof"] is False for question in questions)


def test_security_audit_readiness_is_not_finance_world_action_readiness(tmp_path):
    payload = _build(tmp_path)
    security = payload["security_audit_readiness"]
    transition = payload["finance_world_transition_policy"]

    assert security["ready_for_security_audit"] is False
    assert security["ready_for_finance_world_action"] is False
    assert security["security_audit_readiness_is_not_action_readiness"] is True
    assert "protected proof metadata identified" in security["readiness_requires"]
    assert "no live execution authority" in security["readiness_requires"]
    assert transition["transition_allowed_now"] is False
    assert "proof metadata exists for date/rate/subtotal/customer/payment route as required" in transition["transition_requires"]
    assert "No invoice execution" in transition["until_then"]


def test_context_boundaries_and_stable_map_integration_are_explicit(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["authority_boundary"]
    stable_map = payload["stable_map_integration"]

    assert boundary["coupa_access_allowed"] is False
    assert boundary["browser_oauth_allowed"] is False
    assert boundary["credential_handling_allowed"] is False
    assert boundary["gmail_calendar_access_allowed"] is False
    assert boundary["excel_raw_body_ingestion_allowed"] is False
    assert boundary["raw_finance_body_ingestion_allowed"] is False
    assert boundary["invoice_generation_allowed"] is False
    assert boundary["send_submit_approval_allowed"] is False
    assert boundary["model_call_allowed"] is False
    assert boundary["tool_execution_allowed"] is False
    assert boundary["agent_activation_allowed"] is False
    assert "raw finance/private body ingestion" in boundary["blocked_current_actions"]
    assert stable_map["contract_generated_as_read_model"] is True
    assert stable_map["summary_included_in_stable_map_now"] is False
    assert stable_map["safe_summary_for_next_refresh"]["target_world"] == "Finance"
    assert stable_map["safe_summary_for_next_refresh"]["protected_proof_required"] is True


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    _fixture_repo(tmp_path)

    result = export_main(["--repo-root", tmp_path.as_posix(), "--export-root", "generated/read_models", "--format", "summary"])

    assert result == 0
    exported_json = tmp_path / "generated" / "read_models" / packet.JSON_EXPORT_NAME
    exported_md = tmp_path / "generated" / "read_models" / packet.OPERATOR_EXPORT_NAME
    payload = json.loads(exported_json.read_text(encoding="utf-8"))
    operator = exported_md.read_text(encoding="utf-8")
    assert payload["schema_version"] == packet.SCHEMA_VERSION
    assert payload["capital_hilton_lane_fact_posture"]["target_world"] == "Finance"
    assert "ELI5 Summary" in operator
    assert "Missing Proof Checklist" in operator
    assert "Operator Memory Questions" in operator
    assert "coupa_access_allowed" in operator
