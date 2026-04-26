"""Command-line wrapper for OpenClaw Legal v0 workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from legal.alternative_methods import alternative_methods_for_matter
from legal.deployment_profile import (
    default_legal_local_profile,
    save_deployment_profile,
)
from legal.local_ingestion import (
    ExtractionError,
    extract_all_supported_sources,
    extract_source_text,
)
from legal.local_search import search_extracted_text
from legal.matter_workspace import create_matter_workspace, register_source
from legal.review_packet import export_review_packet
from legal.search_report import export_search_report
from legal.support_packet import export_support_packet


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except (
        ExtractionError,
        FileExistsError,
        FileNotFoundError,
        KeyError,
        ValueError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m legal.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)

    create = subcommands.add_parser("create-matter")
    create.add_argument("--root", required=True)
    create.add_argument("--vault-root")
    create.add_argument("--matter-id", required=True)
    create.add_argument("--display-name", required=True)
    create.set_defaults(handler=_create_matter)

    add_source = subcommands.add_parser("add-source")
    add_source.add_argument("--root", required=True)
    add_source.add_argument("--vault-root")
    add_source.add_argument("--source", required=True)
    add_source.set_defaults(handler=_add_source)

    extract = subcommands.add_parser("extract")
    extract.add_argument("--root", required=True)
    extract.add_argument("--vault-root")
    extract.add_argument("--source-id", required=True)
    extract.set_defaults(handler=_extract)

    extract_all = subcommands.add_parser("extract-all")
    extract_all.add_argument("--root", required=True)
    extract_all.add_argument("--vault-root")
    extract_all.set_defaults(handler=_extract_all)

    search = subcommands.add_parser("search")
    search.add_argument("--root", required=True)
    search.add_argument("--vault-root")
    search.add_argument("--query", required=True)
    search.add_argument("--max-results", type=int, default=20)
    search.add_argument("--snippet-chars", type=int, default=80)
    search.set_defaults(handler=_search)

    report = subcommands.add_parser("report")
    report.add_argument("--root", required=True)
    report.add_argument("--vault-root")
    report.add_argument("--query", required=True)
    report.add_argument("--report-name")
    report.add_argument("--max-results", type=int, default=20)
    report.add_argument("--snippet-chars", type=int, default=80)
    report.set_defaults(handler=_report)

    review_packet = subcommands.add_parser("review-packet")
    review_packet.add_argument("--root", required=True)
    review_packet.add_argument("--vault-root")
    review_packet.add_argument("--packet-name")
    review_packet.add_argument(
        "--no-reports",
        action="store_true",
        help="Exclude Markdown reports from the review packet.",
    )
    review_packet.set_defaults(handler=_review_packet)

    support_packet = subcommands.add_parser("support-packet")
    support_packet.add_argument("--root", required=True)
    support_packet.add_argument("--vault-root")
    support_packet.add_argument("--packet-name")
    support_packet.set_defaults(handler=_support_packet)

    alternative_methods = subcommands.add_parser("alternative-methods")
    alternative_methods.add_argument("--root", required=True)
    alternative_methods.add_argument("--vault-root")
    alternative_methods.set_defaults(handler=_alternative_methods)

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
        allowed_vault_roots=_allowed_vault_roots(args),
    )
    return {
        "matter_id": workspace.matter_id,
        "display_name": workspace.display_name,
        "created_at": workspace.created_at,
        "root_path": workspace.root_path,
    }


def _add_source(args: argparse.Namespace) -> dict[str, Any]:
    return register_source(
        args.root,
        args.source,
        allowed_vault_roots=_allowed_vault_roots(args),
    )


def _extract(args: argparse.Namespace) -> dict[str, Any]:
    return extract_source_text(
        args.root,
        args.source_id,
        allowed_vault_roots=_allowed_vault_roots(args),
    )


def _extract_all(args: argparse.Namespace) -> dict[str, Any]:
    results = extract_all_supported_sources(
        args.root,
        allowed_vault_roots=_allowed_vault_roots(args),
    )
    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "root": args.root,
        "result_count": len(results),
        "status_counts": status_counts,
        "results": results,
    }


def _search(args: argparse.Namespace) -> dict[str, Any]:
    results = search_extracted_text(
        args.root,
        args.query,
        max_results=args.max_results,
        snippet_chars=args.snippet_chars,
        allowed_vault_roots=_allowed_vault_roots(args),
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
        allowed_vault_roots=_allowed_vault_roots(args),
    )


def _review_packet(args: argparse.Namespace) -> dict[str, Any]:
    return export_review_packet(
        args.root,
        packet_name=args.packet_name,
        include_reports=not args.no_reports,
        allowed_vault_roots=_allowed_vault_roots(args),
    )


def _support_packet(args: argparse.Namespace) -> dict[str, Any]:
    return export_support_packet(
        args.root,
        packet_name=args.packet_name,
        allowed_vault_roots=_allowed_vault_roots(args),
    )


def _alternative_methods(args: argparse.Namespace) -> dict[str, Any]:
    return alternative_methods_for_matter(
        args.root,
        allowed_vault_roots=_allowed_vault_roots(args),
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


def _allowed_vault_roots(args: argparse.Namespace) -> list[str] | None:
    vault_root = getattr(args, "vault_root", None)
    if vault_root is None:
        return None
    return [vault_root]


if __name__ == "__main__":
    raise SystemExit(main())
