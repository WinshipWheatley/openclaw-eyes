#!/usr/bin/env python3
"""Build deterministic fleet wake coverage from registry and monitor state."""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping


REGISTRY_SCHEMA_VERSION = "openclaw_fleet_coordination_registry_v2b"
COVERAGE_SCHEMA_VERSION = "openclaw_fleet_coordination_coverage_v2b"
WATCHER_SCHEMA_VERSION = "openclaw_fleet_watcher_state_v2b"
DOORBELL_VALUES = frozenset({"yes", "no"})
MIDTURN_VALUES = frozenset({"yes", "no", "unsupported"})
_COUNT_KEYS = ("doorbell", "midturn", "normal", "urgent", "coalesced", "failures")


class RegistryError(ValueError):
    """Raised when the reviewed fleet registry is malformed."""


def _regular_non_symlink(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode)


def resolve_path_ref(ref: str, *, repo_root: Path, board_root: Path) -> Path:
    text = str(ref or "")
    if text.startswith("repo:"):
        root, relative = repo_root, text.removeprefix("repo:")
    elif text.startswith("board:"):
        root, relative = board_root, text.removeprefix("board:")
    else:
        raise RegistryError("path_ref_prefix_invalid")
    candidate = Path(relative)
    if candidate.is_absolute() or not relative or any(part == ".." for part in candidate.parts):
        raise RegistryError("path_ref_traversal")
    return root / candidate


def load_registry(path: Path) -> dict[str, Any]:
    if not _regular_non_symlink(path):
        raise RegistryError("registry_not_regular")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError("registry_unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise RegistryError("registry_schema_invalid")
    recipients = payload.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        raise RegistryError("registry_recipients_invalid")
    seen: set[str] = set()
    for row in recipients:
        if not isinstance(row, dict):
            raise RegistryError("registry_recipient_not_object")
        seat = str(row.get("seat") or "")
        if not seat:
            raise RegistryError("registry_seat_required")
        if seat in seen:
            raise RegistryError(f"duplicate_seat:{seat}")
        seen.add(seat)
        refs = row.get("inbound_refs")
        if not isinstance(refs, list) or not refs or any(not isinstance(item, str) for item in refs):
            raise RegistryError(f"registry_inbound_refs_invalid:{seat}")
        for ref in (*refs, row.get("outbound_ref")):
            resolve_path_ref(str(ref or ""), repo_root=Path("/repo"), board_root=Path("/board"))
        delivery = row.get("delivery")
        if not isinstance(delivery, dict):
            raise RegistryError(f"registry_delivery_invalid:{seat}")
        if delivery.get("doorbell") not in DOORBELL_VALUES:
            raise RegistryError(f"registry_doorbell_invalid:{seat}")
        if delivery.get("midturn") not in MIDTURN_VALUES:
            raise RegistryError(f"registry_midturn_invalid:{seat}")
        if row.get("kind") == "codex_session" and delivery.get("doorbell") == "yes":
            for field in ("thread_id", "codex_cli", "codex_home", "repo_root"):
                if not str(delivery.get(field) or ""):
                    raise RegistryError(f"registry_codex_{field}_required:{seat}")
    return payload


def _read_json(path: Path) -> Mapping[str, Any] | None:
    if not _regular_non_symlink(path):
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _counts(value: object) -> dict[str, int]:
    mapping = value if isinstance(value, Mapping) else {}
    return {
        key: int(mapping.get(key, 0))
        if isinstance(mapping.get(key, 0), int) and not isinstance(mapping.get(key, 0), bool)
        else 0
        for key in _COUNT_KEYS
    }


def build_coverage(
    registry: Mapping[str, Any],
    *,
    watcher_dir: Path,
    checkin_dir: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    recipients = registry.get("recipients") if isinstance(registry.get("recipients"), list) else []
    for configured in sorted(recipients, key=lambda row: str(row.get("seat") or "")):
        seat = str(configured.get("seat") or "")
        delivery = configured.get("delivery") if isinstance(configured.get("delivery"), Mapping) else {}
        watcher = _read_json(watcher_dir / f"WATCHER-{seat}.json")
        watcher_valid = bool(
            watcher
            and watcher.get("schema_version") == WATCHER_SCHEMA_VERSION
            and watcher.get("seat") == seat
        )
        infrastructure = (
            str(watcher.get("monitor_status") or "invalid")
            if watcher_valid and watcher is not None
            else "missing"
        )
        doorbell = str(delivery.get("doorbell") or "no")
        midturn = str(delivery.get("midturn") or "no")
        if watcher_valid and watcher is not None:
            if watcher.get("doorbell") == "no":
                doorbell = "no"
            if watcher.get("midturn") in MIDTURN_VALUES and watcher.get("midturn") != "yes":
                midturn = str(watcher.get("midturn"))
        checkin = _read_json(checkin_dir / f"CHECKIN-{seat}.json")
        checkin_status = (
            str(checkin.get("status") or "unknown")
            if checkin and checkin.get("seat") == seat
            else "missing"
        )
        configured_kick = bool(configured.get("needs_operator_kick", False))
        needs_operator_kick = configured_kick or infrastructure != "ready"
        if watcher_valid and watcher is not None:
            needs_operator_kick = needs_operator_kick or bool(
                watcher.get("needs_operator_kick", False)
            )
        rows.append(
            {
                "seat": seat,
                "kind": str(configured.get("kind") or ""),
                "checkin_status": checkin_status,
                "infrastructure": infrastructure,
                "doorbell": doorbell,
                "midturn": midturn,
                "needs_operator_kick": needs_operator_kick,
                "watched_lanes": list(watcher.get("watched_lanes") or [])
                if watcher_valid and watcher is not None
                else list(configured.get("inbound_refs") or []),
                "last_event_id": str(watcher.get("last_event_id") or "")
                if watcher_valid and watcher is not None
                else "",
                "last_delivery": str(watcher.get("last_delivery") or "")
                if watcher_valid and watcher is not None
                else "",
                "last_detail": str(watcher.get("last_detail") or "")
                if watcher_valid and watcher is not None
                else str(delivery.get("blocker") or ""),
                "delivery_counts": _counts(watcher.get("delivery_counts"))
                if watcher_valid and watcher is not None
                else _counts({}),
            }
        )
    return {
        "schema_version": COVERAGE_SCHEMA_VERSION,
        "advisory_only": True,
        "liveness_source": "watcher_state_not_model_heartbeat",
        "recipients": rows,
    }


def _atomic_output(path: Path, encoded: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_coverage(payload: Mapping[str, Any], *, outputs: tuple[Path, ...]) -> None:
    encoded = (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
    for output in outputs:
        _atomic_output(output, encoded)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--watcher-dir", type=Path, required=True)
    parser.add_argument("--checkin-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, action="append", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    coverage = build_coverage(
        load_registry(args.registry),
        watcher_dir=args.watcher_dir,
        checkin_dir=args.checkin_dir,
    )
    write_coverage(coverage, outputs=tuple(args.output))
    print(json.dumps(coverage, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
