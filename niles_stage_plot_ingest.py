"""Stage-plot email ingest for Niles X32 show-profile generation.

This module accepts already-received email/webhook payloads.  It does not
connect to mailboxes, send messages, mutate hardware, or load a live console.
It produces deterministic X32 scene/OSC lines for later approved streaming via
``niles_x32_osc_controller``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from niles_x32_osc_controller import parse_scene_line


SCHEMA_VERSION = "niles_stage_plot_ingest_v0"
DEFAULT_SOURCE_BASE = 32
DEFAULT_GAIN = 0.5
DEFAULT_SEND_LEVEL = 0.5
MAX_X32_CHANNEL_NAME = 12


@dataclass(frozen=True)
class StageInput:
    channel: int
    name: str
    source: int
    color: int
    icon: int = 1
    default_gain: float = DEFAULT_GAIN


@dataclass(frozen=True)
class MonitorSend:
    bus: int
    label: str
    source_names: tuple[str, ...]
    level: float = DEFAULT_SEND_LEVEL


@dataclass(frozen=True)
class StagePlotProfile:
    schema_version: str
    source_surface: str
    subject: str
    sender: str
    inputs: tuple[StageInput, ...]
    monitor_sends: tuple[MonitorSend, ...]
    scene_lines: tuple[str, ...]
    authority_boundary: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["inputs"] = [asdict(item) for item in self.inputs]
        payload["monitor_sends"] = [asdict(item) for item in self.monitor_sends]
        return payload


AUTHORITY_BOUNDARY = {
    "email_read_performed": False,
    "email_send_performed": False,
    "hardware_control_performed": False,
    "live_scene_loaded": False,
    "operator_approval_required_before_load": True,
}

INPUT_LINE_RE = re.compile(
    r"^\s*(?:input|in|ch|channel)?\s*(?P<channel>\d{1,2})\s*(?:[-:.)]\s*|\s+)(?P<name>[A-Za-z][^#;]*)$",
    re.IGNORECASE,
)
MONITOR_LINE_RE = re.compile(
    r"^\s*(?P<label>(?:iem|monitor|mon|mix|bus)\s*(?P<bus>\d{1,2})(?:\s*/\s*\d{1,2})?)\s*[-:]\s*(?P<sources>.+)$",
    re.IGNORECASE,
)


def _message_text(payload: Mapping[str, Any] | str) -> tuple[str, str, str]:
    if isinstance(payload, str):
        return "", "", payload
    subject = str(payload.get("subject") or "")
    sender = str(payload.get("from") or payload.get("sender") or "")
    body = str(payload.get("body") or payload.get("text") or payload.get("plain_text") or "")
    return subject, sender, body


def normalize_channel_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(name or "").strip())
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", cleaned).strip()
    return cleaned[:MAX_X32_CHANNEL_NAME].strip() or "Input"


def color_for_name(name: str) -> int:
    text = str(name or "").lower()
    if any(term in text for term in ("kick", "snare", "tom", "drum", "hat", "oh ")):
        return 1
    if "bass" in text:
        return 2
    if any(term in text for term in ("gtr", "guitar", "acoustic")):
        return 4
    if any(term in text for term in ("key", "keys", "synth", "piano")):
        return 6
    if any(term in text for term in ("vox", "vocal", "lead")):
        return 8
    return 0


def _clean_input_name(raw: str) -> str:
    text = raw.strip()
    text = re.split(r"\s{2,}|,\s*mic\b|,\s*di\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return normalize_channel_name(text)


def _parse_sources(raw: str) -> tuple[str, ...]:
    parts = re.split(r",|/|\band\b", raw, flags=re.IGNORECASE)
    return tuple(normalize_channel_name(part) for part in parts if normalize_channel_name(part))


def parse_stage_plot_email(payload: Mapping[str, Any] | str, *, source_base: int = DEFAULT_SOURCE_BASE) -> tuple[tuple[StageInput, ...], tuple[MonitorSend, ...], dict[str, str]]:
    subject, sender, body = _message_text(payload)
    inputs: list[StageInput] = []
    monitors: list[MonitorSend] = []
    seen_channels: set[int] = set()
    for line in body.splitlines():
        monitor_match = MONITOR_LINE_RE.match(line)
        if monitor_match:
            bus = int(monitor_match.group("bus"))
            if 1 <= bus <= 16:
                monitors.append(
                    MonitorSend(
                        bus=bus,
                        label=normalize_channel_name(monitor_match.group("label")),
                        source_names=_parse_sources(monitor_match.group("sources")),
                    )
                )
            continue
        if re.search(r"\b(?:monitor|iem|bus|mix)\b", line, re.IGNORECASE):
            continue
        input_match = INPUT_LINE_RE.match(line)
        if not input_match:
            continue
        channel = int(input_match.group("channel"))
        if channel < 1 or channel > 32 or channel in seen_channels:
            continue
        name = _clean_input_name(input_match.group("name"))
        source = int(source_base) + channel - 1
        inputs.append(StageInput(channel=channel, name=name, source=source, color=color_for_name(name)))
        seen_channels.add(channel)
    return tuple(inputs), tuple(monitors), {"subject": subject, "sender": sender}


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _line(address: str, *args: Any) -> str:
    return " ".join([address, *(str(arg) if not isinstance(arg, str) else _quote(arg) for arg in args)])


def _input_lookup(inputs: Sequence[StageInput]) -> dict[str, StageInput]:
    lookup: dict[str, StageInput] = {}
    for item in inputs:
        lookup[item.name.lower()] = item
        for token in item.name.lower().split():
            lookup.setdefault(token, item)
    return lookup


def _monitor_scene_lines(inputs: Sequence[StageInput], monitor_sends: Sequence[MonitorSend]) -> list[str]:
    lookup = _input_lookup(inputs)
    lines: list[str] = []
    for monitor in monitor_sends:
        for source_name in monitor.source_names:
            source = lookup.get(source_name.lower())
            if source is None:
                for token in source_name.lower().split():
                    source = lookup.get(token)
                    if source is not None:
                        break
            if source is None:
                continue
            lines.append(_line(f"/ch/{source.channel:02d}/mix/{monitor.bus:02d}/level", monitor.level))
            lines.append(_line(f"/ch/{source.channel:02d}/mix/{monitor.bus:02d}/pan", 0.5))
    return lines


def generate_x32_scene_lines(inputs: Sequence[StageInput], monitor_sends: Sequence[MonitorSend] = ()) -> tuple[str, ...]:
    lines: list[str] = [
        "# Niles generated X32 stage-plot profile - review before load",
        "# Boundary: generated scene only; no live rack mutation performed.",
    ]
    for item in sorted(inputs, key=lambda row: row.channel):
        prefix = f"/ch/{item.channel:02d}"
        lines.extend(
            [
                _line(f"{prefix}/config/name", item.name),
                _line(f"{prefix}/config/color", item.color),
                _line(f"{prefix}/config/icon", item.icon),
                _line(f"{prefix}/config/source", item.source),
                _line(f"/headamp/{item.source:03d}/gain", item.default_gain),
                _line(f"{prefix}/eq/on", 1),
                _line(f"{prefix}/dyn/on", 0),
            ]
        )
    lines.extend(_monitor_scene_lines(inputs, monitor_sends))
    return tuple(lines)


def build_show_profile_from_email(payload: Mapping[str, Any] | str, *, source_surface: str = "inbound_email_webhook", source_base: int = DEFAULT_SOURCE_BASE) -> StagePlotProfile:
    inputs, monitor_sends, metadata = parse_stage_plot_email(payload, source_base=source_base)
    scene_lines = generate_x32_scene_lines(inputs, monitor_sends)
    return StagePlotProfile(
        schema_version=SCHEMA_VERSION,
        source_surface=source_surface,
        subject=metadata["subject"],
        sender=metadata["sender"],
        inputs=inputs,
        monitor_sends=monitor_sends,
        scene_lines=scene_lines,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )


def write_scene(profile: StagePlotProfile, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(profile.scene_lines) + "\n", encoding="utf-8")
    for line in profile.scene_lines:
        if line.startswith("#"):
            continue
        parsed = parse_scene_line(line)
        if parsed is None:
            raise ValueError(f"Generated invalid scene line: {line!r}")
    return target


def profile_to_json(profile: StagePlotProfile) -> str:
    return json.dumps(profile.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


__all__ = [
    "AUTHORITY_BOUNDARY",
    "DEFAULT_SOURCE_BASE",
    "MonitorSend",
    "SCHEMA_VERSION",
    "StageInput",
    "StagePlotProfile",
    "build_show_profile_from_email",
    "color_for_name",
    "generate_x32_scene_lines",
    "normalize_channel_name",
    "parse_stage_plot_email",
    "profile_to_json",
    "write_scene",
]
