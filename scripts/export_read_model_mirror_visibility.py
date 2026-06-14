#!/usr/bin/env python3
"""Export Read-Model Mirror Visibility v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import read_model_mirror_visibility


if __name__ == "__main__":
    raise SystemExit(read_model_mirror_visibility.main())
