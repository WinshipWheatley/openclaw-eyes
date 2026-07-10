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
AUDIT_LOCK = Path("/home/openclaw/polish_loop/.audit_lock")
SRC_DIR = Path("/home/openclaw")
TEST_DIR = Path("/home/openclaw/tests")
LOG_FILE = Path("/mnt/c/OpenClaw/logs/queue_balancer.log")
ORCH_LOG = Path("/mnt/c/OpenClaw/logs/orchestrator.log")

PERSONAL_CONTEXT_CANDIDATES = (
    Path("/home/openclaw/mac_eyes/Winship/Right now.md"),
    Path("/home/openclaw/mac_eyes/Winship/Big Picture.md"),
    Path("/mnt/c/OpenClawShared/openclaw-vault/System/Overview.md"),
)

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
MIN_STANDARD_RATIO = 0.35
MIN_ARCHITECT_RATIO = 0.10
MAX_GENERATE = 3         # never generate more than 3 tasks at once
COOLDOWN_HOURS = 4       # don't re-generate within this window
AUTOPILOT_MIN_QUEUE = 5  # Deep-Flight mode: if queue drops below this, refill
AUTOPILOT_BATCH = 5      # number of auto-gen tasks to create in one refill

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


def _next_auto_gen_ids(count: int) -> list[str]:
    """Return next available auto-gen-XXX names, skipping existing/archived ids."""
    used: set[int] = set()

    def _collect_from_name(name: str):
        m = re.search(r"auto-gen-(\d{3})", name)
        if m:
            used.add(int(m.group(1)))

    for n in _get_queued_names():
        _collect_from_name(n)
    for n in _get_completed_names():
        _collect_from_name(n)

    out: list[str] = []
    i = 1
    while len(out) < count:
        if i not in used:
            out.append(f"auto-gen-{i:03d}")
        i += 1
    return out


def _recent_orchestrator_signals() -> list[str]:
    """Extract high-signal operational pain points from recent orchestrator activity."""
    if not ORCH_LOG.exists():
        return ["orchestrator log unavailable"]
    try:
        tail = ORCH_LOG.read_text(errors="replace").splitlines()[-500:]
    except Exception:
        return ["orchestrator log unreadable"]

    checks = {
        "builder_timeout": r"builder_timeout|builder dead|elapsed .*>=",
        "planner_delay": r"planner_timeout|waiting for Planner|mac_turn",
        "blocked_events": r"\[TRANSITION\].*blocked",
        "parked_events": r"\[TRANSITION\].*parked",
        "relaunches": r"re-launch|relaunch",
    }
    signals: list[str] = []
    for label, pat in checks.items():
        count = sum(1 for ln in tail if re.search(pat, ln, flags=re.IGNORECASE))
        if count:
            signals.append(f"{label}:{count}")
    return signals or ["no dominant failure pattern in recent tail"]


def _personal_context_signals() -> list[str]:
    """Extract lightweight personal/business context hints from known context docs."""
    key_terms = (
        "golf", "surf", "music", "album", "briefing", "approval", "billing", "queue",
    )
    hits: list[str] = []
    for path in PERSONAL_CONTEXT_CANDIDATES:
        if not path.exists():
            continue
        try:
            text = path.read_text(errors="replace").lower()
        except Exception:
            continue
        local_hits = [k for k in key_terms if k in text]
        if local_hits:
            hits.append(f"{path.name}:" + ",".join(local_hits[:4]))
    return hits or ["personal context docs missing or sparse"]


def _gen_autopilot_optimizations(count: int = AUTOPILOT_BATCH) -> list[TaskCandidate]:
    """Deep-Flight autopilot tasks that reduce daily manual work.

    These tasks are constrained to PII-safe handling and payment deferral only.
    """
    names = _next_auto_gen_ids(count)
    ops = _recent_orchestrator_signals()
    ctx = _personal_context_signals()

    templates = [
        (
            "Reduce approval click load with grouped decision bundles",
            [
                "Chief + Cassandra analyze pending approvals and cluster similar low-risk actions.",
                "Generate one-click bundle proposals with clear rollback notes.",
                "Tag all payload fields with PII-vault required handling.",
                "Any payment action must be queued in Future Action table (no execution).",
            ],
            "Dashboard shows grouped approval bundles with at least 30% fewer manual clicks.",
        ),
        (
            "Automate overnight ops cleanup and morning handoff quality",
            [
                "Mine recent orchestrator failures and auto-generate remediation checklists.",
                "Summarize unresolved blockers for 8AM briefing with owner + next action.",
                "Ensure task notes include PII-vault scope guard before any data references.",
                "Payment-related follow-ups must be deferred to Future Action table.",
            ],
            "Morning handoff contains actionable blockers with zero manual log triage required.",
        ),
        (
            "Build personal-time protection automations",
            [
                "Use context signals to suppress non-urgent admin interruptions during creative windows.",
                "Auto-route low-priority business chores to queue with due windows.",
                "Enforce PII-vault masking in generated notes and summaries.",
                "Do not send or execute payments; queue for manual approval only.",
            ],
            "Admin interrupts are reduced and non-urgent work is queued automatically.",
        ),
        (
            "Create billing and ledger autopilot exception detector",
            [
                "Detect missing ledger fields and invoice anomalies before they require manual correction.",
                "Generate reconciliation tasks with deterministic acceptance checks.",
                "Apply PII-vault policy to all financial identifiers in task artifacts.",
                "All external payment intents go to Future Action queue pending approval.",
            ],
            "Ledger anomalies are surfaced proactively with ready-to-execute fix tasks.",
        ),
        (
            "Implement self-heal task authoring from runtime failure patterns",
            [
                "Translate repeated builder/planner failures into bounded documentation-research tasks.",
                "Attach failure signatures and affected files for faster fix execution.",
                "Mark generated tasks with PII-vault mandatory handling requirements.",
                "Payment outcomes must remain queued, never auto-executed externally.",
            ],
            "Runtime failures automatically spawn focused fix tasks without operator intervention.",
        ),
    ]

    candidates: list[TaskCandidate] = []
    for idx, task_name in enumerate(names):
        goal, scope, success = templates[idx % len(templates)]
        context_line = f"Signals: ops={'; '.join(ops[:3])} | context={'; '.join(ctx[:2])}"
        candidates.append(TaskCandidate(
            name=task_name,
            tier="standard",
            title=task_name,
            goal=goal,
            scope=scope + [context_line],
            success=success,
            source="autopilot_deep_flight",
        ))
    return candidates


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
          "Required bot vars are role-namespaced (MAESTRO_BOT_TOKEN, CHIEF_BOT_TOKEN, and each listener role); never use one generic bot token",
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


def _gen_chief_tests() -> list[TaskCandidate]:
    """Generate test and quality tasks for Chief system modules."""
    candidates = []
    completed = _get_completed_names()
    queued = _get_queued_names()

    chief_tasks = [
        ("test-chief-router", "chief_router.py",
         "Write unit tests for chief_router.py intent routing",
         ["Test route_message() returns expected handler for known intents",
          "Test fallback behavior when no intent matches",
          "Test that routing respects intent priority order",
          "Do NOT import or call network-bound modules — mock LLM calls"],
         "All tests pass covering main routing paths"),
        ("test-chief-session-manager", "chief_session_manager.py",
         "Write unit tests for chief_session_manager.py shared session state",
         ["Test get_session() returns a fresh session dict for new session IDs",
          "Test set_session() stores and retrieves values correctly",
          "Test session expiry/TTL logic if present",
          "No network calls — test pure state management only"],
         "All tests pass covering session get/set/expire"),
        ("test-chief-approval-policy", "chief_approval_policy.py",
         "Write unit tests for chief_approval_policy.py tier classification",
         ["Test each explicit L0/L1/L2 category correctly classified",
          "Test L2 always-escalate items: billing, credentials, force push",
          "Test L0 always-pass items: reads, git log/status/diff",
          "Test unknown actions default to correct tier (L1 or L2)"],
         "All tests pass confirming tier classification is stable"),
        ("test-chief-llm", "chief_llm.py",
         "Write unit tests for chief_llm.py Ollama client wrapper",
         ["Test build_prompt() formats context correctly",
          "Test that _call() returns a string (mock the HTTP call)",
          "Test timeout/error handling returns a graceful fallback string",
          "Use unittest.mock to avoid real Ollama calls"],
         "All tests pass, LLM wrapper behavior is verified offline"),
        ("doc-chief-architecture", "chief_listener.py",
         "Add module-level architecture comment to chief_listener.py",
         ["Add a comment block at the top of chief_listener.py explaining:",
          "  - Which bot identity this runs as",
          "  - What it routes to (chief_router, brains)",
          "  - What it does NOT do (no direct LLM calls, no DB writes)",
          "Keep the comment concise — max 10 lines"],
         "chief_listener.py has a clear architecture comment at the top"),
    ]

    for module_name, filename, goal, scope, success in chief_tasks:
        task_name = f"chief-{module_name}" if not module_name.startswith("test-") else module_name
        # Normalize: test-chief-router stays as is, doc-chief-architecture stays
        task_name = module_name
        if task_name in completed or task_name in queued:
            continue
        if filename and not (SRC_DIR / filename).exists():
            continue
        tier = "quick" if module_name.startswith("doc-") else "surgical"
        candidates.append(TaskCandidate(
            name=task_name,
            tier=tier,
            title=task_name,
            goal=goal,
            scope=scope,
            success=success,
            source="chief_tests",
        ))

    return candidates


def _gen_guardian_cassandra_tests() -> list[TaskCandidate]:
    """Generate test and quality tasks for Guardian and Cassandra modules."""
    candidates = []
    completed = _get_completed_names()
    queued = _get_queued_names()

    gc_tasks = [
        ("test-cassandra-briefing-brain", "cassandra_briefing_brain.py",
         "Write unit tests for cassandra_briefing_brain.py delivery logic",
         ["Test _should_send_briefing() time-window logic for morning/afternoon/evening",
          "Test that briefing is suppressed when approval_pending.json is fresh and active",
          "Test that stale pending records do NOT suppress briefings",
          "Mock Telegram calls — test logic, not network"],
         "All tests pass, briefing suppression and delivery timing verified"),
        ("test-cassandra-brain-routing", "cassandra_brain.py",
         "Write unit tests for Cassandra's message routing dispatch",
         ["Test that financial keywords route to financial_event handler",
          "Test that calendar keywords route to calendar handler",
          "Test that unrecognized messages fall through to LLM",
          "Test that sensitive keywords trigger pii handling path",
          "Mock all external calls (Telegram, LLM, Google) — test dispatch only"],
         "All tests pass, routing dispatch verified for 5+ routes"),
        ("test-approval-brain", "chief_approval_brain.py",
         "Write unit tests for chief_approval_brain.py tier logic",
         ["Test that L0 actions return immediately without prompting",
          "Test that L2 actions require Guardian approval",
          "Test --resend-pending reads approval_pending.json and resends",
          "Test cooldown/replay cap prevents spam",
          "Mock Telegram send — do not actually send messages"],
         "All tests pass, L0/L1/L2 gate behavior is verified offline"),
        ("doc-cassandra-gap-detection", "cassandra_brain.py",
         "Add inline documentation to detect_capability_gaps()",
         ["Add a docstring explaining the 3 detection signals: flag_value=False, query_match, hedging",
          "Document why _reply_has_hedging() is checked alongside flag state",
          "Add a comment explaining why manual_required=True gaps are skipped by _create_upgrade_task()"],
         "detect_capability_gaps() docstring explains the detection logic clearly"),
        ("fix-cassandra-requeue", "cassandra_brain.py",
         "Prevent _create_upgrade_task() from re-queueing already-completed tasks",
         ["In _existing_upgrade_task_name(), also scan the archive directory for task_* files",
          "If a matching completed task exists in archive, return its name and skip creation",
          "This prevents capability gap detection from re-queueing tasks the loop already finished"],
         "Cassandra stops re-queueing tasks that are already in the archive"),
    ]

    for module_name, filename, goal, scope, success in gc_tasks:
        task_name = module_name
        if task_name in completed or task_name in queued:
            continue
        if filename and not (SRC_DIR / filename).exists():
            continue
        tier = "quick" if module_name.startswith("doc-") or module_name.startswith("fix-") else "surgical"
        candidates.append(TaskCandidate(
            name=task_name,
            tier=tier,
            title=task_name,
            goal=goal,
            scope=scope,
            success=success,
            source="guardian_cassandra_tests",
        ))

    return candidates


def _gen_standard_architect() -> list[TaskCandidate]:
    """Generate deeper standard/architect tasks for cross-system throughput."""
    candidates = []
    completed = _get_completed_names()
    queued = _get_queued_names()

    specs = [
        ("std-chief-router-table-tests", "standard", "chief_router.py",
         "Build table-driven regression tests for chief_router intent precedence",
         ["Create tests/test_chief_router_table.py with >=20 intent samples",
          "Cover overlaps: billing vs ops vs approval routing",
          "Verify fallback route stays deterministic"],
         "Routing precedence regressions are caught by table tests"),
        ("std-chief-session-persistence", "standard", "chief_session_manager.py",
         "Harden session lifecycle with persistence edge-case tests",
         ["Test stale session eviction and restore behavior",
          "Test concurrent update ordering on same session id",
          "Add explicit serialization roundtrip checks"],
         "Session lifecycle is deterministic under edge conditions"),
        ("std-approval-replay-observability", "standard", "chief_approval_brain.py",
         "Add observability around approval replay and cooldown paths",
         ["Log replay decisions with reason codes",
          "Add tests for cooldown and replay cap enforcement",
          "Ensure no duplicate resend during cooldown"],
         "Approval replay behavior is traceable and tested"),
        ("std-cassandra-routing-matrix", "standard", "cassandra_brain.py",
         "Add routing matrix tests for Cassandra keyword and hedge paths",
         ["Cover financial/calendar/email/file/future-action matrices",
          "Verify hedge-only responses do not over-trigger gaps",
          "Lock expected route labels in tests"],
         "Routing matrix has stable, test-backed expectations"),
        ("std-cassandra-briefing-retry-policy", "standard", "cassandra_briefing_scheduler.py",
         "Implement bounded retry policy for briefing PENDING deliveries",
         ["Retry PENDING items with exponential backoff and cap",
          "Log attempts and terminal outcomes",
          "Avoid duplicate delivery spam"],
         "Briefing delivery retries are bounded and visible"),
        ("std-dashboard-loop-health-panel", "standard", "dashboard_gen.py",
         "Add loop health panel with staleness and runner drift indicators",
         ["Surface stale last_updated age threshold warnings",
          "Show planner/builder mismatch and defer flags",
          "Summarize blocked/parked frequency from orchestrator log"],
         "Right Now dashboard highlights actionable health risks"),
        ("std-orchestrator-promotion-audit", "standard", "polish_loop/orchestrator.py",
         "Add structured promotion audit logging for queue decisions",
         ["Log skip reasons per task candidate",
          "Log completed-name suppression hits",
          "Add unit tests for runnable task selection"],
         "Task promotion decisions are auditable"),
        ("std-builder-relaunch-guard-tests", "standard", "builder_watcher.sh",
         "Add regression checks for builder relaunch guard behavior",
         ["Test stopped-process detection paths",
          "Test relaunch guard reset on resume",
          "Validate timeout parking behavior"],
         "Builder relaunch behavior remains regression-safe"),
        ("std-budget-anomaly-alerts", "standard", "budget_tracker.py",
         "Add anomaly alerts for single-run spend spikes",
         ["Detect run cost outliers per runner",
          "Emit warning with task and runner context",
          "Add tests for threshold calculations"],
         "Budget spikes are caught and visible"),
        ("std-queue-balancer-tier-report", "standard", "queue_balancer.py",
         "Add reporting output for candidate pools by tier/source",
         ["Add --pool-status CLI view",
          "Print counts by quick/surgical/standard/architect",
          "Print counts by generator source"],
         "Balancer pool health can be inspected quickly"),
        ("std-cassandra-error-bundle", "standard", "cassandra_brain.py",
         "Bundle Cassandra hard-error context for debug tasks",
         ["Attach traceback excerpt and route context to cas-debug tasks",
          "Add dedup key based on exception signature",
          "Prevent repeated tasks for identical failures"],
         "Debug tasks are richer and less noisy"),
        ("std-chief-watcher-state-guards", "standard", "chief_watcher_brain.py",
         "Harden watcher state transitions with explicit guard checks",
         ["Reject invalid state transitions with reason",
          "Add tests for pending/replay edge cases",
          "Expose guard failure counters"],
         "Watcher state transitions are validated and observable"),

        ("arch-cross-bot-telemetry-schema", "architect", "dashboard_gen.py",
         "Design and implement shared telemetry schema for Chief/Guardian/Cassandra",
         ["Define canonical event fields and severity",
          "Wire event emitters in core loops",
          "Add dashboard views consuming the unified schema"],
         "Cross-bot telemetry is normalized and queryable"),
        ("arch-loop-self-heal-policy", "architect", "polish_loop/orchestrator.py",
         "Implement policy-driven self-heal for stuck loop states",
         ["Add policy table for recoverable vs terminal states",
          "Execute bounded automated remediation",
          "Escalate irrecoverable failures with clear reason"],
         "Loop self-heal behavior is policy-based and bounded"),
        ("arch-chief-capability-registry", "architect", "capability_registry.py",
         "Build unified capability registry consumed by all bots",
         ["Represent capability metadata, owner, approval tier",
          "Expose read API for planner and runtime checks",
          "Migrate duplicated capability flags to registry lookups"],
         "Capabilities are centrally defined and reused"),
        ("arch-cassandra-outreach-pipeline", "architect", "cassandra_outreach.py",
         "Create end-to-end outreach pipeline with retries and review points",
         ["Model draft->review->send lifecycle",
          "Add retry/error handling and audit trail",
          "Preserve approval gating on external sends"],
         "Outreach pipeline is reliable and auditable"),
        ("arch-approval-audit-timeline", "architect", "chief_approval_brain.py",
         "Implement full approval timeline reconstruction",
         ["Link request, resend, response, final decision events",
          "Persist timeline ids in pending records",
          "Add dashboard timeline rendering"],
         "Any approval can be reconstructed end-to-end"),
        ("arch-runner-policy-engine", "architect", "runner_profiles.py",
         "Refactor runner selection into policy engine with constraints",
         ["Define declarative policy for tiers, budgets, sensitivity",
          "Evaluate candidates through policy graph",
          "Add explain output for selection decisions"],
         "Runner decisions are policy-driven and explainable"),
        ("arch-briefing-source-of-truth", "architect", "cassandra_briefing_brain.py",
         "Unify briefing generation and delivery state under one source of truth",
         ["Replace split status derivation with canonical record",
          "Track generated/queued/delivered/failed transitions",
          "Migrate dashboard metrics to canonical record"],
         "Briefing status is consistent across logs and dashboards"),
        ("arch-state-machine-contract-tests", "architect", "polish_loop/orchestrator.py",
         "Add contract tests for all allowed/forbidden state transitions",
         ["Codify transition matrix from STATE_MACHINE.md",
          "Test every edge in matrix",
          "Block release when forbidden transition is introduced"],
         "State-machine behavior is contract-tested"),
        ("arch-chief-dispatch-isolation", "architect", "chief_listener.py",
         "Isolate dispatch path from long-running side effects",
         ["Split fast-path message intake from heavy work",
          "Queue side effects to worker boundary",
          "Add backpressure handling and metrics"],
         "Listener remains responsive under load"),
        ("arch-cassandra-knowledge-store", "architect", "cassandra_brain.py",
         "Add structured knowledge store for long-horizon follow-ups",
         ["Persist follow-up intents with status lifecycle",
          "Link intents to contact and capability",
          "Surface pending/overdue in dashboard"],
         "Long-horizon follow-ups are durable and trackable"),
        ("arch-guardian-safety-contract", "architect", "chief_approval_policy.py",
         "Define machine-readable safety contract for Guardian decisions",
         ["Formalize immutable L2 categories and justifications",
          "Add validation against accidental downgrades",
          "Produce contract report for audits"],
         "Guardian safety boundaries are explicit and testable"),
        ("arch-end-to-end-replay-harness", "architect", "polish_loop/orchestrator.py",
         "Create replay harness for full-loop incident reproduction",
         ["Replay status/log/task sequence from captured incident",
          "Assert expected transitions and outcomes",
          "Generate diff report between expected and observed"],
         "Incidents can be reproduced and debugged deterministically"),
    ]

    for name, tier, file_name, goal, scope, success in specs:
        if name in completed or name in queued:
            continue
        if file_name and not (SRC_DIR / file_name).exists():
            continue
        candidates.append(TaskCandidate(
            name=name,
            tier=tier,
            title=name,
            goal=goal,
            scope=scope,
            success=success,
            source="standard_architect",
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


def _audit_lock_active() -> bool:
    """Hard stop for queue generation during system audit freeze."""
    return AUDIT_LOCK.exists()


def balance_queue(dry_run: bool = True) -> list[TaskCandidate]:
    """Check queue balance and generate filler tasks if needed.

    Returns list of tasks that were (or would be) generated.
    """
    if _audit_lock_active():
        _log(f"Audit lock active at {AUDIT_LOCK}; queue generation blocked")
        return []

    breakdown = get_queue_breakdown()
    total = sum(len(v) for v in breakdown.values())
    easy_count = len(breakdown["quick"]) + len(breakdown["surgical"])
    standard_count = len(breakdown["standard"])
    architect_count = len(breakdown["architect"])

    _log(f"Queue: {total} tasks — quick={len(breakdown['quick'])}, "
         f"surgical={len(breakdown['surgical'])}, standard={len(breakdown['standard'])}, "
         f"architect={len(breakdown['architect'])}")

    easy_ratio = easy_count / total if total > 0 else 0.0
    standard_ratio = standard_count / total if total > 0 else 0.0
    architect_ratio = architect_count / total if total > 0 else 0.0

    # Deep-Flight autopilot: aggressively refill when queue runs thin.
    if total < AUTOPILOT_MIN_QUEUE:
        auto_tasks = _gen_autopilot_optimizations(AUTOPILOT_BATCH)
        _log(f"Autopilot refill triggered: queue={total} < {AUTOPILOT_MIN_QUEUE}; generating {len(auto_tasks)} auto-gen tasks")
        if not dry_run:
            TASK_QUEUE.mkdir(parents=True, exist_ok=True)
            for candidate in auto_tasks:
                scope_lines = "\n".join(f"- {s}" for s in candidate.scope)
                task_body = (
                    f"title: {candidate.title}\n"
                    f"profile: {candidate.tier}\n"
                    f"goal: {candidate.goal}\n"
                    f"pii_vault_required: true\n"
                    f"payment_execution_policy: future_action_only\n"
                    f"scope:\n"
                    f"{scope_lines}\n"
                    f"success:\n"
                    f"- {candidate.success}\n"
                    f"generated_by: queue_balancer\n"
                    f"generated_at: {datetime.now().isoformat()}\n"
                    f"autopilot_mode: deep_flight\n"
                )
                task_path = TASK_QUEUE / f"{candidate.name}.md"
                task_path.write_text(task_body)
                _log(f"Generated autopilot task: {task_path.name}")
        return auto_tasks

    # Decide tier slots to generate this round.
    # Empty queue: seed with 2 easy + 1 standard for momentum + depth.
    slots = {"easy": 0, "standard": 0, "architect": 0}
    if total == 0:
        slots = {"easy": 2, "standard": 1, "architect": 0}
        _log("Queue empty — generating starter mix (2 easy + 1 standard)")
    else:
        if easy_ratio < MIN_EASY_RATIO:
            slots["easy"] = max(1, round(total * MIN_EASY_RATIO) - easy_count)
        if total >= 3 and standard_ratio < MIN_STANDARD_RATIO:
            slots["standard"] = 1
        if total >= 6 and architect_ratio < MIN_ARCHITECT_RATIO:
            slots["architect"] = 1

        slot_total = slots["easy"] + slots["standard"] + slots["architect"]
        if slot_total == 0:
            _log(
                f"Queue balanced: easy={easy_ratio:.0%}, standard={standard_ratio:.0%}, architect={architect_ratio:.0%}"
            )
            return []

        _log(
            "Queue tier deficits: "
            f"easy={slots['easy']}, standard={slots['standard']}, architect={slots['architect']}"
        )

    # Gather candidates from all sources
    all_candidates: list[TaskCandidate] = []
    all_candidates.extend(_gen_missing_tests())
    all_candidates.extend(_gen_config_hardening())
    all_candidates.extend(_gen_chief_tests())
    all_candidates.extend(_gen_guardian_cassandra_tests())
    all_candidates.extend(_gen_doc_and_quality())
    all_candidates.extend(_gen_standard_architect())

    easy_candidates = [c for c in all_candidates if c.tier in ("quick", "surgical")]
    standard_candidates = [c for c in all_candidates if c.tier == "standard"]
    architect_candidates = [c for c in all_candidates if c.tier == "architect"]

    easy_candidates.sort(key=lambda c: 0 if c.tier == "quick" else 1)

    selected: list[TaskCandidate] = []

    def _take(src: list[TaskCandidate], n: int):
        for c in src:
            if n <= 0 or len(selected) >= MAX_GENERATE:
                break
            if c.name in {s.name for s in selected}:
                continue
            selected.append(c)
            n -= 1

    _take(easy_candidates, slots["easy"])
    _take(standard_candidates, slots["standard"])
    _take(architect_candidates, slots["architect"])

    # Fill remaining capacity with deeper work first, then easy work.
    if len(selected) < MAX_GENERATE:
        _take(standard_candidates, MAX_GENERATE - len(selected))
    if len(selected) < MAX_GENERATE:
        _take(easy_candidates, MAX_GENERATE - len(selected))
    if len(selected) < MAX_GENERATE:
        _take(architect_candidates, MAX_GENERATE - len(selected))

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
