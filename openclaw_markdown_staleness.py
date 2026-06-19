"""Advisory OpenClaw Markdown staleness candidates.

This layer sits on top of the bounded Markdown body ingest/query read model.
It classifies allowlisted Markdown documents into review candidates using only
repo-relative paths, titles, headings, and bounded term signals. It does not
export full bodies, promote truth, mutate files, or authorize cleanup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openclaw_markdown_body_ingest_query import (
    DEFAULT_EXPORT_ROOT,
    DEFAULT_MARKDOWN_ROOTS,
    MAX_BODY_BYTES_DEFAULT,
    MAX_DOCS_DEFAULT,
    build_openclaw_markdown_body_ingest_query,
    stable_json,
    utc_now,
)


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "openclaw_markdown_staleness_v0"
READ_MODEL_ID = "openclaw_markdown_staleness"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

SOURCE_READ_MODEL_ID = "openclaw_markdown_body_ingest_query"

CANONICAL_ROOT_DOCS = {
    "AGENTS.md",
    "CORE_ARCHITECTURE_PRINCIPLES.md",
    "OPENCLAW_RUNTIME.md",
    "USER.md",
}

STALE_HINTS = {
    "archive",
    "archived",
    "deprecated",
    "legacy",
    "obsolete",
    "old",
    "previous",
    "replaced",
    "residue",
    "retired",
    "stale",
    "superseded",
    "supersedes",
}

HISTORICAL_PACKET_HINTS = {
    "brief",
    "checkin",
    "claim",
    "done",
    "handoff",
    "landed",
    "packet",
    "pause",
    "receipt",
    "report",
    "status",
}

ACTIVE_WORK_HINTS = {
    "active",
    "backlog",
    "current",
    "gate",
    "open",
    "queue",
    "runtime",
    "todo",
    "work",
}

AUTHORITY_BOUNDARY = {
    "action_authority_granted": False,
    "truth_promotion_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "file_archive_allowed": False,
    "file_rewrite_allowed": False,
    "stable_map_update_allowed": False,
    "runtime_dispatch_allowed": False,
    "external_send_allowed": False,
    "network_operation_allowed": False,
    "model_api_execution_allowed": False,
    "broad_private_root_scan_allowed": False,
    "legal_discovery_access_allowed": False,
    "credential_store_access_allowed": False,
}


@dataclass(frozen=True)
class MarkdownStalenessExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    document_count: int
    review_queue_count: int
    stale_candidate_count: int
    action_authority_granted: bool


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9_-]{1,}", text.lower()))


def _signal_text(card: dict[str, Any]) -> str:
    return " ".join(
        [
            str(card.get("relative_path", "")),
            str(card.get("title", "")),
            " ".join(str(value) for value in card.get("headings_preview", [])),
            " ".join(str(value) for value in card.get("top_terms", [])),
        ]
    )


def _matched(tokens: set[str], hints: set[str]) -> list[str]:
    return sorted(tokens.intersection(hints))


def _candidate_row(card: dict[str, Any]) -> dict[str, Any]:
    relative_path = str(card["relative_path"])
    source_kind = str(card.get("source_kind", "ALLOWLISTED_MARKDOWN"))
    tokens = _tokens(_signal_text(card))
    stale_signals = _matched(tokens, STALE_HINTS)
    historical_signals = _matched(tokens, HISTORICAL_PACKET_HINTS)
    active_signals = _matched(tokens, ACTIVE_WORK_HINTS)

    if relative_path in CANONICAL_ROOT_DOCS:
        status = "current_canonical_root"
        priority = 10
        reasons = ["canonical_root_document"]
        interpretation = "Current canonical root document candidate by repo contract; still do not rewrite automatically."
        next_safe_move = "Use as root governance context, then verify any task-specific claim against receipts."
    elif stale_signals:
        status = "stale_or_superseded_candidate"
        priority = 90
        reasons = [f"stale_hint:{signal}" for signal in stale_signals]
        interpretation = "Likely stale, historical, superseded, or cleanup-review material based on labels/path/title/terms."
        next_safe_move = "Review before using as current truth; do not archive or delete from this read model."
    elif source_kind == "GENERATED_OPERATOR_MARKDOWN":
        status = "generated_read_model_candidate"
        priority = 40
        reasons = ["generated_read_model_markdown"]
        interpretation = "Generated read-model/operator document; freshness is tied to its producing branch, receipt, and gate."
        next_safe_move = "Check the generating branch/commit/gate before treating the generated view as current."
    elif historical_signals:
        status = "historical_or_packet_candidate"
        priority = 70
        reasons = [f"historical_packet_hint:{signal}" for signal in historical_signals]
        interpretation = "Likely a packet, status, receipt, or handoff artifact rather than standing doctrine."
        next_safe_move = "Use as evidence of a past event only unless promoted by a newer canonical receipt."
    elif active_signals:
        status = "active_work_candidate"
        priority = 55
        reasons = [f"active_work_hint:{signal}" for signal in active_signals]
        interpretation = "Potential active-work or current-context document requiring route-specific freshness review."
        next_safe_move = "Check current branch, inbox, and gate receipts before actioning any work described here."
    else:
        status = "review_needed"
        priority = 60
        reasons = ["no_strong_current_or_stale_signal"]
        interpretation = "Allowlisted Markdown with no deterministic current/stale signal in bounded metadata."
        next_safe_move = "Classify with human or relationship-index review before promoting into current operator context."

    return {
        "doc_id": card["doc_id"],
        "relative_path": relative_path,
        "title": card["title"],
        "source_kind": source_kind,
        "staleness_status": status,
        "review_priority": priority,
        "evidence_signals": reasons,
        "matched_stale_terms": stale_signals,
        "matched_historical_terms": historical_signals,
        "matched_active_terms": active_signals,
        "signal_basis": "repo_relative_path_title_headings_top_terms_only",
        "body_storage_policy": card.get("body_storage_policy", "hash_terms_and_bounded_snippets_only_no_full_body_export"),
        "safe_operator_interpretation": interpretation,
        "next_safe_move": next_safe_move,
        "truth_status": "ADVISORY_STALENESS_CANDIDATE_NOT_CANONICAL_TRUTH",
        "action_authority_granted": False,
        "truth_promotion_allowed": False,
        "file_move_allowed": False,
        "file_delete_allowed": False,
        "runtime_dispatch_allowed": False,
    }


def _review_queue(candidates: list[dict[str, Any]], limit: int = 25) -> list[dict[str, Any]]:
    reviewable = [
        candidate
        for candidate in candidates
        if candidate["staleness_status"] != "current_canonical_root"
    ]
    reviewable.sort(key=lambda row: (-int(row["review_priority"]), row["relative_path"]))
    return reviewable[:limit]


def build_openclaw_markdown_staleness(
    *,
    repo_root: str | Path = ROOT,
    markdown_roots: tuple[str, ...] = DEFAULT_MARKDOWN_ROOTS,
    generated_at: str | None = None,
    max_docs: int = MAX_DOCS_DEFAULT,
    max_body_bytes: int = MAX_BODY_BYTES_DEFAULT,
) -> dict[str, Any]:
    source = build_openclaw_markdown_body_ingest_query(
        repo_root=repo_root,
        markdown_roots=markdown_roots,
        query_text="what work on staleness current canonical superseded",
        generated_at=generated_at,
        max_docs=max_docs,
        max_body_bytes=max_body_bytes,
    )
    candidates = [_candidate_row(card) for card in source["document_cards"]]
    candidates.sort(key=lambda row: (row["relative_path"], row["doc_id"]))
    status_counts = dict(sorted(Counter(candidate["staleness_status"] for candidate in candidates).items()))
    review_queue = _review_queue(candidates)
    stale_candidate_count = status_counts.get("stale_or_superseded_candidate", 0)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "advisory_markdown_staleness_candidates",
        "source_read_model": {
            "read_model_id": SOURCE_READ_MODEL_ID,
            "schema_version": source["schema_version"],
            "content_hash": source["machine_proof"]["content_hash"],
            "document_count": source["document_summary"]["document_count"],
            "full_body_exported": source["machine_proof"]["full_body_exported"],
            "body_read_performed": source["machine_proof"]["body_read_performed"],
        },
        "classification_policy": {
            "policy_basis": "deterministic_path_title_heading_term_signals",
            "canonical_root_docs": sorted(CANONICAL_ROOT_DOCS),
            "stale_hints": sorted(STALE_HINTS),
            "historical_packet_hints": sorted(HISTORICAL_PACKET_HINTS),
            "active_work_hints": sorted(ACTIVE_WORK_HINTS),
            "classification_is_advisory": True,
            "no_file_cleanup_authority": True,
            "no_truth_promotion": True,
        },
        "summary": {
            "document_count": len(candidates),
            "status_counts": status_counts,
            "review_queue_count": len(review_queue),
            "stale_candidate_count": stale_candidate_count,
            "current_canonical_root_count": status_counts.get("current_canonical_root", 0),
            "full_body_exported": False,
            "action_authority_granted": False,
            "file_mutation_allowed": False,
        },
        "candidates": candidates,
        "review_queue": review_queue,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_action_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "source_is_bounded_markdown_body_ingest_query": source["read_model_id"] == SOURCE_READ_MODEL_ID,
            "source_full_body_exported": source["machine_proof"]["full_body_exported"],
            "full_body_exported": False,
            "uses_repo_allowlisted_source_docs_only": source["machine_proof"]["body_reads_are_repo_allowlisted"],
            "legal_discovery_excluded": source["machine_proof"]["legal_discovery_excluded"],
            "broad_private_root_scan_allowed": False,
            "classification_is_advisory": True,
            "truth_promotion_allowed": False,
            "file_move_allowed": False,
            "file_delete_allowed": False,
            "runtime_dispatch_allowed": False,
            "action_authority_granted": False,
            "network_operation_performed": False,
            "model_api_execution_performed": False,
            "candidate_count_matches_source_documents": len(candidates) == source["document_summary"]["document_count"],
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_openclaw_markdown_staleness(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# OpenClaw Markdown Staleness Candidates v0",
        "",
        "Evidence:",
        f"- Classified `{summary['document_count']}` allowlisted Markdown documents from the bounded body-ingest read model.",
        f"- Review queue contains `{summary['review_queue_count']}` candidates; stale/superseded candidates: `{summary['stale_candidate_count']}`.",
        "- Classification is advisory and signal-based; it is not cleanup authority or canonical truth promotion.",
        "",
        "Status counts:",
    ]
    for status, count in summary["status_counts"].items():
        lines.append(f"- `{status}`: `{count}`")

    lines.extend(["", "Top review queue:"])
    for candidate in payload["review_queue"][:10]:
        signals = ", ".join(candidate["evidence_signals"][:3])
        lines.append(
            f"- `{candidate['relative_path']}` -> `{candidate['staleness_status']}` "
            f"(priority `{candidate['review_priority']}`, {signals})"
        )

    lines.extend(
        [
            "",
            "Boundary:",
            "- No file moves, archive decisions, rewrites, truth promotion, runtime dispatch, model calls, network calls, or external sends.",
            "- Legal Discovery, credentials, finance/private folders, broad private roots, and hidden key stores remain excluded by the source ingest policy.",
            "",
            "Next safe move:",
            "- Feed the review queue to a human or relationship-index review before using any candidate as current operator context.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_markdown_staleness(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    max_docs: int = MAX_DOCS_DEFAULT,
    max_body_bytes: int = MAX_BODY_BYTES_DEFAULT,
) -> MarkdownStalenessExportResult:
    payload = build_openclaw_markdown_staleness(
        repo_root=repo_root,
        generated_at=generated_at,
        max_docs=max_docs,
        max_body_bytes=max_body_bytes,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_openclaw_markdown_staleness(payload), encoding="utf-8")
    return MarkdownStalenessExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        document_count=payload["summary"]["document_count"],
        review_queue_count=payload["summary"]["review_queue_count"],
        stale_candidate_count=payload["summary"]["stale_candidate_count"],
        action_authority_granted=payload["summary"]["action_authority_granted"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export advisory Markdown staleness candidates.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--max-docs", type=int, default=MAX_DOCS_DEFAULT)
    parser.add_argument("--max-body-bytes", type=int, default=MAX_BODY_BYTES_DEFAULT)
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_markdown_staleness(
        repo_root=args.repo_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
        max_docs=args.max_docs,
        max_body_bytes=args.max_body_bytes,
    )
    summary = asdict(result)
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Markdown Staleness: `{READ_MODEL_ID}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- Review queue: `{result.review_queue_count}`")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "build_openclaw_markdown_staleness",
    "export_openclaw_markdown_staleness",
    "format_openclaw_markdown_staleness",
]
