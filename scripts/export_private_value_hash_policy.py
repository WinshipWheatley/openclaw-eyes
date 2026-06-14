#!/usr/bin/env python3
"""Export the private value HMAC policy read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_private_value_hash


def main(argv: list[str] | None = None) -> int:
    return openclaw_private_value_hash.main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
