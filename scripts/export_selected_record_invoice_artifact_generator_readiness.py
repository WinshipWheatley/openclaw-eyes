#!/usr/bin/env python3
"""Export selected-record invoice artifact generator readiness."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selected_record_invoice_artifact_generator_readiness import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
