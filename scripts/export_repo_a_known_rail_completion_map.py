#!/usr/bin/env python3
"""Export the Repo A known rail completion map read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from repo_a_known_rail_completion_map import main


if __name__ == "__main__":
    raise SystemExit(main())
