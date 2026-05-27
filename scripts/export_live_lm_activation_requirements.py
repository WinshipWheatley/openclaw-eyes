#!/usr/bin/env python3
"""Export Live LM Activation Requirements v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import live_lm_activation_requirements


if __name__ == "__main__":
    raise SystemExit(live_lm_activation_requirements.main())
