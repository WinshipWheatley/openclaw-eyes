"""Synthetic proof for Cassandra listener governed intake.

This module proves the listener replacement seam with a local synthetic update.
It does not import or execute `cassandra_listener.py`, call Telegram, send
messages, switch callers, activate agents, or grant runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_lane_registry import seed_agent_lane_registry
from agent_work_packet import build_agent_work_packet
from business_ops_ledger import DEFAULT_DB_PATH
from telegram_agent_intake import record_telegram_update


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "cassandra_listener_governed_intake_synthetic_proof_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "cassandra_listener_governed_intake_synthetic_proof.json"
OPERATOR_EXPORT_NAME = "cassandra_listener_governed_intake_synthetic_proof_OPERATOR.md"

RUN_ID = "cassandra_listener_governed_intake_synthetic_proof_v0"
SOURCE_CHANNEL = "synthetic_cassandra_governed_intake_proof"
SOURCE_MESSAGE_ID = "synthetic_cassandra_governed_intake_proof_v0"
RECEIVED_AT = "2026-05-17T00:00:00+00:00"
LIVE_TEST_MESSAGE = "Cassandra, receive-only governed intake test: You seeing this through Repo A?"
SYNTHETIC_MESSAGE = (
    "Cassandra, receive-only governed intake test: You seeing this through Repo A? "
    "This synthetic proof body is intentionally longer than the bounded excerpt limit so the "
    "stored record can prove that only a hash and truncated metadata are retained, not the raw "
    "full Telegram body or a reply-capable payload. It is local metadata only."
)

NO_AUTHORITY_FLAGS = {
    "live_receive_proven": False,
    "raw_body_stored": False,
    "send_authority_added": False,
    "reply_authority_added": False,
    "runtime_authority_changed": False,
    "repo_b_executed": False,
    "caller_switched": False,
    "agents_enabled": False,
    "telegram_api_called": False,
    "gmail_api_called": False,
    "network_called": False,
    "runtime_services_mutated": False,
    "live_listener_imported_or_executed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def write_json(path: str | Path, payload: Any) -> str:
    target = rooted(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stable_json(payload), encoding="utf-8")
    return display_path(target)


def write_text(path: str | Path, text: str) -> str:
    target = rooted(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return display_path(target)


def _message_hash(text: str) -> str:
    return hashlib.sha256(("telegram-agent-intake-v0:" + text).encode("utf-8")).hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _dict_row(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _read_observed_rows(db_path: str | Path, update_record_id: str, intent_id: str | None, card_id: str | None) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return {
            "update": _dict_row(conn, "SELECT * FROM telegram_agent_update_records WHERE update_record_id = ?", (update_record_id,)),
            "route": _dict_row(conn, "SELECT * FROM telegram_agent_route_results WHERE update_record_id = ?", (update_record_id,)),
            "receipt": _dict_row(conn, "SELECT * FROM telegram_agent_storage_receipts WHERE update_record_id = ?", (update_record_id,)),
            "intent": _dict_row(conn, "SELECT * FROM intent_records WHERE intent_id = ?", (intent_id,)) if intent_id else None,
            "work_board_card": _dict_row(conn, "SELECT * FROM work_board_cards WHERE card_id = ?", (card_id,)) if card_id else None,
        }
    finally:
        conn.close()


def _make_stage(stage: str, observed: bool, **details: Any) -> dict[str, Any]:
    return {"stage": stage, "observed": observed, **details}


def build_cassandra_listener_governed_intake_synthetic_proof(
    *,
    db_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Create the synthetic proof in SQLite and return the read-model payload."""

    path = str(db_path or DEFAULT_DB_PATH)
    seed_agent_lane_registry(db_path=path, run_id=f"{RUN_ID}_agent_lanes")
    result = record_telegram_update(
        db_path=path,
        text=SYNTHETIC_MESSAGE,
        source_channel=SOURCE_CHANNEL,
        source_message_id=SOURCE_MESSAGE_ID,
        agent_target="cassandra",
        source_user_label="operator",
        operator_message=True,
        route_intent=True,
        create_work_board_card=True,
        run_id=RUN_ID,
        received_at=RECEIVED_AT,
    )

    packet_id: str | None = None
    packet_error: str | None = None
    if result.intent_record_id:
        try:
            packet = build_agent_work_packet(
                db_path=path,
                intent_id=result.intent_record_id,
                packet_id=_row_id("awp", result.intent_record_id, "cassandra_synthetic_proof"),
                run_id=f"{RUN_ID}_agent_work_packet",
            )
            packet_id = packet.packet_id
        except Exception as exc:  # pragma: no cover - tests exercise normal bounded route.
            packet_error = exc.__class__.__name__

    rows = _read_observed_rows(path, result.update_record_id, result.intent_record_id, result.work_board_card_id)
    update = rows["update"] or {}
    route = rows["route"] or {}
    receipt = rows["receipt"] or {}
    intent = rows["intent"] or {}
    work_board_card = rows["work_board_card"] or {}
    excerpt = update.get("message_text_excerpt") or ""
    synthetic_hash = _message_hash(SYNTHETIC_MESSAGE)
    excerpt_truncated = bool(excerpt and len(excerpt) < len(SYNTHETIC_MESSAGE))
    no_send_flags = all(
        not bool(update.get(flag, 0))
        for flag in (
            "telegram_send_allowed",
            "command_execution_allowed",
            "action_auto_execute_allowed",
            "approval_bypass_allowed",
            "external_api_send_allowed",
            "raw_payload_storage_allowed",
        )
    )
    storage_flags_safe = (
        update.get("message_text_stored") == 0
        and update.get("raw_payload_stored") == 0
        and receipt.get("message_text_stored") == 0
        and receipt.get("raw_payload_stored") == 0
    )

    governed_path_observed = [
        _make_stage(
            "telegram_agent_intake",
            bool(update),
            update_record_id=result.update_record_id,
            source_channel=SOURCE_CHANNEL,
            agent_target=update.get("agent_target"),
            message_text_hash_present=bool(update.get("message_text_hash")),
            message_text_excerpt_char_count=len(excerpt),
            excerpt_truncated=excerpt_truncated,
            raw_payload_stored=False,
            message_text_stored=False,
            send_allowed=False,
        ),
        _make_stage(
            "intent_records",
            bool(intent),
            intent_record_id=result.intent_record_id,
            route_status=result.route_status,
            routed_agent_id=result.routed_agent_id,
            routed_lane_id=result.routed_lane_id,
            execution_allowed=False,
        ),
        _make_stage(
            "work_board",
            bool(work_board_card),
            work_board_card_id=result.work_board_card_id,
            board_column=work_board_card.get("board_column"),
            execution_allowed=False,
            auto_execute_allowed=False,
        ),
        _make_stage(
            "agent_work_packet",
            bool(packet_id),
            packet_id=packet_id,
            packet_error=packet_error,
            execution_allowed=False,
            agent_activation_allowed=False,
        ),
        _make_stage(
            "operator_action_guardian_hitl_if_actionable",
            False,
            reason="Synthetic receive-only proof creates no action request; Guardian/Operator Action remains required for any send or runtime action.",
            action_created=False,
            approval_bypass_allowed=False,
        ),
    ]
    blockers: list[str] = []
    if not update:
        blockers.append("telegram_agent_update_record_missing")
    if not route or not result.intent_record_id:
        blockers.append("intent_route_missing")
    if not work_board_card:
        blockers.append("work_board_card_missing")
    if packet_error or not packet_id:
        blockers.append("agent_work_packet_missing")
    if not storage_flags_safe or not excerpt_truncated:
        blockers.append("bounded_metadata_storage_not_proven")
    if not no_send_flags:
        blockers.append("no_send_flags_not_proven")

    synthetic_receive_proven = not blockers
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "db_path": display_path(path),
        "synthetic_receive_proven": synthetic_receive_proven,
        **NO_AUTHORITY_FLAGS,
        "message_proof": {
            "source_channel": SOURCE_CHANNEL,
            "source_message_id": SOURCE_MESSAGE_ID,
            "received_at": RECEIVED_AT,
            "synthetic_message_char_count": len(SYNTHETIC_MESSAGE),
            "synthetic_message_hash": synthetic_hash,
            "stored_excerpt_char_count": len(excerpt),
            "stored_excerpt_truncated": excerpt_truncated,
            "raw_full_body_included_in_read_model": False,
            "message_text_stored": False,
            "raw_payload_stored": False,
        },
        "governed_path_observed": governed_path_observed,
        "route_summary": {
            "route_status": result.route_status,
            "routed_agent_id": result.routed_agent_id,
            "routed_lane_id": result.routed_lane_id,
            "intent_record_id": result.intent_record_id,
            "work_board_card_id": result.work_board_card_id,
            "agent_work_packet_id": packet_id,
            "telegram_route_result_status": route.get("status"),
        },
        "safety_assertions": {
            "raw_body_stored": False,
            "bounded_excerpt_only": excerpt_truncated,
            "message_hash_stored": update.get("message_text_hash") == synthetic_hash,
            "send_authority_added": False,
            "reply_authority_added": False,
            "runtime_authority_changed": False,
            "repo_b_executed": False,
            "caller_switched": False,
            "network_called": False,
            "live_listener_imported_or_executed": False,
        },
        "blockers": blockers,
        "exact_live_test_message": LIVE_TEST_MESSAGE,
        "exact_verification_commands": [
            "cd /home/openclaw",
            "PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_telegram_agent_intake.py --report cassandra-live --format operator",
            "PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_telegram_agent_intake.py --report cassandra-live --format json",
        ],
        "next_safe_move": (
            "Operator live Telegram receive-only test"
            if synthetic_receive_proven
            else "Fix Cassandra governed intake synthetic proof blockers"
        ),
    }


def format_operator_packet(payload: dict[str, Any]) -> str:
    proof = payload["message_proof"]
    lines = [
        "# Cassandra Governed Intake Synthetic Proof v0",
        "",
        "Status:",
        f"- Synthetic receive proven: `{str(payload['synthetic_receive_proven']).lower()}`.",
        "- Live receive proven: `false`.",
        "- Raw body stored: `false`.",
        "- Send authority added: `false`.",
        "- Reply authority added: `false`.",
        "- Runtime authority changed: `false`.",
        "",
        "## What Is Proven",
        "- A Cassandra-targeted synthetic Telegram-style update can be stored as governed Repo A intake metadata.",
        "- The message is routed through deterministic intent records and surfaced on the Work Board.",
        "- A planning-only Agent Work Packet can be built from the routed intent.",
        "- Only hash and bounded excerpt metadata are retained; no full raw body is stored.",
        "",
        "## Governed Path Observed",
    ]
    for stage in payload["governed_path_observed"]:
        status = "observed" if stage["observed"] else "not observed"
        lines.append(f"- `{stage['stage']}`: {status}.")
    lines.extend(
        [
            "",
            "## Storage Proof",
            f"- Synthetic body length: `{proof['synthetic_message_char_count']}` characters.",
            f"- Stored excerpt length: `{proof['stored_excerpt_char_count']}` characters.",
            f"- Excerpt truncated: `{str(proof['stored_excerpt_truncated']).lower()}`.",
            "- Full raw body included in read-model: `false`.",
            "",
            "## What Is Not Proven",
            "- No live Telegram receive has been proven by this lane.",
            "- The legacy listener was not imported, executed, changed, restarted, or replaced.",
            "- No send, reply, runtime, sync, or shell authority was added.",
            "",
            "## Live Test For Winship",
            "Send this exact Telegram message to Cassandra:",
            "",
            f"`{payload['exact_live_test_message']}`",
            "",
            "Then verify from Repo A:",
            "",
        ]
    )
    for command in payload["exact_verification_commands"]:
        lines.append(f"- `{command}`")
    if payload["blockers"]:
        lines.extend(["", "## Blockers", *[f"- {item}" for item in payload["blockers"]]])
    lines.extend(["", "## Next Safe Move", f"- {payload['next_safe_move']}", ""])
    return "\n".join(lines)


def export_cassandra_listener_governed_intake_synthetic_proof(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_cassandra_listener_governed_intake_synthetic_proof(
        db_path=db_path,
        generated_at=generated_at,
    )
    root = rooted(export_root)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    written_json = write_json(json_path, payload)
    written_operator = write_text(operator_path, format_operator_packet(payload))
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_json_path": written_json,
        "read_model_operator_path": written_operator,
        "synthetic_receive_proven": payload["synthetic_receive_proven"],
        "live_receive_proven": False,
        "raw_body_stored": False,
        "send_authority_added": False,
        "reply_authority_added": False,
        "runtime_authority_changed": False,
        "next_recommended_lane": payload["next_safe_move"],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Cassandra listener governed intake synthetic proof.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("json", "operator"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_cassandra_listener_governed_intake_synthetic_proof(
        db_path=args.db,
        export_root=args.export_root,
    )
    if args.format == "operator":
        payload_path = rooted(args.export_root) / JSON_EXPORT_NAME
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        print(format_operator_packet(payload), end="")
    else:
        print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
