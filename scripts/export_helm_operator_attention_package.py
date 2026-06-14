#!/usr/bin/env python3
"""Export Helm operator attention package read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helm_operator_attention_package import main


if __name__ == "__main__":
    raise SystemExit(main())
