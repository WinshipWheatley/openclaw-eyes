"""No-response watchdog for the file bridge.

Detects deposited mission-control requests that are older than a timeout and
have neither a terminal response nor an in-flight processing marker. It emits
Hermes observer suggestions only; it never restarts services or mutates the bus.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping


DEFAULT_INBOX = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")
DEFAULT_AGENT_PRESENCE = Path("/home/openclaw/generated/read_models/agent_presence.json")
DEFAULT_TIMEOUT_S = 180.0

SERVICE_BY_AGENT = {
    "hermes": "hermes-gateway.service",
    "maestro": "openclaw-request-response.service",
    "cassandra": "cassandra-listener.service",
    "chief": "chief-listener.service",
    "niles": "niles-listener.service",
    "producer": "producer-listener.service",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _request_files(inbox: Path) -> list[Path]:
    if not inbox.exists() or not inbox.is_dir():
        return []
    return sorted(
        path
        for path in inbox.glob("mission_control_*request*.json")
        if path.is_file()
    )


def _agent_from_lane(lane: str) -> str:
    normalized = str(lane or "").strip().lower()
    for agent in SERVICE_BY_AGENT:
        if agent in normalized:
            return agent
    if "telegram_pc_maestro_listener" in normalized:
        return "maestro"
    return normalized.replace("-", "_").split("_")[0] or "unknown"


def _response_keys(payload: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for key in ("source_request_filename", "source_request_id", "request_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            keys.add(value)
            keys.add(Path(value).stem)
    return keys


def _answered_keys(response_dir: Path) -> tuple[set[str], dict[str, Mapping[str, Any]]]:
    keys: set[str] = set()
    latest_by_key: dict[str, Mapping[str, Any]] = {}
    manifest = _read_json(response_dir / "response_manifest.json")
    responses = manifest.get("responses") if isinstance(manifest.get("responses"), list) else []
    for row in responses:
        if not isinstance(row, Mapping):
            continue
        row_keys = _response_keys(row)
        keys.update(row_keys)
        for key in row_keys:
            latest_by_key[key] = row

    if response_dir.exists():
        for path in response_dir.glob("openclaw_response_for_mac_*.json"):
            if path.name.endswith("_latest.json") or path.name == "openclaw_response_for_mac_latest.json":
                continue
            payload = _read_json(path)
            row_keys = _response_keys(payload)
            keys.update(row_keys)
            for key in row_keys:
                latest_by_key[key] = payload
    return keys, latest_by_key


def _processing_keys(response_dir: Path) -> set[str]:
    keys: set[str] = set()
    if not response_dir.exists():
        return keys
    for path in response_dir.glob("openclaw_processing_for_mac*.json"):
        payload = _read_json(path)
        keys.update(_response_keys(payload))
        stem = path.stem.replace("openclaw_processing_for_mac_", "")
        if stem:
            keys.add(stem)
    return keys


def _systemctl_state(service: str) -> str:
    if not service:
        return "unknown"
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return f"probe_error:{type(exc).__name__}"
    return (result.stdout or result.stderr or "").strip() or f"exit_{result.returncode}"


def _presence_context(agent_presence_path: Path, agent: str) -> str:
    payload = _read_json(agent_presence_path)
    agents = payload.get("agents") if isinstance(payload.get("agents"), list) else []
    for row in agents:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("agent_id") or "").strip().lower() != agent:
            continue
        blocker = str(row.get("blocker") or "").strip()
        recovery = row.get("recovery_actions")
        parts = []
        if blocker:
            parts.append(f"presence_blocker={blocker}")
        if recovery:
            parts.append("recovery_actions_present=True")
        return "; ".join(parts)
    return ""


def _request_key_set(path: Path, payload: Mapping[str, Any]) -> set[str]:
    keys = {path.name, path.stem}
    for key in ("source_request_id", "request_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            keys.add(value)
            keys.add(Path(value).stem)
    return keys


def no_response_observer(
    *,
    inbox: Path = DEFAULT_INBOX,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    agent_presence_path: Path = DEFAULT_AGENT_PRESENCE,
    now: datetime | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    systemctl_fn: Callable[[str], str] | None = None,
) -> list[dict[str, Any]]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    answered, latest_by_key = _answered_keys(response_dir)
    processing = _processing_keys(response_dir)
    silent_by_agent: dict[str, list[dict[str, Any]]] = {}

    for path in _request_files(inbox):
        payload = _read_json(path)
        created = _parse_time(payload.get("created_at"))
        if created is None:
            continue
        age_s = (now - created).total_seconds()
        if age_s <= timeout_s:
            continue
        keys = _request_key_set(path, payload)
        if keys & answered:
            continue
        if keys & processing:
            continue
        lane = str(payload.get("lane") or payload.get("source_channel") or "").strip()
        agent = _agent_from_lane(lane)
        silent_by_agent.setdefault(agent, []).append(
            {
                "path": path,
                "payload": payload,
                "age_s": age_s,
                "keys": keys,
                "lane": lane,
            }
        )

    suggestions: list[dict[str, Any]] = []
    probe = systemctl_fn or _systemctl_state
    for agent, rows in sorted(silent_by_agent.items()):
        rows.sort(key=lambda row: str(row["payload"].get("created_at") or ""))
        oldest = rows[0]
        service = SERVICE_BY_AGENT.get(agent, "")
        active_state = probe(service) if service else "unknown_service"
        last_failure = ""
        for key in oldest["keys"]:
            row = latest_by_key.get(key)
            if row and str(row.get("internal_status") or "").startswith("FAILED"):
                last_failure = str(row.get("why_it_happened") or row.get("operator_headline") or "").strip()
                break
        presence = _presence_context(agent_presence_path, agent)
        evidence_parts = [
            f"{len(rows)} requests to {agent} (lane {oldest['lane'] or 'unknown'}) unanswered >{int(timeout_s)}s",
            f"oldest={oldest['path'].name} at {oldest['payload'].get('created_at')}",
            f"is-active({service or 'unknown'})={active_state}",
            f"last service_failed: {last_failure or 'none'}",
        ]
        if presence:
            evidence_parts.append(presence)
        suggestions.append(
            {
                "id": f"no_response_{agent}",
                "problem": f"{agent} lane has old request(s) with no response receipt",
                "evidence": "; ".join(evidence_parts),
                "build_goal": (
                    f"Investigate and repair no-response handling for {agent} lane requests: "
                    "join deposited bridge requests to response receipts, diagnose service state, "
                    "and keep recovery Guardian-gated rather than auto-restarting production."
                ),
                "severity": "high",
                "source": "no_response_watchdog",
            }
        )
    return suggestions


__all__ = ["no_response_observer"]
