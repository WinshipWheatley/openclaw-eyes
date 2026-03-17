"""
chief_cpa_brain.py

Tracks income, expenses, and tax categories for Winship Live sole
proprietorship. Reads billing brain invoices/payments as income.
Flags deductions and estimates quarterly tax owed.

Triggered by:
  - "what did I make this month" / "income this month"
  - "what do I owe quarterly" / "estimated tax" / "quarterly tax"
  - "what can I deduct" / "deductions"
  - "log expense" / "add expense [amount] [category] [desc]"
Intent: cpa_query in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/expense_log.json  (source of truth)
  - openclaw-vault/Business/CPA Log.md               (Obsidian)
"""

import csv
import json
import re
from datetime import datetime, date
from pathlib import Path

from chief_llm import claude_call as ollama_call, claude_json as ollama_json

# ── Paths ──────────────────────────────────────────────────────────────────────

BUSINESS_DIR  = Path("/mnt/c/OpenClawShared/business")
EXPENSE_JSON  = BUSINESS_DIR / "expense_log.json"
CPA_LOG_MD    = Path("/mnt/c/OpenClawShared/openclaw-vault/Business/CPA Log.md")
BILLING_CSV   = Path("/home/openclaw/OpenClaw/exports/billing_records.csv")

# ── Tax constants ──────────────────────────────────────────────────────────────

# 2026 quarterly estimated tax deadlines for sole proprietor
QUARTERLY_DEADLINES = [
    ("Q1 2026", "2026-04-15"),
    ("Q2 2026", "2026-06-16"),
    ("Q3 2026", "2026-09-15"),
    ("Q4 2026", "2027-01-15"),
]

# Self-employment tax rate (15.3%) + estimated federal income tax (22% bracket)
SE_TAX_RATE     = 0.153
INCOME_TAX_RATE = 0.22   # conservative estimate for sole prop
SAFE_HARBOR_PCT = 0.90   # IRS safe harbor — pay 90% of estimated liability

DEDUCTION_CATEGORIES = {
    "home_studio":    "Home Studio — dedicated space percentage of rent/mortgage, utilities",
    "gear":           "Gear & Equipment — microphones, instruments, hardware (Section 179 or depreciation)",
    "software":       "Software & Subscriptions — DAW, plugins, DistroKid, Adobe, Canva, etc.",
    "miles":          "Business Miles — travel to gigs, studios, meetings (67¢/mile in 2024)",
    "music_services": "Music Services — ASCAP fees, mastering, mixing, session musicians",
    "meals":          "Business Meals — 50% deductible when discussing business",
    "professional":   "Professional Development — courses, books, industry events",
    "marketing":      "Marketing & Promotion — ads, merch, promo materials",
    "phone":          "Phone & Internet — business-use percentage",
    "legal":          "Legal & Professional Fees — lawyer, accountant, contract review",
}

# ── Income: read billing CSV ───────────────────────────────────────────────────

def _load_billing_income() -> list[dict]:
    """Read all INVOICE and PAYMENT rows from billing_records.csv."""
    if not BILLING_CSV.exists():
        return []
    records = []
    try:
        with BILLING_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                mode = row.get("mode", "").upper()
                if mode == "INVOICE":
                    try:
                        amount = float(row.get("amount_total", 0) or 0)
                    except ValueError:
                        amount = 0
                    records.append({
                        "type":        "invoice",
                        "date":        row.get("timestamp", "")[:10],
                        "client":      row.get("client_name", ""),
                        "project":     row.get("project_or_event", ""),
                        "amount":      amount,
                        "invoice_num": row.get("invoice_number", ""),
                    })
                elif mode == "PAYMENT":
                    try:
                        amount = float(row.get("payment_amount", 0) or 0)
                    except ValueError:
                        amount = 0
                    records.append({
                        "type":        "payment",
                        "date":        row.get("timestamp", "")[:10],
                        "invoice_num": row.get("invoice_number", ""),
                        "amount":      amount,
                        "payment_date": row.get("payment_date", ""),
                    })
    except Exception:
        pass
    return records


def _income_this_month(records: list[dict]) -> dict:
    """Filter income records to current month."""
    today = date.today()
    ym    = f"{today.year}-{today.month:02d}"
    invoiced = [r for r in records if r["type"] == "invoice" and r["date"].startswith(ym)]
    received = [r for r in records if r["type"] == "payment"  and r["date"].startswith(ym)]
    return {
        "month":           today.strftime("%B %Y"),
        "invoiced_total":  sum(r["amount"] for r in invoiced),
        "invoiced_count":  len(invoiced),
        "received_total":  sum(r["amount"] for r in received),
        "received_count":  len(received),
        "invoiced_detail": invoiced,
        "received_detail": received,
    }


def _income_ytd(records: list[dict]) -> float:
    """Sum all PAYMENT amounts this calendar year (cash basis)."""
    year = str(date.today().year)
    return sum(
        r["amount"] for r in records
        if r["type"] == "payment" and r["date"].startswith(year)
    )


# ── Expenses ───────────────────────────────────────────────────────────────────

def _load_expenses() -> dict:
    if EXPENSE_JSON.exists():
        try:
            return json.loads(EXPENSE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": []}


def _save_expenses(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    EXPENSE_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _expenses_ytd(entries: list[dict]) -> dict:
    """Sum expenses by category for current year."""
    year = str(date.today().year)
    by_cat: dict[str, float] = {}
    for e in entries:
        if e.get("date", "").startswith(year):
            cat = e.get("category", "other")
            by_cat[cat] = by_cat.get(cat, 0) + float(e.get("amount", 0))
    return by_cat


# ── Quarterly tax estimate ─────────────────────────────────────────────────────

def _next_deadline() -> tuple[str, str]:
    today_str = date.today().strftime("%Y-%m-%d")
    for label, deadline in QUARTERLY_DEADLINES:
        if deadline >= today_str:
            return label, deadline
    return QUARTERLY_DEADLINES[-1]


def _quarterly_estimate(ytd_income: float, ytd_expenses: float) -> dict:
    net             = max(ytd_income - ytd_expenses, 0)
    se_tax          = net * SE_TAX_RATE * 0.9207  # deductible half of SE
    income_tax      = net * INCOME_TAX_RATE
    total_estimated = se_tax + income_tax
    quarterly_share = total_estimated / 4
    q_label, q_date = _next_deadline()
    return {
        "ytd_income":   ytd_income,
        "ytd_expenses": ytd_expenses,
        "net_income":   net,
        "se_tax":       round(se_tax, 2),
        "income_tax":   round(income_tax, 2),
        "total_annual": round(total_estimated, 2),
        "per_quarter":  round(quarterly_share, 2),
        "next_deadline_label": q_label,
        "next_deadline_date":  q_date,
    }


# ── LLM formatters ─────────────────────────────────────────────────────────────

_INCOME_PROMPT = """\
You are a financial assistant for Winship Live, a sole proprietor music business.

Here is the income summary for {month}:
- Invoices sent: {invoiced_count} totaling ${invoiced_total:.2f}
- Payments received: {received_count} totaling ${received_total:.2f}

Details:
{details}

Write a clear, friendly 3-5 sentence summary of this month's income activity.
Focus on what was billed vs what actually came in. Keep it conversational.
Return plain text only, no markdown."""

_TAX_PROMPT = """\
You are a tax advisor for Winship Live, a sole proprietor music business.

Current numbers:
- YTD income received (cash basis): ${ytd_income:.2f}
- YTD business expenses logged: ${ytd_expenses:.2f}
- Net income: ${net_income:.2f}
- Estimated self-employment tax (15.3%): ${se_tax:.2f}
- Estimated federal income tax (~22%): ${income_tax:.2f}
- Total estimated annual tax liability: ${total_annual:.2f}
- Estimated payment per quarter: ${per_quarter:.2f}
- Next deadline: {next_deadline_label} due {next_deadline_date}

Write a clear 4-6 sentence summary. Include: what they owe per quarter, when the next
payment is due, and a note that these are estimates and a CPA should confirm.
Return plain text only, no markdown."""

_EXPENSE_PARSE_PROMPT = """\
Extract expense details from this message. Return a JSON object with these fields:
  amount      — numeric string (e.g. "49.99")
  category    — one of: home_studio, gear, software, miles, music_services, meals, professional, marketing, phone, legal, other
  description — short description of the expense
  date        — YYYY-MM-DD if mentioned, otherwise today's date {today}

Message: {text}
Return only valid JSON, no markdown."""


def _format_income_reply(summary: dict) -> str:
    details = ""
    for r in summary["invoiced_detail"]:
        details += f"  Invoice {r.get('invoice_num','')} — {r['client']} / {r['project']}: ${r['amount']:.2f}\n"
    for r in summary["received_detail"]:
        details += f"  Payment received for {r.get('invoice_num','')} on {r.get('payment_date','')}: ${r['amount']:.2f}\n"
    if not details:
        details = "  (no transactions this month)"

    prompt = _INCOME_PROMPT.format(
        month=summary["month"],
        invoiced_count=summary["invoiced_count"],
        invoiced_total=summary["invoiced_total"],
        received_count=summary["received_count"],
        received_total=summary["received_total"],
        details=details,
    )
    result = ollama_call(prompt, timeout=30).strip()
    if not result:
        return (
            f"Income for {summary['month']}:\n"
            f"Invoiced: ${summary['invoiced_total']:.2f} ({summary['invoiced_count']} invoice(s))\n"
            f"Received: ${summary['received_total']:.2f} ({summary['received_count']} payment(s))"
        )
    return result


def _format_tax_reply(est: dict) -> str:
    prompt = _TAX_PROMPT.format(**est)
    result = ollama_call(prompt, timeout=30).strip()
    if not result:
        return (
            f"Estimated quarterly payment: ${est['per_quarter']:.2f}\n"
            f"Next due: {est['next_deadline_label']} — {est['next_deadline_date']}\n"
            f"Annual estimate: ${est['total_annual']:.2f} (net ${est['net_income']:.2f})\n"
            f"Note: consult a CPA for accurate figures."
        )
    return result


def _parse_expense_from_text(text: str) -> dict | None:
    """Try to extract expense fields from a natural-language message."""
    today = date.today().strftime("%Y-%m-%d")
    prompt = _EXPENSE_PARSE_PROMPT.format(text=text, today=today)
    parsed = ollama_json(prompt, timeout=20)
    if not isinstance(parsed, dict):
        return None
    try:
        amount = float(parsed.get("amount", 0) or 0)
        if amount <= 0:
            return None
    except (ValueError, TypeError):
        return None
    return {
        "id":          f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "date":        parsed.get("date", today),
        "amount":      amount,
        "category":    parsed.get("category", "other"),
        "description": parsed.get("description", text[:80]),
        "logged_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ── Markdown writer ────────────────────────────────────────────────────────────

def _write_cpa_log_md() -> None:
    billing_records = _load_billing_income()
    expense_data    = _load_expenses()
    entries         = expense_data.get("entries", [])
    ytd_income      = _income_ytd(billing_records)
    expense_by_cat  = _expenses_ytd(entries)
    ytd_expenses    = sum(expense_by_cat.values())
    est             = _quarterly_estimate(ytd_income, ytd_expenses)
    today           = date.today().strftime("%Y-%m-%d")

    cat_rows = "\n".join(
        f"| {DEDUCTION_CATEGORIES.get(cat, cat).split(' — ')[0]} | ${amt:.2f} |"
        for cat, amt in sorted(expense_by_cat.items(), key=lambda x: -x[1])
    ) or "| (none logged) | — |"

    recent_expenses = sorted(entries, key=lambda e: e.get("date",""), reverse=True)[:10]
    expense_rows = "\n".join(
        f"| {e['date']} | {e.get('category','?')} | {e.get('description','')} | ${float(e.get('amount',0)):.2f} |"
        for e in recent_expenses
    ) or "| — | — | — | — |"

    content = (
        "---\n"
        "type: cpa-log\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# CPA Log\n\n"
        "_Managed by `chief_cpa_brain.py` — do not edit manually._\n\n"
        "## YTD Summary\n\n"
        f"| | |\n|---|---|\n"
        f"| YTD Income Received | ${ytd_income:.2f} |\n"
        f"| YTD Expenses Logged | ${ytd_expenses:.2f} |\n"
        f"| Net Income | ${est['net_income']:.2f} |\n"
        f"| Est. Annual Tax | ${est['total_annual']:.2f} |\n"
        f"| Est. Per Quarter | ${est['per_quarter']:.2f} |\n"
        f"| Next Deadline | {est['next_deadline_label']} — {est['next_deadline_date']} |\n\n"
        "## Expenses by Category (YTD)\n\n"
        "| Category | Total |\n|---|---|\n"
        + cat_rows + "\n\n"
        "## Recent Expenses\n\n"
        "| Date | Category | Description | Amount |\n|---|---|---|---|\n"
        + expense_rows + "\n\n"
        "## Deduction Categories\n\n"
        + "\n".join(f"- **{k}** — {v}" for k, v in DEDUCTION_CATEGORIES.items())
        + "\n"
    )
    CPA_LOG_MD.parent.mkdir(parents=True, exist_ok=True)
    CPA_LOG_MD.write_text(content, encoding="utf-8")


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    # ── Log an expense ─────────────────────────────────────────────────────────
    if any(k in t for k in ("log expense", "add expense", "i spent", "i paid for", "expense:")):
        entry = _parse_expense_from_text(text)
        if not entry:
            return ["Couldn't parse that expense. Try: 'log expense $50 software DistroKid renewal'"]
        data = _load_expenses()
        data.setdefault("entries", []).append(entry)
        _save_expenses(data)
        _write_cpa_log_md()
        return [
            f"Expense logged: ${entry['amount']:.2f} — {entry['description']}\n"
            f"Category: {entry['category']}  Date: {entry['date']}\n"
            f"ID: {entry['id']}"
        ]

    # ── Deductions ─────────────────────────────────────────────────────────────
    if any(k in t for k in ("deduction", "what can i deduct", "write off", "write-off")):
        lines = ["Deduction categories for Winship Live (sole proprietor):\n"]
        for cat, desc in DEDUCTION_CATEGORIES.items():
            lines.append(f"• {desc}")
        lines.append("\nLog expenses with: 'log expense $[amount] [category] [description]'")
        _write_cpa_log_md()
        return ["\n".join(lines)]

    # ── Quarterly tax ──────────────────────────────────────────────────────────
    if any(k in t for k in ("quarterly", "estimated tax", "what do i owe", "tax owed", "quarterly tax")):
        billing_records = _load_billing_income()
        expense_data    = _load_expenses()
        ytd_income      = _income_ytd(billing_records)
        ytd_expenses    = sum(_expenses_ytd(expense_data.get("entries", [])).values())
        est             = _quarterly_estimate(ytd_income, ytd_expenses)
        reply           = _format_tax_reply(est)
        _write_cpa_log_md()
        return [reply]

    # ── Income summary (default) ───────────────────────────────────────────────
    billing_records = _load_billing_income()
    summary         = _income_this_month(billing_records)
    reply           = _format_income_reply(summary)
    _write_cpa_log_md()
    return [reply]


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    print(f"Running CPA brain: '{text or 'income summary'}'\n")
    for line in handle(text):
        print(line)
    print(f"\nCPA Log: {CPA_LOG_MD}")
    print(f"Expense JSON: {EXPENSE_JSON}")
