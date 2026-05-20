#!/usr/bin/env python3
"""Export the operator nested lane and mission package spine read-model."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_nested_lane_mission_package_spine import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
