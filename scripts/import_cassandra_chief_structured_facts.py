#!/usr/bin/env python3
"""CLI wrapper for approved Cassandra/Chief structured fact import."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassandra_chief_structured_fact_import import main


if __name__ == "__main__":
    raise SystemExit(main())
