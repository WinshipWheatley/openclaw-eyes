import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capability_authority_loop
import global_run_mode_context
import operator_conversation_router
import test_effect_adapters as adapters


FIXED_NOW = "2026-06-09T02:00:00+00:00"


def _context(run_mode):
    state = global_run_mode_context.build_run_mode_state(
        run_mode=run_mode,
        scope={"scope": "session", "target_world_ref": "test", "target_thread_ref": "effects"},
        generated_at=FIXED_NOW,
    )
    return global_run_mode_context.context_from_state(state, source="test_fixture", generated_at=FIXED_NOW)


def _authority(test_run_id, effect_kinds):
    return adapters.build_test_execution_authority(
        test_run_id=test_run_id,
        allowed_effect_kinds=effect_kinds,
        allowlisted_recipients=[adapters.ALLOWLISTED_TEST_EMAIL],
        max_external_effects=1,
        generated_at=FIXED_NOW,
    )


def _effect(effect_kind, run_mode, **extra):
    context = _context(run_mode)
    request = adapters.build_test_effect_request(
        effect_kind=effect_kind,
        run_mode_context=context,
        target=extra.pop("target", "test_target"),
        payload_summary=extra.pop("payload_summary", "test payload"),
        generated_at=FIXED_NOW,
        **extra,
    )
    return request


def _unsafe_true_grants(value, path="$"):
    unsafe = {
        "email_send_allowed",
        "gmail_allowed",
        "gmail_ui_allowed",
        "browser_access_allowed",
        "coupa_allowed",
        "coupa_submit_allowed",
        "portal_submit_allowed",
        "ledger_posting_allowed",
        "ledger_mutation_allowed",
        "paid_marking_allowed",
        "production_ledger_mutation_allowed",
        "production_workbook_mutation_allowed",
        "production_pdf_export_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "git_push_allowed",
        "merge_allowed",
        "authority_granted",
        "sent",
        "paid",
        "submitted",
    }
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_grants(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_grants(child, f"{path}[{index}]"))
    return found


def test_production_rejects_test_effect_request_with_marker(tmp_path):
    request = _effect(adapters.SQLITE_WRITE, global_run_mode_context.PRODUCTION)
    request["test_marker"] = adapters.TEST_MARKER
    receipt = adapters.execute_test_effect(request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)

    assert receipt["status"] == adapters.BLOCKED_BY_RUN_MODE
    assert receipt["external_effect"] is False
    assert receipt["machine_proof"]["production_action_performed"] is False


def test_test_dry_run_records_receipt_only(tmp_path):
    request = _effect(adapters.SQLITE_WRITE, global_run_mode_context.TEST_DRY_RUN)
    receipt = adapters.execute_test_effect(request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)

    assert receipt["status"] == adapters.DRY_RUN_RECORDED
    con = sqlite3.connect(tmp_path / "effects.sqlite")
    try:
        row_count = con.execute("select count(*) from test_sqlite_rows").fetchone()[0]
        receipt_count = con.execute("select count(*) from test_effect_receipts").fetchone()[0]
    finally:
        con.close()
    assert row_count == 0
    assert receipt_count == 1


def test_test_live_requires_test_execution_authority(tmp_path):
    request = _effect(adapters.SQLITE_WRITE, global_run_mode_context.TEST_LIVE)
    receipt = adapters.execute_test_effect(request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)

    assert receipt["status"] == adapters.BLOCKED_BY_AUTHORITY


def test_raw_authority_granted_cannot_activate_test_live(tmp_path):
    request = _effect(adapters.SQLITE_WRITE, global_run_mode_context.TEST_LIVE)
    request["authority_granted"] = True
    receipt = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        test_execution_authority=_authority(request["test_run_id"], [adapters.SQLITE_WRITE]),
        generated_at=FIXED_NOW,
    )

    assert receipt["status"] == adapters.BLOCKED_BY_AUTHORITY
    assert "Raw authority_granted" in receipt["adapter_missing_reason"]


def test_test_sqlite_write_live_writes_only_marked_test_row(tmp_path):
    request = _effect(adapters.SQLITE_WRITE, global_run_mode_context.TEST_LIVE, payload_summary="write test row")
    receipt = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        test_execution_authority=_authority(request["test_run_id"], [adapters.SQLITE_WRITE]),
        generated_at=FIXED_NOW,
    )

    assert receipt["status"] == adapters.TEST_LIVE_EXECUTED
    con = sqlite3.connect(tmp_path / "effects.sqlite")
    try:
        row = con.execute("select run_mode, test_run_id, test_marker, production_safe from test_sqlite_rows").fetchone()
    finally:
        con.close()
    assert row[0] == global_run_mode_context.TEST_LIVE
    assert row[1] == request["test_run_id"]
    assert row[2] == adapters.TEST_MARKER
    assert row[3] == 0


def test_production_proof_rejects_marked_test_sqlite_row():
    artifact = {"test_marker": adapters.TEST_MARKER, "artifact_kind": "sqlite_db"}

    assert adapters.production_claim_accepts_test_artifact(artifact, "ledger_updated") is False
    assert global_run_mode_context.production_claim_accepts_artifact(artifact, "paid") is False


def test_test_dry_run_sqlite_does_not_mutate_production_db(tmp_path):
    production_db = tmp_path / "production.sqlite"
    con = sqlite3.connect(production_db)
    try:
        con.execute("create table production_rows (id text primary key)")
        con.commit()
    finally:
        con.close()
    request = _effect(adapters.SQLITE_WRITE, global_run_mode_context.TEST_DRY_RUN, target=str(production_db))
    adapters.execute_test_effect(request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)
    con = sqlite3.connect(production_db)
    try:
        count = con.execute("select count(*) from production_rows").fetchone()[0]
    finally:
        con.close()
    assert count == 0


def test_test_dry_run_email_produces_receipt_and_sends_nothing(tmp_path):
    request = _effect(adapters.EMAIL_SEND, global_run_mode_context.TEST_DRY_RUN, target="client@example.com", email_subject="hello", email_body="body")
    receipt = adapters.execute_test_effect(request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)

    assert receipt["status"] == adapters.DRY_RUN_RECORDED
    assert receipt["actual_target"] == adapters.ALLOWLISTED_TEST_EMAIL
    assert receipt["external_effect"] is False
    assert receipt["email_preview"]["subject"].startswith("[OPENCLAW TEST]")
    assert receipt["email_preview"]["body_has_test_marker"] is True


def test_test_live_email_to_allowlisted_requires_authority_and_reports_missing_transport(tmp_path):
    request = _effect(adapters.EMAIL_SEND, global_run_mode_context.TEST_LIVE, target=adapters.ALLOWLISTED_TEST_EMAIL, email_subject="live", email_body="body")
    blocked = adapters.execute_test_effect(request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)
    allowed_but_missing = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        test_execution_authority=_authority(request["test_run_id"], [adapters.EMAIL_SEND]),
        generated_at=FIXED_NOW,
    )

    assert blocked["status"] == adapters.BLOCKED_BY_AUTHORITY
    assert allowed_but_missing["status"] == adapters.TEST_ADAPTER_MISSING
    assert "No safe email transport" in allowed_but_missing["adapter_missing_reason"]


def test_test_live_email_to_non_allowlisted_recipient_redirects_and_does_not_send(tmp_path):
    request = _effect(adapters.EMAIL_SEND, global_run_mode_context.TEST_LIVE, target="client@example.com", email_subject="live", email_body="body")
    receipt = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        test_execution_authority=_authority(request["test_run_id"], [adapters.EMAIL_SEND]),
        generated_at=FIXED_NOW,
    )

    assert receipt["status"] == adapters.TEST_ADAPTER_MISSING
    assert receipt["actual_target"] == adapters.ALLOWLISTED_TEST_EMAIL
    assert receipt["target_redirect"]["original_target_redacted"] == "c***@example.com"
    assert receipt["external_effect"] is False


def test_email_subject_body_marker_and_no_cc_bcc_attachments(tmp_path):
    request = _effect(adapters.EMAIL_SEND, global_run_mode_context.TEST_DRY_RUN, target=adapters.ALLOWLISTED_TEST_EMAIL, cc=["x@example.com"])
    receipt = adapters.execute_test_effect(request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)

    assert receipt["status"] == adapters.BLOCKED_BY_ALLOWLIST
    assert receipt["external_effect"] is False


def test_max_one_live_email_send_per_test_run_is_enforced_if_receipt_exists(tmp_path):
    request = _effect(adapters.EMAIL_SEND, global_run_mode_context.TEST_LIVE, target=adapters.ALLOWLISTED_TEST_EMAIL)
    first_receipt = {
        "schema_version": adapters.TEST_EFFECT_RECEIPT_SCHEMA,
        "effect_id": "preexisting-live-email",
        "effect_kind": adapters.EMAIL_SEND,
        "run_mode": global_run_mode_context.TEST_LIVE,
        "test_run_id": request["test_run_id"],
        "status": adapters.TEST_LIVE_EXECUTED,
        "actual_target": adapters.ALLOWLISTED_TEST_EMAIL,
        "external_effect": True,
        "created_at": FIXED_NOW,
    }
    adapters._store_receipt(tmp_path / "effects.sqlite", first_receipt)
    receipt = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        test_execution_authority=_authority(request["test_run_id"], [adapters.EMAIL_SEND]),
        generated_at=FIXED_NOW,
    )

    assert receipt["status"] == adapters.BLOCKED_BY_ALLOWLIST
    assert "max one live test email" in receipt["adapter_missing_reason"]


def test_email_test_receipt_cannot_prove_client_was_emailed(tmp_path):
    request = _effect(adapters.EMAIL_SEND, global_run_mode_context.TEST_DRY_RUN, target="client@example.com")
    receipt = adapters.execute_test_effect(request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)

    assert adapters.production_claim_accepts_test_artifact(receipt, "client_was_emailed") is False


def test_generic_file_mutation_in_test_live_creates_test_workspace_copy(tmp_path):
    original = tmp_path / "source.txt"
    original.write_text("original", encoding="utf-8")
    request = _effect(adapters.FILE_WORKSPACE_COPY, global_run_mode_context.TEST_LIVE, source_path=str(original), target=str(original))
    receipt = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        workspace_root=tmp_path / "workspaces",
        test_execution_authority=_authority(request["test_run_id"], [adapters.FILE_WORKSPACE_COPY]),
        generated_at=FIXED_NOW,
    )

    copy_path = Path(receipt["workspace_artifact"]["test_copy_path"])
    assert receipt["status"] == adapters.TEST_LIVE_EXECUTED
    assert copy_path.exists()
    assert copy_path.read_text(encoding="utf-8") == "original"
    assert original.read_text(encoding="utf-8") == "original"


def test_logicx_request_creates_test_copy_path_with_marker(tmp_path):
    original = tmp_path / "Session.logicx"
    original.mkdir()
    (original / "projectData").write_text("logic", encoding="utf-8")
    request = _effect(adapters.LOGIC_PROJECT_COPY, global_run_mode_context.TEST_LIVE, source_path=str(original), target=str(original))
    receipt = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        workspace_root=tmp_path / "workspaces",
        test_execution_authority=_authority(request["test_run_id"], [adapters.LOGIC_PROJECT_COPY]),
        generated_at=FIXED_NOW,
    )

    artifact = receipt["workspace_artifact"]
    assert artifact["artifact_kind"] == "logic_project"
    assert "__OPENCLAW_TEST__" in artifact["test_copy_path"]
    assert artifact["test_copy_path"].endswith(".logicx")
    assert Path(artifact["marker_file"]).read_text(encoding="utf-8").strip() == adapters.TEST_MARKER


def test_downstream_automation_receives_test_copy_not_original(tmp_path):
    original = tmp_path / "media.wav"
    original.write_text("audio", encoding="utf-8")
    request = _effect(adapters.FILE_WORKSPACE_COPY, global_run_mode_context.TEST_LIVE, source_path=str(original), target=str(original))
    receipt = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        workspace_root=tmp_path / "workspaces",
        test_execution_authority=_authority(request["test_run_id"], [adapters.FILE_WORKSPACE_COPY]),
        generated_at=FIXED_NOW,
    )

    assert receipt["workspace_artifact"]["downstream_target_path"] != str(original)
    assert receipt["workspace_artifact"]["original_path"] == str(original)


def test_production_proof_rejects_test_workspace_artifact(tmp_path):
    artifact = {"schema_version": adapters.TEST_WORKSPACE_ARTIFACT_SCHEMA, "test_marker": adapters.TEST_MARKER}

    assert adapters.production_claim_accepts_test_artifact(artifact, "production_file_updated") is False
    assert adapters.production_claim_accepts_test_artifact(artifact, "test_workspace_copy_created") is True


def test_coupa_paid_ledger_workbook_pdf_remain_blocked_in_test_mode(tmp_path):
    request = _effect(adapters.SQLITE_WRITE, global_run_mode_context.TEST_LIVE, payload_summary="try Coupa paid ledger workbook PDF")
    receipt = adapters.execute_test_effect(
        request,
        sqlite_path=tmp_path / "effects.sqlite",
        test_execution_authority=_authority(request["test_run_id"], [adapters.SQLITE_WRITE]),
        generated_at=FIXED_NOW,
    )

    assert receipt["authority_boundary"]["coupa_submit_allowed"] is False
    assert receipt["authority_boundary"]["paid_marking_allowed"] is False
    assert receipt["authority_boundary"]["production_ledger_mutation_allowed"] is False
    assert receipt["authority_boundary"]["production_workbook_mutation_allowed"] is False
    assert receipt["authority_boundary"]["production_pdf_export_allowed"] is False


def test_test_authority_does_not_become_production_authority():
    authority = _authority("test-run", [adapters.EMAIL_SEND])

    assert authority["run_mode"] == global_run_mode_context.TEST_LIVE
    assert "business_email_send" in authority["denied_actions"]
    assert authority["authority_boundary"]["business_email_send_allowed"] is False


def test_existing_email_capability_gap_scenarios_still_pass(tmp_path):
    cases = [
        ("Have we received any emails from Annette?", "finance", "capital_hilton"),
        ("Can you check my email and see the new accountant's name, email, and role?", "finance", "live_arts_md"),
        ("Did Glenn acknowledge the invoice or payment timing?", "finance", "st_annes"),
    ]
    for text, world, thread in cases:
        request = {
            "request_type": operator_conversation_router.REQUEST_TYPE,
            "controller_event_type": "chat_goal",
            "operator_text": text,
            "current_world_ref": world,
            "current_thread_ref": thread,
            "authority_boundary": dict(operator_conversation_router.AUTHORITY_BOUNDARY),
        }
        result = operator_conversation_router.route_conversation_text(request, sqlite_path=tmp_path / "conversation.sqlite", generated_at=FIXED_NOW)
        assert result["route_status"] == operator_conversation_router.ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST
        assert result["workflow_request_type_emitted"] == ""
        assert result["make_it_so_objective"]["capability_authority"]["capability_gap"]["capability_id"] == capability_authority_loop.READ_ONLY_EMAIL_LOOKUP


def test_unsafe_true_grant_scan_clean_for_adapter_outputs(tmp_path):
    sqlite_request = _effect(adapters.SQLITE_WRITE, global_run_mode_context.TEST_LIVE)
    sqlite_receipt = adapters.execute_test_effect(
        sqlite_request,
        sqlite_path=tmp_path / "effects.sqlite",
        test_execution_authority=_authority(sqlite_request["test_run_id"], [adapters.SQLITE_WRITE]),
        generated_at=FIXED_NOW,
    )
    email_request = _effect(adapters.EMAIL_SEND, global_run_mode_context.TEST_DRY_RUN, target=adapters.ALLOWLISTED_TEST_EMAIL)
    email_receipt = adapters.execute_test_effect(email_request, sqlite_path=tmp_path / "effects.sqlite", generated_at=FIXED_NOW)

    assert not _unsafe_true_grants(sqlite_receipt)
    assert not _unsafe_true_grants(email_receipt)
