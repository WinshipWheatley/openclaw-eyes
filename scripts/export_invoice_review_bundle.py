#!/usr/bin/env python3
"""Export Invoice Review Bundle v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import invoice_review_bundle


def main(argv: list[str] | None = None) -> int:
    return invoice_review_bundle.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
