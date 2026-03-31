#!/usr/bin/env python3
"""Budget tracker — cross-task spending awareness for the runner pipeline.

Tracks cumulative spending across all runners, enforces daily/window budgets,
and provides budget-aware advice to runner_profiles.py about what can be
afforded right now.

Data lives in /home/openclaw/.budget_state.json — a simple ledger that resets
each billing window (daily by default, configurable per-runner).

Key capabilities:
  - Record cost after each task run
  - Query remaining budget per runner / globally
  - Detect "stuck loop" patterns (repeated high spend with no task completion)
  - Advise on whether a runner+model combo can afford a task
  - Suggest cheaper alternatives when budget is tight
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

STATE_FILE = Path("/home/openclaw/.budget_state.json")
SPEND_LOG = Path("/mnt/c/OpenClaw/logs/budget_spend.log")

# ---------------------------------------------------------------------------
# Budget windows — when limits reset
# ---------------------------------------------------------------------------

# Per-runner daily budget caps (USD).  These are SOFT caps — the system
# degrades gracefully rather than hard-blocking.
DAILY_CAPS: dict[str, float] = {
    "claude": 15.00,    # Anthropic daily — conservative default
    "codex": 10.00,     # OpenAI daily
    "gemini": 5.00,     # Google daily (generous free tier)
    "aider": 10.00,     # Uses underlying API (shared with claude/codex)
    "ollama": 999.00,   # Local — effectively unlimited
}

# Global daily cap across ALL runners
GLOBAL_DAILY_CAP = 25.00

# Cost thresholds for degradation tiers
BUDGET_THRESHOLDS = {
    "green":  0.50,   # <50% spent — full capability
    "yellow": 0.75,   # 50-75% — prefer cheaper models
    "orange": 0.90,   # 75-90% — local/free only for non-critical
    "red":    1.00,   # 90-100% — only blocking tasks, cheapest option
}

# Stuck-loop detection: if we see this many recent runs with high cost
# and no task completion, flag it
STUCK_LOOP_THRESHOLD = 3       # consecutive expensive non-completions
STUCK_LOOP_COST_MIN = 1.00     # each run cost more than this

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SpendEntry:
    """A single spend record."""
    timestamp: str          # ISO format
    runner: str             # "claude", "codex", etc.
    model: str              # "opus", "sonnet", "haiku", etc.
    task_id: str            # from task.md title or "unknown"
    cost_usd: float
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    duration_ms: int = 0
    completed: bool = False  # did the task actually finish successfully?
    exit_code: int = -1
    tier: str = ""          # "quick", "surgical", "standard", "architect"


@dataclass
class BudgetState:
    """Current budget tracking state."""
    window_start: str = ""          # ISO date of current window start
    window_type: str = "daily"      # "daily" | "monthly"
    entries: list[dict] = field(default_factory=list)
    daily_caps: dict[str, float] = field(default_factory=dict)
    global_daily_cap: float = GLOBAL_DAILY_CAP
    stuck_loop_count: int = 0       # consecutive expensive non-completions

    def is_current_window(self) -> bool:
        if not self.window_start:
            return False
        try:
            ws = datetime.fromisoformat(self.window_start)
            now = datetime.now()
            if self.window_type == "daily":
                return ws.date() == now.date()
            return False
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Core tracking functions
# ---------------------------------------------------------------------------

def _load_state() -> BudgetState:
    """Load or initialize budget state."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            state = BudgetState(
                window_start=data.get("window_start", ""),
                window_type=data.get("window_type", "daily"),
                entries=data.get("entries", []),
                daily_caps=data.get("daily_caps", {}),
                global_daily_cap=data.get("global_daily_cap", GLOBAL_DAILY_CAP),
                stuck_loop_count=data.get("stuck_loop_count", 0),
            )
            if state.is_current_window():
                return state
            # Window expired — start fresh (but keep caps)
            return BudgetState(
                window_start=datetime.now().isoformat(),
                daily_caps=state.daily_caps or dict(DAILY_CAPS),
                global_daily_cap=state.global_daily_cap,
            )
        except Exception:
            pass

    return BudgetState(
        window_start=datetime.now().isoformat(),
        daily_caps=dict(DAILY_CAPS),
        global_daily_cap=GLOBAL_DAILY_CAP,
    )


def _save_state(state: BudgetState):
    """Persist budget state."""
    try:
        data = {
            "window_start": state.window_start,
            "window_type": state.window_type,
            "entries": state.entries,
            "daily_caps": state.daily_caps,
            "global_daily_cap": state.global_daily_cap,
            "stuck_loop_count": state.stuck_loop_count,
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        _log(f"State save failed: {e}")


def _log(msg: str):
    """Append to spend log."""
    try:
        SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SPEND_LOG, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_spend(
    runner: str,
    model: str,
    cost_usd: float,
    task_id: str = "unknown",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    duration_ms: int = 0,
    completed: bool = False,
    exit_code: int = -1,
    tier: str = "",
) -> dict:
    """Record a spend entry after a task run.

    Returns a status dict with budget health info.
    """
    state = _load_state()

    entry = SpendEntry(
        timestamp=datetime.now().isoformat(),
        runner=runner,
        model=model,
        task_id=task_id,
        cost_usd=cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        duration_ms=duration_ms,
        completed=completed,
        exit_code=exit_code,
        tier=tier,
    )
    state.entries.append(asdict(entry))

    # Stuck-loop detection
    if cost_usd >= STUCK_LOOP_COST_MIN and not completed:
        state.stuck_loop_count += 1
        if state.stuck_loop_count >= STUCK_LOOP_THRESHOLD:
            _log(f"STUCK LOOP DETECTED: {state.stuck_loop_count} consecutive expensive non-completions (last: ${cost_usd:.2f} on {runner}/{model})")
    else:
        state.stuck_loop_count = 0  # reset on success or cheap run

    _save_state(state)

    status = get_budget_status()
    _log(f"SPEND: ${cost_usd:.4f} on {runner}/{model} task={task_id} completed={completed} | day_total=${status['global_spent']:.2f}/{status['global_cap']:.2f} ({status['budget_zone']})")

    return status


def get_budget_status() -> dict:
    """Get current budget health across all runners.

    Returns dict with:
      - per_runner: {runner: {spent, cap, remaining, pct}}
      - global_spent, global_cap, global_remaining, global_pct
      - budget_zone: "green" | "yellow" | "orange" | "red"
      - stuck_loop: bool
      - recommendation: str (human-readable advice)
    """
    state = _load_state()

    # Sum spending per runner
    runner_totals: dict[str, float] = {}
    for e in state.entries:
        r = e.get("runner", "unknown")
        runner_totals[r] = runner_totals.get(r, 0) + e.get("cost_usd", 0)

    global_spent = sum(runner_totals.values())
    global_cap = state.global_daily_cap
    caps = state.daily_caps or DAILY_CAPS

    per_runner = {}
    for runner, cap in caps.items():
        spent = runner_totals.get(runner, 0)
        per_runner[runner] = {
            "spent": round(spent, 4),
            "cap": cap,
            "remaining": round(max(0, cap - spent), 4),
            "pct": round(spent / cap, 4) if cap > 0 else 0,
        }

    global_pct = global_spent / global_cap if global_cap > 0 else 0

    # Determine zone
    zone = "green"
    for threshold_name, threshold_pct in sorted(BUDGET_THRESHOLDS.items(), key=lambda x: x[1]):
        if global_pct >= threshold_pct:
            zone = threshold_name

    # Stuck loop
    stuck = state.stuck_loop_count >= STUCK_LOOP_THRESHOLD

    # Recommendation
    rec = _build_recommendation(zone, stuck, per_runner, global_spent, global_cap)

    return {
        "per_runner": per_runner,
        "global_spent": round(global_spent, 4),
        "global_cap": global_cap,
        "global_remaining": round(max(0, global_cap - global_spent), 4),
        "global_pct": round(global_pct, 4),
        "budget_zone": zone,
        "stuck_loop": stuck,
        "stuck_loop_count": state.stuck_loop_count,
        "recommendation": rec,
        "window_start": state.window_start,
        "entries_today": len(state.entries),
    }


def get_runner_allowance(runner: str, model: str, tier: str) -> dict:
    """Check if a specific runner+model combo can afford a task tier.

    Returns:
      - allowed: bool
      - max_budget: float (recommended --max-budget-usd for this run)
      - reason: str
      - alternative: optional dict with cheaper runner suggestion
    """
    status = get_budget_status()
    zone = status["budget_zone"]
    stuck = status["stuck_loop"]

    runner_info = status["per_runner"].get(runner, {"remaining": 0, "pct": 0})
    remaining_runner = runner_info.get("remaining", 0)
    remaining_global = status["global_remaining"]
    remaining = min(remaining_runner, remaining_global)

    # Tier cost estimates (typical per-task)
    tier_costs = {
        "quick": 0.10,
        "surgical": 0.30,
        "standard": 1.50,
        "architect": 4.00,
    }
    estimated_cost = tier_costs.get(tier, 1.50)

    # Stuck loop — force downgrade
    if stuck:
        if runner != "ollama":
            return {
                "allowed": False,
                "max_budget": 0,
                "reason": f"Stuck loop detected ({status['stuck_loop_count']} consecutive expensive failures). Forcing local/free runner.",
                "alternative": {"runner": "ollama", "model": "qwen2.5-coder:14b", "reason": "stuck-loop safety valve"},
            }

    # Red zone — only allow if task is blocking AND use minimum viable runner
    if zone == "red":
        if estimated_cost > remaining:
            return {
                "allowed": False,
                "max_budget": 0,
                "reason": f"Red zone: ${status['global_spent']:.2f}/${status['global_cap']:.2f} spent. Task needs ~${estimated_cost:.2f} but only ${remaining:.2f} left.",
                "alternative": _suggest_cheaper(tier, remaining),
                "defer_until": "next_window",
            }
        # Allow but cap tightly
        return {
            "allowed": True,
            "max_budget": min(remaining * 0.5, estimated_cost),  # Only use half remaining
            "reason": f"Red zone — tight cap. ${remaining:.2f} left.",
        }

    # Orange zone — downgrade expensive runners
    if zone == "orange":
        if model in ("opus",) and tier != "architect":
            return {
                "allowed": False,
                "max_budget": 0,
                "reason": f"Orange zone: opus reserved for architect-only tasks. ${remaining:.2f} left.",
                "alternative": {"runner": runner, "model": "sonnet", "reason": "budget conservation"},
            }
        return {
            "allowed": True,
            "max_budget": min(remaining * 0.3, estimated_cost),
            "reason": f"Orange zone — conservative cap. ${remaining:.2f} left.",
        }

    # Yellow zone — prefer cheaper but allow all
    if zone == "yellow":
        if model == "opus" and tier in ("quick", "surgical"):
            return {
                "allowed": True,
                "max_budget": min(remaining * 0.15, estimated_cost * 0.5),
                "reason": f"Yellow zone — opus throttled for {tier}. ${remaining:.2f} left.",
                "alternative": {"runner": runner, "model": "sonnet", "reason": "budget conservation"},
            }
        return {
            "allowed": True,
            "max_budget": min(estimated_cost * 1.2, remaining * 0.4),
            "reason": f"Yellow zone — normal. ${remaining:.2f} left.",
        }

    # Green zone — full capability
    return {
        "allowed": True,
        "max_budget": estimated_cost * 1.5,  # Some overhead allowed
        "reason": f"Green zone — ${remaining:.2f} left of ${status['global_cap']:.2f}.",
    }


def check_partial_completion_strategy(task_id: str, tier: str, is_blocking: bool) -> dict:
    """For expensive tasks that might not finish in one window.

    Returns advice on whether to:
      a) Start now and let it do what it can (pick up later)
      b) Defer until window refreshes
      c) Split the task

    Args:
      task_id: Task identifier
      tier: Task tier ("architect" etc.)
      is_blocking: Whether downstream tasks depend on this one
    """
    status = get_budget_status()
    remaining = status["global_remaining"]

    tier_costs = {"quick": 0.10, "surgical": 0.30, "standard": 1.50, "architect": 4.00}
    estimated = tier_costs.get(tier, 1.50)

    can_probably_finish = remaining >= estimated * 0.8
    can_make_progress = remaining >= estimated * 0.3

    if can_probably_finish:
        return {
            "strategy": "run_full",
            "reason": f"~${remaining:.2f} left, est. ${estimated:.2f} — likely enough to finish.",
            "max_budget": min(estimated * 1.2, remaining * 0.7),
        }

    if is_blocking and can_make_progress:
        return {
            "strategy": "partial_now_continue_later",
            "reason": f"Task is blocking. ${remaining:.2f} left of ~${estimated:.2f} needed. "
                      f"Start now — opus can scaffold/plan. Pick up rest next window.",
            "max_budget": remaining * 0.5,
            "note": "Set task status to 'in_progress_partial' so next window resumes.",
        }

    if is_blocking and not can_make_progress:
        return {
            "strategy": "defer_to_next_window",
            "reason": f"Task is blocking but only ${remaining:.2f} left of ~${estimated:.2f} needed. "
                      f"Not enough to make meaningful progress. Hold for window refresh.",
        }

    # Not blocking, not affordable
    return {
        "strategy": "defer_to_next_window",
        "reason": f"Non-blocking task, ${remaining:.2f} left of ~${estimated:.2f} needed. "
                  f"Queue for next window.",
    }


def _suggest_cheaper(tier: str, remaining: float) -> Optional[dict]:
    """Suggest a cheaper runner alternative."""
    if remaining >= 0.10:
        # Can afford a cheap cloud API call
        return {"runner": "gemini", "model": "default", "reason": "cheapest cloud option"}
    if remaining > 0:
        return {"runner": "ollama", "model": "qwen2.5-coder:14b", "reason": "free local fallback"}
    return {"runner": "ollama", "model": "qwen2.5-coder:7b", "reason": "zero-cost local, minimal quality"}


def _build_recommendation(zone: str, stuck: bool, per_runner: dict, spent: float, cap: float) -> str:
    """Build a human-readable recommendation."""
    if stuck:
        return (
            f"⚠️ STUCK LOOP: Multiple expensive runs with no task completion. "
            f"Switch to local runner (ollama) or defer task. "
            f"Day spend: ${spent:.2f}/${cap:.2f}"
        )
    if zone == "red":
        return f"🔴 Budget critical: ${spent:.2f}/${cap:.2f}. Only free/local runners. Defer non-blocking tasks."
    if zone == "orange":
        return f"🟠 Budget tight: ${spent:.2f}/${cap:.2f}. No opus except architect. Prefer sonnet/local."
    if zone == "yellow":
        return f"🟡 Budget moderate: ${spent:.2f}/${cap:.2f}. Conserve opus. Normal operation otherwise."
    return f"🟢 Budget healthy: ${spent:.2f}/${cap:.2f}. Full capability available."


def update_caps(runner: str = None, daily_cap: float = None, global_cap: float = None):
    """Update budget caps. Called when user changes plan limits."""
    state = _load_state()
    if runner and daily_cap is not None:
        state.daily_caps[runner] = daily_cap
    if global_cap is not None:
        state.global_daily_cap = global_cap
    _save_state(state)
    _log(f"CAPS UPDATED: runner={runner} daily_cap={daily_cap} global_cap={global_cap}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Budget Tracker")
    parser.add_argument("--status", action="store_true", help="Show current budget status")
    parser.add_argument("--record", nargs=4, metavar=("RUNNER", "MODEL", "COST", "TASK_ID"),
                        help="Record a spend entry")
    parser.add_argument("--completed", action="store_true", default=False,
                        help="Mark spend entry as task-completed (with --record)")
    parser.add_argument("--exit-code", type=int, default=None,
                        help="Exit code from runner (with --record)")
    parser.add_argument("--tier", type=str, default="",
                        help="Task tier (with --record)")
    parser.add_argument("--duration-ms", type=int, default=0,
                        help="Run duration in ms (with --record)")
    parser.add_argument("--check", nargs=3, metavar=("RUNNER", "MODEL", "TIER"),
                        help="Check if a runner/model can afford a task tier")
    parser.add_argument("--strategy", nargs=3, metavar=("TASK_ID", "TIER", "IS_BLOCKING"),
                        help="Get partial completion strategy")
    parser.add_argument("--set-cap", nargs=2, metavar=("RUNNER", "DAILY_CAP"),
                        help="Set daily cap for a runner")
    parser.add_argument("--set-global-cap", type=float, help="Set global daily cap")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--reset", action="store_true", help="Reset budget window (start fresh)")
    args = parser.parse_args()

    if args.reset:
        state = BudgetState(
            window_start=datetime.now().isoformat(),
            daily_caps=dict(DAILY_CAPS),
            global_daily_cap=GLOBAL_DAILY_CAP,
        )
        _save_state(state)
        print("Budget window reset.")
        return

    if args.set_cap:
        update_caps(runner=args.set_cap[0], daily_cap=float(args.set_cap[1]))
        print(f"Cap for {args.set_cap[0]} set to ${float(args.set_cap[1]):.2f}/day")
        return

    if args.set_global_cap:
        update_caps(global_cap=args.set_global_cap)
        print(f"Global daily cap set to ${args.set_global_cap:.2f}")
        return

    if args.record:
        runner, model, cost, task_id = args.record
        status = record_spend(
            runner, model, float(cost), task_id,
            completed=args.completed,
            exit_code=args.exit_code if args.exit_code is not None else -1,
            tier=args.tier or "",
            duration_ms=args.duration_ms or 0,
        )
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(f"Recorded: ${float(cost):.4f} on {runner}/{model}")
            print(f"  {status['recommendation']}")
        return

    if args.check:
        runner, model, tier = args.check
        result = get_runner_allowance(runner, model, tier)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"{'✅ ALLOWED' if result['allowed'] else '❌ BLOCKED'}: {runner}/{model} for {tier}")
            print(f"  Max budget: ${result['max_budget']:.2f}")
            print(f"  Reason: {result['reason']}")
            if result.get('alternative'):
                alt = result['alternative']
                print(f"  Alternative: {alt['runner']}/{alt['model']} ({alt['reason']})")
        return

    if args.strategy:
        task_id, tier, is_blocking = args.strategy
        result = check_partial_completion_strategy(task_id, tier, is_blocking.lower() in ("true", "1", "yes"))
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Strategy: {result['strategy']}")
            print(f"  {result['reason']}")
            if 'max_budget' in result:
                print(f"  Max budget: ${result['max_budget']:.2f}")
        return

    # Default: show status
    status = get_budget_status()
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(f"\n  Budget Status — {status['budget_zone'].upper()}")
        print(f"  {status['recommendation']}")
        print(f"\n  Global: ${status['global_spent']:.2f} / ${status['global_cap']:.2f} ({status['global_pct']*100:.1f}%)")
        print(f"  Tasks today: {status['entries_today']}")
        if status['stuck_loop']:
            print(f"  ⚠️  STUCK LOOP: {status['stuck_loop_count']} consecutive failures")
        print()
        for runner, info in status['per_runner'].items():
            bar_len = 20
            filled = int(info['pct'] * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"  {runner:10s} [{bar}] ${info['spent']:.2f}/${info['cap']:.2f}")
        print()


if __name__ == "__main__":
    main()
