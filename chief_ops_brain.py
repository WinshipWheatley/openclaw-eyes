"""
chief_ops_brain.py

Top-level ops/admin intake handler.

Recognizes messages prefixed with any of:
  - Ops update:
  - Operational update:
  - Brain dump:
  - Admin update:

Behavior:
  - When album is active: defers items silently; delivers summary after session closes.
  - Otherwise: routes items immediately and returns a short readout.

Readout format:
  1. What got routed where
  2. What is waiting on you
  3. What to handle next

Intent: ops_intake in chief_router.py
Deferred state: /mnt/c/OpenClaw/logs/ops_intake_deferred.json
"""

import json
from datetime import datetime
from pathlib import Path

INTAKE_JSON = Path("/mnt/c/OpenClaw/logs/ops_intake_deferred.json")

INTAKE_MARKERS = (
    "ops update:",
    "operational update:",
    "brain dump:",
    "admin update:",
)


# ── Detection ─────────────────────────────────────────────────────────────────

def is_ops_intake(text: str) -> bool:
    t = text.lower().strip()
    return any(t.startswith(m) for m in INTAKE_MARKERS)


def _strip_marker(text: str) -> str:
    t = text.strip()
    for m in INTAKE_MARKERS:
        if t.lower().startswith(m):
            return t[len(m):].strip()
    return t


# ── Item parsing ──────────────────────────────────────────────────────────────

def _parse_items(body: str) -> list[str]:
    """Split body into individual line items. Strips bullets/numbers."""
    lines = []
    for line in body.splitlines():
        line = line.strip().lstrip("-–•*0123456789.) ")
        if line:
            lines.append(line)
    # If no line breaks, treat whole body as one item
    if not lines and body.strip():
        lines = [body.strip()]
    return lines


# ── Classification ────────────────────────────────────────────────────────────

_EMAIL_SIGNALS = (
    "email", "follow-up", "follow up", "drafted email", "draft email",
    "sent email", "sent follow", "reply", "outbox", "inbox",
)
_CALENDAR_SIGNALS = (
    "booked", "booking", "gig", "gigs", "cleaning", "golf",
    "tomorrow", "pickup", "appointment", "calendar",
    "march", "april", "may", "june",
    "9:30", "8:15", "8:30", "at 9:", "at 8:", "at 10:", "at 7:",
)
_ACTION_SIGNALS = (
    "review", "need to", "needs to", "handle", "check on",
    "two drafted", "two emails", "needs review", "for review",
    "waiting on", "action needed",
)


def _classify(item: str) -> str:
    t = item.lower()
    # Email wins over calendar if email signals present
    if any(k in t for k in _EMAIL_SIGNALS):
        return "email"
    if any(k in t for k in _ACTION_SIGNALS):
        return "action"
    if any(k in t for k in _CALENDAR_SIGNALS):
        return "calendar"
    return "note"


def _route_item(item: str, cls: str) -> tuple[str, str]:
    """Return (destination_label, status) for display."""
    t = item.lower()
    if cls == "email":
        if any(k in t for k in ("review", "drafted", "draft", "two", "needs")):
            return ("action queue", "needs review")
        return ("email log", "logged")
    if cls == "calendar":
        return ("calendar notes", "noted")
    if cls == "action":
        return ("action queue", "needs attention")
    return ("notes", "captured")


# ── Response builder ──────────────────────────────────────────────────────────

def _build_readout(items: list[str], header: str = "Ops intake processed") -> list[str]:
    """Build the standard 3-part readout for a list of items."""
    if not items:
        return [f"{header} (no items found)."]

    classified = [(item, _classify(item)) for item in items]
    routed     = [(item, cls, *_route_item(item, cls)) for item, cls in classified]
    waiting    = [(item, dest, note) for item, cls, dest, note in routed
                  if note in ("needs review", "needs attention")]

    lines = [f"{header}:\n"]

    # 1. What got routed
    for item, cls, dest, note in routed:
        lines.append(f"• {item[:90]}")
        lines.append(f"  -> {dest} ({note})")

    # 2. What's waiting
    if waiting:
        lines.append(f"\nWaiting on you ({len(waiting)}):")
        for item, dest, note in waiting:
            lines.append(f"• {item[:90]}")

    # 3. What to handle next
    if waiting:
        lines.append(f"\nHandle next: {waiting[0][0][:90]}")
    else:
        lines.append("\nNothing needs immediate action.")

    return ["\n".join(lines)]


# ── Deferred state ────────────────────────────────────────────────────────────

def _load_deferred() -> list[dict]:
    if INTAKE_JSON.exists():
        try:
            return json.loads(INTAKE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_deferred(items: list[dict]) -> None:
    INTAKE_JSON.parent.mkdir(parents=True, exist_ok=True)
    INTAKE_JSON.write_text(json.dumps(items, indent=2), encoding="utf-8")


def save_deferred(text: str) -> None:
    """Append one ops intake message to the defer queue."""
    deferred = _load_deferred()
    deferred.append({
        "text":         text,
        "captured_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_deferred(deferred)


def clear_deferred() -> None:
    _save_deferred([])


def deferred_summary() -> list[str] | None:
    """
    Return deferred ops summary for post-album delivery, then clear the queue.
    Returns None if nothing was deferred.
    """
    entries = _load_deferred()
    if not entries:
        return None

    # Collect all items across all deferred messages
    all_items: list[str] = []
    timestamps: list[str] = []
    for entry in entries:
        body = _strip_marker(entry.get("text", ""))
        all_items.extend(_parse_items(body))
        timestamps.append(entry.get("captured_at", ""))

    time_range = timestamps[0] if len(timestamps) == 1 else f"{timestamps[0]} – {timestamps[-1]}"
    header = f"From focus ({time_range}) — {len(entries)} update(s) captured during album session"

    clear_deferred()
    return _build_readout(all_items, header)


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str) -> list[str]:
    """Parse and immediately route an ops intake message. Returns readout."""
    body  = _strip_marker(text)
    items = _parse_items(body)
    return _build_readout(items)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        _console = Console()
        _rich = True
    except ImportError:
        _rich = False

    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Ops update:\n"
        "- sent follow-up email to Capital Hilton, deposit not received\n"
        "- booked gigs on March 27 and 28, already in calendar, need reflected in system state\n"
        "- tomorrow cleaning company at 9:30\n"
        "- golf with dad tomorrow, pickup 8:15–8:30\n"
        "- Anna owns the cleaning company; front door will be unlocked\n"
        "- two drafted emails need review: Glenn / St. Anne's and Dane / Live Arts"
    )
    result = handle(text)
    for block in result:
        if _rich:
            # Color the readout: green for captured, yellow for waiting, bold for handle next
            t = Text()
            for line in block.splitlines():
                if line.startswith("Waiting on you"):
                    t.append(line + "\n", style="bold yellow")
                elif line.startswith("Handle next:"):
                    t.append(line + "\n", style="bold red")
                elif line.startswith("Nothing needs"):
                    t.append(line + "\n", style="green")
                elif line.startswith("•") and "->" not in line:
                    t.append(line + "\n", style="white")
                elif "->" in line:
                    t.append(line + "\n", style="dim cyan")
                else:
                    t.append(line + "\n", style="bold")
            _console.print(Panel(t, border_style="blue"))
        else:
            print(block)
