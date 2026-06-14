#!/usr/bin/env python3
"""Export the deterministic OpenClaw portable capability index."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_capability_index


if __name__ == "__main__":
    raise SystemExit(openclaw_capability_index.main())
