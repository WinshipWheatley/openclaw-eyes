#!/usr/bin/env python3
"""Export the operator attention delivery contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_attention_delivery_contract


def main(argv: list[str] | None = None) -> int:
    return operator_attention_delivery_contract.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
