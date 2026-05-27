#!/usr/bin/env python3
"""Export External Shadow Provider Config v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_shadow_provider_config


if __name__ == "__main__":
    raise SystemExit(external_shadow_provider_config.main())
