"""Capital Hilton actionable review packet v1.

Builds the clearest review-only operator packet from governed SQLite facts and
existing Capital Hilton/Cassandra-Clara packet posture. It does not send email,
submit Coupa, access credentials, read spreadsheet cells, inspect private raw
data, or grant send/runtime authority.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH
from capital_hilton_finance_fact_intake import init_capital_hilton_fact_intake_schema
from capital_hilton_invoice_packet import CAPITAL_HILTON_PACKET_ID
from cassandra_clara_fact_packet import REQUIRED_FIELDS, stable_json


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "capital_hilton_actionable_review_packet_v1"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "capital_hilton_actionable_review_packet.json"
OPERATOR_EXPORT_NAME = "capital_hilton_actionable_review_packet_OPERATOR.md"
DEFAULT_FACT_PACKET_PATH = DEFAULT_EXPORT_ROOT / "cassandra_clara_fact_packet.json"
DEFAULT_APPROVAL_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_review_packet_approval.json"

SOURCE_POLICY_REQUIRED = "imported_cassandra_chief_memory_sqlite_only"

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "email_sent": False,
    "email_send_allowed": False,
    "portal_submitted": False,
    "portal_submit_allowed": False,
    "credentials_accessed": False,
    "credential_access_allowed": False,
    "spreadsheet_cells_read": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_parsing_allowed": False,
    "bank_access_allowed": False,
    "raw_private_data_read": False,
    "raw_message_bodies_read": False,
    "ad_hoc_memory_used": False,
    "repo_b_execution_allowed": False,
    "send_authority_granted": False,
    "runtime_authority_changed": False,
    "financial_truth_claimed": False,
}

FACT_ALIASES = {
    "recipient_decision": ("recipient_decision", "recipient_cc_decision"),
}

CONTACT_LABEL_PREFIXES = ("contact_candidate_", "operator_remit_email_candidate", "ap_contact_likely", "possible_contacts")

STOP_ACTIONS = (
    "Do not send email or Gmail.",
    "Do not submit, save, upload, or create a payable invoice in Coupa from OpenClaw.",
    "Do not access, store, tokenize, or print credentials in this lane.",
    "Do not read spreadsheet cells or parse workbook formulas.",
    "Do not inspect bank data, private raw files, raw messages, or old HITL state.",
    "Do not treat parsed evidence as financial truth until operator confirmation.",
)


@dataclass(frozen=True)
class CapitalHiltonActionableReviewPacketResult:
    schema_version: str
    actionable_for_manual_review: bool
    ready_for_submission: bool
    missing_required_fact_count: int
    blocker_count: int
    json_path: str
    operator_path: str
    email_sent: bool
    portal_submitted: bool
    credentials_accessed: bool
    spreadsheet_cells_read: bool
    runtime_authority_changed: bool


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


_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(password\s*(is|:|=)|login\s+is|api[_ -]?key\s*[:=]|token\s*[:=]|secret\s*[:=])"
)


def _safe_value(value: object) -> str:
    text = str(value or "").strip()
    if _CREDENTIAL_PATTERN.search(text):
        return "[REDACTED credential-bearing value; operator must handle manually]"
    return text


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _latest_field_rows(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    if _table_exists(conn, "finance_invoice_packet_facts"):
        for row in _dict_rows(
            conn,
            """
SELECT fact_id AS row_id, label AS field_name, value_text, confidence,
       truth_status, source_ref, created_at, 'finance_invoice_packet_facts' AS source_table
FROM finance_invoice_packet_facts
WHERE packet_id = ?
ORDER BY created_at ASC, label ASC
""".strip(),
            (CAPITAL_HILTON_PACKET_ID,),
        ):
            fields[str(row["field_name"])] = row
    if _table_exists(conn, "capital_hilton_invoice_fact_updates"):
        for row in _dict_rows(
            conn,
            """
SELECT fact_update_id AS row_id, field_name, value_text, confidence,
       truth_status, source_ref, created_at, 'capital_hilton_invoice_fact_updates' AS source_table
FROM capital_hilton_invoice_fact_updates
WHERE packet_id = ?
ORDER BY created_at ASC, field_name ASC
""".strip(),
            (CAPITAL_HILTON_PACKET_ID,),
        ):
            fields[str(row["field_name"])] = row
    return fields


def _fact_for(fields: dict[str, dict[str, Any]], field_name: str) -> dict[str, Any] | None:
    aliases = FACT_ALIASES.get(field_name, (field_name,))
    for alias in aliases:
        if alias in fields:
            return fields[alias]
    return None


def _invoice_facts(fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    facts = []
    for field_name, display_name in REQUIRED_FIELDS:
        row = _fact_for(fields, field_name)
        facts.append(
            {
                "field_name": field_name,
                "display_name": display_name,
                "present": row is not None,
                "value_text": _safe_value(row.get("value_text")) if row else "",
                "source_table": row.get("source_table") if row else None,
                "source_ref": row.get("source_ref") if row else None,
                "truth_status": row.get("truth_status") if row else None,
                "evidence_status": "parsed_evidence_not_truth" if row else None,
                "trust_status": "needs_operator_confirmation" if row else None,
                "operator_confirmation_required": True,
                "no_send_authority": True,
                "no_runtime_authority": True,
            }
        )
    return facts


def _contact_posture(fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    contacts = []
    for field_name, row in sorted(fields.items()):
        if field_name.startswith(CONTACT_LABEL_PREFIXES):
            contacts.append(
                {
                    "field_name": field_name,
                    "value_text": _safe_value(row.get("value_text")),
                    "truth_status": row.get("truth_status"),
                    "operator_confirmation_required": True,
                    "email_send_allowed": False,
                }
            )
    return contacts


def _optional_fact(fields: dict[str, dict[str, Any]], name: str) -> str:
    row = fields.get(name)
    return _safe_value(row.get("value_text")) if row else ""


def _review_calculation(facts: list[dict[str, Any]]) -> dict[str, Any]:
    fact_map = {fact["field_name"]: fact["value_text"] for fact in facts if fact["present"]}
    rate = fact_map.get("rate_or_amount_per_gig", "")
    service_dates = [
        fact_map.get("last_friday_gig_date", ""),
        fact_map.get("tonight_gig_date", ""),
    ]
    known_completed = [item for item in service_dates if item]
    candidate_subtotal = ""
    if "$400" in rate and len(known_completed) >= 2:
        candidate_subtotal = "$800 for the two completed governed service-date facts, before any older/upcoming gig review"
    return {
        "review_only": True,
        "rate_or_amount_per_gig": rate,
        "known_completed_service_dates": known_completed,
        "candidate_subtotal": candidate_subtotal,
        "final_total_claimed": False,
        "calculation_note": "Review aid only; do not submit until PO, service list, spreadsheet number, and operator confirmation are complete.",
    }


def _blockers(facts: list[dict[str, Any]], fields: dict[str, dict[str, Any]], fact_packet: dict[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for fact in facts:
        if not fact["present"]:
            blockers.append(
                {
                    "blocker_id": f"missing_{fact['field_name']}",
                    "severity": "blocks_manual_packet_completeness",
                    "description": f"Missing {fact['display_name']}.",
                    "next_safe_move": f"Provide governed fact for {fact['field_name']}.",
                }
            )

    po = next((fact for fact in facts if fact["field_name"] == "po_numbers"), {})
    if "unknown" in str(po.get("value_text", "")).lower():
        blockers.append(
            {
                "blocker_id": "po_coupa_confirmation_required",
                "severity": "blocks_final_submission",
                "description": "PO number is still unknown and must be confirmed manually in Coupa.",
                "next_safe_move": "Operator confirms PO/available credit in Coupa without sharing credentials with OpenClaw.",
            }
        )
    recipient = next((fact for fact in facts if fact["field_name"] == "recipient_decision"), {})
    if "pending confirmation" in str(recipient.get("value_text", "")).lower():
        blockers.append(
            {
                "blocker_id": "recipient_confirmation_required",
                "severity": "blocks_email_send",
                "description": "Recipient posture is review-only and business email still needs operator confirmation.",
                "next_safe_move": "Operator confirms To/CC list before any future email-send lane.",
            }
        )
    attachment = next((fact for fact in facts if fact["field_name"] == "invoice_attachment_output_path"), {})
    if "coupa" in str(attachment.get("value_text", "")).lower():
        blockers.append(
            {
                "blocker_id": "coupa_invoice_creation_manual_only",
                "severity": "blocks_openclaw_submission",
                "description": "Invoice must be created in Coupa against confirmed PO; OpenClaw has no portal/credential authority.",
                "next_safe_move": "Operator manually prepares/reviews Coupa entry or approves a later bounded no-submit portal-review lane.",
            }
        )
    if fields.get("spreadsheet_selection"):
        blockers.append(
            {
                "blocker_id": "spreadsheet_invoice_number_manual_check",
                "severity": "blocks_final_invoice_number_claim",
                "description": "Invoice workbook is known only as metadata; OpenClaw did not read cells or formulas.",
                "next_safe_move": "Operator manually opens the Mac invoice workbook and confirms next invoice number/formulas.",
            }
        )
    if fact_packet.get("usable_capital_hilton_review_packet") is not True:
        blockers.append(
            {
                "blocker_id": "source_fact_packet_not_usable",
                "severity": "blocks_manual_packet_completeness",
                "description": "Cassandra/Clara source packet is not marked usable.",
                "next_safe_move": "Refresh governed facts and regenerate the Cassandra/Clara packet.",
            }
        )
    return blockers


def _manual_steps(facts: list[dict[str, Any]], fields: dict[str, dict[str, Any]]) -> list[str]:
    calculation = _review_calculation(facts)
    service_dates = ", ".join(calculation["known_completed_service_dates"]) or "[confirm service dates]"
    candidate_subtotal = calculation["candidate_subtotal"] or "[calculate manually after confirming service list]"
    spreadsheet = _optional_fact(fields, "spreadsheet_selection") or "Mac Documents/invoices workbook candidate"
    return [
        f"Confirm service dates and service list: {service_dates}. Do not include 2026-05-22 or older gigs unless operator confirms they belong on this invoice.",
        f"Confirm rate and review subtotal: {calculation['rate_or_amount_per_gig'] or '[missing rate]'}; review subtotal candidate: {candidate_subtotal}.",
        "Manually open Coupa/Supplier Portal outside OpenClaw, using operator-controlled credentials only; confirm PO number and available PO credit.",
        f"Manually open the invoice workbook `{spreadsheet}` on the Mac if needed; confirm the current invoice number and set the next invoice number one higher. OpenClaw did not read cells.",
        "Prepare the Coupa invoice manually only after PO, service dates, line items, amount, remit posture, and invoice number are confirmed.",
        "Use recipient posture only as a draft/review list; do not send email from OpenClaw.",
        "Return non-sensitive confirmation metadata to OpenClaw in a later lane if you want a receipt/read-model update.",
    ]


def build_capital_hilton_actionable_review_packet(
    *,
    db_path: str | Path | None = None,
    fact_packet_path: str | Path = DEFAULT_FACT_PACKET_PATH,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    path = init_capital_hilton_fact_intake_schema(db_path or DEFAULT_DB_PATH)
    fact_packet = _read_json_if_present(fact_packet_path)
    approval = _read_json_if_present(approval_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        fields = _latest_field_rows(conn)
    finally:
        conn.close()

    facts = _invoice_facts(fields)
    contacts = _contact_posture(fields)
    missing = [fact for fact in facts if not fact["present"]]
    blockers = _blockers(facts, fields, fact_packet)
    source_packet_approved = approval.get("packet_approved_for_manual_review_preparation") is True
    actionable = not missing and fact_packet.get("usable_capital_hilton_review_packet") is True and source_packet_approved
    ready_for_submission = False
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "target_workflow": "capital_hilton_invoice",
        "packet_id": CAPITAL_HILTON_PACKET_ID,
        "source_policy": SOURCE_POLICY_REQUIRED,
        "source_db_path": _display_path(path),
        "source_read_models": {
            "cassandra_clara_fact_packet": _display_path(fact_packet_path),
            "capital_hilton_review_packet_approval": _display_path(approval_path),
        },
        "source_packet_usable": fact_packet.get("usable_capital_hilton_review_packet") is True,
        "source_packet_approved_for_manual_review_preparation": source_packet_approved,
        "actionable_for_manual_review": actionable,
        "ready_for_submission": ready_for_submission,
        "missing_required_fact_count": len(missing),
        "blocker_count": len(blockers),
        "invoice_facts": facts,
        "review_calculation": _review_calculation(facts),
        "recipient_posture": {
            "contacts": contacts,
            "recipient_decision": next((fact["value_text"] for fact in facts if fact["field_name"] == "recipient_decision"), ""),
            "email_send_allowed": False,
            "operator_confirmation_required": True,
        },
        "po_coupa_confirmation_gate": {
            "required": True,
            "po_confirmed": False,
            "portal_login_allowed": False,
            "portal_submit_allowed": False,
            "credential_access_allowed": False,
            "manual_operator_action_required": True,
            "status": "must_confirm_po_and_credit_in_coupa_before_final_submission",
        },
        "manual_steps": _manual_steps(facts, fields),
        "what_not_to_do": list(STOP_ACTIONS),
        "remaining_blockers": blockers,
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Capital Hilton Manual Coupa PO Confirmation v0",
    }


def format_capital_hilton_actionable_review_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Actionable Review Packet v1",
        "",
        "Status:",
        f"- Actionable for manual review: `{str(payload['actionable_for_manual_review']).lower()}`.",
        "- Ready for submission: `false`.",
        "- Email sent: `false`.",
        "- Portal submitted: `false`.",
        "- Credentials accessed: `false`.",
        "- Spreadsheet cells read: `false`.",
        "",
        "## Invoice Facts",
    ]
    for fact in payload["invoice_facts"]:
        if fact["present"]:
            lines.append(f"- {fact['display_name']}: {fact['value_text']} ({fact['truth_status']}; needs confirmation)")
        else:
            lines.append(f"- {fact['display_name']}: MISSING")

    calc = payload["review_calculation"]
    lines.extend(
        [
            "",
            "## Review Calculation",
            f"- Rate: {calc['rate_or_amount_per_gig'] or '[missing]'}",
            f"- Completed service dates in governed facts: {', '.join(calc['known_completed_service_dates']) or '[missing]'}",
            f"- Candidate subtotal: {calc['candidate_subtotal'] or '[manual calculation required]'}",
            "- Final total claimed: `false`.",
            "",
            "## Recipient Posture",
            f"- {payload['recipient_posture']['recipient_decision'] or '[missing recipient decision]'}",
            "- Email send allowed: `false`.",
        ]
    )
    for contact in payload["recipient_posture"]["contacts"]:
        lines.append(f"- Contact evidence: {contact['value_text']} ({contact['truth_status']})")

    lines.extend(
        [
            "",
            "## PO / Coupa Gate",
            "- PO must be confirmed manually in Coupa before any final submission.",
            "- OpenClaw may not log in, use credentials, upload, save, submit, or create a payable invoice.",
            "",
            "## Exact Manual Steps",
        ]
    )
    for index, step in enumerate(payload["manual_steps"], start=1):
        lines.append(f"{index}. {step}")
    lines.extend(["", "## What Not To Do"])
    for item in payload["what_not_to_do"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Remaining Blockers"])
    if not payload["remaining_blockers"]:
        lines.append("- None for manual review preparation.")
    else:
        for blocker in payload["remaining_blockers"]:
            lines.append(f"- `{blocker['blocker_id']}` ({blocker['severity']}): {blocker['description']} Next: {blocker['next_safe_move']}")
    lines.extend(["", "## Next Safe Lane", f"- {payload['next_recommended_lane']}", ""])
    return "\n".join(lines)


def export_capital_hilton_actionable_review_packet(
    *,
    db_path: str | Path | None = None,
    fact_packet_path: str | Path = DEFAULT_FACT_PACKET_PATH,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CapitalHiltonActionableReviewPacketResult:
    payload = build_capital_hilton_actionable_review_packet(
        db_path=db_path,
        fact_packet_path=fact_packet_path,
        approval_path=approval_path,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_actionable_review_packet(payload), encoding="utf-8")
    return CapitalHiltonActionableReviewPacketResult(
        schema_version=SCHEMA_VERSION,
        actionable_for_manual_review=payload["actionable_for_manual_review"],
        ready_for_submission=payload["ready_for_submission"],
        missing_required_fact_count=payload["missing_required_fact_count"],
        blocker_count=payload["blocker_count"],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        email_sent=False,
        portal_submitted=False,
        credentials_accessed=False,
        spreadsheet_cells_read=False,
        runtime_authority_changed=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton actionable review packet.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite ledger path.")
    parser.add_argument("--fact-packet-json", default=str(DEFAULT_FACT_PACKET_PATH))
    parser.add_argument("--approval-json", default=str(DEFAULT_APPROVAL_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_capital_hilton_actionable_review_packet(
        db_path=args.db,
        fact_packet_path=args.fact_packet_json,
        approval_path=args.approval_json,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(summary.__dict__), end="")
    else:
        payload = build_capital_hilton_actionable_review_packet(
            db_path=args.db,
            fact_packet_path=args.fact_packet_json,
            approval_path=args.approval_json,
        )
        print(format_capital_hilton_actionable_review_packet(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
