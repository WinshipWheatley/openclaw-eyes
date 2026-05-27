#!/usr/bin/env python3
"""Export LM1 Thread Context Package v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm1_thread_context_package


if __name__ == "__main__":
    raise SystemExit(lm1_thread_context_package.main())
