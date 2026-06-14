#!/usr/bin/env python3
"""Export the Intent Ingest Gate read-model."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import intent_ingest_gate


if __name__ == "__main__":
    raise SystemExit(intent_ingest_gate.main())
