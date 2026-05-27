#!/usr/bin/env python3
"""Export the proposal-only intent contract read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm_intent_proposal_contract


def main(argv: list[str] | None = None) -> int:
    return lm_intent_proposal_contract.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
