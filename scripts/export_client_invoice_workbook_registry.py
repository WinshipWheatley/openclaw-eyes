#!/usr/bin/env python3
"""Export the metadata-only client invoice workbook registry."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import client_invoice_workbook_registry


def main(argv: list[str] | None = None) -> int:
    return client_invoice_workbook_registry.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
