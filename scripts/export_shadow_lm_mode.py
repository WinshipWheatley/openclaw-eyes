#!/usr/bin/env python3
"""Export Shadow LM Mode v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shadow_lm_mode


if __name__ == "__main__":
    raise SystemExit(shadow_lm_mode.main())
