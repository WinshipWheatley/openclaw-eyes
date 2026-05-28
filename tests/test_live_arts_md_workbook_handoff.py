import json

import live_arts_md_workbook_handoff as handoff
import invoice_review_action_request_handler as action_handler
from scripts.export_live_arts_md_invoice_candidate_register import main as export_main


FIXED_NOW = "2026-05-28T18:00:00+00:00"


def test_operator_handoff_receipt_marks_facts_operator_provided_not_workbook_parsed():
    receipt = handoff.build_handoff_receipt(generated_at=FIXED_NOW)

    assert receipt["receipt_event"] == "operator_provided_live_arts_md_workbook_handoff"
    assert receipt["client_ref"] == "live_arts_md"
    assert receipt["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert receipt["operator_provided"] is True
    assert receipt["workbook_body_read"] is False
    assert receipt["cell_read"] is False
    assert receipt["confidence"] == "operator_handoff"
    assert "Invoice Register!A1:K7" in receipt["proof_refs"]


def test_candidate_register_includes_three_operator_provided_invoices():
    register = handoff.build_candidate_register(generated_at=FIXED_NOW)
    candidates = {item["invoice_id"]: item for item in register["invoice_candidates"]}

    assert set(candidates) == {"2026-1001", "2026-1002", "2026-1003"}
    assert register["machine_proof"]["operator_provided_not_workbook_parsed"] is True


def test_speaker_rental_candidate_is_draft_ready_but_not_sent_or_paid():
    candidate = handoff.build_candidate_register(generated_at=FIXED_NOW)["invoice_candidates"][0]

    assert candidate["invoice_id"] == "2026-1001"
    assert candidate["work_type"] == "Speaker Rental"
    assert candidate["amount"] == 900
    assert candidate["invoice_status"] == "Draft - ready to send"
    assert candidate["receipt_status"] == "UNPAID"
    assert candidate["sent"] is False
    assert candidate["paid"] is False
    assert candidate["ledger_posted"] is False


def test_av_tech_candidate_requires_verification_before_send():
    candidate = handoff.build_candidate_register(generated_at=FIXED_NOW)["invoice_candidates"][1]

    assert candidate["invoice_id"] == "2026-1002"
    assert candidate["amount"] == 4625
    assert candidate["invoice_status"] == "Draft - verify before send"
    assert candidate["readiness_status"] == "NEEDS_OPERATOR_VERIFICATION"
    assert candidate["send_readiness"] == "NOT_SEND_READY"


def test_july_invoice_is_future_draft_not_send_ready():
    candidate = handoff.build_candidate_register(generated_at=FIXED_NOW)["invoice_candidates"][2]

    assert candidate["invoice_id"] == "2026-1003"
    assert candidate["invoice_status"] == "Future/draft"
    assert candidate["readiness_status"] == "FUTURE_NOT_SEND_READY"
    assert candidate["selection_action"]["enabled"] is False


def test_workbook_existence_does_not_mark_sent_paid_or_ledger_posted():
    register = handoff.build_candidate_register(generated_at=FIXED_NOW)

    for candidate in register["invoice_candidates"]:
        assert candidate["sent"] is False
        assert candidate["submitted"] is False
        assert candidate["paid"] is False
        assert candidate["ledger_posted"] is False
    assert register["machine_proof"]["workbook_existence_does_not_mark_sent_paid_or_ledger_posted"] is True


def test_dance_dane_ambiguity_is_flagged_for_operator_confirmation():
    ambiguity = handoff.build_candidate_register(generated_at=FIXED_NOW)["contact_ambiguity"]

    assert ambiguity["status"] == "NEEDS_OPERATOR_CONFIRMATION"
    assert ambiguity["ambiguous_names"] == ("Dance", "Dane")
    assert ambiguity["do_not_silently_choose"] is True
    assert ambiguity["emails_invented"] is False


def test_candidate_selection_writes_selection_receipt_without_completion_claims():
    candidate = handoff.build_candidate_register(generated_at=FIXED_NOW)["invoice_candidates"][0]
    result = handoff.process_invoice_candidate_selection(
        candidate["selection_action"]["hidden_request_payload"],
        generated_at=FIXED_NOW,
    )
    receipt = result["receipt"]

    assert result["status"] == "SELECTED_REQUIRES_ARTIFACT_AND_APPROVAL"
    assert receipt["receipt_event"] == "live_arts_md_invoice_candidate_selected_receipt"
    assert receipt["invoice_id"] == "2026-1001"
    assert receipt["workbook_body_read"] is False
    assert receipt["cell_read"] is False
    assert receipt["sent"] is False
    assert receipt["paid"] is False
    assert receipt["ledger_posted"] is False
    assert receipt["artifact_ready"] is False
    assert receipt["approval_ready"] is False


def test_invoice_action_handler_accepts_live_arts_candidate_selection(tmp_path):
    candidate = handoff.build_candidate_register(generated_at=FIXED_NOW)["invoice_candidates"][0]
    result = action_handler.process_action_request(
        {
            "request_id": "live_arts_md_select_2026_1001",
            "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
            "client_ref": "live_arts_md",
            "workflow_ref": "live_arts_md_invoice_workflow",
            "action_kind": "select_invoice_candidate",
            "hidden_request_payload": candidate["selection_action"]["hidden_request_payload"],
        },
        generated_at=FIXED_NOW,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        event_db_path=tmp_path / "events.sqlite",
        event_export_root=tmp_path / "events",
    )

    receipt = result["action_start_receipt"]
    assert result["status"] == "GUIDED_ACTION_STARTED"
    assert receipt["receipt_name"] == "live_arts_md_invoice_candidate_selected_receipt"
    assert receipt["invoice_id"] == "2026-1001"
    assert receipt["sent"] is False
    assert receipt["paid"] is False
    assert receipt["ledger_posted"] is False
    assert result["state_machine_progress"]["bridge_mirror_written"] is True


def test_live_arts_record_selection_surface_has_no_capital_hilton_leakage(tmp_path):
    result = action_handler.process_action_request(
        {
            "request_id": "live_arts_md_start_invoice_record_selection",
            "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
            "client_ref": "live_arts_md",
            "workflow_ref": "live_arts_md_invoice_workflow",
            "intended_use": "start_invoice_record_selection",
            "action_kind": "start_invoice_record_selection",
            "hidden_request_payload": {
                "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
                "client_ref": "live_arts_md",
                "workflow_ref": "live_arts_md_invoice_workflow",
                "action_kind": "start_invoice_record_selection",
                "intended_use": "start_invoice_record_selection",
                "no_external_action": True,
                "no_workbook_body_read": True,
                "no_cell_read": True,
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "coupa_submit_allowed": False,
                "physical_deletion_allowed": False,
            },
        },
        generated_at=FIXED_NOW,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        event_db_path=tmp_path / "events.sqlite",
        event_export_root=tmp_path / "events",
    )
    surface = result["local_surface_request"]
    response_text = json.dumps(result)

    assert surface["surface_type"] == "SHOW_INVOICE_RECORD_SELECTION_PANEL"
    assert surface["client_ref"] == "live_arts_md"
    assert surface["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert surface["client_display_name"] == "Live Arts MD"
    assert surface["operator_copy"] == "Let's select the Live Arts MD invoice page/period. No workbook cells will be read."
    assert surface["completion_receipt_required"] == "live_arts_md_invoice_candidate_selected_receipt"
    assert surface["invoice_candidate_context"]["candidate_register_ref"] == "generated/read_models/live_arts_md_invoice_candidate_register.json"
    assert "Capital Hilton" not in response_text
    assert "capital_hilton" not in response_text


def test_capital_hilton_record_selection_surface_has_no_live_arts_leakage(tmp_path):
    result = action_handler.process_action_request(
        {
            "request_id": "capital_hilton_start_invoice_record_selection",
            "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "action_kind": "start_invoice_record_selection",
            "hidden_request_payload": {
                "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
                "client_ref": "capital_hilton",
                "workflow_ref": "capital_hilton_invoice_workflow",
                "action_kind": "start_invoice_record_selection",
                "intended_use": "start_invoice_record_selection",
                "no_external_action": True,
                "no_workbook_body_read": True,
                "no_cell_read": True,
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "coupa_submit_allowed": False,
                "physical_deletion_allowed": False,
            },
        },
        generated_at=FIXED_NOW,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        event_db_path=tmp_path / "events.sqlite",
        event_export_root=tmp_path / "events",
    )
    surface = result["local_surface_request"]
    response_text = json.dumps(result)

    assert surface["client_ref"] == "capital_hilton"
    assert surface["workflow_ref"] == "capital_hilton_invoice_workflow"
    assert "Capital Hilton invoice page/period" in surface["operator_copy"]
    assert "Live Arts" not in response_text
    assert "live_arts_md" not in response_text


def test_live_arts_scoped_response_primary_payload_excludes_stale_capital_proof(tmp_path):
    result = action_handler.process_action_request(
        {
            "request_id": "live_arts_md_selection_with_stale_capital_note",
            "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
            "client_ref": "live_arts_md",
            "workflow_ref": "live_arts_md_invoice_workflow",
            "action_kind": "start_invoice_record_selection",
            "hidden_request_payload": {
                "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
                "client_ref": "live_arts_md",
                "workflow_ref": "live_arts_md_invoice_workflow",
                "action_kind": "start_invoice_record_selection",
                "intended_use": "start_invoice_record_selection",
                "proof_refs": ("capital_hilton_stale_ref",),
                "operator_visible_message": "Capital Hilton stale text should not become primary response.",
                "no_external_action": True,
                "no_workbook_body_read": True,
                "no_cell_read": True,
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "coupa_submit_allowed": False,
                "physical_deletion_allowed": False,
            },
        },
        generated_at=FIXED_NOW,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        event_db_path=tmp_path / "events.sqlite",
        event_export_root=tmp_path / "events",
    )

    primary_payload = {
        "headline": result["headline"],
        "body": result["body"],
        "detail": result["detail"],
        "next_action": result["next_action"],
        "local_surface_request": result["local_surface_request"],
    }
    assert "Capital Hilton" not in json.dumps(primary_payload)
    assert primary_payload["local_surface_request"]["client_ref"] == "live_arts_md"


def test_payment_watch_and_ledger_planning_are_readiness_only():
    register = handoff.build_candidate_register(generated_at=FIXED_NOW)
    payment = register["expected_receivable_payment_watch_readiness"]
    ledger = register["ledger_planning"]

    assert payment["payment_watch_status"] == "READINESS_ONLY_NOT_ACTIVE"
    assert payment["bank_ledger_read_performed"] is False
    assert payment["ledger_posting_allowed"] is False
    assert ledger["current_ledger_pointer_manifest_required"] is True
    assert ledger["silent_ledger_mutation_allowed"] is False
    assert ledger["alias_map_requires_human_approval"] is True


def test_export_writes_candidate_register_and_bridge(tmp_path):
    export_root = tmp_path / "read_models"
    bridge_root = tmp_path / "bridge"
    assert export_main(
        [
            "--export-root",
            str(export_root),
            "--bridge-export-root",
            str(bridge_root),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0
    source = export_root / handoff.JSON_EXPORT_NAME
    bridge = bridge_root / handoff.JSON_EXPORT_NAME

    assert source.is_file()
    assert bridge.is_file()
    assert json.loads(source.read_text(encoding="utf-8"))["candidate_count"] == 3
    assert source.read_bytes() == bridge.read_bytes()
