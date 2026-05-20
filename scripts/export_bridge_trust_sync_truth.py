#!/usr/bin/env python3
"""Export the Bridge Trust / Sync Truth read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge_trust_sync_truth import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
