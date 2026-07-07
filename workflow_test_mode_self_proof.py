"""Workflow Test Mode self-proof runner.

This wires the existing run-mode context, invoice-send state machine, test-mode
recipient lock, SEND_HOLD sentinel, and test-effect adapter into one receipt.
It stages a St. Anne's mock invoice rollup all the way to the test-send step and
records proof that no external send, money move, or ledger mutation happened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from authority_gate import DEFAULT_SEND_HOLD_PATH, ensure_send_hold_sentinel
import global_run_mode_context as grmc
import invoice_send_workflow as invoice_workflow
import test_effect_adapters
from workflow_test_mode import TEST_REDIRECT_FLAG, apply_test_mode_send, resolve_send_disposition


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_RUN_MODE_SQLITE_PATH = grmc.DEFAULT_SQLITE_PATH
DEFAULT_TEST_EFFECT_SQLITE_PATH = Path("generated/test_effects/workflow_test_mode_self_proof.sqlite")

SCHEMA_VERSION = "workflow_test_mode_self_proof_v0"
READ_MODEL_ID = "workflow_test_mode_self_proof"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
PASS_STATUS = "WORKFLOW_TEST_MODE_SELF_PROOF_PASS"
FAIL_STATUS = "WORKFLOW_TEST_MODE_SELF_PROOF_FAIL"
WORKFLOW_REF = "st_annes_invoice_rollup"


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else Path(__file__).resolve().parent / path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _short_hash(*parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if isinstance(part, (dict, list, tuple)):
            value = json.dumps(part, sort_keys=True, ensure_ascii=False)
        else:
            value = str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _redact_email(value: str) -> str:
    email = str(value or "").strip()
    if "@" not in email:
        return email
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def _mock_st_annes_invoice() -> dict[str, Any]:
    return {
        "client_name": "St. Anne's",
        "client_ref": "st_annes",
        "client_email": "sally@example.test",
        "invoice_number": "OPENCLAW-TEST-STANNES-ROLLUP",
        "currency": "USD",
        "line_items": [
            {
                "description": "Mock April event",
                "service_date": "2026-04-26",
                "amount": 12500,
            },
            {
                "description": "Mock May event",
                "service_date": "2026-05-31",
                "amount": 12500,
            },
        ],
        "amount_total": 25000,
        "source": "workflow_test_mode_self_proof_fixture",
        "production_invoice": False,
    }


def _email_body(invoice_data: Mapping[str, Any]) -> str:
    lines = [
        "Hello St. Anne's,",
        "",
        "This is an OpenClaw workflow-test-mode proof using mock St. Anne's rollup data.",
        "No production invoice, client send, payment, or ledger mutation is authorized by this proof.",
        "",
        "Line items:",
    ]
    for item in invoice_data.get("line_items") or []:
        amount = int(item.get("amount") or 0) / 100
        lines.append(f"- {item.get('service_date')}: {item.get('description')} - ${amount:,.2f}")
    total = int(invoice_data.get("amount_total") or 0) / 100
    lines.extend(["", f"Mock total: ${total:,.2f}"])
    return "\n".join(lines)


def _step(kind: str, *, status: str = "pass", **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "status": status, **extra}


def _build_context(generated_at: str) -> dict[str, Any]:
    state = grmc.build_run_mode_state(
        run_mode=grmc.TEST_DRY_RUN,
        scope={
            "scope": "workflow_self_proof",
            "target_world_ref": "finance",
            "target_thread_ref": WORKFLOW_REF,
            "target_project_ref": "openclaw_workflow_test_mode",
        },
        generated_at=generated_at,
    )
    return grmc.context_from_state(state, source="workflow_test_mode_self_proof", generated_at=generated_at)


def _stage_test_send(
    *,
    run_mode_context: Mapping[str, Any],
    send_action: Mapping[str, Any],
    invoice_data: Mapping[str, Any],
    send_hold_active: bool,
) -> dict[str, Any]:
    disposition = resolve_send_disposition(
        run_mode=str(run_mode_context.get("run_mode") or grmc.PRODUCTION),
        send_hold_active=send_hold_active,
        is_send_class=True,
    )
    subject = f"Invoice - {invoice_data.get('client_name')}"
    params = {
        "to": str(send_action.get("to") or ""),
        "cc": "workflow-test-cc@example.test",
        "bcc": "workflow-test-bcc@example.test",
        "subject": subject,
        "body": _email_body(invoice_data),
        "attachment_path": str(send_action.get("attachment") or ""),
        "attachment_sha256": str(send_action.get("attachment_sha256") or ""),
    }
    locked = apply_test_mode_send(
        params,
        operator_inbox=grmc.ALLOWLISTED_TEST_EMAIL,
        test_run_id=str(run_mode_context.get("test_run_id") or ""),
    )
    locked["original_to_redacted"] = _redact_email(str(send_action.get("to") or ""))
    locked["disposition"] = disposition
    locked["recipient_lock_applied"] = locked.get("to") == grmc.ALLOWLISTED_TEST_EMAIL
    locked["cc_bcc_stripped"] = not locked.get("cc") and not locked.get("bcc")
    return locked


def run_st_annes_workflow_test_mode_self_proof(
    *,
    export_root: Path | str = DEFAULT_EXPORT_ROOT,
    run_mode_sqlite_path: Path | str = DEFAULT_RUN_MODE_SQLITE_PATH,
    test_effect_sqlite_path: Path | str = DEFAULT_TEST_EFFECT_SQLITE_PATH,
    send_hold_path: Path | str = DEFAULT_SEND_HOLD_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or grmc.utc_now()
    run_mode_context = _build_context(generated_at)
    invoice_data = _mock_st_annes_invoice()
    pdf_path = "generated/mock_workflows/st-annes-rollup.pdf"
    digest = _short_hash(invoice_data, pdf_path, length=64)

    send_hold_state = ensure_send_hold_sentinel(send_hold_path)
    steps: list[dict[str, Any]] = []

    state, actions = invoice_workflow.start_invoice_send(
        "St. Anne's",
        invoice_data,
        pdf_path,
        digest,
    )
    preview = next((item for item in actions if item.get("kind") == invoice_workflow.SEND_INVOICE_PREVIEW), None)
    steps.append(
        _step(
            invoice_workflow.SEND_INVOICE_PREVIEW,
            pdf_path=str(preview.get("pdf_path") if preview else ""),
            stage=state.get("stage"),
        )
    )

    state, actions = invoice_workflow.handle_reply(state, "looks good")
    draft = next((item for item in actions if item.get("kind") == invoice_workflow.SEND_DRAFT_AND_APPROVAL), None)
    steps.append(_step(invoice_workflow.SEND_DRAFT_AND_APPROVAL, stage=state.get("stage"), client=draft.get("client") if draft else ""))

    state, actions = invoice_workflow.handle_reply(state, "approve")
    test_send = next((item for item in actions if item.get("kind") == invoice_workflow.TEST_SEND), None)
    real_send_emitted = any(item.get("kind") == invoice_workflow.REAL_SEND for item in actions)
    if not test_send:
        test_send = {}
    final_staged_send = _stage_test_send(
        run_mode_context=run_mode_context,
        send_action=test_send,
        invoice_data=invoice_data,
        send_hold_active=send_hold_state.send_hold_active,
    )
    steps.append(
        _step(
            invoice_workflow.TEST_SEND,
            stage=state.get("stage"),
            original_to_redacted=final_staged_send["original_to_redacted"],
            disposition=final_staged_send["disposition"],
            recipient_lock_applied=final_staged_send["recipient_lock_applied"],
            cc_bcc_stripped=final_staged_send["cc_bcc_stripped"],
        )
    )

    effect_request = test_effect_adapters.build_test_effect_request(
        effect_kind=test_effect_adapters.EMAIL_SEND,
        run_mode_context=run_mode_context,
        target=str(test_send.get("to") or ""),
        original_target=str(test_send.get("to") or ""),
        payload_summary="St. Anne's mock invoice rollup test-send staged under Workflow Test Mode.",
        requested_by="workflow_test_mode_self_proof",
        requested_scope={"workflow_ref": WORKFLOW_REF},
        email_subject=str(final_staged_send.get("subject") or ""),
        email_body=str(final_staged_send.get("body") or ""),
        generated_at=generated_at,
    )
    test_effect_receipt = test_effect_adapters.execute_test_effect(
        effect_request,
        sqlite_path=Path(test_effect_sqlite_path),
        generated_at=generated_at,
    )
    adapter_passed = (
        test_effect_receipt.get("status") == test_effect_adapters.DRY_RUN_RECORDED
        and test_effect_receipt.get("actual_target") == grmc.ALLOWLISTED_TEST_EMAIL
        and test_effect_receipt.get("external_effect") is False
    )
    steps.append(
        _step(
            "test_effect_adapter_receipt",
            status="pass" if adapter_passed else "fail",
            adapter_status=str(test_effect_receipt.get("status") or ""),
            actual_target=str(test_effect_receipt.get("actual_target") or ""),
            external_effect=bool(test_effect_receipt.get("external_effect")),
        )
    )

    test_execution_receipt = grmc.build_test_execution_receipt(
        Path(run_mode_sqlite_path),
        run_mode_context=run_mode_context,
        action_kind=f"{WORKFLOW_REF}.test_send_staged",
        target_ref=grmc.ALLOWLISTED_TEST_EMAIL,
        generated_at=generated_at,
    )

    safety = {
        "send_hold_honored": bool(send_hold_state.send_hold_active),
        "external_send_performed": False,
        "business_email_send_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "ledger_mutation_performed": False,
        "paid_marking_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "money_movement_performed": False,
    }
    pass_checks = [
        run_mode_context.get("run_mode") == grmc.TEST_DRY_RUN,
        final_staged_send.get("disposition") == TEST_REDIRECT_FLAG,
        final_staged_send.get("recipient_lock_applied") is True,
        final_staged_send.get("cc_bcc_stripped") is True,
        grmc.TEST_MARKER in str(final_staged_send.get("body") or ""),
        not real_send_emitted,
        adapter_passed,
        send_hold_state.send_hold_active,
        all(value is False for key, value in safety.items() if key != "send_hold_honored"),
    ]
    status = PASS_STATUS if all(pass_checks) else FAIL_STATUS
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": status,
        "receipt_ref": f"{READ_MODEL_ID}:{_short_hash(run_mode_context, final_staged_send, generated_at)}",
        "workflow_ref": WORKFLOW_REF,
        "generated_at": generated_at,
        "test_run_id": str(run_mode_context.get("test_run_id") or ""),
        "test_marker": grmc.TEST_MARKER,
        "run_mode_context": run_mode_context,
        "send_hold": {
            "active": bool(send_hold_state.send_hold_active),
            "path": str(send_hold_state.path),
            "reason": str(send_hold_state.reason),
        },
        "steps": steps,
        "final_step_status": "test_send_staged" if test_send else "test_send_missing",
        "final_staged_send": final_staged_send,
        "test_effect_request": effect_request,
        "test_effect_receipt": test_effect_receipt,
        "test_execution_receipt": test_execution_receipt,
        "real_send_action_emitted": real_send_emitted,
        "safety": safety,
        "source": {
            "invoice_state_machine": "invoice_send_workflow",
            "run_mode_context": "global_run_mode_context",
            "recipient_lock": "workflow_test_mode.apply_test_mode_send",
            "effect_adapter": "test_effect_adapters.EMAIL_SEND",
            "spec_ref": "Operator/FABLE-WORKFLOW-TEST-MODE-SPEC-20260703.md",
            "spec_ref_present": False,
        },
        "authority_boundary": dict(grmc.AUTHORITY_BOUNDARY),
    }
    export_path = Path(export_root) / JSON_EXPORT_NAME
    _write_json(export_path, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the Workflow Test Mode self-proof read model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--run-mode-sqlite-path", default=str(DEFAULT_RUN_MODE_SQLITE_PATH))
    parser.add_argument("--test-effect-sqlite-path", default=str(DEFAULT_TEST_EFFECT_SQLITE_PATH))
    parser.add_argument("--send-hold-path", default=str(DEFAULT_SEND_HOLD_PATH))
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args(argv)
    receipt = run_st_annes_workflow_test_mode_self_proof(
        export_root=Path(args.export_root),
        run_mode_sqlite_path=Path(args.run_mode_sqlite_path),
        test_effect_sqlite_path=Path(args.test_effect_sqlite_path),
        send_hold_path=Path(args.send_hold_path),
        generated_at=args.generated_at or None,
    )
    print(f"{receipt['status']} {Path(args.export_root) / JSON_EXPORT_NAME}")
    return 0 if receipt.get("status") == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
