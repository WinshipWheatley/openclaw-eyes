#!/usr/bin/env python3
"""Export Request-Response Bridge Readiness v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import request_response_bridge_readiness


if __name__ == "__main__":
    raise SystemExit(request_response_bridge_readiness.main())
