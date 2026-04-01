#!/usr/bin/env python3
"""Runner Registry — dynamic, self-discovering programmer tool catalog.

This module is the inventory layer for the polish-loop runner pipeline.
It answers three questions:
  1. Which coding runners are installed on this machine?
  2. What capabilities, flags, and models does each runner expose?
  3. How should that runner be invoked once another module chooses it?

It does NOT decide which runner gets a task. That policy lives in
`runner_profiles.py`, which asks this registry for discovered runners and
then applies task-tier scoring.

Runner selection intent, as implemented across the pipeline:
  - `quick` prefers Gemini as the default smart/cheap/fast option.
  - `surgical` favors Codex or Claude because they are stronger on
    sandboxed, correctness-oriented edits.
  - `standard` mostly prefers Claude, while `runner_profiles.py` rotates
    roughly one out of every three standard tasks to Gemini for cost control.
  - `architect` strongly prefers Claude for its architecture and reasoning
    strengths.

Auto-discovery runs on import or via `refresh()`. New tools are detected by
scanning PATH for known binary names and by reading the plug-in directory for
third-party runner definitions.

Discovery flow each time `refresh()` runs:
  1. In-memory cache check — if `_registry` is populated and fresh
     (`< CACHE_TTL`), return immediately without hitting disk or spawning
     subprocesses.
  2. Disk cache check — if `.runner_registry_cache.json` exists and is within
     TTL, deserialize it into `Runner` objects and return it. This avoids
     shelling out to every binary on startup.
  3. Full scan — for each entry in `KNOWN_RUNNERS`, check PATH for the binary,
     run `--version` and `--help`, and parse flags. Ollama also enumerates
     locally available models via `ollama list`.
  4. Plugin scan — load any `*.json` files from `/home/openclaw/runners.d/`.
     Each file defines a custom runner; the binary is still validated via PATH
     before the entry is accepted.
  5. Change detection — new or removed runners, flag additions, and version
     bumps are logged to `DISCOVERY_LOG` for auditability.
  6. Cache write — the updated registry is serialized to
     `.runner_registry_cache.json` so the next startup can take the disk-cache
     fast path.

Adding a new runner:
  Option A: Drop a JSON file in `/home/openclaw/runners.d/<name>.json`
  Option B: Install the CLI tool. Discovery will find it automatically if it
            matches a known pattern or has a parseable help flag.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

REGISTRY_CACHE = Path("/home/openclaw/.runner_registry_cache.json")
RUNNERS_D = Path("/home/openclaw/runners.d")
DISCOVERY_LOG = Path("/mnt/c/OpenClaw/logs/runner_discovery.log")
CACHE_TTL = 3600  # Re-discover every hour

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RunnerFlag:
    """A CLI flag supported by a runner."""
    name: str                     # e.g. "--effort"
    description: str              # from help text
    values: list[str] = field(default_factory=list)  # e.g. ["low","medium","high","max"]
    value_type: str = "string"    # string, bool, number
    relevant: bool = True         # False = we parsed it but don't use it


@dataclass
class Runner:
    """A coding tool that can execute tasks."""
    name: str                     # e.g. "claude", "codex", "gemini", "aider", "ollama"
    binary: str                   # full path to executable
    version: str                  # version string
    available: bool               # True if binary exists and responds
    runner_type: str              # "cloud" | "local" | "hybrid"
    models: list[str] = field(default_factory=list)
    flags: list[RunnerFlag] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)   # e.g. ["architecture", "large-refactor"]
    weaknesses: list[str] = field(default_factory=list)   # e.g. ["slow", "expensive"]
    cost_tier: str = "unknown"    # "free" | "cheap" | "moderate" | "expensive"
    max_timeout: int = 900        # max seconds before kill
    invoke_pattern: str = ""      # template: e.g. "setsid timeout {timeout} claude --model {model} ..."
    headless_flag: str = ""       # flag for non-interactive mode
    discovered_at: str = ""       # ISO timestamp
    source: str = "auto"          # "auto" | "manual" | "plugin"
    extra: dict = field(default_factory=dict)  # anything else

    def supports_flag(self, flag_name: str) -> bool:
        return any(f.name == flag_name for f in self.flags)

    def get_flag(self, flag_name: str) -> Optional[RunnerFlag]:
        for f in self.flags:
            if f.name == flag_name:
                return f
        return None


# ---------------------------------------------------------------------------
# Well-known runner discovery patterns
# ---------------------------------------------------------------------------

KNOWN_RUNNERS = {
    "claude": {
        "binary_names": ["claude"],
        "version_cmd": ["claude", "--version"],
        "help_cmd": ["claude", "--help"],
        "runner_type": "cloud",
        "cost_tier": "moderate",
        "headless_flag": "--print",
        "invoke_pattern": "setsid timeout {timeout} claude --model {model} --effort {effort} --dangerously-skip-permissions --print --max-budget-usd {budget} --fallback-model {fallback_model} < {prompt_file}",
        "strengths": ["architecture", "complex-reasoning", "multi-file", "safety"],
        "weaknesses": ["cost-on-opus"],
        "flag_parser": "_parse_claude_help",
    },
    "codex": {
        "binary_names": ["codex"],
        "version_cmd": ["codex", "--version"],
        "help_cmd": ["codex", "--help"],
        "runner_type": "cloud",
        "cost_tier": "moderate",
        "headless_flag": "exec",
        "invoke_pattern": "setsid timeout {timeout} codex exec \"$(cat {prompt_file})\"",
        "strengths": ["code-review", "sandbox-isolation", "openai-models"],
        "weaknesses": ["less-context-than-claude"],
        "flag_parser": "_parse_codex_help",
    },
    "gemini": {
        "binary_names": ["gemini"],
        "version_cmd": ["gemini", "--version"],
        "help_cmd": ["gemini", "--help"],
        "runner_type": "cloud",
        "cost_tier": "cheap",
        "headless_flag": "--prompt",
        "invoke_pattern": "setsid timeout {timeout} gemini --prompt \"$(cat {prompt_file})\" --yolo --sandbox --output-format text",
        "strengths": ["fast", "cheap", "large-context", "sandbox"],
        "weaknesses": ["less-agentic-than-claude"],
        "flag_parser": "_parse_generic_help",
    },
    "aider": {
        "binary_names": ["aider"],
        "version_cmd": ["aider", "--version"],
        "help_cmd": ["aider", "--help"],
        "runner_type": "hybrid",  # can use cloud or local models
        "cost_tier": "variable",
        "headless_flag": "--yes-always --no-auto-commits",
        "invoke_pattern": "setsid timeout {timeout} aider --model {model} --yes-always --no-auto-commits --message-file {prompt_file}",
        "strengths": ["git-aware", "multi-model", "edit-format"],
        "weaknesses": ["needs-model-config"],
        "flag_parser": "_parse_generic_help",
    },
    "ollama": {
        "binary_names": ["ollama"],
        "version_cmd": ["ollama", "--version"],
        "help_cmd": ["ollama", "--help"],
        "runner_type": "local",
        "cost_tier": "free",
        "headless_flag": "run",
        "invoke_pattern": "setsid timeout {timeout} ollama run {model} < {prompt_file}",
        "strengths": ["free", "private", "fast-for-small-tasks", "no-internet-needed"],
        "weaknesses": ["limited-reasoning", "small-context", "no-tool-use"],
        "flag_parser": "_parse_ollama_help",
    },
}


# ---------------------------------------------------------------------------
# Help text parsers
# ---------------------------------------------------------------------------

def _run_cmd(cmd: list[str], timeout: int = 10) -> str:
    """Run a command and return stdout+stderr."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return ""


def _parse_flags_generic(help_text: str) -> list[RunnerFlag]:
    """Parse --flag lines from generic help output."""
    flags = []
    for m in re.finditer(
        r'^\s+(--[\w-]+)(?:,\s*--[\w-]+)?\s+(?:<(\w+)>)?\s*(.*)',
        help_text, re.MULTILINE
    ):
        name = m.group(1)
        desc = m.group(3).strip()
        values = []
        # Extract choices from description
        choices_m = re.search(r'choices:\s*"([^"]+(?:",\s*"[^"]+)*)"', desc)
        if choices_m:
            values = [v.strip().strip('"') for v in choices_m.group(0).replace('choices:', '').split(',')]
        paren_m = re.search(r'\(([^)]+)\)', desc)
        if not values and paren_m and ',' in paren_m.group(1):
            values = [v.strip().strip('"') for v in paren_m.group(1).split(',')]

        flags.append(RunnerFlag(
            name=name,
            description=desc[:200],
            values=values,
            value_type="bool" if not m.group(2) else "string",
        ))
    return flags


def _parse_claude_help(help_text: str) -> list[RunnerFlag]:
    """Parse Claude CLI help with awareness of key flags."""
    flags = _parse_flags_generic(help_text)
    # Ensure we capture effort values even if not in choices format
    for f in flags:
        if f.name == "--effort" and not f.values:
            f.values = ["low", "medium", "high", "max"]
        if f.name == "--permission-mode" and not f.values:
            f.values = ["acceptEdits", "bypassPermissions", "default", "dontAsk", "plan", "auto"]
    return flags


def _parse_codex_help(help_text: str) -> list[RunnerFlag]:
    return _parse_flags_generic(help_text)


def _parse_ollama_help(help_text: str) -> list[RunnerFlag]:
    return _parse_flags_generic(help_text)


def _parse_generic_help(help_text: str) -> list[RunnerFlag]:
    return _parse_flags_generic(help_text)


PARSERS = {
    "_parse_claude_help": _parse_claude_help,
    "_parse_codex_help": _parse_codex_help,
    "_parse_ollama_help": _parse_ollama_help,
    "_parse_generic_help": _parse_generic_help,
}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _discover_runner(name: str, spec: dict) -> Optional[Runner]:
    """Discover a single runner from its spec."""
    binary = None
    for bname in spec["binary_names"]:
        found = shutil.which(bname)
        if found:
            binary = found
            break

    if not binary:
        return None

    # Get version
    version = _run_cmd(spec["version_cmd"]).strip().split("\n")[0][:100]
    if not version:
        version = "unknown"

    # Get help and parse flags
    help_text = _run_cmd(spec["help_cmd"])
    parser_name = spec.get("flag_parser", "_parse_generic_help")
    parser_fn = PARSERS.get(parser_name, _parse_generic_help)
    flags = parser_fn(help_text) if help_text else []

    # Get models for ollama
    models = []
    if name == "ollama":
        models_out = _run_cmd(["ollama", "list"])
        for line in models_out.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if parts:
                models.append(parts[0])
    elif name == "claude":
        # Models from help text
        models = ["sonnet", "opus", "haiku"]
    elif name == "codex":
        models = ["default"]

    return Runner(
        name=name,
        binary=binary,
        version=version,
        available=True,
        runner_type=spec["runner_type"],
        models=models,
        flags=flags,
        strengths=spec.get("strengths", []),
        weaknesses=spec.get("weaknesses", []),
        cost_tier=spec.get("cost_tier", "unknown"),
        max_timeout=900,
        invoke_pattern=spec.get("invoke_pattern", ""),
        headless_flag=spec.get("headless_flag", ""),
        discovered_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        source="auto",
    )


def _load_plugin_runners() -> list[Runner]:
    """Load runner definitions from /home/openclaw/runners.d/*.json"""
    runners = []
    if not RUNNERS_D.exists():
        RUNNERS_D.mkdir(parents=True, exist_ok=True)
        return runners

    for f in RUNNERS_D.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            # Validate binary exists
            binary = shutil.which(data.get("binary_name", data.get("name", "")))
            if not binary:
                continue
            version = _run_cmd([binary, "--version"]).strip().split("\n")[0][:100] if binary else "unknown"

            runner = Runner(
                name=data["name"],
                binary=binary,
                version=version,
                available=True,
                runner_type=data.get("runner_type", "cloud"),
                models=data.get("models", []),
                flags=[],  # Will be populated by help parsing
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                cost_tier=data.get("cost_tier", "unknown"),
                max_timeout=data.get("max_timeout", 900),
                invoke_pattern=data.get("invoke_pattern", ""),
                headless_flag=data.get("headless_flag", ""),
                discovered_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                source="plugin",
            )

            # Parse help if available
            help_cmd = data.get("help_cmd")
            if help_cmd:
                help_text = _run_cmd(help_cmd if isinstance(help_cmd, list) else help_cmd.split())
                runner.flags = _parse_generic_help(help_text)

            runners.append(runner)
        except Exception as e:
            _log(f"Plugin load error for {f.name}: {e}")

    return runners


def _log(msg: str):
    """Append to discovery log."""
    try:
        DISCOVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DISCOVERY_LOG, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Registry (the main interface)
# ---------------------------------------------------------------------------

_registry: dict[str, Runner] = {}
_last_refresh: float = 0


def refresh(force: bool = False) -> dict[str, Runner]:
    """Refresh the runner registry via auto-discovery.

    Scans for all known runners + plugin runners.
    Caches results; re-scans every CACHE_TTL seconds unless forced.
    """
    global _registry, _last_refresh

    if not force and _registry and (time.time() - _last_refresh) < CACHE_TTL:
        return _registry

    # Try loading from cache first (fast path)
    if not force and REGISTRY_CACHE.exists():
        try:
            cache = json.loads(REGISTRY_CACHE.read_text())
            cache_age = time.time() - cache.get("_timestamp", 0)
            if cache_age < CACHE_TTL:
                _registry = {}
                for name, data in cache.items():
                    if name.startswith("_"):
                        continue
                    flags = [RunnerFlag(**f) for f in data.pop("flags", [])]
                    _registry[name] = Runner(**data, flags=flags)
                _last_refresh = time.time()
                return _registry
        except Exception:
            pass

    _log("Starting full discovery scan")
    new_registry: dict[str, Runner] = {}

    # Discover known runners
    for name, spec in KNOWN_RUNNERS.items():
        runner = _discover_runner(name, spec)
        if runner:
            new_registry[name] = runner
            _log(f"Found {name}: {runner.binary} v{runner.version} ({len(runner.flags)} flags, {len(runner.models)} models)")
        else:
            _log(f"Not found: {name}")

    # Discover plugin runners
    for runner in _load_plugin_runners():
        new_registry[runner.name] = runner
        _log(f"Plugin: {runner.name}: {runner.binary} v{runner.version}")

    # Detect changes from previous registry
    if _registry:
        old_names = set(_registry.keys())
        new_names = set(new_registry.keys())
        added = new_names - old_names
        removed = old_names - new_names
        if added:
            _log(f"NEW RUNNERS DETECTED: {added}")
        if removed:
            _log(f"RUNNERS REMOVED: {removed}")

        # Check for new flags on existing runners
        for name in old_names & new_names:
            old_flags = {f.name for f in _registry[name].flags}
            new_flags = {f.name for f in new_registry[name].flags}
            flag_diff = new_flags - old_flags
            if flag_diff:
                _log(f"NEW FLAGS on {name}: {flag_diff}")

        # Check for version changes
        for name in old_names & new_names:
            if _registry[name].version != new_registry[name].version:
                _log(f"VERSION CHANGE {name}: {_registry[name].version} → {new_registry[name].version}")

    _registry = new_registry
    _last_refresh = time.time()

    # Write cache
    try:
        cache_data = {"_timestamp": time.time()}
        for name, runner in _registry.items():
            d = asdict(runner)
            cache_data[name] = d
        REGISTRY_CACHE.write_text(json.dumps(cache_data, indent=2))
    except Exception as e:
        _log(f"Cache write failed: {e}")

    _log(f"Discovery complete: {len(_registry)} runners available")
    return _registry


def get_runner(name: str) -> Optional[Runner]:
    """Get a specific runner by name."""
    reg = refresh()
    return reg.get(name)


def get_available_runners() -> list[Runner]:
    """Get all available runners."""
    reg = refresh()
    return [r for r in reg.values() if r.available]


def get_runners_for_task(task_type: str) -> list[Runner]:
    """Get runners suitable for a task type, ranked by fit.

    task_type: "quick" | "surgical" | "standard" | "architect"
    """
    runners = get_available_runners()
    if not runners:
        return []

    scored: list[tuple[float, Runner]] = []
    for r in runners:
        score = _score_runner_for_task(r, task_type)
        scored.append((score, r))

    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored]


def _score_runner_for_task(runner: Runner, task_type: str) -> float:
    """Score a runner's fit for a task tier. Higher scores rank earlier.

    This function is intentionally heuristic, not absolute. It biases toward
    the runner that should usually win for a given tier based on strengths,
    weaknesses, cost, and CLI capabilities, while leaving final selection
    details to `runner_profiles.py`.

    The policy being expressed here is:
      - `quick`: Gemini should usually rank first because it is cheap, fast,
        and still capable. Ollama gets a smaller boost, but it is not meant to
        win general quick work by default.
      - `surgical`: Codex and Claude should rise because sandboxing, safety,
        and code-review traits matter more than raw speed.
      - `standard`: Claude should usually rank first for multi-file reasoning,
        but `runner_profiles.py` may still route about one-third of standard
        tasks to Gemini through ratio rotation after scoring.
      - `architect`: Claude should dominate because architecture and complex
        reasoning matter more than cost.
    """
    score = 50.0  # base

    # --- Universal cost efficiency ---
    if runner.cost_tier == "cheap":
        score += 7
    # free/local gets NO universal bonus — ollama shouldn't win by default
    # moderate = 0 (baseline), expensive = penalty below

    if task_type == "quick":
        # Prefer: smart + cheap + fast.  Gemini > ollama for most quick tasks.
        # Ollama only wins when local_required flag is set (handled in _pick_runner).
        if "fast" in runner.strengths:
            score += 15
        if runner.cost_tier == "cheap":
            score += 15  # stacks with universal +7 = +22 total
        elif runner.cost_tier == "free":
            score += 8   # free is nice but not the priority
        if "large-context" in runner.strengths:
            score += 5
        if "sandbox" in runner.strengths:
            score += 5
        if runner.runner_type == "local":
            score += 3   # small bonus — not dominant
        if "limited-reasoning" in runner.weaknesses:
            score -= 8   # quick tasks still benefit from smarts
        if "fast-for-small-tasks" in runner.strengths:
            score += 5

    elif task_type == "surgical":
        # Prefer: accurate, sandboxed, cost-controlled
        if "safety" in runner.strengths:
            score += 12
        if "sandbox-isolation" in runner.strengths:
            score += 10  # sandboxed execution catches regressions
        if "sandbox" in runner.strengths:
            score += 8
        if "code-review" in runner.strengths:
            score += 8  # good at reviewing changes for correctness
        if runner.cost_tier in ("moderate", "cheap"):
            score += 5
        if runner.supports_flag("--effort"):
            score += 3

    elif task_type == "standard":
        # Prefer: good all-around, large context, multi-file
        # Gemini gets ~1/3 of standard work via ratio rotation in _pick_runner
        if "complex-reasoning" in runner.strengths:
            score += 15
        if "multi-file" in runner.strengths:
            score += 8
        if "large-context" in runner.strengths:
            score += 10  # standard tasks often span many files
        if "sandbox" in runner.strengths:
            score += 5
        if "sandbox-isolation" in runner.strengths:
            score += 5
        if runner.supports_flag("--effort"):
            score += 5
        if runner.cost_tier == "expensive":
            score -= 10
        if "limited-reasoning" in runner.weaknesses:
            score -= 15

    elif task_type == "architect":
        # Prefer: best reasoning, large context, don't care about cost
        if "architecture" in runner.strengths:
            score += 25
        if "complex-reasoning" in runner.strengths:
            score += 20
        if "large-context" in runner.strengths:
            score += 10
        if runner.supports_flag("--effort"):
            score += 5
        if runner.runner_type == "local":
            score -= 20
        if "limited-reasoning" in runner.weaknesses:
            score -= 30
        if "less-agentic-than-claude" in runner.weaknesses:
            score -= 5
        if "small-context" in runner.weaknesses:
            score -= 10

    # General bonuses (minor — shouldn't dominate)
    if runner.supports_flag("--max-budget-usd"):
        score += 2  # cost control
    if runner.supports_flag("--fallback-model"):
        score += 1  # resilience

    return score


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI: print registry as JSON or human-readable report."""
    import argparse
    parser = argparse.ArgumentParser(description="Runner Registry")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--refresh", action="store_true", help="Force rediscovery")
    parser.add_argument("--for-task", type=str, help="Rank runners for a task type")
    args = parser.parse_args()

    reg = refresh(force=args.refresh)

    if args.for_task:
        ranked = get_runners_for_task(args.for_task)
        if args.json:
            print(json.dumps([asdict(r) for r in ranked], indent=2))
        else:
            print(f"Runners ranked for '{args.for_task}' tasks:\n")
            for i, r in enumerate(ranked, 1):
                score = _score_runner_for_task(r, args.for_task)
                print(f"  {i}. {r.name:12s} v{r.version:20s} score={score:.0f}  ({r.runner_type}, {r.cost_tier})")
                print(f"     Strengths: {', '.join(r.strengths)}")
                if r.models:
                    print(f"     Models: {', '.join(r.models[:5])}")
                print()
        return

    if args.json:
        print(json.dumps({n: asdict(r) for n, r in reg.items()}, indent=2))
    else:
        print(f"Runner Registry — {len(reg)} runners available\n")
        for name, r in reg.items():
            status = "✓" if r.available else "✗"
            print(f"  {status} {name:12s} v{r.version:30s} {r.runner_type:8s} {r.cost_tier:10s} {len(r.flags)} flags, {len(r.models)} models")
            if r.strengths:
                print(f"    Strengths: {', '.join(r.strengths)}")
        print(f"\nPlugin dir: {RUNNERS_D}")
        print(f"Cache: {REGISTRY_CACHE}")
        print(f"Log: {DISCOVERY_LOG}")


if __name__ == "__main__":
    main()
