#!/usr/bin/env python3
"""Export the deterministic OpenClaw session state resolver read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import session_state_resolver


def main(argv: list[str] | None = None) -> int:
    return session_state_resolver.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
