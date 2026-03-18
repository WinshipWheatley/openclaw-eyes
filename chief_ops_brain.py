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

INTAKE_JSON  = Path("/mnt/c/OpenClaw/logs/ops_intake_deferred.json")

# ── Durable destination files ──────────────────────────────────────────────────
_VAULT_SYS = Path("/mnt/c/OpenClawShared/openclaw-vault/System")

EMAIL_MD    = _VAULT_SYS / "Ops Email Log.md"
CALENDAR_MD = _VAULT_SYS / "Ops Calendar Notes.md"
ACTIONS_MD  = _VAULT_SYS / "Ops Actions.md"
NOTES_MD    = _VAULT_SYS / "Ops Notes.md"
MASTER_LOG  = Path("/mnt/c/OpenClaw/logs/ops_intake_log.md")

_DEST_MAP: dict[str, Path] = {
    "email":    EMAIL_MD,
    "calendar": CALENDAR_MD,
    "action":   ACTIONS_MD,
    "note":     NOTES_MD,
}

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


# ── Meta-instruction filter ────────────────────────────────────────────────────

# Lines matching these are instructions to Chief, not ops content — skip them.
_META_PATTERNS = (
    "please capture",
    "capture and route this",
    "tell me what got",
    "what got routed",
    "what is waiting on me",
    "what should i handle",
    "what i should handle",
    "what to handle next",
    "after i finish the album",
    "after the album block",
    "operationally, then tell",
    "route this operationally",
)


def _is_meta(content: str) -> bool:
    t = content.lower()
    return any(k in t for k in _META_PATTERNS)


# ── Item parsing ──────────────────────────────────────────────────────────────

def _parse_items(body: str) -> list[str]:
    """
    Parse ops body into clean action items:
    - Groups indented sub-lines under their parent item
    - Filters meta-instruction lines (and their sub-items)
    - Falls back to single item if body has no line breaks
    """
    raw_lines = body.splitlines()

    # Build (indent_level, content) pairs, stripping bullet markers
    entries: list[tuple[int, str]] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        indent  = len(line) - len(line.lstrip(" \t"))
        content = stripped.lstrip("-–•*0123456789.) ").strip()
        if content:
            entries.append((indent, content))

    if not entries:
        return [body.strip()] if body.strip() else []

    items: list[str] = []
    i = 0
    while i < len(entries):
        indent, content = entries[i]

        # Collect children: all immediately following lines that are more indented
        j = i + 1
        children: list[str] = []
        while j < len(entries) and entries[j][0] > indent:
            children.append(entries[j][1])
            j += 1

        # Skip meta lines (and their sub-items)
        if _is_meta(content):
            i = j
            continue

        # Filter any meta children
        real_children = [c for c in children if not _is_meta(c)]

        if real_children:
            # Join sub-items into one composite item: "Parent: child1, child2"
            full = content.rstrip(":").strip() + ": " + ", ".join(real_children)
            items.append(full)
        else:
            items.append(content)

        i = j

    return items if items else ([body.strip()] if body.strip() else [])


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


def _status_for(item: str, cls: str) -> str:
    """Return a short status label for an item."""
    t = item.lower()
    if cls == "email" and any(k in t for k in ("review", "drafted", "draft", "two", "needs")):
        return "needs review"
    if cls == "action":
        return "needs attention"
    if cls == "email":
        return "logged"
    if cls == "calendar":
        return "noted"
    return "captured"


# ── Durable write layer ────────────────────────────────────────────────────────

def _append_to_file(dest: Path, item: str, ts: str) -> None:
    """Append one line to a destination file, creating it with a header if new."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_text(
            f"---\ntype: ops-log\n---\n\n# {dest.stem}\n\n",
            encoding="utf-8",
        )
    with dest.open("a", encoding="utf-8") as f:
        f.write(f"- [{ts}] {item}\n")


def _write_item(item: str, cls: str, ts: str) -> str:
    """
    Write item to the class-specific destination file and the master log.
    Returns the destination filename (basename) for display.
    """
    dest = _DEST_MAP.get(cls, NOTES_MD)
    _append_to_file(dest, item, ts)
    # Master log: one line per item with class tag
    MASTER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with MASTER_LOG.open("a", encoding="utf-8") as f:
        f.write(f"- [{ts}] [{cls}] {item}\n")
    return dest.name


# ── Process + write ────────────────────────────────────────────────────────────

def _process_and_write(items: list[str], ts: str = "") -> list[dict]:
    """
    Classify each item, write it to disk, return a list of result dicts:
      {item, cls, filename, status}
    """
    if not ts:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []
    for item in items:
        cls      = _classify(item)
        filename = _write_item(item, cls, ts)
        status   = _status_for(item, cls)
        results.append({
            "item":     item,
            "cls":      cls,
            "filename": filename,
            "status":   status,
        })
    return results


# ── Response builder ──────────────────────────────────────────────────────────

def _shorten(text: str, n: int = 60) -> str:
    return text if len(text) <= n else text[:n].rstrip() + "..."


def _build_readout(results: list[dict], header: str = "Ops intake processed") -> list[str]:
    """Build compact 3-part Telegram readout from processed results."""
    if not results:
        return [f"{header} (no items)."]

    waiting = [r for r in results if r["status"] in ("needs review", "needs attention")]

    lines = [f"{header} ({len(results)} item{'s' if len(results) != 1 else ''}):\n"]

    # 1. What got routed where — compact one-liner per item
    for r in results:
        lines.append(f"• {_shorten(r['item'])} -> {r['filename']}")

    # 2. What's waiting (full text so nothing is ambiguous)
    if waiting:
        lines.append(f"\nWaiting on you ({len(waiting)}):")
        for r in waiting:
            lines.append(f"• {r['item']}")

    # 3. What to handle next (full text — unambiguous)
    if waiting:
        lines.append(f"\nHandle next: {waiting[0]['item']}")
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
    Write + surface deferred ops items captured during album focus.
    Returns Telegram-ready readout, or None if nothing deferred.
    Items are written to disk at surface time (with their original capture timestamp).
    """
    entries = _load_deferred()
    if not entries:
        return None

    all_results: list[dict] = []
    timestamps: list[str] = []
    for entry in entries:
        body = _strip_marker(entry.get("text", ""))
        items = _parse_items(body)
        ts = entry.get("captured_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        timestamps.append(ts)
        all_results.extend(_process_and_write(items, ts))

    time_range = timestamps[0] if len(timestamps) == 1 else f"{timestamps[0]} – {timestamps[-1]}"
    header = f"From focus ({time_range}) — {len(entries)} update(s) captured during album session"

    clear_deferred()
    return _build_readout(all_results, header)


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str) -> list[str]:
    """Parse, write, and return Telegram readout for an ops intake message."""
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body    = _strip_marker(text)
    items   = _parse_items(body)
    results = _process_and_write(items, ts)
    return _build_readout(results)


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

    if _rich:
        _console.print("[dim]Files written:[/dim]")
        for dest in (EMAIL_MD, CALENDAR_MD, ACTIONS_MD, NOTES_MD, MASTER_LOG):
            if dest.exists():
                _console.print(f"  [cyan]{dest}[/cyan]")
