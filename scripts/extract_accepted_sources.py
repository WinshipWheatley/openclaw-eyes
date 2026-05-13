#!/usr/bin/env python3
"""Safely extract bodies for accepted context promotion candidates."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.build_source_inventory import build_inventory
    from scripts.promote_accepted_context import (
        PROMOTION_MANIFEST_VERSION,
        load_json_artifact,
        stable_json,
        write_json_artifact,
    )
except ImportError:
    from build_source_inventory import build_inventory
    from promote_accepted_context import (
        PROMOTION_MANIFEST_VERSION,
        load_json_artifact,
        stable_json,
        write_json_artifact,
    )


EXTRACTION_ARTIFACT_VERSION = "safe_body_extraction_v0"
DEFAULT_MAX_BYTES = 100_000
ALLOWED_EXTENSIONS = frozenset({".md", ".py", ".txt"})
EVIDENCE_LABEL = "parsed_evidence_not_truth"
EXTRACTION_TIME_POLICY = "omitted_for_deterministic_read_model"


def _records_by_path(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["path"]: record for record in records}


def _manifest_root(promotion_manifest: dict[str, Any], root: Path | None = None) -> Path:
    if root is not None:
        return root.resolve()
    raw_root = promotion_manifest.get("source_inventory_scope", {}).get("root")
    return Path(raw_root or ".").resolve()


def _inventory_for_manifest(promotion_manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    allowlist = promotion_manifest.get("source_inventory_scope", {}).get("allowlist")
    if not allowlist:
        allowlist = [record["path"] for record in promotion_manifest.get("records", [])]
    return build_inventory(root=root, allowlist=tuple(allowlist))


def _safe_repo_path(root: Path, path: str) -> Path | None:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    full_path = (root / candidate).resolve()
    try:
        full_path.relative_to(root.resolve())
    except ValueError:
        return None
    return full_path


def _refusal(path: str, reason: str, record: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "path": path,
        "extraction_state": "refused",
        "reason_refused": reason,
        "source_class": (record or {}).get("source_class"),
        "authority_label": (record or {}).get("authority_label"),
        "body_ingested": False,
        "runtime_authority": False,
    }


def _extract_record(
    *,
    root: Path,
    promotion_record: dict[str, Any],
    inventory_record: dict[str, Any],
    max_bytes: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    path = promotion_record["path"]
    if promotion_record.get("promotion_state") != "accepted_context_candidate":
        return None, _refusal(path, "record_not_accepted_context_candidate", promotion_record)
    if promotion_record.get("eligible_for_extraction") is not True:
        return None, _refusal(path, "record_not_eligible_for_extraction", promotion_record)
    if promotion_record.get("runtime_authority") is True:
        return None, _refusal(path, "runtime_authority_record_refused", promotion_record)
    if inventory_record.get("ingestion_state") != "metadata_only":
        return None, _refusal(path, "source_inventory_record_not_metadata_only", inventory_record)
    if inventory_record.get("allowed_for_agent_context") is not True:
        return None, _refusal(path, "source_inventory_record_not_allowed_for_agent_context", inventory_record)

    extension = str(promotion_record.get("extension") or Path(path).suffix)
    if extension not in ALLOWED_EXTENSIONS:
        return None, _refusal(path, f"unsupported_extension:{extension}", promotion_record)

    declared_size = promotion_record.get("size_bytes")
    if not isinstance(declared_size, int):
        return None, _refusal(path, "missing_declared_size", promotion_record)
    if declared_size > max_bytes:
        return None, _refusal(path, f"max_size_exceeded:{declared_size}>{max_bytes}", promotion_record)

    full_path = _safe_repo_path(root, path)
    if full_path is None:
        return None, _refusal(path, "unsafe_or_outside_repo_path", promotion_record)
    if not full_path.is_file():
        return None, _refusal(path, "source_file_missing", promotion_record)

    body_bytes = full_path.read_bytes()
    if len(body_bytes) > max_bytes:
        return None, _refusal(path, f"max_size_exceeded:{len(body_bytes)}>{max_bytes}", promotion_record)
    try:
        body_text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None, _refusal(path, "source_body_not_utf8_text", promotion_record)

    return {
        "path": path,
        "source_class": promotion_record["source_class"],
        "file_type": promotion_record["file_type"],
        "extension": extension,
        "source_size_bytes": len(body_bytes),
        "declared_size_bytes": declared_size,
        "source_sha256": hashlib.sha256(body_bytes).hexdigest(),
        "extracted_text": body_text,
        "extracted_text_bytes": len(body_bytes),
        "extraction_state": "extracted",
        "ingestion_state": "extracted",
        "evidence_label": EVIDENCE_LABEL,
        "truth_status": "not_truth",
        "authority_label": promotion_record["authority_label"],
        "not_runtime_authority": True,
        "runtime_authority": False,
        "body_ingested": True,
        "extraction_time": None,
        "extraction_time_policy": EXTRACTION_TIME_POLICY,
        "promotion_ref": {
            "manifest_version": PROMOTION_MANIFEST_VERSION,
            "promotion_state": promotion_record["promotion_state"],
            "reason_for_promotion": promotion_record["reason_for_promotion"],
        },
    }, None


def build_extraction_artifact(
    promotion_manifest: dict[str, Any],
    *,
    root: Path | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    root_path = _manifest_root(promotion_manifest, root)
    inventory = _inventory_for_manifest(promotion_manifest, root_path)
    inventory_by_path = _records_by_path(inventory.get("records", []))

    extracted: list[dict[str, Any]] = []
    refusals: list[dict[str, Any]] = []
    for promotion_record in promotion_manifest.get("records", []):
        path = promotion_record.get("path", "")
        inventory_record = inventory_by_path.get(path)
        if inventory_record is None:
            refusals.append(_refusal(path, "path_not_in_source_inventory_allowlist", promotion_record))
            continue
        extracted_record, refusal = _extract_record(
            root=root_path,
            promotion_record=promotion_record,
            inventory_record=inventory_record,
            max_bytes=max_bytes,
        )
        if refusal is not None:
            refusals.append(refusal)
        if extracted_record is not None:
            extracted.append(extracted_record)

    return {
        "artifact_version": EXTRACTION_ARTIFACT_VERSION,
        "source_promotion_manifest_version": promotion_manifest.get("manifest_version"),
        "source_inventory_version": promotion_manifest.get("source_inventory_version"),
        "scope": {
            "root": root_path.as_posix(),
            "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
            "max_bytes": max_bytes,
            "extracts_only_promoted_sources": True,
            "sqlite_touched": False,
            "whole_repo_scan": False,
            "hard_drive_scan": False,
            "runtime_authority": False,
            "runtime_activation": False,
            "agent_activation": False,
            "broker_connection": False,
            "customer_deployment": False,
        },
        "records": extracted,
        "refusals": refusals,
        "summary": {
            "promotion_candidates": len(promotion_manifest.get("records", [])),
            "extracted_records": len(extracted),
            "refused_records": len(refusals),
            "body_ingested": bool(extracted),
            "evidence_label": EVIDENCE_LABEL,
            "runtime_authority": False,
        },
    }


def format_operator_extraction(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]
    scope = artifact["scope"]
    refused_paths = "; ".join(f"`{item['path']}`" for item in artifact.get("refusals", [])[:6]) or "none"

    lines = [
        "Safe Body Extraction v0",
        "",
        "Evidence:",
        f"- {summary['extracted_records']} promoted source records have approved body extraction.",
        f"- Extracted records are labeled `{summary['evidence_label']}` with source hash and size metadata.",
        f"- `body_ingested={str(summary['body_ingested']).lower()}` only for approved promoted records.",
        "",
        "Boundary:",
        (
            "- Extraction reads only `accepted_context_candidate` records with "
            f"extensions {', '.join(scope['allowed_extensions'])} and max size {scope['max_bytes']} bytes."
        ),
        "- Extracted bodies are parsed evidence, not truth; SQLite is untouched.",
        "- `runtime_authority=false`; no extraction record grants execution or activation authority.",
        "",
        "Blocked:",
        f"- {summary['refused_records']} promoted candidates were refused by extraction constraints.",
        f"- Refused paths: {refused_paths}.",
        "- Unapproved paths, no-go paths, secrets, private data, legal, tax, CPA/finance, AppData, and runtime logs are not extracted.",
        "- No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated.",
        "",
        "Next safe move:",
        "- Build deterministic source cards from extracted evidence; keep cards compact and explicitly non-runtime.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract safe text bodies for accepted context promotion candidates."
    )
    parser.add_argument(
        "--promotion-manifest",
        required=True,
        help="Accepted context promotion manifest JSON.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Maximum source size to extract. Defaults to {DEFAULT_MAX_BYTES}.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output path for the extraction artifact.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    promotion_manifest = load_json_artifact(args.promotion_manifest)
    artifact = build_extraction_artifact(
        promotion_manifest,
        max_bytes=args.max_bytes,
    )

    if args.output:
        write_json_artifact(artifact, args.output)

    if args.format == "json":
        print(stable_json(artifact), end="")
    else:
        print(format_operator_extraction(artifact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
