"""
chief_queue_brain.py

Telegram-to-Claude-Code request queue. When Winship sends a feature
request, bug report, or build task via Telegram while not remoted in,
this brain writes it to a queue file with a timestamp.

Claude Code reads this queue at session start and presents pending items
for approval before executing.

Queue file: /mnt/c/OpenClaw/logs/claude_queue.log
Format:     [ISO-TIMESTAMP] STATUS:pending ITEM: <description>

Triggered by:
  - "queue request" / "add to queue" / "remember to"
  - "when you're at the computer" / "feature request"
  - "add a feature" / "build [something]" / "fix [something]"
Intent: queue_request in chief_router.py

Saves to:
  - /mnt/c/OpenClaw/logs/claude_queue.log      (source of truth)
  - /mnt/c/OpenClawShared/openclaw-vault/System/Claude Queue Log.md
"""

import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ────────────────────────────────────────────────────────────────────────

QUEUE_LOG     = Path("/mnt/c/OpenClaw/logs/claude_queue.log")
VAULT_SYS_DIR = Path("/mnt/c/OpenClawShared/openclaw-vault/System")
QUEUE_MD      = VAULT_SYS_DIR / "Claude Queue Log.md"

# ── Queue format ─────────────────────────────────────────────────────────────────
#   [2026-03-17T14:23:00] STATUS:pending ITEM: <description>
#   [2026-03-17T15:00:00] STATUS:done    ITEM: <description>

_LINE_PATTERN = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+STATUS:(?P<status>\w+)\s+ITEM:\s+(?P<item>.+)$"
)


def _read_queue() -> list[dict]:
    if not QUEUE_LOG.exists():
        return []
    entries = []
    for i, line in enumerate(QUEUE_LOG.read_text(encoding="utf-8").splitlines()):
        m = _LINE_PATTERN.match(line.strip())
        if m:
            entries.append({
                "index":  i,
                "ts":     m.group("ts"),
                "status": m.group("status"),
                "item":   m.group("item"),
                "raw":    line,
            })
    return entries


def _write_queue(entries: list[dict]) -> None:
    QUEUE_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"[{e['ts']}] STATUS:{e['status']} ITEM: {e['item']}" for e in entries]
    QUEUE_LOG.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _append_queue(item: str) -> None:
    QUEUE_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] STATUS:pending ITEM: {item}\n"
    with QUEUE_LOG.open("a", encoding="utf-8") as f:
        f.write(line)


def _write_queue_md(entries: list[dict]) -> None:
    VAULT_SYS_DIR.mkdir(parents=True, exist_ok=True)
    today   = datetime.now().strftime("%Y-%m-%d %H:%M")
    pending = [e for e in entries if e["status"] == "pending"]
    done    = [e for e in entries if e["status"] == "done"]

    pending_rows = "\n".join(
        f"| {e['ts'][:16]} | {e['item']} |"
        for e in pending
    ) or "| — | — |"

    done_rows = "\n".join(
        f"| {e['ts'][:16]} | {e['item']} |"
        for e in reversed(done[-10:])
    ) or "| — | — |"

    content = (
        "---\ntype: queue-log\n"
        f"last_updated: {today}\n---\n\n"
        "# Claude Queue Log\n\n"
        "_Managed by `chief_queue_brain.py`. Claude Code reads this at session start._\n\n"
        f"**Pending:** {len(pending)}  **Completed:** {len(done)}\n\n"
        "## Pending Items\n\n"
        "| Queued At | Request |\n|---|---|\n"
        + pending_rows + "\n\n"
        "## Completed Items (last 10)\n\n"
        "| Completed At | Request |\n|---|---|\n"
        + done_rows + "\n"
    )
    QUEUE_MD.write_text(content, encoding="utf-8")


# ── Natural language → clean action description ──────────────────────────────────

_CLEAN_PROMPT = """\
Convert this message into a clean, actionable task description for a developer queue.
The task will be read by Claude Code at the start of a session.

Rules:
- Start with a verb (Build, Add, Fix, Update, Investigate, Refactor, Create)
- Be specific — include the brain name or file if mentioned
- One sentence, max 120 characters
- Don't include phrases like "remember to" or "when you're at the computer"

Message: {text}
Task:"""


def _clean_item(text: str) -> str:
    """Use LLM to turn natural language into a clean task description."""
    # Strip trigger phrases first
    cleaned = re.sub(
        r"(queue request|add to queue|remember to|when you're at the computer|"
        r"feature request|add a feature|add feature)\s*:?\s*",
        "", text, flags=re.IGNORECASE
    ).strip()

    if not cleaned:
        return text[:120]

    prompt = _CLEAN_PROMPT.format(text=cleaned)
    result = ollama_call(prompt, timeout=15, task_class="chief_agentic_code").strip()
    # Fallback: use stripped text if LLM unavailable or too short
    if result and len(result) > 10:
        return result[:120]
    return cleaned[:120]


# ── Public functions (also used by chief_listener.py startup check) ──────────────

def check_pending_queue() -> list[str]:
    """Return list of pending item descriptions. Called at startup."""
    entries = _read_queue()
    return [e["item"] for e in entries if e["status"] == "pending"]


def mark_done(index: int) -> bool:
    """Mark item at position index (among pending items) as done."""
    entries = _read_queue()
    pending = [e for e in entries if e["status"] == "pending"]
    if index < 0 or index >= len(pending):
        return False
    target = pending[index]
    for e in entries:
        if e["ts"] == target["ts"] and e["item"] == target["item"]:
            e["status"] = "done"
            break
    _write_queue(entries)
    _write_queue_md(entries)
    return True


# ── Handlers ─────────────────────────────────────────────────────────────────────

def _handle_add(text: str) -> list[str]:
    item    = _clean_item(text)
    _append_queue(item)
    entries = _read_queue()
    _write_queue_md(entries)
    pending_count = sum(1 for e in entries if e["status"] == "pending")
    return [
        f"Queued: {item}\n"
        f"Queue depth: {pending_count} pending item(s). "
        f"Claude Code will present this at next session start."
    ]


def _handle_status() -> list[str]:
    entries = _read_queue()
    pending = [e for e in entries if e["status"] == "pending"]
    _write_queue_md(entries)

    if not pending:
        return ["Queue is empty. No pending Claude Code requests."]

    lines = [f"Pending queue ({len(pending)} item(s)):\n"]
    for i, e in enumerate(pending):
        lines.append(f"  {i + 1}. [{e['ts'][:16]}] {e['item']}")
    lines.append("\nTell Claude Code 'done queue [n]' to mark an item complete.")
    return ["\n".join(lines)]


def _handle_done(text: str) -> list[str]:
    m = re.search(r"\d+", text)
    if not m:
        return ["Specify which item to mark done. Example: 'done queue 1'"]
    index = int(m.group()) - 1  # convert 1-based to 0-based
    success = mark_done(index)
    if success:
        return [f"Marked queue item {index + 1} as done."]
    return [f"No pending item #{index + 1}. Run 'queue status' to see current items."]


# ── Public entry point ────────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    if any(k in t for k in ("queue status", "what's queued", "whats queued", "show queue", "pending queue")):
        return _handle_status()

    if re.search(r"\bdone queue\b", t) or re.search(r"\bqueue done\b", t):
        return _handle_done(text)

    # Default: add to queue
    return _handle_add(text)


# ── CLI ───────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "queue status"
    print(f"Running queue brain: '{text}'\n")
    for line in handle(text):
        print(line)

    # Show startup check output
    pending = check_pending_queue()
    if pending:
        print(f"\n[Startup check] {len(pending)} pending item(s):")
        for i, item in enumerate(pending, 1):
            print(f"  {i}. {item}")
    print(f"\nQueue log: {QUEUE_LOG}")
    print(f"Queue MD:  {QUEUE_MD}")
