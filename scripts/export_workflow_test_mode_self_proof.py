#!/usr/bin/env python3
"""Export the Workflow Test Mode self-proof read model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow_test_mode_self_proof import main


if __name__ == "__main__":
    raise SystemExit(main())
