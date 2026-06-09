"""Global OpenClaw run mode context V0.

Run mode is a backend-wide operating context. This module persists and resolves
production/test mode state, marks test artifacts, and rejects test-only proof
from production paths. It does not execute external effects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Global Run Mode Context.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/global_run_mode_context.sqlite")

SCHEMA_VERSION = "global_run_mode_context_v0"
READ_MODEL_ID = "global_run_mode_context"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_GLOBAL_RUN_MODE_CONTEXT_READY"
NOT_READY_STATUS = "OPENCLAW_GLOBAL_RUN_MODE_CONTEXT_NOT_READY"

RUN_MODE_CONTEXT_SCHEMA = "RUN_MODE_CONTEXT_V0"
RUN_MODE_SET_REQUEST_SCHEMA = "OPERATOR_RUN_MODE_SET_REQUEST_V0"
RUN_MODE_STATE_SCHEMA = "OPERATOR_RUN_MODE_STATE_V0"
RUN_MODE_TRANSITION_RECEIPT_SCHEMA = "RUN_MODE_TRANSITION_RECEIPT_V0"
TEST_ARTIFACT_REJECTION_SCHEMA = "TEST_ARTIFACT_PRODUCTION_REJECTION_V0"
TEST_EXECUTION_AUTHORITY_SCHEMA = "TEST_EXECUTION_AUTHORITY_V0"

PRODUCTION = "production"
TEST_DRY_RUN = "test_dry_run"
TEST_LIVE = "test_live"
RUN_MODES = (PRODUCTION, TEST_DRY_RUN, TEST_LIVE)
TEST_MARKER = "OPENCLAW_TEST_ONLY_DO_NOT_USE_AS_PROOF_V0"
ALLOWLISTED_TEST_EMAIL = "winshiplive@gmail.com"

RUN_MODE_SET_EVENT_TYPE = "set_run_mode"

DENIED_ACTIONS = (
    "business_email_send",
    "gmail_ui",
    "browser_or_safari",
    "coupa_submit",
    "mark_paid",
    "production_ledger_mutation",
    "production_workbook_mutation",
    "production_pdf_export",
    "git_push",
    "git_merge",
    "lm2_tool_expansion",
    "raw_authority_granted_trust",
)

AUTHORITY_BOUNDARY = {
    "business_email_send_allowed": False,
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

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "authority_granted",
    "raw_authority_granted_trusted",
    "production_proof_from_test_artifact_allowed",
    "test_authority_becomes_production_authority",
    "production_action_performed",
    "business_email_sent",
    "gmail_ui_opened",
    "browser_opened",
    "coupa_submitted",
    "paid_marked",
    "production_ledger_mutated",
    "production_workbook_mutated",
    "production_pdf_exported",
    "git_pushed",
    "git_merged",
    "secret_stored",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: object, length: int = 16) -> str:
    joined = "\0".join(stable_json(part) if isinstance(part, (dict, list)) else str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _walk(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_mode_state (
          state_ref TEXT PRIMARY KEY,
          active_run_mode TEXT NOT NULL,
          test_run_id TEXT NOT NULL,
          test_marker TEXT NOT NULL,
          scope_json TEXT NOT NULL,
          live_external_effects_allowed INTEGER NOT NULL,
          allowlisted_recipients_json TEXT NOT NULL,
          denied_actions_json TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          receipt_ref TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          state_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_mode_transition_receipts (
          receipt_ref TEXT PRIMARY KEY,
          previous_run_mode TEXT NOT NULL,
          next_run_mode TEXT NOT NULL,
          test_run_id TEXT NOT NULL,
          scope_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_artifact_rejections (
          rejection_id TEXT PRIMARY KEY,
          artifact_ref TEXT NOT NULL,
          test_run_id TEXT NOT NULL,
          test_marker TEXT NOT NULL,
          rejected_by TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL,
          rejection_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_execution_receipts (
          receipt_ref TEXT PRIMARY KEY,
          test_run_id TEXT NOT NULL,
          action_kind TEXT NOT NULL,
          created_at TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        )
        """
    )


def default_run_mode_context(*, source: str = "backend_default", generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": RUN_MODE_CONTEXT_SCHEMA,
        "run_mode": PRODUCTION,
        "test_mode": False,
        "test_run_id": "",
        "test_marker": "",
        "operator_session_id": "",
        "initiated_by_operator": False,
        "created_at": generated_at,
        "expires_at": "",
        "allowed_test_capabilities": [],
        "live_external_effects_allowed": False,
        "allowlisted_recipients": [],
        "denied_actions": list(DENIED_ACTIONS),
        "source": source,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _scope_from_request(request: Mapping[str, Any]) -> dict[str, str]:
    context = request.get("current_context") if isinstance(request.get("current_context"), Mapping) else {}
    return {
        "scope": str(request.get("requested_scope") or "session"),
        "target_world_ref": str(request.get("current_world_ref") or context.get("current_world_ref") or ""),
        "target_thread_ref": str(request.get("current_thread_ref") or context.get("current_thread_ref") or ""),
        "target_project_ref": str(request.get("target_project_ref") or ""),
    }


def _expires_at(run_mode: str, generated_at: str) -> str:
    if run_mode == PRODUCTION:
        return ""
    base = datetime.fromisoformat(generated_at)
    return (base + timedelta(hours=4)).isoformat(timespec="seconds")


def build_run_mode_state(
    *,
    run_mode: str,
    scope: Mapping[str, Any],
    generated_at: str,
    test_run_id: str = "",
    live_external_effects_allowed: bool = False,
    allowlisted_recipients: Sequence[str] = (),
    receipt_ref: str = "",
) -> dict[str, Any]:
    test_mode = run_mode in {TEST_DRY_RUN, TEST_LIVE}
    test_run_id = test_run_id or (f"test_run:{_short_hash(run_mode, scope, generated_at)}" if test_mode else "")
    state_ref = f"operator_run_mode_state:{_short_hash(run_mode, scope)}"
    state = {
        "schema_version": RUN_MODE_STATE_SCHEMA,
        "active_run_mode": run_mode,
        "test_run_id": test_run_id,
        "test_marker": TEST_MARKER if test_mode else "",
        "scope": dict(scope),
        "live_external_effects_allowed": bool(live_external_effects_allowed and run_mode == TEST_LIVE),
        "allowlisted_recipients": list(allowlisted_recipients) if run_mode == TEST_LIVE else [],
        "denied_actions": list(DENIED_ACTIONS),
        "expires_at": _expires_at(run_mode, generated_at),
        "state_ref": state_ref,
        "receipt_ref": receipt_ref or f"run_mode_transition_receipt:{_short_hash(run_mode, scope, generated_at)}",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return state


def context_from_state(state: Mapping[str, Any], *, source: str = "backend_state", generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    run_mode = str(state.get("active_run_mode") or PRODUCTION)
    test_mode = run_mode in {TEST_DRY_RUN, TEST_LIVE}
    return {
        "schema_version": RUN_MODE_CONTEXT_SCHEMA,
        "run_mode": run_mode,
        "test_mode": test_mode,
        "test_run_id": str(state.get("test_run_id") or ""),
        "test_marker": str(state.get("test_marker") or (TEST_MARKER if test_mode else "")),
        "operator_session_id": "",
        "initiated_by_operator": source != "backend_default",
        "created_at": generated_at,
        "expires_at": str(state.get("expires_at") or ""),
        "allowed_test_capabilities": ["test_sqlite_write", "dry_run_email_receipt"] if run_mode == TEST_DRY_RUN else ["allowlisted_live_test_email"] if run_mode == TEST_LIVE else [],
        "live_external_effects_allowed": state.get("live_external_effects_allowed") is True,
        "allowlisted_recipients": list(state.get("allowlisted_recipients") or []),
        "denied_actions": list(state.get("denied_actions") or DENIED_ACTIONS),
        "source": source,
        "state_ref": str(state.get("state_ref") or ""),
        "receipt_ref": str(state.get("receipt_ref") or ""),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def load_active_run_mode_state(sqlite_path: Path) -> dict[str, Any] | None:
    sqlite_path = _rooted(sqlite_path)
    if not sqlite_path.exists():
        return None
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        row = conn.execute(
            """
            SELECT state_json
            FROM run_mode_state
            WHERE status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(str(row[0]))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _persist_state(sqlite_path: Path, state: Mapping[str, Any], *, generated_at: str) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        conn.execute("UPDATE run_mode_state SET status = 'inactive', updated_at = ?", (generated_at,))
        scope_json = stable_json(state.get("scope") or {})
        conn.execute(
            """
            INSERT OR REPLACE INTO run_mode_state
            (state_ref, active_run_mode, test_run_id, test_marker, scope_json, live_external_effects_allowed,
             allowlisted_recipients_json, denied_actions_json, expires_at, receipt_ref, status, created_at, updated_at, state_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                str(state.get("state_ref") or ""),
                str(state.get("active_run_mode") or PRODUCTION),
                str(state.get("test_run_id") or ""),
                str(state.get("test_marker") or ""),
                scope_json,
                1 if state.get("live_external_effects_allowed") is True else 0,
                stable_json(state.get("allowlisted_recipients") or []),
                stable_json(state.get("denied_actions") or []),
                str(state.get("expires_at") or ""),
                str(state.get("receipt_ref") or ""),
                generated_at,
                generated_at,
                stable_json(state),
            ),
        )


def _store_transition(sqlite_path: Path, receipt: Mapping[str, Any]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO run_mode_transition_receipts
            (receipt_ref, previous_run_mode, next_run_mode, test_run_id, scope_json, created_at, receipt_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(receipt.get("receipt_ref") or ""),
                str(receipt.get("previous_run_mode") or ""),
                str(receipt.get("next_run_mode") or ""),
                str(receipt.get("test_run_id") or ""),
                stable_json(receipt.get("scope") or {}),
                str(receipt.get("created_at") or ""),
                stable_json(receipt),
            ),
        )


def _valid_test_live_authority(request: Mapping[str, Any], recipients: Sequence[str]) -> bool:
    authority = request.get("test_execution_authority")
    if not isinstance(authority, Mapping):
        return False
    return (
        authority.get("schema_version") == TEST_EXECUTION_AUTHORITY_SCHEMA
        and authority.get("verifier_status") == "VERIFIED_TEST_AUTHORITY"
        and authority.get("live_external_effects_allowed") is True
        and all(recipient == ALLOWLISTED_TEST_EMAIL for recipient in recipients)
    )


def handle_run_mode_set_request(
    sqlite_path: Path,
    request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    previous = load_active_run_mode_state(sqlite_path)
    previous_mode = str((previous or {}).get("active_run_mode") or PRODUCTION)
    requested = str(request.get("requested_run_mode") or request.get("run_mode") or PRODUCTION).strip().lower()
    if requested not in RUN_MODES:
        requested = PRODUCTION
    recipients = [str(item).strip().lower() for item in request.get("allowlisted_recipients") or [] if str(item).strip()]
    blockers: list[str] = []
    if requested == TEST_LIVE:
        if request.get("authority_granted") is True:
            blockers.append("raw_authority_granted_not_accepted")
        if not _valid_test_live_authority(request, recipients):
            blockers.append("verified_test_execution_authority_required")
        if ALLOWLISTED_TEST_EMAIL not in recipients:
            blockers.append("allowlisted_test_recipient_required")
    live_allowed = requested == TEST_LIVE and not blockers
    scope = _scope_from_request(request)
    state = build_run_mode_state(
        run_mode=requested if not blockers else previous_mode,
        scope=scope,
        generated_at=generated_at,
        live_external_effects_allowed=live_allowed,
        allowlisted_recipients=recipients if live_allowed else [],
    )
    receipt = {
        "schema_version": RUN_MODE_TRANSITION_RECEIPT_SCHEMA,
        "previous_run_mode": previous_mode,
        "next_run_mode": state["active_run_mode"],
        "test_run_id": state["test_run_id"],
        "scope": scope,
        "created_at": generated_at,
        "denied_actions_preserved": list(DENIED_ACTIONS),
        "receipt_ref": state["receipt_ref"],
        "blockers": blockers,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    if not blockers:
        _persist_state(sqlite_path, state, generated_at=generated_at)
        _store_transition(sqlite_path, receipt)
    status = "RUN_MODE_SET" if not blockers else "RUN_MODE_SET_BLOCKED"
    return {
        "schema_version": RUN_MODE_SET_REQUEST_SCHEMA,
        "status": status,
        "requested_run_mode": requested,
        "run_mode_state": state,
        "transition_receipt": receipt,
        "run_mode_context": context_from_state(state, source="controller_event", generated_at=generated_at),
        "blockers": blockers,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _request_run_mode_hint(request: Mapping[str, Any]) -> str:
    event = request.get("event") if isinstance(request.get("event"), Mapping) else {}
    for key in ("run_mode", "requested_run_mode"):
        value = request.get(key) or event.get(key)
        if str(value or "").strip().lower() in RUN_MODES:
            return str(value).strip().lower()
    text = str(request.get("operator_text") or request.get("text") or "")
    if "run this as a test" in text.lower() or "dry-run" in text.lower() or "dry run" in text.lower():
        return TEST_DRY_RUN
    return ""


def _payload_has_test_marker(value: Any) -> bool:
    if isinstance(value, str):
        return TEST_MARKER in value
    if isinstance(value, Mapping):
        return any(_payload_has_test_marker(child) for child in value.values())
    if isinstance(value, list):
        return any(_payload_has_test_marker(child) for child in value)
    return False


def resolve_run_mode_context(
    sqlite_path: Path,
    request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    state = load_active_run_mode_state(sqlite_path)
    context = context_from_state(state, source="backend_state", generated_at=generated_at) if state else default_run_mode_context(generated_at=generated_at)
    requested = _request_run_mode_hint(request)
    rejected = False
    blockers: list[str] = []
    if requested == TEST_DRY_RUN and context["run_mode"] == PRODUCTION:
        # Request-scoped dry-run is safe and non-persistent.
        temp_state = build_run_mode_state(
            run_mode=TEST_DRY_RUN,
            scope=_scope_from_request(request),
            generated_at=generated_at,
            receipt_ref=f"run_mode_request_scoped:{_short_hash(request, generated_at)}",
        )
        context = context_from_state(temp_state, source="controller_event", generated_at=generated_at)
    elif requested == TEST_LIVE and context["run_mode"] != TEST_LIVE:
        rejected = True
        blockers.append("test_live_requested_without_active_backend_test_live_state")
    if _payload_has_test_marker(request) and context["run_mode"] == PRODUCTION:
        rejected = True
        blockers.append("test_artifact_marker_rejected_in_production")
    context["resolution_status"] = "rejected" if rejected else "resolved"
    context["blockers"] = blockers
    return context


def build_test_artifact_rejection(
    artifact_ref: str,
    *,
    test_run_id: str,
    rejected_by: str,
    reason: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": TEST_ARTIFACT_REJECTION_SCHEMA,
        "rejection_id": f"test_artifact_rejection:{_short_hash(artifact_ref, test_run_id, reason)}",
        "artifact_ref": artifact_ref,
        "test_run_id": test_run_id,
        "test_marker": TEST_MARKER,
        "rejected_by": rejected_by,
        "reason": reason,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def reject_test_artifact_in_production(
    sqlite_path: Path,
    artifact: Mapping[str, Any],
    *,
    rejected_by: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if not _payload_has_test_marker(artifact):
        return {"schema_version": TEST_ARTIFACT_REJECTION_SCHEMA, "rejected": False, "reason": "no_test_marker"}
    rejection = build_test_artifact_rejection(
        str(artifact.get("artifact_ref") or artifact.get("proof_ref") or "test_artifact"),
        test_run_id=str(artifact.get("test_run_id") or ""),
        rejected_by=rejected_by,
        reason="test artifact cannot be used as production proof",
        generated_at=generated_at,
    )
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO test_artifact_rejections
            (rejection_id, artifact_ref, test_run_id, test_marker, rejected_by, reason, created_at, rejection_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rejection["rejection_id"],
                rejection["artifact_ref"],
                rejection["test_run_id"],
                rejection["test_marker"],
                rejection["rejected_by"],
                rejection["reason"],
                rejection["created_at"],
                stable_json(rejection),
            ),
        )
    rejection["rejected"] = True
    return rejection


def production_claim_accepts_artifact(artifact: Mapping[str, Any], claim_kind: str) -> bool:
    if _payload_has_test_marker(artifact):
        return claim_kind in {
            "test_mode_dry_run_completed",
            "test_sqlite_write_completed",
            "live_test_email_accepted_for_allowlisted_recipient",
            "production_rejection_guard_worked",
        }
    return True


def build_test_execution_receipt(
    sqlite_path: Path,
    *,
    run_mode_context: Mapping[str, Any],
    action_kind: str,
    target_ref: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    run_mode = str(run_mode_context.get("run_mode") or PRODUCTION)
    test_run_id = str(run_mode_context.get("test_run_id") or "")
    if run_mode == PRODUCTION:
        status = "TEST_ADAPTER_BLOCKED_IN_PRODUCTION"
        performed = False
    elif run_mode == TEST_DRY_RUN:
        status = "DRY_RUN_ONLY"
        performed = False
    elif run_mode == TEST_LIVE:
        status = "TEST_LIVE_REQUIRES_ALLOWLISTED_ADAPTER"
        performed = False
    else:
        status = "UNKNOWN_RUN_MODE_BLOCKED"
        performed = False
    receipt = {
        "schema_version": "TEST_EXECUTION_RECEIPT_V0",
        "receipt_ref": f"test_execution_receipt:{_short_hash(run_mode, action_kind, target_ref, generated_at)}",
        "run_mode": run_mode,
        "test_run_id": test_run_id,
        "test_marker": TEST_MARKER if run_mode in {TEST_DRY_RUN, TEST_LIVE} else "",
        "action_kind": action_kind,
        "target_ref": target_ref,
        "status": status,
        "external_effect_performed": performed,
        "production_action_performed": False,
        "production_write_performed": False,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "portal_submit_performed": False,
        "ledger_mutation_performed": False,
        "paid_marking_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    if run_mode in {TEST_DRY_RUN, TEST_LIVE}:
        sqlite_path = _rooted(sqlite_path)
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(sqlite_path) as conn:
            _ensure_tables(conn)
            conn.execute(
                """
                INSERT OR REPLACE INTO test_execution_receipts
                (receipt_ref, test_run_id, action_kind, created_at, receipt_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (receipt["receipt_ref"], test_run_id, action_kind, generated_at, stable_json(receipt)),
            )
    return receipt


def build_contract_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contracts": [
            RUN_MODE_CONTEXT_SCHEMA,
            RUN_MODE_SET_REQUEST_SCHEMA,
            RUN_MODE_STATE_SCHEMA,
            RUN_MODE_TRANSITION_RECEIPT_SCHEMA,
            TEST_ARTIFACT_REJECTION_SCHEMA,
        ],
        "run_modes": list(RUN_MODES),
        "global_test_marker": TEST_MARKER,
        "default_run_mode": PRODUCTION,
        "test_live_constraints": {
            "requires_test_execution_authority": True,
            "allowlisted_recipients": [ALLOWLISTED_TEST_EMAIL],
            "max_live_email_sends_per_test_run_id": 1,
            "business_or_client_email_allowed": False,
        },
        "production_rejection_policy": {
            "test_artifacts_cannot_support_business_truth": True,
            "blocked_claims": [
                "client_was_emailed",
                "client_replied",
                "payment_received",
                "ledger_updated",
                "coupa_submitted",
                "invoice_acknowledged",
                "contact_saved_as_verified",
                "production_capability_executed",
            ],
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    payload["unsafe_true_grants"] = unsafe_true_grants(payload)
    if payload["unsafe_true_grants"]:
        payload["status"] = NOT_READY_STATUS
    return payload


def _write_sqlite(sqlite_path: Path, payload: Mapping[str, Any]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_tables(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS global_run_mode_context (
              read_model_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              generated_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO global_run_mode_context VALUES (?, ?, ?, ?)",
            (
                str(payload.get("read_model_id") or READ_MODEL_ID),
                str(payload.get("status") or ""),
                str(payload.get("generated_at") or ""),
                stable_json(payload),
            ),
        )


def build_wiki(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Global Run Mode Context",
        "",
        f"Status: `{payload.get('status', NOT_READY_STATUS)}`",
        "",
        "Run mode is a backend source of truth for production, dry-run test, and controlled live-test behavior.",
        "",
        "## Contracts",
        "",
    ]
    for contract in payload.get("contracts", []):
        lines.append(f"- `{contract}`")
    lines.extend(
        [
            "",
            "## Rules",
            "",
            f"- Production is the default when no state exists.",
            f"- Test artifacts carry `{TEST_MARKER}`.",
            "- Production proof rejects test-only artifacts.",
            "- Test-live requires verified test execution authority and an allowlisted recipient.",
            "- Run mode does not grant protected business authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_global_run_mode_context(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    payload = build_contract_read_model(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, payload)
    _write_sqlite(sqlite_path, payload)
    bridge_path = ""
    if bridge_root is not None:
        bridge = _rooted(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        bridge_target = bridge / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_target)
        bridge_path = bridge_target.as_posix()
    wiki = _rooted(wiki_path)
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(build_wiki(payload), encoding="utf-8")
    return {
        "status": str(payload.get("status") or NOT_READY_STATUS),
        "read_model_path": read_model_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish global run mode context.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args(argv)
    result = export_global_run_mode_context(
        export_root=Path(args.export_root),
        bridge_root=Path(args.bridge_root) if args.bridge_root else None,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
