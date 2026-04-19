#!/usr/bin/env python3
"""inbox_parser.py — Automated inbox classifier and queue router for OpenClaw Eyes."""

import sys
import os
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chief_llm import ollama_json

HANDOFF_DIR = Path("/mnt/c/OpenClawShared/OpenClaw-Handoff")

FILLER_WORDS = frozenset({
    "a", "an", "the", "is", "to", "for", "and", "of", "in",
    "my", "that", "this", "it", "when", "what", "how",
})

# Section definitions for 04_Queues.md sections that may need to be created
_QUEUE_SECTIONS = {
    "feature": {
        "header": "## Feature Queue",
        "pattern": r"^## Feature",
        "table_header": "| ID | Title | Type | Priority | Winship | Bot | Notes | Queued By |",
        "separator":    "|---|---|---|---|---|---|---|---|",
    },
    "not_possible_now": {
        "header": "## Not Possible Now — Prerequisite Maps",
        "pattern": r"^## Not Possible Now",
        "table_header": "| ID | Title | Blocking Reason | Prerequisite Map |",
        "separator":    "|---|---|---|---|",
    },
    "complex_multi_step": {
        "header": "## Complex Multi-Step — Step Sequences",
        "pattern": r"^## Complex Multi-Step",
        "table_header": "| ID | Title | Summary | Steps |",
        "separator":    "|---|---|---|---|",
    },
}


# ── Env loading ───────────────────────────────────────────────────────────────

def load_env() -> None:
    env_path = Path.home() / ".chief.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            # Handle both "KEY=val" and "export KEY=val" formats
            if line.startswith("export "):
                line = line[len("export "):]
            k, v = line.split("=", 1)
            # Strip quotes from value if present
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Slug and ID generation ────────────────────────────────────────────────────

def make_slug(text: str) -> str:
    """First 3 meaningful words from text, lowercased, hyphenated."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    meaningful = [w for w in words if w not in FILLER_WORDS]
    return "-".join(meaningful[:3])


def make_id(date_str: str, source: str, slug: str) -> str:
    """Build entry id from date field, source, and slug."""
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M")
        date_part = dt.strftime("%Y-%m-%d-%H%M")
    except Exception:
        date_part = re.sub(r"[^0-9a-zA-Z-]", "-", date_str.strip()).strip("-")
    source_part = re.sub(r"[^a-z0-9]", "", (source or "unknown").strip().lower())
    return f"{date_part}-{source_part}-{slug}"


# ── Block parsing ─────────────────────────────────────────────────────────────

def parse_entry_fields(block: str) -> dict:
    """Parse YAML-like key: value fields from a block. text: may be multi-line."""
    lines = block.strip().splitlines()
    if lines and lines[0].strip() == "---":
        lines = lines[1:]
    if lines and lines[-1].strip() == "---":
        lines = lines[:-1]

    fields: dict = {}
    current_key = None
    current_val_lines: list = []

    for line in lines:
        m = re.match(r"^([a-zA-Z_][a-zA-Z_0-9]*):\s*(.*)", line)
        if m:
            if current_key is not None:
                fields[current_key] = "\n".join(current_val_lines).strip()
            current_key = m.group(1)
            rest = m.group(2).strip()
            current_val_lines = [rest] if rest else []
        else:
            if current_key is not None:
                current_val_lines.append(line)

    if current_key is not None:
        fields[current_key] = "\n".join(current_val_lines).strip()

    return fields


def set_field(block: str, key: str, value: str) -> str:
    """Replace the value of a single-line field in a block. Noop if field absent."""
    return re.sub(
        rf"^({re.escape(key)}:)\s*.*$",
        lambda m: f"{m.group(1)} {value}" if value else m.group(1),
        block,
        count=1,
        flags=re.MULTILINE,
    )


# ── Inbox parsing ─────────────────────────────────────────────────────────────

def find_unrouted_entries(content: str) -> list:
    """Return list of entry dicts for all unrouted entries in ## Active Inbox."""
    m = re.search(r"^## Active Inbox\s*$", content, re.MULTILINE)
    if not m:
        return []

    next_sec = re.search(r"^## ", content[m.end():], re.MULTILINE)
    active_end = m.end() + next_sec.start() if next_sec else len(content)
    active_section = content[m.start():active_end]

    entry_re = re.compile(r"(### [^\n]+\n+)(`{3,})\n(.*?)\2", re.DOTALL)
    entries = []
    for em in entry_re.finditer(active_section):
        heading = em.group(1).strip().lstrip("#").strip()
        block = em.group(3)
        fields = parse_entry_fields(block)
        if fields.get("status", "").strip() == "unrouted":
            entries.append({
                "heading": heading,
                "fence": em.group(2),
                "block": block,
                "fields": fields,
                "full_match": em.group(0),
            })
    return entries


# ── Queue ID helpers ──────────────────────────────────────────────────────────

def find_highest_id(content: str, prefix: str) -> int:
    """Return the highest NNN found for prefix-NNN in content, or 0."""
    nums = [int(m.group(1))
            for m in re.finditer(rf"\b{re.escape(prefix)}-(\d+)\b", content)]
    return max(nums, default=0)


# ── LLM classification ────────────────────────────────────────────────────────

def build_classify_prompt(fields: dict) -> str:
    text = fields.get("text", "").strip()
    return f"""Classify this idea for a software project task queue.

IDEA TEXT:
{text}

EXISTING SYSTEM CONTEXT:
- This is OpenClaw, a Telegram-based AI assistant for a music label (Deep Pocket Records)
- It has 40+ brain modules, runs on WSL/Ubuntu, uses Claude API + local Ollama
- Current capabilities: album management, billing, scheduling, marketing, calendar, email/SMS drafts

Classify as exactly ONE of:
- "dhp" — bug fix, performance improvement, logging fix, test addition, code cleanup, or improvement to something that already exists
- "feature" — new capability, new bot behavior, new integration, new brain
- "architecture" — structural change to how parts of the system connect
- "not_possible_now" — blocked by hardware, infrastructure, or permissions that don't exist yet
- "complex_multi_step" — possible but clearly requires 10+ ordered steps across multiple files/systems
- "hold" — vague, premature, or no clear action yet

Also score bot_confidence 1-5:
- Scope clarity: +2 (clear specific files/behavior) / +1 (mostly clear) / +0 (vague)
- Unblock value: +1 (unlocks other tasks) / +0 (standalone)
- Token cost ratio: +1 (targeted edit, low cost) / +0 (broad refactor)
- Test safety: +1 (clear test mode) / +0 (no clear test)

Return JSON only:
{{"classification": "dhp|feature|architecture|not_possible_now|complex_multi_step|hold", "bot_confidence": N, "router_note": "one-line reasoning", "suggested_title": "short task title", "suggested_priority": "high|medium|low", "suggested_type": "debug|harden|polish|feature|architecture"}}
"""


# ── File mutation helpers ─────────────────────────────────────────────────────

def append_row_to_section(content: str, pattern: str, row: str,
                           create_header: str = None,
                           create_table_header: str = None,
                           create_separator: str = None) -> str:
    """Find section by pattern, append row to its last table line.

    If section is missing and create_* args are provided, creates it first.
    """
    m = re.search(pattern, content, re.MULTILINE)
    if not m and create_header:
        content = (
            content.rstrip()
            + f"\n\n{create_header}\n\n{create_table_header}\n{create_separator}\n"
        )
        m = re.search(pattern, content, re.MULTILINE)
    if not m:
        return content

    section_start = m.end()
    next_sec = re.search(r"^## ", content[section_start:], re.MULTILINE)
    section_end = section_start + next_sec.start() if next_sec else len(content)
    section = content[section_start:section_end]

    lines = section.splitlines(keepends=True)
    last_table_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            last_table_idx = i

    if last_table_idx >= 0:
        lines.insert(last_table_idx + 1, row + "\n")
    else:
        lines.append("\n" + row + "\n")

    return content[:section_start] + "".join(lines) + content[section_end:]


def remove_entry_from_active(inbox: str, full_match: str) -> str:
    """Remove an entry block from Active Inbox and clean up excess blank lines."""
    result = inbox.replace(full_match, "", 1)
    return re.sub(r"\n{3,}", "\n\n", result)


def append_classified_queue_row(
    queues: str,
    classification: str,
    queue_id: str | None,
    suggested_title: str,
    suggested_type: str,
    suggested_priority: str,
    bot_confidence: int,
    router_note: str,
) -> str:
    """Append the queue row for a classified entry to in-memory queue content."""
    if not queue_id:
        return queues

    if classification == "dhp":
        row = (f"| {queue_id} | {suggested_title} | {suggested_type} "
               f"| {suggested_priority} | — | {bot_confidence} "
               f"| {router_note} | inbox-parser | unassigned |")
        return append_row_to_section(queues, r"^### Candidates", row)

    if classification in ("feature", "architecture"):
        row = (f"| {queue_id} | {suggested_title} | {suggested_type} "
               f"| {suggested_priority} | — | {bot_confidence} "
               f"| {router_note} | inbox-parser |")
        sec = _QUEUE_SECTIONS["feature"]
        return append_row_to_section(
            queues, sec["pattern"], row,
            create_header=sec["header"],
            create_table_header=sec["table_header"],
            create_separator=sec["separator"],
        )

    if classification == "not_possible_now":
        row = f"| {queue_id} | {suggested_title} | {router_note} | [prerequisites TBD] |"
        sec = _QUEUE_SECTIONS["not_possible_now"]
        return append_row_to_section(
            queues, sec["pattern"], row,
            create_header=sec["header"],
            create_table_header=sec["table_header"],
            create_separator=sec["separator"],
        )

    if classification == "complex_multi_step":
        row = f"| {queue_id} | {suggested_title} | {router_note} | [steps TBD] |"
        sec = _QUEUE_SECTIONS["complex_multi_step"]
        return append_row_to_section(
            queues, sec["pattern"], row,
            create_header=sec["header"],
            create_table_header=sec["table_header"],
            create_separator=sec["separator"],
        )

    return queues


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Classify and route OpenClaw inbox entries to the correct queue."
    )
    ap.add_argument("--dir", default=str(HANDOFF_DIR),
                    help="Directory containing 03_Inbox.md and 04_Queues.md")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print planned actions without writing any files")
    args = ap.parse_args()

    load_env()

    work_dir = Path(args.dir)
    inbox_path = work_dir / "03_Inbox.md"
    queues_path = work_dir / "04_Queues.md"
    log_path = work_dir / "parser.log"

    for p in (inbox_path, queues_path):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(1)

    inbox = inbox_path.read_text()
    queues = queues_path.read_text()

    entries = find_unrouted_entries(inbox)
    if not entries:
        print("Inbox empty — nothing to route")
        sys.exit(0)

    print(f"Found {len(entries)} unrouted entr{'y' if len(entries) == 1 else 'ies'}.")

    log_lines: list = []
    updated_inbox = inbox
    updated_queues = queues

    for entry in entries:
        fields = entry["fields"]
        text = fields.get("text", "").strip()
        source = fields.get("source", "unknown")
        date_str = fields.get("date", "")

        slug = make_slug(text)
        entry_id = fields.get("id", "").strip()
        if not entry_id or entry_id.startswith("[generated:"):
            entry_id = make_id(date_str, source, slug)

        print(f"\nEntry: {entry['heading']} → {entry_id}")

        result = ollama_json(
            build_classify_prompt(fields),
            timeout=30,
            task_class="chief_structured_plan",
        )
        if not result:
            print("  [SKIP] LLM classification failed")
            log_lines.append(f"[{ts()}] SKIP: {entry_id} — LLM classification failed")
            continue

        classification = result.get("classification", "hold")
        bot_confidence = result.get("bot_confidence", 0)
        router_note = result.get("router_note", "")
        suggested_title = result.get("suggested_title", entry["heading"])
        suggested_priority = result.get("suggested_priority", "medium")
        suggested_type = result.get("suggested_type", "feature")

        # Assign queue ID based on current queues content (tracks prior iterations)
        if classification == "dhp":
            queue_id = f"dhp-{find_highest_id(updated_queues, 'dhp') + 1:03d}"
            new_status = "routed"
        elif classification in ("feature", "architecture"):
            queue_id = f"feat-{find_highest_id(updated_queues, 'feat') + 1:03d}"
            new_status = "routed"
        elif classification == "not_possible_now":
            queue_id = f"npl-{find_highest_id(updated_queues, 'npl') + 1:03d}"
            new_status = "not-possible-now"
        elif classification == "complex_multi_step":
            queue_id = f"cms-{find_highest_id(updated_queues, 'cms') + 1:03d}"
            new_status = "routed"
        else:  # hold
            queue_id = None
            new_status = "hold"

        print(f"  classification: {classification} | queue_id: {queue_id} | status: {new_status}")
        print(f"  router_note: {router_note}")

        updated_queues = append_classified_queue_row(
            updated_queues,
            classification,
            queue_id,
            suggested_title,
            suggested_type,
            suggested_priority,
            bot_confidence,
            router_note,
        )

        if args.dry_run:
            print("  [DRY-RUN] No files modified.")
            continue

        # ── Update entry block fields ─────────────────────────────────────────
        updated_block = entry["block"]
        for key, val in [
            ("id", entry_id),
            ("status", new_status),
            ("bot_confidence", str(bot_confidence)),
            ("router_note", router_note),
            ("routed_to", queue_id or ""),
        ]:
            updated_block = set_field(updated_block, key, val)

        # ── Update 03_Inbox.md ────────────────────────────────────────────────
        if new_status in ("routed", "not-possible-now"):
            # Remove from Active Inbox
            updated_inbox = remove_entry_from_active(updated_inbox, entry["full_match"])
            # Add row to Routed table
            summary = text.replace("\n", " ")
            if len(summary) > 60:
                summary = summary[:60] + "..."
            tags = fields.get("tags", "").strip() or "—"
            date_today = datetime.now().strftime("%Y-%m-%d")
            routed_row = (f"| {entry_id} | {summary} | {tags} "
                          f"| {queue_id or '—'} | inbox-parser | {date_today} |")
            updated_inbox = append_row_to_section(
                updated_inbox, r"^## Routed\s*$", routed_row
            )
        else:  # hold — update fields in place, keep in Active Inbox
            new_full = entry["full_match"].replace(entry["block"], updated_block, 1)
            updated_inbox = updated_inbox.replace(entry["full_match"], new_full, 1)

        log_lines.append(
            f"[{ts()}] PARSED: {entry_id} → {classification}/{queue_id} ({router_note})"
        )

    if args.dry_run:
        print("\n[DRY-RUN] No files were written.")
        sys.exit(0)

    # ── Write outputs ─────────────────────────────────────────────────────────
    inbox_path.write_text(updated_inbox)
    queues_path.write_text(updated_queues)
    with open(log_path, "a") as f:
        for line in log_lines:
            f.write(line + "\n")

    print(f"\nWrote: {inbox_path}")
    print(f"Wrote: {queues_path}")
    print(f"Logged {len(log_lines)} line(s) to {log_path}")


if __name__ == "__main__":
    main()
