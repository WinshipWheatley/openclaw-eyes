"""Build warning-only quarantine read-models for high-risk active machinery.

This module consumes the operator disposition packet and the quarantine ready
packet. It does not execute candidate machinery, inspect source bodies, edit
launchers, disable services, or change runtime behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "active_machinery_high_risk_quarantine_v0"
REVIEW_SCHEMA_VERSION = "active_machinery_quarantine_operator_review_v0"
DEFAULT_DISPOSITION_PATH = Path("generated/read_models/active_machinery_operator_disposition.json")
DEFAULT_READY_PACKET_PATH = Path("docs/operations/ACTIVE_MACHINERY_HIGH_RISK_QUARANTINE_READY_PACKET.json")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
OPERATOR_EXPORT_NAME = "active_machinery_high_risk_quarantine_OPERATOR.md"
REVIEW_OPERATOR_EXPORT_NAME = "active_machinery_quarantine_operator_review_OPERATOR.md"

WARNING_DISPOSITIONS = {
    "block_no_go",
    "replace_with_governed_path",
    "wrap_with_guardian",
    "retire_later",
    "keep_test_only",
}

REVIEW_GROUPS = [
    ("block_later", "Block later"),
    ("replace_with_governed_path", "Replace with governed path"),
    ("wrap_with_guardian", "Wrap with Guardian"),
    ("retire_later", "Retire later"),
    ("keep_for_now_current_dependency", "Keep for now / current dependency"),
    ("needs_operator_decision", "Needs operator decision"),
]

DISPOSITION_TO_PRIMARY_REVIEW_GROUP = {
    "block_no_go": "block_later",
    "replace_with_governed_path": "replace_with_governed_path",
    "wrap_with_guardian": "wrap_with_guardian",
    "retire_later": "retire_later",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def load_json(path: str | Path) -> dict[str, Any]:
    target = rooted(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {display_path(target)}")
    return payload


def write_json(path: str | Path, payload: Any) -> str:
    target = rooted(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stable_json(payload), encoding="utf-8")
    return display_path(target)


def write_text(path: str | Path, text: str) -> str:
    target = rooted(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return display_path(target)


def _by_relative_path(disposition: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["relative_path"]): item
        for item in disposition.get("high_risk_dispositions", [])
        if isinstance(item, dict) and item.get("relative_path")
    }


def _references_for_path(relative_path: str, findings: list[str]) -> list[str]:
    path_name = Path(relative_path).name
    references: list[str] = []
    for finding in findings:
        if relative_path in finding or path_name in finding:
            references.append(finding)
    return references


def _base_warning_fields() -> dict[str, bool | str]:
    return {
        "quarantine_status": "warning_only",
        "activation_allowed": False,
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "services_disabled": False,
        "destructive_quarantine_allowed": False,
        "service_disable_allowed": False,
        "file_rename_allowed": False,
        "file_delete_allowed": False,
        "file_move_allowed": False,
        "chmod_change_allowed": False,
        "launcher_edit_allowed": False,
        "caller_switch_allowed": False,
        "send_wrapper_change_allowed": False,
        "runtime_activation_allowed": False,
        "operator_approval_required_for_runtime_change": True,
        "first_safe_action": "generated_read_model_warning",
    }


def _warning_from_disposition(
    item: dict[str, Any],
    *,
    static_reference_findings: list[str],
    not_ready_for: list[str],
) -> dict[str, Any]:
    disposition = str(item.get("recommended_disposition"))
    if disposition not in WARNING_DISPOSITIONS:
        raise ValueError(f"unsupported quarantine disposition for {item.get('relative_path')}: {disposition}")
    relative_path = str(item["relative_path"])
    warning = {
        **_base_warning_fields(),
        "surface_id": relative_path.replace("/", "__"),
        "relative_path": relative_path,
        "repo_root": item.get("repo_root"),
        "repo_role": item.get("repo_role"),
        "is_test_only": bool(item.get("is_test_only")),
        "live_runtime_machinery": not bool(item.get("is_test_only")),
        "machinery_type": item.get("machinery_type"),
        "verification_status": item.get("verification_status"),
        "current_authority_risk": item.get("current_authority_risk"),
        "disposition": disposition,
        "affected_domains": item.get("affected_domains") or [],
        "signal_groups": item.get("signal_groups") or [],
        "static_capabilities": item.get("static_capabilities") or {},
        "why_it_matters": item.get("why_it_matters"),
        "what_must_happen_before_it_can_run": item.get("what_must_happen_before_it_can_run"),
        "operator_decision_required": bool(item.get("operator_decision_required")),
        "not_ready_for": not_ready_for,
        "static_references": _references_for_path(relative_path, static_reference_findings),
        "next_safe_move": "operator review before any runtime quarantine action",
    }
    if warning["is_test_only"]:
        warning["quarantine_status"] = "test_only_warning"
        warning["live_runtime_machinery"] = False
        warning["operator_approval_required_for_runtime_change"] = False
        warning["next_safe_move"] = "keep test-only unless a later audit proves live runtime exposure"
    return warning


def build_quarantine_payload(
    *,
    disposition_path: str | Path = DEFAULT_DISPOSITION_PATH,
    ready_packet_path: str | Path = DEFAULT_READY_PACKET_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    disposition = load_json(disposition_path)
    ready_packet = load_json(ready_packet_path)
    if not ready_packet.get("ready_for_implementation"):
        raise ValueError("quarantine ready packet is not marked ready_for_implementation")
    if ready_packet.get("implementation_scope") != "metadata_read_model_warning_only":
        raise ValueError("quarantine ready packet does not allow this warning-only implementation")

    live_targets = [str(path) for path in ready_packet.get("high_risk_live_script_items", [])]
    test_only_targets = [
        str(path) for path in ready_packet.get("test_only_items_excluded_from_runtime_quarantine", [])
    ]
    static_reference_findings = [str(item) for item in ready_packet.get("static_active_reference_findings", [])]
    not_ready_for = [str(item) for item in ready_packet.get("not_ready_for", [])]
    by_path = _by_relative_path(disposition)

    missing_live = [path for path in live_targets if path not in by_path]
    missing_test_only = [path for path in test_only_targets if path not in by_path]
    if missing_live or missing_test_only:
        raise ValueError(
            "quarantine ready packet references disposition rows that are missing: "
            f"live={missing_live}; test_only={missing_test_only}"
        )

    high_risk_warnings = [
        _warning_from_disposition(
            by_path[path],
            static_reference_findings=static_reference_findings,
            not_ready_for=not_ready_for,
        )
        for path in live_targets
    ]
    test_only_items = [
        _warning_from_disposition(
            by_path[path],
            static_reference_findings=static_reference_findings,
            not_ready_for=not_ready_for,
        )
        for path in test_only_targets
    ]
    by_disposition: dict[str, int] = {}
    for item in high_risk_warnings + test_only_items:
        disposition_key = str(item["disposition"])
        by_disposition[disposition_key] = by_disposition.get(disposition_key, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "mode": "metadata_read_model_warning_only",
        "source_files": {
            "disposition_read_model": display_path(rooted(disposition_path)),
            "ready_packet": display_path(rooted(ready_packet_path)),
        },
        "warning_only": True,
        "quarantine_status": "warning_only",
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "services_disabled": False,
        "destructive_quarantine_allowed": False,
        "repo_b_executed": False,
        "subprocess_or_shell_execution_used": False,
        "agents_enabled": False,
        "sends_enabled": False,
        "daemons_enabled": False,
        "callers_switched": False,
        "launchers_edited": False,
        "old_hitl_deleted": False,
        "counts": {
            "high_risk_warning_count": len(high_risk_warnings),
            "test_only_warning_count": len(test_only_items),
            "static_reference_count": len(static_reference_findings),
            "high_risk_with_static_references": sum(1 for item in high_risk_warnings if item["static_references"]),
            "by_disposition": dict(sorted(by_disposition.items())),
        },
        "high_risk_warnings": high_risk_warnings,
        "test_only_items": test_only_items,
        "static_reference_findings": static_reference_findings,
        "not_ready_for": not_ready_for,
        "boundaries": {
            "no_runtime_modification": True,
            "no_service_disable": True,
            "no_file_move_delete_rename_chmod": True,
            "no_launcher_edit": True,
            "no_agent_send_daemon_enablement": True,
            "no_repo_b_execution": True,
        },
        "next_safe_move": "Active Machinery Quarantine Operator Review v0",
    }


def _capability_summary(item: dict[str, Any]) -> dict[str, list[str]]:
    capabilities = item.get("static_capabilities") or {}
    return {
        key: [str(value) for value in capabilities.get(key, [])]
        for key in ("reads", "writes", "executes", "sends")
    }


def _what_it_is(item: dict[str, Any]) -> str:
    machinery_type = str(item.get("machinery_type") or "active_machinery")
    if machinery_type == "send_external_api":
        return "Send/API-capable surface"
    if machinery_type == "daemon_listener":
        if str(item.get("relative_path", "")).endswith(".sh"):
            return "Shell launcher or watcher surface"
        return "Listener, watcher, or daemon-style surface"
    return machinery_type.replace("_", " ").title()


def _blocks_for_item(item: dict[str, Any]) -> dict[str, bool]:
    domains = set(item.get("affected_domains") or [])
    signals = set(item.get("signal_groups") or [])
    return {
        "cassandra_chief_utility": bool(domains & {"Cassandra", "Chief", "Guardian/HITL"}),
        "remote_builder": "remote builder" in domains,
        "send_paths": "send paths" in domains or bool(signals & {"send_external_api", "path_send_api_hint"}),
        "module_cleanup": True,
    }


def _recommended_future_action(item: dict[str, Any]) -> str:
    disposition = item["disposition"]
    if disposition == "block_no_go":
        return "Keep warning-only now; later block activation or replace with governed path after operator approval."
    if disposition == "replace_with_governed_path":
        return "Design a governed replacement before any caller switch or service change."
    if disposition == "wrap_with_guardian":
        return "Keep no-send now; require immutable Guardian/Operator Action packet and receipt proof before runtime use."
    if disposition == "retire_later":
        return "Prove no active dependency or governed equivalent before retirement."
    return "Keep untouched until operator decides a bounded lane."


def _review_item_from_warning(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "surface_id": item["surface_id"],
        "relative_path": item["relative_path"],
        "what_it_is": _what_it_is(item),
        "why_it_matters": item.get("why_it_matters"),
        "current_risk": item.get("current_authority_risk"),
        "current_disposition": item.get("disposition"),
        "current_static_references": item.get("static_references") or [],
        "current_static_dependencies": {
            "affected_domains": item.get("affected_domains") or [],
            "signal_groups": item.get("signal_groups") or [],
            "capabilities": _capability_summary(item),
        },
        "recommended_future_action": _recommended_future_action(item),
        "what_must_be_proven_before_acting": item.get("what_must_happen_before_it_can_run"),
        "blocks": _blocks_for_item(item),
        "runtime_action_allowed_now": False,
        "files_moved_or_deleted": False,
        "services_disabled": False,
        "operator_decision_required": bool(item.get("operator_decision_required")),
    }


def _empty_review_groups() -> dict[str, dict[str, Any]]:
    return {
        group_id: {"group_id": group_id, "display_name": display_name, "count": 0, "items": []}
        for group_id, display_name in REVIEW_GROUPS
    }


def build_operator_review_payload(
    *,
    quarantine_path: str | Path = DEFAULT_READ_MODEL_ROOT / "active_machinery_high_risk_quarantine.json",
    disposition_path: str | Path = DEFAULT_DISPOSITION_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    quarantine = load_json(quarantine_path)
    disposition = load_json(disposition_path)
    if quarantine.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("expected active machinery high-risk quarantine read-model")
    if quarantine.get("warning_only") is not True:
        raise ValueError("quarantine read-model is not warning-only")

    groups = _empty_review_groups()
    review_items = [_review_item_from_warning(item) for item in quarantine.get("high_risk_warnings", [])]
    for item in review_items:
        primary_group = DISPOSITION_TO_PRIMARY_REVIEW_GROUP.get(
            str(item["current_disposition"]), "needs_operator_decision"
        )
        groups[primary_group]["items"].append(item)
        if item["operator_decision_required"]:
            groups["needs_operator_decision"]["items"].append(item)

    for group in groups.values():
        group["count"] = len(group["items"])

    counts = {group_id: groups[group_id]["count"] for group_id, _ in REVIEW_GROUPS}
    counts["total_high_risk_live_script_items"] = len(review_items)
    counts["test_only_items_excluded"] = int(quarantine.get("counts", {}).get("test_only_warning_count", 0))

    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "mode": "operator_review_read_model_only",
        "source_files": {
            "high_risk_quarantine_read_model": display_path(rooted(quarantine_path)),
            "operator_disposition_read_model": display_path(rooted(disposition_path)),
        },
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "services_disabled": False,
        "repo_b_executed": False,
        "warning_only": True,
        "operator_review_only": True,
        "destructive_action_allowed": False,
        "counts": counts,
        "review_groups": groups,
        "test_only_items_not_runtime_targets": quarantine.get("test_only_items", []),
        "static_reference_findings": quarantine.get("static_reference_findings", []),
        "operator_decisions_needed": [
            "Approve which block_later surfaces should become denylisted, replaced, or left as warning-only.",
            "Approve replacement lanes for Cassandra/Chief/Guardian listener surfaces before caller or service changes.",
            "Approve Guardian-wrapped send-path design before any send-capable surface is allowed to run.",
            "Approve retirement only after static dependencies and rollback are proven.",
        ],
        "next_safe_move": "Active Machinery Quarantine Decision Packet v0",
        "source_disposition_counts": disposition.get("counts", {}).get("by_high_risk_disposition", {}),
    }


def format_operator_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Active Machinery High-Risk Quarantine Warnings v0",
        "",
        "Status:",
        "- Warning only: `true`.",
        "- Runtime changed: `false`.",
        "- Files moved or deleted: `false`.",
        "- Services disabled: `false`.",
        "- Destructive quarantine allowed: `false`.",
        "",
        "## Summary",
        f"- High-risk live/script warnings: `{payload['counts']['high_risk_warning_count']}`.",
        f"- Test-only items kept out of runtime quarantine: `{payload['counts']['test_only_warning_count']}`.",
        f"- Static references represented: `{payload['counts']['static_reference_count']}`.",
        f"- Dispositions: `{payload['counts']['by_disposition']}`.",
        "",
        "## High-Risk Warning Surfaces",
        "| Surface | Disposition | Static refs | Why it matters |",
        "| --- | --- | ---: | --- |",
    ]
    for item in payload["high_risk_warnings"]:
        why = str(item.get("why_it_matters") or "").replace("|", "/")
        lines.append(
            f"| `{item['relative_path']}` | `{item['disposition']}` | {len(item['static_references'])} | {why} |"
        )

    lines.extend(
        [
            "",
            "## Test-Only Items",
        ]
    )
    for item in payload["test_only_items"]:
        lines.append(
            f"- `{item['relative_path']}` stays `keep_test_only`; it is not treated as live runtime machinery."
        )

    lines.extend(
        [
            "",
            "## Static References Already Captured",
        ]
    )
    for finding in payload["static_reference_findings"]:
        lines.append(f"- {finding}")

    lines.extend(
        [
            "",
            "## What Did Not Happen",
            "- No services were disabled.",
            "- No files were moved, deleted, renamed, or chmodded.",
            "- No launchers or systemd templates were edited.",
            "- No agents, sends, daemons, or runtime activation were enabled.",
            "- Repo B was not executed.",
            "",
            "## Next Safe Move",
            f"- {payload['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def format_operator_review_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Active Machinery Quarantine Operator Review v0",
        "",
        "Status:",
        "- Review/read-model only: `true`.",
        "- Runtime changed: `false`.",
        "- Files moved or deleted: `false`.",
        "- Services disabled: `false`.",
        "- No blocking, wrapping, replacement, retirement, or caller switch happened.",
        "",
        "## Summary",
        f"- High-risk live/script items: `{payload['counts']['total_high_risk_live_script_items']}`.",
        f"- Block later: `{payload['counts']['block_later']}`.",
        f"- Replace with governed path: `{payload['counts']['replace_with_governed_path']}`.",
        f"- Wrap with Guardian: `{payload['counts']['wrap_with_guardian']}`.",
        f"- Retire later: `{payload['counts']['retire_later']}`.",
        f"- Keep for now / current dependency: `{payload['counts']['keep_for_now_current_dependency']}`.",
        f"- Needs operator decision: `{payload['counts']['needs_operator_decision']}`.",
        "",
    ]
    for group_id, display_name in REVIEW_GROUPS:
        group = payload["review_groups"][group_id]
        lines.extend([f"## {display_name}", f"Count: `{group['count']}`.", ""])
        if not group["items"]:
            if group_id == "keep_for_now_current_dependency":
                lines.append("No high-risk live/script item is recommended to stay as-is. Physically leave all files untouched until a separate approved lane acts.")
            else:
                lines.append("No items in this bucket.")
            lines.append("")
            continue
        for item in group["items"]:
            blocks = [name for name, blocked in item["blocks"].items() if blocked]
            refs = item["current_static_references"] or ["no static reference captured in the warning packet"]
            lines.extend(
                [
                    f"### `{item['relative_path']}`",
                    f"- What it is: {item['what_it_is']}.",
                    f"- Why it matters: {item['why_it_matters']}",
                    f"- Current risk: `{item['current_risk']}`.",
                    f"- Static references/dependencies: {'; '.join(refs)}.",
                    f"- Recommended future action: {item['recommended_future_action']}",
                    f"- Prove before acting: {item['what_must_be_proven_before_acting']}",
                    f"- Blocks/affects: {', '.join(blocks) if blocks else 'none flagged'}.",
                    "",
                ]
            )

    lines.extend(
        [
            "## Operator Decisions Needed",
            *[f"- {decision}" for decision in payload["operator_decisions_needed"]],
            "",
            "## What Did Not Happen",
            "- No high-risk scripts were executed.",
            "- Repo B was not run.",
            "- Runtime behavior did not change.",
            "- Services, files, launchers, and permissions were left untouched.",
            "- Agents, sends, and daemons were not enabled.",
            "",
            "## Next Safe Move",
            f"- {payload['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_quarantine_read_model(
    *,
    disposition_path: str | Path = DEFAULT_DISPOSITION_PATH,
    ready_packet_path: str | Path = DEFAULT_READY_PACKET_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_quarantine_payload(
        disposition_path=disposition_path,
        ready_packet_path=ready_packet_path,
        generated_at=generated_at,
    )
    root = rooted(read_model_root)
    json_path = root / "active_machinery_high_risk_quarantine.json"
    operator_path = root / OPERATOR_EXPORT_NAME
    written_json = write_json(json_path, payload)
    written_operator = write_text(operator_path, format_operator_packet(payload))
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_json_path": written_json,
        "read_model_operator_path": written_operator,
        "high_risk_warning_count": payload["counts"]["high_risk_warning_count"],
        "static_reference_count": payload["counts"]["static_reference_count"],
        "warning_only": True,
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "services_disabled": False,
        "destructive_quarantine_allowed": False,
        "next_recommended_lane": payload["next_safe_move"],
    }


def export_operator_review(
    *,
    quarantine_path: str | Path = DEFAULT_READ_MODEL_ROOT / "active_machinery_high_risk_quarantine.json",
    disposition_path: str | Path = DEFAULT_DISPOSITION_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_operator_review_payload(
        quarantine_path=quarantine_path,
        disposition_path=disposition_path,
        generated_at=generated_at,
    )
    root = rooted(read_model_root)
    json_path = root / "active_machinery_quarantine_operator_review.json"
    operator_path = root / REVIEW_OPERATOR_EXPORT_NAME
    written_json = write_json(json_path, payload)
    written_operator = write_text(operator_path, format_operator_review_packet(payload))
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "read_model_json_path": written_json,
        "read_model_operator_path": written_operator,
        "counts": payload["counts"],
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "services_disabled": False,
        "next_recommended_lane": payload["next_safe_move"],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export high-risk active machinery quarantine warnings.")
    parser.add_argument("--disposition-path", default=DEFAULT_DISPOSITION_PATH.as_posix())
    parser.add_argument("--ready-packet-path", default=DEFAULT_READY_PACKET_PATH.as_posix())
    parser.add_argument(
        "--quarantine-path",
        default=(DEFAULT_READ_MODEL_ROOT / "active_machinery_high_risk_quarantine.json").as_posix(),
    )
    parser.add_argument("--read-model-root", default=DEFAULT_READ_MODEL_ROOT.as_posix())
    parser.add_argument("--packet", choices=("quarantine", "operator-review"), default="quarantine")
    parser.add_argument("--format", choices=("json", "operator"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.packet == "operator-review":
        summary = export_operator_review(
            quarantine_path=args.quarantine_path,
            disposition_path=args.disposition_path,
            read_model_root=args.read_model_root,
        )
        if args.format == "operator":
            payload = load_json(Path(args.read_model_root) / "active_machinery_quarantine_operator_review.json")
            print(format_operator_review_packet(payload), end="")
        else:
            print(stable_json(summary), end="")
        return 0

    summary = export_quarantine_read_model(
        disposition_path=args.disposition_path,
        ready_packet_path=args.ready_packet_path,
        read_model_root=args.read_model_root,
    )
    if args.format == "operator":
        payload = load_json(Path(args.read_model_root) / "active_machinery_high_risk_quarantine.json")
        print(format_operator_packet(payload), end="")
    else:
        print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
