"""Deterministic renderers shared by typed-contract adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")


def _load(root: str | Path, name: str) -> dict[str, Any]:
    try:
        payload = json.loads((Path(root) / name).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _stale_days(payload: Mapping[str, Any]) -> int | None:
    if not payload:
        return None
    try:
        from read_model_freshness_audit import _parse_date, _timestamp_from_payload, _today

        parsed = _parse_date(_timestamp_from_payload(payload))
        return None if parsed is None else (_today() - parsed).days
    except Exception:
        return None


def render_niles_status(*, read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT) -> str:
    lines: list[str] = []
    try:
        from niles_x32_capability import _handle_status

        rig_reply = _handle_status(allow_network=False, controller_factory=None)["reply"]
        lines.append(f"Rig: {rig_reply}")
    except Exception:
        pass

    registry = _load(read_model_root, "niles_track_registry.json")
    stale = _stale_days(registry)
    if registry and stale is not None and stale > 30:
        lines.append("Tracks: registry data is stale, excluded.")
    elif registry:
        track_count = registry.get("track_count")
        summary = registry.get("status_summary") if isinstance(registry.get("status_summary"), Mapping) else {}
        summary_text = ", ".join(f"{count} {status}" for status, count in summary.items())
        lines.append(
            f"Tracks: {track_count} in flight ({summary_text})."
            if summary_text
            else f"Tracks: {track_count} in flight."
        )

    if not lines:
        return "I don't have current Niles status data to report -- the usual read models are missing or stale."
    return "\n".join(lines)


def render_hermes_status(*, read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT) -> str:
    presence = _load(read_model_root, "agent_presence.json")
    hermes_row: Mapping[str, Any] | None = None
    presence_days = _stale_days(presence)
    if presence and presence_days is not None and presence_days <= 3:
        for row in presence.get("agents") or ():
            if isinstance(row, Mapping) and str(row.get("agent_id") or "").lower() == "hermes":
                hermes_row = row
                break

    if presence and (presence_days is None or presence_days > 3):
        presence_line = "Hermes runtime presence snapshot is stale or undated, so I excluded it."
    elif hermes_row is None:
        presence_line = "Hermes runtime presence is not currently evidenced."
    else:
        state = str(hermes_row.get("actual_state") or "unknown").replace("_", " ")
        observed = str(hermes_row.get("observed_at") or hermes_row.get("last_seen_at") or "").strip()
        presence_line = f"Hermes runtime: {state}"
        if observed:
            presence_line += f" (observed {observed})"
        presence_line += "."

    sidecar = _load(read_model_root, "openclaw_hermes_sidecar.json")
    sidecar_days = _stale_days(sidecar)
    if sidecar and sidecar_days is not None and sidecar_days <= 3:
        posture = sidecar.get("current_posture") if isinstance(sidecar.get("current_posture"), Mapping) else {}
        status = str(posture.get("status") or sidecar.get("readiness") or "available").replace("_", " ").lower()
        advisory_line = f"Advisory snapshot: {status}."
    elif sidecar:
        advisory_line = "Advisory snapshot is stale, so I excluded it from current status."
    else:
        advisory_line = "Advisory snapshot is unavailable; I am not claiming it is healthy."

    return f"{presence_line} {advisory_line} Read-only status; no model or action ran."


__all__ = ["render_hermes_status", "render_niles_status"]
