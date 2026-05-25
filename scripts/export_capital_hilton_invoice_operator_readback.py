#!/usr/bin/env python3
"""CLI wrapper for Capital Hilton invoice operator readback."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capital_hilton_invoice_operator_readback import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
