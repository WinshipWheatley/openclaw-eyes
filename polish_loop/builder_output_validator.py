#!/usr/bin/env python3
"""builder_output_validator.py — Validate pc_output.md format and content.

Called by builder_watcher.sh after each runner invocation to detect:
  - Missing output file
  - Empty output
  - Missing PASS: header (quota messages, CLI errors, raw stdout)
  - Known quota / rate-limit indicators in the first 400 characters

Exit codes (CLI): 0 = valid, 1 = invalid
Stdout: reason string — one of:
    "ok"              valid output, loop may advance
    "missing"         pc_output.md does not exist
    "empty"           file exists but is empty or whitespace-only
    "no_pass_line"    first non-RUNNER: line is not PASS:
    "quota_message"   quota / rate-limit text detected near the top
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Patterns that indicate a runner quota or overload response rather than
# real builder output.  Only scanned in the first 400 bytes so a normal
# pc_output that happens to say "quota" in CONCERNS: won't false-positive.
_QUOTA_RE = re.compile(
    r"quota|rate.?limit|exceeded|too many requests|overloaded|"
    r"service unavailable|temporarily unavailable",
    re.IGNORECASE,
)


def validate(path: "str | Path") -> "tuple[bool, str]":
    """Return (ok, reason).

    ok=True and reason="ok" means the file is structurally valid.
    Any other return means the file should be treated as invalid output
    and the watcher should attempt a fallback runner.
    """
    p = Path(path)

    if not p.exists():
        return False, "missing"

    try:
        content = p.read_text()
    except Exception as exc:
        return False, f"unreadable:{exc}"

    if not content.strip():
        return False, "empty"

    lines = content.splitlines()
    first = lines[0].strip() if lines else ""

    # Allow optional RUNNER: prefix line (written by builder_watcher.sh)
    if first.upper().startswith("RUNNER:"):
        if len(lines) < 2:
            return False, "no_pass_line"
        first = lines[1].strip()

    if not first.upper().startswith("PASS:"):
        # Check whether the content looks like a quota / error response
        if _QUOTA_RE.search(content[:400]):
            return False, "quota_message"
        return False, "no_pass_line"

    # Also check whether the top of an otherwise well-formed file was prefixed
    # with a quota blurb before the PASS: line was written.
    header_region = "\n".join(lines[:5])
    if _QUOTA_RE.search(header_region):
        return False, "quota_message"

    return True, "ok"


def validate_candidate_evidence(path: "str | Path") -> "tuple[bool, str]":
    """Validate the builder-owned evidence before the ledger runs acceptance.

    This remains a structural check only. Phase-C DONE is decided by
    `control_plane.ControlPlaneLedger.decide_acceptance()`, which combines this
    evidence check with the immutable acceptance ref and `green_gate.sh`.
    """
    ok, reason = validate(path)
    if not ok:
        return ok, reason
    content = Path(path).read_text()
    if re.search(r"^\s*STATUS:\s*BLOCKED\s*$", content, re.IGNORECASE | re.MULTILINE):
        return False, "candidate_blocked"
    return True, "ok"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: builder_output_validator.py <pc_output_path>", file=sys.stderr)
        sys.exit(2)

    ok, reason = validate(sys.argv[1])
    print(reason)
    sys.exit(0 if ok else 1)
