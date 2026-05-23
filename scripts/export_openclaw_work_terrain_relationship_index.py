#!/usr/bin/env python3
"""Export the OpenClaw Work Terrain Relationship Index read-model."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openclaw_work_terrain_relationship_index import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
