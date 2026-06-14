#!/usr/bin/env python3
"""Export Gate 1 Privacy Request Readiness v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gate1_privacy_request_readiness


if __name__ == "__main__":
    raise SystemExit(gate1_privacy_request_readiness.main())
