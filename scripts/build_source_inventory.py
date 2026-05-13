#!/usr/bin/env python3
"""Build a bounded, metadata-only source inventory read model."""

from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]

INVENTORY_VERSION = "bounded_source_inventory_v0"

INGESTION_STATES = {
    "metadata_only",
    "extracted",
    "summarized",
    "accepted_working_context",
    "blocked",
}

AUTHORITY_LABELS = {
    "documentation_only",
    "receipt_record_only",
    "no_runtime_authority",
    "validation_proven",
    "blocked",
}

DEFAULT_ALLOWLIST = (
    "docs/module_atlas/",
    "docs/operations/OPENCLAW_GENERIC_RECEIPT_SPINE_V0.md",
    "docs/operations/OPENCLAW_OPERATOR_STATUS_GRAMMAR_V0.md",
    "scripts/record_artifact_checkpoint_receipts.py",
    "scripts/generate_operator_status.py",
    "scripts/validate_module_manifests.py",
    "tests/test_artifact_checkpoint_receipts.py",
    "tests/test_generate_operator_status.py",
    "tests/test_generic_receipt_spine.py",
    "tests/test_module_manifest_validation.py",
)


@dataclass(frozen=True)
class BlockedExample:
    path: str
    sensitivity_label: str
    blocked_reason: str


DEFAULT_BLOCKED_EXAMPLES = (
    BlockedExample(".chief.env", "secret_or_credential", "credential file is outside source inventory scope"),
    BlockedExample(".google-secrets/", "secret_or_credential", "secret directory is outside source inventory scope"),
    BlockedExample("Private/", "private_data", "private folder boundary example; contents are not inspected"),
    BlockedExample("Legal/", "legal_sensitive", "legal material requires a separate approved lane"),
    BlockedExample("Tax/", "tax_sensitive", "tax material requires a separate approved lane"),
    BlockedExample("CPA/", "financial_sensitive", "CPA/finance material requires a separate approved lane"),
    BlockedExample("C:/Users/Winship/AppData/", "local_appdata", "hard-drive/AppData scanning is forbidden"),
    BlockedExample(".openclaw/runtime_logs/", "runtime_log", "runtime logs are not source inventory inputs"),
)

NO_GO_PREFIXES = (
    ".chief.env",
    ".google-secrets/",
    "Private/",
    "Legal/",
    "Tax/",
    "CPA/",
    ".openclaw/runtime_logs/",
)


def _is_windows_drive_path(path: str) -> bool:
    first_part = Path(path).parts[0] if Path(path).parts else ""
    return len(first_part) == 2 and first_part[1] == ":"


def _is_no_go_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    normalized_lower = normalized.lower()
    if _is_windows_drive_path(normalized):
        return True
    if "/appdata/" in f"/{normalized_lower}/":
        return True
    return any(
        normalized_lower == prefix.lower().rstrip("/")
        or normalized_lower.startswith(prefix.lower())
        for prefix in NO_GO_PREFIXES
    )


def _run_git(args: list[str], root: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _normalize_repo_relative_path(path: str, root: Path) -> str | None:
    candidate = Path(path)
    if _is_windows_drive_path(path):
        return None
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(root.resolve())
        except ValueError:
            return None

    parts = candidate.parts
    if ".." in parts:
        return None

    normalized = candidate.as_posix().lstrip("./")
    return normalized or None


def _expand_allowlist(allowlist: Iterable[str], root: Path) -> list[str]:
    expanded: list[str] = []
    for raw_path in allowlist:
        normalized = _normalize_repo_relative_path(raw_path, root)
        if not normalized:
            continue
        if _is_no_go_path(normalized):
            continue

        if raw_path.endswith("/") or (root / normalized).is_dir():
            directory = root / normalized
            if directory.exists() and directory.is_dir():
                for child in sorted(directory.iterdir(), key=lambda item: item.as_posix()):
                    if child.is_file():
                        expanded.append(child.relative_to(root).as_posix())
            else:
                expanded.append(normalized.rstrip("/") + "/")
            continue

        expanded.append(normalized)

    return list(dict.fromkeys(expanded))


def _git_metadata(paths: list[str], root: Path) -> dict[str, dict[str, Any]]:
    if not paths:
        return {}

    tracked_result = _run_git(["ls-files", "--", *paths], root)
    tracked_paths = set()
    if tracked_result and tracked_result.returncode == 0:
        tracked_paths = {line.strip() for line in tracked_result.stdout.splitlines() if line.strip()}

    status_result = _run_git(["status", "--short", "--", *paths], root)
    status_by_path: dict[str, str] = {}
    if status_result and status_result.returncode == 0:
        for line in status_result.stdout.splitlines():
            if not line.strip():
                continue
            status = line[:2]
            status_path = line[3:].strip()
            if " -> " in status_path:
                status_path = status_path.split(" -> ", 1)[1]
            status_by_path[status_path] = status.strip() or "clean"

    metadata: dict[str, dict[str, Any]] = {}
    for path in paths:
        git_tracked = path in tracked_paths if tracked_result and tracked_result.returncode == 0 else None
        if git_tracked is None:
            committed_status = "unknown_git_unavailable"
        elif not git_tracked:
            committed_status = "untracked_or_missing"
        elif path in status_by_path:
            committed_status = f"tracked_with_status_{status_by_path[path]}"
        else:
            committed_status = "tracked_clean"
        metadata[path] = {
            "git_tracked": git_tracked,
            "committed_status": committed_status,
        }
    return metadata


def _classify_allowed_path(path: str) -> dict[str, str]:
    if path.startswith("docs/module_atlas/"):
        if "VALIDATION_CONTRACT" in path:
            return {
                "source_class": "module_atlas_validation_contract",
                "sensitivity_label": "repo_allowlisted_documentation",
                "authority_label": "validation_proven",
                "reason_included": "committed Module Atlas validation contract",
            }
        return {
            "source_class": "module_atlas_documentation",
            "sensitivity_label": "repo_allowlisted_documentation",
            "authority_label": "documentation_only",
            "reason_included": "committed Module Atlas documentation allowlist",
        }

    if path == "docs/operations/OPENCLAW_GENERIC_RECEIPT_SPINE_V0.md":
        return {
            "source_class": "receipt_spine_doctrine",
            "sensitivity_label": "repo_allowlisted_documentation",
            "authority_label": "receipt_record_only",
            "reason_included": "receipt spine doctrine for metadata-only evidence handling",
        }

    if path == "docs/operations/OPENCLAW_OPERATOR_STATUS_GRAMMAR_V0.md":
        return {
            "source_class": "operator_status_doctrine",
            "sensitivity_label": "repo_allowlisted_documentation",
            "authority_label": "documentation_only",
            "reason_included": "operator status grammar doctrine",
        }

    if path == "scripts/record_artifact_checkpoint_receipts.py":
        return {
            "source_class": "receipt_bootstrap_script",
            "sensitivity_label": "repo_allowlisted_source_code",
            "authority_label": "receipt_record_only",
            "reason_included": "generic artifact checkpoint receipt bootstrap path",
        }

    if path == "scripts/generate_operator_status.py":
        return {
            "source_class": "operator_status_script",
            "sensitivity_label": "repo_allowlisted_source_code",
            "authority_label": "no_runtime_authority",
            "reason_included": "generated operator status read-model path",
        }

    if path == "scripts/validate_module_manifests.py":
        return {
            "source_class": "module_manifest_validator",
            "sensitivity_label": "repo_allowlisted_source_code",
            "authority_label": "validation_proven",
            "reason_included": "committed Module Atlas validation script",
        }

    if path.startswith("tests/"):
        return {
            "source_class": "validation_test",
            "sensitivity_label": "repo_allowlisted_test_code",
            "authority_label": "validation_proven",
            "reason_included": "committed focused proof test allowlist",
        }

    return {
        "source_class": "explicit_allowlist_source",
        "sensitivity_label": "repo_allowlisted_metadata",
        "authority_label": "documentation_only",
        "reason_included": "explicit allowlist entry",
    }


def _file_type(path: str) -> str:
    guessed_type, _ = mimetypes.guess_type(path)
    if guessed_type:
        return guessed_type
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return "text/x-python"
    if suffix == ".md":
        return "text/markdown"
    return "unknown"


def _allowed_record(path: str, root: Path, git_meta: dict[str, Any]) -> dict[str, Any]:
    full_path = root / path
    classification = _classify_allowed_path(path)
    exists = full_path.exists() and full_path.is_file()
    stat_result = full_path.stat() if exists else None
    ingestion_state = "metadata_only" if exists else "blocked"
    blocked_reason = "" if exists else "allowlisted path is missing or not a file"
    authority_label = classification["authority_label"] if exists else "blocked"

    return {
        "path": path,
        "file_type": _file_type(path) if exists else "missing",
        "extension": Path(path).suffix,
        "size_bytes": stat_result.st_size if stat_result else None,
        "modified_time": None,
        "modified_time_policy": "omitted_for_stable_metadata_output",
        "git_tracked": git_meta.get("git_tracked"),
        "committed_status": git_meta.get("committed_status", "unknown"),
        "source_class": classification["source_class"] if exists else "missing_allowlisted_source",
        "sensitivity_label": classification["sensitivity_label"],
        "authority_label": authority_label,
        "ingestion_state": ingestion_state,
        "reason_included": classification["reason_included"],
        "allowed_for_agent_context": bool(exists),
        "body_ingested": False,
        "blocked_reason": blocked_reason,
    }


def _blocked_record(example: BlockedExample) -> dict[str, Any]:
    return {
        "path": example.path,
        "file_type": "blocked_example",
        "extension": Path(example.path.rstrip("/")).suffix,
        "size_bytes": None,
        "modified_time": None,
        "modified_time_policy": "not_checked_for_blocked_no_go_boundary",
        "git_tracked": None,
        "committed_status": "not_checked_no_go_boundary",
        "source_class": "blocked_no_go_example",
        "sensitivity_label": example.sensitivity_label,
        "authority_label": "blocked",
        "ingestion_state": "blocked",
        "reason_included": "boundary example only; no scan, stat, or body read performed",
        "allowed_for_agent_context": False,
        "body_ingested": False,
        "blocked_reason": example.blocked_reason,
    }


def build_inventory(
    root: Path = ROOT,
    allowlist: Iterable[str] = DEFAULT_ALLOWLIST,
    blocked_examples: Iterable[BlockedExample] = DEFAULT_BLOCKED_EXAMPLES,
    include_blocked_examples: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    allowed_paths = _expand_allowlist(allowlist, root)
    git_meta = _git_metadata(allowed_paths, root)
    allowed_records = [
        _allowed_record(path, root, git_meta.get(path, {})) for path in allowed_paths
    ]
    blocked_records = (
        [_blocked_record(example) for example in blocked_examples]
        if include_blocked_examples
        else []
    )
    records = allowed_records + blocked_records

    return {
        "inventory_version": INVENTORY_VERSION,
        "mode": "explicit_allowlist_metadata_only",
        "scope": {
            "root": root.as_posix(),
            "allowlist": list(allowlist),
            "whole_repo_scan": False,
            "hard_drive_scan": False,
            "sqlite_touched": False,
            "runtime_activation": False,
            "agent_activation": False,
            "broker_connection": False,
            "customer_deployment": False,
            "body_ingested": False,
        },
        "allowed_ingestion_states": sorted(INGESTION_STATES),
        "allowed_authority_labels": sorted(AUTHORITY_LABELS),
        "records": records,
        "summary": {
            "allowlisted_records": len(allowed_records),
            "blocked_records": len(blocked_records),
            "records_total": len(records),
            "body_ingested": any(record["body_ingested"] for record in records),
            "metadata_only_records": sum(
                1 for record in records if record["ingestion_state"] == "metadata_only"
            ),
            "blocked_no_go_examples": sum(
                1 for record in records if record["ingestion_state"] == "blocked"
            ),
        },
    }


def format_operator_inventory(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    records = inventory["records"]
    source_groups = Counter(
        record["source_class"]
        for record in records
        if record["ingestion_state"] == "metadata_only"
    )
    blocked_paths = [
        record["path"] for record in records if record["ingestion_state"] == "blocked"
    ]
    source_group_text = ", ".join(
        f"{source_class}={count}" for source_class, count in sorted(source_groups.items())
    )
    blocked_path_text = "; ".join(f"`{path}`" for path in blocked_paths) or "none"

    lines = [
        "Bounded Source Inventory v0",
        "",
        "Evidence:",
        (
            f"- {summary['allowlisted_records']} explicit allowlisted source records are "
            "known as metadata-only context."
        ),
        "- Records carry path, type, size, Git status when available, sensitivity label, authority label, and inclusion reason.",
        f"- Source groups: {source_group_text}.",
        f"- Body ingest is `{str(summary['body_ingested']).lower()}` for every record.",
    ]

    lines.extend(
        [
            "",
            "Boundary:",
            "- Inventory is allowlist-only; it does not scan the whole repo or hard drives.",
            "- `body_ingested=false`; SQLite is untouched; records are source metadata, not source bodies.",
            "- Authority labels describe documentation/receipt/validation posture only; they do not grant runtime authority.",
            "",
            "Blocked:",
            f"- {summary['blocked_records']} no-go boundary examples are represented without stat, scan, or body read.",
            "- Secrets, private data, legal, tax, CPA/finance, AppData, and runtime logs remain outside source inventory.",
            f"- Blocked examples: {blocked_path_text}.",
            "- No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated.",
        ]
    )

    lines.extend(
        [
            "",
            "Next safe move:",
            "- Use `--format json` as metadata-only agent context; promote any body access or accepted working context in a separate approved lane.",
        ]
    )

    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a bounded metadata-only source inventory."
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--allow-path",
        action="append",
        help="Explicit repo-relative allowlist path. May be repeated.",
    )
    parser.add_argument(
        "--no-blocked-examples",
        action="store_true",
        help="Do not include synthetic no-go boundary examples.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    inventory = build_inventory(
        allowlist=tuple(args.allow_path) if args.allow_path else DEFAULT_ALLOWLIST,
        include_blocked_examples=not args.no_blocked_examples,
    )

    if args.format == "json":
        print(json.dumps(inventory, indent=2, sort_keys=True))
    else:
        print(format_operator_inventory(inventory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
