"""Universal OpenClaw test effect adapters.

These adapters make Test Mode useful without contaminating production. They
never mutate production ledger/workbook/PDF paths, open Gmail/browser/Coupa,
mark paid, push/merge, or trust raw authority grants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import global_run_mode_context


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Test Effect Adapters.md")
DEFAULT_SQLITE_PATH = Path("generated/test_effects/test_effect_adapters.sqlite")
DEFAULT_WORKSPACE_ROOT = Path("/tmp/openclaw-mission-control/test_workspaces")

SCHEMA_VERSION = "test_effect_adapters_v0"
READ_MODEL_ID = "test_effect_adapters"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_TEST_EFFECT_ADAPTERS_READY"

TEST_EFFECT_REQUEST_SCHEMA = "TEST_EFFECT_REQUEST_V0"
TEST_EFFECT_RECEIPT_SCHEMA = "TEST_EFFECT_RECEIPT_V0"
TEST_TARGET_REDIRECT_SCHEMA = "TEST_TARGET_REDIRECT_V0"
TEST_WORKSPACE_ARTIFACT_SCHEMA = "TEST_WORKSPACE_ARTIFACT_V0"
TEST_EXECUTION_AUTHORITY_SCHEMA = global_run_mode_context.TEST_EXECUTION_AUTHORITY_SCHEMA

SQLITE_WRITE = "sqlite_write"
EMAIL_SEND = "email_send"
CALENDAR_EVENT = "calendar_event"
FILE_WORKSPACE_COPY = "file_workspace_copy"
FILE_WRITE = "file_write"
LOGIC_PROJECT_COPY = "logic_project_copy"
EFFECT_KINDS = {
    SQLITE_WRITE,
    EMAIL_SEND,
    CALENDAR_EVENT,
    FILE_WORKSPACE_COPY,
    FILE_WRITE,
    LOGIC_PROJECT_COPY,
}

DRY_RUN_RECORDED = "DRY_RUN_RECORDED"
TEST_LIVE_EXECUTED = "TEST_LIVE_EXECUTED"
TEST_ADAPTER_MISSING = "TEST_ADAPTER_MISSING"
BLOCKED_BY_ALLOWLIST = "BLOCKED_BY_ALLOWLIST"
BLOCKED_BY_RUN_MODE = "BLOCKED_BY_RUN_MODE"
BLOCKED_BY_AUTHORITY = "BLOCKED_BY_AUTHORITY"
FAILED = "FAILED"

TEST_MARKER = global_run_mode_context.TEST_MARKER
ALLOWLISTED_TEST_EMAIL = global_run_mode_context.ALLOWLISTED_TEST_EMAIL

DENIED_ACTIONS = tuple(global_run_mode_context.DENIED_ACTIONS) + (
    "cc_bcc_email",
    "email_attachment_send",
    "mutate_original_file",
    "launch_logic_pro",
)

AUTHORITY_BOUNDARY = {
    "business_email_send_allowed": False,
    "calendar_access_allowed": False,
    "calendar_event_create_allowed": False,
    "calendar_event_delete_allowed": False,
    "gmail_ui_allowed": False,
    "browser_access_allowed": False,
    "coupa_submit_allowed": False,
    "paid_marking_allowed": False,
    "production_ledger_mutation_allowed": False,
    "production_workbook_mutation_allowed": False,
    "production_pdf_export_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "lm2_tool_expansion_allowed": False,
    "secrets_storage_allowed": False,
    "authority_granted_from_raw_text_allowed": False,
    "sent": False,
    "paid": False,
}

PRODUCTION_REJECTED_CLAIMS = {
    "client_was_emailed",
    "email_sent_to_client",
    "annette_replied",
    "live_arts_accountant_identified",
    "glenn_acknowledged",
    "paid",
    "ledger_updated",
    "coupa_submitted",
    "production_file_updated",
    "production_workbook_updated",
    "production_pdf_updated",
    "contact_saved_as_verified",
}

ALLOWED_TEST_CLAIMS = {
    "test_dry_run_recorded",
    "test_sqlite_write_recorded",
    "test_workspace_copy_created",
    "test_calendar_event_dry_run_recorded",
    "test_live_email_sent_to_allowlisted_recipient",
    "production_rejection_guard_worked",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


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


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS test_effect_receipts (
          effect_id TEXT PRIMARY KEY,
          effect_kind TEXT NOT NULL,
          run_mode TEXT NOT NULL,
          test_run_id TEXT NOT NULL,
          status TEXT NOT NULL,
          actual_target TEXT NOT NULL,
          external_effect INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS test_sqlite_rows (
          row_id TEXT PRIMARY KEY,
          effect_id TEXT NOT NULL,
          run_mode TEXT NOT NULL,
          test_run_id TEXT NOT NULL,
          test_marker TEXT NOT NULL,
          payload_summary TEXT NOT NULL,
          production_safe INTEGER NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS test_workspace_artifacts (
          artifact_ref TEXT PRIMARY KEY,
          effect_id TEXT NOT NULL,
          original_path TEXT NOT NULL,
          test_copy_path TEXT NOT NULL,
          test_run_id TEXT NOT NULL,
          test_marker TEXT NOT NULL,
          artifact_kind TEXT NOT NULL,
          created_at TEXT NOT NULL,
          artifact_json TEXT NOT NULL
        );
        """
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _redact_target(value: str) -> str:
    target = str(value or "").strip()
    if "@" in target:
        local, _, domain = target.partition("@")
        return f"{local[:1]}***@{domain}" if domain else "***"
    if len(target) > 80:
        return target[:32] + "..." + target[-16:]
    return target


def _safe_test_run_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "test_run"))
    return safe[:80] or "test_run"


def _context_from_request(request: Mapping[str, Any]) -> dict[str, Any]:
    context = request.get("run_mode_context")
    if isinstance(context, Mapping):
        return dict(context)
    return global_run_mode_context.default_run_mode_context()


def _scope_from_request(request: Mapping[str, Any]) -> dict[str, str]:
    scope = request.get("requested_scope") if isinstance(request.get("requested_scope"), Mapping) else {}
    return {
        "target_world_ref": str(scope.get("target_world_ref") or request.get("current_world_ref") or ""),
        "target_thread_ref": str(scope.get("target_thread_ref") or request.get("current_thread_ref") or ""),
        "target_project_ref": str(scope.get("target_project_ref") or request.get("target_project_ref") or ""),
    }


def test_effect_id(effect_kind: str, run_mode_context: Mapping[str, Any], target: str, payload_summary: str) -> str:
    return f"test_effect:{_short_hash(effect_kind, run_mode_context.get('test_run_id'), target, payload_summary)}"


def build_test_effect_request(
    *,
    effect_kind: str,
    run_mode_context: Mapping[str, Any],
    target: str,
    payload_summary: str,
    requested_by: str = "operator_controller",
    requested_scope: Mapping[str, Any] | None = None,
    allowlist: Sequence[str] = (),
    requires_test_live: bool | None = None,
    requires_test_authority: bool | None = None,
    original_target: str = "",
    source_path: str = "",
    content: str = "",
    email_subject: str = "",
    email_body: str = "",
    cc: Sequence[str] = (),
    bcc: Sequence[str] = (),
    attachments: Sequence[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if effect_kind not in EFFECT_KINDS:
        effect_kind = FILE_WRITE
    context = dict(run_mode_context)
    run_mode = str(context.get("run_mode") or global_run_mode_context.PRODUCTION)
    test_run_id = str(context.get("test_run_id") or "")
    if requires_test_live is None:
        requires_test_live = effect_kind in {EMAIL_SEND, CALENDAR_EVENT, SQLITE_WRITE, FILE_WORKSPACE_COPY, FILE_WRITE, LOGIC_PROJECT_COPY}
    if requires_test_authority is None:
        requires_test_authority = effect_kind in {EMAIL_SEND, CALENDAR_EVENT, SQLITE_WRITE, FILE_WORKSPACE_COPY, FILE_WRITE, LOGIC_PROJECT_COPY}
    target_value = str(target or original_target or source_path or "")
    request = {
        "schema_version": TEST_EFFECT_REQUEST_SCHEMA,
        "effect_id": test_effect_id(effect_kind, context, target_value, payload_summary),
        "effect_kind": effect_kind,
        "run_mode": run_mode,
        "test_run_id": test_run_id,
        "test_marker": TEST_MARKER if run_mode in {global_run_mode_context.TEST_DRY_RUN, global_run_mode_context.TEST_LIVE} else "",
        "requested_by": requested_by,
        "requested_scope": dict(requested_scope or {}),
        "payload_summary": str(payload_summary or ""),
        "target": target_value,
        "allowlist": list(allowlist),
        "denied_actions": list(DENIED_ACTIONS),
        "requires_test_live": bool(requires_test_live),
        "requires_test_authority": bool(requires_test_authority),
        "created_at": generated_at,
        "run_mode_context": context,
        "original_target": str(original_target or target_value),
        "source_path": str(source_path or ""),
        "content": str(content or ""),
        "email_subject": str(email_subject or ""),
        "email_body": str(email_body or ""),
        "cc": list(cc),
        "bcc": list(bcc),
        "attachments": list(attachments),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return request


def _valid_test_authority(authority: Mapping[str, Any] | None, effect_kind: str, target: str, test_run_id: str) -> bool:
    if not isinstance(authority, Mapping):
        return False
    if authority.get("schema_version") != TEST_EXECUTION_AUTHORITY_SCHEMA:
        return False
    if authority.get("verifier_status") != "VERIFIED_TEST_AUTHORITY":
        return False
    allowed_effects = set(authority.get("allowed_effect_kinds") or [])
    if allowed_effects and effect_kind not in allowed_effects:
        return False
    if effect_kind == EMAIL_SEND:
        recipients = {str(item).lower() for item in authority.get("allowlisted_recipients") or []}
        if ALLOWLISTED_TEST_EMAIL not in recipients:
            return False
    max_effects = authority.get("max_external_effects")
    if effect_kind == EMAIL_SEND and max_effects is not None and int(max_effects) < 1:
        return False
    scope_run = str(authority.get("test_run_id") or "")
    return not scope_run or scope_run == test_run_id


def build_target_redirect(original_target: str, redirected_target: str, *, reason: str, test_run_id: str) -> dict[str, Any]:
    return {
        "schema_version": TEST_TARGET_REDIRECT_SCHEMA,
        "original_target_redacted": _redact_target(original_target),
        "redirected_target": redirected_target,
        "reason": reason,
        "allowlist_rule": f"V0 allows only {ALLOWLISTED_TEST_EMAIL} for test email",
        "test_run_id": test_run_id,
        "test_marker": TEST_MARKER,
    }


def _base_receipt(request: Mapping[str, Any], *, status: str, actual_target: str, generated_at: str, external_effect: bool = False) -> dict[str, Any]:
    return {
        "schema_version": TEST_EFFECT_RECEIPT_SCHEMA,
        "effect_id": str(request.get("effect_id") or ""),
        "effect_kind": str(request.get("effect_kind") or ""),
        "run_mode": str(request.get("run_mode") or ""),
        "test_run_id": str(request.get("test_run_id") or ""),
        "test_marker": str(request.get("test_marker") or ""),
        "status": status,
        "actual_target": actual_target,
        "original_target_redacted": _redact_target(str(request.get("original_target") or request.get("target") or "")),
        "artifact_ref": "",
        "external_effect": external_effect,
        "production_safe": False,
        "production_write_performed": False,
        "email_send_performed": False,
        "calendar_api_called": False,
        "calendar_event_created": False,
        "calendar_event_deleted": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "portal_submit_performed": False,
        "ledger_mutation_performed": False,
        "paid_marking_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "created_at": generated_at,
        "verifier_status": "VERIFIED_TEST_ONLY" if status in {DRY_RUN_RECORDED, TEST_LIVE_EXECUTED, TEST_ADAPTER_MISSING} else "BLOCKED",
        "target_redirect": {},
        "adapter_missing_reason": "",
        "workspace_artifact": {},
        "email_preview": {},
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "test_marker_present": bool(request.get("test_marker")),
            "production_action_performed": False,
            "business_email_send_performed": False,
            "calendar_api_called": False,
            "calendar_event_created": False,
            "calendar_event_deleted": False,
            "gmail_ui_opened": False,
            "browser_opened": False,
            "coupa_submitted": False,
            "paid_marked": False,
            "production_ledger_mutated": False,
            "production_workbook_mutated": False,
            "production_pdf_exported": False,
            "git_pushed": False,
            "git_merged": False,
            "raw_authority_granted_trusted": False,
            "original_file_mutated": False,
        },
    }


def _store_receipt(sqlite_path: Path, receipt: Mapping[str, Any]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO test_effect_receipts
            (effect_id, effect_kind, run_mode, test_run_id, status, actual_target, external_effect, created_at, receipt_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt["effect_id"],
                receipt["effect_kind"],
                receipt["run_mode"],
                receipt["test_run_id"],
                receipt["status"],
                receipt["actual_target"],
                1 if receipt["external_effect"] else 0,
                receipt["created_at"],
                stable_json(receipt),
            ),
        )


def _sqlite_write(sqlite_path: Path, request: Mapping[str, Any], generated_at: str, authority: Mapping[str, Any] | None) -> dict[str, Any]:
    run_mode = str(request.get("run_mode") or "")
    target = str(request.get("target") or "test_sqlite_rows")
    if run_mode == global_run_mode_context.PRODUCTION:
        return _base_receipt(request, status=BLOCKED_BY_RUN_MODE, actual_target=target, generated_at=generated_at)
    if run_mode == global_run_mode_context.TEST_DRY_RUN:
        return _base_receipt(request, status=DRY_RUN_RECORDED, actual_target=target, generated_at=generated_at)
    if not _valid_test_authority(authority, SQLITE_WRITE, target, str(request.get("test_run_id") or "")):
        return _base_receipt(request, status=BLOCKED_BY_AUTHORITY, actual_target=target, generated_at=generated_at)
    receipt = _base_receipt(request, status=TEST_LIVE_EXECUTED, actual_target="generated/test_effects/test_effect_adapters.sqlite:test_sqlite_rows", generated_at=generated_at)
    row_id = f"test_sqlite_row:{_short_hash(request.get('effect_id'), generated_at)}"
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO test_sqlite_rows
            (row_id, effect_id, run_mode, test_run_id, test_marker, payload_summary, production_safe, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                request["effect_id"],
                run_mode,
                request["test_run_id"],
                TEST_MARKER,
                str(request.get("payload_summary") or ""),
                0,
                generated_at,
            ),
        )
    receipt["artifact_ref"] = row_id
    receipt["sqlite_row_ref"] = row_id
    receipt["machine_proof"]["test_sqlite_row_written"] = True
    return receipt


def _normalize_test_email(request: Mapping[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    original = str(request.get("target") or "")
    target = ALLOWLISTED_TEST_EMAIL
    subject = str(request.get("email_subject") or "OpenClaw test email").strip()
    if not subject.startswith("[OPENCLAW TEST]"):
        subject = f"[OPENCLAW TEST] {subject}"
    body = str(request.get("email_body") or "This is a controlled OpenClaw test email.").strip()
    prefix = f"{TEST_MARKER}\nTest run: {request.get('test_run_id')}\nThis is a controlled OpenClaw test email.\n\n"
    if not body.startswith(TEST_MARKER):
        body = prefix + body
    redirect = build_target_redirect(original, target, reason="non-production test email redirects to allowlisted V0 recipient", test_run_id=str(request.get("test_run_id") or ""))
    return target, subject, body, redirect


def _email_send(sqlite_path: Path, request: Mapping[str, Any], generated_at: str, authority: Mapping[str, Any] | None, email_transport_available: bool) -> dict[str, Any]:
    run_mode = str(request.get("run_mode") or "")
    target, subject, body, redirect = _normalize_test_email(request)
    if run_mode == global_run_mode_context.PRODUCTION:
        return _base_receipt(request, status=BLOCKED_BY_RUN_MODE, actual_target=target, generated_at=generated_at)
    if request.get("cc") or request.get("bcc") or request.get("attachments"):
        receipt = _base_receipt(request, status=BLOCKED_BY_ALLOWLIST, actual_target=target, generated_at=generated_at)
        receipt["adapter_missing_reason"] = "V0 test email does not allow CC, BCC, or attachments."
        return receipt
    if run_mode == global_run_mode_context.TEST_DRY_RUN:
        receipt = _base_receipt(request, status=DRY_RUN_RECORDED, actual_target=target, generated_at=generated_at)
        receipt["target_redirect"] = redirect
        receipt["email_preview"] = {"to": target, "subject": subject, "body_preview": body[:240], "body_has_test_marker": body.startswith(TEST_MARKER)}
        return receipt
    if not _valid_test_authority(authority, EMAIL_SEND, target, str(request.get("test_run_id") or "")):
        receipt = _base_receipt(request, status=BLOCKED_BY_AUTHORITY, actual_target=target, generated_at=generated_at)
        receipt["target_redirect"] = redirect
        return receipt
    if target != ALLOWLISTED_TEST_EMAIL:
        return _base_receipt(request, status=BLOCKED_BY_ALLOWLIST, actual_target=target, generated_at=generated_at)
    if _count_live_test_emails(sqlite_path, str(request.get("test_run_id") or "")) >= 1:
        receipt = _base_receipt(request, status=BLOCKED_BY_ALLOWLIST, actual_target=target, generated_at=generated_at)
        receipt["adapter_missing_reason"] = "V0 max one live test email per test_run_id already reached."
        return receipt
    receipt = _base_receipt(request, status=TEST_ADAPTER_MISSING, actual_target=target, generated_at=generated_at)
    receipt["target_redirect"] = redirect
    receipt["email_preview"] = {"to": target, "subject": subject, "body_preview": body[:240], "body_has_test_marker": body.startswith(TEST_MARKER)}
    receipt["adapter_missing_reason"] = "No safe email transport is configured for test_live V0; credentials/secrets were not read."
    return receipt


def _calendar_event(sqlite_path: Path, request: Mapping[str, Any], generated_at: str, authority: Mapping[str, Any] | None) -> dict[str, Any]:
    run_mode = str(request.get("run_mode") or "")
    target = str(request.get("target") or "test_calendar")
    if run_mode == global_run_mode_context.PRODUCTION:
        return _base_receipt(request, status=BLOCKED_BY_RUN_MODE, actual_target=target, generated_at=generated_at)
    if run_mode == global_run_mode_context.TEST_DRY_RUN:
        receipt = _base_receipt(request, status=DRY_RUN_RECORDED, actual_target=target, generated_at=generated_at)
        receipt["calendar_preview"] = {
            "calendar_ref": target,
            "payload_summary": str(request.get("payload_summary") or ""),
            "calendar_api_called": False,
            "calendar_event_created": False,
            "calendar_event_deleted": False,
            "body_has_test_marker": str(request.get("content") or request.get("payload_summary") or "").startswith(TEST_MARKER),
        }
        receipt["adapter_missing_reason"] = "Calendar dry-run recorded only; no Calendar API call or event mutation was performed."
        return receipt
    if not _valid_test_authority(authority, CALENDAR_EVENT, target, str(request.get("test_run_id") or "")):
        return _base_receipt(request, status=BLOCKED_BY_AUTHORITY, actual_target=target, generated_at=generated_at)
    receipt = _base_receipt(request, status=TEST_ADAPTER_MISSING, actual_target=target, generated_at=generated_at)
    receipt["calendar_preview"] = {
        "calendar_ref": target,
        "payload_summary": str(request.get("payload_summary") or ""),
        "calendar_api_called": False,
        "calendar_event_created": False,
        "calendar_event_deleted": False,
    }
    receipt["adapter_missing_reason"] = "No safe Calendar transport is configured for test_live V0; credentials/secrets were not read."
    return receipt


def _count_live_test_emails(sqlite_path: Path, test_run_id: str) -> int:
    sqlite_path = _rooted(sqlite_path)
    if not sqlite_path.exists():
        return 0
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        row = conn.execute(
            """
            SELECT count(*) FROM test_effect_receipts
            WHERE effect_kind = ? AND test_run_id = ? AND status = ?
            """,
            (EMAIL_SEND, test_run_id, TEST_LIVE_EXECUTED),
        ).fetchone()
    return int(row[0] if row else 0)


def _copy_path(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def _workspace_copy(sqlite_path: Path, request: Mapping[str, Any], generated_at: str, authority: Mapping[str, Any] | None, workspace_root: Path) -> dict[str, Any]:
    run_mode = str(request.get("run_mode") or "")
    original = Path(str(request.get("source_path") or request.get("target") or ""))
    effect_kind = str(request.get("effect_kind") or FILE_WORKSPACE_COPY)
    if run_mode == global_run_mode_context.PRODUCTION:
        return _base_receipt(request, status=BLOCKED_BY_RUN_MODE, actual_target=str(original), generated_at=generated_at)
    if run_mode == global_run_mode_context.TEST_DRY_RUN:
        return _base_receipt(request, status=DRY_RUN_RECORDED, actual_target=str(original), generated_at=generated_at)
    if not _valid_test_authority(authority, effect_kind, str(original), str(request.get("test_run_id") or "")):
        return _base_receipt(request, status=BLOCKED_BY_AUTHORITY, actual_target=str(original), generated_at=generated_at)
    if not original.exists():
        receipt = _base_receipt(request, status=FAILED, actual_target=str(original), generated_at=generated_at)
        receipt["adapter_missing_reason"] = "Source path does not exist; no copy was created."
        return receipt
    test_run_safe = _safe_test_run_id(str(request.get("test_run_id") or "test_run"))
    workspace = Path(workspace_root) / test_run_safe
    workspace.mkdir(parents=True, exist_ok=True)
    marker_path = workspace / TEST_MARKER
    marker_path.write_text(TEST_MARKER + "\n", encoding="utf-8")
    if effect_kind == LOGIC_PROJECT_COPY or original.suffix.lower() == ".logicx":
        copy_name = f"{original.stem}__OPENCLAW_TEST__{test_run_safe}{original.suffix or '.logicx'}"
        artifact_kind = "logic_project"
    else:
        copy_name = f"{original.name}__OPENCLAW_TEST__{test_run_safe}"
        artifact_kind = "generic_file"
    dst = workspace / copy_name
    _copy_path(original, dst)
    artifact = {
        "schema_version": TEST_WORKSPACE_ARTIFACT_SCHEMA,
        "artifact_ref": f"test_workspace_artifact:{_short_hash(request.get('effect_id'), dst)}",
        "original_path": str(original),
        "test_copy_path": str(dst),
        "test_run_id": str(request.get("test_run_id") or ""),
        "test_marker": TEST_MARKER,
        "artifact_kind": artifact_kind,
        "created_at": generated_at,
        "production_rejection_required": True,
        "downstream_target_path": str(dst),
        "marker_file": str(marker_path),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    metadata_path = workspace / f"{artifact['artifact_ref'].replace(':', '_')}.json"
    _write_json(metadata_path, artifact)
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO test_workspace_artifacts
            (artifact_ref, effect_id, original_path, test_copy_path, test_run_id, test_marker, artifact_kind, created_at, artifact_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact["artifact_ref"],
                request["effect_id"],
                artifact["original_path"],
                artifact["test_copy_path"],
                artifact["test_run_id"],
                artifact["test_marker"],
                artifact["artifact_kind"],
                artifact["created_at"],
                stable_json(artifact),
            ),
        )
    receipt = _base_receipt(request, status=TEST_LIVE_EXECUTED, actual_target=str(dst), generated_at=generated_at)
    receipt["artifact_ref"] = artifact["artifact_ref"]
    receipt["workspace_artifact"] = artifact
    receipt["machine_proof"]["test_workspace_copy_created"] = True
    receipt["machine_proof"]["original_file_mutated"] = False
    return receipt


def execute_test_effect(
    request: Mapping[str, Any],
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    test_execution_authority: Mapping[str, Any] | None = None,
    email_transport_available: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    effect_kind = str(request.get("effect_kind") or "")
    if request.get("authority_granted") is True:
        receipt = _base_receipt(request, status=BLOCKED_BY_AUTHORITY, actual_target=str(request.get("target") or ""), generated_at=generated_at)
        receipt["adapter_missing_reason"] = "Raw authority_granted is not accepted by test effect adapters."
        _store_receipt(sqlite_path, receipt)
        return receipt
    if effect_kind == SQLITE_WRITE:
        receipt = _sqlite_write(sqlite_path, request, generated_at, test_execution_authority)
    elif effect_kind == EMAIL_SEND:
        receipt = _email_send(sqlite_path, request, generated_at, test_execution_authority, email_transport_available)
    elif effect_kind == CALENDAR_EVENT:
        receipt = _calendar_event(sqlite_path, request, generated_at, test_execution_authority)
    elif effect_kind in {FILE_WORKSPACE_COPY, FILE_WRITE, LOGIC_PROJECT_COPY}:
        receipt = _workspace_copy(sqlite_path, request, generated_at, test_execution_authority, workspace_root)
    else:
        receipt = _base_receipt(request, status=FAILED, actual_target=str(request.get("target") or ""), generated_at=generated_at)
        receipt["adapter_missing_reason"] = f"Unknown test effect kind: {effect_kind}"
    _store_receipt(sqlite_path, receipt)
    return receipt


def production_claim_accepts_test_artifact(artifact: Mapping[str, Any], claim_kind: str) -> bool:
    if not _has_test_marker(artifact):
        return True
    if claim_kind in ALLOWED_TEST_CLAIMS:
        return True
    if claim_kind in PRODUCTION_REJECTED_CLAIMS:
        return False
    return False


def _has_test_marker(value: Any) -> bool:
    if isinstance(value, str):
        return TEST_MARKER in value
    if isinstance(value, Mapping):
        return any(_has_test_marker(child) for child in value.values())
    if isinstance(value, list):
        return any(_has_test_marker(child) for child in value)
    return False


def build_test_execution_authority(
    *,
    test_run_id: str,
    allowed_effect_kinds: Sequence[str],
    allowlisted_recipients: Sequence[str] = (),
    max_external_effects: int = 0,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": TEST_EXECUTION_AUTHORITY_SCHEMA,
        "authority_id": f"test_execution_authority:{_short_hash(test_run_id, allowed_effect_kinds, allowlisted_recipients)}",
        "run_mode": global_run_mode_context.TEST_LIVE,
        "test_run_id": test_run_id,
        "allowed_effect_kinds": list(allowed_effect_kinds),
        "allowed_targets": [ALLOWLISTED_TEST_EMAIL] if EMAIL_SEND in allowed_effect_kinds else [],
        "allowlisted_recipients": list(allowlisted_recipients),
        "max_external_effects": int(max_external_effects),
        "expires_at": "",
        "denied_actions": list(DENIED_ACTIONS),
        "receipt_ref": f"test_execution_authority_receipt:{_short_hash(test_run_id, generated_at)}",
        "verifier_status": "VERIFIED_TEST_AUTHORITY",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_contract_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contracts": [
            TEST_EFFECT_REQUEST_SCHEMA,
            TEST_EFFECT_RECEIPT_SCHEMA,
            TEST_TARGET_REDIRECT_SCHEMA,
            TEST_WORKSPACE_ARTIFACT_SCHEMA,
            TEST_EXECUTION_AUTHORITY_SCHEMA,
        ],
        "effect_kinds": sorted(EFFECT_KINDS),
        "run_mode_behavior": {
            "production": "test effect requests and test markers are blocked from production proof",
            "test_dry_run": "dry-run receipts only; no external effects",
            "test_live": "controlled test effects only with explicit test authority, marker, allowlist, and receipts",
        },
        "email_adapter": {
            "allowlisted_recipient": ALLOWLISTED_TEST_EMAIL,
            "subject_prefix": "[OPENCLAW TEST]",
            "body_marker": TEST_MARKER,
            "max_live_email_sends_per_test_run_id": 1,
            "real_transport_configured": False,
            "live_status_without_transport": TEST_ADAPTER_MISSING,
        },
        "workspace_adapter": {
            "workspace_root": str(DEFAULT_WORKSPACE_ROOT),
            "logic_copy_suffix": "__OPENCLAW_TEST__<test_run_id>.logicx",
            "launch_logic_pro_allowed": False,
        },
        "production_rejected_claims": sorted(PRODUCTION_REJECTED_CLAIMS),
        "allowed_test_claims": sorted(ALLOWED_TEST_CLAIMS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "production_email_send_enabled": False,
            "gmail_ui_open_enabled": False,
            "browser_open_enabled": False,
            "coupa_submit_enabled": False,
            "paid_marking_enabled": False,
            "production_ledger_mutation_enabled": False,
            "production_workbook_mutation_enabled": False,
            "production_pdf_export_enabled": False,
            "push_merge_enabled": False,
            "external_model_enabled": False,
            "lm2_tool_expansion_enabled": False,
            "raw_authority_granted_trusted": False,
        },
    }


def build_wiki(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Test Effect Adapters",
            "",
            f"Status: `{payload['status']}`",
            "",
            "Universal adapters for useful Test Mode effects without production contamination.",
            "",
            "## Effects",
            "- SQLite: dry-run receipt or marked test row in dedicated test DB.",
            "- Email: dry-run receipt; live test requires a future safe transport and only `winshiplive@gmail.com`.",
            "- Files/Logic: copy-before-mutate into `/tmp/openclaw-mission-control/test_workspaces/`.",
            "",
            "## Production Boundary",
            f"All test artifacts carry `{TEST_MARKER}` and are rejected for production claims.",
            "",
        ]
    )


def _write_sqlite(sqlite_path: Path, payload: Mapping[str, Any]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_effect_adapters_contract (
              read_model_id TEXT PRIMARY KEY,
              generated_at TEXT NOT NULL,
              status TEXT NOT NULL,
              payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO test_effect_adapters_contract
            (read_model_id, generated_at, status, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (READ_MODEL_ID, str(payload.get("generated_at") or ""), str(payload.get("status") or ""), stable_json(payload)),
        )


def export_test_effect_adapters(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_contract_read_model(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, payload)
    wiki = _rooted(wiki_path)
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(build_wiki(payload), encoding="utf-8")
    _write_sqlite(sqlite_path, payload)
    bridge_path = ""
    if bridge_root is not None:
        bridge = Path(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        target = bridge / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, target)
        bridge_path = target.as_posix()
    return {
        "status": str(payload["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args()
    result = export_test_effect_adapters(
        export_root=Path(args.export_root),
        bridge_root=Path(args.bridge_root) if args.bridge_root else None,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
    )
    print(stable_json(result))


if __name__ == "__main__":
    main()
