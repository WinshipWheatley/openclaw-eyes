#!/usr/bin/env python3
"""Smart runner profile selector for the polish loop.

Reads task metadata (YAML frontmatter from task.md) and returns the optimal
CLI invocation for the builder.  Called by builder_watcher.sh before each
launch.

Profiles (task tiers — determines parameters, NOT which tool to use)
--------
quick      – config tweak, typo, 1-2 file touch  → low effort, 120s, $0.25
surgical   – scoped fix, ≤3 files                → medium effort, 300s, $0.50
standard   – normal implementation                → high effort, 600s, $2.00
architect  – multi-file design, new subsystem     → max effort, 900s, $5.00

Runner selection is DYNAMIC via runner_registry.py — the system auto-discovers
which tools are installed and scores them per task tier.  If the registry is
unavailable, falls back to hardcoded Claude.

Detection order:
1. Explicit `profile:` in task frontmatter → used as-is
2. Heuristic from scope size, file count, keywords

Output (stdout): JSON with keys:
  runner, model, effort, timeout, budget, permission_mode, extra_flags,
  invoke_cmd, reason
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

TASK_FILE = Path("/home/openclaw/polish_loop/task.md")
STATUS_FILE = Path("/home/openclaw/polish_loop/status.json")

# ---------------------------------------------------------------------------
# Planner-mode adjustments — planner reviews builder output, doesn't build
# ---------------------------------------------------------------------------

PLANNER_PREFERRED_MODELS = {
    "quick": "sonnet",
    "surgical": "sonnet",
    "standard": "sonnet",
    "architect": "sonnet",   # planner rarely needs opus even for big reviews
}

PLANNER_BUDGET_SCALE = 0.5  # planner reviews cost ~half of building

# ---------------------------------------------------------------------------
# Profile definitions — task parameters only, runner is chosen dynamically
# ---------------------------------------------------------------------------

PROFILES: dict[str, dict] = {
    "quick": {
        "effort": "low",
        "timeout": 120,
        "budget": 0.25,
        "permission_mode": "auto",
        "extra_flags": [],
    },
    "surgical": {
        "effort": "medium",
        "timeout": 300,
        "budget": 0.50,
        "permission_mode": "auto",
        "extra_flags": [],
    },
    "standard": {
        "effort": "high",
        "timeout": 600,
        "budget": 2.00,
        "permission_mode": "auto",
        "extra_flags": [],
    },
    "architect": {
        "effort": "max",
        "timeout": 900,
        "budget": 5.00,
        "permission_mode": "auto",
        "extra_flags": [],
    },
}

# Preferred model per tier when the runner supports model selection
PREFERRED_MODELS = {
    "quick": "sonnet",
    "surgical": "sonnet",
    "standard": "sonnet",
    "architect": "opus",
}

DEFAULT_PROFILE = "standard"

# ---------------------------------------------------------------------------
# Keyword / heuristic signals
# ---------------------------------------------------------------------------

ARCHITECT_KEYWORDS = {
    "new subsystem", "architecture", "redesign", "refactor major",
    "multi-file", "new module", "new brain", "new listener",
    "new integration", "broker", "pipeline", "framework",
}

QUICK_KEYWORDS = {
    "typo", "config change", "flag flip", "toggle", "rename",
    "bump version", "update comment", "fix import", "env var",
}

SURGICAL_KEYWORDS = {
    "bug fix", "small fix", "patch", "one-liner", "guard",
    "regression", "edge case", "validation",
}


def _parse_frontmatter(text: str) -> dict:
    """Rough YAML-ish frontmatter parser (no PyYAML dependency)."""
    meta: dict = {}
    lines = text.strip().splitlines()

    current_key = ""
    current_list: list[str] = []
    current_scalar = ""
    in_list = False
    in_block = False

    for line in lines:
        # Stop at first markdown heading or blank-line-after-content
        if line.startswith("# "):
            break

        # List item
        if re.match(r"^- ", line):
            if in_list and current_key:
                current_list.append(line[2:].strip())
                continue
            # Start of a new list under previous key
            if current_key:
                in_list = True
                in_block = False
                current_list = [line[2:].strip()]
                continue

        # Block scalar continuation
        if in_block and (line.startswith("  ") or line.startswith("\t")):
            current_scalar += line.strip() + "\n"
            continue

        # Flush previous key
        if current_key:
            if in_list:
                meta[current_key] = current_list
            elif in_block:
                meta[current_key] = current_scalar.strip()
            in_list = False
            in_block = False
            current_list = []
            current_scalar = ""

        # New key: value pair
        m = re.match(r"^([a-z_][a-z0-9_ /()-]*):\s*(.*)", line, re.IGNORECASE)
        if m:
            current_key = m.group(1).strip().lower().replace(" ", "_")
            val = m.group(2).strip()
            if val == "|":
                in_block = True
                current_scalar = ""
            elif val and val.startswith("-"):
                # Inline list start?  rare
                meta[current_key] = val
            elif val:
                meta[current_key] = val
            else:
                # Value on next lines (list or block)
                pass
        elif not line.strip():
            # Blank line — flush
            if current_key:
                if in_list:
                    meta[current_key] = current_list
                elif in_block:
                    meta[current_key] = current_scalar.strip()
                in_list = False
                in_block = False
                current_list = []
                current_scalar = ""
                current_key = ""

    # Final flush
    if current_key:
        if in_list:
            meta[current_key] = current_list
        elif in_block:
            meta[current_key] = current_scalar.strip()

    return meta


def _count_files(meta: dict) -> int:
    """Count how many files the task expects to touch."""
    # Try multiple common key names
    for key in ("exact_files_likely_to_be_touched_first",
                "files", "files_to_touch", "exact_files"):
        files_field = meta.get(key)
        if files_field:
            break
    else:
        files_field = None

    if files_field is None:
        # Fallback: count file-like paths in the full text
        return 0
    if isinstance(files_field, list):
        return len(files_field)
    if isinstance(files_field, str):
        return len([l for l in files_field.splitlines() if l.strip()])
    return 0


def _scope_size(meta: dict) -> int:
    """Count scope bullet points.  Also counts lines in goal as complexity signal."""
    scope = meta.get("scope", [])
    if isinstance(scope, list):
        count = len(scope)
    elif isinstance(scope, str):
        count = len([l for l in scope.splitlines() if l.strip()])
    else:
        count = 0

    # Also look at raw text length as complexity signal
    full_text = str(meta.get("scope", "")) + str(meta.get("goal", ""))
    # Every 200 chars of scope/goal text ≈ +1 complexity point
    count += len(full_text) // 200
    return count


def _has_keywords(meta: dict, keywords: set[str]) -> bool:
    """Check if any keyword appears in goal, title, or scope text."""
    text = " ".join([
        str(meta.get("title", "")),
        str(meta.get("goal", "")),
        str(meta.get("scope", "")),
    ]).lower()
    return any(kw in text for kw in keywords)


def select_profile(task_text: str, *, planner_mode: bool = False) -> dict:
    """Select the best runner profile for the given task text.

    Returns a profile dict with all CLI parameters, chosen runner, and
    a fully-built invoke_cmd ready for shell execution.

    If planner_mode=True, adjusts for the Mac planner role:
      - Uses PLANNER_PREFERRED_MODELS (sonnet-heavy, opus only explicitly)
      - Scales budget down (reviews cost less than building)
      - Omits invoke_cmd (Mac builds its own with local paths)
      - Adds role="planner" to output
    """
    meta = _parse_frontmatter(task_text)

    # 1. Explicit profile override
    explicit = meta.get("profile", "").strip().lower()
    if explicit in PROFILES:
        tier = explicit
        reason_prefix = f"explicit profile: {explicit}"
    else:
        # 2. Heuristic detection
        file_count = _count_files(meta)
        scope_count = _scope_size(meta)

        if file_count >= 6 or scope_count >= 8 or _has_keywords(meta, ARCHITECT_KEYWORDS):
            tier = "architect"
            reason_prefix = f"auto-detected architect (files={file_count}, scope={scope_count})"
        elif _has_keywords(meta, SURGICAL_KEYWORDS) and scope_count <= 4:
            tier = "surgical"
            reason_prefix = f"auto-detected surgical (files={file_count}, scope={scope_count})"
        elif (file_count <= 1 and scope_count <= 2) or _has_keywords(meta, QUICK_KEYWORDS):
            if not _has_keywords(meta, SURGICAL_KEYWORDS):
                tier = "quick"
                reason_prefix = f"auto-detected quick (files={file_count}, scope={scope_count})"
            else:
                tier = DEFAULT_PROFILE
                reason_prefix = f"default standard (files={file_count}, scope={scope_count})"
        else:
            tier = DEFAULT_PROFILE
            reason_prefix = f"default standard (files={file_count}, scope={scope_count})"

    result = dict(PROFILES[tier])
    result["tier"] = tier
    result["role"] = "planner" if planner_mode else "builder"

    # Planner mode: scale budget down (reviews cost less)
    if planner_mode:
        result["budget"] = round(result["budget"] * PLANNER_BUDGET_SCALE, 2)

    # 3. Check if this is a blocking task (from frontmatter)
    is_blocking = meta.get("blocking", "").lower() in ("true", "yes", "1")
    task_id = meta.get("title", "unknown")

    # 4. Dynamic runner selection via registry + budget awareness
    model_prefs = PLANNER_PREFERRED_MODELS if planner_mode else PREFERRED_MODELS
    runner_name, model, runner_reason, budget_override = _pick_runner(
        tier, task_id, is_blocking, model_prefs=model_prefs
    )

    # Planner runs on Mac — ollama is PC-only; fall back to claude/sonnet
    if planner_mode and runner_name == "ollama":
        runner_name = "claude"
        model = model_prefs.get(tier, "sonnet")
        runner_reason += " → planner override: ollama unavailable on Mac"
        budget_override = None  # let default planner budget apply

    result["runner"] = runner_name
    result["model"] = model
    result["reason"] = f"{reason_prefix}; runner={runner_name} ({runner_reason})"

    # Budget tracker may override the per-task budget cap
    if budget_override is not None:
        result["budget"] = budget_override

    # 5. Check for task deferral (budget too low to even start)
    defer_info = _check_deferral(task_id, tier, is_blocking)
    if defer_info:
        result["defer"] = True
        result["defer_strategy"] = defer_info["strategy"]
        result["defer_reason"] = defer_info["reason"]
    else:
        result["defer"] = False

    # 6. Build the full invoke command (builder only — planner builds its own on Mac)
    if planner_mode:
        result["invoke_cmd"] = ""  # Mac planner_runner.py builds this with local paths
    else:
        prompt_file = str(Path("/home/openclaw/polish_loop/POLISH_PROMPT.md"))
        result["invoke_cmd"] = _build_invoke_cmd(runner_name, result, prompt_file)

    return result


def _check_deferral(task_id: str, tier: str, is_blocking: bool) -> Optional[dict]:
    """Check if task should be deferred due to budget constraints.

    Returns None if task should run, or a strategy dict if deferred.
    """
    try:
        import budget_tracker
        strategy = budget_tracker.check_partial_completion_strategy(task_id, tier, is_blocking)
        if strategy["strategy"] == "defer_to_next_window":
            return strategy
        if strategy["strategy"] == "partial_now_continue_later":
            # Not a full deferral — let it run with a note
            return None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Runner rotation — spread work across runners overnight
# ---------------------------------------------------------------------------

# After this many consecutive tasks on the SAME cloud runner, try the next one.
# Doesn't apply to ollama (free/local) or architect tier (needs the best).
ROTATION_THRESHOLD = 3


def _get_recent_runner_streak() -> tuple[str, int]:
    """Check how many consecutive recent tasks used the same runner.

    Returns (runner_name, streak_count).  Returns ("", 0) if no history.
    """
    try:
        import budget_tracker
        state = budget_tracker._load_state()
        entries = state.entries
        if not entries:
            return ("", 0)

        # Walk backwards through entries to find the streak
        last_runner = entries[-1].get("runner", "")
        if not last_runner:
            return ("", 0)

        streak = 0
        for entry in reversed(entries):
            if entry.get("runner", "") == last_runner:
                streak += 1
            else:
                break

        return (last_runner, streak)
    except Exception:
        return ("", 0)


def _apply_rotation(ranked_runners: list, tier: str) -> list:
    """Reorder runners to spread work when one runner dominates.

    Rules:
      - Only activates after ROTATION_THRESHOLD consecutive tasks on same runner
      - Never rotates for architect tier (needs the best tool available)
      - Only promotes cloud runners (won't force-promote ollama for standard work)
      - The promoted runner must be within a competitive score range
      - Rotation is a soft preference, not mandatory — budget checks still apply
    """
    if tier == "architect":
        return ranked_runners  # architect always gets the best

    if len(ranked_runners) < 2:
        return ranked_runners

    last_runner, streak = _get_recent_runner_streak()
    if streak < ROTATION_THRESHOLD:
        return ranked_runners

    top = ranked_runners[0]
    if top.name != last_runner:
        return ranked_runners  # top pick is already different

    # Find the best alternative that's NOT the streak runner and NOT local
    try:
        import runner_registry as rr
        top_score = rr._score_runner_for_task(top, tier)

        for i, candidate in enumerate(ranked_runners[1:], 1):
            if candidate.runner_type == "local":
                continue  # don't promote local for paid-tier work
            alt_score = rr._score_runner_for_task(candidate, tier)
            # Only promote if within reasonable range (not a terrible fit)
            if alt_score >= top_score * 0.5:
                # Swap: promote this runner to #1
                rotated = list(ranked_runners)
                rotated.insert(0, rotated.pop(i))
                return rotated
    except Exception:
        pass

    return ranked_runners


def _pick_runner(tier: str, task_id: str = "unknown", is_blocking: bool = False,
                  *, model_prefs: Optional[dict] = None) -> tuple[str, str, str, Optional[float]]:
    """Pick the best available runner for a task tier, budget-aware + rotation.

    Returns (runner_name, model, reason_fragment, budget_override_or_None).
    Falls back to claude/sonnet if registry unavailable.
    """
    if model_prefs is None:
        model_prefs = PREFERRED_MODELS
    budget_override = None

    # Step 1: Get registry ranking
    ranked_runners = []
    try:
        import runner_registry
        ranked_runners = runner_registry.get_runners_for_task(tier)
    except Exception:
        pass

    if not ranked_runners:
        model = model_prefs.get(tier, "sonnet")
        return ("claude", model, "fallback — registry unavailable", None)

    # Step 2: Apply rotation — if top runner has been used too many times
    # consecutively, promote the next-best runner that's within competitive range
    ranked_runners = _apply_rotation(ranked_runners, tier)

    # Step 3: Check budget for each candidate until we find one that's allowed
    try:
        import budget_tracker
        for candidate in ranked_runners:
            preferred_model = model_prefs.get(tier, "sonnet")
            if candidate.models and preferred_model in candidate.models:
                model = preferred_model
            elif candidate.models:
                model = candidate.models[0]
            else:
                model = "default"

            allowance = budget_tracker.get_runner_allowance(candidate.name, model, tier)

            if allowance["allowed"]:
                import runner_registry as rr
                score = rr._score_runner_for_task(candidate, tier)
                budget_override = allowance["max_budget"]
                return (
                    candidate.name,
                    model,
                    f"registry score={score:.0f}, budget={allowance['reason']}",
                    budget_override,
                )

            # Not allowed — check if there's a suggested alternative
            alt = allowance.get("alternative")
            if alt:
                # Try the alternative directly
                alt_runner = alt["runner"]
                alt_model = alt.get("model", "default")
                alt_allowance = budget_tracker.get_runner_allowance(alt_runner, alt_model, tier)
                if alt_allowance["allowed"]:
                    budget_override = alt_allowance["max_budget"]
                    return (
                        alt_runner,
                        alt_model,
                        f"budget downgrade from {candidate.name}/{model}: {alt.get('reason', 'budget')}",
                        budget_override,
                    )

        # All runners rejected by budget — fall back to free local
        return ("ollama", "qwen2.5-coder:14b", "all paid runners over budget — free local fallback", 0)

    except ImportError:
        pass  # budget_tracker not available — skip budget checks

    # No budget tracker — use registry ranking without budget awareness
    best = ranked_runners[0]
    try:
        import runner_registry as rr
        score = rr._score_runner_for_task(best, tier)
    except Exception:
        score = 0

    preferred_model = model_prefs.get(tier, "sonnet")
    if best.models and preferred_model in best.models:
        model = preferred_model
    elif best.models:
        model = best.models[0]
    else:
        model = "default"

    return (best.name, model, f"registry score={score:.0f}", None)


def _build_invoke_cmd(runner_name: str, profile: dict, prompt_file: str) -> str:
    """Build a shell-ready invoke command for ANY runner.

    Uses the runner's invoke_pattern from the registry if available,
    otherwise falls back to known patterns.
    """
    timeout = profile["timeout"]
    model = profile["model"]
    effort = profile.get("effort", "high")
    budget = profile.get("budget", 2.0)

    # Try to get invoke_pattern from registry
    invoke_pattern = None
    try:
        import runner_registry
        runner = runner_registry.get_runner(runner_name)
        if runner and runner.invoke_pattern:
            invoke_pattern = runner.invoke_pattern
    except Exception:
        pass

    if invoke_pattern:
        # Substitute template variables
        fallback_model = "haiku" if model == "sonnet" else "sonnet"
        cmd = invoke_pattern.format(
            timeout=timeout,
            model=model,
            effort=effort,
            budget=budget,
            prompt_file=prompt_file,
            fallback_model=fallback_model,
        )
        return cmd

    # Hardcoded fallback patterns (only claude and codex)
    if runner_name == "codex":
        return f'setsid timeout {timeout} codex exec "$(cat {prompt_file})"'
    else:
        fallback_model = "haiku" if model == "sonnet" else "sonnet"
        return (
            f"setsid timeout {timeout} claude"
            f" --model {model} --effort {effort}"
            f" --dangerously-skip-permissions --print"
            f" --max-budget-usd {budget} --fallback-model {fallback_model}"
            f" < {prompt_file}"
        )


def main():
    """CLI entry point — reads task.md and prints profile JSON to stdout.

    Flags:
      --planner-mode   Select profile for the Mac planner role (review, not build)
      --task-stdin     Read task text from stdin instead of task.md file
      --tier TIER      Force a specific tier (skip heuristic detection)
    """
    import argparse
    parser = argparse.ArgumentParser(description="Smart runner profile selector")
    parser.add_argument("--planner-mode", action="store_true",
                        help="Select profile for Mac planner role")
    parser.add_argument("--task-stdin", action="store_true",
                        help="Read task text from stdin instead of task.md")
    parser.add_argument("--tier", type=str, choices=list(PROFILES.keys()),
                        help="Force a specific task tier")
    args = parser.parse_args()

    planner_mode = args.planner_mode

    # Get task text
    if args.task_stdin:
        task_text = sys.stdin.read()
    elif TASK_FILE.exists():
        task_text = TASK_FILE.read_text()
    else:
        task_text = ""

    if not task_text.strip():
        # No task — return default with dynamic runner
        tier = args.tier or DEFAULT_PROFILE
        result = dict(PROFILES[tier])
        result["tier"] = tier
        result["role"] = "planner" if planner_mode else "builder"
        if planner_mode:
            result["budget"] = round(result["budget"] * PLANNER_BUDGET_SCALE, 2)
        model_prefs = PLANNER_PREFERRED_MODELS if planner_mode else PREFERRED_MODELS
        runner_name, model, runner_reason, budget_override = _pick_runner(
            tier, model_prefs=model_prefs
        )
        # Planner runs on Mac — ollama is PC-only
        if planner_mode and runner_name == "ollama":
            runner_name = "claude"
            model = model_prefs.get(tier, "sonnet")
            runner_reason += " → planner override: ollama unavailable on Mac"
            budget_override = None
        result["runner"] = runner_name
        result["model"] = model
        result["reason"] = f"no task text, using default; runner={runner_name} ({runner_reason})"
        result["defer"] = False
        if budget_override is not None:
            result["budget"] = budget_override
        if not planner_mode:
            prompt_file = str(Path("/home/openclaw/polish_loop/POLISH_PROMPT.md"))
            result["invoke_cmd"] = _build_invoke_cmd(runner_name, result, prompt_file)
        else:
            result["invoke_cmd"] = ""
        print(json.dumps(result))
        return

    # If --tier is forced, inject it into the task text as frontmatter
    if args.tier:
        task_text = f"profile: {args.tier}\n{task_text}"

    profile = select_profile(task_text, planner_mode=planner_mode)
    print(json.dumps(profile))


if __name__ == "__main__":
    main()
