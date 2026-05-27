#!/usr/bin/env python3
"""Export the Gate 1 operational snapshot read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gate1_operational_snapshot


if __name__ == "__main__":
    raise SystemExit(gate1_operational_snapshot.main())
