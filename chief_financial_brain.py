"""
chief_financial_brain.py

Financial reporting specialist for Finance Operations domain.
Owns the money layer: money owed to the operator, income by period,
payment history, quarterly tax projections.

Task 140 (ONE money truth): this brain is bound to the shared money source —
generated/read_models/receivables_month_bounded.json via money_truth.py.
The legacy billing_records.jsonl/.csv toy-export binding is RETIRED (it
carried stale placeholder rows and drove the "Outstanding — none / YTD $0.00"
lie while $1,095+ was open). Empty ledger data renders "not tracked yet" —
NEVER "Outstanding — none": no data is a data gap, not a zero balance.

This is distinct from chief_analytics_brain.py, which covers
cross-domain metrics (album progress, content pipeline, activity).

Triggered by:
  - "financial report" / "p&l" / "profit and loss"
  - "outstanding invoices" / "who owes me" / "unpaid invoices"
  - "payment history" / "revenue this month"
  - "quarterly projection" / "tax projection"
Intent: financial_report in chief_router.py

Saves to:
  - openclaw-vault/Business/Financial Report.md
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

# ── Paths ─────────────────────────────────────────────────────────────────────

FINANCIAL_MD  = Path("/mnt/c/OpenClawShared/openclaw-vault/Business/Financial Report.md")

# ── 2025 tax baseline (from filed return) ─────────────────────────────────────

BASELINE_2025 = {
    "total_income":    47340.00,
    "federal_refund":  1847.00,
    "state_refund":    389.00,
    "se_tax_paid":     6697.00,
    "federal_tax_paid": 7240.00,
}

# ── Quarterly deadlines ───────────────────────────────────────────────────────

QUARTERLY_DEADLINES = [
    ("Q1 2026", "2026-04-15"),
    ("Q2 2026", "2026-06-16"),
    ("Q3 2026", "2026-09-15"),
    ("Q4 2026", "2027-01-15"),
]

SE_TAX_RATE    = 0.1413   # 14.13% self-employment tax
FED_TAX_RATE   = 0.22     # estimated federal bracket
STATE_TAX_RATE = 0.05     # estimated state


# ── Record loader — the ONE money truth ───────────────────────────────────────

def _load_records() -> list[dict]:
    """Load receivable month rows from the shared money truth read-model.

    Task 140: the only money source is receivables_month_bounded.json.
    (The old billing_records.jsonl/.csv toy export — with its
    record_type-vs-'mode' field bug — is retired.)
    """
    from money_truth import load_money_truth, money_rows

    payload = load_money_truth()
    rows = money_rows(payload)
    for row in rows:
        row["_generated_at"] = str(payload.get("generated_at") or "")
    return rows


def _parse_date(val: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(val)[:10], fmt[:10])
        except ValueError:
            continue
    return None


# ── Financial analysis ────────────────────────────────────────────────────────

def _analyze(records: list[dict]) -> dict:
    """Aggregate the ledger rows. `records` are receivables_month_bounded rows."""
    now = datetime.now()
    this_year  = f"{now.year:04d}"
    this_month = f"{now.year:04d}-{now.month:02d}"

    income_ytd = income_month = 0.0
    outstanding_total = 0.0
    unknown_amount_clients: list[dict] = []
    outstanding_rows: list[dict] = []
    pending_send_rows: list[dict] = []
    settled_rows: list[dict] = []
    income_by_client: dict[str, float] = defaultdict(float)

    for r in records:
        client = str(r.get("client_display_name") or r.get("client_ref") or "Unknown").strip()
        month = str(r.get("month") or "").strip()
        status = str(r.get("payment_status") or "unknown").strip().lower()
        amount_known = bool(r.get("amount_known", True))
        open_minor = r.get("open_minor_units")
        paid_minor = r.get("paid_minor_units")

        if isinstance(paid_minor, int) and paid_minor > 0:
            paid = paid_minor / 100
            if month.startswith(this_year):
                income_ytd += paid
                income_by_client[client] += paid
            if month == this_month:
                income_month += paid

        if status == "expected_uninvoiced":
            pending_send_rows.append({"client": client, "month": month, "status": status})
        elif status == "settled" or bool(r.get("settled_past_no_compound")):
            settled_rows.append({"client": client, "month": month})
        elif not amount_known or open_minor is None:
            unknown_amount_clients.append({"client": client, "month": month, "status": status})
        elif int(open_minor or 0) > 0 or bool(r.get("needs_reconcile")):
            balance = int(open_minor or 0) / 100
            outstanding_total += balance
            outstanding_rows.append(
                {
                    "client": client,
                    "month": month,
                    "balance": balance,
                    "status": "needs_reconcile" if r.get("needs_reconcile") else status,
                }
            )

    # Quarterly tax projection on YTD received income
    net_income = income_ytd
    se_tax_projected    = net_income * SE_TAX_RATE
    fed_tax_projected   = net_income * FED_TAX_RATE
    state_tax_projected = net_income * STATE_TAX_RATE
    total_tax_projected = se_tax_projected + fed_tax_projected + state_tax_projected

    today_str = now.strftime("%Y-%m-%d")
    next_deadline = next(
        ((label, d) for label, d in QUARTERLY_DEADLINES if d >= today_str),
        None
    )

    return {
        "income_month": income_month,
        "income_ytd":   income_ytd,
        "outstanding_total":    outstanding_total,
        "outstanding_rows":     outstanding_rows,
        "unknown_amount_clients": unknown_amount_clients,
        "pending_send_rows":    pending_send_rows,
        "settled_rows":         settled_rows,
        "top_clients":  sorted(income_by_client.items(), key=lambda x: x[1], reverse=True)[:5],
        "tax_projection": {
            "net_income":  net_income,
            "se_tax":      se_tax_projected,
            "fed_tax":     fed_tax_projected,
            "state_tax":   state_tax_projected,
            "total":       total_tax_projected,
        },
        "next_deadline": next_deadline,
        "record_count":  len(records),
        "not_tracked":   len(records) == 0,
        "as_of": str(records[0].get("_generated_at") or "")[:10] if records else "",
        "baseline_2025": BASELINE_2025,
    }


# ── Report builder ────────────────────────────────────────────────────────────

def _fmt(amount: float) -> str:
    return f"${amount:,.2f}"


def _build_report(data: dict) -> str:
    from money_truth import NOT_TRACKED_LINE, money_lines

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"**Financial Report — {today}**", ""]

    # No data is a DATA GAP, never a clean zero. "Outstanding — none" is banned.
    if data["not_tracked"]:
        lines += [
            f"**Money** — {NOT_TRACKED_LINE}",
            "",
            "No income, outstanding, or tax numbers are claimed from empty data.",
            "_Source: receivables_month_bounded (the one money truth)._",
        ]
        return "\n".join(lines)

    # Money owed to you — the shared humanized lines (fleet-identical facts)
    lines += ["**Money owed to you**"]
    for line in money_lines():
        lines.append(f"  {line}")
    summary = f"  Outstanding total (known amounts): {_fmt(data['outstanding_total'])}"
    if data["unknown_amount_clients"]:
        summary += f" — plus {len(data['unknown_amount_clients'])} item(s) with amount not yet confirmed"
    lines += [summary, ""]

    # Income (ledger paid amounts, month-bounded)
    lines += [
        "**Income (received, from ledger)**",
        f"  This month: {_fmt(data['income_month'])}",
        f"  YTD {datetime.now().year}:    {_fmt(data['income_ytd'])}",
        f"  Prior year: {_fmt(data['baseline_2025']['total_income'])} (2025 filed)",
        "",
    ]

    # Top clients
    if data["top_clients"] and any(v > 0 for _, v in data["top_clients"]):
        lines += ["**Top clients (YTD received)**"]
        for client, amt in data["top_clients"]:
            if amt > 0:
                lines.append(f"  {client}: {_fmt(amt)}")
        lines.append("")

    # Tax projection
    tax = data["tax_projection"]
    if tax["net_income"] > 0:
        lines += [
            "**Tax projection (YTD estimate)**",
            f"  Net income: {_fmt(tax['net_income'])}",
            f"  SE tax:     {_fmt(tax['se_tax'])} (14.13%)",
            f"  Federal:    {_fmt(tax['fed_tax'])} (~22%)",
            f"  State:      {_fmt(tax['state_tax'])} (~5%)",
            f"  Total est.: {_fmt(tax['total'])}",
        ]
        if data["next_deadline"]:
            label, date = data["next_deadline"]
            days_out = (_parse_date(date) - datetime.now()).days
            lines.append(f"  Next deadline: {label} — {date} ({days_out} days)")
        lines.append("")

    as_of = f", as of {data['as_of']}" if data.get("as_of") else ""
    lines.append(f"_Source: receivables_month_bounded (the one money truth){as_of}._")
    return "\n".join(lines)


# ── LLM narrative ─────────────────────────────────────────────────────────────

_NARRATIVE_PROMPT = """\
You are a financial advisor reviewing the financial position of an independent music producer.

{report}

Write 2-3 sentences:
- Lead with the most important financial fact right now (income trend, outstanding balance, or tax exposure)
- Note one thing that needs attention
- Be direct and specific with numbers
- Only use numbers that appear in the report above; never invent totals

No bullet points. No headers."""


def _build_narrative(report: str) -> str:
    prompt = _NARRATIVE_PROMPT.format(report=report)
    try:
        result = _local_model_call(prompt, timeout=20).strip()
    except Exception as e:
        print(f"[chief_financial] narrative LLM error: {e}", flush=True)
        result = ""
    return result if result else ""


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_financial_md(report: str, narrative: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = (
        "---\n"
        "type: financial-report\n"
        f"last_updated: {today}\n"
        "source: receivables_month_bounded\n"
        "---\n\n"
        "# Financial Report\n\n"
        "_Managed by `chief_financial_brain.py`. Say 'financial report' to refresh._\n\n"
    )
    if narrative:
        content += f"## Summary\n\n{narrative}\n\n"
    content += "## Details\n\n" + report.replace("**", "").strip() + "\n"
    try:
        FINANCIAL_MD.parent.mkdir(parents=True, exist_ok=True)
        FINANCIAL_MD.write_text(content, encoding="utf-8")
    except OSError as e:
        print(f"[chief_financial] vault write skipped: {e}", flush=True)


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    records = _load_records()
    data    = _analyze(records)
    report  = _build_report(data)
    narrative = _build_narrative(report)
    _write_financial_md(report, narrative)

    parts = []
    if narrative:
        parts.append(narrative + "\n")
    parts.append(report)
    parts.append("\nFull report saved to vault/Business/Financial Report.md")
    return ["\n".join(parts)]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for line in handle():
        print(line)
