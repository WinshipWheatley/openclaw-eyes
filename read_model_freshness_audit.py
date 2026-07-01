#!/usr/bin/env python3
"""Audit freshness of read-models that feed agent/front-door packets.

This is intentionally read-only. It inventories the explicit read-model constants used by
packet builders, classifies their timestamps, and emits a compact JSON report so stale
packet sources cannot quietly age for weeks.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_STALE_AFTER_DAYS = 14
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse_date(raw: str) -> date | None:
    match = _DATE_RE.search(str(raw or ""))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _today() -> date:
    return date.today()


def _timestamp_from_payload(payload: Mapping[str, Any]) -> str:
    for key in ("generated_at", "updated_at", "as_of", "observed_at", "created_at"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    run = payload.get("run")
    if isinstance(run, Mapping):
        value = run.get("generated_at") or run.get("updated_at")
        if isinstance(value, str) and value.strip():
            return value.strip()
    freshness = payload.get("freshness")
    if isinstance(freshness, Mapping):
        value = freshness.get("as_of") or freshness.get("generated_at") or freshness.get("updated_at")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def discover_packet_read_models() -> list[str]:
    names: set[str] = set()
    modules = (
        ("maestro_context_packet", "KNOWN_READ_MODELS"),
        ("cassandra_context_packet", "CASSANDRA_READ_MODELS"),
        ("hermes_context_packet", "HERMES_READ_MODELS"),
    )
    for module_name, attr in modules:
        try:
            module = __import__(module_name)
            values = getattr(module, attr, ())
        except Exception:
            continue
        for value in values:
            name = str(value or "").strip()
            if name.endswith(".json"):
                names.add(Path(name).name)
    return sorted(names)


def _producer_hints(name: str, *, repo_root: Path) -> list[str]:
    """Cheap hints only; not a proof of producer coverage."""
    stem = Path(name).stem
    candidates = [
        repo_root / f"{stem}.py",
        repo_root / "scripts" / f"{stem}.py",
        repo_root / "scripts" / f"generate_{stem}.py",
        repo_root / "scripts" / f"export_{stem}.py",
    ]
    return [path.as_posix() for path in candidates if path.exists()]


def audit_read_models(
    names: Iterable[str],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: Path = Path("."),
    today: date | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    today = today or _today()
    items: list[dict[str, Any]] = []
    for raw_name in sorted({Path(str(name)).name for name in names if str(name or "").strip()}):
        path = read_model_root / raw_name
        item: dict[str, Any] = {
            "name": raw_name,
            "path": path.as_posix(),
            "timestamp": "",
            "age_days": None,
            "freshness_status": "unknown",
            "producer_hints": _producer_hints(raw_name, repo_root=repo_root),
        }
        if not path.exists():
            item["freshness_status"] = "missing_file"
            items.append(item)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            item["freshness_status"] = "bad_json"
            item["error_type"] = type(exc).__name__
            items.append(item)
            continue
        if not isinstance(payload, Mapping):
            item["freshness_status"] = "bad_json"
            item["error_type"] = "non_object_json"
            items.append(item)
            continue
        timestamp = _timestamp_from_payload(payload)
        item["timestamp"] = timestamp
        parsed = _parse_date(timestamp)
        if parsed is None:
            item["freshness_status"] = "missing_timestamp"
            items.append(item)
            continue
        age_days = (today - parsed).days
        item["age_days"] = age_days
        item["freshness_status"] = "stale" if age_days >= stale_after_days else "fresh"
        items.append(item)

    problem_statuses = {"stale", "missing_file", "missing_timestamp", "bad_json", "unknown"}
    summary = {
        "read_model_count": len(items),
        "problem_count": sum(1 for item in items if item["freshness_status"] in problem_statuses),
        "stale_count": sum(1 for item in items if item["freshness_status"] == "stale"),
        "missing_file_count": sum(1 for item in items if item["freshness_status"] == "missing_file"),
        "missing_timestamp_count": sum(1 for item in items if item["freshness_status"] == "missing_timestamp"),
        "bad_json_count": sum(1 for item in items if item["freshness_status"] == "bad_json"),
        "stale_after_days": stale_after_days,
        "today": today.isoformat(),
    }
    return {"summary": summary, "items": items}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit packet read-model freshness")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--stale-after-days", type=int, default=DEFAULT_STALE_AFTER_DAYS)
    args = parser.parse_args()

    result = audit_read_models(
        discover_packet_read_models(),
        read_model_root=Path(args.read_model_root),
        repo_root=Path(args.repo_root),
        stale_after_days=args.stale_after_days,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["summary"]["problem_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
