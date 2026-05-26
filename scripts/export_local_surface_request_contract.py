#!/usr/bin/env python3
"""Export the local surface request contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_surface_request_contract


def main(argv: list[str] | None = None) -> int:
    return local_surface_request_contract.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
