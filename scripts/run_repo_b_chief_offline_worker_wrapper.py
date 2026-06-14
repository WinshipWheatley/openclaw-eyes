#!/usr/bin/env python3
"""CLI wrapper for fixture-running Repo B Chief offline worker wrapper."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from repo_b_chief_offline_worker_wrapper import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
