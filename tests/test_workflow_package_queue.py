import json
import sqlite3
from pathlib import Path

import pytest

import workflow_package_queue as queue


FIXED_NOW = "2026-06-01T23:10:00+00:00"


def _package(text: str, **kwargs):
    return queue.create_package(text, created_at=FIXED_NOW, **kwargs)


def _sentence_count(text: str) -> int:
    return sum(1 for char in text if char in ".?!")


def _assert_compact_display(display):
    assert len(display["headline"].split()) <= 8
    assert _sentence_count(display["plain_summary"]) <= 1
    assert _sentence_count(display["next_safe_action"]) <= 1
    assert display["proof_caption"] == "Proof available."
    assert display["show_machine_details_by_default"] is False
    assert display["why_it_matters"]
    assert isinstance(display["secondary_facts"], list)


def test_st_annes_work_log_instruction_stages_record_only_package():
    package = _package("Mark that I'm at church running sound.")
    display = package["operator_display"]

    assert package["workflow_ref"] == "st_annes_work_log_event"
    assert package["client_ref"] == "st_annes"
    assert package["status"] == "OPERATOR_REVIEW_REQUIRED"
    assert display["headline"] == "St. Anne's work log captured"
    assert display["speaker_ref"] == "cassandra"
    assert display["voice_profile_ref"] == "agent_voice_profile:cassandra"
    assert display["voice_mode"] == "operator_intake"
    assert display["audience"] == "internal_operator"
    assert display["routing_reason"] == "work-log intake"
    assert display["status_label"] == "Needs confirmation"
    assert display["tone"] == "warning"
    assert display["plain_summary"] == "Saved as a draft event until you confirm it."
    assert display["next_safe_action"] == "Confirm or discard."
    _assert_compact_display(display)
    assert "st_annes_work_log_event" not in display["headline"]
    assert display["show_machine_details_by_default"] is False
    assert package["capability_gate_result"]["status"] == "ALLOW_DRY_RUN"
    assert package["authority_boundary"]["workbook_source_mutation_allowed"] is False
    assert package["authority_boundary"]["email_send_allowed"] is False
    assert package["authority_boundary"]["ledger_posting_allowed"] is False
    assert package["worker_result"]["workbook_mutation_performed"] is False
    assert package["worker_result"]["email_send_performed"] is False
    assert package["worker_result"]["ledger_mutation_performed"] is False
    assert package["source_text_ref"].startswith("protected_text_hash:sha256:")
    assert package["privacy_impact"]["raw_text_stored"] is False


def test_st_annes_invoice_send_blocks_before_permission_or_artifact():
    package = _package("Send St. Anne's invoice.")

    assert package["workflow_ref"] == "st_annes_monthly_invoice_rollup"
    assert package["client_ref"] == "st_annes"
    assert package["status"] == "PERMISSION_REQUIRED"
    assert package["capability_gate_result"]["status"] == "PERMISSION_REQUIRED"
    assert package["worker_result"]["result_status"] == "NOOP_BLOCKED_BY_GATE"
    assert package["business_action_gate_result"]["status"] == "CLOSED"
    assert package["business_action_gate_result"]["email_send_allowed"] is False
    assert package["business_action_gate_result"]["sent"] is False


def test_st_annes_invoice_send_blocks_for_artifact_when_permission_ready():
    package = _package(
        "Send St. Anne's invoice.",
        config=queue.QueueConfig(st_annes_send_permission_ready=True),
    )

    assert package["status"] == "ARTIFACT_REQUIRED"
    assert package["capability_gate_result"]["status"] == "ARTIFACT_REQUIRED"
    assert "email_send" in package["capability_gate_result"]["blocked_actions"]


def test_st_annes_invoice_dry_run_has_real_source_inventory_and_pdf_first_proof():
    package = _package(
        "Send St. Anne's invoice.",
        config=queue.QueueConfig(
            st_annes_send_permission_ready=True,
            st_annes_approved_pdf_artifact_available=True,
        ),
    )

    assert package["status"] == "OPERATOR_REVIEW_REQUIRED"
    assert package["capability_gate_result"]["status"] == "ALLOW_DRY_RUN"
    assert package["project_room_ready"] is True
    assert package["synthesis_allowed"] is True
    assert "source_inventory_missing" not in package["project_room_gate_result"]["blockers"]
    assert not package["project_room_gate_result"]["missing_project_room_refs"]

    source_room = package["source_room_context"]
    assert source_room["source_inventory_exists"] is True
    assert source_room["source_inventory_ref"] == "source_inventory:st_annes_monthly_invoice_rollup"
    assert source_room["conflict_log_ref"] == "conflict_log:st_annes_monthly_invoice_rollup"
    assert source_room["duplicate_report_ref"] == "duplicate_report:st_annes_monthly_invoice_rollup"
    assert source_room["decision_trace_ref"] == "decision_trace:st_annes_monthly_invoice_rollup"
    assert source_room["dry_run_artifact_order"] == ["pdf_proof", "clara_draft", "guardian_gate"]
    source_refs = {row["source_ref"] for row in source_room["source_inventory"]["sources"]}
    assert "generated/read_models/st_annes_work_log_events.json" in source_refs
    assert "generated/system_knowledge/st_annes_invoice_status_SEED.sql" in source_refs
    assert any(row["artifact_kind"] == "operator_provided_pdf_invoice" for row in source_room["source_inventory"]["sources"])
    assert source_room["source_inventory"]["machine_proof"]["derived_from_existing_files"] is True
    assert package["worker_result"]["live_worker_executed"] is False
    assert package["worker_result"]["pdf_export_performed"] is False
    assert package["worker_result"]["email_send_performed"] is False


def test_st_annes_source_inventory_flag_fails_closed_when_required_source_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(queue, "DEFAULT_EXPORT_ROOT", tmp_path / "missing_read_models")
    context = queue._source_room_context_for_workflow("st_annes_monthly_invoice_rollup")

    assert context["source_inventory_exists"] is False
    assert context["missing_source_refs"]


def test_capital_hilton_proposal_followup_is_business_development_no_invoice_or_send():
    package = _package("Follow up on Capital Hilton proposal.")
    display = package["operator_display"]

    assert package["workflow_ref"] == "capital_hilton_proposal_followup"
    assert package["world"] == "business_development"
    assert package["client_ref"] == "capital_hilton"
    assert package["status"] == "OPERATOR_REVIEW_REQUIRED"
    assert display["headline"] == "Proposal follow-up staged"
    assert display["speaker_ref"] == "cassandra"
    assert display["voice_profile_ref"] == "agent_voice_profile:cassandra"
    assert display["voice_mode"] == "operator_calm"
    assert display["audience"] == "internal_operator"
    assert display["routing_reason"] == "human-layer coordination or correspondence prep"
    assert display["status_label"] == "Needs review"
    assert display["tone"] == "calm"
    assert "capital_hilton_proposal_followup" not in display["headline"]
    assert display["plain_summary"] == "No email will be sent until approved."
    assert display["next_safe_action"] == "Review the follow-up."
    _assert_compact_display(display)
    assert package["business_action_gate_result"]["email_send_allowed"] is False
    assert package["authority_boundary"]["email_send_allowed"] is False
    assert package["authority_boundary"]["ledger_posting_allowed"] is False
    assert "invoice_creation" in package["capability_gate_result"]["blocked_actions"]


def test_capital_hilton_invoice_submit_requires_operator_assist_provider_and_submit_gate():
    package = _package("Submit Capital Hilton invoice.")
    display = package["operator_display"]

    assert package["workflow_ref"] == "capital_hilton_invoice_operator_assist"
    assert package["client_ref"] == "capital_hilton"
    assert package["status"] == "PROVIDER_GATE_REQUIRED"
    assert display["headline"] == "Capital Hilton needs operator assist"
    assert display["speaker_ref"] == "chief"
    assert display["voice_profile_ref"] == "agent_voice_profile:chief"
    assert display["voice_mode"] == "diagnostic"
    assert display["audience"] == "internal_operator"
    assert display["routing_reason"] == "provider gate required"
    assert display["status_label"] == "Provider gate required"
    assert display["tone"] == "blocked"
    assert "capital_hilton_invoice_operator_assist" not in display["headline"]
    assert display["plain_summary"] == "Coupa cannot run unattended."
    assert display["next_safe_action"] == "Stage an operator-assist packet."
    _assert_compact_display(display)
    assert package["capability_gate_result"]["status"] == "PROVIDER_GATE_REQUIRED"
    assert "coupa_submit" in package["capability_gate_result"]["blocked_actions"]
    assert package["worker_result"]["coupa_access_performed"] is False
    assert package["worker_result"]["submit_performed"] is False


def test_each_package_carries_privacy_redundancy_evaluator_fields():
    package = _package("Follow up on Capital Hilton proposal.")
    evaluator = package["privacy_redundancy_evaluator"]

    assert evaluator["provider_considered"] == "local_noop_worker"
    assert evaluator["data_exposure_class"] == "local_instruction_metadata"
    assert evaluator["local_alternative"] == "deterministic_local_classifier_and_sqlite_registry"
    assert evaluator["final_provider_decision"] == "local_only_noop_worker"
    assert evaluator["approval_required"] is True


def test_sqlite_registry_persists_all_required_gate_rows(tmp_path):
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    packages = [
        _package("Mark that I'm at church running sound."),
        _package("Send St. Anne's invoice."),
        _package("Follow up on Capital Hilton proposal."),
        _package("Submit Capital Hilton invoice."),
    ]

    queue.record_packages(sqlite_path, packages)

    conn = sqlite3.connect(sqlite_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "packages",
            "package_inputs",
            "privacy_gate_results",
            "intent_classification_results",
            "capability_gate_results",
            "worker_assignments",
            "worker_results",
            "operator_review_receipts",
            "business_action_gate_results",
        }.issubset(tables)
        for table in (
            "packages",
            "package_inputs",
            "privacy_gate_results",
            "intent_classification_results",
            "capability_gate_results",
            "worker_assignments",
            "worker_results",
            "operator_review_receipts",
            "business_action_gate_results",
        ):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == len(packages)
        rows = conn.execute(
            "SELECT email_send_allowed, ledger_posting_allowed, coupa_allowed, paid, sent "
            "FROM business_action_gate_results"
        ).fetchall()
        assert rows
        assert all(row == (0, 0, 0, 0, 0) for row in rows)
    finally:
        conn.close()


def test_export_writes_contract_read_model_wiki_bridge_and_sqlite(tmp_path):
    result = queue.export_workflow_package_queue(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Workflow Package Queue.md",
        sqlite_path=tmp_path / "system_knowledge" / "workflow_package_queue.sqlite",
        generated_at=FIXED_NOW,
    )

    read_model = json.loads(Path(result.read_model_path).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result.bridge_read_model_path).read_text(encoding="utf-8"))
    assert read_model == bridge
    assert read_model["status"] == "WORKFLOW_PACKAGE_QUEUE_V0_READY"
    assert read_model["supported_package_types"] == list(queue.SUPPORTED_PACKAGE_TYPES)
    assert "operator_display" in read_model["package_field_contract"]
    assert read_model["operator_display_schema"] == list(queue.OPERATOR_DISPLAY_FIELDS)
    assert "voice_profile_ref" in read_model["operator_display_schema"]
    assert "routing_reason" in read_model["operator_display_schema"]
    assert read_model["agent_voice_routing_contract_ref"] == "generated/read_models/agent_voice_routing_contract.json"
    assert len(read_model["packages"]) == 5
    assert all("operator_display" in package for package in read_model["packages"])
    assert Path(result.wiki_path).exists()
    assert Path(result.sqlite_path).exists()

    conn = sqlite3.connect(result.sqlite_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 5
        statuses = {
            row[0]
            for row in conn.execute("SELECT status FROM capability_gate_results")
        }
        assert {"ALLOW_DRY_RUN", "PERMISSION_REQUIRED", "PROVIDER_GATE_REQUIRED"}.issubset(statuses)
    finally:
        conn.close()


@pytest.mark.parametrize(
    "text,workflow_ref",
    [
        ("Mark that I'm at church running sound.", "st_annes_work_log_event"),
        ("Send St. Anne's invoice.", "st_annes_monthly_invoice_rollup"),
        ("Follow up on Capital Hilton proposal.", "capital_hilton_proposal_followup"),
        ("Submit Capital Hilton invoice.", "capital_hilton_invoice_operator_assist"),
        ("Run diagnostic package gate smoke.", "diagnostic_package_gate_smoke"),
    ],
)
def test_intent_classifier_supported_package_types(text, workflow_ref):
    assert queue.classify_intent(text)["workflow_ref"] == workflow_ref
