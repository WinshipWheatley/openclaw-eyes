#!/usr/bin/env python3
"""CLI wrapper for Repo B Telegram intake bridge export."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from repo_b_telegram_intake_bridge import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
