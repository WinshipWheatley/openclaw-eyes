#!/usr/bin/env python3
"""Query/report Corpus Atlas v0.6 rows from the existing ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_atlas import (
    DEFAULT_DB_PATH,
    build_atlas_report,
    format_atlas_report,
    query_report_section,
    stable_json,
)
from mac_mirror_atlas import (
    format_mac_mirror_report,
    query_mac_mirror_report_section,
)


REPORT_SECTIONS = (
    "summary",
    "top-level",
    "no-go",
    "generated-read-models",
    "stale",
    "world-bound",
    "reorg",
    "ingestion",
    "retrieval",
    "unknown-review",
    "canonical-current",
    "overbroad-current",
    "roots",
    "multi-root",
    "mirrors",
    "mac-roots",
    "mirror-mismatches",
    "generated-read-model-mirror",
    "legacy-root",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Corpus Atlas v0.6 reports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional atlas run id. Defaults to latest run.")
    parser.add_argument(
        "--report",
        choices=REPORT_SECTIONS,
        default="summary",
        help="Report section to emit.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def _format_section(payload: dict) -> str:
    if payload.get("status") == "no_runs":
        return "Corpus Atlas v0.6\n\nNo atlas runs are recorded."
    if "items" not in payload:
        report = build_atlas_report(run_id=payload["run"]["run_id"])
        return format_atlas_report(report)
    lines = [
        f"Corpus Atlas v0.6 - {payload['section']}",
        "",
        f"Run: `{payload['run_id']}`",
    ]
    if payload.get("counts"):
        rendered = ", ".join(
            f"{key}={value}" for key, value in sorted(payload["counts"].items())
        )
        lines.extend(["", f"Counts: {rendered}"])
    lines.extend(
        [
            "",
            "Items:",
        ]
    )
    if not payload["items"]:
        lines.append("- none")
        return "\n".join(lines)
    for item in payload["items"]:
        if "root_id" in item:
            lines.append(
                "- "
                + item["root_id"]
                + f" ({item.get('root_kind')}, {item.get('owner_scope')}, "
                + f"{item.get('canonical_status')}, {item.get('import_status')})"
            )
            continue
        if "mirror_root_id" in item:
            lines.append(
                "- "
                + item["relative_path"].replace("\n", "\\n")
                + f" -> {item['mirror_root_id']} ({item['mirror_kind']}, {item['status']})"
            )
            continue
        lines.append(
            "- "
            + item["relative_path"].replace("\n", "\\n")
            + f" ({item['source_role']}, {item['freshness_label']}, "
            + f"{item['canonicality']}, {item['retrieval_eligibility']}, "
            + f"{item['ingestion_eligibility']}, {item['world_binding']}, "
            + f"{item['reorg_bucket']})"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.report == "roots":
        args.report = "multi-root"
    if args.report in {
        "mac-roots",
        "mirror-mismatches",
        "generated-read-model-mirror",
    }:
        payload = query_mac_mirror_report_section(db_path=args.db, section=args.report)
        if args.format == "json":
            print(stable_json(payload), end="")
        else:
            print(format_mac_mirror_report(payload))
        return 0
    if args.report == "mirrors":
        payload = query_mac_mirror_report_section(db_path=args.db, section=args.report)
        if payload.get("items"):
            if args.format == "json":
                print(stable_json(payload), end="")
            else:
                print(format_mac_mirror_report(payload))
            return 0

    if args.report == "summary" and args.format == "operator":
        report = build_atlas_report(db_path=args.db, run_id=args.run_id)
        print(format_atlas_report(report))
        return 0

    payload = query_report_section(db_path=args.db, run_id=args.run_id, section=args.report)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(_format_section(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
