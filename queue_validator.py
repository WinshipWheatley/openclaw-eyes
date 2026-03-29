#!/usr/bin/env python3
"""
queue_validator.py — Check 04_Queues.md for rows appended outside tables.

Rows appended after the closing --- of a section land outside the markdown
table and are invisible to the Planner. This validator detects them.

Usage:
    python3 queue_validator.py [path_to_04_Queues.md]

Default path: ~/Eyes/04_Queues.md

Exit codes:
    0 — file is valid (no orphaned rows)
    1 — one or more orphaned rows found outside table boundaries
    2 — file not found or unreadable
"""

import sys
import os
import re

DEFAULT_PATH = os.path.expanduser("~/Eyes/04_Queues.md")


def find_orphaned_rows(lines: list) -> list:
    """
    Walk the file and return error strings for pipe rows found outside a table.

    State machine:
      - in_table: True while inside an open markdown table
      - after_rule: True after a --- horizontal rule closed a table;
                    resets when a new section header or new table opens

    A pipe row is orphaned when after_rule=True and in_table=False.
    """
    errors = []
    in_code_block = False
    in_table = False
    after_rule = False
    current_section = "(preamble)"

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")

        # Code block fence toggles — ignore content inside fences
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Section headers (##, ###, etc.) reset table state
        if re.match(r"^#{1,6}\s", line):
            current_section = line.strip()
            in_table = False
            after_rule = False
            continue

        # Horizontal rule (---, not |---|) closes the current table
        if re.match(r"^-{3,}\s*$", line):
            in_table = False
            after_rule = True
            continue

        # Pipe row
        if line.startswith("|"):
            if in_table:
                # Normal table row — no action needed
                pass
            elif after_rule:
                # Orphaned: we're past a --- and haven't opened a new table
                errors.append(
                    f"  Line {lineno} in [{current_section}]: "
                    f"row outside table (appended after ---)\n"
                    f"    {line[:100]}"
                )
                # Do not set in_table — keep flagging further orphaned rows
            else:
                # First pipe row in a section: opens a new table
                in_table = True
                after_rule = False
            continue

        # Non-pipe, non-blank content while in a table shouldn't happen in
        # well-formed markdown, but if it does, close the table defensively
        if line.strip() and in_table:
            in_table = False

    return errors


def validate(path: str) -> int:
    """Validate a single file. Returns 0 (ok), 1 (errors), or 2 (not found)."""
    path = os.path.expanduser(path)

    if not os.path.isfile(path):
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        return 2

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"ERROR: Cannot read {path}: {e}", file=sys.stderr)
        return 2

    print(f"Validating: {path}")
    errors = find_orphaned_rows(lines)

    if not errors:
        print(f"OK — {len(lines)} lines checked, no orphaned rows found.")
        return 0

    print(
        f"VALIDATION FAILED — {len(errors)} orphaned row(s) found outside table boundaries:"
    )
    for err in errors:
        print(err)
    print()
    print(
        "Fix: Move these rows inside the correct table, before the trailing ---."
    )
    return 1


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    sys.exit(validate(path))


if __name__ == "__main__":
    main()
