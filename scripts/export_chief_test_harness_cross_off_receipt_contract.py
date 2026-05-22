#!/usr/bin/env python3
"""Export the Chief Test Harness / Cross-Off Receipt Contract v0 read-model."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chief_test_harness_cross_off_receipt_contract import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
