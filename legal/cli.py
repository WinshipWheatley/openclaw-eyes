"""Command-line wrapper for OpenClaw Legal v0 workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from legal.deployment_profile import (
    default_legal_local_profile,
    save_deployment_profile,
)
from legal.local_ingestion import extract_source_text
from legal.local_search import search_extracted_text
from legal.matter_workspace import create_matter_workspace, register_source
from legal.review_packet import export_review_packet
from legal.search_report import export_search_report


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except (FileExistsError, FileNotFoundError, KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m legal.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)

    create = subcommands.add_parser("create-matter")
    create.add_argument("--root", required=True)
    create.add_argument("--matter-id", required=True)
    create.add_argument("--display-name", required=True)
    create.set_defaults(handler=_create_matter)

    add_source = subcommands.add_parser("add-source")
    add_source.add_argument("--root", required=True)
    add_source.add_argument("--source", required=True)
    add_source.set_defaults(handler=_add_source)

    extract = subcommands.add_parser("extract")
    extract.add_argument("--root", required=True)
    extract.add_argument("--source-id", required=True)
    extract.set_defaults(handler=_extract)

    search = subcommands.add_parser("search")
    search.add_argument("--root", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--max-results", type=int, default=20)
    search.add_argument("--snippet-chars", type=int, default=80)
    search.set_defaults(handler=_search)

    report = subcommands.add_parser("report")
    report.add_argument("--root", required=True)
    report.add_argument("--query", required=True)
    report.add_argument("--report-name")
    report.add_argument("--max-results", type=int, default=20)
    report.add_argument("--snippet-chars", type=int, default=80)
    report.set_defaults(handler=_report)

    review_packet = subcommands.add_parser("review-packet")
    review_packet.add_argument("--root", required=True)
    review_packet.add_argument("--packet-name")
    review_packet.add_argument(
        "--no-reports",
        action="store_true",
        help="Exclude Markdown reports from the review packet.",
    )
    review_packet.set_defaults(handler=_review_packet)

    default_profile = subcommands.add_parser("default-profile")
    default_profile.add_argument("--firm-name", required=True)
    default_profile.add_argument("--output", required=True)
    default_profile.add_argument("--profile-name", default="legal-local")
    default_profile.set_defaults(handler=_default_profile)
    return parser


def _create_matter(args: argparse.Namespace) -> dict[str, Any]:
    workspace = create_matter_workspace(
        args.root,
        matter_id=args.matter_id,
        display_name=args.display_name,
    )
    return {
        "matter_id": workspace.matter_id,
        "display_name": workspace.display_name,
        "created_at": workspace.created_at,
        "root_path": workspace.root_path,
    }


def _add_source(args: argparse.Namespace) -> dict[str, Any]:
    return register_source(args.root, args.source)


def _extract(args: argparse.Namespace) -> dict[str, Any]:
    return extract_source_text(args.root, args.source_id)


def _search(args: argparse.Namespace) -> dict[str, Any]:
    results = search_extracted_text(
        args.root,
        args.query,
        max_results=args.max_results,
        snippet_chars=args.snippet_chars,
    )
    return {
        "query": args.query,
        "result_count": len(results),
        "results": results,
    }


def _report(args: argparse.Namespace) -> dict[str, Any]:
    return export_search_report(
        args.root,
        args.query,
        report_name=args.report_name,
        max_results=args.max_results,
        snippet_chars=args.snippet_chars,
    )


def _review_packet(args: argparse.Namespace) -> dict[str, Any]:
    return export_review_packet(
        args.root,
        packet_name=args.packet_name,
        include_reports=not args.no_reports,
    )


def _default_profile(args: argparse.Namespace) -> dict[str, Any]:
    profile = default_legal_local_profile(
        args.firm_name,
        profile_name=args.profile_name,
    )
    output = Path(args.output)
    save_deployment_profile(profile, output)
    return {
        "profile_path": str(output),
        "profile_name": profile["profile_name"],
        "firm_name": profile["firm_name"],
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
