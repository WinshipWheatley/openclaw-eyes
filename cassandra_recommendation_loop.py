"""Actionable Cassandra recommendation loop.

Cassandra can propose a structured recommendation, then the operator can
accept, modify, or deny it. Accept and modify only create a normal HITL action
request; they do not approve, execute, or bypass SEND_HOLD.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import hitl_action_service
from authority_gate import ensure_send_hold_sentinel
from business_ops_ledger import init_business_ops_ledger, record_receipt, resolve_business_ops_ledger_path


SCHEMA_VERSION = "CASSANDRA_RECOMMENDATION_LOOP_V0"
OUTCOME_SCHEMA_VERSION = "CASSANDRA_RECOMMENDATION_OUTCOME_V0"
DEFAULT_SEND_HOLD_PATH = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")
DEFAULT_TTL_SECONDS = 86400

STATUS_PROPOSED = "proposed"
STATUS_ACCEPTED = "accepted"
STATUS_MODIFIED = "modified"
STATUS_DENIED = "denied"

DECISION_PROPOSED = "proposed"
DECISION_ACCEPTED = "accepted"
DECISION_MODIFIED = "modified"
DECISION_DENIED = "denied"

SEND_LIKE_ACTION_TYPES = frozenset(
    {
        "email_send",
        "exact_gmail_send",
        "invoice_send",
        "sms",
        "social_post",
    }
)


@dataclass(frozen=True)
class Recommendation:
    """Cassandra recommendation ready for operator decision."""

    id: str
    surface: str
    summary: str
    proposed_action: Mapping[str, Any]
    rationale: str
    confidence: float
    created_by: str = "cassandra"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "surface": self.surface,
            "summary": self.summary,
            "proposed_action": dict(self.proposed_action),
            "rationale": self.rationale,
            "confidence": self.confidence,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class RecommendationOutcome:
    """Receipt for one operator response to a recommendation."""

    outcome_id: str
    recommendation_id: str
    decision: str
    status: str
    actor: str
    hitl_action_id: str | None
    hitl_status: str | None
    gate_status: str
    send_hold_active: bool
    send_hold_blocked: bool
    receipt: Mapping[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "recommendation_id": self.recommendation_id,
            "decision": self.decision,
            "status": self.status,
            "actor": self.actor,
            "hitl_action_id": self.hitl_action_id,
            "hitl_status": self.hitl_status,
            "gate_status": self.gate_status,
            "send_hold_active": self.send_hold_active,
            "send_hold_blocked": self.send_hold_blocked,
            "receipt": dict(self.receipt),
            "created_at": self.created_at,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _expires_at(ttl_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _db_path(db_path: str | Path | None) -> str:
    return resolve_business_ops_ledger_path(str(db_path) if db_path is not None else None)


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = _db_path(db_path)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _init_recommendation_schema(conn)
    return conn


def _init_recommendation_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cassandra_recommendations (
            recommendation_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            surface TEXT NOT NULL,
            summary TEXT NOT NULL,
            proposed_action_json TEXT NOT NULL,
            rationale TEXT NOT NULL,
            confidence REAL NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            latest_outcome_id TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cassandra_recommendation_outcomes (
            outcome_id TEXT PRIMARY KEY,
            recommendation_id TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            decision TEXT NOT NULL,
            status TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason TEXT,
            edits_json TEXT NOT NULL,
            dispatched_action_json TEXT NOT NULL,
            hitl_action_id TEXT,
            hitl_status TEXT,
            gate_status TEXT NOT NULL,
            send_hold_active INTEGER NOT NULL DEFAULT 0,
            send_hold_blocked INTEGER NOT NULL DEFAULT 0,
            receipt_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (recommendation_id) REFERENCES cassandra_recommendations (recommendation_id)
        )
        """
    )
    conn.commit()


def _validate_recommendation(recommendation: Recommendation) -> None:
    if not str(recommendation.id or "").strip():
        raise ValueError("recommendation id is required")
    if not str(recommendation.surface or "").strip():
        raise ValueError("recommendation surface is required")
    if not str(recommendation.summary or "").strip():
        raise ValueError("recommendation summary is required")
    if not isinstance(recommendation.proposed_action, Mapping):
        raise ValueError("proposed_action must be a mapping")
    _validate_proposed_action(dict(recommendation.proposed_action))
    if not str(recommendation.rationale or "").strip():
        raise ValueError("recommendation rationale is required")
    if not 0.0 <= float(recommendation.confidence) <= 1.0:
        raise ValueError("recommendation confidence must be between 0 and 1")
    if not str(recommendation.created_by or "").strip():
        raise ValueError("created_by is required")


def _validate_proposed_action(action: Mapping[str, Any]) -> None:
    action_type = str(action.get("action_type") or "").strip()
    if not action_type:
        raise ValueError("proposed_action.action_type is required")
    payload = action.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("proposed_action.payload must be a mapping")


def emit_recommendation(
    recommendation: Recommendation,
    *,
    db_path: str | Path | None = None,
) -> RecommendationOutcome:
    """Persist a recommendation and its proposed receipt."""
    _validate_recommendation(recommendation)
    created_at = recommendation.created_at or _utc_now()
    outcome_id = f"crec_{uuid.uuid4().hex[:12]}"
    receipt = _build_receipt(
        recommendation_id=recommendation.id,
        decision=DECISION_PROPOSED,
        status=STATUS_PROPOSED,
        actor=recommendation.created_by,
        hitl_action_id=None,
        hitl_status=None,
        gate_status="proposed_waiting_operator_response",
        send_hold_active=False,
        send_hold_blocked=False,
        created_at=created_at,
        reason="",
    )
    ledger_receipt_id = _record_metadata_receipt(
        receipt_id=outcome_id,
        receipt_type="cassandra_recommendation_proposed",
        payload=receipt,
        db_path=db_path,
    )
    if ledger_receipt_id:
        receipt["ledger_receipt_id"] = ledger_receipt_id

    with _connect(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO cassandra_recommendations (
                    recommendation_id, schema_version, surface, summary,
                    proposed_action_json, rationale, confidence, created_by,
                    created_at, status, latest_outcome_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation.id,
                    SCHEMA_VERSION,
                    recommendation.surface,
                    recommendation.summary,
                    _stable_json(dict(recommendation.proposed_action)),
                    recommendation.rationale,
                    float(recommendation.confidence),
                    recommendation.created_by,
                    created_at,
                    STATUS_PROPOSED,
                    outcome_id,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"recommendation already exists: {recommendation.id}") from exc
        _insert_outcome(
            conn,
            outcome_id=outcome_id,
            recommendation_id=recommendation.id,
            decision=DECISION_PROPOSED,
            status=STATUS_PROPOSED,
            actor=recommendation.created_by,
            reason="",
            edits={},
            dispatched_action=dict(recommendation.proposed_action),
            hitl_action_id=None,
            hitl_status=None,
            gate_status="proposed_waiting_operator_response",
            send_hold_active=False,
            send_hold_blocked=False,
            receipt=receipt,
            created_at=created_at,
        )
        conn.commit()

    return RecommendationOutcome(
        outcome_id=outcome_id,
        recommendation_id=recommendation.id,
        decision=DECISION_PROPOSED,
        status=STATUS_PROPOSED,
        actor=recommendation.created_by,
        hitl_action_id=None,
        hitl_status=None,
        gate_status="proposed_waiting_operator_response",
        send_hold_active=False,
        send_hold_blocked=False,
        receipt=receipt,
        created_at=created_at,
    )


def accept_recommendation(
    recommendation_id: str,
    *,
    actor: str = "operator",
    db_path: str | Path | None = None,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> RecommendationOutcome:
    """Accept a recommendation and queue its proposed action through HITL."""
    return _resolve_with_action(
        recommendation_id,
        decision=DECISION_ACCEPTED,
        actor=actor,
        edits={},
        db_path=db_path,
        send_hold_path=send_hold_path,
        ttl_seconds=ttl_seconds,
    )


def modify_recommendation(
    recommendation_id: str,
    edits: Mapping[str, Any],
    *,
    actor: str = "operator",
    db_path: str | Path | None = None,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> RecommendationOutcome:
    """Apply operator edits, then queue the edited action through HITL."""
    if not isinstance(edits, Mapping) or not edits:
        raise ValueError("modify requires a non-empty edits mapping")
    return _resolve_with_action(
        recommendation_id,
        decision=DECISION_MODIFIED,
        actor=actor,
        edits=edits,
        db_path=db_path,
        send_hold_path=send_hold_path,
        ttl_seconds=ttl_seconds,
    )


def deny_recommendation(
    recommendation_id: str,
    reason: str,
    *,
    actor: str = "operator",
    db_path: str | Path | None = None,
) -> RecommendationOutcome:
    """Deny a recommendation, recording why and queueing no action."""
    if not str(reason or "").strip():
        raise ValueError("deny requires a reason")
    recommendation = _load_open_recommendation(recommendation_id, db_path=db_path)
    created_at = _utc_now()
    outcome_id = f"crec_{uuid.uuid4().hex[:12]}"
    receipt = _build_receipt(
        recommendation_id=recommendation["id"],
        decision=DECISION_DENIED,
        status=STATUS_DENIED,
        actor=actor,
        hitl_action_id=None,
        hitl_status=None,
        gate_status="denied_no_action_queued",
        send_hold_active=False,
        send_hold_blocked=False,
        created_at=created_at,
        reason=reason,
    )
    ledger_receipt_id = _record_metadata_receipt(
        receipt_id=outcome_id,
        receipt_type="cassandra_recommendation_denied",
        payload=receipt,
        db_path=db_path,
    )
    if ledger_receipt_id:
        receipt["ledger_receipt_id"] = ledger_receipt_id

    with _connect(db_path) as conn:
        _mark_resolved(
            conn,
            recommendation_id=recommendation["id"],
            status=STATUS_DENIED,
            latest_outcome_id=outcome_id,
            updated_at=created_at,
        )
        _insert_outcome(
            conn,
            outcome_id=outcome_id,
            recommendation_id=recommendation["id"],
            decision=DECISION_DENIED,
            status=STATUS_DENIED,
            actor=actor,
            reason=reason,
            edits={},
            dispatched_action={},
            hitl_action_id=None,
            hitl_status=None,
            gate_status="denied_no_action_queued",
            send_hold_active=False,
            send_hold_blocked=False,
            receipt=receipt,
            created_at=created_at,
        )
        conn.commit()

    return RecommendationOutcome(
        outcome_id=outcome_id,
        recommendation_id=recommendation["id"],
        decision=DECISION_DENIED,
        status=STATUS_DENIED,
        actor=actor,
        hitl_action_id=None,
        hitl_status=None,
        gate_status="denied_no_action_queued",
        send_hold_active=False,
        send_hold_blocked=False,
        receipt=receipt,
        created_at=created_at,
    )


def get_recommendation(
    recommendation_id: str,
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM cassandra_recommendations
            WHERE recommendation_id = ?
            """,
            (recommendation_id,),
        ).fetchone()
    return _recommendation_from_row(row) if row else None


def list_recommendations(
    *,
    status: str | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM cassandra_recommendations"
    params: tuple[Any, ...] = ()
    if status is not None:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY created_at, recommendation_id"
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_recommendation_from_row(row) for row in rows]


def get_recommendation_outcomes(
    recommendation_id: str,
    *,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM cassandra_recommendation_outcomes
            WHERE recommendation_id = ?
            ORDER BY rowid
            """,
            (recommendation_id,),
        ).fetchall()
    return [_outcome_from_row(row) for row in rows]


def _resolve_with_action(
    recommendation_id: str,
    *,
    decision: str,
    actor: str,
    edits: Mapping[str, Any],
    db_path: str | Path | None,
    send_hold_path: str | Path,
    ttl_seconds: int,
) -> RecommendationOutcome:
    recommendation = _load_open_recommendation(recommendation_id, db_path=db_path)
    base_action = dict(recommendation["proposed_action"])
    dispatched_action = _deep_merge(base_action, dict(edits)) if edits else base_action
    _validate_proposed_action(dispatched_action)

    hitl_result = _queue_hitl_action(
        recommendation=recommendation,
        action=dispatched_action,
        decision=decision,
        actor=actor,
        ttl_seconds=ttl_seconds,
    )
    action_type = str(dispatched_action.get("action_type") or "")
    send_hold_active = _send_hold_active(send_hold_path)
    send_hold_blocked = send_hold_active and _is_send_like_action(action_type)
    gate_status = (
        "queued_pending_hitl_send_hold_active"
        if send_hold_blocked
        else "queued_pending_hitl"
    )
    status = STATUS_ACCEPTED if decision == DECISION_ACCEPTED else STATUS_MODIFIED
    created_at = _utc_now()
    outcome_id = f"crec_{uuid.uuid4().hex[:12]}"
    receipt = _build_receipt(
        recommendation_id=recommendation["id"],
        decision=decision,
        status=status,
        actor=actor,
        hitl_action_id=hitl_result["action_id"],
        hitl_status=hitl_result["status"],
        gate_status=gate_status,
        send_hold_active=send_hold_active,
        send_hold_blocked=send_hold_blocked,
        created_at=created_at,
        reason="",
        proposed_action_type=action_type,
    )
    receipt["hitl_created"] = hitl_result["created"]
    receipt["external_send_allowed"] = False if send_hold_blocked else None
    ledger_receipt_id = _record_metadata_receipt(
        receipt_id=outcome_id,
        receipt_type=f"cassandra_recommendation_{decision}",
        payload=receipt,
        db_path=db_path,
    )
    if ledger_receipt_id:
        receipt["ledger_receipt_id"] = ledger_receipt_id

    with _connect(db_path) as conn:
        _mark_resolved(
            conn,
            recommendation_id=recommendation["id"],
            status=status,
            latest_outcome_id=outcome_id,
            updated_at=created_at,
        )
        _insert_outcome(
            conn,
            outcome_id=outcome_id,
            recommendation_id=recommendation["id"],
            decision=decision,
            status=status,
            actor=actor,
            reason="",
            edits=dict(edits),
            dispatched_action=dispatched_action,
            hitl_action_id=hitl_result["action_id"],
            hitl_status=hitl_result["status"],
            gate_status=gate_status,
            send_hold_active=send_hold_active,
            send_hold_blocked=send_hold_blocked,
            receipt=receipt,
            created_at=created_at,
        )
        conn.commit()

    return RecommendationOutcome(
        outcome_id=outcome_id,
        recommendation_id=recommendation["id"],
        decision=decision,
        status=status,
        actor=actor,
        hitl_action_id=hitl_result["action_id"],
        hitl_status=hitl_result["status"],
        gate_status=gate_status,
        send_hold_active=send_hold_active,
        send_hold_blocked=send_hold_blocked,
        receipt=receipt,
        created_at=created_at,
    )


def _queue_hitl_action(
    *,
    recommendation: Mapping[str, Any],
    action: Mapping[str, Any],
    decision: str,
    actor: str,
    ttl_seconds: int,
) -> dict[str, Any]:
    action_type = str(action.get("action_type") or "").strip()
    payload = dict(action.get("payload") or {})
    ttl = int(action.get("ttl_seconds") or ttl_seconds or DEFAULT_TTL_SECONDS)
    route_back = dict(action.get("route_back") or {})
    route_back.setdefault("source", "cassandra_recommendation_loop")
    route_back.setdefault("recommendation_id", recommendation["id"])
    route_back.setdefault("operator_decision", decision)

    request_id = str(
        action.get("request_id")
        or f"cassandra-recommendation:{recommendation['id']}:{decision}"
    )
    owner_agent = str(action.get("owner_agent") or recommendation.get("created_by") or "cassandra")
    owner_objective_id = str(
        action.get("owner_objective_id")
        or f"recommendation:{recommendation['id']}"
    )
    result = hitl_action_service.create_operator_action_approval_request(
        action_type=action_type,
        owner_agent=owner_agent,
        owner_objective_id=owner_objective_id,
        request_id=request_id,
        summary=str(action.get("summary") or recommendation.get("summary") or ""),
        payload=payload,
        risk_warning=str(
            action.get("risk_warning")
            or "Operator approval and downstream gates remain required before execution."
        ),
        expires_at=str(action.get("expires_at") or _expires_at(ttl)),
        route_back=route_back,
        authority_refs=_as_string_list(action.get("authority_refs")),
        credential_lease_refs=_as_string_list(action.get("credential_lease_refs")),
        risk_tier=str(action.get("risk_tier") or "") or None,
        ttl_seconds=ttl,
    )
    return {
        "action_id": str(result.get("action_id") or ""),
        "created": bool(result.get("created")),
        "status": str(result.get("status") or ""),
        "raw": result,
    }


def _load_open_recommendation(
    recommendation_id: str,
    *,
    db_path: str | Path | None,
) -> dict[str, Any]:
    recommendation = get_recommendation(recommendation_id, db_path=db_path)
    if recommendation is None:
        raise ValueError(f"recommendation not found: {recommendation_id}")
    if recommendation["status"] != STATUS_PROPOSED:
        raise ValueError(
            f"recommendation already resolved: {recommendation_id} "
            f"status={recommendation['status']}"
        )
    return recommendation


def _mark_resolved(
    conn: sqlite3.Connection,
    *,
    recommendation_id: str,
    status: str,
    latest_outcome_id: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        UPDATE cassandra_recommendations
        SET status = ?, latest_outcome_id = ?, updated_at = ?
        WHERE recommendation_id = ? AND status = ?
        """,
        (status, latest_outcome_id, updated_at, recommendation_id, STATUS_PROPOSED),
    )
    if conn.total_changes < 1:
        raise ValueError(f"recommendation could not be resolved: {recommendation_id}")


def _insert_outcome(
    conn: sqlite3.Connection,
    *,
    outcome_id: str,
    recommendation_id: str,
    decision: str,
    status: str,
    actor: str,
    reason: str,
    edits: Mapping[str, Any],
    dispatched_action: Mapping[str, Any],
    hitl_action_id: str | None,
    hitl_status: str | None,
    gate_status: str,
    send_hold_active: bool,
    send_hold_blocked: bool,
    receipt: Mapping[str, Any],
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO cassandra_recommendation_outcomes (
            outcome_id, recommendation_id, schema_version, decision, status,
            actor, reason, edits_json, dispatched_action_json, hitl_action_id,
            hitl_status, gate_status, send_hold_active, send_hold_blocked,
            receipt_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            outcome_id,
            recommendation_id,
            OUTCOME_SCHEMA_VERSION,
            decision,
            status,
            actor,
            reason,
            _stable_json(dict(edits)),
            _stable_json(dict(dispatched_action)),
            hitl_action_id,
            hitl_status,
            gate_status,
            1 if send_hold_active else 0,
            1 if send_hold_blocked else 0,
            _stable_json(dict(receipt)),
            created_at,
        ),
    )


def _build_receipt(
    *,
    recommendation_id: str,
    decision: str,
    status: str,
    actor: str,
    hitl_action_id: str | None,
    hitl_status: str | None,
    gate_status: str,
    send_hold_active: bool,
    send_hold_blocked: bool,
    created_at: str,
    reason: str,
    proposed_action_type: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "recommendation_id": recommendation_id,
        "decision": decision,
        "status": status,
        "actor": actor,
        "reason": reason,
        "hitl_action_id": hitl_action_id,
        "hitl_status": hitl_status,
        "gate_status": gate_status,
        "send_hold_active": bool(send_hold_active),
        "send_hold_blocked": bool(send_hold_blocked),
        "proposed_action_type": proposed_action_type,
        "execution_performed": False,
        "external_send_performed": False,
        "approval_bypassed": False,
        "created_at": created_at,
    }


def _record_metadata_receipt(
    *,
    receipt_id: str,
    receipt_type: str,
    payload: Mapping[str, Any],
    db_path: str | Path | None,
) -> str:
    safe_payload = {
        "recommendation_id": payload.get("recommendation_id"),
        "decision": payload.get("decision"),
        "status": payload.get("status"),
        "hitl_action_id": payload.get("hitl_action_id"),
        "hitl_status": payload.get("hitl_status"),
        "gate_status": payload.get("gate_status"),
        "send_hold_active": payload.get("send_hold_active"),
        "send_hold_blocked": payload.get("send_hold_blocked"),
        "execution_performed": False,
        "external_send_performed": False,
        "approval_bypassed": False,
    }
    try:
        path = _db_path(db_path)
        init_business_ops_ledger(path)
        return record_receipt(
            receipt_type=receipt_type,
            payload=safe_payload,
            authority_status="approval_record_only",
            receipt_id=receipt_id,
            actor="cassandra_recommendation_loop",
            db_path=path,
        )
    except Exception:
        return ""


def _recommendation_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["recommendation_id"],
        "schema_version": row["schema_version"],
        "surface": row["surface"],
        "summary": row["summary"],
        "proposed_action": _json_loads(row["proposed_action_json"], {}),
        "rationale": row["rationale"],
        "confidence": row["confidence"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "status": row["status"],
        "latest_outcome_id": row["latest_outcome_id"],
        "updated_at": row["updated_at"],
    }


def _outcome_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "outcome_id": row["outcome_id"],
        "recommendation_id": row["recommendation_id"],
        "schema_version": row["schema_version"],
        "decision": row["decision"],
        "status": row["status"],
        "actor": row["actor"],
        "reason": row["reason"],
        "edits": _json_loads(row["edits_json"], {}),
        "dispatched_action": _json_loads(row["dispatched_action_json"], {}),
        "hitl_action_id": row["hitl_action_id"],
        "hitl_status": row["hitl_status"],
        "gate_status": row["gate_status"],
        "send_hold_active": bool(row["send_hold_active"]),
        "send_hold_blocked": bool(row["send_hold_blocked"]),
        "receipt": _json_loads(row["receipt_json"], {}),
        "created_at": row["created_at"],
    }


def _send_hold_active(send_hold_path: str | Path) -> bool:
    return ensure_send_hold_sentinel(send_hold_path).send_hold_active


def _is_send_like_action(action_type: str) -> bool:
    normalized = str(action_type or "").strip()
    return normalized in SEND_LIKE_ACTION_TYPES or normalized.endswith("_send")


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Sequence):
        return [str(item) for item in value if str(item or "")]
    return [str(value)]


def _deep_merge(base: Mapping[str, Any], edits: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in edits.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


__all__ = [
    "DEFAULT_SEND_HOLD_PATH",
    "DECISION_ACCEPTED",
    "DECISION_DENIED",
    "DECISION_MODIFIED",
    "DECISION_PROPOSED",
    "Recommendation",
    "RecommendationOutcome",
    "STATUS_ACCEPTED",
    "STATUS_DENIED",
    "STATUS_MODIFIED",
    "STATUS_PROPOSED",
    "accept_recommendation",
    "deny_recommendation",
    "emit_recommendation",
    "get_recommendation",
    "get_recommendation_outcomes",
    "list_recommendations",
    "modify_recommendation",
]
