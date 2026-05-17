#!/usr/bin/env python3
"""CLI wrapper for active machinery high-risk quarantine warnings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from active_machinery_high_risk_quarantine import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
