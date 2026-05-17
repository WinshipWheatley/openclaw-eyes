#!/usr/bin/env python3
"""Export Capital Hilton review packet approval receipt read-models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capital_hilton_review_packet_approval import (
    DEFAULT_PACKET_PATH,
    build_capital_hilton_review_packet_approval,
    export_capital_hilton_review_packet_approval,
    format_capital_hilton_review_packet_approval,
)
from cassandra_clara_fact_packet import stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the Capital Hilton review packet approval receipt."
    )
    parser.add_argument(
        "--packet-json",
        default=str(DEFAULT_PACKET_PATH),
        help="Generated Cassandra/Clara packet JSON.",
    )
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Generated read-model export root.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_capital_hilton_review_packet_approval(
        packet_path=args.packet_json,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(summary.__dict__), end="")
    else:
        payload = build_capital_hilton_review_packet_approval(packet_path=args.packet_json)
        print(format_capital_hilton_review_packet_approval(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
