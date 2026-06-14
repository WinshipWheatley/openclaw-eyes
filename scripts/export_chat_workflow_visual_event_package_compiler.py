#!/usr/bin/env python3
"""CLI wrapper for Chat Workflow Visual Event Package Compiler."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat_workflow_visual_event_package_compiler import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
