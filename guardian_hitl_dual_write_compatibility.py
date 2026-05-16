"""Guardian/HITL SQLite dual-write compatibility v0.

This module records observational SQLite mirrors for selected legacy Guardian
HITL approval requests. It does not read live HITL JSON, approve decisions,
send notifications, execute actions, switch callers, or grant runtime
authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from guardian_hitl_sqlite_authority_contract import (
    FORBIDDEN_PAYLOAD_KEYS,
    OLD_HITL_CLASSIFICATION,
    validate_canonical_approval_payload,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
SCHEMA_VERSION = "guardian_hitl_dual_write_compatibility_v0"
JSON_EXPORT_NAME = "guardian_hitl_dual_write_compatibility.json"
OPERATOR_EXPORT_NAME = "guardian_hitl_dual_write_compatibility_OPERATOR.md"

CHIEF_SOURCE_SURFACE = "chief_approval_brain"
APPROVAL_PENDING_SOURCE_SURFACE = "approval_pending_json"
LEGACY_APPROVAL_PENDING_REF = "/mnt/c/OpenClaw/logs/approval_pending.json"
PAYLOAD_SCHEMA_VERSION = "legacy_chief_approval_request_observation_v0"
CHIEF_TTL_SECONDS = 86400
DECISION_LABELS = {
    "YES": ("decision_shadow_observed", "approved_observed", "approved"),
    "YES_FOR_ALL": ("decision_shadow_observed", "approved_observed", "approved_for_all"),
    "NO": ("decision_shadow_rejected", "denied_observed", "denied"),
    "TIMEOUT": ("decision_shadow_expired", "expired_observed", "expired"),
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority_changed": False,
    "runtime_authority": False,
    "dual_write_enabled": True,
    "caller_switched": False,
    "old_hitl_deleted": False,
    "legacy_json_authoritative": True,
    "raw_content_stored": False,
    "raw_action_text_stored": False,
    "raw_command_text_stored": False,
    "freeform_shell_approval_allowed": False,
    "approval_bypass_allowed": False,
    "can_approve": False,
    "can_execute": False,
    "repo_b_execution_allowed": False,
    "repo_b_code_imported": False,
    "telegram_send_added": False,
    "gmail_send_added": False,
    "email_send_added": False,
    "safe_to_import_cassandra_chief_memory": False,
    "safe_to_enable_remote_builder": False,
    "safe_to_expand_send_paths": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _bool(value: bool) -> int:
    return 1 if value else 0


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _ledger_path(db_path: str | Path | None) -> Path:
    path = Path(db_path or DEFAULT_DB_PATH)
    if path.is_absolute():
        return path
    return ROOT / path


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS guardian_hitl_approval_requests (
  approval_id TEXT PRIMARY KEY,
  source_surface_id TEXT NOT NULL,
  legacy_approval_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  target TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  payload_schema_version TEXT NOT NULL,
  source_intent_ref TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  requested_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  ttl_seconds INTEGER NOT NULL,
  authority_scope TEXT NOT NULL,
  risk_tier TEXT NOT NULL,
  status TEXT NOT NULL,
  request_receipt_id TEXT NOT NULL,
  legacy_json_ref TEXT NOT NULL,
  action_kind TEXT NOT NULL,
  action_summary_label TEXT NOT NULL,
  legacy_action_hash TEXT,
  approval_context_key_count INTEGER NOT NULL DEFAULT 0,
  approval_context_safe_keys_json TEXT NOT NULL DEFAULT '[]',
  unsafe_context_key_count INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  dual_write_enabled INTEGER NOT NULL DEFAULT 1,
  caller_switched INTEGER NOT NULL DEFAULT 0,
  old_hitl_deleted INTEGER NOT NULL DEFAULT 0,
  legacy_json_authoritative INTEGER NOT NULL DEFAULT 1,
  raw_content_stored INTEGER NOT NULL DEFAULT 0,
  raw_action_text_stored INTEGER NOT NULL DEFAULT 0,
  raw_command_text_stored INTEGER NOT NULL DEFAULT 0,
  freeform_shell_approval_allowed INTEGER NOT NULL DEFAULT 0,
  approval_required INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS guardian_hitl_legacy_authority_refs (
  legacy_ref_id TEXT PRIMARY KEY,
  source_surface_id TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  source_type TEXT NOT NULL,
  used_by_current_repo_a INTEGER NOT NULL DEFAULT 1,
  classification TEXT NOT NULL,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  deprecation_proof_required TEXT NOT NULL,
  delete_allowed INTEGER NOT NULL DEFAULT 0,
  old_files_are_truth INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS guardian_hitl_approval_receipts (
  receipt_id TEXT PRIMARY KEY,
  approval_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  receipt_type TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  source_surface TEXT NOT NULL,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  raw_content_stored INTEGER NOT NULL DEFAULT 0,
  raw_action_text_stored INTEGER NOT NULL DEFAULT 0,
  raw_command_text_stored INTEGER NOT NULL DEFAULT 0,
  caller_switched INTEGER NOT NULL DEFAULT 0,
  old_hitl_deleted INTEGER NOT NULL DEFAULT 0,
  legacy_json_authoritative INTEGER NOT NULL DEFAULT 1,
  FOREIGN KEY (approval_id) REFERENCES guardian_hitl_approval_requests(approval_id)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_guardian_hitl_requests_idempotency ON guardian_hitl_approval_requests(idempotency_key)",
        "CREATE INDEX IF NOT EXISTS idx_guardian_hitl_requests_status ON guardian_hitl_approval_requests(status)",
        "CREATE INDEX IF NOT EXISTS idx_guardian_hitl_receipts_type ON guardian_hitl_approval_receipts(receipt_type)",
    )


def init_guardian_hitl_dual_write_schema(db_path: str | Path | None = None) -> str:
    path = _ledger_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path.as_posix())
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path.as_posix()


def _parse_requested_at(value: str) -> datetime:
    value = str(value or "").strip()
    if not value:
        raise ValueError("requested_at is required")
    for fmt in ("%Y-%m-%d %H:%M:%S",):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("requested_at must be parseable") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _safe_actor(value: object) -> str:
    text = str(value or "unknown").strip().lower()
    cleaned = "".join(char if char.isalnum() or char in ("_", "-") else "_" for char in text)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned[:80] or "unknown"


def _context_key_summary(context: object) -> tuple[list[str], int]:
    if not isinstance(context, Mapping):
        return [], 0
    safe_keys: list[str] = []
    unsafe_count = 0
    for key in context:
        key_text = str(key)
        if key_text in FORBIDDEN_PAYLOAD_KEYS:
            unsafe_count += 1
            continue
        if key_text and key_text.replace("_", "").replace("-", "").isalnum():
            safe_keys.append(key_text[:80])
    return sorted(set(safe_keys)), unsafe_count


def _payload_hash_basis(
    pending: Mapping[str, Any],
    *,
    safe_context_keys: list[str],
    unsafe_context_key_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "source_surface_id": CHIEF_SOURCE_SURFACE,
        "legacy_approval_id": str(pending.get("id", "")).strip(),
        "legacy_action_text": str(pending.get("action", "")),
        "requester": str(pending.get("requester", "")).strip(),
        "requested_at": str(pending.get("requested_at", "")).strip(),
        "tier": int(pending.get("tier", 2) or 2),
        "options": int(pending.get("options", 2) or 2),
        "legacy_action_hash": str(pending.get("hash", "")).strip(),
        "approval_context_safe_keys": safe_context_keys,
        "unsafe_context_key_count": unsafe_context_key_count,
    }


def build_chief_approval_request_mirror(
    pending: Mapping[str, Any],
    *,
    ttl_seconds: int = CHIEF_TTL_SECONDS,
    source_ref: str = LEGACY_APPROVAL_PENDING_REF,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a safe canonical-shaped mirror from an in-process Chief pending dict.

    Raw action text and full approval_context are used only for hashing. They
    are never returned or persisted by this function.
    """
    legacy_approval_id = str(pending.get("id", "")).strip()
    requester = str(pending.get("requester", "")).strip()
    legacy_action = str(pending.get("action", ""))
    if not legacy_approval_id:
        raise ValueError("legacy approval id is required")
    if not requester:
        raise ValueError("requester is required")
    if not legacy_action:
        raise ValueError("legacy action text is required for hash binding")
    if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be a positive integer")

    requested_at_dt = _parse_requested_at(str(pending.get("requested_at", "")))
    expires_at_dt = requested_at_dt + timedelta(seconds=ttl_seconds)
    requested_at = requested_at_dt.isoformat()
    expires_at = expires_at_dt.isoformat()
    safe_context_keys, unsafe_context_key_count = _context_key_summary(
        pending.get("approval_context", {})
    )
    payload_hash = _sha256_text(
        stable_json(
            _payload_hash_basis(
                pending,
                safe_context_keys=safe_context_keys,
                unsafe_context_key_count=unsafe_context_key_count,
            )
        )
    )
    idempotency_key = (
        f"guardian_hitl_dual_write:{CHIEF_SOURCE_SURFACE}:"
        f"{legacy_approval_id}:{payload_hash}"
    )
    receipt_id = _row_id("ghitl_receipt", idempotency_key, "request_shadow_created")
    actor = _safe_actor(requester)
    risk_tier = f"tier_{int(pending.get('tier', 2) or 2)}"
    canonical_payload = {
        "approval_id": legacy_approval_id,
        "action_type": "chief_approval_request",
        "actor": actor,
        "target": "legacy_chief_approval_gate",
        "payload_hash": payload_hash,
        "payload_schema_version": PAYLOAD_SCHEMA_VERSION,
        "source_intent_ref": f"legacy:{APPROVAL_PENDING_SOURCE_SURFACE}:{legacy_approval_id}",
        "idempotency_key": idempotency_key,
        "requested_at": requested_at,
        "expires_at": expires_at,
        "ttl_seconds": ttl_seconds,
        "authority_scope": "observational_dual_write_only",
        "risk_tier": risk_tier,
    }
    validation = validate_canonical_approval_payload(canonical_payload)
    if not validation["valid"]:
        raise ValueError("canonical mirror payload invalid: " + ",".join(validation["errors"]))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "canonical_payload": canonical_payload,
        "legacy_approval_id": legacy_approval_id,
        "legacy_action_hash": str(pending.get("hash", "")).strip() or None,
        "source_surface_id": CHIEF_SOURCE_SURFACE,
        "legacy_source_surface_id": APPROVAL_PENDING_SOURCE_SURFACE,
        "legacy_json_ref": source_ref,
        "request_receipt_id": receipt_id,
        "status": "request_shadow_created",
        "action_kind": "chief_tiered_approval_request",
        "action_summary_label": "Chief approval request",
        "approval_context_safe_keys": safe_context_keys,
        "approval_context_key_count": len(safe_context_keys),
        "unsafe_context_key_count": unsafe_context_key_count,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "freeform_shell_approval_allowed": False,
        "can_approve": False,
        "can_execute": False,
    }


def record_chief_approval_request_mirror(
    pending: Mapping[str, Any],
    *,
    ttl_seconds: int = CHIEF_TTL_SECONDS,
    db_path: str | Path | None = None,
    source_ref: str = LEGACY_APPROVAL_PENDING_REF,
    generated_at: str | None = None,
) -> dict[str, Any]:
    mirror = build_chief_approval_request_mirror(
        pending,
        ttl_seconds=ttl_seconds,
        source_ref=source_ref,
        generated_at=generated_at,
    )
    path = init_guardian_hitl_dual_write_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        existing = conn.execute(
            """
SELECT approval_id
FROM guardian_hitl_approval_requests
WHERE idempotency_key = ?
""".strip(),
            (mirror["canonical_payload"]["idempotency_key"],),
        ).fetchone()
        status = "existing" if existing else "mirrored"
        now = mirror["generated_at"]
        canonical = mirror["canonical_payload"]
        conn.execute(
            """
INSERT INTO guardian_hitl_legacy_authority_refs (
  legacy_ref_id, source_surface_id, source_ref, source_type,
  used_by_current_repo_a, classification, raw_content_read,
  deprecation_proof_required, delete_allowed, old_files_are_truth,
  runtime_authority, created_at, updated_at
) VALUES (?, ?, ?, ?, 1, ?, 0, ?, 0, 0, 0, ?, ?)
ON CONFLICT(legacy_ref_id) DO UPDATE SET
  updated_at = excluded.updated_at,
  classification = excluded.classification,
  raw_content_read = 0,
  delete_allowed = 0,
  old_files_are_truth = 0,
  runtime_authority = 0
""".strip(),
            (
                f"legacy_ref_{APPROVAL_PENDING_SOURCE_SURFACE}",
                APPROVAL_PENDING_SOURCE_SURFACE,
                source_ref,
                "windows_side_json_pending_approval",
                OLD_HITL_CLASSIFICATION,
                "Prove every current non-test Repo A caller no longer reads/writes approval_pending.json and equivalent SQLite request/decision/receipt paths exist.",
                now,
                now,
            ),
        )
        conn.execute(
            """
INSERT INTO guardian_hitl_approval_requests (
  approval_id, source_surface_id, legacy_approval_id, action_type,
  actor, target, payload_hash, payload_schema_version, source_intent_ref,
  idempotency_key, requested_at, expires_at, ttl_seconds, authority_scope,
  risk_tier, status, request_receipt_id, legacy_json_ref, action_kind,
  action_summary_label, legacy_action_hash, approval_context_key_count,
  approval_context_safe_keys_json, unsafe_context_key_count, runtime_authority,
  dual_write_enabled, caller_switched, old_hitl_deleted,
  legacy_json_authoritative, raw_content_stored, raw_action_text_stored,
  raw_command_text_stored, freeform_shell_approval_allowed, approval_required,
  created_at, updated_at
) VALUES (
  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
  0, 1, 0, 0, 1, 0, 0, 0, 0, 1, ?, ?
)
ON CONFLICT(idempotency_key) DO UPDATE SET
  updated_at = excluded.updated_at,
  status = guardian_hitl_approval_requests.status,
  runtime_authority = 0,
  dual_write_enabled = 1,
  caller_switched = 0,
  old_hitl_deleted = 0,
  legacy_json_authoritative = 1,
  raw_content_stored = 0,
  raw_action_text_stored = 0,
  raw_command_text_stored = 0,
  freeform_shell_approval_allowed = 0
""".strip(),
            (
                canonical["approval_id"],
                mirror["source_surface_id"],
                mirror["legacy_approval_id"],
                canonical["action_type"],
                canonical["actor"],
                canonical["target"],
                canonical["payload_hash"],
                canonical["payload_schema_version"],
                canonical["source_intent_ref"],
                canonical["idempotency_key"],
                canonical["requested_at"],
                canonical["expires_at"],
                canonical["ttl_seconds"],
                canonical["authority_scope"],
                canonical["risk_tier"],
                mirror["status"],
                mirror["request_receipt_id"],
                mirror["legacy_json_ref"],
                mirror["action_kind"],
                mirror["action_summary_label"],
                mirror["legacy_action_hash"],
                mirror["approval_context_key_count"],
                stable_json(mirror["approval_context_safe_keys"]),
                mirror["unsafe_context_key_count"],
                now,
                now,
            ),
        )
        conn.execute(
            """
INSERT INTO guardian_hitl_approval_receipts (
  receipt_id, approval_id, idempotency_key, receipt_type, status, summary,
  created_at, payload_hash, source_surface, runtime_authority,
  raw_content_stored, raw_action_text_stored, raw_command_text_stored,
  caller_switched, old_hitl_deleted, legacy_json_authoritative
) VALUES (?, ?, ?, 'request_shadow_created', ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 1)
ON CONFLICT(receipt_id) DO UPDATE SET
  status = excluded.status,
  summary = excluded.summary,
  runtime_authority = 0,
  raw_content_stored = 0,
  raw_action_text_stored = 0,
  raw_command_text_stored = 0,
  caller_switched = 0,
  old_hitl_deleted = 0,
  legacy_json_authoritative = 1
""".strip(),
            (
                mirror["request_receipt_id"],
                canonical["approval_id"],
                canonical["idempotency_key"],
                "observed" if status == "mirrored" else "duplicate_observed",
                "Observed Chief approval request mirror. Legacy JSON remains authoritative.",
                now,
                canonical["payload_hash"],
                CHIEF_SOURCE_SURFACE,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "approval_id": mirror["canonical_payload"]["approval_id"],
        "idempotency_key": mirror["canonical_payload"]["idempotency_key"],
        "request_receipt_id": mirror["request_receipt_id"],
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "adapter_health": "healthy",
        "db_path": path,
    }


def _decision_receipt_shape(decision: str) -> tuple[str, str, str]:
    raw = str(decision or "").strip().upper()
    if raw not in DECISION_LABELS:
        raise ValueError("unsupported decision receipt label")
    return DECISION_LABELS[raw]


def build_chief_approval_decision_receipt(
    pending: Mapping[str, Any],
    decision: str,
    *,
    ttl_seconds: int = CHIEF_TTL_SECONDS,
    source_ref: str = LEGACY_APPROVAL_PENDING_REF,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build safe decision receipt metadata from an in-process Chief pending dict.

    The pending action text and approval context are used only to recompute the
    request payload hash. They are not returned or persisted.
    """
    mirror = build_chief_approval_request_mirror(
        pending,
        ttl_seconds=ttl_seconds,
        source_ref=source_ref,
        generated_at=generated_at,
    )
    receipt_type, status, decision_label = _decision_receipt_shape(decision)
    canonical = mirror["canonical_payload"]
    receipt_id = _row_id(
        "ghitl_receipt",
        canonical["idempotency_key"],
        receipt_type,
        decision_label,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "approval_id": canonical["approval_id"],
        "idempotency_key": canonical["idempotency_key"],
        "payload_hash": canonical["payload_hash"],
        "receipt_id": receipt_id,
        "receipt_type": receipt_type,
        "status": status,
        "decision_label": decision_label,
        "source_surface": CHIEF_SOURCE_SURFACE,
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "freeform_shell_approval_allowed": False,
        "can_approve": False,
        "can_execute": False,
    }


def _insert_decision_receipt(
    conn: sqlite3.Connection,
    *,
    receipt_id: str,
    approval_id: str,
    idempotency_key: str,
    receipt_type: str,
    status: str,
    summary: str,
    created_at: str,
    payload_hash: str,
    source_surface: str,
) -> None:
    conn.execute(
        """
INSERT INTO guardian_hitl_approval_receipts (
  receipt_id, approval_id, idempotency_key, receipt_type, status, summary,
  created_at, payload_hash, source_surface, runtime_authority,
  raw_content_stored, raw_action_text_stored, raw_command_text_stored,
  caller_switched, old_hitl_deleted, legacy_json_authoritative
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 1)
ON CONFLICT(receipt_id) DO UPDATE SET
  status = excluded.status,
  summary = excluded.summary,
  runtime_authority = 0,
  raw_content_stored = 0,
  raw_action_text_stored = 0,
  raw_command_text_stored = 0,
  caller_switched = 0,
  old_hitl_deleted = 0,
  legacy_json_authoritative = 1
""".strip(),
        (
            receipt_id,
            approval_id,
            idempotency_key,
            receipt_type,
            status,
            summary,
            created_at,
            payload_hash,
            source_surface,
        ),
    )


def record_chief_approval_decision_receipt(
    pending: Mapping[str, Any],
    decision: str,
    *,
    ttl_seconds: int = CHIEF_TTL_SECONDS,
    db_path: str | Path | None = None,
    source_ref: str = LEGACY_APPROVAL_PENDING_REF,
    generated_at: str | None = None,
) -> dict[str, Any]:
    receipt = build_chief_approval_decision_receipt(
        pending,
        decision,
        ttl_seconds=ttl_seconds,
        source_ref=source_ref,
        generated_at=generated_at,
    )
    path = init_guardian_hitl_dual_write_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        exact_request = conn.execute(
            """
SELECT approval_id, idempotency_key, payload_hash
FROM guardian_hitl_approval_requests
WHERE approval_id = ? AND idempotency_key = ? AND payload_hash = ?
""".strip(),
            (
                receipt["approval_id"],
                receipt["idempotency_key"],
                receipt["payload_hash"],
            ),
        ).fetchone()
        now = receipt["generated_at"]
        if exact_request:
            stored_receipt_id = receipt["receipt_id"]
            stored_receipt_type = receipt["receipt_type"]
            _insert_decision_receipt(
                conn,
                receipt_id=stored_receipt_id,
                approval_id=receipt["approval_id"],
                idempotency_key=receipt["idempotency_key"],
                receipt_type=stored_receipt_type,
                status=receipt["status"],
                summary=(
                    "Observed Chief approval decision receipt. "
                    "Legacy JSON remains authoritative."
                ),
                created_at=now,
                payload_hash=receipt["payload_hash"],
                source_surface=CHIEF_SOURCE_SURFACE,
            )
            status = "mirrored"
        else:
            existing_by_id = conn.execute(
                """
SELECT approval_id, idempotency_key, payload_hash
FROM guardian_hitl_approval_requests
WHERE approval_id = ?
""".strip(),
                (receipt["approval_id"],),
            ).fetchone()
            if not existing_by_id:
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "missing_request_mirror",
                    "approval_id": receipt["approval_id"],
                    "runtime_authority_changed": False,
                    "runtime_authority": False,
                    "dual_write_enabled": True,
                    "caller_switched": False,
                    "old_hitl_deleted": False,
                    "legacy_json_authoritative": True,
                    "raw_content_stored": False,
                    "raw_action_text_stored": False,
                    "raw_command_text_stored": False,
                    "adapter_health": "needs_request_mirror",
                    "db_path": path,
                }

            mismatch_receipt_id = _row_id(
                "ghitl_receipt",
                existing_by_id["idempotency_key"],
                "legacy_sqlite_mismatch",
                receipt["payload_hash"],
            )
            stored_receipt_id = mismatch_receipt_id
            stored_receipt_type = "legacy_sqlite_mismatch"
            _insert_decision_receipt(
                conn,
                receipt_id=mismatch_receipt_id,
                approval_id=existing_by_id["approval_id"],
                idempotency_key=existing_by_id["idempotency_key"],
                receipt_type="legacy_sqlite_mismatch",
                status="mismatch_observed",
                summary=(
                    "Observed Chief decision context did not match the existing "
                    "SQLite request mirror. Legacy JSON remains authoritative."
                ),
                created_at=now,
                payload_hash=existing_by_id["payload_hash"],
                source_surface=CHIEF_SOURCE_SURFACE,
            )
            status = "mismatch_observed"
        conn.commit()
    finally:
        conn.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "approval_id": receipt["approval_id"],
        "receipt_id": stored_receipt_id,
        "receipt_type": stored_receipt_type,
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "adapter_health": "healthy" if status == "mirrored" else "needs_review",
        "db_path": path,
    }


def mirror_chief_approval_decision_fail_open(
    pending: Mapping[str, Any],
    decision: str,
    *,
    ttl_seconds: int = CHIEF_TTL_SECONDS,
    db_path: str | Path | None = None,
    source_ref: str = LEGACY_APPROVAL_PENDING_REF,
) -> dict[str, Any]:
    """Attempt a Chief decision receipt mirror without affecting legacy flow."""
    try:
        return record_chief_approval_decision_receipt(
            pending,
            decision,
            ttl_seconds=ttl_seconds,
            db_path=db_path,
            source_ref=source_ref,
        )
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "failed_open",
            "adapter_health": "failed",
            "error_type": exc.__class__.__name__,
            "runtime_authority_changed": False,
            "runtime_authority": False,
            "dual_write_enabled": False,
            "caller_switched": False,
            "old_hitl_deleted": False,
            "legacy_json_authoritative": True,
            "raw_content_stored": False,
            "raw_action_text_stored": False,
            "raw_command_text_stored": False,
        }


def mirror_chief_approval_request_fail_open(
    pending: Mapping[str, Any],
    *,
    ttl_seconds: int = CHIEF_TTL_SECONDS,
    db_path: str | Path | None = None,
    source_ref: str = LEGACY_APPROVAL_PENDING_REF,
) -> dict[str, Any]:
    """Attempt a Chief request mirror and return failure metadata instead of raising."""
    try:
        return record_chief_approval_request_mirror(
            pending,
            ttl_seconds=ttl_seconds,
            db_path=db_path,
            source_ref=source_ref,
        )
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "failed_open",
            "adapter_health": "failed",
            "error_type": exc.__class__.__name__,
            "runtime_authority_changed": False,
            "runtime_authority": False,
            "dual_write_enabled": False,
            "caller_switched": False,
            "old_hitl_deleted": False,
            "legacy_json_authoritative": True,
            "raw_content_stored": False,
            "raw_action_text_stored": False,
            "raw_command_text_stored": False,
        }


def _all_rows(conn: sqlite3.Connection, table: str, order_by: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
    ]


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def build_guardian_hitl_dual_write_read_model(
    *,
    db_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    path = init_guardian_hitl_dual_write_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        requests = _all_rows(
            conn,
            "guardian_hitl_approval_requests",
            "created_at DESC, approval_id DESC",
        )
        receipts = _all_rows(
            conn,
            "guardian_hitl_approval_receipts",
            "created_at DESC, receipt_id DESC",
        )
        legacy_refs = _all_rows(
            conn,
            "guardian_hitl_legacy_authority_refs",
            "updated_at DESC, legacy_ref_id DESC",
        )
        request_mirror_count = _count_rows(conn, "guardian_hitl_approval_requests")
        decision_receipt_count = int(
            conn.execute(
                """
SELECT COUNT(*)
FROM guardian_hitl_approval_receipts
WHERE receipt_type LIKE 'decision_%'
""".strip()
            ).fetchone()[0]
        )
        notification_receipt_count = int(
            conn.execute(
                """
SELECT COUNT(*)
FROM guardian_hitl_approval_receipts
WHERE receipt_type LIKE 'notification_%'
""".strip()
            ).fetchone()[0]
        )
        mismatch_count = int(
            conn.execute(
                """
SELECT COUNT(*)
FROM guardian_hitl_approval_receipts
WHERE receipt_type = 'legacy_sqlite_mismatch'
""".strip()
            ).fetchone()[0]
        )
    finally:
        conn.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "db_path": path,
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "dual_write_enabled_surfaces": [CHIEF_SOURCE_SURFACE, APPROVAL_PENDING_SOURCE_SURFACE],
        "legacy_json_authoritative": True,
        "callers_switched": False,
        "old_hitl_deleted": False,
        "old_hitl_classification": OLD_HITL_CLASSIFICATION,
        "raw_content_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "freeform_shell_approval_allowed": False,
        "request_mirror_count": request_mirror_count,
        "decision_receipt_count": decision_receipt_count,
        "notification_receipt_count": notification_receipt_count,
        "mismatch_count": mismatch_count,
        "adapter_health": "healthy" if mismatch_count == 0 else "needs_review",
        "safe_to_import_cassandra_chief_memory": False,
        "safe_to_enable_remote_builder": False,
        "safe_to_expand_send_paths": False,
        "tables": [
            "guardian_hitl_approval_requests",
            "guardian_hitl_legacy_authority_refs",
            "guardian_hitl_approval_receipts",
        ],
        "recent_request_mirrors": requests[:20],
        "legacy_authority_refs": legacy_refs,
        "recent_receipts": receipts[:20],
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        "next_safe_move": "Prove Chief request and decision receipt parity, then plan Cassandra HITL proposal shadow without switching callers.",
    }


def format_guardian_hitl_dual_write_read_model(payload: dict[str, Any]) -> str:
    lines = [
        "# Guardian HITL SQLite Chief Approval Dual-Write v0",
        "",
        "## Bottom Line",
        "",
        "Chief approval requests and decisions can now be mirrored into SQLite as observational records. Old `approval_pending.json` remains runtime-authoritative. No caller switched, no old HITL file was deleted, and no raw action or command text is stored.",
        "",
        "## Status",
        "",
        f"- Runtime authority changed: `{str(payload['runtime_authority_changed']).lower()}`",
        f"- Dual-write surfaces: `{', '.join(payload['dual_write_enabled_surfaces'])}`",
        f"- Legacy JSON authoritative: `{str(payload['legacy_json_authoritative']).lower()}`",
        f"- Callers switched: `{str(payload['callers_switched']).lower()}`",
        f"- Old HITL deleted: `{str(payload['old_hitl_deleted']).lower()}`",
        f"- Raw action text stored: `{str(payload['raw_action_text_stored']).lower()}`",
        f"- Raw command text stored: `{str(payload['raw_command_text_stored']).lower()}`",
        f"- Adapter health: `{payload['adapter_health']}`",
        "",
        "## Counts",
        "",
        f"- Request mirrors: `{payload['request_mirror_count']}`",
        f"- Decision receipts: `{payload['decision_receipt_count']}`",
        f"- Notification receipts: `{payload['notification_receipt_count']}`",
        f"- Mismatches: `{payload['mismatch_count']}`",
        "",
        "## Recent Mirrors",
        "",
    ]
    if not payload["recent_request_mirrors"]:
        lines.append("- No Chief approval request mirrors recorded yet.")
    else:
        for item in payload["recent_request_mirrors"]:
            lines.append(
                f"- `{item['approval_id']}`: `{item['status']}` / `{item['action_summary_label']}`"
            )

    lines.extend(
        [
            "",
            "## Still Blocked",
            "",
            f"- Cassandra/Chief memory import safe now: `{str(payload['safe_to_import_cassandra_chief_memory']).lower()}`",
            f"- Remote-builder bridge safe now: `{str(payload['safe_to_enable_remote_builder']).lower()}`",
            f"- Send-path expansion safe now: `{str(payload['safe_to_expand_send_paths']).lower()}`",
            "",
            "## Next Safe Move",
            "",
            payload["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def export_guardian_hitl_dual_write_read_model(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    db_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    export_path = _export_root_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_hitl_dual_write_read_model(
        db_path=db_path,
        generated_at=generated_at,
    )
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(
        format_guardian_hitl_dual_write_read_model(payload),
        encoding="utf-8",
    )
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "request_mirror_count": payload["request_mirror_count"],
        "adapter_health": payload["adapter_health"],
        "runtime_authority_changed": payload["runtime_authority_changed"],
        "callers_switched": payload["callers_switched"],
        "old_hitl_deleted": payload["old_hitl_deleted"],
        "raw_action_text_stored": payload["raw_action_text_stored"],
        "raw_command_text_stored": payload["raw_command_text_stored"],
    }


__all__ = [
    "APPROVAL_PENDING_SOURCE_SURFACE",
    "CHIEF_SOURCE_SURFACE",
    "CHIEF_TTL_SECONDS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_chief_approval_request_mirror",
    "build_chief_approval_decision_receipt",
    "build_guardian_hitl_dual_write_read_model",
    "export_guardian_hitl_dual_write_read_model",
    "format_guardian_hitl_dual_write_read_model",
    "init_guardian_hitl_dual_write_schema",
    "mirror_chief_approval_decision_fail_open",
    "mirror_chief_approval_request_fail_open",
    "record_chief_approval_decision_receipt",
    "record_chief_approval_request_mirror",
    "stable_json",
]
