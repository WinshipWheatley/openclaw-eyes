#!/usr/bin/env python3
"""Export the Mac-safe chat readback card mirror."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat_readback_card_mirror import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
