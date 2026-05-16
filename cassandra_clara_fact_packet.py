"""Cassandra/Clara fact packet v0.

Builds review-only invoice/contact/email draft artifacts from governed Repo A
SQLite facts and read-model posture. This does not read ad hoc notes, raw
private files, spreadsheet cells, logs, old HITL state, or agent presence
snapshots, and it grants no send or runtime authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH
from capital_hilton_invoice_packet import CAPITAL_HILTON_PACKET_ID
from finance_invoice_evidence_packet import init_finance_invoice_evidence_packet_schema


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "cassandra_clara_fact_packet_v0"
JSON_EXPORT_NAME = "cassandra_clara_fact_packet.json"
OPERATOR_EXPORT_NAME = "cassandra_clara_fact_packet_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_ARTIFACT_ROOT = Path("generated/finance_packets/cassandra_clara_fact_packet_v0")

INTERNAL_AGENT = "cassandra"
EXTERNAL_PERSONA = "Clara Reid"
TARGET_WORKFLOW = "capital_hilton_invoice"

REQUIRED_FIELDS = (
    ("tonight_gig_date", "Exact service date for tonight's gig"),
    ("last_friday_gig_date", "Exact service date for last Friday's gig"),
    ("rate_or_amount_per_gig", "Rate or amount per gig"),
    ("invoice_count_preference", "One invoice or two invoices"),
    ("po_numbers", "PO number(s) or explicit none"),
    ("billing_remit_details", "Billing/remit details"),
    ("recipient_decision", "To/CC recipient decision"),
    ("supplier_portal_reference", "Supplier portal reference"),
    ("invoice_attachment_output_path", "Invoice attachment/output path"),
)

FIELD_LABEL_ALIASES = {
    "recipient_decision": {"recipient_decision", "recipient_cc_decision"},
}

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "runtime_authority_changed": False,
    "runtime_authority": False,
    "no_runtime_authority": True,
    "send_authority_granted": False,
    "no_send_authority": True,
    "email_send_allowed": False,
    "invoice_send_allowed": False,
    "supplier_portal_login_allowed": False,
    "browser_automation_allowed": False,
    "bank_access_allowed": False,
    "ledger_write_allowed": False,
    "external_api_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_parsing_allowed": False,
    "raw_private_files_read": False,
    "raw_messages_read": False,
    "ad_hoc_notes_read": False,
    "old_hitl_read": False,
    "agent_presence_read": False,
    "repo_b_execution_allowed": False,
    "financial_truth_claimed": False,
    "operator_approval_required": True,
}


@dataclass(frozen=True)
class CassandraClaraFactPacketResult:
    schema_version: str
    target_workflow: str
    packet_kind: str
    usable_capital_hilton_review_packet: bool
    missing_required_fact_count: int
    governed_fact_count: int
    contact_candidate_count: int
    artifact_root: str
    read_model_json_path: str
    read_model_operator_path: str
    no_send_authority: bool
    no_runtime_authority: bool


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
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _rooted_path(path: str | Path) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return ROOT / resolved


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _safe_text(value: object, limit: int = 800) -> str:
    return str(value or "").strip()[:limit]


def _governed_fact(row: dict[str, Any], *, field_name: str, value_key: str = "value_text") -> dict[str, Any]:
    return {
        "fact_id": _safe_text(row.get("fact_update_id") or row.get("fact_id") or _row_id("fact", field_name, row.get(value_key))),
        "field_name": field_name,
        "value_text": _safe_text(row.get(value_key)),
        "source_ref": _safe_text(row.get("source_ref")),
        "source_kind": _safe_text(row.get("source_kind") or row.get("fact_kind") or "sqlite_governed_fact"),
        "confidence": _safe_text(row.get("confidence") or "unknown_review"),
        "truth_status": _safe_text(row.get("truth_status") or "needs_review"),
        "evidence_status": "parsed_evidence_not_truth",
        "trust_status": "needs_operator_confirmation",
        "no_send_authority": True,
        "no_runtime_authority": True,
        "approval_required": True,
        "raw_content_read": False,
    }


def _load_governed_facts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if _table_exists(conn, "capital_hilton_invoice_fact_updates"):
        for row in _dict_rows(
            conn,
            """
SELECT fact_update_id, field_name, value_text, source_kind, source_ref,
       confidence, truth_status
FROM capital_hilton_invoice_fact_updates
WHERE packet_id = ?
ORDER BY field_name, created_at
""".strip(),
            (CAPITAL_HILTON_PACKET_ID,),
        ):
            facts.append(_governed_fact(row, field_name=_safe_text(row.get("field_name"))))
    if _table_exists(conn, "finance_invoice_packet_facts"):
        for row in _dict_rows(
            conn,
            """
SELECT fact_id, label, value_text, fact_kind, source_ref, confidence, truth_status
FROM finance_invoice_packet_facts
WHERE packet_id = ?
ORDER BY label, created_at
""".strip(),
            (CAPITAL_HILTON_PACKET_ID,),
        ):
            facts.append(_governed_fact(row, field_name=_safe_text(row.get("label"))))
    return facts


def _load_contact_candidates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(conn, "capital_hilton_contact_candidates"):
        return []
    rows = _dict_rows(
        conn,
        """
SELECT contact_candidate_id, organization, contact_name, role, email,
       confidence, source_basis, allowed_use, external_send_allowed,
       operator_approval_required, verified
FROM capital_hilton_contact_candidates
WHERE packet_id = ?
ORDER BY contact_name
""".strip(),
        (CAPITAL_HILTON_PACKET_ID,),
    )
    candidates = []
    for row in rows:
        candidates.append(
            {
                "contact_candidate_id": _safe_text(row.get("contact_candidate_id")),
                "organization": _safe_text(row.get("organization")),
                "contact_name": _safe_text(row.get("contact_name")),
                "role": _safe_text(row.get("role")),
                "email": _safe_text(row.get("email")) or None,
                "confidence": _safe_text(row.get("confidence")),
                "source_ref": _safe_text(row.get("source_basis")),
                "allowed_use": _safe_text(row.get("allowed_use")),
                "verified": bool(row.get("verified")),
                "evidence_status": "parsed_evidence_not_truth",
                "trust_status": "needs_operator_confirmation",
                "no_send_authority": True,
                "no_runtime_authority": True,
                "approval_required": bool(row.get("operator_approval_required", 1)),
                "external_send_allowed": False,
            }
        )
    return candidates


def _load_missing_items(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(conn, "finance_invoice_packet_missing_items"):
        return []
    return _dict_rows(
        conn,
        """
SELECT description, why_needed, blocker_level, next_safe_move
FROM finance_invoice_packet_missing_items
WHERE packet_id = ?
ORDER BY CASE blocker_level WHEN 'blocks_packet' THEN 0
                            WHEN 'blocks_invoice_draft' THEN 1
                            WHEN 'blocks_send' THEN 2
                            ELSE 3 END,
         description
""".strip(),
        (CAPITAL_HILTON_PACKET_ID,),
    )


def _fact_lookup(facts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup = {}
    for fact in facts:
        key = fact["field_name"]
        if key and key not in lookup:
            lookup[key] = fact
    return lookup


def _field_fact(lookup: dict[str, dict[str, Any]], field_name: str) -> dict[str, Any] | None:
    aliases = {field_name} | FIELD_LABEL_ALIASES.get(field_name, set())
    for alias in aliases:
        fact = lookup.get(alias)
        if fact and fact.get("value_text"):
            return fact
    return None


def _required_status(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = _fact_lookup(facts)
    statuses = []
    for field_name, label in REQUIRED_FIELDS:
        fact = _field_fact(lookup, field_name)
        statuses.append(
            {
                "field_name": field_name,
                "display_name": label,
                "present": fact is not None,
                "fact_id": fact["fact_id"] if fact else None,
                "evidence_status": "parsed_evidence_not_truth" if fact else None,
                "trust_status": "needs_operator_confirmation" if fact else None,
                "next_safe_move": (
                    "Operator confirms this governed fact for draft review."
                    if fact
                    else f"Provide governed Repo A fact for {label}."
                ),
            }
        )
    return statuses


def _artifact_paths(root: Path) -> dict[str, Path]:
    return {
        "missing_facts": root / "CAPITAL_HILTON_MISSING_FACTS_PACKET.md",
        "contact_review": root / "CAPITAL_HILTON_CONTACT_REVIEW.md",
        "draft_email": root / "CAPITAL_HILTON_CLARA_DRAFT_EMAIL_REVIEW_ONLY.md",
        "receivable_review": root / "CAPITAL_HILTON_RECEIVABLE_REVIEW.md",
        "manifest": root / "MANIFEST.json",
    }


def _render_missing_facts(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Missing-Facts Packet",
        "",
        "This packet was built from governed Repo A SQLite/read-model facts only.",
        "",
        f"Usable review packet: `{str(payload['usable_capital_hilton_review_packet']).lower()}`",
        f"Packet kind: `{payload['packet_kind']}`",
        "",
        "## Missing Required Facts",
    ]
    missing = [item for item in payload["required_fact_status"] if not item["present"]]
    if not missing:
        lines.append("- None.")
    else:
        for item in missing:
            lines.append(f"- `{item['field_name']}`: {item['display_name']} -> {item['next_safe_move']}")
    lines.extend(
        [
            "",
            "## Boundaries",
            "- No send authority.",
            "- No runtime authority.",
            "- No raw notes, logs, messages, spreadsheet cells, old HITL, or agent presence snapshots were read.",
            "- All facts remain parsed evidence, not truth, until operator confirmation.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_contact_review(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Contact Review",
        "",
        "Contact candidates are review-only. They do not authorize any email send.",
        "",
    ]
    if not payload["contact_candidates"]:
        lines.append("- No governed contact candidates found.")
    else:
        for contact in payload["contact_candidates"]:
            email = contact["email"] or "unknown"
            lines.append(
                f"- {contact['contact_name']} ({contact['role']}), email={email}, "
                f"allowed_use={contact['allowed_use']}, verified={str(contact['verified']).lower()}"
            )
    lines.extend(["", "Boundary: no-send, no-runtime, needs operator confirmation.", ""])
    return "\n".join(lines)


def _render_draft_email(payload: dict[str, Any]) -> str:
    lookup = _fact_lookup(payload["governed_facts"])

    def value(field_name: str, fallback: str) -> str:
        fact = _field_fact(lookup, field_name)
        return fact["value_text"] if fact else fallback

    recipient = value("recipient_decision", "[MISSING - confirm To/CC recipients]")
    dates = [
        value("tonight_gig_date", "[MISSING tonight gig date]"),
        value("last_friday_gig_date", "[MISSING last Friday gig date]"),
    ]
    amount = value("rate_or_amount_per_gig", "[MISSING amount/rate]")
    invoice_count = value("invoice_count_preference", "[MISSING one invoice or two]")
    po_numbers = value("po_numbers", "[MISSING PO number(s) or explicit none]")
    portal = value("supplier_portal_reference", "[MISSING portal reference]")
    attachment = value("invoice_attachment_output_path", "[MISSING attachment/output path]")

    return f"""# Clara Reid Draft Email - Capital Hilton - Review Only, Do Not Send

To/CC decision: {recipient}
Subject: Capital Hilton invoice review - [operator approval required]

Hi [CONFIRM NAME],

I am preparing the Capital Hilton invoice packet for review.

Governed facts currently available:
- Service dates: {dates[0]}; {dates[1]}
- Rate/amount per gig: {amount}
- Invoice grouping: {invoice_count}
- PO reference: {po_numbers}
- Portal/reference path: {portal}
- Attachment/output path: {attachment}

Before anything is sent or submitted, please confirm the remaining invoice details and recipient list.

Best,
{EXTERNAL_PERSONA}

Boundary: review-only draft. Do not send, submit, upload, attach, or treat these parsed facts as truth until operator confirmation.
"""


def _render_receivable_review(payload: dict[str, Any]) -> str:
    return f"""# Capital Hilton Receivable Review - Draft Only

owner_internal: {INTERNAL_AGENT}
external_persona: {EXTERNAL_PERSONA}
invoice_sent: false
payment_status_claimed: false
send_authority: false
runtime_authority: false

Status:
- Packet kind: {payload['packet_kind']}
- Usable review packet: {str(payload['usable_capital_hilton_review_packet']).lower()}
- Missing required facts: {payload['missing_required_fact_count']}

Next safe move:
{payload['next_safe_lane']}
"""


def _write_artifacts(payload: dict[str, Any], artifact_root: str | Path) -> dict[str, str]:
    root = _rooted_path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    paths = _artifact_paths(root)
    paths["missing_facts"].write_text(_render_missing_facts(payload), encoding="utf-8")
    paths["contact_review"].write_text(_render_contact_review(payload), encoding="utf-8")
    paths["draft_email"].write_text(_render_draft_email(payload), encoding="utf-8")
    paths["receivable_review"].write_text(_render_receivable_review(payload), encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": payload["generated_at"],
        "target_workflow": TARGET_WORKFLOW,
        "packet_kind": payload["packet_kind"],
        "usable_capital_hilton_review_packet": payload["usable_capital_hilton_review_packet"],
        "files": {key: _display_path(path) for key, path in paths.items() if key != "manifest"},
        "boundaries": payload["boundaries"],
    }
    paths["manifest"].write_text(stable_json(manifest), encoding="utf-8")
    return {key: _display_path(path) for key, path in paths.items()}


def build_cassandra_clara_fact_packet(
    *,
    db_path: str | Path | None = None,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    path = init_finance_invoice_evidence_packet_schema(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        facts = _load_governed_facts(conn)
        contacts = _load_contact_candidates(conn)
        missing_rows = _load_missing_items(conn)
    finally:
        conn.close()

    required_status = _required_status(facts)
    missing_required = [item for item in required_status if not item["present"]]
    usable = not missing_required
    packet_kind = "capital_hilton_review_packet" if usable else "capital_hilton_missing_facts_packet"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "target_workflow": TARGET_WORKFLOW,
        "packet_id": CAPITAL_HILTON_PACKET_ID,
        "internal_agent": INTERNAL_AGENT,
        "external_persona": EXTERNAL_PERSONA,
        "source_policy": "governed_repo_a_sqlite_and_read_models_only",
        "sqlite_db_path": str(path),
        "read_model_sources": [
            "generated/read_models/finance_invoice_evidence_packets.json",
            "generated/read_models/cassandra_chief_memory_authority.json",
        ],
        "packet_kind": packet_kind,
        "usable_capital_hilton_review_packet": usable,
        "missing_required_fact_count": len(missing_required),
        "governed_fact_count": len(facts),
        "contact_candidate_count": len(contacts),
        "required_fact_status": required_status,
        "missing_required_fields": missing_required,
        "governed_facts": facts,
        "contact_candidates": contacts,
        "sqlite_missing_items": missing_rows,
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        "raw_data_imported": False,
        "raw_private_files_read": False,
        "ad_hoc_notes_read": False,
        "raw_messages_read": False,
        "spreadsheet_cells_read": False,
        "old_hitl_read": False,
        "agent_presence_read": False,
        "send_authority_granted": False,
        "runtime_authority_changed": False,
        "next_safe_lane": (
            "Capital Hilton Invoice Review Packet Approval v0"
            if usable
            else "Capital Hilton Governed Fact Intake v1"
        ),
    }
    artifacts = _write_artifacts(payload, artifact_root)
    payload["artifact_root"] = _display_path(_rooted_path(artifact_root))
    payload["artifacts"] = artifacts
    return payload


def format_cassandra_clara_fact_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Cassandra/Clara Fact Packet v0",
        "",
        f"Target workflow: `{payload['target_workflow']}`",
        f"Packet kind: `{payload['packet_kind']}`",
        f"Usable Capital Hilton review packet: `{str(payload['usable_capital_hilton_review_packet']).lower()}`",
        f"Governed facts found: `{payload['governed_fact_count']}`",
        f"Contact candidates found: `{payload['contact_candidate_count']}`",
        f"Missing required facts: `{payload['missing_required_fact_count']}`",
        "",
        "## Artifacts",
    ]
    for name, path in payload.get("artifacts", {}).items():
        lines.append(f"- `{name}`: `{path}`")
    lines.extend(["", "## Missing Required Facts"])
    missing = payload.get("missing_required_fields") or []
    if not missing:
        lines.append("- None.")
    else:
        for item in missing:
            lines.append(f"- `{item['field_name']}`: {item['display_name']}")
    lines.extend(
        [
            "",
            "## Boundaries",
            "- No send authority.",
            "- No runtime authority.",
            "- No raw private files, logs, messages, spreadsheet cells, old HITL, or agent presence snapshots were read.",
            "- Facts are parsed evidence, not truth, and need operator confirmation.",
            "",
            "## Next Lane",
            "",
            payload["next_safe_lane"],
            "",
        ]
    )
    return "\n".join(lines)


def export_cassandra_clara_fact_packet(
    *,
    db_path: str | Path | None = None,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CassandraClaraFactPacketResult:
    payload = build_cassandra_clara_fact_packet(
        db_path=db_path,
        artifact_root=artifact_root,
        generated_at=generated_at,
    )
    export_path = _rooted_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_cassandra_clara_fact_packet(payload), encoding="utf-8")
    return CassandraClaraFactPacketResult(
        schema_version=SCHEMA_VERSION,
        target_workflow=TARGET_WORKFLOW,
        packet_kind=payload["packet_kind"],
        usable_capital_hilton_review_packet=payload["usable_capital_hilton_review_packet"],
        missing_required_fact_count=payload["missing_required_fact_count"],
        governed_fact_count=payload["governed_fact_count"],
        contact_candidate_count=payload["contact_candidate_count"],
        artifact_root=payload["artifact_root"],
        read_model_json_path=_display_path(json_path),
        read_model_operator_path=_display_path(operator_path),
        no_send_authority=True,
        no_runtime_authority=True,
    )


__all__ = [
    "DEFAULT_ARTIFACT_ROOT",
    "DEFAULT_EXPORT_ROOT",
    "EXTERNAL_PERSONA",
    "INTERNAL_AGENT",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "REQUIRED_FIELDS",
    "SCHEMA_VERSION",
    "CassandraClaraFactPacketResult",
    "build_cassandra_clara_fact_packet",
    "export_cassandra_clara_fact_packet",
    "format_cassandra_clara_fact_packet",
    "stable_json",
]
