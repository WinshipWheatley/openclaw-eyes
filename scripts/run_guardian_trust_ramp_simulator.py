#!/usr/bin/env python3
"""Run Guardian Trust Ramp Simulator v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import guardian_trust_ramp_simulator


if __name__ == "__main__":
    raise SystemExit(guardian_trust_ramp_simulator.main())
