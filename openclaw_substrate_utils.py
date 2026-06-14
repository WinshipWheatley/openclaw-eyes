"""Leaf-level deterministic helpers for OpenClaw substrate modules.

This module intentionally imports only the Python standard library. The SHA-256
file helper is for file-integrity comparison only; it is not a privacy boundary
and must not be used for PII matching or protected-value tokenization.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    if not is_dataclass(value):
        raise TypeError("dataclass_to_dict requires a dataclass instance")
    return asdict(value)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "dataclass_to_dict",
    "sha256_file",
    "stable_json",
    "utc_now",
]
