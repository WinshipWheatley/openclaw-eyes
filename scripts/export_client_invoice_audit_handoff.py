#!/usr/bin/env python3
"""Export the client invoice audit path/schema handoff read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import client_invoice_audit_handoff


def main(argv: list[str] | None = None) -> int:
    return client_invoice_audit_handoff.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
