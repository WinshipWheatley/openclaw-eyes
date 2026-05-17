"""Capital Hilton manual confirmation receipt read-model v0.

This module records operator manual confirmation posture for the Capital
Hilton review packet as evidence only. It does not send email, submit Coupa,
read or write spreadsheet cells, create invoice numbers, access credentials,
run Repo B, or grant runtime/approval authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capital_hilton_actionable_review_packet import (
    JSON_EXPORT_NAME as ACTIONABLE_PACKET_JSON_EXPORT_NAME,
    DEFAULT_EXPORT_ROOT,
    stable_json,
)


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "capital_hilton_manual_confirmation_receipt_v0"
JSON_EXPORT_NAME = "capital_hilton_manual_confirmation_receipt.json"
OPERATOR_EXPORT_NAME = "capital_hilton_manual_confirmation_receipt_OPERATOR.md"
DEFAULT_ACTIONABLE_PACKET_PATH = DEFAULT_EXPORT_ROOT / ACTIONABLE_PACKET_JSON_EXPORT_NAME

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "receipts_are_evidence_only": True,
    "external_action_authorized": False,
    "email_sent": False,
    "gmail_or_email_send_triggered": False,
    "telegram_send_triggered": False,
    "coupa_submit_triggered": False,
    "portal_submitted": False,
    "portal_submit_allowed": False,
    "credentials_accessed": False,
    "credential_access_allowed": False,
    "spreadsheet_cells_read": False,
    "spreadsheet_write_triggered": False,
    "spreadsheet_cell_write_allowed": False,
    "invoice_number_created": False,
    "approval_authority_added": False,
    "send_or_submit_authority_added": False,
    "runtime_authority_added": False,
    "repo_b_executed": False,
    "broad_private_ingest_performed": False,
    "confirmations_invented": False,
    "financial_truth_claimed": False,
}

_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(password\s*(is|:|=)|login\s+is|api[_ -]?key\s*[:=]|token\s*[:=]|secret\s*[:=])"
)

SUPPORTED_CONFIRMATION_FIELDS: tuple[dict[str, Any], ...] = (
    {
        "field_name": "po_coupa_requirement_confirmed",
        "display_name": "PO/Coupa requirement confirmed",
        "source_blocker_id": "po_coupa_confirmation_required",
        "confirmation_group": "hard_blocker",
        "required_for_manual_preparation": True,
        "required_satisfied_value": True,
        "pending_status": "pending_po_coupa_confirmation",
    },
    {
        "field_name": "recipient_confirmed",
        "display_name": "Recipient posture confirmed",
        "source_blocker_id": "recipient_confirmation_required",
        "confirmation_group": "hard_blocker",
        "required_for_manual_preparation": True,
        "required_satisfied_value": True,
        "pending_status": "pending_recipient_confirmation",
    },
    {
        "field_name": "coupa_invoice_created_manually",
        "display_name": "Coupa invoice created manually",
        "source_blocker_id": "coupa_invoice_creation_manual_only",
        "confirmation_group": "hard_blocker",
        "required_for_manual_preparation": True,
        "required_satisfied_value": True,
        "pending_status": "pending_manual_coupa_invoice_creation",
    },
    {
        "field_name": "spreadsheet_invoice_number_checked",
        "display_name": "Spreadsheet invoice number checked",
        "source_blocker_id": "spreadsheet_invoice_number_manual_check",
        "confirmation_group": "hard_blocker",
        "required_for_manual_preparation": True,
        "required_satisfied_value": True,
        "pending_status": "pending_spreadsheet_invoice_number_check",
    },
    {
        "field_name": "include_2026_05_22",
        "display_name": "Include 2026-05-22 gig decision",
        "source_blocker_id": None,
        "confirmation_group": "scope_decision",
        "required_for_manual_preparation": False,
        "required_satisfied_value": None,
        "pending_status": "pending_2026_05_22_scope_decision",
    },
    {
        "field_name": "include_older_gigs",
        "display_name": "Include older gigs decision",
        "source_blocker_id": None,
        "confirmation_group": "scope_decision",
        "required_for_manual_preparation": False,
        "required_satisfied_value": None,
        "pending_status": "pending_older_gigs_scope_decision",
    },
)


@dataclass(frozen=True)
class ManualConfirmationReceiptExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    real_confirmations_recorded: bool
    pending_confirmation_count: int
    packet_ready_for_manual_preparation: bool
    packet_ready_for_submission: bool
    coupa_submit_triggered: bool
    spreadsheet_write_triggered: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path) -> dict[str, Any]:
    target = _rooted(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _receipt_id(packet_id: str, field_name: str, decision_value: object) -> str:
    digest = hashlib.sha256(f"{packet_id}\0{field_name}\0{decision_value!r}".encode("utf-8")).hexdigest()
    return f"cap_hilton_manual_receipt_{digest[:20]}"


def _sanitize_label(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if _CREDENTIAL_PATTERN.search(text):
        return "[REDACTED credential-bearing confirmation value]"
    return " ".join(text.split())[:160]


def _safe_confirmation_value(value: object) -> object:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    return _sanitize_label(value)


def _normalize_confirmation_inputs(raw: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not raw:
        return {}
    source = raw.get("confirmations") if isinstance(raw.get("confirmations"), dict) else raw
    normalized: dict[str, dict[str, Any]] = {}
    supported = {item["field_name"] for item in SUPPORTED_CONFIRMATION_FIELDS}
    for field_name, value in source.items():
        if field_name not in supported:
            continue
        if isinstance(value, dict):
            supplied = any(key in value for key in ("confirmed", "decision", "value", "value_label", "operator_value_label"))
            decision_value = value.get("confirmed", value.get("decision", value.get("value")))
            value_label = value.get("value_label", value.get("operator_value_label", decision_value))
            evidence_ref = value.get("evidence_ref", value.get("source_ref", "operator_supplied_confirmation"))
            confirmed_at = value.get("confirmed_at")
            synthetic = bool(value.get("synthetic", raw.get("synthetic", False)))
        else:
            supplied = True
            decision_value = value
            value_label = value
            evidence_ref = "operator_supplied_confirmation"
            confirmed_at = None
            synthetic = bool(raw.get("synthetic", False))
        if supplied:
            normalized[field_name] = {
                "decision_value": _safe_confirmation_value(decision_value),
                "value_label": _sanitize_label(value_label),
                "evidence_ref": _sanitize_label(evidence_ref),
                "confirmed_at": _sanitize_label(confirmed_at),
                "synthetic": synthetic,
            }
    return normalized


def _boolish(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "confirmed", "include"}:
            return True
        if lowered in {"false", "no", "n", "not_confirmed", "exclude", "do_not_include"}:
            return False
    return None


def _confirmation_items(
    *,
    packet_id: str,
    normalized_inputs: dict[str, dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for spec in SUPPORTED_CONFIRMATION_FIELDS:
        field_name = spec["field_name"]
        supplied = normalized_inputs.get(field_name)
        decision_bool = _boolish(supplied.get("decision_value")) if supplied else None
        supplied_value = supplied.get("decision_value") if supplied else None
        is_recorded = supplied is not None
        satisfied = False
        if is_recorded and spec["required_satisfied_value"] is None:
            satisfied = True
        elif is_recorded:
            satisfied = decision_bool is spec["required_satisfied_value"]
        receipt_id = _receipt_id(packet_id, field_name, supplied_value) if is_recorded else None
        items.append(
            {
                "confirmation_key": field_name,
                "field_name": field_name,
                "display_name": spec["display_name"],
                "source_blocker_id": spec["source_blocker_id"],
                "confirmation_group": spec["confirmation_group"],
                "required_for_manual_preparation": spec["required_for_manual_preparation"],
                "status": "recorded" if is_recorded else "pending",
                "pending_status": None if is_recorded else spec["pending_status"],
                "receipt_id": receipt_id,
                "decision_value": supplied_value if is_recorded else None,
                "confirmation_value": supplied_value if is_recorded else None,
                "decision_value_label": supplied["value_label"] if is_recorded else "",
                "confirmation_satisfied": satisfied,
                "evidence_ref": supplied["evidence_ref"] if is_recorded else "",
                "confirmed_at": supplied["confirmed_at"] if is_recorded else "",
                "synthetic": bool(supplied.get("synthetic")) if is_recorded else False,
                "operator_supplied": bool(is_recorded and not supplied.get("synthetic")),
                "evidence_status": "operator_confirmation_evidence"
                if is_recorded
                else "manual_confirmation_pending",
                "no_external_action": True,
                "receipt_kind": "manual_confirmation_evidence" if is_recorded else "manual_confirmation_pending",
                "raw_confirmation_payload_stored": False,
                "external_action_authorized": False,
                "send_or_submit_authority_added": False,
                "runtime_authority_added": False,
                "generated_at": generated_at if is_recorded else None,
            }
        )
    return items


def _source_blocker_map(actionable_packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("blocker_id")): item
        for item in actionable_packet.get("remaining_blockers", [])
        if item.get("blocker_id")
    }


def _remaining_blocked_items(
    *,
    blocker_map: dict[str, dict[str, Any]],
    confirmations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_blocker = {
        item["source_blocker_id"]: item
        for item in confirmations
        if item.get("source_blocker_id")
    }
    blocked: list[dict[str, Any]] = []
    for blocker_id, blocker in sorted(blocker_map.items()):
        confirmation = by_blocker.get(blocker_id)
        if confirmation and confirmation["confirmation_satisfied"]:
            continue
        if confirmation and confirmation["status"] == "recorded":
            status = "explicit_negative_or_unsatisfied_confirmation_recorded"
        else:
            status = "pending_confirmation"
        blocked.append(
            {
                "blocker_id": blocker_id,
                "status": status,
                "confirmation_key": confirmation.get("confirmation_key") if confirmation else "",
                "description": blocker.get("description", ""),
                "severity": blocker.get("severity", ""),
                "next_safe_move": blocker.get("next_safe_move", ""),
                "external_action_authorized": False,
            }
        )
    return blocked


def build_capital_hilton_manual_confirmation_receipt(
    *,
    actionable_packet_path: str | Path = DEFAULT_ACTIONABLE_PACKET_PATH,
    confirmation_inputs: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    actionable_packet = _read_json_if_present(actionable_packet_path)
    packet_id = str(actionable_packet.get("packet_id") or "finance_capital_hilton_invoice_packet_v0")
    normalized = _normalize_confirmation_inputs(confirmation_inputs)
    confirmations = _confirmation_items(packet_id=packet_id, normalized_inputs=normalized, generated_at=generated)
    recorded = [item for item in confirmations if item["status"] == "recorded"]
    pending = [item for item in confirmations if item["status"] == "pending"]
    hard = [item for item in confirmations if item["confirmation_group"] == "hard_blocker"]
    scope = [item for item in confirmations if item["confirmation_group"] == "scope_decision"]
    blocker_map = _source_blocker_map(actionable_packet)
    remaining_blocked_items = _remaining_blocked_items(blocker_map=blocker_map, confirmations=confirmations)
    hard_cleared = bool(hard) and all(item["confirmation_satisfied"] for item in hard)
    scope_pending = any(item["status"] == "pending" for item in scope)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated,
        "target_workflow": "capital_hilton_invoice",
        "workflow_domain": "finance_ap_invoice",
        "workflow_name": "capital_hilton_invoice_manual_confirmation",
        "packet_identity": {
            "packet_id": packet_id,
            "source_packet_schema_version": actionable_packet.get("schema_version"),
            "source_packet_path": _display_path(actionable_packet_path),
            "source_packet_present": bool(actionable_packet),
            "source_packet_review_only": bool(actionable_packet.get("review_only", True)),
            "source_packet_actionable_for_manual_review": bool(
                actionable_packet.get("actionable_for_manual_review", False)
            ),
            "source_packet_ready_for_submission": bool(actionable_packet.get("ready_for_submission", False)),
        },
        "confirmation_contract": {
            "contract_kind": "manual_confirmation_receipt_for_review_packet",
            "supported_fields": [item["field_name"] for item in SUPPORTED_CONFIRMATION_FIELDS],
            "generalizable_to_other_review_packets": True,
            "confirmation_values_required_from_operator": True,
            "explicit_operator_values_required": True,
            "capture_input_path": "scripts/export_capital_hilton_manual_confirmation_receipt.py --confirmations-json <operator-confirmations.json>",
            "client_specific_overlay": "hilton_coupa_supplier_portal",
            "two_invoice_workflow_contract": "capital_hilton_two_invoice_workflow_v0",
            "field_alignment": {
                "po_coupa_requirement_confirmed": "Hilton Coupa PO requirement understood; not portal submission.",
                "recipient_confirmed": "Excel companion/reference communication posture; not email send authority.",
                "coupa_invoice_created_manually": "Manual Coupa payment invoice creation evidence; not OpenClaw portal creation.",
                "spreadsheet_invoice_number_checked": "Excel companion invoice number/workbook check; not spreadsheet write authority.",
                "include_2026_05_22": "Scope decision for companion invoice/future payment planning.",
                "include_older_gigs": "Scope decision for companion invoice/historical context.",
            },
            "accepted_input_shape": {
                "confirmations": {
                    "po_coupa_requirement_confirmed": "true/false or {confirmed: true/false, evidence_ref: string}",
                    "recipient_confirmed": "true/false or {confirmed: true/false, evidence_ref: string}",
                    "coupa_invoice_created_manually": "true/false or {confirmed: true/false, evidence_ref: string}",
                    "spreadsheet_invoice_number_checked": "true/false or {confirmed: true/false, evidence_ref: string}",
                    "include_2026_05_22": "include/exclude true/false decision",
                    "include_older_gigs": "include/exclude true/false decision",
                }
            },
            "no_confirmations_invented": True,
        },
        "source_blockers": [
            {
                "blocker_id": blocker_id,
                "description": blocker.get("description", ""),
                "severity": blocker.get("severity", ""),
                "next_safe_move": blocker.get("next_safe_move", ""),
            }
            for blocker_id, blocker in sorted(blocker_map.items())
        ],
        "confirmation_items": confirmations,
        "confirmed_items": [item for item in confirmations if item["status"] == "recorded"],
        "pending_items": pending,
        "recorded_confirmation_keys": [item["confirmation_key"] for item in recorded],
        "pending_confirmation_keys": [item["confirmation_key"] for item in pending],
        "remaining_blocked_items": remaining_blocked_items,
        "remaining_blocked_item_count": len(remaining_blocked_items),
        "manual_confirmation_evidence": [
            {
                "receipt_id": item["receipt_id"],
                "confirmation_key": item["confirmation_key"],
                "field_name": item["field_name"],
                "confirmation_value": item["confirmation_value"],
                "decision_value_label": item["decision_value_label"],
                "confirmation_satisfied": item["confirmation_satisfied"],
                "operator_supplied": item["operator_supplied"],
                "evidence_status": item["evidence_status"],
                "evidence_ref": item["evidence_ref"],
                "synthetic": item["synthetic"],
                "no_external_action": True,
                "receipts_are_evidence_only": True,
            }
            for item in recorded
        ],
        "real_confirmations_recorded": any(item["synthetic"] is False for item in recorded),
        "synthetic_confirmations_recorded": any(item["synthetic"] is True for item in recorded),
        "recorded_confirmation_count": len(recorded),
        "pending_confirmation_count": len(pending),
        "hard_blocker_confirmation_count": len(hard),
        "hard_blockers_cleared_by_receipt": hard_cleared,
        "scope_decision_pending": scope_pending,
        "packet_ready_after_confirmations": {
            "packet_ready_for_manual_preparation": hard_cleared,
            "packet_scope_still_pending": scope_pending,
            "packet_ready_for_submission": False,
            "submission_blocked_reason": "Manual receipts do not grant Coupa submit, email send, spreadsheet write, or runtime authority.",
        },
        "read_model_posture": {
            "review_only": True,
            "receipts_are_evidence_only": True,
            "pending_blockers_preserved": bool(pending),
            "remaining_blockers_preserved": bool(remaining_blocked_items),
            "confirmations_invented": False,
            "old_packet_blockers_not_deleted": True,
            "operator_supplied_values_required": True,
        },
        "next_recommended_lane": (
            "Capital Hilton Coupa Payment Invoice Proof Capture v0"
            if not hard_cleared
            else "Capital Hilton Operator Action Readiness Review v0"
        ),
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_capital_hilton_manual_confirmation_receipt(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Manual Confirmation Receipts",
        "",
        "Status:",
        f"- Real confirmations recorded: `{str(payload['real_confirmations_recorded']).lower()}`.",
        f"- Recorded confirmation count: `{payload['recorded_confirmation_count']}`.",
        f"- Pending confirmation count: `{payload['pending_confirmation_count']}`.",
        f"- Remaining blocked item count: `{payload['remaining_blocked_item_count']}`.",
        f"- Packet ready for manual preparation: `{str(payload['packet_ready_after_confirmations']['packet_ready_for_manual_preparation']).lower()}`.",
        "- Packet ready for submission: `false`.",
        "- Email/Gmail sent: `false`.",
        "- Coupa submitted: `false`.",
        "- Spreadsheet write triggered: `false`.",
        "",
        "## Recorded Confirmations",
    ]
    if payload["confirmed_items"]:
        for item in payload["confirmed_items"]:
            synthetic = "synthetic test receipt" if item["synthetic"] else "operator evidence"
            lines.append(
                f"- `{item['field_name']}`: {item['decision_value_label']} "
                f"({synthetic}; satisfied={str(item['confirmation_satisfied']).lower()})"
            )
    else:
        lines.append("- None. No operator confirmation values were supplied in this lane.")

    lines.extend(["", "## Pending Confirmations"])
    for item in payload["pending_items"]:
        lines.append(f"- `{item['field_name']}`: {item['display_name']} ({item['pending_status']})")

    lines.extend(["", "## Remaining Blocked Items"])
    if payload["remaining_blocked_items"]:
        for item in payload["remaining_blocked_items"]:
            lines.append(f"- `{item['blocker_id']}`: {item['status']} - {item['description']}")
    else:
        lines.append("- None cleared by current receipt evidence, but external send/submit remains blocked.")

    lines.extend(
        [
            "",
            "## Source Packet Blockers",
        ]
    )
    for blocker in payload["source_blockers"]:
        lines.append(f"- `{blocker['blocker_id']}`: {blocker['description']}")

    lines.extend(
        [
            "",
            "## Boundary",
            "- Receipts are evidence only.",
            "- No send path, Gmail/email path, Coupa submit, spreadsheet write, runtime action, or approval authority was added.",
            "- Pending items stay pending until explicit operator confirmation values are provided.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_manual_confirmation_receipt(
    *,
    actionable_packet_path: str | Path = DEFAULT_ACTIONABLE_PACKET_PATH,
    confirmation_inputs: dict[str, Any] | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ManualConfirmationReceiptExportResult:
    payload = build_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=actionable_packet_path,
        confirmation_inputs=confirmation_inputs,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_manual_confirmation_receipt(payload), encoding="utf-8")
    readiness = payload["packet_ready_after_confirmations"]
    return ManualConfirmationReceiptExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        real_confirmations_recorded=payload["real_confirmations_recorded"],
        pending_confirmation_count=payload["pending_confirmation_count"],
        packet_ready_for_manual_preparation=readiness["packet_ready_for_manual_preparation"],
        packet_ready_for_submission=readiness["packet_ready_for_submission"],
        coupa_submit_triggered=False,
        spreadsheet_write_triggered=False,
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton manual confirmation receipt read-model.")
    parser.add_argument("--actionable-packet-json", default=str(DEFAULT_ACTIONABLE_PACKET_PATH))
    parser.add_argument("--confirmations-json", default="", help="Optional JSON file with explicit operator confirmations.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    confirmation_inputs = _read_json_if_present(args.confirmations_json) if args.confirmations_json else None
    result = export_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=args.actionable_packet_json,
        confirmation_inputs=confirmation_inputs,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_capital_hilton_manual_confirmation_receipt(
            actionable_packet_path=args.actionable_packet_json,
            confirmation_inputs=confirmation_inputs,
        )
        print(format_capital_hilton_manual_confirmation_receipt(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
