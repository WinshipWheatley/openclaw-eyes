#!/usr/bin/env python3
"""Run bounded Evidence Kettle v0.1 seed ingestion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from corpus_atlas import DEFAULT_ROOT
from evidence_kettle import (
    build_evidence_report,
    format_evidence_report,
    plan_evidence_ingestion,
    run_evidence_kettle,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed generated read-model and receipt evidence into the existing ledger."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--root", default=DEFAULT_ROOT.as_posix(), help="Atlas root path.")
    parser.add_argument("--atlas-run-id", help="Corpus Atlas run id. Defaults to latest.")
    parser.add_argument("--run-id", help="Optional deterministic evidence ingestion run id.")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print the bounded source plan without writing evidence rows.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def _format_plan(plan: dict) -> str:
    if plan.get("status") == "no_atlas_runs":
        return "Evidence Kettle v0.1 plan\n\nNo Corpus Atlas runs are recorded."
    lines = [
        "Evidence Kettle v0.1 plan",
        "",
        f"Atlas run: `{plan['atlas_run_id']}`",
        f"Planned sources: {plan['source_count']}",
    ]
    for count_name, counts in plan["counts"].items():
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        lines.append(f"{count_name}: {rendered or 'none'}")
    lines.extend(["", "Sample sources:"])
    if not plan["sample_sources"]:
        lines.append("- none")
    for source in plan["sample_sources"]:
        lines.append(
            "- "
            + source["relative_path"].replace("\n", "\\n")
            + f" ({source['ingestion_eligibility']}, {source['source_role']}, "
            + f"{source['sensitivity_label']}, {source['raw_content_eligibility']})"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.plan_only:
        plan = plan_evidence_ingestion(db_path=args.db, atlas_run_id=args.atlas_run_id)
        if args.format == "json":
            print(stable_json(plan), end="")
        else:
            print(_format_plan(plan))
        return 0

    result = run_evidence_kettle(
        db_path=args.db,
        root=args.root,
        atlas_run_id=args.atlas_run_id,
        ingestion_run_id=args.run_id,
    )
    report = build_evidence_report(db_path=args.db, ingestion_run_id=result.ingestion_run_id)
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_evidence_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
