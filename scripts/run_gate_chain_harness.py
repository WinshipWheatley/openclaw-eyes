#!/usr/bin/env python3
"""Run the deterministic Gate Chain Harness."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gate_chain_harness


if __name__ == "__main__":
    raise SystemExit(gate_chain_harness.main())
