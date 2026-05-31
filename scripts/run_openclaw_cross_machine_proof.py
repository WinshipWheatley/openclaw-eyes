#!/usr/bin/env python3
"""CLI wrapper for the OpenClaw Cross-Machine Proof Runner."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openclaw_cross_machine_proof_runner import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
