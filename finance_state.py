"""finance_state — hand-maintained per-account workflow narrative (finance_state.json).

Task 140 (ONE money truth): this module is DEPRECATED as a money-claims source.
finance_state.json is a stale, hand-edited narrative file (last substantive
update 2026-04-11) whose client keys and amounts drift from the ledger
(e.g. live_arts_maryland_recurring vs the ledger's live_arts_md). Money-class
questions (who owes / how much open / did they pay) are answered from
receivables_month_bounded via money_truth.py BEFORE any path in this module
runs — see cassandra_brain._handle_money_truth_question. What remains
legitimate here is workflow/status NARRATIVE (next actions, document status),
not amount claims. Do not add new money-amount consumers to this file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


FINANCE_STATE_PATH = Path("/home/openclaw/finance_state.json")

# Task 140 disposition marker: money AMOUNT claims must come from money_truth.py.
MONEY_CLAIMS_DEPRECATED = True

_PAYMENT_HINTS = (
    "payment",
    "paid",
    "deposit",
    "came through",
    "cleared",
    "received",
    "venmo",
    "zelle",
    "direct deposit",
)
_INVOICE_HINTS = (
    "invoice",
    "smartspend",
    "w-9",
    "routing",
    "account number",
    "portal",
)
_STATUS_HINTS = (
    "where are we",
    "what's the status",
    "what is the status",
    "what's going on",
    "what is going on",
    "what do i need to do",
    "what still needs",
    "next step",
    "where does that stand",
    "update",
    "status",
)


def load_finance_state(path: Path | None = None) -> dict:
    target = path or FINANCE_STATE_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _accounts(state: dict | None = None) -> dict[str, dict]:
    data = state if isinstance(state, dict) else load_finance_state()
    accounts = data.get("accounts")
    return accounts if isinstance(accounts, dict) else {}


def _aliases(account_key: str, account: dict) -> tuple[str, ...]:
    aliases = [account_key, str(account.get("label") or "").strip()]
    aliases.extend(a for a in account.get("aliases", []) if isinstance(a, str))
    return tuple(dict.fromkeys(a.lower() for a in aliases if a and a.strip()))


def find_finance_account(query: str, *, state: dict | None = None) -> tuple[str, dict] | None:
    q = (query or "").lower()
    for key, account in _accounts(state).items():
        if not isinstance(account, dict):
            continue
        if any(alias in q for alias in _aliases(key, account)):
            return key, account
    return None


def finance_entity_terms(query: str, *, state: dict | None = None) -> tuple[str, ...]:
    found = find_finance_account(query, state=state)
    if found is None:
        return ()
    key, account = found
    return _aliases(key, account)


def _open_actions(account: dict) -> list[dict]:
    actions = account.get("next_actions", [])
    if not isinstance(actions, list):
        return []
    kept: list[dict] = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "open").strip().lower() != "done":
            kept.append(item)
    return kept


def _first_open_action_text(account: dict) -> str:
    actions = _open_actions(account)
    if not actions:
        return ""
    return str(actions[0].get("action") or "").strip()


def _clean_sentence(text: str | None) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if value[-1] in ".!?":
        return value
    return value + "."


def _join_sentences(parts: list[str]) -> str:
    seen: set[str] = set()
    cleaned: list[str] = []
    for part in parts:
        sentence = _clean_sentence(part)
        if not sentence:
            continue
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(sentence)
    return " ".join(cleaned).strip()


def build_finance_snapshot(*, state: dict | None = None, limit: int = 4) -> str:
    lines: list[str] = []
    for _, account in list(_accounts(state).items())[:limit]:
        if not isinstance(account, dict):
            continue
        label = str(account.get("label") or "").strip()
        workflow = str(account.get("workflow_summary") or "").strip()
        next_step = _first_open_action_text(account)
        if not label or not workflow:
            continue
        line = f"  {label}: {workflow}"
        if next_step:
            line += f" Next: {next_step}"
        lines.append(line)
    if not lines:
        return ""
    return "[FINANCE STATE SNAPSHOT]\n" + "\n".join(lines)


def format_finance_context(query: str, *, state: dict | None = None) -> str:
    found = find_finance_account(query, state=state)
    if found is None:
        return ""

    _, account = found
    label = str(account.get("label") or "Finance account").strip()
    workflow = str(account.get("workflow_summary") or "").strip()
    payment = str(account.get("payment_summary") or "").strip()
    invoice = str(account.get("invoice_summary") or "").strip()
    lines = [f"[FINANCE STATE - {label}]"]

    if workflow:
        lines.append(f"Workflow: {workflow}")
    if payment:
        lines.append(f"Payments: {payment}")
    if invoice:
        lines.append(f"Invoices: {invoice}")

    documents = account.get("documents", [])
    if isinstance(documents, list):
        doc_lines = []
        for item in documents:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            status = str(item.get("status") or "").strip()
            if name and status:
                doc_lines.append(f"  {name}: {status}")
        if doc_lines:
            lines.append("Documents:")
            lines.extend(doc_lines)

    actions = _open_actions(account)
    if actions:
        lines.append("Open actions:")
        for item in actions[:3]:
            action = str(item.get("action") or "").strip()
            if not action:
                continue
            owner = str(item.get("owner") or "").strip()
            blocker = str(item.get("blocking_for") or "").strip()
            detail = action
            if owner:
                detail += f" (owner: {owner})"
            if blocker:
                detail += f" (blocks: {blocker})"
            lines.append(f"  - {detail}")

    quickbooks = account.get("quickbooks_ready")
    if isinstance(quickbooks, dict):
        ledger_status = str(quickbooks.get("ledger_status") or "").strip()
        needs_sync = quickbooks.get("needs_sync", [])
        if ledger_status or (isinstance(needs_sync, list) and needs_sync):
            lines.append("QuickBooks readiness:")
            if ledger_status:
                lines.append(f"  Ledger sync status: {ledger_status}")
            if isinstance(needs_sync, list):
                for item in needs_sync[:3]:
                    if isinstance(item, str) and item.strip():
                        lines.append(f"  - {item.strip()}")

    return "\n".join(lines)


def _asks_any(query: str, hints: tuple[str, ...]) -> bool:
    q = (query or "").lower()
    return any(hint in q for hint in hints)


def detect_finance_status_intent(query: str, *, state: dict | None = None) -> bool:
    if find_finance_account(query, state=state) is None:
        return False
    q = (query or "").lower()
    if _asks_any(q, _STATUS_HINTS) or _asks_any(q, _PAYMENT_HINTS) or _asks_any(q, _INVOICE_HINTS):
        return True
    if q.strip().endswith("?") and len(q.split()) <= 12:
        return True
    return False


def get_finance_payment_answer(query: str, *, state: dict | None = None) -> str | None:
    found = find_finance_account(query, state=state)
    if found is None:
        return None
    _, account = found
    payment = str(account.get("payment_summary") or "").strip()
    next_step = _first_open_action_text(account)
    return _join_sentences([payment, f"Next: {next_step}" if next_step else ""]) or None


def get_finance_status_answer(query: str, *, state: dict | None = None) -> str | None:
    found = find_finance_account(query, state=state)
    if found is None:
        return None
    _, account = found
    q = (query or "").lower()
    workflow = str(account.get("workflow_summary") or "").strip()
    payment = str(account.get("payment_summary") or "").strip()
    invoice = str(account.get("invoice_summary") or "").strip()
    next_step = _first_open_action_text(account)

    if _asks_any(q, _PAYMENT_HINTS):
        return _join_sentences([payment, f"Next: {next_step}" if next_step else ""]) or None
    if _asks_any(q, _INVOICE_HINTS):
        parts = [invoice]
        if "w-9" in q:
            parts.extend(
                str(item.get("detail") or "")
                for item in account.get("documents", [])
                if isinstance(item, dict) and "w-9" in str(item.get("name") or "").lower()
            )
        if "routing" in q or "account number" in q:
            parts.extend(
                str(item.get("detail") or "")
                for item in account.get("documents", [])
                if isinstance(item, dict)
                and any(term in str(item.get("name") or "").lower() for term in ("routing", "account"))
            )
        parts.append(f"Next: {next_step}" if next_step else "")
        return _join_sentences(parts) or None

    return _join_sentences([workflow, payment, f"Next: {next_step}" if next_step else ""]) or None
