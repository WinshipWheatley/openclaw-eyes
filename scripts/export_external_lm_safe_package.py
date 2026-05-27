#!/usr/bin/env python3
"""Export External LM Safe Package Compiler v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_safe_package_compiler


if __name__ == "__main__":
    raise SystemExit(external_lm_safe_package_compiler.main())
