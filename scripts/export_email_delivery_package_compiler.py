#!/usr/bin/env python3
"""CLI wrapper for Email Delivery Package Compiler export."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from email_delivery_package_compiler import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
