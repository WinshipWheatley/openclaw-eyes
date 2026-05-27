#!/usr/bin/env python3
"""Run/export the local-only live LM shadow trial."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import live_lm_shadow_trial


if __name__ == "__main__":
    raise SystemExit(live_lm_shadow_trial.main())
