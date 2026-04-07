#!/usr/bin/env python3
"""Settings/Tool Drift Control Scanner.

Periodically diffs live tool/command discovery against the canonical
settings_suite_registry.json and writes structured drift reports for
operator review. Never modifies the registry automatically — only
--apply-proposal does that, on explicit human invocation.

Usage:
    python3 drift_control_scanner.py --scan [--force]
    python3 drift_control_scanner.py --status
    python3 drift_control_scanner.py --apply-proposal [--yes]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE = Path("/home/openclaw")
REGISTRY_JSON = BASE / "settings_suite_registry.json"
CRON_JOBS = BASE / ".openclaw" / "cron" / "jobs.json"
MAC_EYES = BASE / "mac_eyes"
DRIFT_REPORT = MAC_EYES / "drift_report.md"
DRIFT_STATE = MAC_EYES / "drift_state.json"
CHANGELOG = BASE / ".claude" / "cache" / "changelog.md"
SETTINGS_JSON = BASE / ".claude" / "settings.json"
SETTINGS_LOCAL = BASE / ".claude" / "settings.local.json"
COMMANDS_PROJECT = BASE / ".claude" / "commands"
COMMANDS_USER = Path.home() / ".claude" / "commands"
PLUGINS_DIR = BASE / ".claude" / "plugins"
HOOKS_DIR = BASE / ".claude" / "hooks"
MCP_JSON = BASE / ".mcp.json"
COMPLIANCE_VERDICTS = BASE / "compliance_verdicts"
AGENTS_MD = BASE / "AGENTS.md"
OPENCLAW_RUNTIME_MD = BASE / "OPENCLAW_RUNTIME.md"
TASKS_DIR = BASE / "polish_loop" / "tasks"

CRON_JOB_ID = "drift-control-scan"
CADENCE_HOURS = 168  # weekly


# ---------------------------------------------------------------------------
# Phase A — Live discovery
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 10) -> tuple[str, str | None]:
    """Run a command. Returns (stdout, None) on success or ("", reason) on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr, None
    except subprocess.TimeoutExpired:
        return "", f"timeout after {timeout}s"
    except FileNotFoundError:
        return "", f"binary not found: {cmd[0]}"
    except Exception as e:
        return "", str(e)


def _discover_claude_version() -> dict:
    out, err = _run(["claude", "--version"])
    if err:
        return {"status": "check_failed", "reason": err}
    m = re.search(r"(\d+\.\d+\.\d+)", out)
    if m:
        return {"version": m.group(1), "raw": out.strip()}
    return {"status": "check_failed", "reason": f"could not parse version from: {out!r}"}


def _discover_slash_commands() -> dict:
    """Parse claude --help for subcommands and CLI flags."""
    out, err = _run(["claude", "--help"], timeout=15)
    if err:
        return {"status": "check_failed", "reason": err}

    subcommands = []
    in_commands = False
    for line in out.splitlines():
        if line.strip().startswith("Commands:"):
            in_commands = True
            continue
        if in_commands:
            if line.strip() == "" or (line and not line.startswith(" ")):
                if line.strip():
                    in_commands = False
                continue
            parts = line.strip().split()
            if parts:
                name = parts[0].split("|")[0]  # handle "update|upgrade"
                subcommands.append(name)

    cli_flags = re.findall(r"(--[\w-]+)", out)
    return {
        "subcommands": sorted(set(subcommands)),
        "cli_flags": sorted(set(cli_flags)),
    }


def _discover_settings() -> dict:
    result = {}
    for path, label in [(SETTINGS_JSON, "project"), (SETTINGS_LOCAL, "local")]:
        try:
            data = json.loads(path.read_text())
            result[label] = data
        except FileNotFoundError:
            result[label] = {"status": "check_failed", "reason": "file not found"}
        except Exception as e:
            result[label] = {"status": "check_failed", "reason": str(e)}
    return result


def _discover_custom_commands() -> list[dict]:
    commands = []
    seen_paths: set[Path] = set()
    for scope, dir_path in [("project", COMMANDS_PROJECT), ("user", COMMANDS_USER)]:
        try:
            if not dir_path.exists():
                continue
            resolved = dir_path.resolve()
            if resolved in seen_paths:
                continue  # skip if project and user dirs resolve to the same path
            seen_paths.add(resolved)
            for f in dir_path.glob("*.md"):
                commands.append({"name": f.stem, "path": str(f), "scope": scope})
        except Exception as e:
            commands.append({"scope": scope, "status": "check_failed", "reason": str(e)})
    return commands


def _discover_plugins() -> list[dict]:
    try:
        if not PLUGINS_DIR.exists():
            return []
        plugins = []
        for entry in PLUGINS_DIR.iterdir():
            if entry.name.startswith("."):
                continue
            plugins.append({
                "name": entry.stem if entry.is_file() else entry.name,
                "path": str(entry),
                "is_dir": entry.is_dir(),
            })
        return plugins
    except Exception as e:
        return [{"status": "check_failed", "reason": str(e)}]


def _discover_hooks() -> dict:
    try:
        exists = HOOKS_DIR.exists()
        if not exists:
            return {"directory_exists": False, "files": []}
        files = [f.name for f in HOOKS_DIR.iterdir() if not f.name.startswith(".")]
        return {"directory_exists": True, "files": sorted(files)}
    except Exception as e:
        return {"status": "check_failed", "reason": str(e)}


def _discover_mcp() -> list[dict]:
    try:
        data = json.loads(MCP_JSON.read_text())
        servers = data.get("mcpServers", {})
        return [{"server_name": k, "transport": v.get("command", "unknown")} for k, v in servers.items()]
    except FileNotFoundError:
        return []
    except Exception as e:
        return [{"status": "check_failed", "reason": str(e)}]


def _discover_runners() -> dict:
    try:
        sys.path.insert(0, str(BASE))
        from runner_registry import refresh
        # Use cached data (up to 1h old) — acceptable for a weekly drift scan.
        # force=True spawns 5+ binaries and risks timing out the scan.
        runners = refresh(force=False)
        return {name: {"available": r.available, "version": r.version} for name, r in runners.items()}
    except Exception as e:
        return {"status": "check_failed", "reason": str(e)}


def _discover_changelog_version() -> dict:
    try:
        text = CHANGELOG.read_text()
        m = re.search(r"^##\s+(\d+\.\d+\.\d+)", text, re.MULTILINE)
        if m:
            return {"version": m.group(1)}
        return {"status": "check_failed", "reason": "no version header found"}
    except FileNotFoundError:
        return {"status": "check_failed", "reason": "changelog not found"}
    except Exception as e:
        return {"status": "check_failed", "reason": str(e)}


def _run_all_discovery() -> dict:
    return {
        "claude_version": _discover_claude_version(),
        "slash_commands": _discover_slash_commands(),
        "settings": _discover_settings(),
        "custom_commands": _discover_custom_commands(),
        "plugins": _discover_plugins(),
        "hooks": _discover_hooks(),
        "mcp": _discover_mcp(),
        "runners": _discover_runners(),
        "changelog_version": _discover_changelog_version(),
    }


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def _load_registry() -> dict | None:
    """Load the canonical registry. Returns None if not found."""
    if not REGISTRY_JSON.exists():
        return None
    try:
        return json.loads(REGISTRY_JSON.read_text())
    except Exception as e:
        print(f"[drift_scanner] WARNING: could not load registry: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Phase B — Registry diff
# ---------------------------------------------------------------------------

def _classify_runner_change(name: str, live_val: dict | None, reg_entry: dict | None) -> str:
    if reg_entry is None:
        return "capability_appeared"
    if live_val is None:
        return "capability_disappeared"
    if live_val.get("version") != reg_entry.get("version"):
        return "version_upgrade"
    return "runner_availability_change"


def _diff_registry(registry: dict, live: dict) -> list[dict]:
    """Compare registry entries against live discovery. Returns list of drift items."""
    diffs = []

    # --- Runners ---
    reg_runners = {
        r.get("name", r.get("id", "unknown")): r
        for r in registry.get("runners", {}).values()
        if isinstance(r, dict)
    } if isinstance(registry.get("runners"), dict) else {}
    # runners may also be a list
    if isinstance(registry.get("runners"), list):
        reg_runners = {r.get("name", ""): r for r in registry.get("runners", [])}

    live_runners = live.get("runners", {})
    if isinstance(live_runners, dict) and "status" not in live_runners:
        all_runner_names = set(reg_runners) | set(live_runners)
        for name in all_runner_names:
            reg = reg_runners.get(name)
            lv = live_runners.get(name)
            live_available = lv.get("available", False) if lv else False
            reg_available = reg.get("available", True) if reg else False

            if reg is None and lv:
                diffs.append({
                    "item": name, "section": "runners",
                    "status": "new", "change_class": "capability_appeared",
                    "registry_value": None, "live_value": lv,
                    "proposed_update": {"action": "add", "entry": {"name": name, **lv}},
                })
            elif lv is None and reg:
                diffs.append({
                    "item": name, "section": "runners",
                    "status": "missing", "change_class": "capability_disappeared",
                    "registry_value": reg, "live_value": None,
                    "proposed_update": {"action": "update", "field": "available", "value": False},
                })
            elif reg and lv:
                reg_ver = reg.get("version", "")
                live_ver = lv.get("version", "")
                if reg_available != live_available:
                    cls = "capability_disappeared" if not live_available else "capability_appeared"
                    diffs.append({
                        "item": name, "section": "runners",
                        "status": "changed", "change_class": cls,
                        "registry_value": {"available": reg_available},
                        "live_value": {"available": live_available},
                        "proposed_update": {"action": "update", "field": "available", "value": live_available},
                    })
                elif reg_ver and live_ver and reg_ver != live_ver:
                    diffs.append({
                        "item": name, "section": "runners",
                        "status": "changed", "change_class": "version_upgrade",
                        "registry_value": {"version": reg_ver},
                        "live_value": {"version": live_ver},
                        "proposed_update": {"action": "update", "field": "version", "value": live_ver},
                    })
                else:
                    diffs.append({
                        "item": name, "section": "runners",
                        "status": "unchanged", "change_class": "runner_availability_change",
                        "registry_value": reg, "live_value": lv,
                        "proposed_update": None,
                    })

    # --- Claude Code version ---
    reg_ver = registry.get("claude_code_version", "")
    live_ver_data = live.get("claude_version", {})
    live_ver = live_ver_data.get("version", "") if isinstance(live_ver_data, dict) else ""
    if reg_ver and live_ver and reg_ver != live_ver:
        diffs.append({
            "item": "claude_code_version", "section": "meta",
            "status": "changed", "change_class": "version_upgrade",
            "registry_value": reg_ver, "live_value": live_ver,
            "proposed_update": {"action": "update", "field": "claude_code_version", "value": live_ver},
        })

    # --- Settings toggles ---
    reg_settings = registry.get("settings_toggles", [])
    live_proj = live.get("settings", {}).get("project", {})
    live_local = live.get("settings", {}).get("local", {})
    live_settings_flat = {}
    if isinstance(live_proj, dict) and "status" not in live_proj:
        live_settings_flat.update(live_proj)
    if isinstance(live_local, dict) and "status" not in live_local:
        live_settings_flat.update(live_local)

    if isinstance(reg_settings, list):
        reg_settings_map = {s.get("key", s.get("name", "")): s for s in reg_settings}
        for key, reg in reg_settings_map.items():
            reg_val = reg.get("current_value")
            live_val = live_settings_flat.get(key, "__NOT_FOUND__")
            if live_val == "__NOT_FOUND__":
                diffs.append({
                    "item": key, "section": "settings_toggles",
                    "status": "missing", "change_class": "value_drift",
                    "registry_value": reg_val, "live_value": None,
                    "proposed_update": {"action": "update", "field": "available", "value": False},
                })
            elif live_val != reg_val:
                diffs.append({
                    "item": key, "section": "settings_toggles",
                    "status": "changed", "change_class": "value_drift",
                    "registry_value": reg_val, "live_value": live_val,
                    "proposed_update": {"action": "update", "field": "current_value", "value": live_val},
                })
            else:
                diffs.append({
                    "item": key, "section": "settings_toggles",
                    "status": "unchanged", "change_class": "value_drift",
                    "registry_value": reg_val, "live_value": live_val,
                    "proposed_update": None,
                })

    # --- Custom commands ---
    reg_cmds = registry.get("custom_slash_commands", registry.get("project_custom_slash_commands", []))
    live_cmds = live.get("custom_commands", [])
    if isinstance(reg_cmds, list) and isinstance(live_cmds, list):
        reg_cmd_names = {c.get("name", "") for c in reg_cmds if isinstance(c, dict)}
        live_cmd_names = {
            c.get("name", "") for c in live_cmds
            if isinstance(c, dict) and "status" not in c
        }
        for name in live_cmd_names - reg_cmd_names:
            diffs.append({
                "item": name, "section": "custom_commands",
                "status": "new", "change_class": "local_config_change",
                "registry_value": None, "live_value": {"name": name},
                "proposed_update": {"action": "add", "entry": {"name": name, "classification": "project_custom_slash_command"}},
            })
        for name in reg_cmd_names - live_cmd_names:
            diffs.append({
                "item": name, "section": "custom_commands",
                "status": "missing", "change_class": "capability_disappeared",
                "registry_value": {"name": name}, "live_value": None,
                "proposed_update": {"action": "update", "field": "available", "value": False},
            })

    # --- MCP servers ---
    reg_mcp = registry.get("mcp_servers", [])
    live_mcp = live.get("mcp", [])
    if isinstance(reg_mcp, list) and isinstance(live_mcp, list):
        reg_mcp_names = {s.get("server_name", s.get("name", "")) for s in reg_mcp if isinstance(s, dict)}
        live_mcp_names = {
            s.get("server_name", "") for s in live_mcp
            if isinstance(s, dict) and "status" not in s
        }
        for name in live_mcp_names - reg_mcp_names:
            diffs.append({
                "item": name, "section": "mcp_servers",
                "status": "new", "change_class": "capability_appeared",
                "registry_value": None, "live_value": {"server_name": name},
                "proposed_update": {"action": "add", "entry": {"server_name": name}},
            })
        for name in reg_mcp_names - live_mcp_names:
            diffs.append({
                "item": name, "section": "mcp_servers",
                "status": "missing", "change_class": "capability_disappeared",
                "registry_value": {"server_name": name}, "live_value": None,
                "proposed_update": {"action": "update", "field": "available", "value": False},
            })

    # --- Hooks ---
    reg_hooks = registry.get("hooks", {})
    live_hooks = live.get("hooks", {})
    if isinstance(reg_hooks, dict) and isinstance(live_hooks, dict):
        reg_dir_exists = reg_hooks.get("directory_exists", False)
        live_dir_exists = live_hooks.get("directory_exists", False)
        if reg_dir_exists != live_dir_exists:
            cls = "capability_appeared" if live_dir_exists else "capability_disappeared"
            diffs.append({
                "item": "hooks_directory", "section": "hooks",
                "status": "changed", "change_class": cls,
                "registry_value": reg_dir_exists, "live_value": live_dir_exists,
                "proposed_update": {"action": "update", "field": "directory_exists", "value": live_dir_exists},
            })

    return diffs


# ---------------------------------------------------------------------------
# Phase C — Stale-reference scan
# ---------------------------------------------------------------------------

def _scan_stale_references(registry: dict | None) -> list[dict]:
    """Scan runtime-law docs and task files for stale /command references."""
    stale_items: set[str] = set()
    if registry:
        for entry in registry.get("slash_commands", []):
            if isinstance(entry, dict):
                if entry.get("classification") == "nonexistent_stale_assumption" or not entry.get("available", True):
                    stale_items.add(entry.get("name", ""))

    pattern = re.compile(r"/([a-z][a-z_-]+)\b")
    refs = []

    targets = [OPENCLAW_RUNTIME_MD, AGENTS_MD] + list(TASKS_DIR.glob("*.md"))
    for file_path in targets:
        try:
            text = file_path.read_text(errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                for m in pattern.finditer(line):
                    cmd = "/" + m.group(1)
                    if cmd.lstrip("/") in stale_items:
                        refs.append({
                            "reference": cmd,
                            "file": str(file_path.relative_to(BASE)),
                            "line": i,
                            "registry_status": "nonexistent_stale_assumption",
                        })
        except Exception:
            pass

    return refs


# ---------------------------------------------------------------------------
# Phase D — Compliance pattern analysis
# ---------------------------------------------------------------------------

def _analyze_compliance_patterns(max_verdicts: int = 20) -> list[dict]:
    """Check for dimensions noncompliant 3+ times consecutively."""
    if not COMPLIANCE_VERDICTS.exists():
        return []
    try:
        files = sorted(COMPLIANCE_VERDICTS.glob("*.json"))[-max_verdicts:]
        from collections import defaultdict
        streaks: dict[str, int] = defaultdict(int)
        signals = []
        for f in files:
            try:
                data = json.loads(f.read_text())
                for dim, result in (data.get("dimensions") or {}).items():
                    if result == "noncompliant":
                        streaks[dim] += 1
                    else:
                        streaks[dim] = 0
            except Exception:
                pass
        for dim, count in streaks.items():
            if count >= 3:
                signals.append({"dimension": dim, "consecutive_noncompliant": count})
        return signals
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _icon_for_status(status: str) -> str:
    return {"new": "🆕", "missing": "❌", "changed": "🔄", "unchanged": "✅", "stale": "⚠️",
            "reclassify_needed": "🔁", "check_failed": "⛔"}.get(status, "•")


def _write_drift_report(scan_result: dict) -> None:
    MAC_EYES.mkdir(parents=True, exist_ok=True)

    ts = scan_result["scan_timestamp"]
    next_ts = scan_result["next_scan"]
    summary = scan_result["summary"]
    changes = scan_result.get("changes", [])
    stale_refs = scan_result.get("stale_references", [])
    signals = scan_result.get("systemic_drift_signals", [])
    no_registry = scan_result.get("no_registry_baseline", False)
    reg_ts = scan_result.get("registry_timestamp", "unknown")
    reg_ver = scan_result.get("claude_code_version_registry", "unknown")
    live_ver = scan_result.get("claude_code_version_live", "unknown")
    ver_drift = reg_ver != live_ver and reg_ver != "unknown" and live_ver != "unknown"

    action_required = any(c["status"] != "unchanged" for c in changes)
    changes_needing_review = [c for c in changes if c["status"] != "unchanged"]
    unchanged = [c for c in changes if c["status"] == "unchanged"]

    lines = [
        "# 🔍 Settings Drift Report",
        f"*Scanned: {ts} — next scan: {next_ts}*",
        "",
        "### Summary",
    ]

    if no_registry:
        lines += [
            "- ⚠️ **No canonical registry found** — `settings_suite_registry.json` does not yet exist.",
            "  Run `impl-settings-suite-registry` to create the baseline before drift detection is meaningful.",
            f"- **Claude Code (live):** {live_ver}",
            f"- **Changelog version:** {scan_result.get('changelog_version_live', 'unknown')}",
            f"- **Custom commands:** {summary.get('custom_commands_found', 0)} found",
            f"- **MCP servers:** {summary.get('mcp_servers_found', 0)} found",
            f"- **Runners:** {summary.get('runners_found', 0)} found",
            "- **Action required:** Build the registry first.",
        ]
    else:
        ver_note = f" ⚠️ version drift" if ver_drift else ""
        lines += [
            f"- **Registry version:** {reg_ts}",
            f"- **Claude Code:** {reg_ver} → {live_ver}{ver_note}",
            f"- **Changes detected:** {summary.get('new', 0)} new, {summary.get('missing', 0)} missing, "
            f"{summary.get('changed', 0)} changed, {summary.get('stale_references', 0)} stale references",
            f"- **Action required:** {'Yes — review proposed registry updates below' if action_required else 'No'}",
        ]

    lines += [""]

    if no_registry:
        lines += [
            "### 🔍 Discovery Results (No Baseline Diff Available)",
            "",
            "The following were discovered on this system:",
        ]
        live = scan_result.get("live_discovery", {})
        cv = live.get("claude_version", {})
        if "version" in cv:
            lines.append(f"- **Claude Code version:** {cv['version']}")
        cc = live.get("changelog_version", {})
        if "version" in cc:
            lines.append(f"- **Changelog version:** {cc['version']}")
        cmds = [c for c in live.get("custom_commands", []) if "status" not in c]
        if cmds:
            lines.append(f"- **Custom commands:** {', '.join(c['name'] for c in cmds)}")
        mcp = [s for s in live.get("mcp", []) if "status" not in s]
        if mcp:
            lines.append(f"- **MCP servers:** {', '.join(s['server_name'] for s in mcp)}")
        runners = live.get("runners", {})
        if isinstance(runners, dict) and "status" not in runners:
            avail = [n for n, r in runners.items() if r.get("available")]
            lines.append(f"- **Runners available:** {', '.join(avail) if avail else 'none'}")
        hooks = live.get("hooks", {})
        if isinstance(hooks, dict):
            lines.append(f"- **Hooks directory exists:** {hooks.get('directory_exists', False)}")
        settings = live.get("settings", {})
        proj = settings.get("project", {})
        if isinstance(proj, dict) and "status" not in proj:
            for k, v in proj.items():
                lines.append(f"- **Setting `{k}`:** `{v}`")
        lines.append("")
    elif changes_needing_review:
        lines += [f"### ⚠️ Changes Requiring Review ({len(changes_needing_review)})", ""]
        for c in changes_needing_review:
            icon = _icon_for_status(c["status"])
            name = c["item"]
            section = c["section"]
            cls = c.get("change_class", "unknown")
            old = c.get("registry_value")
            new = c.get("live_value")
            proposed = c.get("proposed_update")
            proposed_str = f" · proposed: {json.dumps(proposed)}" if proposed else ""
            lines.append(
                f"- {icon} **`{name}`** [{section}] — {cls} "
                f"· was: `{old}` → now: `{new}`{proposed_str}"
            )
        lines.append("")

    if unchanged and not no_registry:
        by_section: dict[str, int] = {}
        for c in unchanged:
            by_section[c["section"]] = by_section.get(c["section"], 0) + 1
        summary_parts = [f"{count} {section}" for section, count in by_section.items()]
        lines += [
            f"### ✅ Unchanged ({len(unchanged)} items)",
            f"- {' · '.join(summary_parts)} — all match registry",
            "",
        ]

    lines += [f"### 📋 Stale References ({len(stale_refs)})"]
    if stale_refs:
        for r in stale_refs:
            lines.append(f"- `{r['reference']}` in `{r['file']}` line {r['line']} — registry status: {r['registry_status']}")
    else:
        lines.append("- No stale mode/command references found in task artifacts or runtime-law docs")
    lines.append("")

    if signals:
        lines += ["### 🔁 Systemic Drift Signals", ""]
        for s in signals:
            lines.append(f"- Dimension `{s['dimension']}` noncompliant {s['consecutive_noncompliant']}x consecutively — registry may be stale")
        lines.append("")

    if action_required and not no_registry:
        lines += [
            "### 🔁 Action: Registry Update Proposal",
            "To apply these changes, review and run:",
            "```",
            "python3 drift_control_scanner.py --apply-proposal",
            "```",
            "This will update `settings_suite_registry.json` with the proposed changes above.",
            "**Do not run without operator review.**",
            "",
        ]

    DRIFT_REPORT.write_text("\n".join(lines) + "\n")

    # Write machine-readable state
    DRIFT_STATE.write_text(json.dumps(scan_result, indent=2, default=str))


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def _register_cron_job() -> None:
    """Add drift-control-scan to .openclaw/cron/jobs.json if not present."""
    try:
        data = json.loads(CRON_JOBS.read_text())
    except Exception:
        data = {"version": 1, "jobs": []}

    jobs = data.setdefault("jobs", [])
    if any(j.get("id") == CRON_JOB_ID for j in jobs):
        return  # already registered

    jobs.append({
        "id": CRON_JOB_ID,
        "command": f"python3 {BASE}/drift_control_scanner.py --scan",
        "cadence_hours": CADENCE_HOURS,
        "last_run": None,
        "enabled": True,
        "description": "Weekly settings/tool drift scan against canonical registry",
    })
    CRON_JOBS.parent.mkdir(parents=True, exist_ok=True)
    CRON_JOBS.write_text(json.dumps(data, indent=2))


def _update_cron_last_run() -> None:
    try:
        data = json.loads(CRON_JOBS.read_text())
        for job in data.get("jobs", []):
            if job.get("id") == CRON_JOB_ID:
                job["last_run"] = datetime.now(timezone.utc).isoformat()
        CRON_JOBS.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _is_scan_due() -> bool:
    """Return True if enough time has passed since last_run per cadence_hours."""
    try:
        data = json.loads(CRON_JOBS.read_text())
        for job in data.get("jobs", []):
            if job.get("id") == CRON_JOB_ID:
                last_run = job.get("last_run")
                if last_run is None:
                    return True
                last_dt = datetime.fromisoformat(last_run)
                elapsed_h = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                return elapsed_h >= CADENCE_HOURS
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# Core public API
# ---------------------------------------------------------------------------

def run_scan(force: bool = False) -> dict:
    """Run the full drift scan. Returns the scan result dict."""
    _register_cron_job()

    if not force and not _is_scan_due():
        print("[drift_scanner] Scan not due yet — use --force to override.", flush=True)
        return {}

    now = datetime.now(timezone.utc)
    next_scan = datetime.fromtimestamp(now.timestamp() + CADENCE_HOURS * 3600, tz=timezone.utc)

    print("[drift_scanner] Running live discovery…", flush=True)
    live = _run_all_discovery()

    registry = _load_registry()
    no_registry = registry is None

    print("[drift_scanner] Running registry diff…", flush=True)
    changes = _diff_registry(registry or {}, live) if not no_registry else []

    print("[drift_scanner] Scanning stale references…", flush=True)
    stale_refs = _scan_stale_references(registry)

    print("[drift_scanner] Analyzing compliance patterns…", flush=True)
    signals = _analyze_compliance_patterns()

    # Build summary
    live_ver_data = live.get("claude_version", {})
    live_ver = live_ver_data.get("version", "unknown") if isinstance(live_ver_data, dict) else "unknown"
    changelog_ver = live.get("changelog_version", {})
    changelog_ver_str = changelog_ver.get("version", "unknown") if isinstance(changelog_ver, dict) else "unknown"

    custom_cmds = [c for c in live.get("custom_commands", []) if "status" not in c]
    mcp_servers = [s for s in live.get("mcp", []) if "status" not in s]
    runners = live.get("runners", {})
    runners_found = len([n for n, r in runners.items() if r.get("available")]) if isinstance(runners, dict) and "status" not in runners else 0

    status_counts: dict[str, int] = {}
    for c in changes:
        s = c["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    summary = {
        "total_items_checked": len(changes),
        "unchanged": status_counts.get("unchanged", 0),
        "new": status_counts.get("new", 0),
        "missing": status_counts.get("missing", 0),
        "changed": status_counts.get("changed", 0),
        "stale_references": len(stale_refs),
        "check_failed": status_counts.get("check_failed", 0),
        "custom_commands_found": len(custom_cmds),
        "mcp_servers_found": len(mcp_servers),
        "runners_found": runners_found,
    }

    scan_result = {
        "schema_version": "1.0",
        "scan_timestamp": now.isoformat(),
        "next_scan": next_scan.isoformat(),
        "registry_timestamp": registry.get("generated_at", "unknown") if registry else "no_registry",
        "claude_code_version_registry": registry.get("claude_code_version", "unknown") if registry else "no_registry",
        "claude_code_version_live": live_ver,
        "changelog_version_live": changelog_ver_str,
        "no_registry_baseline": no_registry,
        "summary": summary,
        "changes": changes,
        "proposed_registry_updates": [c["proposed_update"] for c in changes if c.get("proposed_update")],
        "stale_references": stale_refs,
        "systemic_drift_signals": signals,
        "live_discovery": live,
    }

    print("[drift_scanner] Writing drift report…", flush=True)
    _write_drift_report(scan_result)
    _update_cron_last_run()

    changed = sum(1 for c in changes if c["status"] != "unchanged")
    print(
        f"[drift_scanner] Done. {changed} change(s) detected, "
        f"{len(stale_refs)} stale reference(s). "
        f"Report: {DRIFT_REPORT}",
        flush=True,
    )
    return scan_result


def apply_proposal(dry_run: bool = False, yes: bool = False) -> None:
    """Apply proposed registry updates from last scan. Requires explicit human invocation."""
    if not DRIFT_STATE.exists():
        print("ERROR: No drift_state.json found. Run --scan first.", file=sys.stderr)
        sys.exit(1)

    state = json.loads(DRIFT_STATE.read_text())
    proposals = state.get("proposed_registry_updates", [])

    if not proposals:
        print("No proposed updates found in last scan. Registry is current.")
        return

    print(f"Proposed updates: {len(proposals)}")
    for p in proposals:
        print(f"  {json.dumps(p)}")

    if dry_run:
        print("\n[dry-run] No changes applied.")
        return

    if not yes:
        confirm = input(f"\nApply {len(proposals)} update(s) to {REGISTRY_JSON}? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    if not REGISTRY_JSON.exists():
        print(f"ERROR: {REGISTRY_JSON} not found. Cannot apply proposals.", file=sys.stderr)
        sys.exit(1)

    registry = json.loads(REGISTRY_JSON.read_text())

    applied = 0
    for proposal in proposals:
        try:
            action = proposal.get("action")
            if action == "update":
                field = proposal.get("field")
                value = proposal.get("value")
                item = proposal.get("item")
                section = proposal.get("section")
                if section and field:
                    entries = registry.get(section, [])
                    if isinstance(entries, list):
                        for entry in entries:
                            if entry.get("name") == item or entry.get("key") == item:
                                entry[field] = value
                                applied += 1
                    elif isinstance(entries, dict):
                        if item in entries:
                            entries[item][field] = value
                            applied += 1
                elif field == "claude_code_version":
                    registry["claude_code_version"] = value
                    applied += 1
            elif action == "add":
                section = proposal.get("section")
                entry = proposal.get("entry")
                if section and entry:
                    if section not in registry:
                        registry[section] = []
                    if isinstance(registry[section], list):
                        registry[section].append(entry)
                        applied += 1
        except Exception as e:
            print(f"  WARNING: could not apply proposal {proposal}: {e}")

    registry["generated_at"] = datetime.now(timezone.utc).isoformat()
    REGISTRY_JSON.write_text(json.dumps(registry, indent=2))
    print(f"\nApplied {applied}/{len(proposals)} update(s) to {REGISTRY_JSON}.")


def print_status() -> None:
    """Print last scan summary."""
    if not DRIFT_STATE.exists():
        print("No scan has been run yet.")
        return
    state = json.loads(DRIFT_STATE.read_text())
    print(f"Last scan: {state.get('scan_timestamp', 'unknown')}")
    print(f"Next scan: {state.get('next_scan', 'unknown')}")
    summary = state.get("summary", {})
    for k, v in summary.items():
        print(f"  {k}: {v}")
    if state.get("no_registry_baseline"):
        print("  ⚠️  No registry baseline — drift detection pending registry creation")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Settings/tool drift scanner")
    parser.add_argument("--scan", action="store_true", help="Run drift scan (respects cadence unless --force)")
    parser.add_argument("--force", action="store_true", help="Ignore cadence, scan now")
    parser.add_argument("--apply-proposal", action="store_true", help="Apply proposed registry updates (REQUIRES REVIEW)")
    parser.add_argument("--dry-run", action="store_true", help="With --apply-proposal: show changes without applying")
    parser.add_argument("--yes", action="store_true", help="With --apply-proposal: skip confirmation prompt")
    parser.add_argument("--status", action="store_true", help="Print last scan summary")
    args = parser.parse_args()

    if args.scan:
        run_scan(force=args.force)
    elif args.apply_proposal:
        apply_proposal(dry_run=args.dry_run, yes=args.yes)
    elif args.status:
        print_status()
    else:
        parser.print_help()
