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

TASK_FILE = Path("/home/openclaw/polish_loop/task.md")
STATUS_FILE = Path("/home/openclaw/polish_loop/status.json")

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


def select_profile(task_text: str) -> dict:
    """Select the best runner profile for the given task text.

    Returns a profile dict with all CLI parameters, chosen runner, and
    a fully-built invoke_cmd ready for shell execution.
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

    # 3. Dynamic runner selection via registry
    runner_name, model, runner_reason = _pick_runner(tier)
    result["runner"] = runner_name
    result["model"] = model
    result["reason"] = f"{reason_prefix}; runner={runner_name} ({runner_reason})"

    # 4. Build the full invoke command
    prompt_file = str(Path("/home/openclaw/polish_loop/POLISH_PROMPT.md"))
    result["invoke_cmd"] = _build_invoke_cmd(runner_name, result, prompt_file)

    return result


def _pick_runner(tier: str) -> tuple[str, str, str]:
    """Pick the best available runner for a task tier.

    Returns (runner_name, model, reason_fragment).
    Falls back to claude/sonnet if registry unavailable.
    """
    try:
        import runner_registry
        ranked = runner_registry.get_runners_for_task(tier)
        if ranked:
            best = ranked[0]
            score = runner_registry._score_runner_for_task(best, tier)

            # Pick model: prefer tier-specific model if runner supports it
            preferred_model = PREFERRED_MODELS.get(tier, "sonnet")
            if best.models and preferred_model in best.models:
                model = preferred_model
            elif best.models:
                model = best.models[0]
            else:
                model = "default"

            return (best.name, model, f"registry score={score:.0f}")
    except Exception as e:
        pass  # Registry unavailable — fall back

    # Hardcoded fallback
    model = PREFERRED_MODELS.get(tier, "sonnet")
    return ("claude", model, "fallback — registry unavailable")


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
        cmd = invoke_pattern.format(
            timeout=timeout,
            model=model,
            effort=effort,
            budget=budget,
            prompt_file=prompt_file,
        )
        return cmd

    # Hardcoded fallback patterns (only claude and codex)
    if runner_name == "codex":
        return f'setsid timeout {timeout} codex exec "$(cat {prompt_file})"'
    else:
        return (
            f"setsid timeout {timeout} claude"
            f" --model {model} --effort {effort}"
            f" --dangerously-skip-permissions --print"
            f" --max-budget-usd {budget} --fallback-model sonnet"
            f" < {prompt_file}"
        )


def main():
    """CLI entry point — reads task.md and prints profile JSON to stdout."""
    if not TASK_FILE.exists():
        # No task — return default with dynamic runner
        tier = DEFAULT_PROFILE
        result = dict(PROFILES[tier])
        result["tier"] = tier
        runner_name, model, runner_reason = _pick_runner(tier)
        result["runner"] = runner_name
        result["model"] = model
        result["reason"] = f"no task.md found, using default; runner={runner_name} ({runner_reason})"
        prompt_file = str(Path("/home/openclaw/polish_loop/POLISH_PROMPT.md"))
        result["invoke_cmd"] = _build_invoke_cmd(runner_name, result, prompt_file)
        print(json.dumps(result))
        return

    task_text = TASK_FILE.read_text()
    profile = select_profile(task_text)
    print(json.dumps(profile))


if __name__ == "__main__":
    main()
