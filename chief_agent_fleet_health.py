"""Chief fleet-health read-model generator v0.

Answers "what is the system state / what agents are running / what's healthy"
for Chief's lane. Sources are REAL, deterministic, and fully traceable:

  1. agent_presence.json   — each agent's actual runtime state
  2. sync_health.json      — Mac/PC read-model sync posture
  3. git log              — recently shipped milestones on the active branch

SAFETY: pure read-only, no network, no subprocess except git-log.
No confabulation: every field traces to a file or git command.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "chief_agent_fleet_health_v0"
JSON_EXPORT_NAME = "chief_agent_fleet_health.json"
OPERATOR_EXPORT_NAME = "chief_agent_fleet_health_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

# Source ref constants (stable, used for grounding provenance)
AGENT_PRESENCE_REF = "generated/read_models/agent_presence.json"
SYNC_HEALTH_REF = "generated/read_models/sync_health.json"
GIT_MILESTONES_REF = "git log (shipped feat/fix/chore/perf/refactor commits)"

MILESTONE_KINDS = frozenset({"feat", "fix", "chore", "perf", "refactor"})
MILESTONE_LIMIT = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _freshness_of(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Return {as_of, source_ref} for grounding provenance."""
    generated_at = str(payload.get("generated_at") or payload.get("updated_at") or "").strip()
    if not generated_at:
        try:
            generated_at = datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc
            ).replace(microsecond=0).isoformat()
        except OSError:
            generated_at = ""
    return {"as_of": generated_at, "source_ref": str(path)}


def _agent_health_summary(presence: dict[str, Any]) -> dict[str, Any]:
    """Distil agent_presence.json into Chief-relevant fleet health facts."""
    agents = presence.get("agents") or []
    by_state: dict[str, list[str]] = {}
    blockers: list[dict[str, Any]] = []
    for agent in agents:
        state = str(agent.get("actual_state") or "unknown")
        agent_id = str(agent.get("agent_id") or "unknown")
        by_state.setdefault(state, []).append(agent_id)
        if state not in ("online", "metadata_available") and agent.get("expected_online"):
            blocker = str(agent.get("blocker") or "")
            blockers.append({"agent_id": agent_id, "state": state, "blocker": blocker})

    online = by_state.get("online", [])
    degraded = by_state.get("degraded", [])
    offline = by_state.get("offline", [])
    total = int(presence.get("agent_count") or len(agents))
    online_count = int(presence.get("online_count") or len(online))

    parts: list[str] = [f"Fleet: {online_count}/{total} agents online."]
    if online:
        parts.append(f"Online: {', '.join(online)}.")
    if degraded:
        parts.append(f"Degraded: {', '.join(degraded)}.")
    if offline:
        parts.append(f"Offline: {', '.join(offline)}.")
    if blockers:
        blocker_lines = [f"{b['agent_id']}({b['state']})" for b in blockers]
        parts.append(f"Blockers: {', '.join(blocker_lines)}.")
    summary_text = " ".join(parts)

    return {
        "total_agents": total,
        "online_count": online_count,
        "online_agents": online,
        "degraded_agents": degraded,
        "offline_agents": offline,
        "unexpected_offline_count": len(blockers),
        "blockers": blockers,
        "summary": summary_text,
    }


def _sync_health_summary(sync: dict[str, Any]) -> dict[str, Any]:
    """Distil sync_health.json into Chief-relevant posture facts."""
    mirror_status = str(sync.get("mirror_status") or "unknown")
    display_status = str(sync.get("display_status") or "unknown")
    trust_status = str(sync.get("trust_status") or "unknown")
    operator_action_required = bool(sync.get("operator_action_required", False))
    missing = int(sync.get("missing_expected") or 0)
    hash_mismatch = int(sync.get("hash_mismatch") or 0)

    last_mac = sync.get("last_mac_completion") or {}
    last_sync_time = str(last_mac.get("time") or "")
    last_sync_status = str(last_mac.get("status") or "")

    problems: list[str] = []
    if missing:
        problems.append(f"{missing} files missing")
    if hash_mismatch:
        problems.append(f"{hash_mismatch} hash mismatches")
    if operator_action_required:
        problems.append("operator action required")

    summary_parts = [f"Sync: mirror={mirror_status}, display={display_status}."]
    if last_sync_time:
        summary_parts.append(f"Last Mac sync: {last_sync_time} ({last_sync_status}).")
    if problems:
        summary_parts.append(f"Problems: {'; '.join(problems)}.")
    else:
        summary_parts.append("No blocking sync problems.")

    return {
        "mirror_status": mirror_status,
        "display_status": display_status,
        "trust_status": trust_status,
        "operator_action_required": operator_action_required,
        "last_mac_completion_time": last_sync_time,
        "last_mac_completion_status": last_sync_status,
        "missing_expected": missing,
        "hash_mismatch": hash_mismatch,
        "summary": " ".join(summary_parts),
    }


def _git_milestones(repo_root: Path, limit: int = MILESTONE_LIMIT) -> dict[str, Any]:
    """Read real shipped milestones from git log. No confabulation."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{limit * 4}", "--no-merges", "--pretty=%h%x1f%cI%x1f%s"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        raw = result.stdout.strip()
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        branch = branch_result.stdout.strip() or "unknown"
    except Exception:
        return {"branch": "unknown", "milestones": [], "count": 0, "available": False}

    milestones: list[dict[str, str]] = []
    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        commit, at, subject = parts
        kind = subject.split("(", 1)[0].split(":", 1)[0].strip().lower()
        if kind in MILESTONE_KINDS:
            milestones.append({"commit": commit, "at": at, "summary": subject})
        if len(milestones) >= limit:
            break

    return {
        "branch": branch,
        "milestones": milestones,
        "count": len(milestones),
        "available": True,
    }


def build_chief_agent_fleet_health(
    *,
    repo_root: Path | str = Path("."),
    read_model_root: Path | str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the Chief fleet-health read-model from real sources."""
    root = Path(repo_root).resolve()
    rm_root = Path(read_model_root) if read_model_root else root / DEFAULT_READ_MODEL_ROOT

    presence_path = rm_root / "agent_presence.json"
    sync_path = rm_root / "sync_health.json"

    presence = _read_json(presence_path)
    sync = _read_json(sync_path)

    presence_freshness = _freshness_of(presence_path, presence)
    sync_freshness = _freshness_of(sync_path, sync)

    agent_health = _agent_health_summary(presence) if presence else None
    sync_health = _sync_health_summary(sync) if sync else None
    git_data = _git_milestones(root)

    sources: list[dict[str, Any]] = []
    if presence:
        sources.append({
            "source_ref": AGENT_PRESENCE_REF,
            "present": True,
            "freshness": presence_freshness,
            "role": "Agent runtime state (per-agent actual/desired/blocker)",
        })
    else:
        sources.append({
            "source_ref": AGENT_PRESENCE_REF,
            "present": False,
            "freshness": {},
            "role": "Agent runtime state (per-agent actual/desired/blocker)",
        })

    if sync:
        sources.append({
            "source_ref": SYNC_HEALTH_REF,
            "present": True,
            "freshness": sync_freshness,
            "role": "Mac/PC read-model sync posture",
        })
    else:
        sources.append({
            "source_ref": SYNC_HEALTH_REF,
            "present": False,
            "freshness": {},
            "role": "Mac/PC read-model sync posture",
        })

    sources.append({
        "source_ref": GIT_MILESTONES_REF,
        "present": git_data["available"],
        "freshness": {"as_of": generated_at or _utc_now(), "source_ref": GIT_MILESTONES_REF},
        "role": "Recently shipped engineering milestones",
    })

    grounded_facts: list[dict[str, Any]] = []

    if agent_health:
        grounded_facts.append({
            "topic": "fleet_health",
            "label": "Agent fleet health summary",
            "value": agent_health["summary"],
            "source_ref": AGENT_PRESENCE_REF,
            "freshness": presence_freshness,
            "pii_tier": "PUBLIC",
        })

    if sync_health:
        grounded_facts.append({
            "topic": "sync_health",
            "label": "Mac/PC sync health posture",
            "value": sync_health["summary"],
            "source_ref": SYNC_HEALTH_REF,
            "freshness": sync_freshness,
            "pii_tier": "PUBLIC",
        })

    if git_data["available"] and git_data["milestones"]:
        top = git_data["milestones"][:5]
        lines = [f"{m['commit']}: {m['summary']}" for m in top]
        value = f"{git_data['count']} recent milestones on {git_data['branch']}. Latest: {'; '.join(lines)}."
        grounded_facts.append({
            "topic": "shipped_milestones",
            "label": "Recently shipped engineering milestones",
            "value": value,
            "source_ref": GIT_MILESTONES_REF,
            "freshness": {"as_of": generated_at or _utc_now(), "source_ref": GIT_MILESTONES_REF},
            "pii_tier": "PUBLIC",
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "generated_by": "chief_agent_fleet_health.py",
        "sources": sources,
        "agent_health": agent_health,
        "sync_health": sync_health,
        "git_milestones": git_data,
        "grounded_facts": grounded_facts,
        "grounded_fact_count": len(grounded_facts),
        "agent_activation_allowed": False,
        "repair_authority_added": False,
        "send_authority_added": False,
        "note": (
            "Chief fleet-health: grounded facts from agent_presence.json, sync_health.json, and git log. "
            "Read-only. No agent activation, no repair, no sends."
        ),
    }


def format_operator(payload: dict[str, Any]) -> str:
    lines = [
        "# Chief Agent Fleet Health v0",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Fleet Health",
    ]
    ah = payload.get("agent_health") or {}
    if ah:
        lines.append(f"- {ah.get('summary', 'no data')}")
        online = ah.get("online_agents") or []
        degraded = ah.get("degraded_agents") or []
        offline = ah.get("offline_agents") or []
        if online:
            lines.append(f"  - Online: {', '.join(online)}")
        if degraded:
            lines.append(f"  - Degraded: {', '.join(degraded)}")
        if offline:
            lines.append(f"  - Offline: {', '.join(offline)}")
    else:
        lines.append("- No agent presence data available.")

    lines.extend(["", "## Sync Health"])
    sh = payload.get("sync_health") or {}
    if sh:
        lines.append(f"- {sh.get('summary', 'no data')}")
    else:
        lines.append("- No sync health data available.")

    lines.extend(["", "## Recent Milestones"])
    gm = payload.get("git_milestones") or {}
    if gm.get("available") and gm.get("milestones"):
        lines.append(f"Branch: `{gm['branch']}` — {gm['count']} milestones scanned.")
        for m in gm["milestones"][:5]:
            lines.append(f"- `{m['commit']}` {m['summary']}")
    else:
        lines.append("- Git milestone data unavailable.")

    lines.extend(["", "## Sources"])
    for src in payload.get("sources") or []:
        present = "present" if src.get("present") else "MISSING"
        freshness = (src.get("freshness") or {}).get("as_of") or "unknown"
        lines.append(f"- `{src['source_ref']}` ({present}, as-of: {freshness})")

    lines.extend(["", "## Boundaries", "- No agent activation.", "- No repair authority.", "- No sends."])
    return "\n".join(lines) + "\n"


def export_chief_agent_fleet_health(
    *,
    repo_root: Path | str = Path("."),
    read_model_root: Path | str | None = None,
    export_root: Path | str = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Generate and write the fleet-health read model. Returns a summary dict."""
    root = Path(repo_root).resolve()
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = build_chief_agent_fleet_health(
        repo_root=root,
        read_model_root=read_model_root,
        generated_at=generated_at,
    )

    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(_stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator(payload), encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "json_path": str(json_path.relative_to(root)),
        "operator_path": str(operator_path.relative_to(root)),
        "grounded_fact_count": payload["grounded_fact_count"],
        "agent_health_available": payload["agent_health"] is not None,
        "sync_health_available": payload["sync_health"] is not None,
        "git_milestones_available": (payload.get("git_milestones") or {}).get("available", False),
    }


def main() -> int:
    import sys
    root = Path(__file__).resolve().parent
    summary = export_chief_agent_fleet_health(
        repo_root=root,
        export_root=DEFAULT_EXPORT_ROOT,
    )
    print(f"wrote {summary['json_path']} :: {summary['grounded_fact_count']} grounded facts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
