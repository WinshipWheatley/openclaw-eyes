#!/usr/bin/env python3
"""Read-only OpenClaw receipt commands for low-context repo proof snapshots."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path("/home/openclaw")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openclaw_sensitive_policy import (
    PathPolicyFinding,
    broad_source_set_prefix_findings,
    is_under,
    normalize_repo_path,
    path_policy_findings,
    sensitive_root_contract,
)


CANONICAL_RECEIPT_COMMAND = "./scripts/openclaw_receipts.py"

ACTIVE_PACKET_RELATIVE_PATH = Path(
    "docs/planning/project_packets/"
    "06_OPERATOR_HARNESS_ACTOR_EFFICIENCY_AND_SENSITIVE_WORKFLOWS"
)
PACKET_INDEX_RELATIVE_PATH = Path("docs/planning/project_packets/README.md")
ACTIVE_HANDOFF_RELATIVE_PATH = ACTIVE_PACKET_RELATIVE_PATH / "00_ACTIVE_HANDOFF.md"
ACTIVE_RAILS_RELATIVE_PATH = ACTIVE_PACKET_RELATIVE_PATH / "24_files"

REQUIRED_RAIL_FILES = (
    "01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
    "02_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md",
    "03_CORE_ARCHITECTURE_PRINCIPLES.md",
    "04_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md",
    "05_OPERATOR_NORTH_STAR_MACHINE_CONTRACT.md",
    "06_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md",
    "07_VALIDATION_MAP_AND_TEST_BOUNDARIES.md",
    "08_BACKEND_DATA_CONTRACT_AND_SCHEMA_TRUTH.md",
    "09_BACKEND_REPOSITORY_AND_RUNTIME_TRUTH.md",
    "10_CONTEXT_SUBSTRATE_AND_TRAVERSAL_TRUTH.md",
    "11_ACTOR_REGISTRY_AND_TRUST_BRIDGE_TRUTH.md",
    "12_STORAGE_INTELLIGENCE_AND_AUTHORIZATION.md",
    "13_PERFORMANCE_DIRECTOR_SHOW_MAP_TRUTH.md",
    "14_CLI_RECEIPT_LAYER_AND_LOW_CONTEXT_INTERFACE.md",
    "15_SENSITIVE_ROOT_QUARANTINE_POLICY_AND_REGISTRY.md",
    "16_INVOICE_ARTIFACT_AND_BILLING_BRIDGE_PLAN.md",
    "17_ACTOR_SIDECAR_AND_CONTEXT_EXPORT_HARDENING_PLAN.md",
    "18_OPERATOR_HARNESS_READ_MODEL_PLAN.md",
    "19_LEGAL_CONTEXT_EXPORT_POLICY_PLAN.md",
    "20_RUNTIME_INTEGRATION_AND_RECOVERY_ARCHITECTURE.md",
    "21_MCP_SHARED_MEMORY_ARCHITECTURE_REVIEW.md",
    "22_RUNTIME_AUTHORITY_AND_LEGACY_GATING.md",
    "23_BROAD_SOURCE_SET_EXCLUSION_GUARD.md",
    "24_VISIBLE_ROAD_AND_BIG_STRIDES_DOCTRINE.md",
)

KEY_RAIL_FILES = (
    "01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
    "07_VALIDATION_MAP_AND_TEST_BOUNDARIES.md",
    "14_CLI_RECEIPT_LAYER_AND_LOW_CONTEXT_INTERFACE.md",
    "15_SENSITIVE_ROOT_QUARANTINE_POLICY_AND_REGISTRY.md",
    "17_ACTOR_SIDECAR_AND_CONTEXT_EXPORT_HARDENING_PLAN.md",
    "18_OPERATOR_HARNESS_READ_MODEL_PLAN.md",
    "20_RUNTIME_INTEGRATION_AND_RECOVERY_ARCHITECTURE.md",
    "22_RUNTIME_AUTHORITY_AND_LEGACY_GATING.md",
    "23_BROAD_SOURCE_SET_EXCLUSION_GUARD.md",
    "24_VISIBLE_ROAD_AND_BIG_STRIDES_DOCTRINE.md",
)

@dataclass(frozen=True)
class GitCommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ChangedFile:
    status: str
    path: str


def _run_git(root: Path, args: Sequence[str]) -> GitCommandResult:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return GitCommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _first_line(text: str) -> str:
    return text.splitlines()[0] if text.splitlines() else ""


def _clean_git_path(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        try:
            parsed = ast.literal_eval(cleaned)
        except (SyntaxError, ValueError):
            return cleaned.strip('"')
        if isinstance(parsed, str):
            return parsed
    return cleaned


def parse_porcelain_status(output: str) -> list[ChangedFile]:
    changed: list[ChangedFile] = []
    for line in output.splitlines():
        if not line:
            continue
        status = line[:2].strip() or line[:2]
        raw_path = line[3:] if len(line) > 3 else ""
        if " -> " in raw_path:
            old_path, new_path = raw_path.split(" -> ", 1)
            changed.append(ChangedFile(status=status, path=_clean_git_path(old_path)))
            changed.append(ChangedFile(status=status, path=_clean_git_path(new_path)))
            continue
        changed.append(ChangedFile(status=status, path=_clean_git_path(raw_path)))
    return changed


def changed_files(root: Path = ROOT) -> tuple[ChangedFile, ...]:
    result = _run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return tuple(parse_porcelain_status(result.stdout))


def _packet_index_points_to_active(index_text: str) -> bool:
    full_path = str(ACTIVE_PACKET_RELATIVE_PATH).replace("\\", "/")
    packet_name = ACTIVE_PACKET_RELATIVE_PATH.name
    accepted_markers = (
        full_path,
        full_path + "/",
        packet_name,
        packet_name + "/",
    )
    return any(marker in index_text for marker in accepted_markers)


def docs_only_guard_report(
    files: Iterable[ChangedFile],
    *,
    allowed_prefixes: Sequence[str],
    root: Path = ROOT,
) -> dict[str, object]:
    normalized_allowed = tuple(
        normalize_repo_path(prefix, root)[0].rstrip("/") for prefix in allowed_prefixes
    )
    changed = tuple(files)
    changed_paths = tuple(item.path for item in changed)
    private_findings = path_policy_findings(changed_paths, root=root)
    broad_allowed_prefixes = broad_source_set_prefix_findings(
        normalized_allowed,
        root=root,
    )
    outside_allowed = tuple(
        item.path
        for item in changed
        if normalized_allowed
        and not any(
            is_under(normalize_repo_path(item.path, root)[0], prefix)
            for prefix in normalized_allowed
        )
    )

    return {
        "receipt_type": "openclaw.docs_only_guard",
        "mode": "read-only/static-path-policy",
        "allowed_prefixes": normalized_allowed,
        "broad_allowed_prefixes": broad_allowed_prefixes,
        "changed_files": changed,
        "private_findings": private_findings,
        "outside_allowed": outside_allowed,
        "passed": not private_findings and not outside_allowed and not broad_allowed_prefixes,
    }


def packet_status(root: Path = ROOT) -> dict[str, object]:
    packet_index = root / PACKET_INDEX_RELATIVE_PATH
    packet_dir = root / ACTIVE_PACKET_RELATIVE_PATH
    handoff = root / ACTIVE_HANDOFF_RELATIVE_PATH
    rails_dir = root / ACTIVE_RAILS_RELATIVE_PATH

    existing_rails: tuple[str, ...] = ()
    if rails_dir.is_dir():
        existing_rails = tuple(
            sorted(
                path.name
                for path in rails_dir.iterdir()
                if path.is_file() and path.suffix == ".md"
            )
        )

    missing_rails = tuple(name for name in REQUIRED_RAIL_FILES if name not in existing_rails)
    extra_rails = tuple(name for name in existing_rails if name not in REQUIRED_RAIL_FILES)
    key_rails = {
        name: (rails_dir / name).is_file()
        for name in KEY_RAIL_FILES
    }

    index_text = packet_index.read_text(encoding="utf-8") if packet_index.is_file() else ""
    handoff_first_line = _first_line(handoff.read_text(encoding="utf-8")) if handoff.is_file() else ""
    index_points_to_active = _packet_index_points_to_active(index_text)

    return {
        "receipt_type": "openclaw.packet_status",
        "mode": "read-only/exact-packet-paths",
        "active_packet": str(ACTIVE_PACKET_RELATIVE_PATH),
        "packet_index_present": packet_index.is_file(),
        "packet_index_points_to_active": index_points_to_active,
        "packet_dir_present": packet_dir.is_dir(),
        "handoff_present": handoff.is_file(),
        "handoff_first_line": handoff_first_line,
        "rails_dir_present": rails_dir.is_dir(),
        "rail_count": len(existing_rails),
        "missing_rails": missing_rails,
        "extra_rails": extra_rails,
        "key_rails": key_rails,
        "passed": (
            packet_index.is_file()
            and index_points_to_active
            and packet_dir.is_dir()
            and handoff.is_file()
            and rails_dir.is_dir()
            and len(existing_rails) == 24
            and not missing_rails
            and not extra_rails
            and all(key_rails.values())
        ),
    }


def repo_check_receipt(root: Path = ROOT) -> dict[str, object]:
    status = _run_git(root, ["status", "-sb", "--untracked-files=all"])
    head = _run_git(root, ["--no-pager", "log", "--oneline", "-1"])
    diff_check = _run_git(root, ["diff", "--check"])
    cached_diff_check = _run_git(root, ["diff", "--cached", "--check"])
    packet = packet_status(root)
    changed = parse_porcelain_status(
        _run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"]).stdout
    )

    return {
        "receipt_type": "openclaw.repo_check",
        "mode": "read-only/git-and-exact-packet-paths",
        "root": str(root),
        "canonical_command": CANONICAL_RECEIPT_COMMAND,
        "branch_status": _first_line(status.stdout),
        "head": _first_line(head.stdout),
        "worktree_clean": not changed,
        "changed_file_count": len(changed),
        "diff_check_passed": diff_check.returncode == 0,
        "cached_diff_check_passed": cached_diff_check.returncode == 0,
        "packet_status_passed": bool(packet["passed"]),
        "git_failures": tuple(
            name
            for name, result in (
                ("status", status),
                ("head", head),
                ("diff_check", diff_check),
                ("cached_diff_check", cached_diff_check),
            )
            if result.returncode != 0
        ),
        "passed": (
            status.returncode == 0
            and head.returncode == 0
            and diff_check.returncode == 0
            and cached_diff_check.returncode == 0
            and bool(packet["passed"])
        ),
    }


def operator_harness_read_model(
    *,
    root: Path = ROOT,
    files: Sequence[ChangedFile] | None = None,
) -> dict[str, object]:
    changed = tuple(files) if files is not None else changed_files(root)
    changed_paths = tuple(item.path for item in changed)
    private_findings = path_policy_findings(changed_paths, root=root)
    packet = packet_status(root)
    sensitive_contract = sensitive_root_contract()
    status = _run_git(root, ["status", "-sb", "--untracked-files=all"])
    head = _run_git(root, ["--no-pager", "log", "--oneline", "-1"])

    return {
        "receipt_type": "openclaw.operator_harness_read_model",
        "mode": "read-only/low-context",
        "authority_note": "Receipts are proof snapshots; File 01 remains roadmap authority.",
        "cards": (
            {
                "card": "command_surface",
                "canonical_command": CANONICAL_RECEIPT_COMMAND,
                "read_only": True,
                "write_capable": False,
            },
            {
                "card": "repo",
                "branch_status": _first_line(status.stdout),
                "head": _first_line(head.stdout),
                "changed_file_count": len(changed),
                "private_path_policy": "blocked" if private_findings else "clear",
            },
            {
                "card": "packet",
                "active_packet": packet["active_packet"],
                "rail_count": packet["rail_count"],
                "packet_status": "present" if packet["passed"] else "review",
            },
            {
                "card": "active_handoff",
                "present": packet["handoff_present"],
                "first_line": packet["handoff_first_line"],
                "roadmap_authority": "24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
                "is_roadmap_authority": False,
            },
            {
                "card": "sensitive_root_policy",
                "contract_mode": sensitive_contract["mode"],
                "path_policy_only": sensitive_contract["path_policy_only"],
                "content_access_allowed": sensitive_contract["content_access_allowed"],
                "filesystem_inspected": sensitive_contract["filesystem_inspected"],
            },
            {
                "card": "source_set_exclusion",
                "broad_scan_used": False,
                "broad_source_set_authority": False,
                "private_root_inspection_used": False,
                "withheld_surfaces": (
                    "private roots",
                    "secrets/env/credentials",
                    "legal/client/private folders",
                    "runtime/provider/billing surfaces",
                ),
            },
            {
                "card": "runtime_authority",
                "live_service_inspection_used": False,
                "runtime_mutation_allowed": False,
                "receipt_grants_execution": False,
                "static_review_pointer": "service_inventory_audit.py",
            },
            {
                "card": "recovery",
                "runtime_launched": False,
                "self_authorizing": False,
                "static_review_pointer": "tests/test_chief_listener_lifecycle.py",
            },
            {
                "card": "mcp_shared_memory",
                "external_mcp_calls_used": False,
                "hidden_memory_writes_allowed": False,
                "receipts_are_execution_authority": False,
            },
        ),
        "private_findings": private_findings,
        "passed": bool(packet["passed"]) and not private_findings,
    }


def _print_scalar_lines(title: str, rows: Iterable[tuple[str, object]]) -> None:
    print(f"# {title}")
    for key, value in rows:
        print(f"{key}: {value}")


def _print_list(name: str, values: Iterable[object]) -> None:
    print(f"{name}:")
    items = list(values)
    if not items:
        print("- none")
        return
    for value in items:
        print(f"- {value}")


def _redacted_path(path: str, findings: Sequence[PathPolicyFinding]) -> str:
    if any(finding.path == path for finding in findings):
        return "<withheld_by_static_path_policy>"
    return path


def _redacted_match(finding: PathPolicyFinding) -> str:
    if finding.finding == "outside_repo_or_parent_escape":
        return "<withheld_by_static_path_policy>"
    return finding.matched


def print_packet_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Packet Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("active_packet", report["active_packet"]),
            ("packet_index_present", report["packet_index_present"]),
            ("packet_index_points_to_active", report["packet_index_points_to_active"]),
            ("packet_dir_present", report["packet_dir_present"]),
            ("handoff_present", report["handoff_present"]),
            ("rails_dir_present", report["rails_dir_present"]),
            ("rail_count", report["rail_count"]),
            ("passed", report["passed"]),
        ),
    )
    print(f"handoff_first_line: {report['handoff_first_line']}")
    _print_list("missing_rails", report["missing_rails"])
    _print_list("extra_rails", report["extra_rails"])
    print("key_rails:")
    for name, present in report["key_rails"].items():
        print(f"- {name}: {present}")


def print_repo_check(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Repo Check Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("root", report["root"]),
            ("canonical_command", report["canonical_command"]),
            ("branch_status", report["branch_status"]),
            ("head", report["head"]),
            ("worktree_clean", report["worktree_clean"]),
            ("changed_file_count", report["changed_file_count"]),
            ("diff_check_passed", report["diff_check_passed"]),
            ("cached_diff_check_passed", report["cached_diff_check_passed"]),
            ("packet_status_passed", report["packet_status_passed"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("git_failures", report["git_failures"])


def print_changed_files_receipt(files: Sequence[ChangedFile], findings: Sequence[PathPolicyFinding]) -> None:
    _print_scalar_lines(
        "OpenClaw Changed Files Receipt",
        (
            ("receipt_type", "openclaw.changed_files"),
            ("mode", "read-only/git-status-and-static-path-policy"),
            ("changed_file_count", len(files)),
            ("private_path_policy", "blocked" if findings else "clear"),
        ),
    )
    print("changed_files:")
    if not files:
        print("- none")
    for item in files:
        print(f"- {item.status} {_redacted_path(item.path, findings)}")
    print_findings(findings)


def print_findings(findings: Sequence[PathPolicyFinding]) -> None:
    print("path_policy_findings:")
    if not findings:
        print("- none")
        return
    for finding in findings:
        print(f"- <withheld_by_static_path_policy>: {finding.finding} ({_redacted_match(finding)})")


def print_no_private_root_check(paths: Sequence[str], findings: Sequence[PathPolicyFinding]) -> None:
    _print_scalar_lines(
        "OpenClaw No Private Root Check Receipt",
        (
            ("receipt_type", "openclaw.no_private_root_check"),
            ("mode", "read-only/path-strings-only"),
            ("path_policy_only", True),
            ("filesystem_inspected", False),
            ("content_accessed", False),
            ("path_count", len(paths)),
            ("passed", not findings),
        ),
    )
    print_findings(findings)


def print_docs_only_guard(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Docs-Only Guard Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("allowed_prefixes", report["allowed_prefixes"])
    _print_list("broad_allowed_prefixes", report["broad_allowed_prefixes"])
    print("changed_files:")
    for item in report["changed_files"]:
        print(f"- {item.status} {_redacted_path(item.path, report['private_findings'])}")
    _print_list(
        "outside_allowed",
        (
            _redacted_path(path, report["private_findings"])
            for path in report["outside_allowed"]
        ),
    )
    print_findings(report["private_findings"])


def print_sensitive_root_contract(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Sensitive Root Static Contract Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("content_access_allowed", report["content_access_allowed"]),
            ("path_policy_only", report["path_policy_only"]),
            ("filesystem_inspected", report["filesystem_inspected"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("registry_fields", report["registry_fields"])
    _print_list("quarantine_states", report["quarantine_states"])
    print("quarantine_intake_contract:")
    for key, value in report["quarantine_intake_contract"].items():
        print(f"- {key}: {value}")
    _print_list("forbidden_actions", report["forbidden_actions"])


def print_operator_harness_read_model(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Operator Harness Read Model Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("authority_note", report["authority_note"]),
            ("passed", report["passed"]),
        ),
    )
    print("cards:")
    for card in report["cards"]:
        print(f"- {card['card']}:")
        for key, value in card.items():
            if key == "card":
                continue
            print(f"  {key}: {value}")
    print_findings(report["private_findings"])


def _paths_from_args_or_changes(args: argparse.Namespace, root: Path) -> tuple[str, ...]:
    paths = tuple(args.paths or ())
    if args.from_changed_files or not paths:
        paths = tuple(item.path for item in changed_files(root))
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=CANONICAL_RECEIPT_COMMAND,
        description="Read-only OpenClaw proof receipts.",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root.")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("repo-check", help="Print git and active-packet proof receipt.")
    subparsers.add_parser("changed-files-receipt", help="Print changed files with static path policy.")
    subparsers.add_parser("packet-status", help="Print active Packet 06 status receipt.")

    docs_guard = subparsers.add_parser(
        "docs-only-guard",
        help="Fail if changed files leave allowed prefixes.",
    )
    docs_guard.add_argument(
        "--allowed",
        action="append",
        required=True,
        help="Allowed repo-relative path or prefix. Repeat for multiple prefixes.",
    )

    private_check = subparsers.add_parser(
        "no-private-root-check",
        help="Check path strings against private/sensitive deny policy.",
    )
    private_check.add_argument("paths", nargs="*", help="Path strings to check.")
    private_check.add_argument(
        "--from-changed-files",
        action="store_true",
        help="Check current git changed-file paths.",
    )

    subparsers.add_parser(
        "sensitive-root-contract",
        help="Print metadata-only Sensitive Root Registry static contract.",
    )
    subparsers.add_parser(
        "operator-harness-status",
        help="Print low-context read-only operator harness receipt cards.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root

    if args.command == "repo-check":
        report = repo_check_receipt(root)
        print_repo_check(report)
        return 0 if report["passed"] else 1
    if args.command == "changed-files-receipt":
        files = changed_files(root)
        findings = path_policy_findings((item.path for item in files), root=root)
        print_changed_files_receipt(files, findings)
        return 0 if not findings else 1
    if args.command == "packet-status":
        report = packet_status(root)
        print_packet_status(report)
        return 0 if report["passed"] else 1
    if args.command == "docs-only-guard":
        report = docs_only_guard_report(
            changed_files(root),
            allowed_prefixes=tuple(args.allowed),
            root=root,
        )
        print_docs_only_guard(report)
        return 0 if report["passed"] else 1
    if args.command == "no-private-root-check":
        paths = _paths_from_args_or_changes(args, root)
        findings = path_policy_findings(paths, root=root)
        print_no_private_root_check(paths, findings)
        return 0 if not findings else 1
    if args.command == "sensitive-root-contract":
        report = sensitive_root_contract()
        print_sensitive_root_contract(report)
        return 0
    if args.command == "operator-harness-status":
        report = operator_harness_read_model(root=root)
        print_operator_harness_read_model(report)
        return 0 if report["passed"] else 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
