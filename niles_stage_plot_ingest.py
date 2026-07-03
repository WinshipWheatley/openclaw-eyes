"""Email stage-plot adapter for the Niles X32 show-profile lane.

This is intentionally an intake adapter, not a second X32 scene generator. It
accepts already-received email/webhook payloads, normalizes their body text into
the same ``showprofile`` channel dictionaries the X32 lane already uses, and
returns a reviewable scene string. It does not read mailboxes, send email, open
sockets, or load a live desk.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping

from showprofile import build_scene, parse_input_list


SCHEMA_VERSION = "niles_stage_plot_ingest_v1"

AUTHORITY_BOUNDARY = {
    "email_read_performed": False,
    "email_send_performed": False,
    "hardware_control_performed": False,
    "live_scene_loaded": False,
    "operator_approval_required_before_load": True,
}

_EMAIL_INPUT_PREFIX_RE = re.compile(
    r"^\s*(?:input|in|channel)\s*(?P<channel>\d{1,2})\s*(?:[-:.)]\s*|\s+)(?P<name>\S.*)$",
    re.IGNORECASE,
)
_MONITOR_NOTE_RE = re.compile(r"^\s*(?:iem|monitor|mon|mix|bus)\s*\d{1,2}\b.*", re.IGNORECASE)
_HEADER_MARKERS = ("stage plot", "input list", "patch list", "channel list")


@dataclass(frozen=True)
class EmailStagePlotProfile:
    schema_version: str
    source_surface: str
    subject: str
    sender: str
    scene_name: str
    channels: tuple[dict[str, Any], ...]
    scene_text: str
    monitor_notes: tuple[str, ...]
    unparsed_lines: tuple[str, ...]
    authority_boundary: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_surface": self.source_surface,
            "subject": self.subject,
            "sender": self.sender,
            "scene_name": self.scene_name,
            "channels": [dict(channel) for channel in self.channels],
            "scene_text": self.scene_text,
            "monitor_notes": list(self.monitor_notes),
            "unparsed_lines": list(self.unparsed_lines),
            "authority_boundary": dict(self.authority_boundary),
        }


def _message_text(payload: Mapping[str, Any] | str) -> tuple[str, str, str]:
    if isinstance(payload, str):
        return "", "", payload
    subject = str(payload.get("subject") or "")
    sender = str(payload.get("from") or payload.get("sender") or "")
    body = str(payload.get("body") or payload.get("text") or payload.get("plain_text") or "")
    return subject, sender, body


def _normalize_input_line(line: str) -> str:
    match = _EMAIL_INPUT_PREFIX_RE.match(line)
    if not match:
        return line
    return f"{int(match.group('channel'))}. {match.group('name').strip()}"


def _looks_like_header(line: str) -> bool:
    text = line.strip().strip(":").lower()
    if not text:
        return True
    return any(marker in text for marker in _HEADER_MARKERS) and len(text) <= 80


def normalize_email_stage_plot_text(body: str) -> str:
    """Return body text normalized for ``showprofile.parse_input_list``."""

    return "\n".join(_normalize_input_line(line) for line in str(body or "").splitlines())


def _valid_channels(text: str) -> list[dict[str, Any]]:
    channels: list[dict[str, Any]] = []
    for channel in parse_input_list(text):
        try:
            channel_number = int(channel.get("ch", 0))
        except (TypeError, ValueError):
            continue
        if 1 <= channel_number <= 32:
            channels.append(dict(channel))
    return channels


def _parse_review_lines(body: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    monitor_notes: list[str] = []
    unparsed: list[str] = []
    for raw_line in str(body or "").splitlines():
        line = raw_line.strip()
        if not line or _looks_like_header(line):
            continue
        if _valid_channels(_normalize_input_line(line)):
            continue
        if _MONITOR_NOTE_RE.match(line):
            monitor_notes.append(line)
            continue
        unparsed.append(line)
    return tuple(monitor_notes), tuple(unparsed)


def _scene_name(subject: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(subject or "").strip())
    return cleaned or "Email Stage Plot"


def build_show_profile_from_email(
    payload: Mapping[str, Any] | str,
    *,
    source_surface: str = "inbound_email_payload",
) -> EmailStagePlotProfile:
    subject, sender, body = _message_text(payload)
    normalized_body = normalize_email_stage_plot_text(body)
    channels = tuple(_valid_channels(normalized_body))
    scene_name = _scene_name(subject)
    monitor_notes, unparsed_lines = _parse_review_lines(body)
    return EmailStagePlotProfile(
        schema_version=SCHEMA_VERSION,
        source_surface=source_surface,
        subject=subject,
        sender=sender,
        scene_name=scene_name,
        channels=channels,
        scene_text=build_scene(list(channels), scene_name=scene_name),
        monitor_notes=monitor_notes,
        unparsed_lines=unparsed_lines,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )


def profile_to_json(profile: EmailStagePlotProfile) -> str:
    return json.dumps(profile.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"


__all__ = [
    "AUTHORITY_BOUNDARY",
    "EmailStagePlotProfile",
    "SCHEMA_VERSION",
    "build_show_profile_from_email",
    "normalize_email_stage_plot_text",
    "profile_to_json",
]
