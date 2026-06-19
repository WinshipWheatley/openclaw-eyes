"""Receipt-only gap map between Mac Markdown inventory and corpus ingest.

The map compares generated root-inventory receipts with corpus-ingest receipts
so the operator can see which Markdown roots have already been fed into the
MD-KB body corpus. It reads receipt JSON only, not Markdown bodies.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from md_corpus_ingest import NO_AUTHORITY_FLAGS as CORPUS_NO_AUTHORITY_FLAGS, stable_json


MD_INGEST_GAP_MAP_VERSION = "md_ingest_gap_map_v0"

NO_AUTHORITY_FLAGS = {
    **CORPUS_NO_AUTHORITY_FLAGS,
    "markdown_body_read_allowed": False,
    "source_markdown_writeback_allowed": False,
    "truth_claimed": False,
    "advisory_only": True,
}


@dataclass(frozen=True)
class MarkdownIngestGapMapResult:
    map_id: str
    root_inventory_receipt: str
    corpus_receipts: list[str]
    root_count: int
    mapped_root_count: int
    partial_root_count: int
    unmapped_root_count: int
    total_allowed_markdown_count: int
    total_ingested_document_count: int
    remaining_markdown_count_lower_bound: int
    roots: list[dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize(path: str) -> str:
    return Path(path).expanduser().as_posix().rstrip("/")


def _is_same_or_child(child: str, parent: str) -> bool:
    child_path = _normalize(child)
    parent_path = _normalize(parent)
    return child_path == parent_path or child_path.startswith(parent_path + "/")


def _coverage_status(root_path: str, allowed_count: int, matching_receipts: list[dict[str, Any]]) -> tuple[str, int, int]:
    ingested_count = sum(int(receipt.get("ingested_document_count") or 0) for receipt in matching_receipts)
    exact_receipts = [receipt for receipt in matching_receipts if _normalize(str(receipt.get("root_path"))) == _normalize(root_path)]
    if exact_receipts and ingested_count >= allowed_count:
        return "mapped_exact", ingested_count, 0
    if exact_receipts:
        return "mapped_count_mismatch", ingested_count, max(allowed_count - ingested_count, 0)
    if matching_receipts:
        return "partially_mapped_subroot", ingested_count, max(allowed_count - ingested_count, 0)
    return "unmapped", 0, allowed_count


def build_ingest_gap_map(
    *,
    root_inventory_receipt: str | Path,
    corpus_receipts: list[str | Path],
    map_id: str | None = None,
) -> MarkdownIngestGapMapResult:
    inventory_path = Path(root_inventory_receipt)
    active_map_id = map_id or f"md_ingest_gap_map_{utc_now().replace(':', '').replace('+', 'Z')}"
    inventory = _load_json(inventory_path)
    corpus_paths = [Path(path) for path in corpus_receipts]
    corpus = [_load_json(path) for path in corpus_paths]
    roots: list[dict[str, Any]] = []
    for root in inventory.get("roots", []):
        root_path = str(root["root_path"])
        allowed_count = int(root.get("allowed_markdown_count") or 0)
        matching = [
            receipt
            for receipt in corpus
            if receipt.get("root_path") and _is_same_or_child(str(receipt["root_path"]), root_path)
        ]
        status, ingested_count, remaining_count = _coverage_status(root_path, allowed_count, matching)
        roots.append(
            {
                "root_path": root_path,
                "coverage_status": status,
                "allowed_markdown_count": allowed_count,
                "ingested_document_count": ingested_count,
                "remaining_markdown_count_lower_bound": remaining_count,
                "matching_corpus_roots": [receipt["root_path"] for receipt in matching],
                "body_read": False,
                "truth_claimed": False,
            }
        )
    mapped = sum(1 for root in roots if root["coverage_status"] in {"mapped_exact", "mapped_count_mismatch"})
    partial = sum(1 for root in roots if root["coverage_status"] == "partially_mapped_subroot")
    unmapped = sum(1 for root in roots if root["coverage_status"] == "unmapped")
    total_allowed = sum(int(root["allowed_markdown_count"]) for root in roots)
    total_ingested = sum(int(receipt.get("ingested_document_count") or 0) for receipt in corpus)
    remaining = sum(int(root["remaining_markdown_count_lower_bound"]) for root in roots)
    roots.sort(key=lambda item: (-int(item["remaining_markdown_count_lower_bound"]), item["root_path"]))
    return MarkdownIngestGapMapResult(
        map_id=active_map_id,
        root_inventory_receipt=inventory_path.as_posix(),
        corpus_receipts=[path.as_posix() for path in corpus_paths],
        root_count=len(roots),
        mapped_root_count=mapped,
        partial_root_count=partial,
        unmapped_root_count=unmapped,
        total_allowed_markdown_count=total_allowed,
        total_ingested_document_count=total_ingested,
        remaining_markdown_count_lower_bound=remaining,
        roots=roots,
    )


def result_as_dict(result: MarkdownIngestGapMapResult) -> dict[str, Any]:
    return {
        **result.__dict__,
        "gap_map_version": MD_INGEST_GAP_MAP_VERSION,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }


def format_operator_result(result: MarkdownIngestGapMapResult) -> str:
    lines = [
        "Markdown Ingest Gap Map",
        "",
        "Evidence:",
        f"- Map ID: `{result.map_id}`.",
        f"- Root inventory receipt: `{result.root_inventory_receipt}`.",
        f"- Corpus receipts: `{len(result.corpus_receipts)}`.",
        f"- Roots: `{result.root_count}`.",
        f"- Mapped roots: `{result.mapped_root_count}`.",
        f"- Partially mapped roots: `{result.partial_root_count}`.",
        f"- Unmapped roots: `{result.unmapped_root_count}`.",
        f"- Allowed Markdown files: `{result.total_allowed_markdown_count}`.",
        f"- Corpus-ingested documents: `{result.total_ingested_document_count}`.",
        f"- Remaining lower-bound count: `{result.remaining_markdown_count_lower_bound}`.",
        "",
        "Root Coverage:",
    ]
    for item in result.roots:
        lines.append(
            f"- `{item['root_path']}`: `{item['coverage_status']}`, "
            f"allowed `{item['allowed_markdown_count']}`, "
            f"ingested `{item['ingested_document_count']}`, "
            f"remaining lower-bound `{item['remaining_markdown_count_lower_bound']}`."
        )
    lines.extend(
        [
            "",
            "Authority:",
            "- Reads generated receipts only: `true`.",
            "- Markdown body reads: `false`.",
            "- Source Markdown writeback: `false`.",
            "- Truth claimed: `false`.",
            "- Advisory only: `true`.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Mac Markdown inventory roots with corpus-ingest receipts.")
    parser.add_argument("--root-inventory-receipt", required=True, help="Path to mac_md_root_inventory receipt JSON.")
    parser.add_argument("--corpus-receipt", action="append", required=True, help="Path to a corpus ingest receipt JSON.")
    parser.add_argument("--map-id", help="Stable map id for deterministic receipts.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_ingest_gap_map(
        root_inventory_receipt=args.root_inventory_receipt,
        corpus_receipts=args.corpus_receipt,
        map_id=args.map_id,
    )
    if args.format == "json":
        print(stable_json(result_as_dict(result)), end="")
    else:
        print(format_operator_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
