#!/usr/bin/env python3
"""Queue Balancer — keeps the task queue healthy with a mix of tiers.

Problem: if the queue is all architect/standard tasks, gemini and codex have
no appropriate work.  If it's all quick tasks, claude is wasted on trivial stuff.

Solution: periodically scan the queue, estimate the tier mix, and generate
useful filler tasks from known "easy win" sources when a tier is under-
represented.  This ensures every runner always has appropriate work.

Easy-win sources (quick/surgical):
  - Missing unit tests for production modules
  - Dead imports / unused code cleanup
  - Docstring gaps in public functions
  - Config validation hardening
  - Cassandra capability flag checks

Run modes:
  python3 queue_balancer.py              # dry-run: show what would be generated
  python3 queue_balancer.py --apply      # generate task files into the queue
  python3 queue_balancer.py --status     # show current queue tier breakdown

Designed to be called from loop_supervisor.sh or cron.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TASK_QUEUE = Path("/home/openclaw/polish_loop/tasks")
ARCHIVE_DIR = Path("/home/openclaw/polish_loop/archive")
STATUS_FILE = Path("/home/openclaw/polish_loop/status.json")
SRC_DIR = Path("/home/openclaw")
TEST_DIR = Path("/home/openclaw/tests")
LOG_FILE = Path("/mnt/c/OpenClaw/logs/queue_balancer.log")

SKIP_TASK_NAMES = {"env-001-install.md", "env-001-spec-tools.md"}

# ---------------------------------------------------------------------------
# Target tier ratios — what a healthy queue looks like
# ---------------------------------------------------------------------------

# For every 6 tasks in the queue, we want roughly:
#   2 quick/surgical  (gemini/codex territory)
#   3 standard        (claude/gemini split via rotation)
#   1 architect       (claude-only)
#
# If quick+surgical < 1/3 of queue, generate easy tasks.
# If architect < 1 and queue has 4+ tasks, that's fine — architect tasks
# come from planning, not auto-generation.

MIN_EASY_RATIO = 0.25   # at least 25% of queue should be quick/surgical
MAX_GENERATE = 3         # never generate more than 3 tasks at once
COOLDOWN_HOURS = 4       # don't re-generate within this window

COOLDOWN_FILE = Path("/home/openclaw/.queue_balancer_last_run")

# ---------------------------------------------------------------------------
# Completed-task tracking (avoid regenerating finished work)
# ---------------------------------------------------------------------------

def _get_completed_names() -> set[str]:
    """Get set of task names already completed (from archive)."""
    completed: set[str] = set()
    if ARCHIVE_DIR.exists():
        for archived in ARCHIVE_DIR.glob("task_*"):
            parts = archived.stem.split("_", 1)
            if len(parts) > 1:
                name_part = parts[1].rsplit("_", 1)[0]
                completed.add(name_part)
        for closeout in ARCHIVE_DIR.glob("closeout_*"):
            parts = closeout.stem.split("_", 1)
            if len(parts) > 1:
                name_part = parts[1].rsplit("_", 1)[0]
                completed.add(name_part)
    return completed


def _get_queued_names() -> set[str]:
    """Get set of task names currently in queue."""
    names: set[str] = set()
    if TASK_QUEUE.exists():
        for f in TASK_QUEUE.glob("*.md"):
            if f.name not in SKIP_TASK_NAMES:
                names.add(f.stem)
    # Also include active task
    if STATUS_FILE.exists():
        try:
            status = json.loads(STATUS_FILE.read_text())
            tn = status.get("task_name", "")
            if tn:
                names.add(tn)
        except Exception:
            pass
    return names


# ---------------------------------------------------------------------------
# Tier estimation (reuses runner_profiles heuristics)
# ---------------------------------------------------------------------------

def estimate_tier(task_text: str) -> str:
    """Rough tier estimation from task text."""
    try:
        from runner_profiles import _parse_frontmatter, _count_files, _scope_size
        from runner_profiles import ARCHITECT_KEYWORDS, QUICK_KEYWORDS, SURGICAL_KEYWORDS
        meta = _parse_frontmatter(task_text)

        explicit = meta.get("profile", "").strip().lower()
        if explicit in ("quick", "surgical", "standard", "architect"):
            return explicit

        file_count = _count_files(meta)
        scope_count = _scope_size(meta)

        if file_count >= 6 or scope_count >= 8:
            return "architect"

        text = " ".join([
            str(meta.get("title", "")),
            str(meta.get("goal", "")),
            str(meta.get("scope", "")),
        ]).lower()

        if any(kw in text for kw in ARCHITECT_KEYWORDS):
            return "architect"
        if any(kw in text for kw in SURGICAL_KEYWORDS) and scope_count <= 4:
            return "surgical"
        if (file_count <= 1 and scope_count <= 2) or any(kw in text for kw in QUICK_KEYWORDS):
            return "quick"
        return "standard"
    except Exception:
        return "standard"


def get_queue_breakdown() -> dict[str, list[str]]:
    """Get current queue contents grouped by estimated tier."""
    breakdown: dict[str, list[str]] = {
        "quick": [], "surgical": [], "standard": [], "architect": [],
    }
    if not TASK_QUEUE.exists():
        return breakdown

    for f in sorted(TASK_QUEUE.glob("*.md")):
        if f.name in SKIP_TASK_NAMES:
            continue
        try:
            text = f.read_text()
            tier = estimate_tier(text)
            breakdown[tier].append(f.stem)
        except Exception:
            breakdown["standard"].append(f.stem)

    return breakdown


# ---------------------------------------------------------------------------
# Easy-win task generators
# ---------------------------------------------------------------------------

@dataclass
class TaskCandidate:
    """A potential task to add to the queue."""
    name: str
    tier: str       # quick or surgical
    title: str
    goal: str
    scope: list[str]
    success: str
    source: str     # which generator produced this


def _gen_missing_tests() -> list[TaskCandidate]:
    """Find production modules without test files."""
    candidates = []
    completed = _get_completed_names()
    queued = _get_queued_names()

    # Modules worth testing (high-value, pure logic, no external deps)
    test_worthy = [
        ("runner_profiles", "runner_profiles.py",
         "Write unit tests for runner_profiles.py tier detection and profile selection",
         ["Test _parse_frontmatter() with various YAML-ish inputs",
          "Test select_profile() returns correct tier for quick/surgical/standard/architect keywords",
          "Test _count_files() and _scope_size() with edge cases",
          "Test _task_is_sensitive() with sensitive keywords and flags",
          "Test _should_gemini_take_this() ratio logic"],
         "All tests pass, cover the main selection paths"),
        ("budget_tracker", "budget_tracker.py",
         "Write unit tests for budget_tracker spend recording and budget zones",
         ["Test record_spend() correctly updates state",
          "Test get_budget_status() returns correct zone colors",
          "Test get_runner_allowance() respects daily caps",
          "Test stuck_loop detection after consecutive failures"],
         "All tests pass, cover spend tracking and zone logic"),
        ("runner_registry", "runner_registry.py",
         "Write unit tests for runner_registry scoring and discovery",
         ["Test _score_runner_for_task() produces expected rankings per tier",
          "Test get_runners_for_task() returns runners in score order",
          "Test Runner.supports_flag() and get_flag() methods"],
         "All tests pass, scoring produces correct tier winners"),
        ("dashboard_gen", "dashboard_gen.py",
         "Write unit tests for dashboard_gen data collection functions",
         ["Test get_runner_settings() returns valid JSON for both planner and builder",
          "Test gen_right_now() produces markdown with key sections",
          "Test output file generation doesn't crash on missing data"],
         "All tests pass, dashboard renders without errors"),
        ("pii_vault", "pii_vault.py",
         "Write unit tests for pii_vault encryption and decryption",
         ["Test encrypt/decrypt roundtrip with known key",
          "Test key generation produces valid Fernet key",
          "Test handling of missing or invalid key"],
         "All tests pass, encryption roundtrip verified"),
        ("brain_dump_parser", "brain_dump_parser.py",
         "Write unit tests for brain_dump_parser extraction logic",
         ["Test parse() with single and multi-section brain dumps",
          "Test extraction of action items from freeform text",
          "Test edge cases: empty input, missing sections"],
         "All tests pass, parsing produces structured output"),
        ("queue_validator", "queue_validator.py",
         "Write unit tests for queue_validator task validation",
         ["Test validation catches missing required fields",
          "Test validation accepts well-formed task files",
          "Test edge cases: empty files, malformed frontmatter"],
         "All tests pass, validator catches bad tasks"),
    ]

    for module_name, filename, goal, scope, success in test_worthy:
        task_name = f"test-{module_name}"
        if task_name in completed or task_name in queued:
            continue
        if not (SRC_DIR / filename).exists():
            continue
        # Check if test already exists
        test_exists = (
            (TEST_DIR / f"test_{module_name}.py").exists()
            or (SRC_DIR / f"test_{module_name}.py").exists()
        )
        if test_exists:
            continue

        candidates.append(TaskCandidate(
            name=task_name,
            tier="surgical",
            title=task_name,
            goal=goal,
            scope=scope + [f"Create tests/test_{module_name}.py"],
            success=success,
            source="missing_tests",
        ))

    return candidates


def _gen_config_hardening() -> list[TaskCandidate]:
    """Generate tasks for config validation and safety improvements."""
    candidates = []
    completed = _get_completed_names()
    queued = _get_queued_names()

    hardening_tasks = [
        ("harden-env-validation", "quick",
         "Add .chief.env validation at startup",
         ["Add a validate_env() function to start_chief.sh that checks all required env vars are set",
          "Required vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PII_VAULT_KEY",
          "Exit with clear error message if any are missing"],
         "start_chief.sh exits cleanly with helpful message when env vars missing"),
        ("harden-task-frontmatter", "quick",
         "Add frontmatter validation when tasks are loaded by orchestrator",
         ["In orchestrator.py handle_idle(), validate promoted task has title: and goal: fields",
          "Log a warning and skip invalid tasks instead of promoting them",
          "Write a brief skip reason to the log"],
         "Orchestrator skips malformed tasks with a log message instead of crashing"),
        ("cleanup-stale-imports", "quick",
         "Remove unused imports from production Python files",
         ["Scan chief_*.py and cassandra_*.py files for unused imports",
          "Remove imports that are not referenced in the file body",
          "Do not touch imports guarded by try/except or TYPE_CHECKING blocks"],
         "All modified files still import correctly and pass syntax check"),
    ]

    for name, tier, goal, scope, success in hardening_tasks:
        if name in completed or name in queued:
            continue
        candidates.append(TaskCandidate(
            name=name, tier=tier, title=name,
            goal=goal, scope=scope, success=success,
            source="config_hardening",
        ))

    return candidates


def _gen_doc_and_quality() -> list[TaskCandidate]:
    """Generate documentation and code quality tasks."""
    candidates = []
    completed = _get_completed_names()
    queued = _get_queued_names()

    quality_tasks = [
        ("doc-runner-pipeline", "quick",
         "Add inline documentation to the runner selection pipeline",
         ["Add module-level docstring to runner_registry.py explaining discovery flow",
          "Add docstring to _score_runner_for_task explaining the scoring philosophy",
          "Document the quick→gemini, surgical→codex/claude, standard→2:1, architect→claude mapping"],
         "Pipeline documentation is clear for future maintainers"),
        ("fix-log-rotation", "quick",
         "Add log rotation to prevent log files from growing unbounded",
         ["builder_watcher.log, orchestrator.log, and watcher.log grow forever",
          "Add a rotate_log() function that truncates when log exceeds 1MB",
          "Call rotate_log() at the start of each watcher cycle"],
         "Log files stay under 1MB with rotation"),
        ("validate-status-transitions", "surgical",
         "Add status transition validation to orchestrator",
         ["In orchestrator.py _write_status_raw(), validate the new status is in the allowed set",
          "Log invalid transitions instead of silently writing bad state",
          "Reference STATE_MACHINE.md for valid states: idle, pc_turn, mac_turn, approved, blocked, parked"],
         "Invalid status transitions are caught and logged"),
    ]

    for name, tier, goal, scope, success in quality_tasks:
        if name in completed or name in queued:
            continue
        candidates.append(TaskCandidate(
            name=name, tier=tier, title=name,
            goal=goal, scope=scope, success=success,
            source="doc_and_quality",
        ))

    return candidates


# ---------------------------------------------------------------------------
# Balancer logic
# ---------------------------------------------------------------------------

def _log(msg: str):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [queue_balancer] {msg}\n")
    except Exception:
        pass


def _check_cooldown() -> bool:
    """Return True if we're still in cooldown (generated recently)."""
    if COOLDOWN_FILE.exists():
        try:
            last_ts = float(COOLDOWN_FILE.read_text().strip())
            hours_ago = (time.time() - last_ts) / 3600
            if hours_ago < COOLDOWN_HOURS:
                return True
        except Exception:
            pass
    return False


def _set_cooldown():
    """Mark that we just generated tasks."""
    try:
        COOLDOWN_FILE.write_text(str(time.time()))
    except Exception:
        pass


def balance_queue(dry_run: bool = True) -> list[TaskCandidate]:
    """Check queue balance and generate filler tasks if needed.

    Returns list of tasks that were (or would be) generated.
    """
    breakdown = get_queue_breakdown()
    total = sum(len(v) for v in breakdown.values())
    easy_count = len(breakdown["quick"]) + len(breakdown["surgical"])

    _log(f"Queue: {total} tasks — quick={len(breakdown['quick'])}, "
         f"surgical={len(breakdown['surgical'])}, standard={len(breakdown['standard'])}, "
         f"architect={len(breakdown['architect'])}")

    if total == 0:
        _log("Queue empty — nothing to balance")
        return []

    easy_ratio = easy_count / total if total > 0 else 0
    if easy_ratio >= MIN_EASY_RATIO:
        _log(f"Queue balanced: {easy_ratio:.0%} easy (>= {MIN_EASY_RATIO:.0%} target)")
        return []

    # Need more easy tasks
    deficit = max(1, round(total * MIN_EASY_RATIO) - easy_count)
    deficit = min(deficit, MAX_GENERATE)
    _log(f"Queue imbalanced: {easy_ratio:.0%} easy, need {deficit} more easy tasks")

    # Gather candidates from all sources
    all_candidates: list[TaskCandidate] = []
    all_candidates.extend(_gen_missing_tests())
    all_candidates.extend(_gen_config_hardening())
    all_candidates.extend(_gen_doc_and_quality())

    # Sort: quick first (cheapest), then surgical
    tier_order = {"quick": 0, "surgical": 1}
    all_candidates.sort(key=lambda c: tier_order.get(c.tier, 2))

    # Pick the top N
    selected = all_candidates[:deficit]

    if not selected:
        _log("No candidate tasks available to generate")
        return []

    _log(f"Selected {len(selected)} tasks: {[c.name for c in selected]}")

    if not dry_run:
        if _check_cooldown():
            _log("Skipping generation — cooldown active")
            return selected

        TASK_QUEUE.mkdir(parents=True, exist_ok=True)
        for candidate in selected:
            scope_lines = "\n".join(f"- {s}" for s in candidate.scope)
            task_body = (
                f"title: {candidate.title}\n"
                f"profile: {candidate.tier}\n"
                f"goal: {candidate.goal}\n"
                f"scope:\n"
                f"{scope_lines}\n"
                f"success:\n"
                f"- {candidate.success}\n"
                f"generated_by: queue_balancer\n"
                f"generated_at: {datetime.now().isoformat()}\n"
            )
            task_path = TASK_QUEUE / f"{candidate.name}.md"
            if not task_path.exists():
                task_path.write_text(task_body)
                _log(f"Generated: {task_path.name}")
            else:
                _log(f"Skipped (already exists): {task_path.name}")

        _set_cooldown()

    return selected


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Queue Balancer — maintain healthy tier mix")
    parser.add_argument("--apply", action="store_true",
                        help="Actually generate tasks (default is dry-run)")
    parser.add_argument("--status", action="store_true",
                        help="Show current queue breakdown only")
    parser.add_argument("--force", action="store_true",
                        help="Ignore cooldown timer")
    args = parser.parse_args()

    if args.status:
        breakdown = get_queue_breakdown()
        total = sum(len(v) for v in breakdown.values())
        easy = len(breakdown["quick"]) + len(breakdown["surgical"])
        print(f"Queue: {total} tasks")
        for tier, tasks in breakdown.items():
            print(f"  {tier:12s}: {len(tasks):2d}  {tasks}")
        if total > 0:
            pct = easy / total
            target = "OK" if pct >= MIN_EASY_RATIO else f"NEEDS {max(1, round(total * MIN_EASY_RATIO) - easy)} MORE EASY"
            print(f"\nEasy ratio: {pct:.0%} (target >= {MIN_EASY_RATIO:.0%}) — {target}")
        return

    if args.force:
        try:
            COOLDOWN_FILE.unlink()
        except FileNotFoundError:
            pass

    dry_run = not args.apply
    selected = balance_queue(dry_run=dry_run)

    if not selected:
        print("Queue is balanced or no candidates available.")
        return

    mode = "DRY RUN" if dry_run else "GENERATED"
    print(f"\n{mode}: {len(selected)} task(s)")
    for c in selected:
        print(f"  [{c.tier:8s}] {c.name}")
        print(f"            {c.goal}")
        print(f"            source: {c.source}")
    if dry_run:
        print("\nRun with --apply to generate these tasks.")


if __name__ == "__main__":
    main()
