#!/usr/bin/env python3
"""Export the Make Winship Life Easier Batch v0 manifest."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from make_winship_life_easier_batch_manifest import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
