#!/usr/bin/env python3
"""Export the approved local artifact reference read-model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_artifact_reference


def main(argv: list[str] | None = None) -> int:
    return local_artifact_reference.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
