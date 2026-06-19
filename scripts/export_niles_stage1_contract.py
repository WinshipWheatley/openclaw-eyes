#!/usr/bin/env python3
"""CLI wrapper for Niles Stage 1 contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from niles_stage1_contract import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
