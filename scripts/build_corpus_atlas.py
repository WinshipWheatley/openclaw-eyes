#!/usr/bin/env python3
"""Run the bounded OpenClaw Corpus Atlas v0.5 metadata scan."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_atlas import (
    DEFAULT_DB_PATH,
    DEFAULT_HOST_KIND,
    DEFAULT_REPORT_ROOT,
    DEFAULT_ROOT,
    DEFAULT_ROOT_ID,
    build_atlas_report,
    format_atlas_report,
    run_corpus_atlas,
    stable_json,
    write_report_artifacts,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a metadata-first Corpus Atlas v0.5 in the existing ledger."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--root", default=DEFAULT_ROOT.as_posix(), help="Root to classify.")
    parser.add_argument("--root-id", default=DEFAULT_ROOT_ID, help="Atlas root id.")
    parser.add_argument("--host-kind", default=DEFAULT_HOST_KIND, help="Host kind label.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write concise generated JSON/Markdown report artifacts.",
    )
    parser.add_argument(
        "--report-root",
        default=DEFAULT_REPORT_ROOT.as_posix(),
        help="Report output root when --write-report is used.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = run_corpus_atlas(
        db_path=args.db,
        root=Path(args.root),
        root_id=args.root_id,
        host_kind=args.host_kind,
        run_id=args.run_id,
    )
    report = build_atlas_report(db_path=args.db, run_id=result.run_id)
    if args.write_report:
        report["written_reports"] = write_report_artifacts(
            report,
            report_root=args.report_root,
        )

    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_atlas_report(report))
        if args.write_report:
            written = report["written_reports"]
            print("")
            print("Reports:")
            print(f"- JSON: {written['json']}")
            print(f"- Markdown: {written['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
