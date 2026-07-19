"""Closed contracts for fleet coordination WAKE records."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "openclaw_fleet_wake_v2"
KNOWN_SEATS = frozenset(
    {
        "PC-Sol",
        "Mac-Sol-Desktop",
        "Mac-Sol-VSCode",
        "Mac-Fable",
        "Gemini",
        "Opus",
    }
)
PRIORITIES = frozenset({"normal", "urgent"})
URGENT_REASONS = frozenset(
    {"operator_directive", "safety_stop", "blocking_confer"}
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class WakeContractError(ValueError):
    """Raised when a WAKE record violates the closed contract."""


@dataclass(frozen=True)
class WakePing:
    from_seat: str
    to_seat: str
    mission_id: str
    file: Path
    sha: str
    needs_human_kick: bool
    created_at: str
    priority: str
    urgent_reason: str = ""
    verification: str = "verified_v2"


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WakeContractError("wake_payload_not_object")
    return value


def _visible_text(value: object, *, field: str, required: bool = True) -> str:
    text = str(value or "")
    if required and not text:
        raise WakeContractError(f"{field}_required")
    if _CONTROL_PATTERN.search(text):
        raise WakeContractError(f"{field}_control_character")
    return text


def _seat(value: object, *, field: str) -> str:
    seat = _visible_text(value, field=field)
    if seat not in KNOWN_SEATS:
        raise WakeContractError(f"{field}_unknown_seat")
    return seat


def _reference(path_value: object) -> Path:
    text = _visible_text(path_value, field="file")
    path = Path(text)
    if not path.is_absolute():
        raise WakeContractError("reference_not_absolute")
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise WakeContractError("reference_not_regular") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise WakeContractError("reference_not_regular")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _priority_and_reason(payload: Mapping[str, Any]) -> tuple[str, str]:
    priority = _visible_text(payload.get("priority", "normal"), field="priority")
    if priority not in PRIORITIES:
        raise WakeContractError("priority_invalid")
    urgent_reason = _visible_text(
        payload.get("urgent_reason", ""),
        field="urgent_reason",
        required=False,
    )
    if priority == "urgent":
        if not urgent_reason:
            raise WakeContractError("urgent_reason_required")
        if urgent_reason not in URGENT_REASONS:
            raise WakeContractError("urgent_reason_invalid")
    elif urgent_reason:
        raise WakeContractError("urgent_reason_forbidden")
    return priority, urgent_reason


def _created_at(value: object) -> str:
    text = _visible_text(value, field="created_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WakeContractError("created_at_invalid") from exc
    if not text.endswith("Z") or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise WakeContractError("created_at_not_utc")
    return text


def _compact_timestamp(created_at: str) -> str:
    return created_at.replace("-", "").replace(":", "").replace(".", "")


def _validate_filename(path: Path, *, recipient: str, created_at: str = "") -> None:
    prefix = f"WAKE-{recipient}-"
    if not path.name.startswith(prefix):
        raise WakeContractError("filename_recipient_mismatch")
    if created_at and path.name != f"{prefix}{_compact_timestamp(created_at)}.json":
        raise WakeContractError("filename_timestamp_mismatch")


def _verify_reference(payload: Mapping[str, Any]) -> tuple[Path, str]:
    reference = _reference(payload.get("file"))
    expected_sha = _visible_text(payload.get("sha"), field="sha")
    if not _SHA256_PATTERN.fullmatch(expected_sha):
        raise WakeContractError("sha_invalid")
    if _sha256(reference) != expected_sha:
        raise WakeContractError("reference_sha_mismatch")
    return reference, expected_sha


def read_wake_ping(path: Path, *, recipient: str) -> WakePing:
    """Read and validate one v2 or legacy-normal WAKE record."""

    exact_recipient = _seat(recipient, field="recipient")
    _validate_filename(path, recipient=exact_recipient)
    try:
        payload = _mapping(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise WakeContractError("wake_payload_unreadable") from exc
    from_seat = _seat(payload.get("from"), field="from")
    to_seat = _seat(payload.get("to"), field="to")
    if to_seat != exact_recipient:
        raise WakeContractError("recipient_mismatch")
    reference, expected_sha = _verify_reference(payload)

    if payload.get("schema_version") != SCHEMA_VERSION:
        priority = _visible_text(payload.get("priority", "normal"), field="priority")
        if priority != "normal":
            raise WakeContractError("legacy_urgent_forbidden")
        needs_human_kick = payload.get("needs_human_kick")
        if not isinstance(needs_human_kick, bool):
            raise WakeContractError("needs_human_kick_not_boolean")
        return WakePing(
            from_seat=from_seat,
            to_seat=to_seat,
            mission_id="",
            file=reference,
            sha=expected_sha,
            needs_human_kick=needs_human_kick,
            created_at="",
            priority="normal",
            verification="unverified_legacy",
        )

    priority, urgent_reason = _priority_and_reason(payload)
    allowed = {
        "schema_version",
        "from",
        "to",
        "mission_id",
        "file",
        "sha",
        "needs_human_kick",
        "created_at",
        "priority",
    }
    if priority == "urgent":
        allowed.add("urgent_reason")
    if set(payload) != allowed:
        raise WakeContractError("wake_schema_fields_invalid")
    mission_id = _visible_text(payload.get("mission_id"), field="mission_id")
    needs_human_kick = payload.get("needs_human_kick")
    if not isinstance(needs_human_kick, bool):
        raise WakeContractError("needs_human_kick_not_boolean")
    created_at = _created_at(payload.get("created_at"))
    _validate_filename(path, recipient=exact_recipient, created_at=created_at)
    return WakePing(
        from_seat=from_seat,
        to_seat=to_seat,
        mission_id=mission_id,
        file=reference,
        sha=expected_sha,
        needs_human_kick=needs_human_kick,
        created_at=created_at,
        priority=priority,
        urgent_reason=urgent_reason,
    )


def _utc_text(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise WakeContractError("created_at_timezone_required")
    exact = now.astimezone(timezone.utc)
    timespec = "microseconds" if exact.microsecond else "seconds"
    return exact.isoformat(timespec=timespec).replace("+00:00", "Z")


def write_wake_ping(
    *,
    wake_dir: Path,
    from_seat: str,
    to_seat: str,
    mission_id: str,
    reference_path: Path,
    priority: str = "normal",
    urgent_reason: str | None = None,
    needs_human_kick: bool = False,
    now: datetime | None = None,
) -> Path:
    """Atomically write a new closed-schema WAKE record without overwriting one."""

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "from": _seat(from_seat, field="from"),
        "to": _seat(to_seat, field="to"),
        "mission_id": _visible_text(mission_id, field="mission_id"),
        "file": str(_reference(reference_path)),
        "sha": _sha256(_reference(reference_path)),
        "needs_human_kick": bool(needs_human_kick),
        "created_at": _utc_text(now or datetime.now(timezone.utc)),
        "priority": _visible_text(priority, field="priority"),
    }
    if urgent_reason is not None:
        payload["urgent_reason"] = urgent_reason
    _priority_and_reason(payload)

    wake_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = wake_dir / (
        f"WAKE-{payload['to']}-{_compact_timestamp(payload['created_at'])}.json"
    )
    if destination.exists():
        raise WakeContractError("wake_destination_exists")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=wake_dir,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination
