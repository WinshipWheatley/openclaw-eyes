#!/usr/bin/env python3
"""Export or summarize the Google broker read-only wrapper readback."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import google_broker_readonly_wrapper as wrapper


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Export Google broker read-only readback.")
    parser.add_argument("--export-root", default=str(wrapper.DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    readback_path = export_root / wrapper.JSON_EXPORT_NAME
    if readback_path.exists():
        payload = json.loads(readback_path.read_text(encoding="utf-8"))
    else:
        payload = wrapper.build_from_fixture("contacts", generated_at=args.generated_at)
        wrapper.write_exports(payload, export_root)
    paths = (export_root / wrapper.JSON_EXPORT_NAME, export_root / wrapper.OPERATOR_EXPORT_NAME)
    output = payload if args.format == "json" else wrapper.build_summary(payload, paths)
    print(wrapper.stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
