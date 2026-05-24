#!/usr/bin/env python3
"""Export the OpenClaw Work Terrain Surface Map Build Cue Scout read-model."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from work_terrain_surface_map_build_cue_scout import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
