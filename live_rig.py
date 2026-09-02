"""Live rig as data: LIVE-RIG.md becomes a read model with the budget, the deal terms side by
side, open loops by owner with days waiting, and a proposed X32 channel map plus a .scn artifact
that answers the two open routing questions as proposals.

Artifact only. Nothing here touches the console, a DAW, audio, or a purchase. Loading the scene on
real hardware stays with the operator.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import showprofile

SCHEMA_VERSION = "live_rig_read_model_v0"
READ_MODEL_ID = "live_rig"
DEFAULT_CONFIG_PATH = Path("config/live_rig.v1.json")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_ARTIFACT_ROOT = Path("generated/artifacts/live_rig")
SCENE_FILENAME = "live_rig_proposed.scn"

AUTHORITY_BOUNDARY = {
    "console_write_performed": False,
    "scene_loaded_on_hardware": False,
    "daw_control_performed": False,
    "audio_ingested": False,
    "purchase_performed": False,
    "send_performed": False,
    "telegram_send_performed": False,
    "external_model_called": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dollars(minor_units: int, currency: str = "USD") -> str:
    prefix = "$" if currency == "USD" else f"{currency} "
    whole, cents = divmod(int(minor_units), 100)
    return f"{prefix}{whole:,}" if cents == 0 else f"{prefix}{whole:,}.{cents:02d}"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("live rig config must be a JSON object")
    return dict(payload)


def _budget(config: Mapping[str, Any]) -> dict[str, Any]:
    gear = [row for row in (config.get("gear_to_buy") or []) if isinstance(row, Mapping)]
    deal = config.get("deal") if isinstance(config.get("deal"), Mapping) else {}
    covered_ids = set(str(x) for x in (deal.get("fee_covers_device_ids") or []))
    total_low = sum(int(row.get("price_minor_units_low") or 0) for row in gear)
    total_high = sum(int(row.get("price_minor_units_high") or 0) for row in gear)
    covered_low = sum(int(row.get("price_minor_units_low") or 0) for row in gear if str(row.get("device_id")) in covered_ids)
    covered_high = sum(int(row.get("price_minor_units_high") or 0) for row in gear if str(row.get("device_id")) in covered_ids)
    self_funded = [str(row.get("label")) for row in gear if str(row.get("device_id")) not in covered_ids]
    fee_low = int(deal.get("fee_minor_units_low") or 0)
    fee_high = int(deal.get("fee_minor_units_high") or 0)
    return {
        "gear_total_minor_units_low": total_low,
        "gear_total_minor_units_high": total_high,
        "fee_minor_units_low": fee_low,
        "fee_minor_units_high": fee_high,
        "fee_covered_gear_minor_units_low": covered_low,
        "fee_covered_gear_minor_units_high": covered_high,
        "fee_after_covered_gear_minor_units_low": fee_low - covered_high,
        "fee_after_covered_gear_minor_units_high": fee_high - covered_low,
        "self_funded_items": self_funded,
        "self_funded_minor_units": total_high - covered_high,
    }


def _open_loops(config: Mapping[str, Any], *, today: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in config.get("open_loops") or []:
        if not isinstance(raw, Mapping):
            continue
        opened_text = str(raw.get("opened") or "")
        try:
            opened = date.fromisoformat(opened_text)
            days_open = (today - opened).days
        except ValueError:
            days_open = None
        rows.append(
            {
                "id": str(raw.get("id") or ""),
                "text": str(raw.get("text") or ""),
                "owner": str(raw.get("owner") or "me"),
                "opened": opened_text or None,
                "days_open": days_open,
                "blocked_on": str(raw.get("blocked_on") or "") or None,
                "unblocks": [str(x) for x in (raw.get("unblocks") or [])],
                "proposal": str(raw.get("proposal") or "") or None,
            }
        )
    # Mine first, then by how much each unblocks, then oldest.
    rows.sort(key=lambda row: (0 if row["owner"] == "me" else 1, -len(row["unblocks"]), -(row["days_open"] or 0), row["id"]))
    return rows


def proposed_channels(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    proposed = config.get("proposed_x32") if isinstance(config.get("proposed_x32"), Mapping) else {}
    channels: list[dict[str, Any]] = []
    for raw in proposed.get("channels") or []:
        if not isinstance(raw, Mapping):
            continue
        name = str(raw.get("name") or "").strip()
        category, color, icon = showprofile.categorize(name)
        channels.append(
            {
                "ch": int(raw.get("ch")),
                "name": name,
                "source": str(raw.get("source") or ""),
                "category": category,
                "color": str(raw.get("color") or color),
                "icon": int(raw.get("icon") or icon),
                "to_main": bool(raw.get("to_main", True)),
                "to_looper_send": bool(raw.get("to_looper_send", False)),
                "to_iem": bool(raw.get("to_iem", True)),
            }
        )
    return sorted(channels, key=lambda row: row["ch"])


def render_scene(config: Mapping[str, Any]) -> str:
    proposed = config.get("proposed_x32") if isinstance(config.get("proposed_x32"), Mapping) else {}
    scene_name = str(proposed.get("scene_name") or "Winship Loop v0")
    return showprofile.build_scene(proposed_channels(config), scene_name=scene_name)


def build_live_rig_read_model(
    config: Mapping[str, Any],
    *,
    today: date | None = None,
    generated_at: str | None = None,
    scene_path: str | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    generated_at = generated_at or _utc_now()
    currency = str(config.get("currency_iso") or "USD").upper()
    deal = dict(config.get("deal") or {})
    proposed = dict(config.get("proposed_x32") or {})
    loops = _open_loops(config, today=today)
    channels = proposed_channels(config)
    uncategorized = [row["name"] for row in channels if row["category"] == "other"]
    motion = [dict(row) for row in (config.get("also_in_motion") or []) if isinstance(row, Mapping)]
    for row in motion:
        window = row.get("window") or []
        if len(window) == 2:
            try:
                start = date.fromisoformat(str(window[0]))
                row["days_until_window"] = (start - today).days
            except ValueError:
                row["days_until_window"] = None
    deals_side_by_side = [
        {
            "deal": "Capital Hilton show development",
            "money": f"{_dollars(int(deal.get('fee_minor_units_low') or 0), currency)} to {_dollars(int(deal.get('fee_minor_units_high') or 0), currency)} upfront",
            "then": f"{_dollars(int((deal.get('catalog_rates') or {}).get('full_rig_night_minor_units') or 0), currency)}/night full rig, {_dollars(int((deal.get('catalog_rates') or {}).get('acoustic_night_minor_units') or 0), currency)} acoustic, consecutive-night blocks",
            "gear": "bought by me, stays mine",
            "next": " then ".join(str(step) for step in (deal.get("pitch_sequence") or [])),
        },
    ]
    for row in motion:
        deals_side_by_side.append(
            {
                "deal": str(row.get("what") or row.get("id")),
                "money": "not stated yet",
                "then": "window " + " to ".join(str(x) for x in (row.get("window") or [])),
                "gear": "acoustic or current rig",
                "next": f"waiting on {row.get('waiting_on')}",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "as_of": today.isoformat(),
        "source_ref": str(config.get("source_ref") or ""),
        "status": str(config.get("status") or ""),
        "last_updated": str(config.get("last_updated") or ""),
        "budget": _budget(config),
        "deals_side_by_side": deals_side_by_side,
        "deal_terms": [str(x) for x in (deal.get("terms") or [])],
        "gear_to_buy": [dict(row) for row in (config.get("gear_to_buy") or []) if isinstance(row, Mapping)],
        "gear_owned": [dict(row) for row in (config.get("gear_owned") or []) if isinstance(row, Mapping)],
        "signal_flow": [dict(row) for row in (config.get("signal_flow") or []) if isinstance(row, Mapping)],
        "design_rules": [str(x) for x in (config.get("design_rules") or [])],
        "open_loops": loops,
        "open_loops_by_owner": {
            owner: [row["id"] for row in loops if row["owner"] == owner]
            for owner in sorted({row["owner"] for row in loops})
        },
        "also_in_motion": motion,
        "routing_questions": [dict(row) for row in (config.get("routing_questions") or []) if isinstance(row, Mapping)],
        "proposed_x32": {
            "scene_name": str(proposed.get("scene_name") or ""),
            "confirmation_status": str(proposed.get("confirmation_status") or "proposed_not_confirmed"),
            "principle": str(proposed.get("principle") or ""),
            "channels": channels,
            "uncategorized_channels": uncategorized,
            "buses": [dict(row) for row in (proposed.get("buses") or []) if isinstance(row, Mapping)],
            "matrix": [dict(row) for row in (proposed.get("matrix") or []) if isinstance(row, Mapping)],
            "answers": dict(proposed.get("answers") or {}),
            "caveats": [str(x) for x in (proposed.get("caveats") or [])],
            "scene_artifact_path": scene_path,
        },
        "synth_audition": dict(config.get("synth_audition") or {}),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "artifact_only": True,
            "scene_loaded_on_hardware": False,
            "purchase_performed": False,
            "channel_count": len(channels),
            "uncategorized_channel_count": len(uncategorized),
        },
    }


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    budget = payload["budget"]
    lines = ["Live Rig v0", "", f"As of `{payload['as_of']}`, source `{payload['source_ref']}`, status `{payload['status']}`.", ""]
    lines.append(
        f"Budget: gear {_dollars(budget['gear_total_minor_units_low'])} to {_dollars(budget['gear_total_minor_units_high'])}; "
        f"fee {_dollars(budget['fee_minor_units_low'])} to {_dollars(budget['fee_minor_units_high'])} covers "
        f"{_dollars(budget['fee_covered_gear_minor_units_low'])} to {_dollars(budget['fee_covered_gear_minor_units_high'])} of it; "
        f"self-funded: {', '.join(budget['self_funded_items']) or 'nothing'} ({_dollars(budget['self_funded_minor_units'])})."
    )
    lines.append("")
    lines.append("Deals side by side:")
    for row in payload["deals_side_by_side"]:
        lines.append(f"- {row['deal']}: {row['money']}; then {row['then']}; gear {row['gear']}; next: {row['next']}.")
    lines.append("")
    lines.append("Open loops (mine first):")
    for row in payload["open_loops"]:
        blocked = f" (blocked on {row['blocked_on']})" if row.get("blocked_on") else ""
        proposal = " (proposal below)" if row.get("proposal") else ""
        lines.append(f"- [{row['owner']}] {row['text']}{blocked}{proposal}; {row['days_open']} days open.")
    lines.append("")
    proposed = payload["proposed_x32"]
    lines.append(f"Proposed X32 scene `{proposed['scene_name']}` ({proposed['confirmation_status']}):")
    for row in proposed["channels"]:
        flags = []
        if not row["to_main"]:
            flags.append("not on LR")
        if row["to_looper_send"]:
            flags.append("to looper send")
        suffix = f" [{'; '.join(flags)}]" if flags else ""
        lines.append(f"- ch {row['ch']:02d} {row['name']} ({row['color']}, icon {row['icon']}): {row['source']}{suffix}")
    for row in proposed["buses"]:
        lines.append(f"- bus {row['bus']} {row['name']}: {row['feeds']}")
    for row in proposed["matrix"]:
        lines.append(f"- matrix {row['matrix']} {row['name']}: {row['feeds']}")
    for key, answer in sorted(proposed["answers"].items()):
        lines.append(f"- answers `{key}`: {answer}")
    if proposed.get("scene_artifact_path"):
        lines.append(f"- artifact: `{proposed['scene_artifact_path']}`")
    for caveat in proposed["caveats"]:
        lines.append(f"- caveat: {caveat}")
    lines.append("")
    lines.append("Boundary: artifact only; the operator loads the scene; no purchase, no console write, no audio read.")
    return "\n".join(lines) + "\n"


def export_live_rig(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    today: date | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    artifacts = Path(artifact_root)
    artifacts.mkdir(parents=True, exist_ok=True)
    scene_path = artifacts / SCENE_FILENAME
    scene_path.write_text(render_scene(config), encoding="utf-8")
    payload = build_live_rig_read_model(config, today=today, generated_at=generated_at, scene_path=str(scene_path))
    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{READ_MODEL_ID}.json"
    operator_path = root / f"{READ_MODEL_ID}_OPERATOR.md"
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "scene_path": str(scene_path),
        "open_loop_count": len(payload["open_loops"]),
        "channel_count": payload["machine_proof"]["channel_count"],
        "uncategorized_channels": payload["proposed_x32"]["uncategorized_channels"],
    }
