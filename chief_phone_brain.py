"""
chief_phone_brain.py

Logs phone calls, generates call scripts, and tracks call history
for Winship Live / Deep Pocket Records client relationships.

No outbound calling — pure logging and LLM-assisted drafting.

Triggered by:
  - "log call" / "log a call" / "just got off a call" / "had a call with"
  - "call script" / "what should I say to" / "talking points for"
  - "call log" / "call history" / "recent calls"
Intent: phone_log in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/call_log.json  (source of truth)
  - openclaw-vault/Business/Call Log.md            (Obsidian)
"""

import json
from datetime import datetime, date
from pathlib import Path

from chief_llm import ollama_call, ollama_json

# ── Paths ──────────────────────────────────────────────────────────────────────

BUSINESS_DIR  = Path("/mnt/c/OpenClawShared/business")
CALL_JSON     = BUSINESS_DIR / "call_log.json"
CALL_MD       = Path("/mnt/c/OpenClawShared/openclaw-vault/Business/Call Log.md")
BILLING_CSV   = Path("/home/openclaw/OpenClaw/exports/billing_records.csv")

# ── Storage ────────────────────────────────────────────────────────────────────

def _load_calls() -> dict:
    if CALL_JSON.exists():
        try:
            return json.loads(CALL_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"calls": []}


def _save_calls(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    CALL_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _new_call_id() -> str:
    today = datetime.now().strftime("%Y%m%d")
    data  = _load_calls()
    count = sum(1 for c in data.get("calls", []) if c["id"].startswith(f"CALL-{today}"))
    return f"CALL-{today}-{count + 1:03d}"


# ── LLM: parse a call log from natural language ───────────────────────────────

_PARSE_CALL_PROMPT = """\
Extract phone call details from this message. Return a JSON object with these fields:
  contact      — person's name (string)
  direction    — "inbound" or "outbound" (default "outbound")
  duration_min — call duration in minutes as integer, or null if not mentioned
  outcome      — one-sentence summary of what was decided or discussed
  invoice_ref  — invoice number if mentioned (e.g. "INV-1001"), or null
  notes        — any additional details worth keeping, or null
  date         — YYYY-MM-DD if a specific date was mentioned, otherwise null

Message: {text}
Today's date: {today}

Return only valid JSON, no markdown."""

_SCRIPT_PROMPT = """\
You are a professional music business assistant helping Winship Wheatley IV
(Winship Live / Deep Pocket Records) prepare for a phone call.

Context: {context}

Generate a concise call script with:
1. Opening (how to start the call professionally)
2. Key talking points (3-5 bullet points)
3. Ask (what to request or confirm)
4. Closing (how to end the call)

Keep it natural and direct. Under 200 words. Plain text, no markdown headers."""


def _parse_call_entry(text: str) -> dict | None:
    today = date.today().strftime("%Y-%m-%d")
    prompt = _PARSE_CALL_PROMPT.format(text=text, today=today)
    parsed = ollama_json(prompt, timeout=30)
    if not isinstance(parsed, dict):
        return None
    contact = parsed.get("contact", "").strip()
    if not contact:
        return None
    return {
        "id":           _new_call_id(),
        "date":         parsed.get("date") or today,
        "logged_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "contact":      contact,
        "direction":    parsed.get("direction", "outbound"),
        "duration_min": parsed.get("duration_min"),
        "outcome":      (parsed.get("outcome") or "").strip() or "logged",
        "invoice_ref":  parsed.get("invoice_ref") or None,
        "notes":        parsed.get("notes") or "",
    }


def _generate_script(text: str) -> str:
    # Pull recent call context for this contact if available
    data  = _load_calls()
    calls = data.get("calls", [])

    # Look for a name in the text
    context_lines = [f"Request: {text}"]
    for call in reversed(calls[-10:]):
        name = call.get("contact", "")
        if name and name.lower() in text.lower():
            context_lines.append(
                f"Previous call with {name} on {call['date']}: {call['outcome']}"
            )
            if call.get("invoice_ref"):
                context_lines.append(f"  Invoice reference: {call['invoice_ref']}")

    prompt = _SCRIPT_PROMPT.format(context="\n".join(context_lines))
    result = ollama_call(prompt, timeout=40).strip()
    if not result:
        return (
            "Call script:\n"
            "1. Introduce yourself and reason for calling\n"
            "2. Reference your previous conversation\n"
            "3. State what you need clearly\n"
            "4. Confirm next steps and timeline\n"
            "5. Thank them and close"
        )
    return result


# ── Markdown writer ────────────────────────────────────────────────────────────

def _write_call_log_md() -> None:
    data  = _load_calls()
    calls = data.get("calls", [])
    today = date.today().strftime("%Y-%m-%d")

    recent = sorted(calls, key=lambda c: c.get("date", ""), reverse=True)[:20]

    rows = []
    for c in recent:
        dur     = f"{c['duration_min']}m" if c.get("duration_min") else "—"
        inv     = c.get("invoice_ref") or "—"
        outcome = (c.get("outcome") or "")[:80]
        rows.append(
            f"| {c['date']} | {c.get('contact','?')} "
            f"| {c.get('direction','?')} | {dur} | {inv} | {outcome} |"
        )

    table = (
        "| Date | Contact | Direction | Duration | Invoice | Outcome |\n"
        "|---|---|---|---|---|---|\n"
        + ("\n".join(rows) if rows else "| — | — | — | — | — | (no calls logged yet) |")
    )

    content = (
        "---\n"
        "type: call-log\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Call Log\n\n"
        "_Managed by `chief_phone_brain.py` — do not edit manually._\n\n"
        f"**Total calls logged:** {len(calls)}\n\n"
        "## Recent Calls\n\n"
        + table + "\n\n"
        "## How to Log a Call\n\n"
        "- `log call with [name] — [what happened]`\n"
        "- `call script for [purpose]`\n"
        "- `call log` or `recent calls`\n"
    )
    CALL_MD.parent.mkdir(parents=True, exist_ok=True)
    CALL_MD.write_text(content, encoding="utf-8")


# ── Formatters ─────────────────────────────────────────────────────────────────

def _format_call_entry(entry: dict) -> str:
    dur  = f"  Duration: {entry['duration_min']} min" if entry.get("duration_min") else ""
    inv  = f"  Invoice: {entry['invoice_ref']}" if entry.get("invoice_ref") else ""
    note = f"  Notes: {entry['notes']}" if entry.get("notes") else ""
    return (
        f"📞 Call logged — {entry['id']}\n"
        f"Contact: {entry['contact']}  ({entry['direction']})\n"
        f"Date: {entry['date']}{dur}{inv}\n"
        f"Outcome: {entry['outcome']}{note}"
    )


def _format_history(calls: list[dict], limit: int = 10) -> str:
    if not calls:
        return "No calls logged yet.\n\nTo log a call: 'log call with [name] — [outcome]'"
    recent = sorted(calls, key=lambda c: c.get("date", ""), reverse=True)[:limit]
    lines  = [f"📞 Call Log — last {len(recent)} entries\n"]
    for c in recent:
        dur = f" ({c['duration_min']}m)" if c.get("duration_min") else ""
        inv = f" [{c['invoice_ref']}]" if c.get("invoice_ref") else ""
        lines.append(
            f"• {c['date']}  {c['contact']}{dur}{inv}\n"
            f"  {c.get('outcome','')}"
        )
    return "\n".join(lines)


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    # ── Call history ───────────────────────────────────────────────────────────
    if any(k in t for k in ("call log", "call history", "recent calls", "show calls")):
        data  = _load_calls()
        reply = _format_history(data.get("calls", []))
        _write_call_log_md()
        return [reply]

    # ── Call script / talking points ───────────────────────────────────────────
    if any(k in t for k in ("call script", "talking points", "what should i say",
                             "how should i approach", "script for")):
        reply = _generate_script(text)
        return [reply]

    # ── Log a call (default) ───────────────────────────────────────────────────
    entry = _parse_call_entry(text)
    if not entry:
        return [
            "Couldn't parse that call. Try:\n"
            "'log call with Marcus — discussed INV-1001, agreed to pay Friday'\n"
            "'just got off a call with Sarah, she wants a revised quote'"
        ]
    data = _load_calls()
    data.setdefault("calls", []).append(entry)
    _save_calls(data)
    _write_call_log_md()
    return [_format_call_entry(entry)]


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "call log"
    print(f"Running phone brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nCall Log MD: {CALL_MD}")
    print(f"Call JSON:   {CALL_JSON}")
