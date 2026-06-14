#!/usr/bin/env python3
"""Export LM Readiness Dashboard v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm_readiness_dashboard


if __name__ == "__main__":
    raise SystemExit(lm_readiness_dashboard.main())
