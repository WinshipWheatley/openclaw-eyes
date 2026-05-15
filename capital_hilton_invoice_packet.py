"""Capital Hilton Invoice Packet v0.

Creates a real, reviewable invoice evidence packet for the Capital Hilton gigs
without sending email, submitting portal forms, reading spreadsheets, accessing
banks, writing ledgers, or making final financial truth claims.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH
from finance_invoice_evidence_packet import (
    FinancePacketFactInput,
    MAC_SPREADSHEET_FOLDER,
    MAC_SPREADSHEET_NEXT_LANE,
    build_finance_invoice_evidence_packet,
    export_finance_invoice_evidence_packets_read_model,
    init_finance_invoice_evidence_packet_schema,
    stable_json,
)
from work_board import DEFAULT_BOARD_ID


ROOT = Path(__file__).resolve().parent
CAPITAL_HILTON_PACKET_ID = "finance_capital_hilton_invoice_packet_v0"
CAPITAL_HILTON_RUN_PREFIX = "capital_hilton_invoice_packet_v0"
DEFAULT_ARTIFACT_ROOT = Path("generated/finance_packets/capital_hilton_invoice_packet_v0")

NO_AUTHORITY_FLAGS = {
    "email_send_allowed": False,
    "invoice_send_allowed": False,
    "supplier_portal_login_allowed": False,
    "browser_automation_allowed": False,
    "bank_access_allowed": False,
    "ledger_write_allowed": False,
    "external_api_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "repo_b_execution_allowed": False,
    "financial_truth_claimed": False,
    "operator_approval_required": True,
}


@dataclass(frozen=True)
class CapitalHiltonPacketResult:
    packet_id: str
    run_id: str
    db_path: str
    artifact_root: str
    draft_email_path: str
    portal_prompt_path: str
    receivable_proposal_path: str
    packet_summary_path: str
    missing_required_fact_count: int
    output_count: int
    work_board_card_count: int
    financial_truth_claimed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _artifact_root_path(artifact_root: str | Path) -> Path:
    path = Path(artifact_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _facts() -> list[FinancePacketFactInput]:
    return [
        FinancePacketFactInput(
            label="client_location",
            value_text="Capital Hilton / Capitol Hilton",
            fact_kind="operator_supplied",
            confidence="operator_claim",
            truth_status="unverified_claim",
            source_ref="operator_prompt:capital_hilton_invoice_packet_v0",
        ),
        FinancePacketFactInput(
            label="gig_scope",
            value_text="Two gigs: tonight's gig and last Friday's gig. Exact dates require operator confirmation.",
            fact_kind="operator_supplied",
            confidence="operator_claim",
            truth_status="unverified_claim",
            source_ref="operator_prompt:capital_hilton_invoice_packet_v0",
        ),
        FinancePacketFactInput(
            label="ap_contact_likely",
            value_text="Annette Sunga",
            fact_kind="operator_supplied",
            confidence="operator_claim",
            truth_status="needs_review",
            source_ref="operator_prompt:capital_hilton_invoice_packet_v0",
        ),
        FinancePacketFactInput(
            label="possible_contacts",
            value_text=(
                "Chyna Hardin, Director of Finance, Chyna.Hardin@hilton.com; "
                "Lawrence / Will Valcovic, lawrencevalcovic@hilton.com"
            ),
            fact_kind="operator_supplied",
            confidence="operator_claim",
            truth_status="needs_review",
            source_ref="operator_prompt:capital_hilton_invoice_packet_v0",
        ),
        FinancePacketFactInput(
            label="supplier_portal_context",
            value_text="Supplier portal has previously been SmartSpend / Coupa related.",
            fact_kind="operator_supplied",
            confidence="operator_claim",
            truth_status="needs_review",
            source_ref="operator_prompt:capital_hilton_invoice_packet_v0",
        ),
        FinancePacketFactInput(
            label="remit_email",
            value_text="winshiplive@gmail.com",
            fact_kind="operator_supplied",
            confidence="operator_claim",
            truth_status="unverified_claim",
            source_ref="operator_prompt:capital_hilton_invoice_packet_v0",
        ),
    ]


def _required_missing_items() -> list[dict[str, str]]:
    return [
        {
            "description": "Exact date for tonight's gig is not operator-confirmed for invoice use.",
            "why_needed": "Invoice packet must not infer gig dates from relative wording.",
            "blocker_level": "blocks_invoice_draft",
            "next_safe_move": "Operator confirms the invoice date/service date for tonight's gig.",
        },
        {
            "description": "Exact date for last Friday's gig is not operator-confirmed for invoice use.",
            "why_needed": "Invoice packet must not infer prior gig dates from relative wording.",
            "blocker_level": "blocks_invoice_draft",
            "next_safe_move": "Operator confirms the invoice date/service date for last Friday's gig.",
        },
        {
            "description": "Amount or rate per gig is missing.",
            "why_needed": "No invoice amount can be claimed or drafted without operator-provided or approved evidence.",
            "blocker_level": "blocks_invoice_draft",
            "next_safe_move": "Operator provides rate/amount per gig or approved evidence reference.",
        },
        {
            "description": "One invoice versus two invoices is undecided.",
            "why_needed": "Portal/email packet needs invoice grouping before any draft can be prepared.",
            "blocker_level": "blocks_invoice_draft",
            "next_safe_move": "Operator chooses one combined invoice or separate invoices per gig.",
        },
        {
            "description": "PO number(s) are missing.",
            "why_needed": "Capital Hilton supplier/payment flow may require PO references.",
            "blocker_level": "blocks_invoice_draft",
            "next_safe_move": "Operator provides PO number(s), says none, or approves portal metadata lookup later.",
        },
        {
            "description": "Billing/remit details need confirmation.",
            "why_needed": "The packet has remit email context only; full invoice/remit details require operator confirmation.",
            "blocker_level": "blocks_invoice_draft",
            "next_safe_move": "Operator confirms billing name, remit email, mailing/payment details, and any tax/remit fields.",
        },
        {
            "description": "Recipient and CC decision is pending.",
            "why_needed": "The packet has likely/possible contacts but should not choose recipients without review.",
            "blocker_level": "blocks_send",
            "next_safe_move": "Operator confirms To/CC list before any email draft is used.",
        },
        {
            "description": "Supplier portal reference is unresolved.",
            "why_needed": "SmartSpend/Coupa context is operator-supplied but not verified for this invoice.",
            "blocker_level": "blocks_invoice_draft",
            "next_safe_move": "Operator confirms whether SmartSpend/Coupa is required and provides portal reference if known.",
        },
        {
            "description": "Invoice attachment/output path is missing.",
            "why_needed": "No final invoice file should be created or attached until output path and approval are explicit.",
            "blocker_level": "blocks_send",
            "next_safe_move": "Operator chooses or approves invoice attachment/output path in a later lane.",
        },
    ]


def _risk_items() -> list[dict[str, str]]:
    return [
        {
            "risk_kind": "missing_amount",
            "severity": "high",
            "mitigation": "Operator must provide amount/rate per gig or approved evidence before any invoice draft context can be considered.",
        },
        {
            "risk_kind": "missing_date",
            "severity": "medium",
            "mitigation": "Operator must confirm exact service dates for tonight's gig and last Friday's gig.",
        },
        {
            "risk_kind": "unsupported_claim",
            "severity": "high",
            "mitigation": "Treat all Capital Hilton facts as operator claims until dates, amount, PO, recipient, and portal reference are confirmed.",
        },
        {
            "risk_kind": "send_not_allowed",
            "severity": "high",
            "mitigation": "Draft email is review-only; no send or external communication is authorized.",
        },
        {
            "risk_kind": "bank_data_needed",
            "severity": "medium",
            "mitigation": "Payment tracking later requires approved bank/ledger evidence; this lane performs no bank access.",
        },
        {
            "risk_kind": "sensitive_data_needed",
            "severity": "medium",
            "mitigation": "Invoice details and spreadsheet data remain sensitive metadata only until approved evidence intake.",
        },
        {
            "risk_kind": "spreadsheet_needs_review",
            "severity": "medium",
            "mitigation": f"Treat {MAC_SPREADSHEET_FOLDER} as sensitive metadata only; next safe lane is {MAC_SPREADSHEET_NEXT_LANE}.",
        },
    ]


def draft_email_body() -> str:
    return """# Capital Hilton Draft Email - Review Only, Do Not Send

To: [CONFIRM RECIPIENT - likely Annette Sunga]
CC: [CONFIRM CC - possibly Chyna Hardin and/or Lawrence / Will Valcovic]
From/Remit email context: winshiplive@gmail.com
Subject: Invoice for music services - [CONFIRM DATE(S)]

Hi [CONFIRM NAME],

I am preparing invoice documentation for two Capital Hilton gigs:

- Tonight's gig: [CONFIRM EXACT DATE]
- Last Friday's gig: [CONFIRM EXACT DATE]

Before I send the invoice or upload it through SmartSpend/Coupa, could you please confirm:

- Whether these should be one combined invoice or two separate invoices
- The PO number(s), if required
- The correct recipient/CC list
- Whether SmartSpend/Coupa is the required submission path
- Any required invoice attachment or vendor reference details

Amount/rate fields are intentionally left blank until confirmed:

- Rate/amount per gig: [CONFIRM AMOUNT/RATE]
- Total: [DO NOT FILL UNTIL APPROVED]

Best,
Clara Reid

Boundary: This is a draft for operator review only. Do not send, attach, submit, or treat any amount/date/recipient as final until approved.
"""


def portal_fill_prompt() -> str:
    return """# Codex Desktop Prompt - Capital Hilton Portal Fill Prep, No Submit

You are helping prepare a supplier portal invoice entry for Capital Hilton on the Mac/Safari side.

Hard boundaries:
- Do not submit anything.
- Do not send email.
- Do not access bank portals.
- Do not read spreadsheet cells unless a separate approved Mac spreadsheet intake lane authorizes it.
- Do not invent dates, amounts, PO numbers, recipient details, or totals.
- Stop before any irreversible action, final save, upload, or submit button.

Known operator-supplied context:
- Client/location: Capital Hilton / Capitol Hilton.
- Gigs: tonight's gig and last Friday's gig.
- Finance/AP contact likely: Annette Sunga.
- Possible contacts: Chyna Hardin and Lawrence / Will Valcovic.
- Supplier portal context has previously been SmartSpend / Coupa related.
- Remit email context: winshiplive@gmail.com.

Missing facts to collect from the operator before portal entry:
- Exact date for tonight's gig.
- Exact date for last Friday's gig.
- Amount/rate per gig.
- One invoice or two.
- PO number(s).
- Billing/remit details.
- Recipient/CC decision.
- Supplier portal reference.
- Invoice attachment/output path.
- Mac invoice spreadsheet exact filename or approved Mac metadata packet, if the spreadsheet is relevant.

Allowed work:
1. Present the missing-facts checklist to the operator.
2. If the operator supplies facts, prepare a portal-fill checklist with placeholders resolved.
3. Keep all fields as draft/review-only.
4. Stop before login, upload, final save, or submit unless a later explicit approval is provided.
5. Treat ~/Documents/invoices/ as sensitive metadata only; do not read workbook cells in this prompt.
"""


def receivable_tracking_proposal() -> str:
    return """# Capital Hilton Receivable Tracking Proposal - Review Only

status: pending_invoice_approval
follow_up_owner_internal: Cassandra
follow_up_external_persona: Clara Reid
follow_up_email_sent: false
invoice_sent: false
payment_tracking_status: not_started

Scope:
- Track two Capital Hilton gigs after invoice details are approved.
- Do not send follow-up email yet.
- Do not claim payment is due, paid, unpaid, or overdue without approved invoice and payment evidence.
- Payment tracking requires later approved bank/ledger evidence or operator-provided payment confirmation.

Next safe moves:
1. Operator confirms missing invoice facts.
2. OpenClaw prepares draft invoice context only.
3. Operator approves send/submission path in a later lane.
4. After approved send/submission, Clara Reid may own follow-up reminders as metadata only until sending is separately approved.
"""


def packet_summary() -> str:
    return """# Capital Hilton Invoice Packet v0 - Summary

Purpose: prepare a reviewable evidence packet for two Capital Hilton gigs without sending anything or making financial truth claims.

Current status: pending required facts.

Known operator-supplied context:
- Client/location: Capital Hilton / Capitol Hilton.
- AP contact likely: Annette Sunga.
- Possible contacts: Chyna Hardin and Lawrence / Will Valcovic.
- Portal context: SmartSpend / Coupa related in prior flow.
- Remit email context: winshiplive@gmail.com.
- Mac spreadsheet candidate: ~/Documents/invoices/ is known as a sensitive metadata-only candidate, but no filename or workbook cells were read.

Missing required facts:
- Exact date for tonight's gig.
- Exact date for last Friday's gig.
- Amount/rate per gig.
- One invoice or two.
- PO number(s).
- Billing/remit details.
- Recipient/CC decision.
- Supplier portal reference.
- Invoice attachment/output path.
- Spreadsheet filename or approved Mac-side metadata packet, if the spreadsheet is needed.

Boundaries: no send, no submit, no portal login, no bank access, no ledger write, no spreadsheet cell read, no final invoice.
"""


def _write_artifacts(artifact_root: Path) -> dict[str, Path]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "draft_email": artifact_root / "CAPITAL_HILTON_DRAFT_EMAIL_REVIEW_ONLY.md",
        "portal_prompt": artifact_root / "CAPITAL_HILTON_PORTAL_FILL_PROMPT_NO_SUBMIT.md",
        "receivable_proposal": artifact_root / "CAPITAL_HILTON_RECEIVABLE_TRACKING_PROPOSAL.md",
        "packet_summary": artifact_root / "CAPITAL_HILTON_PACKET_SUMMARY.md",
        "manifest": artifact_root / "MANIFEST.json",
    }
    paths["draft_email"].write_text(draft_email_body(), encoding="utf-8")
    paths["portal_prompt"].write_text(portal_fill_prompt(), encoding="utf-8")
    paths["receivable_proposal"].write_text(receivable_tracking_proposal(), encoding="utf-8")
    paths["packet_summary"].write_text(packet_summary(), encoding="utf-8")
    manifest = {
        "schema_version": "capital_hilton_invoice_packet_v0",
        "generated_at": utc_now(),
        "packet_id": CAPITAL_HILTON_PACKET_ID,
        "files": {key: _display_path(path) for key, path in paths.items() if key != "manifest"},
        "no_authority_flags": NO_AUTHORITY_FLAGS,
    }
    paths["manifest"].write_text(stable_json(manifest), encoding="utf-8")
    return paths


def _insert_missing_items(conn: sqlite3.Connection, *, packet_id: str, now: str) -> int:
    count = 0
    for item in _required_missing_items():
        conn.execute(
            """
INSERT OR REPLACE INTO finance_invoice_packet_missing_items (
  missing_item_id, packet_id, description, why_needed,
  blocker_level, next_safe_move, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("finpktmiss", packet_id, item["description"]),
                packet_id,
                item["description"],
                item["why_needed"],
                item["blocker_level"],
                item["next_safe_move"],
                now,
            ),
        )
        count += 1
    conn.execute(
        """
INSERT OR REPLACE INTO finance_invoice_packet_missing_items (
  missing_item_id, packet_id, description, why_needed,
  blocker_level, next_safe_move, created_at
) VALUES (?, ?, ?, ?, 'optional', ?, ?)
""".strip(),
        (
            _row_id("finpktmiss", packet_id, "capital_hilton_mac_spreadsheet_metadata"),
            packet_id,
            "Mac invoice spreadsheet filename or metadata packet is not available.",
            "The operator reports a likely relevant spreadsheet, but this PC/WSL lane must not read the Mac Documents folder or workbook cells.",
            MAC_SPREADSHEET_NEXT_LANE,
            now,
        ),
    )
    return count


def _insert_risks(conn: sqlite3.Connection, *, packet_id: str, now: str) -> int:
    count = 0
    for risk in _risk_items():
        conn.execute(
            """
INSERT OR REPLACE INTO finance_invoice_packet_risks (
  risk_id, packet_id, risk_kind, severity, mitigation, created_at
) VALUES (?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("finpktrisk", packet_id, risk["risk_kind"], risk["mitigation"]),
                packet_id,
                risk["risk_kind"],
                risk["severity"],
                risk["mitigation"],
                now,
            ),
        )
        count += 1
    return count


def _insert_outputs(conn: sqlite3.Connection, *, packet_id: str, paths: dict[str, Path], now: str) -> int:
    outputs = [
        (
            "capital_hilton_draft_email_review_only",
            "Draft email body for operator review only",
            draft_email_body(),
            paths["draft_email"],
        ),
        (
            "capital_hilton_portal_fill_instruction_prompt",
            "Codex Desktop portal-fill instruction prompt, no submit",
            portal_fill_prompt(),
            paths["portal_prompt"],
        ),
        (
            "capital_hilton_receivable_tracking_proposal",
            "Receivable tracking proposal pending invoice approval",
            receivable_tracking_proposal(),
            paths["receivable_proposal"],
        ),
        (
            "capital_hilton_packet_summary",
            "Capital Hilton packet summary and missing facts",
            packet_summary(),
            paths["packet_summary"],
        ),
    ]
    for output_kind, title, body, path in outputs:
        conn.execute(
            """
INSERT OR REPLACE INTO finance_invoice_packet_outputs (
  output_id, packet_id, output_kind, title, body_text,
  send_allowed, invoice_creation_allowed, raw_sensitive_body_included,
  created_at
) VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?)
""".strip(),
            (_row_id("finpktout", packet_id, output_kind), packet_id, output_kind, f"{title} (`{_display_path(path)}`)", body, now),
        )
    return len(outputs)


def _insert_work_board_cards(conn: sqlite3.Connection, *, packet_id: str, now: str) -> int:
    board_id = DEFAULT_BOARD_ID
    conn.execute(
        """
INSERT INTO work_boards (
  board_id, board_name, board_version, description, created_at, updated_at,
  direct_execution_allowed, auto_approval_allowed, auto_execute_allowed,
  agent_activation_allowed
) VALUES (?, 'OpenClaw Work Board', 'openclaw_work_board_v0', ?, ?, ?, 0, 0, 0, 0)
ON CONFLICT(board_id) DO UPDATE SET updated_at = excluded.updated_at
""".strip(),
        (board_id, "Local review board over OpenClaw control-plane metadata, including finance invoice packets.", now, now),
    )
    specs = [
        (
            "capital_hilton_invoice_packet_needs_facts",
            "Capital Hilton invoice packet needs facts",
            "Capital Hilton packet exists but exact gig dates, rate/amount, PO, invoice grouping, recipient, portal reference, and attachment path need review.",
            "needs_review",
            "pending_required_facts",
            "Ask operator to answer the Capital Hilton missing-facts checklist.",
            "chief",
            "system_orchestration",
        ),
        (
            "capital_hilton_portal_fill_prompt_pending_approval",
            "Capital Hilton portal-fill prompt pending approval",
            "Review-only Codex Desktop/Mac prompt exists. No portal login, upload, save, or submit is authorized.",
            "needs_review",
            "portal_prompt_review_only",
            "Operator reviews prompt and approves a future Mac/Safari portal-prep lane if needed.",
            "chief",
            "system_orchestration",
        ),
        (
            "capital_hilton_receivable_tracking_pending_invoice_send",
            "Capital Hilton receivable tracking pending invoice send",
            "Receivable tracking proposal is pending invoice approval; Cassandra follow-up is later and no email has been sent.",
            "planned",
            "pending_invoice_approval",
            "After approved invoice send/submission, create a receivable tracking packet with approved evidence.",
            "cassandra",
            "operator_comms",
        ),
    ]
    for source_suffix, title, summary, column, status, next_safe_move, agent_id, lane_id in specs:
        source_id = f"capital_hilton_invoice_packet:{source_suffix}"
        card_id = _row_id("wbcard", board_id, "manual_seed", source_id)
        conn.execute(
            """
INSERT INTO work_board_cards (
  card_id, board_id, title, summary, source_kind, source_id, world_hint,
  agent_id, lane_id, intent_category, board_column, status, priority_hint,
  approval_required, execution_allowed, action_request_id, work_packet_id,
  receipt_id, blocker_reason, next_safe_move, evidence_basis, created_at,
  updated_at, raw_body_stored, direct_execution_allowed, arbitrary_shell_allowed,
  auto_approval_allowed, auto_execute_allowed, agent_activation_allowed,
  model_call_allowed, tool_execution_allowed, network_authority,
  no_go_raw_access_allowed, file_move_allowed, file_delete_allowed,
  client_deployment_allowed
) VALUES (?, ?, ?, ?, 'manual_seed', ?, 'finance', ?,
  ?, 'capital_hilton_invoice_packet', ?, ?, 'high',
  1, 0, NULL, NULL, NULL, NULL, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(board_id, source_kind, source_id) DO UPDATE SET
  title = excluded.title,
  summary = excluded.summary,
  world_hint = excluded.world_hint,
  agent_id = excluded.agent_id,
  lane_id = excluded.lane_id,
  intent_category = excluded.intent_category,
  board_column = excluded.board_column,
  status = excluded.status,
  approval_required = 1,
  execution_allowed = 0,
  next_safe_move = excluded.next_safe_move,
  evidence_basis = excluded.evidence_basis,
  updated_at = excluded.updated_at,
  raw_body_stored = 0,
  direct_execution_allowed = 0,
  arbitrary_shell_allowed = 0,
  auto_approval_allowed = 0,
  auto_execute_allowed = 0,
  agent_activation_allowed = 0,
  model_call_allowed = 0,
  tool_execution_allowed = 0,
  network_authority = 0,
  no_go_raw_access_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  client_deployment_allowed = 0
""".strip(),
            (
                card_id,
                board_id,
                title,
                summary,
                source_id,
                agent_id,
                lane_id,
                column,
                status,
                next_safe_move,
                f"capital_hilton_invoice_packet:{packet_id}",
                now,
                now,
            ),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_sources (
  card_source_id, card_id, source_kind, source_id, source_path,
  source_summary, raw_body_stored, created_at
) VALUES (?, ?, 'manual_seed', ?, NULL, ?, 0, ?)
""".strip(),
            (_row_id("wbsrc", card_id, source_id), card_id, source_id, summary, now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_agents (
  card_agent_id, card_id, agent_id, lane_id, role,
  can_execute, can_bypass_approval, created_at
) VALUES (?, ?, ?, ?, 'assigned_lane', 0, 0, ?)
""".strip(),
            (_row_id("wbagent", card_id, agent_id), card_id, agent_id, lane_id, now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_worlds (
  card_world_id, card_id, world_hint, confidence, created_at
) VALUES (?, ?, 'finance', 'metadata_hint', ?)
""".strip(),
            (_row_id("wbworld", card_id, "finance"), card_id, now),
        )
    return len(specs)


def build_capital_hilton_invoice_packet(
    *,
    db_path: str | Path | None = None,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    run_id: str | None = None,
    export_read_model: bool = True,
    read_model_export_root: str | Path = "generated/read_models",
) -> CapitalHiltonPacketResult:
    path = init_finance_invoice_evidence_packet_schema(db_path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("caprun", CAPITAL_HILTON_RUN_PREFIX, now)
    base = build_finance_invoice_evidence_packet(
        db_path=path,
        title="Capital Hilton Invoice Evidence Packet v0",
        subject="Capital Hilton / Capitol Hilton",
        workflow_kind="invoice_prep",
        facts=_facts(),
        packet_id=CAPITAL_HILTON_PACKET_ID,
        run_id=resolved_run_id,
        synthetic_demo=False,
        create_work_board_cards=True,
    )
    root = _artifact_root_path(artifact_root)
    paths = _write_artifacts(root)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("DELETE FROM finance_invoice_packet_missing_items WHERE packet_id = ?", (base.packet_id,))
        conn.execute("DELETE FROM finance_invoice_packet_risks WHERE packet_id = ?", (base.packet_id,))
        missing_count = _insert_missing_items(conn, packet_id=base.packet_id, now=now)
        risk_count = _insert_risks(conn, packet_id=base.packet_id, now=now)
        output_count = _insert_outputs(conn, packet_id=base.packet_id, paths=paths, now=now)
        card_count = _insert_work_board_cards(conn, packet_id=base.packet_id, now=now)
        conn.execute(
            """
UPDATE finance_invoice_packets
SET status = 'blocked_missing_info',
    next_safe_move = ?,
    financial_truth_claimed = 0,
    send_allowed = 0,
    bank_access_allowed = 0,
    ledger_write_allowed = 0,
    tax_filing_allowed = 0,
    updated_at = ?
WHERE packet_id = ?
""".strip(),
            (
                "Answer the Capital Hilton missing-facts checklist; then review draft email and portal prompt without sending/submitting.",
                now,
                base.packet_id,
            ),
        )
        conn.execute(
            """
UPDATE finance_invoice_packet_runs
SET missing_item_count = (
      SELECT COUNT(*) FROM finance_invoice_packet_missing_items WHERE packet_id = ?
    ),
    risk_count = (
      SELECT COUNT(*) FROM finance_invoice_packet_risks WHERE packet_id = ?
    ),
    work_board_card_count = work_board_card_count + ?,
    financial_truth_claimed = 0
WHERE run_id = ?
""".strip(),
            (base.packet_id, base.packet_id, card_count, resolved_run_id),
        )
        conn.commit()
        if export_read_model:
            export_finance_invoice_evidence_packets_read_model(db_path=path, export_root=read_model_export_root)
        return CapitalHiltonPacketResult(
            packet_id=base.packet_id,
            run_id=resolved_run_id,
            db_path=path,
            artifact_root=_display_path(root),
            draft_email_path=_display_path(paths["draft_email"]),
            portal_prompt_path=_display_path(paths["portal_prompt"]),
            receivable_proposal_path=_display_path(paths["receivable_proposal"]),
            packet_summary_path=_display_path(paths["packet_summary"]),
            missing_required_fact_count=missing_count,
            output_count=output_count,
            work_board_card_count=card_count,
            financial_truth_claimed=False,
        )
    finally:
        conn.close()


def format_capital_hilton_invoice_packet_result(result: CapitalHiltonPacketResult) -> str:
    return "\n".join(
        [
            "Capital Hilton Invoice Packet v0",
            "",
            f"Packet: `{result.packet_id}`",
            f"Run: `{result.run_id}`",
            f"Artifact root: `{result.artifact_root}`",
            f"Draft email: `{result.draft_email_path}`",
            f"Portal prompt: `{result.portal_prompt_path}`",
            f"Receivable proposal: `{result.receivable_proposal_path}`",
            f"Packet summary: `{result.packet_summary_path}`",
            f"Missing required facts: {result.missing_required_fact_count}",
            f"Outputs: {result.output_count}",
            f"Work Board cards: {result.work_board_card_count}",
            "",
            "Boundary:",
            "- Review-only packet. No send, submit, portal login, browser automation, bank access, ledger write, spreadsheet cell read, or financial truth claim.",
        ]
    )


__all__ = [
    "CAPITAL_HILTON_PACKET_ID",
    "DEFAULT_ARTIFACT_ROOT",
    "NO_AUTHORITY_FLAGS",
    "CapitalHiltonPacketResult",
    "build_capital_hilton_invoice_packet",
    "draft_email_body",
    "format_capital_hilton_invoice_packet_result",
    "packet_summary",
    "portal_fill_prompt",
    "receivable_tracking_proposal",
    "stable_json",
]
