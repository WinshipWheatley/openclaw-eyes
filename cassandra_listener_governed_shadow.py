"""Cassandra listener governed shadow replacement read-model.

This module maps the high-risk `cassandra_listener.py` surface to the intended
governed intake path. It does not import or execute the listener, read Telegram
logs, send messages, switch callers, edit services, or grant runtime authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "cassandra_listener_governed_shadow_v0"
DEFAULT_DECISION_PACKET_PATH = Path("generated/read_models/active_machinery_quarantine_decision_packet.json")
DEFAULT_READY_PACKET_PATH = Path("docs/operations/ACTIVE_MACHINERY_REPLACE_WITH_GOVERNED_PATH_READY_PACKET.json")
DEFAULT_GUARDRAIL_PATH = Path("generated/read_models/active_machinery_block_later_guardrail.json")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "cassandra_listener_governed_shadow.json"
OPERATOR_EXPORT_NAME = "cassandra_listener_governed_shadow_OPERATOR.md"

GOVERNED_TARGET_PATH = [
    "telegram_agent_intake",
    "governed_intake_spine",
    "intent_records",
    "work_board",
    "agent_work_packet",
    "operator_action_guardian_hitl_if_actionable",
]

NO_AUTHORITY_FLAGS = {
    "runtime_authority_changed": False,
    "runtime_authority": False,
    "caller_switched": False,
    "live_listener_replaced": False,
    "live_listener_touched": False,
    "high_risk_file_edited": False,
    "services_disabled": False,
    "launchers_edited": False,
    "agents_enabled": False,
    "telegram_send_allowed": False,
    "gmail_email_send_allowed": False,
    "external_send_allowed": False,
    "runtime_activation_allowed": False,
    "sync_bridge_authority": False,
    "shell_execution_allowed": False,
    "repo_b_executed": False,
    "raw_telegram_body_stored": False,
    "raw_private_content_read": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def load_json(path: str | Path) -> dict[str, Any]:
    target = rooted(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {display_path(target)}")
    return payload


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


def _find_cassandra_listener(decision_packet: dict[str, Any]) -> dict[str, Any]:
    replace_group = (decision_packet.get("decision_buckets") or {}).get("replace_with_governed_path") or {}
    for item in replace_group.get("items", []):
        if item.get("relative_path") == "cassandra_listener.py":
            return item
    raise ValueError("cassandra_listener.py was not found in replace_with_governed_path decision bucket")


def _ready_item(ready_packet: dict[str, Any]) -> dict[str, Any]:
    for item in ready_packet.get("replace_with_governed_path_items", []):
        if item.get("relative_path") == "cassandra_listener.py":
            return item
    raise ValueError("cassandra_listener.py was not found in replacement ready packet")


def build_cassandra_listener_governed_shadow(
    *,
    decision_packet_path: str | Path = DEFAULT_DECISION_PACKET_PATH,
    ready_packet_path: str | Path = DEFAULT_READY_PACKET_PATH,
    guardrail_path: str | Path = DEFAULT_GUARDRAIL_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    decision_packet = load_json(decision_packet_path)
    ready_packet = load_json(ready_packet_path)
    guardrail = load_json(guardrail_path)
    if decision_packet.get("schema_version") != "active_machinery_quarantine_decision_packet_v0":
        raise ValueError("expected active machinery quarantine decision packet")
    if not ready_packet.get("ready_for_implementation"):
        raise ValueError("replacement ready packet is not marked ready_for_implementation")
    if ready_packet.get("ready_for_runtime_replacement") is not False:
        raise ValueError("this lane requires ready_for_runtime_replacement=false")
    if guardrail.get("schema_version") != "active_machinery_block_later_guardrail_v0":
        raise ValueError("expected active machinery block-later guardrail read-model")

    listener = _find_cassandra_listener(decision_packet)
    ready = _ready_item(ready_packet)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "mode": "shadow_replacement_read_model_only",
        "source_files": {
            "decision_packet": display_path(rooted(decision_packet_path)),
            "replacement_ready_packet": display_path(rooted(ready_packet_path)),
            "block_later_guardrail": display_path(rooted(guardrail_path)),
        },
        **NO_AUTHORITY_FLAGS,
        "replacement_surface": {
            "relative_path": "cassandra_listener.py",
            "surface_id": listener.get("surface_id"),
            "decision_bucket": listener.get("decision_bucket"),
            "current_risk": listener.get("current_risk"),
            "what_it_is": listener.get("what_it_is"),
            "current_static_references": listener.get("current_static_references") or [],
            "current_static_dependencies": listener.get("blocks") or {},
            "live_listener_imported_or_executed": False,
        },
        "current_listener_summary": {
            "static_role": "Listener-style Cassandra intake surface.",
            "static_signals": [
                "approval/HITL",
                "daemon/listener",
                "importer/exporter",
                "send/API",
                "shell/process",
                "sync bridge",
            ],
            "unsafe_as_is": [
                "can behave like a live listener outside governed intake",
                "send/API and shell/process signals require Guardian/Operator Action boundary",
                "service/start references require proof and rollback before caller switch",
            ],
            "source_of_summary": "decision and replacement spec metadata only; cassandra_listener.py was not imported or executed",
        },
        "expected_input": {
            "input_kind": "telegram_update_metadata_only",
            "allowed_fields": [
                "source_surface_id",
                "source_channel",
                "agent_target",
                "source_message_id_hash",
                "source_user_label_or_hash",
                "received_at",
                "message_text_hash",
                "sanitized_preview_optional",
                "tenant_id_or_owner_scope_if_available",
                "idempotency_key",
                "sensitivity_level",
            ],
            "raw_telegram_body_allowed": False,
            "raw_telegram_body_stored": False,
            "private_content_allowed": False,
            "telegram_api_call_allowed": False,
            "message_text_storage_allowed": False,
            "hash_or_sanitized_preview_only": True,
        },
        "target_governed_path": [
            {
                "stage": "telegram_agent_intake",
                "role": "store bounded Telegram-facing metadata and hashes",
                "raw_payload_storage_allowed": False,
                "send_allowed": False,
            },
            {
                "stage": "governed_intake_spine",
                "role": "bridge metadata into deterministic intent routing",
                "execution_allowed": False,
                "model_call_allowed": False,
            },
            {
                "stage": "intent_records",
                "role": "record deterministic route or needs-review result",
                "unknown_input_route": "needs_operator_review",
            },
            {
                "stage": "work_board",
                "role": "surface a review/planning card when useful",
                "auto_execute_allowed": False,
            },
            {
                "stage": "agent_work_packet",
                "role": "draft bounded work packet only after route is safe",
                "agent_activation_allowed": False,
            },
            {
                "stage": "operator_action_guardian_hitl_if_actionable",
                "role": "required for any send, runtime, sync bridge, or external action",
                "approval_required": True,
            },
        ],
        "governed_path_names": GOVERNED_TARGET_PATH,
        "mapping_to_existing_surfaces": {
            "telegram_agent_intake": True,
            "governed_intake_spine": True,
            "intent_records": True,
            "work_board": True,
            "agent_work_packet": True,
            "operator_action": True,
            "operator_action_inbox": True,
            "guardian_hitl": "required only for action-capable proposals",
            "memory_authority": "parsed facts only; no ad hoc listener state authority",
            "sync_bridge": "read-model/export posture only; no sync authority",
            "module_registry": "cassandra_clara_fact_intake / operator_comms_stack boundary metadata",
        },
        "legacy_surfaces_remaining": [
            "cassandra_listener.py",
            "systemd/user/cassandra-listener.service.in",
            "start_cassandra_core.sh",
        ],
        "blocked_until_proven": [
            "direct listener activation",
            "caller switch",
            "service disable or edit",
            "launcher edit",
            "reply/send path",
            "runtime recovery action",
            "shell/process execution",
            "sync bridge authority",
            "raw Telegram body storage",
        ],
        "proof_required_before_caller_switch": [
            "metadata-only intake fixture maps to telegram_agent_intake shape",
            "governed_intake_spine route is deterministic",
            "unknown input routes to review/triage",
            "Work Board / Agent Work Packet outputs are deterministic",
            "Operator Action is required for any action-capable proposal",
            "no raw Telegram body or private content is stored",
            "service/start references are represented but untouched",
        ],
        "ready_packet_alignment": {
            "recommended_lane": ready_packet.get("recommended_lane"),
            "governed_target": ready.get("governed_target"),
            "runtime_replacement_authorized": bool(ready.get("runtime_replacement_authorized")),
            "readiness_scope": ready_packet.get("readiness_scope"),
        },
        "next_safe_move": "Cassandra Listener Governed Intake Synthetic Proof v0",
    }


def format_operator_packet(payload: dict[str, Any]) -> str:
    surface = payload["replacement_surface"]
    lines = [
        "# Cassandra Listener Governed Shadow v0",
        "",
        "Status:",
        "- Shadow/read-model only: `true`.",
        "- Runtime authority changed: `false`.",
        "- Caller switched: `false`.",
        "- Live listener replaced: `false`.",
        "- Raw Telegram body stored: `false`.",
        "",
        "## Current Listener",
        f"- Surface: `{surface['relative_path']}`.",
        f"- Risk: `{surface['current_risk']}`.",
        f"- Static references: {'; '.join(surface['current_static_references'])}.",
        "- The live listener was not imported, executed, edited, or replaced.",
        "",
        "## Governed Replacement Path",
    ]
    for stage in payload["target_governed_path"]:
        lines.append(f"- `{stage['stage']}`: {stage['role']}")
    lines.extend(
        [
            "",
            "## Expected Input",
            "- Telegram/update metadata only.",
            "- Hashes and sanitized preview only where needed.",
            "- No raw Telegram body, private content, token, or credential material.",
            "",
            "## Still Legacy",
            *[f"- `{item}`" for item in payload["legacy_surfaces_remaining"]],
            "",
            "## Blocked Until Proven",
            *[f"- {item}" for item in payload["blocked_until_proven"]],
            "",
            "## Proof Needed Before Caller Switch",
            *[f"- {item}" for item in payload["proof_required_before_caller_switch"]],
            "",
            "## Next Safe Move",
            f"- {payload['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_cassandra_listener_governed_shadow(
    *,
    decision_packet_path: str | Path = DEFAULT_DECISION_PACKET_PATH,
    ready_packet_path: str | Path = DEFAULT_READY_PACKET_PATH,
    guardrail_path: str | Path = DEFAULT_GUARDRAIL_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_cassandra_listener_governed_shadow(
        decision_packet_path=decision_packet_path,
        ready_packet_path=ready_packet_path,
        guardrail_path=guardrail_path,
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
        "runtime_authority_changed": False,
        "caller_switched": False,
        "live_listener_replaced": False,
        "raw_telegram_body_stored": False,
        "next_recommended_lane": payload["next_safe_move"],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Cassandra listener governed shadow read-model.")
    parser.add_argument("--decision-packet-path", default=DEFAULT_DECISION_PACKET_PATH.as_posix())
    parser.add_argument("--ready-packet-path", default=DEFAULT_READY_PACKET_PATH.as_posix())
    parser.add_argument("--guardrail-path", default=DEFAULT_GUARDRAIL_PATH.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("json", "operator"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_cassandra_listener_governed_shadow(
        decision_packet_path=args.decision_packet_path,
        ready_packet_path=args.ready_packet_path,
        guardrail_path=args.guardrail_path,
        export_root=args.export_root,
    )
    if args.format == "operator":
        payload = load_json(Path(args.export_root) / JSON_EXPORT_NAME)
        print(format_operator_packet(payload), end="")
    else:
        print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
