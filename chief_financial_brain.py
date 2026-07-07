"""
chief_financial_brain.py

Financial reporting specialist for Finance Operations domain.
Owns the money layer: income by period, outstanding invoices,
P&L summary, payment history, quarterly tax projections.

This is distinct from chief_analytics_brain.py, which covers
cross-domain metrics (album progress, content pipeline, activity).
This brain covers only: billing records, invoices, payments, and
financial position.

Triggered by:
  - "financial report" / "p&l" / "profit and loss"
  - "outstanding invoices" / "who owes me" / "unpaid invoices"
  - "payment history" / "revenue this month"
  - "quarterly projection" / "tax projection"
Intent: financial_report in chief_router.py

Saves to:
  - openclaw-vault/Business/Financial Report.md
"""

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

# ── Paths ─────────────────────────────────────────────────────────────────────

BILLING_JSONL = Path("/home/openclaw/OpenClaw/exports/billing_records.jsonl")
BILLING_CSV   = Path("/home/openclaw/OpenClaw/exports/billing_records.csv")
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


# ── Record loader ─────────────────────────────────────────────────────────────

def _load_records() -> list[dict]:
    records = []
    if BILLING_JSONL.exists():
        for line in BILLING_JSONL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    elif BILLING_CSV.exists():
        with BILLING_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                records.append(row)
    return records


def _parse_amount(val) -> float:
    try:
        return float(str(val).replace(",", "").strip() or "0")
    except (ValueError, TypeError):
        return 0.0


def _parse_date(val: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(val)[:10], fmt[:10])
        except ValueError:
            continue
    return None


# ── Financial analysis ────────────────────────────────────────────────────────

def _analyze(records: list[dict]) -> dict:
    now = datetime.now()
    ytd_start  = datetime(now.year, 1, 1)
    month_ago  = now - timedelta(days=30)
    week_ago   = now - timedelta(days=7)

    income_ytd = income_month = income_week = 0.0
    outstanding_total = 0.0
    outstanding_invoices: list[dict] = []
    payments: list[dict] = []
    income_by_client: dict[str, float] = defaultdict(float)
    income_by_project: dict[str, float] = defaultdict(float)

    for r in records:
        rtype = r.get("record_type", r.get("type", "")).upper()

        if rtype in ("PAYMENT", "RECEIPT"):
            amount = _parse_amount(r.get("payment_amount") or r.get("amount_received"))
            date   = _parse_date(r.get("payment_date") or r.get("date_created", ""))
            client = r.get("client_name", "Unknown")
            project = r.get("project_or_event", "Unknown")

            if date:
                if date >= ytd_start:
                    income_ytd += amount
                    income_by_client[client] += amount
                    income_by_project[project] += amount
                if date >= month_ago:
                    income_month += amount
                if date >= week_ago:
                    income_week += amount

            payments.append({
                "date":    (date.strftime("%Y-%m-%d") if date else "—"),
                "client":  client,
                "project": project,
                "amount":  amount,
            })

        elif rtype == "INVOICE":
            amount = _parse_amount(r.get("amount_total"))
            deposit = _parse_amount(r.get("deposit_amount") or 0)
            due_date = r.get("due_date", "")
            inv_num  = r.get("invoice_number", "—")
            client   = r.get("client_name", "Unknown")
            project  = r.get("project_or_event", "Unknown")
            status   = r.get("status", "").lower()

            # Consider outstanding if no matching payment and not marked paid
            if status not in ("paid", "receipt"):
                balance = amount - deposit
                if balance > 0:
                    outstanding_total += balance
                    outstanding_invoices.append({
                        "invoice_number": inv_num,
                        "client":  client,
                        "project": project,
                        "amount":  amount,
                        "deposit": deposit,
                        "balance": balance,
                        "due":     due_date or "—",
                    })

    # Quarterly tax projection on YTD income
    net_income = income_ytd
    se_tax_projected   = net_income * SE_TAX_RATE
    fed_tax_projected  = net_income * FED_TAX_RATE
    state_tax_projected = net_income * STATE_TAX_RATE
    total_tax_projected = se_tax_projected + fed_tax_projected + state_tax_projected

    # Days until next quarterly deadline
    today_str = now.strftime("%Y-%m-%d")
    next_deadline = next(
        ((label, d) for label, d in QUARTERLY_DEADLINES if d >= today_str),
        None
    )

    return {
        "income_week":  income_week,
        "income_month": income_month,
        "income_ytd":   income_ytd,
        "outstanding_total":    outstanding_total,
        "outstanding_invoices": outstanding_invoices,
        "payments":     sorted(payments, key=lambda x: x["date"], reverse=True)[:10],
        "top_clients":  sorted(income_by_client.items(), key=lambda x: x[1], reverse=True)[:5],
        "top_projects": sorted(income_by_project.items(), key=lambda x: x[1], reverse=True)[:5],
        "tax_projection": {
            "net_income":  net_income,
            "se_tax":      se_tax_projected,
            "fed_tax":     fed_tax_projected,
            "state_tax":   state_tax_projected,
            "total":       total_tax_projected,
        },
        "next_deadline": next_deadline,
        "record_count":  len(records),
        "baseline_2025": BASELINE_2025,
    }


# ── Report builder ────────────────────────────────────────────────────────────

def _fmt(amount: float) -> str:
    return f"${amount:,.2f}"


def _build_report(data: dict) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"**Financial Report — {today}**", ""]

    # Income
    lines += [
        "**Income**",
        f"  This week:  {_fmt(data['income_week'])}",
        f"  This month: {_fmt(data['income_month'])}",
        f"  YTD {datetime.now().year}:    {_fmt(data['income_ytd'])}",
        f"  Prior year: {_fmt(data['baseline_2025']['total_income'])} (2025 filed)",
        "",
    ]

    # Outstanding
    if data["outstanding_invoices"]:
        lines += [f"**Outstanding ({_fmt(data['outstanding_total'])})**"]
        for inv in data["outstanding_invoices"][:5]:
            lines.append(
                f"  [{inv['invoice_number']}] {inv['client']} — "
                f"{_fmt(inv['balance'])} due {inv['due']}"
            )
        if len(data["outstanding_invoices"]) > 5:
            lines.append(f"  ... and {len(data['outstanding_invoices']) - 5} more")
        lines.append("")
    else:
        lines += ["**Outstanding** — none", ""]

    # Top clients
    if data["top_clients"] and any(v > 0 for _, v in data["top_clients"]):
        lines += ["**Top clients (YTD)**"]
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

    # Recent payments
    if data["payments"]:
        lines += ["**Recent payments**"]
        for p in data["payments"][:5]:
            if p["amount"] > 0:
                lines.append(f"  {p['date']} | {p['client']} | {_fmt(p['amount'])}")

    return "\n".join(lines)


# ── LLM narrative ─────────────────────────────────────────────────────────────

_NARRATIVE_PROMPT = """\
You are a financial advisor reviewing the financial position of an independent music producer.

{report}

Write 2-3 sentences:
- Lead with the most important financial fact right now (income trend, outstanding balance, or tax exposure)
- Note one thing that needs attention
- Be direct and specific with numbers

No bullet points. No headers."""


def _build_narrative(report: str) -> str:
    prompt = _NARRATIVE_PROMPT.format(report=report)
    result = _local_model_call(prompt, timeout=20).strip()
    return result if result else ""


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_financial_md(report: str, narrative: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = (
        "---\n"
        "type: financial-report\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Financial Report\n\n"
        "_Managed by `chief_financial_brain.py`. Say 'financial report' to refresh._\n\n"
    )
    if narrative:
        content += f"## Summary\n\n{narrative}\n\n"
    content += "## Details\n\n" + report.replace("**", "").strip() + "\n"
    FINANCIAL_MD.parent.mkdir(parents=True, exist_ok=True)
    FINANCIAL_MD.write_text(content, encoding="utf-8")


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
