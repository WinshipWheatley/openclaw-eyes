#!/usr/bin/env python3
"""Promote bounded Source Inventory records to accepted context candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.build_source_inventory import build_inventory
except ImportError:
    from build_source_inventory import build_inventory


PROMOTION_MANIFEST_VERSION = "accepted_context_promotion_gate_v0"
PROMOTION_STATE = "accepted_context_candidate"

RUNTIME_AUTHORITY_LABELS = {
    "runtime_authority",
    "runtime_execution",
    "execution_authority",
    "live_runtime_authority",
}


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def load_json_artifact(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_artifact(payload: dict[str, Any], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(stable_json(payload), encoding="utf-8")


def _normalize_requested_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _records_by_path(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {record["path"]: record for record in inventory.get("records", [])}


def _is_non_runtime_authority(authority_label: str) -> bool:
    return authority_label not in RUNTIME_AUTHORITY_LABELS


def _promotable(record: dict[str, Any]) -> bool:
    return (
        record.get("ingestion_state") == "metadata_only"
        and record.get("allowed_for_agent_context") is True
        and record.get("body_ingested") is False
        and record.get("authority_label") != "blocked"
        and _is_non_runtime_authority(str(record.get("authority_label", "")))
    )


def _eligible_paths(inventory: dict[str, Any]) -> list[str]:
    return [
        record["path"]
        for record in inventory.get("records", [])
        if _promotable(record)
    ]


def _refusal(path: str, reason: str, record: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "path": path,
        "promotion_state": "refused",
        "eligible_for_extraction": False,
        "accepted_context_candidate": False,
        "reason_refused": reason,
        "source_class": (record or {}).get("source_class"),
        "authority_label": (record or {}).get("authority_label"),
        "runtime_authority": False,
        "body_ingested": False,
        "source_body_read": False,
    }


def _promotion_record(record: dict[str, Any], reason_for_promotion: str) -> dict[str, Any]:
    return {
        "path": record["path"],
        "source_class": record["source_class"],
        "file_type": record["file_type"],
        "extension": record["extension"],
        "size_bytes": record["size_bytes"],
        "committed_status": record["committed_status"],
        "sensitivity_label": record["sensitivity_label"],
        "authority_label": record["authority_label"],
        "source_inventory_ingestion_state": record["ingestion_state"],
        "promotion_state": PROMOTION_STATE,
        "eligible_for_extraction": True,
        "accepted_context_candidate": True,
        "reason_for_promotion": reason_for_promotion,
        "runtime_authority": False,
        "body_ingested": False,
        "source_body_read": False,
        "blocked_reason": "",
    }


def build_promotion_manifest(
    inventory: dict[str, Any],
    *,
    requested_paths: Iterable[str] = (),
    reason_for_promotion: str,
    all_allowlisted: bool = False,
) -> dict[str, Any]:
    reason = reason_for_promotion.strip()
    if not reason:
        raise ValueError("reason_for_promotion is required")

    if all_allowlisted:
        paths = _eligible_paths(inventory)
    else:
        paths = [_normalize_requested_path(path) for path in requested_paths]

    if not paths:
        raise ValueError("at least one path or all_allowlisted=True is required")

    records_by_path = _records_by_path(inventory)
    promoted: list[dict[str, Any]] = []
    refusals: list[dict[str, Any]] = []

    for path in paths:
        record = records_by_path.get(path)
        if record is None:
            refusals.append(
                _refusal(path, "path_not_in_source_inventory_allowlist")
            )
            continue

        if not _promotable(record):
            reason_refused = record.get("blocked_reason") or record.get("ingestion_state") or "not_promotable"
            refusals.append(_refusal(path, f"source_record_not_promotable:{reason_refused}", record))
            continue

        promoted.append(_promotion_record(record, reason))

    return {
        "manifest_version": PROMOTION_MANIFEST_VERSION,
        "source_inventory_version": inventory.get("inventory_version"),
        "source_inventory_mode": inventory.get("mode"),
        "source_inventory_scope": {
            "root": inventory.get("scope", {}).get("root"),
            "allowlist": inventory.get("scope", {}).get("allowlist", []),
        },
        "promotion_gate": {
            "state": "evaluated",
            "reason_for_promotion": reason,
            "requires_reason_for_promotion": True,
            "requires_allowlisted_source_inventory_record": True,
            "requires_non_runtime_authority": True,
        },
        "scope": {
            "body_ingested": False,
            "source_body_read": False,
            "sqlite_touched": False,
            "whole_repo_scan": False,
            "hard_drive_scan": False,
            "runtime_authority": False,
            "runtime_activation": False,
            "agent_activation": False,
            "broker_connection": False,
            "customer_deployment": False,
        },
        "records": promoted,
        "refusals": refusals,
        "summary": {
            "requested_records": len(paths),
            "promoted_records": len(promoted),
            "refused_records": len(refusals),
            "accepted_context_candidates": len(promoted),
            "eligible_for_extraction": len(promoted),
            "body_ingested": False,
            "source_body_read": False,
            "runtime_authority": False,
        },
    }


def format_operator_promotion(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    refusals = manifest.get("refusals", [])
    refused_paths = "; ".join(f"`{item['path']}`" for item in refusals[:6]) or "none"

    lines = [
        "Accepted Context Promotion Gate v0",
        "",
        "Evidence:",
        (
            f"- {summary['promoted_records']} allowlisted metadata-only source records are "
            "accepted context candidates."
        ),
        "- `reason_for_promotion` is required and recorded before extraction eligibility.",
        "- `body_ingested=false`; `source_body_read=false`; promotion uses Source Inventory metadata only.",
        "",
        "Boundary:",
        "- Promotion does not read source bodies, summarize content, touch SQLite, or scan beyond the inventory allowlist.",
        "- Approved records become `accepted_context_candidate` and `eligible_for_extraction`; they do not become truth or runtime authority.",
        "- `runtime_authority=false`; authority labels must remain non-runtime.",
        "",
        "Blocked:",
        f"- {summary['refused_records']} requested records were refused by the promotion gate.",
        f"- Refused paths: {refused_paths}.",
        "- Blocked/no-go records, missing records, secrets, private data, legal, tax, CPA/finance, AppData, and runtime logs remain outside accepted context.",
        "- No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated.",
        "",
        "Next safe move:",
        "- Run safe extraction only for promoted `eligible_for_extraction` records, then keep extracted evidence separate from truth and runtime authority.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote bounded Source Inventory records to accepted context candidates."
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--inventory-json",
        help="Optional Source Inventory JSON artifact. Defaults to rebuilding the deterministic inventory.",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Repo-relative inventory path to request for promotion. May be repeated.",
    )
    parser.add_argument(
        "--all-allowlisted",
        action="store_true",
        help="Promote every currently promotable allowlisted Source Inventory record.",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="Required reason_for_promotion recorded in the manifest.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output path for the promotion manifest.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    inventory = load_json_artifact(args.inventory_json) if args.inventory_json else build_inventory()
    manifest = build_promotion_manifest(
        inventory,
        requested_paths=args.path,
        reason_for_promotion=args.reason,
        all_allowlisted=args.all_allowlisted,
    )

    if args.output:
        write_json_artifact(manifest, args.output)

    if args.format == "json":
        print(stable_json(manifest), end="")
    else:
        print(format_operator_promotion(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
