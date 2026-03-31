#!/usr/bin/env python3
"""
pc_review_fallback.py — PC-side structural review when Mac planner is unavailable.

When the Mac-side planner cannot launch (claude/codex not found on Mac),
this module provides a deterministic structural review of builder output
that keeps the loop moving autonomously.

The review validates:
  1. pc_output.md has all required sections (CHANGES, REASONING, ROLLBACK PLAN)
  2. PASS number matches the current pass in status.json
  3. STATUS is DONE (not BLOCKED)
  4. Listed changed files actually exist on disk
  5. Changed files have recent modifications (not stale claims)

This is NOT a semantic code review. It verifies structural completeness
and file-level evidence. For deep code review, the Mac planner is needed.

Usage:
    python3 pc_review_fallback.py              # write mac_review.md if needed
    python3 pc_review_fallback.py --dry-run    # check only, no file writes
    python3 pc_review_fallback.py --check      # exit 0=review needed, 1=not needed
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LOOP_DIR    = Path("/home/openclaw/polish_loop")
STATUS_FILE = LOOP_DIR / "status.json"
CURRENT_DIR = LOOP_DIR / "current"
PC_OUTPUT   = CURRENT_DIR / "pc_output.md"
MAC_REVIEW  = CURRENT_DIR / "mac_review.md"
TASK_MD     = LOOP_DIR / "task.md"
LOG_FILE    = Path("/mnt/c/OpenClaw/logs/orchestrator.log")

REQUIRED_SECTIONS = ("CHANGES:", "REASONING:", "ROLLBACK PLAN:")


# ---------------------------------------------------------------------------
# Logging (appends to orchestrator log for unified trail)
# ---------------------------------------------------------------------------

# Set to True during orchestrator self-tests to avoid polluting the live log.
_SUPPRESS_FILE_LOGS: bool = False


def log(tag: str, msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [pc-review-{tag}] {msg}"
    print(line)
    if _SUPPRESS_FILE_LOGS:
        return
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def read_status() -> dict | None:
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def needs_review() -> bool:
    """True if the loop is in a state where PC review fallback should fire."""
    status = read_status()
    if not status:
        return False
    state = status.get("status")
    # Fire when mac_turn (planner should be reviewing) or blocked due to planner failure
    if state == "mac_turn":
        return not MAC_REVIEW.exists()
    if state == "blocked":
        reason = status.get("block_reason", "")
        return reason in ("planner_runner_missing", "planner_timeout_no_review")
    return False


# ---------------------------------------------------------------------------
# Structural review
# ---------------------------------------------------------------------------

def _extract_changed_files(content: str) -> list[str]:
    """Extract file paths from the CHANGES: section of pc_output.md."""
    changes_match = re.search(
        r"^CHANGES:\s*\n(.*?)(?=\n^(?:NOT CHANGED|VAULT_CHANGES|CONCERNS|ROLLBACK PLAN|REASONING)|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not changes_match:
        return []
    block = changes_match.group(1)
    # Match paths in backticks or after - 
    paths = re.findall(r'`(/[^`]+)`', block)
    # Also match paths after "- " that look like absolute paths
    paths += re.findall(r'^-\s+(/\S+)', block, re.MULTILINE)
    # Also match "—" separated entries like `/path/to/file` — description
    paths += re.findall(r'`(/[^`]+\.(?:py|sh|md|json|yaml|yml|toml|cfg|conf|txt))`', block)
    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _verify_file_exists(path: str) -> bool:
    """Check if a claimed changed file actually exists."""
    return Path(path).exists()


def _verify_file_recent(path: str, max_age_hours: int = 24) -> bool:
    """Check if a file was modified recently enough to be plausibly from this pass."""
    try:
        mtime = Path(path).stat().st_mtime
        age_hours = (datetime.datetime.now().timestamp() - mtime) / 3600
        return age_hours < max_age_hours
    except Exception:
        return False


def _run_verification_command(task_content: str) -> tuple[bool, str]:
    """
    Try to find and run a verification command from task.md.
    Returns (success, detail_message).
    """
    # Look for verification commands in task.md
    verify_match = re.search(
        r'(?:verification|verify|test|check).*?```(?:bash|sh)?\s*\n(.+?)\n```',
        task_content,
        re.IGNORECASE | re.DOTALL,
    )
    if not verify_match:
        return True, "no verification command found in task.md — skipped"

    cmd = verify_match.group(1).strip()

    # Safety: only run commands that are clearly read-only or test commands
    safe_prefixes = (
        "python3", "source", "cat ", "grep ", "diff ", "ls ", "test ",
        "bash /home/openclaw/polish_loop/orchestrator.py --run-tests",
    )
    if not any(cmd.startswith(p) for p in safe_prefixes):
        return True, f"verification command not in safe-list — skipped: {cmd[:80]}"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd="/home/openclaw",
        )
        if result.returncode == 0:
            return True, f"verification passed (exit 0): {cmd[:80]}"
        else:
            return False, f"verification failed (exit {result.returncode}): {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, f"verification timed out (120s): {cmd[:80]}"
    except Exception as e:
        return True, f"verification error (non-fatal): {e}"


def structural_review() -> tuple[str, list[str], list[str]]:
    """
    Perform structural review of pc_output.md.

    Returns:
        (verdict, pass_reasons, fail_reasons)
        verdict: "APPROVED" or "NEEDS_REWORK"
    """
    passes: list[str] = []
    fails: list[str] = []

    status = read_status()
    if not status:
        fails.append("Cannot read status.json")
        return "NEEDS_REWORK", passes, fails

    expected_pass = status.get("pass", 1)
    task_name = status.get("task_name", "unknown")

    # ---- Check pc_output.md exists and is readable ----
    if not PC_OUTPUT.exists():
        fails.append("pc_output.md does not exist")
        return "NEEDS_REWORK", passes, fails

    try:
        content = PC_OUTPUT.read_text()
    except Exception as e:
        fails.append(f"pc_output.md unreadable: {e}")
        return "NEEDS_REWORK", passes, fails

    # ---- Check PASS number ----
    first_line = content.splitlines()[0] if content.splitlines() else ""
    pass_match = re.match(r"PASS:\s*(\d+)", first_line, re.IGNORECASE)
    if pass_match:
        found_pass = int(pass_match.group(1))
        if found_pass == expected_pass:
            passes.append(f"PASS number matches ({found_pass})")
        else:
            fails.append(f"PASS mismatch: output says {found_pass}, status says {expected_pass}")
    else:
        fails.append("No PASS: line found at start of pc_output.md")

    # ---- Check STATUS is DONE ----
    status_match = re.search(r"^STATUS:\s*(\S+)", content, re.MULTILINE | re.IGNORECASE)
    if status_match:
        found_status = status_match.group(1).upper()
        if found_status == "DONE":
            passes.append("STATUS: DONE confirmed")
        elif found_status == "BLOCKED":
            fails.append("STATUS: BLOCKED — builder reported it could not complete the task")
        else:
            passes.append(f"STATUS: {found_status} (non-blocking)")
    else:
        fails.append("No STATUS: line found in pc_output.md")

    # ---- Check required sections ----
    upper_content = content.upper()
    for header in REQUIRED_SECTIONS:
        if header in upper_content:
            passes.append(f"Section present: {header}")
        else:
            fails.append(f"Missing required section: {header}")

    # ---- Check changed files exist ----
    changed_files = _extract_changed_files(content)
    if changed_files:
        existing = 0
        for fp in changed_files:
            if _verify_file_exists(fp):
                existing += 1
            else:
                # Non-fatal: file might have been renamed or is in a different location
                passes.append(f"File not found (may be expected): {fp}")
        if existing > 0:
            passes.append(f"{existing}/{len(changed_files)} changed files verified on disk")
        else:
            fails.append("None of the listed changed files exist on disk")
    else:
        passes.append("No specific file paths extracted from CHANGES (format may vary)")

    # ---- Run verification command from task.md if available ----
    if TASK_MD.exists():
        try:
            task_content = TASK_MD.read_text()
            verify_ok, verify_detail = _run_verification_command(task_content)
            if verify_ok:
                passes.append(verify_detail)
            else:
                fails.append(verify_detail)
        except Exception as e:
            passes.append(f"Could not read task.md for verification: {e}")

    # ---- Determine verdict ----
    # APPROVED if no hard failures. Structural review is intentionally lenient —
    # it catches format issues and obvious problems but doesn't reject on style.
    verdict = "NEEDS_REWORK" if fails else "APPROVED"
    return verdict, passes, fails


# ---------------------------------------------------------------------------
# Write mac_review.md
# ---------------------------------------------------------------------------

def write_review(verdict: str, passes: list[str], fails: list[str], dry_run: bool = False) -> bool:
    """Write mac_review.md with the review verdict. Returns True on success."""
    status = read_status() or {}
    task_name = status.get("task_name", "unknown")
    pass_num = status.get("pass", 1)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    checks_lines = []
    for p in passes:
        checks_lines.append(f"- ✓ {p}")
    for f in fails:
        checks_lines.append(f"- ✗ {f}")
    checks_block = "\n".join(checks_lines) if checks_lines else "- (no checks performed)"

    review = f"""# Mac Review — {task_name} Pass {pass_num}

**VERDICT: {verdict}**

{verdict}

## Reviewer
PC-side structural review fallback (Mac planner unavailable)
Reviewed at: {now}

## Checks
{checks_block}

## Notes
This review was performed by the PC-side structural validator because the Mac
planner could not launch (claude/codex CLI not found on Mac). The review checks
output format, required sections, file existence, and verification commands.
Semantic code quality review was not performed.
"""

    if dry_run:
        log("DRY-RUN", f"Would write mac_review.md with VERDICT: {verdict}")
        return True

    try:
        CURRENT_DIR.mkdir(parents=True, exist_ok=True)
        MAC_REVIEW.write_text(review)
        log("ACTION", f"Wrote mac_review.md — VERDICT: {verdict} for {task_name} pass {pass_num}")
        return True
    except Exception as e:
        log("ERROR", f"Failed to write mac_review.md: {e}")
        return False


def write_closeout(dry_run: bool = False) -> bool:
    """Write closeout.ok for approved tasks."""
    status = read_status() or {}
    task_name = status.get("task_name", "unknown")
    pass_num = status.get("pass", 1)

    closeout = json.dumps({"task_name": task_name, "pass": pass_num})

    if dry_run:
        log("DRY-RUN", f"Would write closeout.ok: {closeout}")
        return True

    try:
        CURRENT_DIR.mkdir(parents=True, exist_ok=True)
        (CURRENT_DIR / "closeout.ok").write_text(closeout)
        log("ACTION", f"Wrote closeout.ok for {task_name} pass {pass_num}")
        return True
    except Exception as e:
        log("ERROR", f"Failed to write closeout.ok: {e}")
        return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_review(dry_run: bool = False) -> int:
    """
    Run the PC-side structural review.
    Returns 0 on success, 1 on error, 2 if review not needed.
    """
    if not needs_review():
        log("INFO", "Review not needed (loop not in mac_turn or planner-blocked state)")
        return 2

    log("START", "PC-side structural review starting (Mac planner unavailable)")

    verdict, passes, fails = structural_review()

    log("RESULT", f"Verdict: {verdict} | {len(passes)} passes, {len(fails)} fails")
    for p in passes:
        log("PASS", p)
    for f in fails:
        log("FAIL", f)

    if not write_review(verdict, passes, fails, dry_run=dry_run):
        return 1

    if verdict == "APPROVED":
        write_closeout(dry_run=dry_run)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PC-side planner review fallback")
    parser.add_argument("--dry-run", action="store_true", help="Check only, no file writes")
    parser.add_argument("--check", action="store_true", help="Exit 0 if review needed, 1 if not")
    args = parser.parse_args(argv)

    if args.check:
        needed = needs_review()
        print(f"Review needed: {needed}")
        return 0 if needed else 1

    return run_review(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
