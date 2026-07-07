import json
import sqlite3
from pathlib import Path

import global_run_mode_context as grmc
import invoice_send_workflow as invoice_workflow
import test_effect_adapters
import workflow_test_mode_self_proof as self_proof


FIXED_NOW = "2026-07-07T14:00:00+00:00"


def test_st_annes_test_mode_self_proof_runs_real_workflow_to_staged_send(tmp_path):
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD remains active for the self-proof.\n", encoding="utf-8")

    receipt = self_proof.run_st_annes_workflow_test_mode_self_proof(
        export_root=tmp_path / "read_models",
        run_mode_sqlite_path=tmp_path / "run_mode.sqlite",
        test_effect_sqlite_path=tmp_path / "test_effects.sqlite",
        send_hold_path=send_hold,
        generated_at=FIXED_NOW,
    )

    assert receipt["schema_version"] == self_proof.SCHEMA_VERSION
    assert receipt["status"] == self_proof.PASS_STATUS
    assert receipt["workflow_ref"] == "st_annes_invoice_rollup"
    assert receipt["run_mode_context"]["run_mode"] == grmc.TEST_DRY_RUN
    assert receipt["test_marker"] == grmc.TEST_MARKER
    assert receipt["send_hold"]["active"] is True
    assert receipt["final_step_status"] == "test_send_staged"
    assert receipt["real_send_action_emitted"] is False

    step_kinds = [step["kind"] for step in receipt["steps"]]
    assert step_kinds == [
        invoice_workflow.SEND_INVOICE_PREVIEW,
        invoice_workflow.SEND_DRAFT_AND_APPROVAL,
        invoice_workflow.TEST_SEND,
        "test_effect_adapter_receipt",
    ]
    assert all(step["status"] == "pass" for step in receipt["steps"])

    staged = receipt["final_staged_send"]
    assert staged["to"] == grmc.ALLOWLISTED_TEST_EMAIL
    assert staged["original_to_redacted"] == "s***@example.test"
    assert not staged.get("cc")
    assert not staged.get("bcc")
    assert "[OPENCLAW TEST]" in staged["subject"]
    assert grmc.TEST_MARKER in staged["body"]
    assert receipt["test_run_id"] in staged["body"]
    assert staged["attachment_path"].endswith("st-annes-rollup.pdf")

    adapter_receipt = receipt["test_effect_receipt"]
    assert adapter_receipt["status"] == test_effect_adapters.DRY_RUN_RECORDED
    assert adapter_receipt["actual_target"] == grmc.ALLOWLISTED_TEST_EMAIL
    assert adapter_receipt["external_effect"] is False
    assert adapter_receipt["email_preview"]["body_has_test_marker"] is True

    assert receipt["safety"]["external_send_performed"] is False
    assert receipt["safety"]["business_email_send_performed"] is False
    assert receipt["safety"]["ledger_mutation_performed"] is False
    assert receipt["safety"]["paid_marking_performed"] is False
    assert receipt["safety"]["send_hold_honored"] is True

    export_path = tmp_path / "read_models" / self_proof.JSON_EXPORT_NAME
    assert export_path.exists()
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["receipt_ref"] == receipt["receipt_ref"]

    con = sqlite3.connect(tmp_path / "test_effects.sqlite")
    try:
        row = con.execute(
            "select effect_kind, run_mode, status, external_effect from test_effect_receipts"
        ).fetchone()
    finally:
        con.close()
    assert row == (
        test_effect_adapters.EMAIL_SEND,
        grmc.TEST_DRY_RUN,
        test_effect_adapters.DRY_RUN_RECORDED,
        0,
    )

    con = sqlite3.connect(tmp_path / "run_mode.sqlite")
    try:
        run_row = con.execute(
            "select action_kind, receipt_json from test_execution_receipts"
        ).fetchone()
    finally:
        con.close()
    assert run_row[0] == "st_annes_invoice_rollup.test_send_staged"
    assert grmc.TEST_MARKER in run_row[1]
