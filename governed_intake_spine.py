"""Unified Governed Intake Spine v0.

This module is a thin deterministic bridge over existing Repo A substrate:
operator text -> intent record -> optional Work Board / Agent Work Packet
projection. It does not execute, approve, send, call models, call networks, or
read private/no-go content.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_work_packet import build_agent_work_packet
from business_ops_ledger import DEFAULT_DB_PATH
from intent_router import IntentRouteResult, init_intent_router_schema, route_operator_intent
from work_board import build_work_board


GOVERNED_INTAKE_SPINE_VERSION = "governed_intake_spine_v0"
READ_MODEL_VERSION = "governed_intake_spine_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "governed_intake_spine.json"
OPERATOR_EXPORT_NAME = "governed_intake_spine_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "execution_allowed": False,
    "action_created": False,
    "approval_bypass_allowed": False,
    "auto_approval_allowed": False,
    "auto_execute_allowed": False,
    "agent_activation_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "telegram_send_allowed": False,
    "smtp_send_allowed": False,
    "repo_creation_allowed": False,
    "deployment_allowed": False,
    "runtime_authority": False,
    "arbitrary_shell_allowed": False,
    "raw_private_content_read": False,
}


@dataclass(frozen=True)
class GovernedIntakeResult:
    intake_id: str
    intent_id: str
    route_status: str
    routed_agent_id: str | None
    routed_lane_id: str | None
    intent_category: str
    confidence: float
    work_board_card_id: str | None
    work_packet_id: str | None
    execution_allowed: bool = False
    action_created: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(__file__).resolve().parent)
    except (OSError, ValueError):
        return path_obj.as_posix()


def _work_board_card_id(db_path: str | Path, intent_id: str) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
SELECT card_id
FROM work_board_cards
WHERE source_kind = 'intent_record' AND source_id = ?
ORDER BY updated_at DESC, card_id DESC
LIMIT 1
""".strip(),
            (intent_id,),
        ).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def capture_governed_operator_intake(
    *,
    raw_text: str,
    source_kind: str = "cli",
    source_channel: str = "governed_intake_spine",
    requested_by: str = "operator",
    source_message_id: str | None = None,
    source_user_label: str | None = "operator",
    db_path: str | Path | None = None,
    create_work_board_card: bool = True,
    create_agent_work_packet: bool = False,
    intent_id: str | None = None,
    run_id: str | None = None,
) -> GovernedIntakeResult:
    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text is required")
    path = init_intent_router_schema(db_path or DEFAULT_DB_PATH)
    text_hash = hashlib.sha256(raw_text.strip().encode("utf-8")).hexdigest()
    resolved_intake_id = _row_id("gintake", source_kind, source_channel, requested_by, text_hash)
    resolved_intent_id = intent_id or _row_id("intent", "governed_intake", resolved_intake_id)
    resolved_run_id = run_id or _row_id("irun", "governed_intake", resolved_intake_id)

    route_result: IntentRouteResult = route_operator_intent(
        text=raw_text,
        source_kind=source_kind,
        source_channel=source_channel,
        requested_by=requested_by,
        source_message_id=source_message_id,
        source_user_label=source_user_label,
        db_path=path,
        intent_id=resolved_intent_id,
        run_id=resolved_run_id,
    )

    work_board_card_id: str | None = None
    if create_work_board_card:
        build_work_board(db_path=path, run_id=_row_id("wbrun", "governed_intake", resolved_intent_id, utc_now()))
        work_board_card_id = _work_board_card_id(path, resolved_intent_id)

    work_packet_id: str | None = None
    if create_agent_work_packet and route_result.status == "routed":
        packet = build_agent_work_packet(
            db_path=path,
            intent_id=route_result.intent_id,
            packet_id=_row_id("awp", "governed_intake", route_result.intent_id),
            run_id=_row_id("awprun", "governed_intake", route_result.intent_id),
        )
        work_packet_id = packet.packet_id

    return GovernedIntakeResult(
        intake_id=resolved_intake_id,
        intent_id=route_result.intent_id,
        route_status=route_result.status,
        routed_agent_id=route_result.routed_agent_id,
        routed_lane_id=route_result.routed_lane_id,
        intent_category=route_result.intent_category,
        confidence=route_result.confidence,
        work_board_card_id=work_board_card_id,
        work_packet_id=work_packet_id,
        execution_allowed=False,
        action_created=False,
    )


def _spine_rows(db_path: str | Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
SELECT intent_id, source_kind, source_channel, requested_by,
       routed_agent_id, routed_lane_id, world_hint, intent_category,
       confidence, status, created_at, execution_allowed,
       action_request_created, raw_text_stored
FROM intent_records
WHERE source_channel LIKE 'governed_intake_spine%'
ORDER BY created_at DESC, intent_id DESC
LIMIT 50
""".strip()
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def build_governed_intake_spine_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = init_intent_router_schema(db_path or DEFAULT_DB_PATH)
    rows = _spine_rows(path)
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "generated_at": utc_now(),
        "source_ledger_path": str(_display_path(path)),
        "source_ledger_namespace": "intent_router_* plus optional work_board_* / agent_work_packet_*",
        "record_count": len(rows),
        "records": rows,
        "capability_status": {
            "deterministic_intent_record": True,
            "work_board_projection_supported": True,
            "agent_work_packet_projection_supported": True,
            "llm_classification_used": False,
            "telegram_send_allowed": False,
            "external_send_allowed": False,
        },
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_governed_intake_spine_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Governed Intake Spine Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over deterministic governed intake records captured through Repo A routing.",
        "",
        "What this is not:",
        "- It is not execution, approval, Telegram send, SMTP send, model calling, network access, repo creation, or deployment.",
        "",
        "Summary:",
        f"- Captured spine records: {read_model['record_count']}.",
        "",
        "Latest records:",
    ]
    for item in read_model["records"][:10]:
        lines.append(
            f"- `{item['intent_id']}` status=`{item['status']}` agent=`{item['routed_agent_id'] or 'none'}` "
            f"category=`{item['intent_category']}` execution_allowed=`{bool(item['execution_allowed'])}`"
        )
    if not read_model["records"]:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Boundary:",
            "- `execution_allowed=false`; `action_created=false`; `approval_bypass_allowed=false`.",
            "- No raw private content, external sends, runtime activation, or arbitrary shell behavior.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_governed_intake_spine_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent / root
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_governed_intake_spine_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_governed_intake_spine_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "record_count": read_model["record_count"],
        **NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "GOVERNED_INTAKE_SPINE_VERSION",
    "NO_AUTHORITY_FLAGS",
    "READ_MODEL_VERSION",
    "GovernedIntakeResult",
    "build_governed_intake_spine_read_model",
    "capture_governed_operator_intake",
    "export_governed_intake_spine_read_model",
    "format_governed_intake_spine_read_model",
    "stable_json",
]
