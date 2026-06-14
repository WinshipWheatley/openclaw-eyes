#!/usr/bin/env python3
"""Export operator-ready translated readback cards."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_card_translation_toolkit import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
