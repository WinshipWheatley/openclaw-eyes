#!/usr/bin/env python3
"""Export the Guardian output gate read-model."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import guardian_output_gate


if __name__ == "__main__":
    raise SystemExit(guardian_output_gate.main())
