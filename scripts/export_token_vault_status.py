#!/usr/bin/env python3
"""Export Token Vault Status v0."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import token_vault


if __name__ == "__main__":
    raise SystemExit(token_vault.main())
