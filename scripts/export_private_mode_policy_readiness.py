#!/usr/bin/env python3
"""Export Private Mode Policy Readiness v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import private_mode_policy_readiness


if __name__ == "__main__":
    raise SystemExit(private_mode_policy_readiness.main())
