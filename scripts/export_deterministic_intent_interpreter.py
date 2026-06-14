#!/usr/bin/env python3
"""Export the deterministic OpenClaw intent interpreter read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import deterministic_intent_interpreter


def main(argv: list[str] | None = None) -> int:
    return deterministic_intent_interpreter.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
