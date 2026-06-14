#!/usr/bin/env python3
"""CLI wrapper for Gated Email Draft Adapter."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gated_email_draft_adapter import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
