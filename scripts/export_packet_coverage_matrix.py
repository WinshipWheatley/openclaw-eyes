#!/usr/bin/env python3
"""Export the packet coverage matrix read-model."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maestro_context_packet import build_maestro_context_packet
from packet_coverage_contract import DEFAULT_AGENTS, build_packet_coverage_matrix, stable_json


def export_packet_coverage_matrix(
    *,
    read_model_root: str | Path = "generated/read_models",
    export_root: str | Path = "generated/read_models",
    packets_by_agent: Mapping[str, Mapping[str, Any]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    root = Path(read_model_root)
    if packets_by_agent is None:
        packet = build_maestro_context_packet(
            question="orient me on my plate, invoices, gigs, contacts, agent status, advice, and drafting",
            read_model_root=root,
            require_real_truth=False,
        )
        packets_by_agent = {agent: packet for agent in DEFAULT_AGENTS}
    payload = build_packet_coverage_matrix(
        read_model_root=root,
        packets_by_agent=packets_by_agent,
        today=today,
    )
    out_root = Path(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / "packet_coverage_matrix.json"
    out_path.write_text(stable_json(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export packet coverage matrix read-model.")
    parser.add_argument("--read-model-root", default="generated/read_models")
    parser.add_argument("--export-root", default="generated/read_models")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)
    payload = export_packet_coverage_matrix(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = payload["summary"]
        print(
            "Packet coverage matrix: "
            f"{summary['covered_count']}/{summary['row_count']} covered, "
            f"{summary['sources_fresh_count']}/{summary['row_count']} source-fresh."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
