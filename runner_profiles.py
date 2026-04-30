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
which approved tools are installed and scores them per task tier.  If the
registry is unavailable, falls back to Codex.

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

from chief_llm import (
    EXTERNAL_MODEL_BLOCK_MARKERS,
    EXTERNAL_MODEL_SAFE_CLASSIFICATIONS,
    external_model_packet_policy,
)

TASK_FILE_CANDIDATES = (
    Path("/home/openclaw/polish_loop/current/task.md"),
    Path("/home/openclaw/polish_loop/task.md"),
)
STATUS_FILE = Path("/home/openclaw/polish_loop/status.json")
TASK_QUEUE_DIR = Path("/home/openclaw/polish_loop/tasks")
ARCHIVE_DIR = Path("/home/openclaw/polish_loop/archive")


def _get_task_file() -> Path:
    """Return the live task file path, preferring the canonical current/ path."""
    for path in TASK_FILE_CANDIDATES:
        if path.exists():
            return path
    return TASK_FILE_CANDIDATES[0]

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
# Autonomous runner policy (2026-04-04)
#   Gemini = planner, Codex = builder. Claude CLI is human-only and must never
#   be selected for autonomous loop spawning.
# ---------------------------------------------------------------------------
HUMAN_ONLY_RUNNERS = {"claude"}
AUTONOMOUS_BLOCKED_RUNNERS = set(HUMAN_ONLY_RUNNERS)
AUTONOMOUS_BUILDER_BLOCKED_RUNNERS = AUTONOMOUS_BLOCKED_RUNNERS | {"gemini", "aider", "ollama"}

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

MAX_CASCADE_CHILDREN = 5

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


def _as_list(value) -> list[str]:
    """Normalize frontmatter field values to a clean list of strings."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [line.strip("- ").strip() for line in value.splitlines() if line.strip()]
    return []


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", text.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60] or "task"


def _is_completed_task(task_name: str) -> bool:
    if not ARCHIVE_DIR.exists():
        return False
    return any(ARCHIVE_DIR.glob(f"task_{task_name}_*"))


def _cascade_child_exists(task_name: str) -> bool:
    return (TASK_QUEUE_DIR / f"{task_name}.md").exists() or _is_completed_task(task_name)


def _build_child_chunks(scope_items: list[str], max_children: int = MAX_CASCADE_CHILDREN) -> list[list[str]]:
    """Chunk scope bullets into bounded child-task scopes."""
    if not scope_items:
        return []
    # Prefer 2-3 bullets per child to keep chunks executable by lower-tier runners.
    chunk_size = 3 if len(scope_items) >= 6 else 2
    chunks: list[list[str]] = []
    for i in range(0, len(scope_items), chunk_size):
        chunks.append(scope_items[i:i + chunk_size])
        if len(chunks) >= max_children:
            break
    return chunks


def _queue_cascade_children(meta: dict, parent_tier: str, task_id: str) -> list[str]:
    """Queue smaller child tasks for budget-edge high-tier work.

    Architect -> standard children
    Standard  -> surgical children
    """
    if parent_tier not in ("architect", "standard"):
        return []

    scope_items = _as_list(meta.get("scope"))
    success_items = _as_list(meta.get("success"))
    if not scope_items:
        return []

    child_tier = "standard" if parent_tier == "architect" else "surgical"
    parent_title = str(meta.get("title", task_id or "task")).strip() or "task"
    parent_slug = _safe_slug(parent_title)
    chunks = _build_child_chunks(scope_items)
    if not chunks:
        return []

    TASK_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        child_name = f"cascade-{parent_slug}-{idx:02d}"
        if _cascade_child_exists(child_name):
            continue

        scope_lines = "\n".join(f"- {line}" for line in chunk)
        success_line = success_items[0] if success_items else "Child scope completed and verified."
        body = (
            f"title: {child_name}\n"
            f"profile: {child_tier}\n"
            f"goal: Execute child chunk {idx} of parent task '{parent_title}'\n"
            f"parent_task: {parent_title}\n"
            f"scope:\n"
            f"{scope_lines}\n"
            f"- Keep changes bounded and reviewable\n"
            f"success:\n"
            f"- {success_line}\n"
            f"- Child task is complete with clear verification notes\n"
            f"generated_by: cascade_decomposition\n"
        )
        (TASK_QUEUE_DIR / f"{child_name}.md").write_text(body)
        created.append(child_name)

    return created


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
    result["cloud_allowed"] = _task_allows_cloud(meta)
    if _task_is_sensitive(meta):
        result["cloud_policy"] = "local_only_sensitive"
    elif result["cloud_allowed"]:
        result["cloud_policy"] = "cloud_allowed"
    else:
        result["cloud_policy"] = "local_only_unclassified"

    # Planner mode: scale budget down (reviews cost less)
    if planner_mode:
        result["budget"] = round(result["budget"] * PLANNER_BUDGET_SCALE, 2)

    # 3. Check if this is a blocking task (from frontmatter)
    is_blocking = meta.get("blocking", "").lower() in ("true", "yes", "1")
    task_id = meta.get("title", "unknown")

    # 4. Dynamic runner selection via registry + budget awareness
    model_prefs = PLANNER_PREFERRED_MODELS if planner_mode else PREFERRED_MODELS
    blocked_runners = AUTONOMOUS_BLOCKED_RUNNERS if planner_mode else AUTONOMOUS_BUILDER_BLOCKED_RUNNERS
    runner_name, model, runner_reason, budget_override = _pick_runner(
        tier, task_id, is_blocking, model_prefs=model_prefs,
        task_text=task_text, task_meta=meta,
        blocked_runners=blocked_runners,
    )

    # Planner policy surface: Gemini is the planner runner on Mac.
    # TODO: the real Mac-side launcher is outside this repo, so Gemini
    # invocation remains unverified here; only the routing surface is enforced.
    if planner_mode and runner_name != "gemini":
        runner_name = "gemini"
        model = "default"
        runner_reason += " → planner policy override: gemini required on Mac planner surface"
        budget_override = None  # let default planner budget apply

    result["runner"] = runner_name
    result["model"] = model
    result["reason"] = f"{reason_prefix}; runner={runner_name} ({runner_reason})"

    # 4b. Cascade decomposition path for budget-edge high-tier work.
    # If a big task is near/over budget, break it down so lower-tier runners can execute well.
    budget_edge = (
        "budget downgrade" in runner_reason.lower()
        or "over budget" in runner_reason.lower()
    )
    if (not planner_mode) and tier in ("architect", "standard") and budget_edge:
        children = _queue_cascade_children(meta, tier, str(task_id))
        if children:
            result["defer"] = True
            result["defer_strategy"] = "cascade_decomposition"
            result["defer_reason"] = (
                f"budget-edge {tier} task decomposed into {len(children)} child tasks for lower-tier execution"
            )
            result["cascade_decomposed"] = True
            result["cascade_child_count"] = len(children)
            result["cascade_children"] = children
            result["reason"] += f"; cascade queued {len(children)} child tasks"

    # Budget tracker may override the per-task budget cap
    if budget_override is not None:
        result["budget"] = budget_override

    # 5. Check for task deferral (budget too low to even start)
    defer_info = _check_deferral(task_id, tier, is_blocking)
    if defer_info and not result.get("defer", False):
        result["defer"] = True
        result["defer_strategy"] = defer_info["strategy"]
        result["defer_reason"] = defer_info["reason"]
    elif not result.get("defer", False):
        result["defer"] = False

    # 6. Build the full invoke command (builder only — Mac planner launch is external)
    if planner_mode:
        result["invoke_cmd"] = ""  # External Mac-side planner launcher is not present in this repo
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
# Runner rotation — ratio-based with queue look-ahead
# ---------------------------------------------------------------------------

# Standard-tier cost rotation can promote Gemini among approved candidates.
STANDARD_GEMINI_RATIO = (2, 1)  # (primary_share, gemini_share)

TASK_QUEUE_DIR = Path("/home/openclaw/polish_loop/tasks")
ARCHIVE_DIR = Path("/home/openclaw/polish_loop/archive")

CLOUD_CAPABLE_RUNNERS = {"aider", "codex", "gemini"}
CLOUD_ALLOWED_CLASSIFICATIONS = set(EXTERNAL_MODEL_SAFE_CLASSIFICATIONS)

# Keywords that signal sensitive data requiring local-only processing
SENSITIVE_KEYWORDS = set(EXTERNAL_MODEL_BLOCK_MARKERS)


def _truthy(value) -> bool:
    return str(value).strip().lower() in ("true", "yes", "1", "y", "on")


def _normalize_policy_value(value) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _policy_text(value) -> str:
    if isinstance(value, dict):
        return " ".join(_policy_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_policy_text(v) for v in value)
    return str(value)


def _task_is_sensitive(meta: dict) -> bool:
    """Check if a task requires local-only processing for data sensitivity."""
    return bool(external_model_packet_policy(meta, metadata=meta).get("sensitive"))


def _task_allows_cloud(meta: dict) -> bool:
    """Require explicit non-sensitive classification before cloud runners."""
    if not meta:
        return False
    return bool(external_model_packet_policy(meta, metadata=meta).get("external_model_safe"))


def _get_recent_runner_ratio(runner_a: str = "codex", runner_b: str = "gemini",
                              window: int = 6) -> tuple[int, int]:
    """Count recent tasks assigned to runner_a vs runner_b.

    Looks at the last `window` budget_tracker entries (roughly the last
    batch of tasks).  Returns (count_a, count_b).
    """
    try:
        import budget_tracker
        state = budget_tracker._load_state()
        entries = state.entries[-window:] if state.entries else []
        a = sum(1 for e in entries if e.get("runner") == runner_a)
        b = sum(1 for e in entries if e.get("runner") == runner_b)
        return (a, b)
    except Exception:
        return (0, 0)


def _estimate_task_complexity(task_text: str) -> int:
    """Quick complexity score from task text.  Lower = easier.

    Used to decide which task in a batch should go to gemini.
    """
    meta = _parse_frontmatter(task_text)
    files = _count_files(meta)
    scope = _scope_size(meta)
    # Simple composite: files + scope bullets
    return files + scope


def _should_gemini_take_this(task_text: str, tier: str) -> bool:
    """Decide if this standard-tier task should go to gemini.

        Logic:
            1. Check the legacy cloud-runner ratio — is it gemini's turn?
      2. If yes, peek at upcoming queued tasks.  If this task is the
         easiest in the next batch of 3, gemini takes it.  Otherwise
         wait for an easier one.
      3. If the queue is empty (this is the only task), and it's
         gemini's turn by ratio, gemini takes it regardless.
    """
    if tier != "standard":
        return False

    # Check ratio
    primary_count, gemini_count = _get_recent_runner_ratio("codex", "gemini")
    target_primary, target_gemini = STANDARD_GEMINI_RATIO
    total = primary_count + gemini_count

    # Determine if gemini is "due" a task
    if total == 0:
        # Fresh start — keep the current approved ranking.
        return False

    # Current gemini share vs target share
    target_gemini_pct = target_gemini / (target_primary + target_gemini)  # 0.333
    actual_gemini_pct = gemini_count / total if total > 0 else 0

    if actual_gemini_pct >= target_gemini_pct:
        # Gemini has had enough turns — keep the current approved ranking.
        return False

    # Gemini is under-represented.  Check queue to find easiest task.
    current_complexity = _estimate_task_complexity(task_text)

    # Peek at queued tasks
    queue_complexities = []
    if TASK_QUEUE_DIR.exists():
        # Build skip set (same logic as orchestrator)
        skip_names = {"env-001-install.md", "env-001-spec-tools.md"}
        completed_names: set[str] = set()
        if ARCHIVE_DIR.exists():
            for archived in ARCHIVE_DIR.glob("task_*"):
                parts = archived.stem.split("_", 1)
                if len(parts) > 1:
                    name_part = parts[1].rsplit("_", 1)[0]
                    completed_names.add(name_part)

        for qf in sorted(TASK_QUEUE_DIR.glob("*.md"), key=lambda p: p.name):
            if qf.name in skip_names or qf.stem in completed_names:
                continue
            try:
                qtxt = qf.read_text()
                qmeta = _parse_frontmatter(qtxt)
                # Only consider standard-tier tasks
                qprofile = qmeta.get("profile", "").strip().lower()
                if qprofile and qprofile != "standard":
                    continue
                # Quick heuristic: if it looks like architect or quick, skip
                qfiles = _count_files(qmeta)
                qscope = _scope_size(qmeta)
                if qfiles >= 6 or qscope >= 8:
                    continue  # likely architect
                if qfiles <= 1 and qscope <= 2:
                    continue  # likely quick
                queue_complexities.append(qfiles + qscope)
            except Exception:
                continue
            if len(queue_complexities) >= 2:
                break  # only peek at next 2

    if not queue_complexities:
        # No upcoming standard tasks — gemini takes this one (it's due)
        return True

    # Is this the easiest in the batch?
    all_complexities = [current_complexity] + queue_complexities
    min_complexity = min(all_complexities)
    if current_complexity <= min_complexity:
        return True  # this is the easiest — gemini gets it

    # This isn't the easiest — save gemini for an easier upcoming task
    return False


def _apply_rotation(ranked_runners: list, tier: str, task_text: str = "") -> list:
    """Reorder runners based on ratio targets and task complexity.

    Standard tier: legacy ratio can promote Gemini for the easiest task in a
    batch after human-only runners have already been filtered.

    Surgical tier: registry ranking after human-only runner filtering.

    Architect tier: no rotation — always picks best tool.

    Quick tier: gemini is already the scoring winner.  Ollama only wins when
    local_required/sensitive flag is set (handled in _pick_runner).
    """
    if tier == "architect":
        return ranked_runners  # architect always gets the best

    if tier == "standard" and len(ranked_runners) >= 2:
        # Ratio-based: should gemini take this task?
        if _should_gemini_take_this(task_text, tier):
            # Promote gemini to #1
            for i, r in enumerate(ranked_runners):
                if r.name == "gemini":
                    rotated = list(ranked_runners)
                    rotated.insert(0, rotated.pop(i))
                    return rotated

    # For other tiers, no rotation needed — scoring handles it
    return ranked_runners


_HEADROOM_POLICY_FILE = Path("/home/openclaw/headroom_routing_policy.json")
_headroom_policy_cache: Optional[dict] = None
_headroom_policy_mtime: float = 0.0


def _load_headroom_policy() -> dict:
    """Load (and cache) headroom_routing_policy.json. Reloads if mtime changes."""
    global _headroom_policy_cache, _headroom_policy_mtime
    try:
        mtime = _HEADROOM_POLICY_FILE.stat().st_mtime
        if _headroom_policy_cache is not None and mtime <= _headroom_policy_mtime:
            return _headroom_policy_cache
        _headroom_policy_cache = json.loads(_HEADROOM_POLICY_FILE.read_text())
        _headroom_policy_mtime = mtime
        return _headroom_policy_cache
    except Exception:
        return {}


def _check_headroom_policy(runner: str, tier: str, task_meta: dict) -> dict:
    """Check if provider headroom allows this runner for this tier.

    Returns:
        {"allow": bool, "reason": str, "headroom_state": dict}

    When headroom data is unavailable for a provider, returns allow=True
    with reason="headroom_unknown_passthrough". The system never blocks
    a runner solely because headroom data is missing.
    """
    try:
        policy = _load_headroom_policy()
        if not policy:
            return {"allow": True, "reason": "headroom_check_error_passthrough",
                    "headroom_state": {"provenance": "policy_missing"}}

        provider_policy = policy.get("providers", {}).get(runner)
        if provider_policy is None:
            return {"allow": True, "reason": f"headroom_unknown: {runner} (not in policy)",
                    "headroom_state": {"provenance": "unavailable"}}

        # Passthrough / always-allow policies
        runner_policy_type = provider_policy.get("policy", "")
        if runner_policy_type == "always_allow_local":
            return {"allow": True,
                    "reason": f"headroom_unknown: {runner} (local, no limits)",
                    "headroom_state": {"provenance": "not_applicable"}}
        if runner_policy_type == "passthrough_to_budget_zone":
            return {"allow": True,
                    "reason": f"headroom_unknown: {runner} (passthrough)",
                    "headroom_state": {"provenance": "unavailable"}}

        # Provider has real headroom config — fetch actual headroom data
        try:
            from cost_truth_surface import get_headroom
            headroom = get_headroom()
        except Exception:
            return {"allow": True, "reason": "headroom_check_error_passthrough",
                    "headroom_state": {"provenance": "error"}}

        provider_headroom = headroom.get(runner, {})
        if not provider_headroom.get("available", False):
            return {"allow": True,
                    "reason": f"headroom_unknown: {runner} (passthrough)",
                    "headroom_state": {"provenance": "unavailable"}}

        # Real headroom data available — check each rate limit window
        rate_limits = provider_headroom.get("rate_limits", {})
        for wslug, wdata in rate_limits.items():
            used_pct = wdata.get("used_percentage")
            if used_pct is None:
                continue

            wname = wdata.get("window", "").lower()
            wslug_lower = wslug.lower()
            # Detect window type from name/slug
            is_short = any(x in wslug_lower or x in wname
                           for x in ["5h", "5-h", "five", "hour"])
            is_long = any(x in wslug_lower or x in wname
                          for x in ["7d", "7-d", "seven", "day", "week"])
            if is_short:
                window_config = provider_policy.get("five_hour_window", {})
            elif is_long:
                window_config = provider_policy.get("seven_day_window", {})
            else:
                # Unknown window — apply most conservative configured threshold
                five_h = provider_policy.get("five_hour_window", {})
                seven_d = provider_policy.get("seven_day_window", {})
                window_config = (five_h if five_h.get("divert_above_pct", 100)
                                 <= seven_d.get("divert_above_pct", 100) else seven_d)

            if not window_config:
                continue

            divert_pct = window_config.get("divert_above_pct", 100)
            reserve_tiers = window_config.get("reserve_for_tiers", [])
            if used_pct > divert_pct and tier not in reserve_tiers:
                divert_to = window_config.get("divert_to", [])
                dest = divert_to[0] if divert_to else "other"
                display = wdata.get("window", wslug)
                return {
                    "allow": False,
                    "reason": f"headroom_divert: {runner} {display}@{used_pct:.0f}%\u2192{dest}",
                    "headroom_state": provider_headroom,
                }

        # All windows within threshold — report first window's usage for context
        first_pct = None
        first_label = None
        for wslug, wdata in rate_limits.items():
            pct = wdata.get("used_percentage")
            if pct is not None:
                first_pct = pct
                first_label = wdata.get("window", wslug)
                break

        reason = (f"headroom_ok: {runner} {first_label}@{first_pct:.0f}%"
                  if first_pct is not None else f"headroom_ok: {runner}")
        return {"allow": True, "reason": reason, "headroom_state": provider_headroom}

    except Exception:
        return {"allow": True, "reason": "headroom_check_error_passthrough",
                "headroom_state": {"provenance": "error"}}


def _pick_runner(tier: str, task_id: str = "unknown", is_blocking: bool = False,
                  *, model_prefs: Optional[dict] = None,
                  task_text: str = "", task_meta: Optional[dict] = None,
                  blocked_runners: Optional[set[str]] = None,
                  ) -> tuple[str, str, str, Optional[float]]:
    """Pick the best available runner for a task tier, budget-aware + rotation.

    Returns (runner_name, model, reason_fragment, budget_override_or_None).
    Falls back to codex if registry unavailable.
    """
    if model_prefs is None:
        model_prefs = PREFERRED_MODELS
    if blocked_runners is None:
        blocked_runners = AUTONOMOUS_BLOCKED_RUNNERS
    budget_override = None

    # Step 0: Cloud admission gate. Sensitive and unclassified tasks stay local.
    if task_meta and _task_is_sensitive(task_meta):
        return ("ollama", "chief-fast:latest",
                "sensitive data — local-only required", 0)
    if task_meta and not _task_allows_cloud(task_meta):
        return ("ollama", "chief-fast:latest",
                "cloud not explicitly allowed — local-only required", 0)

    # Step 1: Get registry ranking
    ranked_runners = []
    try:
        import runner_registry
        ranked_runners = runner_registry.get_runners_for_task(tier)
    except Exception:
        pass

    if not ranked_runners:
        model = model_prefs.get(tier, "sonnet")
        return ("codex", model, "fallback — registry unavailable", None)

    # Step 1b: Filter out autonomously-blocked runners (e.g. claude)
    ranked_runners = [r for r in ranked_runners if r.name not in blocked_runners]
    if not ranked_runners:
        return ("codex", "default", "all candidates blocked by runner policy", None)

    # Step 2: Apply ratio-based rotation for standard tier
    ranked_runners = _apply_rotation(ranked_runners, tier, task_text)

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

            # --- headroom gate: check before spending a budget-allowance query ---
            headroom_result = _check_headroom_policy(candidate.name, tier, task_meta or {})
            if not headroom_result["allow"]:
                # Headroom too low for this tier — skip and try next candidate
                continue
            # --- end headroom gate ---

            allowance = budget_tracker.get_runner_allowance(candidate.name, model, tier)

            if allowance["allowed"]:
                import runner_registry as rr
                score = rr._score_runner_for_task(candidate, tier)
                budget_override = allowance["max_budget"]
                return (
                    candidate.name,
                    model,
                    f"registry score={score:.0f}, budget={allowance['reason']} | {headroom_result['reason']}",
                    budget_override,
                )

            # Not allowed — check if there's a suggested alternative
            alt = allowance.get("alternative")
            if alt:
                # Try the alternative directly
                alt_runner = alt["runner"]
                if alt_runner in blocked_runners or alt_runner in HUMAN_ONLY_RUNNERS:
                    continue
                alt_model = alt.get("model", "default")
                alt_allowance = budget_tracker.get_runner_allowance(alt_runner, alt_model, tier)
                if alt_allowance["allowed"]:
                    budget_override = alt_allowance["max_budget"]
                    return (
                        alt_runner,
                        alt_model,
                        f"budget downgrade from {candidate.name}/{model}: {alt.get('reason', 'budget')} | {headroom_result['reason']}",
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

    if runner_name == "codex":
        return f'setsid timeout {timeout} codex exec --sandbox workspace-write - < "{prompt_file}"'

    if runner_name == "gemini":
        return f'setsid timeout {timeout} gemini --prompt "$(cat {prompt_file})" --yolo --output-format text'

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

    # Hardcoded fallback patterns — codex is the default autonomous builder
    if runner_name == "codex":
        return f'setsid timeout {timeout} codex exec --sandbox workspace-write - < "{prompt_file}"'
    elif runner_name == "gemini":
        return f'setsid timeout {timeout} gemini --prompt "$(cat {prompt_file})" --yolo --output-format text'
    else:
        # Unexpected runner — use codex as safe default (claude blocked from autonomous use)
        return f'setsid timeout {timeout} codex exec --sandbox workspace-write - < "{prompt_file}"'


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
    else:
        task_file = _get_task_file()
        task_text = task_file.read_text() if task_file.exists() else ""

    if not task_text.strip():
        # No task — return default with dynamic runner
        tier = args.tier or DEFAULT_PROFILE
        result = dict(PROFILES[tier])
        result["tier"] = tier
        result["role"] = "planner" if planner_mode else "builder"
        if planner_mode:
            result["budget"] = round(result["budget"] * PLANNER_BUDGET_SCALE, 2)
        model_prefs = PLANNER_PREFERRED_MODELS if planner_mode else PREFERRED_MODELS
        blocked_runners = AUTONOMOUS_BLOCKED_RUNNERS if planner_mode else AUTONOMOUS_BUILDER_BLOCKED_RUNNERS
        runner_name, model, runner_reason, budget_override = _pick_runner(
            tier, model_prefs=model_prefs, blocked_runners=blocked_runners
        )
        # Planner policy surface: Gemini is the planner runner on Mac.
        # TODO: the real Mac-side launcher is outside this repo, so Gemini
        # invocation remains unverified here; only the routing surface is enforced.
        if planner_mode and runner_name != "gemini":
            runner_name = "gemini"
            model = "default"
            runner_reason += " → planner policy override: gemini required on Mac planner surface"
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
