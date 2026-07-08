"""
invoice_generator.py

PDF invoice generator for Winship Live.
Generates professional PDF invoices using reportlab.

Public API
----------
generate_invoice_pdf(data: dict) -> Path
get_next_invoice_number() -> str
detect_net_terms(client_name: str, project_desc: str) -> str
append_tracker_row(data: dict) -> None
build_st_annes_invoice_data(events, *, rate_minor=12500) -> dict
"""

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

# ── Constants ─────────────────────────────────────────────────────────────────

INVOICES_DIR = Path(os.environ.get("OPENCLAW_INVOICES_DIR", "/home/openclaw/state/invoices"))
TRACKER_DIR  = Path(os.environ.get("OPENCLAW_INVOICE_TRACKER_DIR", "/home/openclaw/state/invoices/tracker"))
ST_ANNES_WORK_LOG_EVENTS_PATH = Path("generated/read_models/st_annes_work_log_events.json")

BUSINESS_NAME    = "Winship Live"
BUSINESS_CONTACT = "H. Winship Wheatley IV"
BUSINESS_EMAIL   = "winshipwheatley@gmail.com"
BUSINESS_PHONE   = "443-758-4913"

_NET_30_KEYWORDS = (
    "hotel", "hilton", "corporate", "institution", "university",
    "theater", "theatre", "arts", "gallery", "venue", "production",
)

TRACKER_COLUMNS = [
    "invoice_number", "client_name", "client_email", "project_desc",
    "service_date", "issue_date", "net_terms", "amount_total",
    "deposit_paid", "balance_due", "pdf_path", "invoice_status",
    "payment_status", "updated_at",
]

DEFAULT_ST_ANNES_EVENTS = [
    {"description": "Wedding", "service_date": "2026-06-27"},
    {"description": "Church service (10:00)", "service_date": "2026-06-28"},
]

_ST_ANNES_READY_INVOICE_STATUSES = {"READY_FOR_MONTHLY_ROLLUP"}


def _line_items_use_minor_units(line_items: list[dict]) -> bool:
    amounts = [item.get("amount", 0) for item in line_items]
    return bool(amounts) and all(
        isinstance(amount, int) and not isinstance(amount, bool) and abs(amount) >= 1000
        for amount in amounts
    )


def _coerce_invoice_amount(amount, *, minor_units: bool):
    if minor_units:
        if isinstance(amount, int) and not isinstance(amount, bool):
            return amount
        return int(round(float(amount) * 100))
    return float(amount)


def _format_invoice_amount(amount, *, minor_units: bool) -> str:
    dollars = amount / 100 if minor_units else float(amount)
    return f"${dollars:,.2f}"


def _line_item_description(event: dict) -> str:
    return str(
        event.get("description")
        or event.get("service_label")
        or event.get("label")
        or "St. Anne's service"
    )


def _line_item_service_date(event: dict) -> str:
    service_date = event.get("service_date") or event.get("date")
    if service_date:
        return str(service_date)
    created_at = str(event.get("created_at") or "")
    if re.match(r"\d{4}-\d{2}-\d{2}", created_at):
        return created_at[:10]
    return "TBD"


def _is_invoice_ready_st_annes_event(event: dict) -> bool:
    status = str(event.get("invoice_inclusion_status") or "").upper()
    if status in _ST_ANNES_READY_INVOICE_STATUSES:
        return True
    if event.get("operator_confirmed") is True or event.get("operator_business_confirmed") is True:
        blocked_terms = ("NOT_INCLUDED", "SMOKE", "TEST", "DISCARDED")
        return not any(term in status for term in blocked_terms)
    return False


def _load_st_annes_work_log_events() -> list[dict]:
    try:
        payload = json.loads(ST_ANNES_WORK_LOG_EVENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    raw_events = payload.get("staged_events") or payload.get("events") or []
    if not isinstance(raw_events, list):
        return []

    ready_events = [
        event
        for event in raw_events
        if isinstance(event, dict) and _is_invoice_ready_st_annes_event(event)
    ]
    return ready_events if len(ready_events) == 2 else []


# ── Stage-aware rendering (task 134) ────────────────────────────────────────────

VALID_INVOICE_STAGES = ("draft", "finalized", "test")

_DRAFT_WORD_RE = re.compile(r"\bdraft\b[\s\-—:]*", re.IGNORECASE)
_EMPTY_BRACKET_RE = re.compile(r"[\(\[]\s*[\)\]]")


def _scrub_draft_wording(text: str) -> str:
    """Strip the word 'draft' (any case, plus a trailing separator) from operator-facing
    text. Applied only to finalized/test stage rendering -- draft-stage text is left alone
    since 'Draft' marking is CORRECT pre-approval. Defensive: covers text pulled in from an
    external source (e.g. a Mac-Codex invoice receipt) that might carry the word anywhere,
    not just the invoice_number field."""
    scrubbed = _DRAFT_WORD_RE.sub("", str(text or ""))
    scrubbed = _EMPTY_BRACKET_RE.sub("", scrubbed)
    return " ".join(scrubbed.split())


# ── Net terms detection ───────────────────────────────────────────────────────

def detect_net_terms(client_name: str, project_desc: str) -> str:
    """
    Returns "Net 30" for institutional clients, "Due on Receipt" otherwise.
    Case-insensitive match on client_name or project_desc.
    """
    combined = (client_name + " " + project_desc).lower()
    if any(kw in combined for kw in _NET_30_KEYWORDS):
        return "Net 30"
    return "Due on Receipt"


# ── Invoice number generation ─────────────────────────────────────────────────

def get_next_invoice_number(*, preview: bool = False) -> str:
    """
    Reads and increments the year-scoped counter file.
    Counter file: TRACKER_DIR/invoice_counter_YYYY.txt
    Returns: WL-YYYY-NNNN (zero-padded 4 digits).
    Does NOT modify the legacy invoice_counter.txt.

    preview=True computes what the next number WOULD be without writing the counter file --
    for test-mode rendering that must never burn a real sequence number.
    """
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    year = datetime.now().year
    counter_file = TRACKER_DIR / f"invoice_counter_{year}.txt"

    if counter_file.exists():
        current = int(counter_file.read_text().strip())
    else:
        current = 0

    next_num = current + 1
    if not preview:
        counter_file.write_text(str(next_num))
    return f"WL-{year}-{next_num:04d}"


# ── Tracker CSV append ────────────────────────────────────────────────────────

def append_tracker_row(data: dict) -> None:
    """
    Appends one row to the invoice tracker CSV.
    Creates the file with header if missing.
    """
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    tracker_path = TRACKER_DIR / "invoice_tracker.csv"
    write_header = not tracker_path.exists()

    row = {
        "invoice_number": data.get("invoice_number", ""),
        "client_name":    data.get("client_name", ""),
        "client_email":   data.get("client_email", "unknown"),
        "project_desc":   data.get("project_desc", ""),
        "service_date":   data.get("service_date", ""),
        "issue_date":     data.get("issue_date", ""),
        "net_terms":      data.get("net_terms", ""),
        "amount_total":   data.get("amount_total", 0.0),
        "deposit_paid":   data.get("deposit_paid", 0.0),
        "balance_due":    data.get("balance_due", 0.0),
        "pdf_path":       str(data.get("pdf_path", "")),
        "invoice_status": "drafted",
        "payment_status": "unpaid",
        "updated_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    with open(tracker_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ── St. Anne's helper ─────────────────────────────────────────────────────────

def build_st_annes_invoice_data(events=None, *, rate_minor=12500, stage: str = "draft") -> dict:
    """
    Build invoice data for St. Anne's from work-log events.

    Events are intentionally mapped at the supplied rate rather than trusting
    a generated work-log amount field.

    stage (task 134 -- stage-aware rendering, not word-deletion):
      "draft" (default) -- pre-approval review copy. The "WL-DRAFT-ST-ANNES" placeholder
        number is CORRECT here; behavior is byte-identical to before this parameter existed.
      "finalized" -- post-approval, pre-send. A real sequential invoice number via
        get_next_invoice_number() (consumes the persistent counter); zero "draft" wording.
      "test" -- workflow-test-mode (recipient-locked) review. Same clean rendering as
        finalized so the operator sees the true final copy, but PREVIEWS the number without
        consuming the real counter; generate_invoice_pdf adds a visible TEST watermark.
    """
    if stage not in VALID_INVOICE_STAGES:
        raise ValueError(f"unknown invoice stage: {stage!r}")
    if events is None:
        work_log_events = _load_st_annes_work_log_events()
        source_events = work_log_events or list(DEFAULT_ST_ANNES_EVENTS)
        line_item_source = "st_annes_work_log" if work_log_events else "default_st_annes_events"
    else:
        source_events = list(events or DEFAULT_ST_ANNES_EVENTS)
        line_item_source = "provided_events" if events else "default_st_annes_events"

    line_items = [
        {
            "description": _line_item_description(event),
            "service_date": _line_item_service_date(event),
            "amount": int(rate_minor),
        }
        for event in source_events
    ]
    amount_total = sum(item["amount"] for item in line_items)
    project_desc = "; ".join(item["description"] for item in line_items)
    service_date = line_items[0]["service_date"] if line_items else "TBD"

    if stage == "draft":
        invoice_number = "WL-DRAFT-ST-ANNES"
    elif stage == "finalized":
        invoice_number = get_next_invoice_number()
    else:  # test
        invoice_number = get_next_invoice_number(preview=True)

    return {
        "invoice_number": invoice_number,
        "invoice_stage": stage,
        "client_name": "St. Anne's",
        "client_email": "draper.carter@gmail.com",
        "project_desc": project_desc,
        "service_date": service_date,
        "issue_date": datetime.now().strftime("%Y-%m-%d"),
        "net_terms": detect_net_terms("St. Anne's", project_desc),
        "amount_total": amount_total,
        "deposit_paid": 0,
        "balance_due": amount_total,
        "line_items": line_items,
        "line_item_source": line_item_source,
    }


# ── PDF generation ────────────────────────────────────────────────────────────

def generate_invoice_pdf(data: dict) -> Path:
    """
    Generate a PDF invoice for Winship Live.
    Saves to INVOICES_DIR/WL-YYYY-NNNN__ClientName.pdf.
    Returns the Path to the saved file.

    Required keys in data:
      invoice_number, client_name, client_email, project_desc,
      service_date, issue_date, net_terms, amount_total,
      deposit_paid, balance_due
    """
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)

    invoice_stage = str(data.get("invoice_stage") or "").strip().lower()
    is_test_stage = invoice_stage == "test"
    scrub_draft = invoice_stage in ("finalized", "test")

    invoice_number = data["invoice_number"]
    client_name    = data["client_name"]
    client_email   = data.get("client_email", "unknown")
    project_desc   = data["project_desc"]
    service_date   = data["service_date"]
    issue_date     = data["issue_date"]
    net_terms      = data["net_terms"]
    line_items = list(data.get("line_items") or [])
    if scrub_draft:
        # Task 134: defensive scrub for finalized/test rendering -- covers text pulled in
        # from an external source (e.g. a Mac-Codex invoice receipt) that might carry
        # "draft" wording anywhere, not just the invoice_number field this module controls.
        invoice_number = _scrub_draft_wording(invoice_number) or invoice_number
        client_name = _scrub_draft_wording(client_name) or client_name
        project_desc = _scrub_draft_wording(project_desc) or project_desc
        line_items = [
            {**item, "description": _scrub_draft_wording(item.get("description", "")) or item.get("description", "")}
            for item in line_items
        ]
    line_items_are_minor = _line_items_use_minor_units(line_items)
    if line_items:
        amount_total = sum(
            _coerce_invoice_amount(item.get("amount", 0), minor_units=line_items_are_minor)
            for item in line_items
        )
        deposit_paid = _coerce_invoice_amount(
            data.get("deposit_paid", 0), minor_units=line_items_are_minor
        )
        balance_due = max(amount_total - deposit_paid, 0)
        data["amount_total"] = amount_total
        data["balance_due"] = balance_due
    else:
        amount_total   = float(data["amount_total"])
        deposit_paid   = float(data.get("deposit_paid", 0.0))
        balance_due    = float(data.get("balance_due", max(amount_total - deposit_paid, 0.0)))

    # Sanitize client name for filename
    safe_client = re.sub(r"[^\w\s-]", "", client_name).strip().replace(" ", "_")
    filename = f"{invoice_number}__{safe_client}.pdf"
    pdf_path = INVOICES_DIR / filename

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    style_normal  = styles["Normal"]
    style_heading = ParagraphStyle("InvHeading", fontSize=28, leading=34,
                                   fontName="Helvetica-Bold", alignment=2)  # right
    style_small   = ParagraphStyle("InvSmall", fontSize=9, leading=12,
                                   fontName="Helvetica")
    style_small_bold = ParagraphStyle("InvSmallBold", fontSize=9, leading=12,
                                      fontName="Helvetica-Bold")
    style_label   = ParagraphStyle("InvLabel", fontSize=8, leading=11,
                                   fontName="Helvetica", textColor=colors.grey)
    style_footer  = ParagraphStyle("InvFooter", fontSize=9, leading=12,
                                   fontName="Helvetica-Oblique", alignment=1)  # center
    style_test_watermark = ParagraphStyle("InvTestWatermark", fontSize=12, leading=16,
                                          fontName="Helvetica-Bold", alignment=1,
                                          textColor=colors.HexColor("#c0392b"))

    elements = []

    if is_test_stage:
        # Task 134: workflow-test-mode gets the TRUE final copy (no "draft" wording, real-
        # looking layout) so the operator reviews what will actually be sent -- clearly
        # marked so it is never mistaken for the real send.
        elements.append(Paragraph("TEST — WORKFLOW TEST MODE, NOT A REAL INVOICE", style_test_watermark))
        elements.append(Spacer(1, 0.1 * inch))

    # ── Header row: business info (left) + "INVOICE" (right) ─────────────────
    header_data = [
        [
            Paragraph(
                f"<b>{BUSINESS_NAME}</b><br/>"
                f"{BUSINESS_CONTACT}<br/>"
                f"{BUSINESS_EMAIL}<br/>"
                f"{BUSINESS_PHONE}",
                style_small,
            ),
            Paragraph("INVOICE", style_heading),
        ]
    ]
    header_table = Table(header_data, colWidths=[3.5 * inch, 3.5 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Spacer(1, 0.15 * inch))

    # ── Invoice details (right-side mini block) ───────────────────────────────
    details_data = [
        [
            Paragraph("Invoice #", style_label),
            Paragraph(invoice_number, style_small_bold),
        ],
        [
            Paragraph("Issue Date", style_label),
            Paragraph(issue_date, style_small),
        ],
        [
            Paragraph("Net Terms", style_label),
            Paragraph(net_terms, style_small),
        ],
    ]
    details_table = Table(details_data, colWidths=[1.2 * inch, 2 * inch],
                          hAlign="RIGHT")
    details_table.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 0.2 * inch))

    # ── Bill To ───────────────────────────────────────────────────────────────
    elements.append(Paragraph("<b>Bill To</b>", style_small_bold))
    elements.append(Spacer(1, 0.05 * inch))
    elements.append(Paragraph(client_name, style_small))
    if client_email and client_email.lower() != "unknown":
        elements.append(Paragraph(client_email, style_small))
    elements.append(Spacer(1, 0.25 * inch))

    # ── Service table ─────────────────────────────────────────────────────────
    service_data = [
        [
            Paragraph("<b>Description</b>", style_small_bold),
            Paragraph("<b>Service Date</b>", style_small_bold),
            Paragraph("<b>Amount</b>", style_small_bold),
        ],
    ]
    if line_items:
        for item in line_items:
            service_data.append([
                Paragraph(str(item.get("description", "")), style_small),
                Paragraph(str(item.get("service_date", "")), style_small),
                Paragraph(
                    _format_invoice_amount(
                        _coerce_invoice_amount(item.get("amount", 0), minor_units=line_items_are_minor),
                        minor_units=line_items_are_minor,
                    ),
                    style_small,
                ),
            ])
    else:
        service_data.append([
            Paragraph(project_desc, style_small),
            Paragraph(service_date, style_small),
            Paragraph(f"${amount_total:,.2f}", style_small),
        ])
    service_table = Table(service_data, colWidths=[3.75 * inch, 1.5 * inch, 1.75 * inch])
    service_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ALIGN",        (2, 0), (2, -1), "RIGHT"),
    ]))
    elements.append(service_table)
    elements.append(Spacer(1, 0.1 * inch))

    # ── Totals block ──────────────────────────────────────────────────────────
    totals_data = [
        ["Subtotal", _format_invoice_amount(amount_total, minor_units=line_items_are_minor)],
    ]
    if deposit_paid > 0:
        totals_data.append([
            "Deposit Paid",
            f"({_format_invoice_amount(deposit_paid, minor_units=line_items_are_minor)})",
        ])
    totals_data.append([
        "Balance Due",
        _format_invoice_amount(balance_due, minor_units=line_items_are_minor),
    ])

    totals_table = Table(totals_data, colWidths=[1.5 * inch, 1.5 * inch], hAlign="RIGHT")
    totals_style = [
        ("ALIGN",        (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("LINEABOVE",    (0, -1), (-1, -1), 1, colors.black),
        ("FONTNAME",     (0, -1), (-1, -1), "Helvetica-Bold"),
    ]
    totals_table.setStyle(TableStyle(totals_style))
    elements.append(totals_table)
    elements.append(Spacer(1, 0.35 * inch))

    # ── Payment methods ───────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph("<b>Payment Methods</b>", style_small_bold))
    elements.append(Spacer(1, 0.05 * inch))
    payment_text = (
        "Cash  |  Check payable to Winship Live  |  "
        "Venmo: @Winship  |  Zelle: 443-758-4913  |  Square/card on request"
    )
    elements.append(Paragraph(payment_text, style_small))
    elements.append(Spacer(1, 0.4 * inch))

    # ── Footer ────────────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph("Thank you for your business.", style_footer))

    doc.build(elements)
    return pdf_path
