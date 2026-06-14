import json
import sqlite3
from pathlib import Path

import invoice_review_action_request_handler as action_handler
import invoice_review_bundle
import operator_action_event_journal as journal


FIXED_NOW = "2026-05-28T12:00:00+00:00"


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    return (
        tmp_path / "invoice_review_state.sqlite",
        tmp_path / "operator_action_events.sqlite",
        tmp_path / "generated" / "read_models",
        tmp_path / "bridge" / "generated" / "read_models",
        tmp_path / "events" / "read_models",
    )


def _request(action_kind: str, *, request_id: str | None = None, label: str | None = None) -> dict:
    bundle = invoice_review_bundle.build_capital_hilton_bundle(generated_at=FIXED_NOW)
    actions = {}
    for action in bundle["correction_actions"]:
        actions[action["action_kind"]] = action
    for step in bundle["review_proof_timeline"]:
        if step["primary_action"]:
            actions[step["primary_action"]["action_kind"]] = step["primary_action"]
            compatibility = step["primary_action"]["hidden_request_payload"].get("compatibility_action_kind")
            if compatibility:
                actions[str(compatibility)] = step["primary_action"]
        for action in step["secondary_actions"]:
            actions[action["action_kind"]] = action
    hidden = dict(actions.get(action_kind, {}).get("hidden_request_payload") or {})
    hidden.update(
        {
            "client_ref": "capital_hilton",
            "workflow_ref": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
            "source_workflow_id": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
            "source_bundle_id": invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID,
            "action_kind": action_kind,
            "request_kind": action_kind,
            "intended_use": action_kind,
            "label": label or actions.get(action_kind, {}).get("label") or action_kind,
            "no_external_action": True,
            "physical_deletion_allowed": False,
        }
    )
    return {
        "request_id": request_id or f"journal_test_{action_kind}",
        "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
        "kind": "INVOICE_REVIEW_ACTION_REQUEST",
        "workflow_ref": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        "client_ref": "capital_hilton",
        "action_kind": action_kind,
        "intended_use": action_kind,
        "hidden_request_payload": hidden,
    }


def _process(tmp_path: Path, action_kind: str, *, label: str | None = None) -> dict:
    state_db, event_db, export_root, bridge_root, event_export_root = _paths(tmp_path)
    return action_handler.process_action_request(
        _request(action_kind, label=label),
        db_path=state_db,
        export_root=export_root,
        bridge_export_root=bridge_root,
        event_db_path=event_db,
        event_export_root=event_export_root,
        generated_at=FIXED_NOW,
    )


def _journal_payload(tmp_path: Path) -> dict:
    _, _, _, _, event_export_root = _paths(tmp_path)
    return json.loads((event_export_root / journal.JSON_EXPORT_NAME).read_text(encoding="utf-8"))


def test_supported_invoice_review_action_writes_handled_event(tmp_path):
    payload = _process(tmp_path, "start_invoice_record_selection")
    event = payload["operator_action_event"]
    read_model = _journal_payload(tmp_path)

    assert event["action_category"] == "GOVERNED_REQUEST"
    assert event["status"] == "HANDLED"
    assert event["handled"] is True
    assert event["no_external_action"] is True
    assert event["physical_deletion_allowed"] is False
    assert event["proof_refs"] == (payload["action_start_receipt"]["receipt_id"],)
    assert read_model["events"][0]["event_id"] == event["event_id"]


def test_unsupported_meaningful_action_writes_pending_not_wired_event(tmp_path):
    payload = _process(tmp_path, "future_invoice_magic_button", label="Future invoice magic")
    event = payload["operator_action_event"]
    read_model = _journal_payload(tmp_path)

    assert event["action_category"] == "UNSUPPORTED_PENDING"
    assert event["status"] == "PENDING_NOT_WIRED"
    assert event["handled"] is False
    assert read_model["pending_operator_intents"][0]["event_id"] == event["event_id"]
    assert "not wired yet" in read_model["pending_operator_intents"][0]["operator_visible_summary"]


def test_disabled_action_can_be_recorded_with_reason(tmp_path):
    _, event_db, _, _, event_export_root = _paths(tmp_path)
    event = journal.record_operator_action_event(
        source_request_id="disabled_action_request",
        client_ref="capital_hilton",
        workflow_ref=invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        bundle_id=invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID,
        action_ref="prepare_send_approval_request",
        intended_use="prepare_send_approval_request",
        label_clicked="Approve",
        action_category="DISABLED",
        emitted_backend_request=False,
        handled=False,
        handler_ref="invoice_review_action_request.capital_hilton",
        status="DISABLED",
        operator_visible_summary="Approval is disabled until prerequisites are complete.",
        no_external_action=True,
        physical_deletion_allowed=False,
        db_path=event_db,
        generated_at=FIXED_NOW,
    )
    payload, _, _ = journal.export_read_model(
        db_path=event_db,
        export_root=event_export_root,
        generated_at=FIXED_NOW,
    )

    assert event["status"] == "DISABLED"
    assert payload["blocked_or_disabled_events"][0]["event_id"] == event["event_id"]


def test_wrong_workbook_action_records_no_deletion_or_mutation(tmp_path):
    payload = _process(tmp_path, "replace_source_workbook_reference", label="Wrong workbook")
    state_db, event_db, _, _, _ = _paths(tmp_path)
    event = payload["operator_action_event"]

    assert event["operator_visible_summary"] == "Operator indicated the current workbook reference may be wrong."
    assert event["physical_deletion_allowed"] is False
    assert event["no_external_action"] is True
    with sqlite3.connect(state_db) as conn:
        row = conn.execute(
            "SELECT completion_receipt_written, underlying_blocker_completed FROM invoice_review_receipts"
        ).fetchone()
    assert row == (0, 0)
    with sqlite3.connect(event_db) as conn:
        journal_row = conn.execute(
            "SELECT physical_deletion_allowed, status FROM operator_action_events WHERE event_id = ?",
            (event["event_id"],),
        ).fetchone()
    assert journal_row == (0, "HANDLED")


def test_event_journal_does_not_mark_blocker_complete(tmp_path):
    payload = _process(tmp_path, "request_supplier_portal_submission_proof")
    state_progress = payload["state_machine_progress"]

    assert payload["operator_action_event"]["status"] == "HANDLED"
    assert state_progress["action_progress_receipt"]["completion_receipt_written"] is False
    assert state_progress["action_progress_receipt"]["underlying_blocker_completed"] is False
