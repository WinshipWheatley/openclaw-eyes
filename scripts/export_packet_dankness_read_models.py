#!/usr/bin/env python3
"""Export packet dankness visibility read-models.

This creates or normalizes the score log and escalation read-models without
running enrichment work. It is safe for the read-model auto-refresh registry:
repo-local writes only, no network, no external actions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packet_dankness_enricher import ensure_packet_dankness_read_models


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export packet dankness read-models.")
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = ensure_packet_dankness_read_models(generated_at=args.generated_at)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "packet dankness read-models exported: "
            f"{result['score_log_path']} ({result['score_record_count']} records), "
            f"{result['escalations_path']} ({result['escalation_count']} escalations)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
