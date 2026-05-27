#!/usr/bin/env python3
"""Export Provider Policy Registry v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import provider_policy_registry


if __name__ == "__main__":
    raise SystemExit(provider_policy_registry.main())
