#!/usr/bin/env python3
"""Export the chat workflow run state visual feed read-model."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat_workflow_run_state_visual_feed import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
