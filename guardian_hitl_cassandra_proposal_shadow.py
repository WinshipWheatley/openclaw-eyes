"""Cassandra HITL proposal shadow v0.

This module mirrors in-process Cassandra HITL pending-action records into the
Guardian/HITL SQLite contract shape for visibility only. Legacy
``hitl_pending_state.json`` remains runtime-authoritative.

It does not read live HITL JSON, approve decisions, send notifications, execute
actions, switch callers, import Repo B code, or store raw payload content.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from guardian_hitl_dual_write_compatibility import (
    DEFAULT_EXPORT_ROOT,
    init_guardian_hitl_dual_write_schema,
)
from guardian_hitl_sqlite_authority_contract import (
    FORBIDDEN_PAYLOAD_KEYS,
    OLD_HITL_CLASSIFICATION,
    validate_canonical_approval_payload,
)


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "guardian_hitl_cassandra_proposal_shadow_v0"
JSON_EXPORT_NAME = "guardian_hitl_cassandra_proposal_shadow.json"
OPERATOR_EXPORT_NAME = "guardian_hitl_cassandra_proposal_shadow_OPERATOR.md"

CASSANDRA_SOURCE_SURFACE = "hitl_pending_store"
LEGACY_STATE_AUTHORITY = "hitl_pending_state_json"
LEGACY_HITL_STATE_REF = "/mnt/c/OpenClaw/logs/hitl_pending_state.json"
CANONICAL_ACTION_TYPE = "cassandra_hitl_proposal"
PAYLOAD_SCHEMA_VERSION = "legacy_cassandra_hitl_proposal_observation_v0"
DEFAULT_TTL_SECONDS = 86400
DECISION_LABELS = {
    "APPROVED": ("decision_shadow_observed", "approved_observed", "approved"),
    "DENIED": ("decision_shadow_rejected", "denied_observed", "denied"),
    "EXPIRED": ("decision_shadow_expired", "expired_observed", "expired"),
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority_changed": False,
    "runtime_authority": False,
    "dual_write_enabled": True,
    "caller_switched": False,
    "old_hitl_deleted": False,
    "legacy_json_authoritative": True,
    "raw_content_stored": False,
    "raw_payload_stored": False,
    "raw_action_text_stored": False,
    "raw_command_text_stored": False,
    "freeform_shell_approval_allowed": False,
    "approval_bypass_allowed": False,
    "can_approve": False,
    "can_execute": False,
    "notification_send_added": False,
    "callback_decision_shadow_added": True,
    "callback_decision_shadow_support": True,
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


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _safe_label(value: object, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return fallback
    cleaned = "".join(char if char.isalnum() or char in ("_", "-", ".") else "_" for char in text)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned[:80] or fallback


def _safe_action_label(action_type: object) -> str:
    text = _safe_label(action_type, fallback="unknown_action")
    if any(token in text for token in ("command", "shell", "exec", "subprocess")):
        return "unsafe_action_type_hash_only"
    return text


def _payload_key_summary(payload: object) -> tuple[list[str], int, int]:
    if not isinstance(payload, Mapping):
        return [], 0, 0

    top_level_key_count = len(payload)
    safe_keys: list[str] = []
    unsafe_count = 0

    def visit(value: object) -> None:
        nonlocal unsafe_count
        if isinstance(value, Mapping):
            for key, nested in value.items():
                key_text = str(key)
                if key_text in FORBIDDEN_PAYLOAD_KEYS:
                    unsafe_count += 1
                visit(nested)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for key, value in payload.items():
        key_text = str(key)
        if key_text in FORBIDDEN_PAYLOAD_KEYS:
            unsafe_count += 1
        elif key_text and key_text.replace("_", "").replace("-", "").isalnum():
            safe_keys.append(key_text[:80])
        visit(value)

    return sorted(set(safe_keys)), top_level_key_count, unsafe_count


def _ttl_seconds(record: Mapping[str, Any], fallback_ttl_seconds: int) -> int:
    if isinstance(fallback_ttl_seconds, int) and fallback_ttl_seconds > 0:
        return fallback_ttl_seconds
    requested = _parse_time(record.get("requested_at"))
    expires = _parse_time(record.get("expires_at"))
    if requested and expires:
        delta = int((expires - requested).total_seconds())
        if delta > 0:
            return delta
    return DEFAULT_TTL_SECONDS


def _requested_and_expires(record: Mapping[str, Any], ttl_seconds: int) -> tuple[str, str]:
    requested = _parse_time(record.get("requested_at")) or datetime.now(timezone.utc).replace(microsecond=0)
    expires = _parse_time(record.get("expires_at"))
    if expires is None:
        expires = requested + timedelta(seconds=ttl_seconds)
    return requested.isoformat(), expires.isoformat()


def _payload_hash_basis(
    record: Mapping[str, Any],
    *,
    safe_payload_keys: list[str],
    payload_key_count: int,
    unsafe_payload_key_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "source_surface_id": CASSANDRA_SOURCE_SURFACE,
        "legacy_action_id": str(record.get("action_id", "")).strip(),
        "source_agent": str(record.get("source_agent", "")).strip(),
        "legacy_action_type": str(record.get("action_type", "")).strip(),
        "legacy_payload": record.get("payload") if isinstance(record.get("payload"), Mapping) else {},
        "idempotency_key": str(record.get("idempotency_key", "")).strip(),
        "review_state": str(record.get("review_state", "")).strip(),
        "review_reason_codes": list(record.get("review_reason_codes") or []),
        "normalized_amount_present": record.get("normalized_amount") is not None,
        "requested_at": str(record.get("requested_at", "")).strip(),
        "expires_at": str(record.get("expires_at", "")).strip(),
        "safe_payload_keys": safe_payload_keys,
        "payload_key_count": payload_key_count,
        "unsafe_payload_key_count": unsafe_payload_key_count,
    }


def build_cassandra_hitl_proposal_mirror(
    record: Mapping[str, Any],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    source_ref: str = LEGACY_HITL_STATE_REF,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a safe canonical-shaped mirror from an in-process HITL record."""
    legacy_action_id = str(record.get("action_id", "")).strip()
    source_agent = str(record.get("source_agent", "")).strip()
    legacy_action_type = str(record.get("action_type", "")).strip()
    if not legacy_action_id:
        raise ValueError("legacy action_id is required")
    if not source_agent:
        raise ValueError("source_agent is required")
    if not legacy_action_type:
        raise ValueError("action_type is required")

    ttl = _ttl_seconds(record, ttl_seconds)
    requested_at, expires_at = _requested_and_expires(record, ttl)
    payload = record.get("payload")
    safe_payload_keys, payload_key_count, unsafe_payload_key_count = _payload_key_summary(payload)
    payload_hash = _sha256_text(
        stable_json(
            _payload_hash_basis(
                record,
                safe_payload_keys=safe_payload_keys,
                payload_key_count=payload_key_count,
                unsafe_payload_key_count=unsafe_payload_key_count,
            )
        )
    )
    safe_action_type = _safe_action_label(legacy_action_type)
    approval_id = f"cassandra_hitl_{legacy_action_id}"
    idempotency_key = (
        f"guardian_hitl_shadow:{CASSANDRA_SOURCE_SURFACE}:"
        f"{legacy_action_id}:{payload_hash}"
    )
    receipt_id = _row_id("ghitl_receipt", idempotency_key, "cassandra_proposal_shadow_created")
    canonical_payload = {
        "approval_id": approval_id,
        "action_type": CANONICAL_ACTION_TYPE,
        "actor": _safe_label(source_agent, fallback="cassandra"),
        "target": "legacy_cassandra_hitl_pending_store",
        "payload_hash": payload_hash,
        "payload_schema_version": PAYLOAD_SCHEMA_VERSION,
        "source_intent_ref": f"legacy:{LEGACY_STATE_AUTHORITY}:{legacy_action_id}",
        "idempotency_key": idempotency_key,
        "requested_at": requested_at,
        "expires_at": expires_at,
        "ttl_seconds": ttl,
        "authority_scope": "observational_shadow_only",
        "risk_tier": _safe_label(record.get("review_state") or "normal", fallback="normal"),
    }
    validation = validate_canonical_approval_payload(canonical_payload)
    if not validation["valid"]:
        raise ValueError("canonical mirror payload invalid: " + ",".join(validation["errors"]))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "canonical_payload": canonical_payload,
        "source_surface_id": CASSANDRA_SOURCE_SURFACE,
        "canonical_action_type": CANONICAL_ACTION_TYPE,
        "legacy_action_id": legacy_action_id,
        "legacy_action_type_label": safe_action_type,
        "legacy_state_authority": LEGACY_STATE_AUTHORITY,
        "legacy_json_ref": source_ref,
        "request_receipt_id": receipt_id,
        "status": "cassandra_proposal_shadow_created",
        "action_kind": safe_action_type,
        "action_summary_label": f"Cassandra HITL proposal: {safe_action_type}",
        "safe_payload_keys": safe_payload_keys,
        "payload_key_count": payload_key_count,
        "unsafe_payload_key_count": unsafe_payload_key_count,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_payload_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "freeform_shell_approval_allowed": False,
        "can_approve": False,
        "can_execute": False,
    }


def record_cassandra_hitl_proposal_mirror(
    record: Mapping[str, Any],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    db_path: str | Path | None = None,
    source_ref: str = LEGACY_HITL_STATE_REF,
    generated_at: str | None = None,
) -> dict[str, Any]:
    mirror = build_cassandra_hitl_proposal_mirror(
        record,
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
                f"legacy_ref_{LEGACY_STATE_AUTHORITY}",
                LEGACY_STATE_AUTHORITY,
                source_ref,
                "windows_side_json_hitl_pending_action",
                OLD_HITL_CLASSIFICATION,
                "Prove Cassandra HITL proposal, decision, expiry, and notification state is mirrored and then owned by SQLite before deprecating hitl_pending_state.json.",
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
  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?,
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
                mirror["legacy_action_id"],
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
                mirror["payload_key_count"],
                stable_json(mirror["safe_payload_keys"]),
                mirror["unsafe_payload_key_count"],
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
) VALUES (?, ?, ?, 'cassandra_proposal_shadow_created', ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 1)
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
                "Observed Cassandra HITL proposal shadow. Legacy hitl_pending_state.json remains authoritative.",
                now,
                canonical["payload_hash"],
                CASSANDRA_SOURCE_SURFACE,
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
        "source_surface_id": CASSANDRA_SOURCE_SURFACE,
        "canonical_action_type": CANONICAL_ACTION_TYPE,
        "legacy_state_authority": LEGACY_STATE_AUTHORITY,
        "proposal_shadow_support": True,
        "decision_receipt_shadow_support": True,
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_payload_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "adapter_health": "healthy",
        "db_path": path,
    }


def mirror_cassandra_hitl_proposal_fail_open(
    record: Mapping[str, Any],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    db_path: str | Path | None = None,
    source_ref: str = LEGACY_HITL_STATE_REF,
) -> dict[str, Any]:
    """Attempt a Cassandra proposal shadow without affecting legacy flow."""
    try:
        return record_cassandra_hitl_proposal_mirror(
            record,
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
            "raw_payload_stored": False,
            "raw_action_text_stored": False,
            "raw_command_text_stored": False,
    }


def _decision_receipt_shape(decision_status: str) -> tuple[str, str, str]:
    raw = str(decision_status or "").strip().upper()
    if raw not in DECISION_LABELS:
        raise ValueError("unsupported Cassandra HITL decision receipt status")
    return DECISION_LABELS[raw]


def build_cassandra_hitl_decision_receipt(
    record: Mapping[str, Any],
    decision_status: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    source_ref: str = LEGACY_HITL_STATE_REF,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build safe observational decision metadata from an in-process HITL record."""
    mirror = build_cassandra_hitl_proposal_mirror(
        record,
        ttl_seconds=ttl_seconds,
        source_ref=source_ref,
        generated_at=generated_at,
    )
    receipt_type, status, decision_label = _decision_receipt_shape(decision_status)
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
        "source_surface": CASSANDRA_SOURCE_SURFACE,
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_payload_stored": False,
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


def record_cassandra_hitl_decision_receipt(
    record: Mapping[str, Any],
    decision_status: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    db_path: str | Path | None = None,
    source_ref: str = LEGACY_HITL_STATE_REF,
    generated_at: str | None = None,
) -> dict[str, Any]:
    receipt = build_cassandra_hitl_decision_receipt(
        record,
        decision_status,
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
                    "Observed Cassandra HITL decision receipt. "
                    "Legacy hitl_pending_state.json remains authoritative."
                ),
                created_at=now,
                payload_hash=receipt["payload_hash"],
                source_surface=CASSANDRA_SOURCE_SURFACE,
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
                    "raw_payload_stored": False,
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
                receipt_type=stored_receipt_type,
                status="mismatch_observed",
                summary=(
                    "Observed Cassandra HITL decision context did not match "
                    "the existing SQLite proposal mirror. Legacy JSON remains authoritative."
                ),
                created_at=now,
                payload_hash=existing_by_id["payload_hash"],
                source_surface=CASSANDRA_SOURCE_SURFACE,
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
        "source_surface_id": CASSANDRA_SOURCE_SURFACE,
        "canonical_action_type": CANONICAL_ACTION_TYPE,
        "legacy_state_authority": LEGACY_STATE_AUTHORITY,
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_payload_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "adapter_health": "healthy" if status == "mirrored" else "needs_review",
        "db_path": path,
    }


def mirror_cassandra_hitl_decision_fail_open(
    record: Mapping[str, Any],
    decision_status: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    db_path: str | Path | None = None,
    source_ref: str = LEGACY_HITL_STATE_REF,
) -> dict[str, Any]:
    """Attempt a Cassandra decision receipt mirror without affecting legacy flow."""
    try:
        return record_cassandra_hitl_decision_receipt(
            record,
            decision_status,
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
            "raw_payload_stored": False,
            "raw_action_text_stored": False,
            "raw_command_text_stored": False,
        }


def _all_rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def build_guardian_hitl_cassandra_proposal_shadow_read_model(
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
            """
SELECT *
FROM guardian_hitl_approval_requests
WHERE source_surface_id = ? AND action_type = ?
ORDER BY created_at DESC, approval_id DESC
""".strip(),
            (CASSANDRA_SOURCE_SURFACE, CANONICAL_ACTION_TYPE),
        )
        receipts = _all_rows(
            conn,
            """
SELECT *
FROM guardian_hitl_approval_receipts
WHERE source_surface = ?
ORDER BY created_at DESC, receipt_id DESC
""".strip(),
            (CASSANDRA_SOURCE_SURFACE,),
        )
        legacy_refs = _all_rows(
            conn,
            """
SELECT *
FROM guardian_hitl_legacy_authority_refs
WHERE source_surface_id = ?
ORDER BY updated_at DESC, legacy_ref_id DESC
            """.strip(),
            (LEGACY_STATE_AUTHORITY,),
        )
        decision_receipt_count = int(
            conn.execute(
                """
SELECT COUNT(*)
FROM guardian_hitl_approval_receipts
WHERE source_surface = ? AND receipt_type LIKE 'decision_%'
""".strip(),
                (CASSANDRA_SOURCE_SURFACE,),
            ).fetchone()[0]
        )
        mismatch_count = int(
            conn.execute(
                """
SELECT COUNT(*)
FROM guardian_hitl_approval_receipts
WHERE source_surface = ? AND receipt_type = 'legacy_sqlite_mismatch'
""".strip(),
                (CASSANDRA_SOURCE_SURFACE,),
            ).fetchone()[0]
        )
    finally:
        conn.close()

    proposal_shadow_count = len(requests)
    receipt_count = len(receipts)
    unsafe_payload_key_count = sum(int(row.get("unsafe_context_key_count") or 0) for row in requests)
    safe_to_import_cassandra_chief_memory = bool(
        mismatch_count == 0
        and NO_AUTHORITY_FLAGS["callback_decision_shadow_support"] is True
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "db_path": path,
        "shared_guardian_hitl_tables_used": True,
        "source_surface_id": CASSANDRA_SOURCE_SURFACE,
        "canonical_action_type": CANONICAL_ACTION_TYPE,
        "legacy_state_authority": LEGACY_STATE_AUTHORITY,
        "proposal_shadow_support": True,
        "decision_receipt_shadow_support": True,
        "callback_decision_shadow_support": True,
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "dual_write_enabled": True,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "legacy_json_authoritative": True,
        "raw_content_stored": False,
        "raw_payload_stored": False,
        "raw_action_text_stored": False,
        "raw_command_text_stored": False,
        "freeform_shell_approval_allowed": False,
        "proposal_shadow_count": proposal_shadow_count,
        "receipt_count": receipt_count,
        "decision_receipt_count": decision_receipt_count,
        "mismatch_count": mismatch_count,
        "unsafe_payload_key_count": unsafe_payload_key_count,
        "adapter_health": "healthy" if mismatch_count == 0 else "needs_review",
        "safe_to_import_cassandra_chief_memory": safe_to_import_cassandra_chief_memory,
        "safe_to_enable_remote_builder": False,
        "safe_to_expand_send_paths": False,
        "tables": [
            "guardian_hitl_approval_requests",
            "guardian_hitl_legacy_authority_refs",
            "guardian_hitl_approval_receipts",
        ],
        "recent_proposal_shadows": requests[:20],
        "legacy_authority_refs": legacy_refs,
        "recent_receipts": receipts[:20],
        "boundaries": {
            **NO_AUTHORITY_FLAGS,
            "safe_to_import_cassandra_chief_memory": safe_to_import_cassandra_chief_memory,
        },
        "next_safe_move": (
            "Record the operator-approved Cassandra/Chief memory import decision receipt; do not import real data until that receipt exists."
            if safe_to_import_cassandra_chief_memory
            else "Resolve Cassandra HITL shadow mismatches before memory import approval."
        ),
    }


def format_guardian_hitl_cassandra_proposal_shadow_read_model(payload: dict[str, Any]) -> str:
    lines = [
        "# Guardian HITL Cassandra Proposal Shadow v0",
        "",
        "## Bottom Line",
        "",
        "Cassandra HITL pending-action proposals and decisions can now be mirrored into SQLite as observational records. Old `hitl_pending_state.json` remains runtime-authoritative. No caller switched, no old HITL file was deleted, and no raw payload content is stored.",
        "",
        "## Status",
        "",
        f"- Shared Guardian HITL tables used: `{str(payload['shared_guardian_hitl_tables_used']).lower()}`",
        f"- Runtime authority changed: `{str(payload['runtime_authority_changed']).lower()}`",
        f"- Source surface: `{payload['source_surface_id']}`",
        f"- Canonical action type: `{payload['canonical_action_type']}`",
        f"- Legacy state authority: `{payload['legacy_state_authority']}`",
        f"- Proposal shadow support: `{str(payload['proposal_shadow_support']).lower()}`",
        f"- Decision receipt shadow support: `{str(payload['decision_receipt_shadow_support']).lower()}`",
        f"- Callback decision shadow support: `{str(payload['callback_decision_shadow_support']).lower()}`",
        f"- Legacy JSON authoritative: `{str(payload['legacy_json_authoritative']).lower()}`",
        f"- Callers switched: `{str(payload['caller_switched']).lower()}`",
        f"- Old HITL deleted: `{str(payload['old_hitl_deleted']).lower()}`",
        f"- Raw payload stored: `{str(payload['raw_payload_stored']).lower()}`",
        f"- Raw command text stored: `{str(payload['raw_command_text_stored']).lower()}`",
        f"- Adapter health: `{payload['adapter_health']}`",
        "",
        "## Counts",
        "",
        f"- Proposal shadows: `{payload['proposal_shadow_count']}`",
        f"- Decision receipts: `{payload['decision_receipt_count']}`",
        f"- Receipts: `{payload['receipt_count']}`",
        f"- Mismatches: `{payload['mismatch_count']}`",
        f"- Unsafe payload key count: `{payload['unsafe_payload_key_count']}`",
        "",
        "## Recent Proposal Shadows",
        "",
    ]
    if not payload["recent_proposal_shadows"]:
        lines.append("- No Cassandra HITL proposal shadows recorded yet.")
    else:
        for item in payload["recent_proposal_shadows"]:
            lines.append(
                f"- `{item['approval_id']}`: `{item['status']}` / `{item['action_summary_label']}`"
            )

    lines.extend(
        [
            "",
            "## Remaining Gates",
            "",
            f"- Cassandra/Chief memory import safe now: `{str(payload['safe_to_import_cassandra_chief_memory']).lower()}`",
            "- Real data import still requires the operator-approved memory import decision receipt.",
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


def export_guardian_hitl_cassandra_proposal_shadow_read_model(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    db_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    export_path = _export_root_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_hitl_cassandra_proposal_shadow_read_model(
        db_path=db_path,
        generated_at=generated_at,
    )
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(
        format_guardian_hitl_cassandra_proposal_shadow_read_model(payload),
        encoding="utf-8",
    )
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "proposal_shadow_count": payload["proposal_shadow_count"],
        "decision_receipt_count": payload["decision_receipt_count"],
        "mismatch_count": payload["mismatch_count"],
        "safe_to_import_cassandra_chief_memory": payload["safe_to_import_cassandra_chief_memory"],
        "adapter_health": payload["adapter_health"],
        "runtime_authority_changed": payload["runtime_authority_changed"],
        "caller_switched": payload["caller_switched"],
        "old_hitl_deleted": payload["old_hitl_deleted"],
        "raw_payload_stored": payload["raw_payload_stored"],
        "raw_command_text_stored": payload["raw_command_text_stored"],
    }


__all__ = [
    "CANONICAL_ACTION_TYPE",
    "CASSANDRA_SOURCE_SURFACE",
    "DEFAULT_TTL_SECONDS",
    "JSON_EXPORT_NAME",
    "LEGACY_STATE_AUTHORITY",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_cassandra_hitl_proposal_mirror",
    "build_cassandra_hitl_decision_receipt",
    "build_guardian_hitl_cassandra_proposal_shadow_read_model",
    "export_guardian_hitl_cassandra_proposal_shadow_read_model",
    "format_guardian_hitl_cassandra_proposal_shadow_read_model",
    "mirror_cassandra_hitl_decision_fail_open",
    "mirror_cassandra_hitl_proposal_fail_open",
    "record_cassandra_hitl_decision_receipt",
    "record_cassandra_hitl_proposal_mirror",
    "stable_json",
]
