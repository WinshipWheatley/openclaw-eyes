#!/usr/bin/env python3
"""Export the Live Arts MD simple invoice review bundle."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from live_arts_md_invoice_review_bundle import main


if __name__ == "__main__":
    raise SystemExit(main())
