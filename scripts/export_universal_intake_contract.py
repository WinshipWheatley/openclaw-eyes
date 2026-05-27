#!/usr/bin/env python3
"""Export Universal Intake Contract v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import universal_intake_contract


if __name__ == "__main__":
    raise SystemExit(universal_intake_contract.main())
