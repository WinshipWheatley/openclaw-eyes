#!/usr/bin/env python3
"""Export the Live Arts PDF operator-assistance annotation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selected_invoice_pdf_export_operator_assistance_annotation import main


if __name__ == "__main__":
    raise SystemExit(main())
