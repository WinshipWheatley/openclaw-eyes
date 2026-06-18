"""Build operator disposition packets for active machinery findings.

This module consumes the active-machinery Gemini verification read-model and
assigns review-only dispositions. It does not execute candidate machinery,
inspect source bodies, bind findings to modules/nodes, or change runtime state.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "active_machinery_operator_disposition_v0"
DEFAULT_VERIFICATION_PATH = Path("generated/read_models/active_machinery_gemini_verification.json")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_DOC_PATH = Path("docs/operations/ACTIVE_MACHINERY_OPERATOR_DISPOSITION_V0.md")

ALLOWED_DISPOSITIONS = {
    "keep_canonical",
    "keep_test_only",
    "keep_reference_only",
    "wrap_with_guardian",
    "replace_with_governed_path",
    "block_no_go",
    "retire_later",
    "operator_decision_required",
}

HIGH_RISK_OVERRIDES = {
    "builder_watcher.sh": {
        "disposition": "block_no_go",
        "why": "Verified watcher/daemon signals on a builder surface; legacy watchdog-style build loops should not run outside a governed Operator Action packet.",
        "before_run": "Replace with Work Board / Operator Action handoff and prove bounded receipts; do not run as a watcher.",
    },
    "cassandra_listener.py": {
        "disposition": "replace_with_governed_path",
        "why": "Verified listener signals on Cassandra intake; current direction is governed intake plus Work Board projection, not an ungated listener.",
        "before_run": "Route through governed intake, Operator Action, and Guardian/HITL receipts before any live listener use.",
    },
    "cassandra_watcher.py": {
        "disposition": "retire_later",
        "why": "Verified watcher/listener signals on a Cassandra surface; likely superseded by governed intake and read-model flows.",
        "before_run": "Prove it is still needed; otherwise retire after equivalent governed path is confirmed.",
    },
    "chief_brainstorm_watcher.py": {
        "disposition": "retire_later",
        "why": "Verified watcher/state-mutator signals on a Chief brainstorming surface; not on the current canonical authority path.",
        "before_run": "Keep disabled until an operator-approved use case proves it should become a governed Work Board source.",
    },
    "chief_email_brain.py": {
        "disposition": "wrap_with_guardian",
        "why": "Verified send/API signals on an email capability; external communication must remain draft/review-only until explicitly approved.",
        "before_run": "Require immutable approved packet, no-send default, and Guardian receipt before any external send behavior.",
    },
    "chief_guardian_listener.py": {
        "disposition": "replace_with_governed_path",
        "why": "Verified listener plus approval/HITL signals on legacy Guardian machinery; canonical direction is SQLite Operator Action / Guardian contract.",
        "before_run": "Use SQLite-backed Operator Action/HITL surfaces; keep legacy listener compatibility-only until replacement proof exists.",
    },
    "chief_guardian_sender.py": {
        "disposition": "wrap_with_guardian",
        "why": "Verified send/API plus Guardian signals; any notification/sender path needs explicit approval boundaries.",
        "before_run": "Allow only approved notification packets and receipts; no raw or freeform send authority.",
    },
    "chief_listener.py": {
        "disposition": "replace_with_governed_path",
        "why": "Verified central listener signals; current Chief direction is deterministic control-plane over governed intake, not autonomous listener authority.",
        "before_run": "Prove caller scope, HITL boundary, and receipt path before live listener activation.",
    },
    "chief_sender.py": {
        "disposition": "wrap_with_guardian",
        "why": "Verified send/API signals on a sender surface; external sends require Guardian/operator approval.",
        "before_run": "Require approved immutable packet, recipient binding, no raw command text, and receipt proof.",
    },
    "chief_watcher_brain.py": {
        "disposition": "block_no_go",
        "why": "Verified watcher plus shell/process signals; this is too risky to run as active machinery without a replacement contract.",
        "before_run": "Replace with bounded Work Board / Operator Action workflow; do not run watcher/process behavior directly.",
    },
    "producer_listener.py": {
        "disposition": "replace_with_governed_path",
        "why": "Verified listener/scheduler/send signals on Producer/Niles-adjacent machinery; not ready as autonomous runtime.",
        "before_run": "Define Producer/Niles module boundary and route actions through Guardian/HITL before activation.",
    },
    "retry_send_demo_dashboard.sh": {
        "disposition": "keep_reference_only",
        "why": "Retired from the runtime root after the demo sender was replaced by review-only proof artifacts; stale scan rows are historical evidence only.",
        "before_run": "Do not run. Restore only through a new no-send review fixture or an explicitly approved bounded demo packet.",
    },
    "scripts/run_producer_listener.sh": {
        "disposition": "block_no_go",
        "why": "Verified launcher for listener machinery; shell launchers should not activate daemons outside governed runtime approval.",
        "before_run": "Do not run until Producer listener has a governed contract and operator-approved activation lane.",
    },
    "send_demo_dashboard.py": {
        "disposition": "keep_reference_only",
        "why": "Retired from the runtime root because it was a one-off external-send demo surface; stale scan rows are historical evidence only.",
        "before_run": "Do not run. Restore only through a new no-send review fixture or an explicitly approved bounded demo packet.",
    },
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


def _is_test_path(relative_path: str) -> bool:
    return relative_path.startswith("tests/") or "/tests/" in relative_path


def affected_domains(relative_path: str, signal_groups: list[str]) -> list[str]:
    lowered = relative_path.lower()
    domains: set[str] = set()
    if "cassandra" in lowered:
        domains.add("Cassandra")
    if "chief" in lowered:
        domains.add("Chief")
    if any(part in lowered for part in ("guardian", "hitl", "approval")) or "approval_hitl" in signal_groups:
        domains.add("Guardian/HITL")
    if any(part in lowered for part in ("producer", "niles", "album")):
        domains.add("Producer/Niles")
    if any(part in lowered for part in ("sync", "mirror", "shuttle")) or "sync_bridge" in signal_groups:
        domains.add("sync")
    if any(part in lowered for part in ("send", "email", "gmail", "smtp")) or "send_external_api" in signal_groups:
        domains.add("send paths")
    if "builder" in lowered:
        domains.add("remote builder")
    return sorted(domains) or ["general machinery review"]


def static_capabilities(item: dict[str, Any]) -> dict[str, Any]:
    signals = set(item.get("signal_groups") or [])
    reads: list[str] = []
    writes: list[str] = []
    executes: list[str] = []
    sends: list[str] = []

    if signals & {"importer_exporter", "sync_bridge"}:
        reads.append("safe static signals indicate local file/generated read-model metadata access")
    if signals & {"approval_hitl"}:
        reads.append("safe static signals indicate approval/HITL state references")
    if signals & {"mcp_tool_plugin_surface"}:
        reads.append("safe static signals indicate tool/plugin metadata references")
    if signals & {"state_mutator"}:
        writes.append("safe static signals indicate local state or generated artifact mutation")
    if signals & {"importer_exporter", "sync_bridge"}:
        writes.append("safe static signals indicate importer/exporter or sync output behavior")
    if signals & {"daemon_listener", "path_daemon_listener_hint", "scheduler_watchdog"}:
        executes.append("safe static signals indicate listener/watcher/scheduler runtime behavior")
    if signals & {"shell_or_process"}:
        executes.append("safe static signals indicate shell/process execution risk")
    if signals & {"send_external_api", "path_send_api_hint"} or item.get("sends_external") not in {None, "", "none", "no"}:
        sends.append("safe static signals indicate external send/API posture")

    return {
        "reads": reads or ["no read capability proven from safe static signals"],
        "writes": writes or ["no write capability proven from safe static signals"],
        "executes": executes or ["no execution capability proven from safe static signals"],
        "sends": sends or ["no external send capability proven from safe static signals"],
        "static_evidence_basis": "active_machinery_gemini_verification signal groups from safe shard headers",
    }


def disposition_for_high_risk(item: dict[str, Any]) -> dict[str, str | bool]:
    relative_path = item["relative_path"]
    if _is_test_path(relative_path):
        return {
            "disposition": "keep_test_only",
            "why": "The file is under tests/; treat it as test-only unless a later audit proves it exposes a live unsafe path.",
            "before_run": "Run only as a focused test under normal test validation; never treat it as runtime machinery.",
            "operator_decision_required": False,
        }
    override = HIGH_RISK_OVERRIDES.get(relative_path)
    if override:
        return {
            "disposition": override["disposition"],
            "why": override["why"],
            "before_run": override["before_run"],
            "operator_decision_required": override["disposition"] in {
                "wrap_with_guardian",
                "replace_with_governed_path",
                "retire_later",
            },
        }
    signals = set(item.get("signal_groups") or [])
    if "send_external_api" in signals or "path_send_api_hint" in signals:
        return {
            "disposition": "wrap_with_guardian",
            "why": "The surface has send/API signals and must not gain external authority without Guardian/operator approval.",
            "before_run": "Require immutable approved packet, exact recipient/action binding, and receipt proof.",
            "operator_decision_required": True,
        }
    if "daemon_listener" in signals or "path_daemon_listener_hint" in signals:
        return {
            "disposition": "replace_with_governed_path",
            "why": "The surface has daemon/listener signals and should route through governed intake/runtime boundaries.",
            "before_run": "Prove bounded activation, HITL posture, and receipts before any runtime use.",
            "operator_decision_required": True,
        }
    return {
        "disposition": "operator_decision_required",
        "why": "The verified high-risk signals need operator disposition before any runtime use.",
        "before_run": "Operator must approve a specific bounded lane before this can run.",
        "operator_decision_required": True,
    }


def build_high_risk_dispositions(verification: dict[str, Any]) -> list[dict[str, Any]]:
    rows = verification["groups"]["verified_high_risk_active_machinery"]["items"]
    dispositions: list[dict[str, Any]] = []
    for item in rows:
        decision = disposition_for_high_risk(item)
        disposition = str(decision["disposition"])
        if disposition not in ALLOWED_DISPOSITIONS:
            raise ValueError(f"invalid disposition for {item['relative_path']}: {disposition}")
        capabilities = static_capabilities(item)
        dispositions.append(
            {
                "relative_path": item["relative_path"],
                "repo_root": item.get("repo_root"),
                "repo_role": item.get("repo_role"),
                "is_test_only": _is_test_path(item["relative_path"]),
                "machinery_type": item.get("machinery_type"),
                "verification_status": item.get("verification_status"),
                "current_authority_risk": item.get("authority_risk"),
                "signal_groups": item.get("signal_groups") or [],
                "why_it_matters": decision["why"],
                "static_capabilities": capabilities,
                "recommended_disposition": disposition,
                "what_must_happen_before_it_can_run": decision["before_run"],
                "operator_decision_required": bool(decision["operator_decision_required"]),
                "affected_domains": affected_domains(item["relative_path"], item.get("signal_groups") or []),
            }
        )
    return dispositions


def major_group_dispositions(verification: dict[str, Any]) -> list[dict[str, Any]]:
    groups = verification["groups"]
    return [
        {
            "group_id": "verified_high_risk_active_machinery",
            "display_name": "Verified high-risk active machinery",
            "count": groups["verified_high_risk_active_machinery"]["count"],
            "recommended_disposition": "operator_decision_required",
            "why_it_matters": "These rows have deterministic high-risk static signals and should be reviewed item-by-item before any runtime activation.",
            "next_action": "Use the high-risk item table; tests stay test-only, live listeners/senders need governed replacement or Guardian wrapping.",
        },
        {
            "group_id": "likely_active_machinery_needing_operator_review",
            "display_name": "Likely active machinery needing operator review",
            "count": groups["likely_active_machinery_needing_operator_review"]["count"],
            "recommended_disposition": "operator_decision_required",
            "why_it_matters": "These rows have active-machinery hypotheses but not enough deterministic evidence to assign final authority fate.",
            "next_action": "Run a later no-execution static review lane by subgroup: HITL, sync, importer/exporter, and plugin/tool surfaces.",
        },
        {
            "group_id": "false_positives_safe_docs_generated_files",
            "display_name": "False positives / safe docs and generated files",
            "count": groups["false_positives_safe_docs_generated_files"]["count"],
            "recommended_disposition": "keep_canonical",
            "why_it_matters": "Docs and generated read-models mention machinery terms but are not runtime machinery.",
            "next_action": "Keep as documentation/generated artifacts unless a future lane proves a specific file is executable.",
        },
        {
            "group_id": "repo_b_reference_only_machinery",
            "display_name": "Repo B reference-only machinery",
            "count": groups["repo_b_reference_only_machinery"]["count"],
            "recommended_disposition": "keep_reference_only",
            "why_it_matters": "Repo B is pre-split capability-tree evidence, not current runtime authority.",
            "next_action": "Inspect only as reference in explicit reconciliation lanes; never execute Repo B code.",
        },
        {
            "group_id": "send_api_surfaces",
            "display_name": "Send/API surfaces",
            "count": groups["send_api_surfaces"]["count"],
            "recommended_disposition": "wrap_with_guardian",
            "why_it_matters": "External send/API paths can affect real recipients or services if activated.",
            "next_action": "Keep no-send by default; require immutable packet, exact binding, Guardian approval, and receipts.",
        },
        {
            "group_id": "sync_bridge_surfaces",
            "display_name": "Sync/bridge surfaces",
            "count": groups["sync_bridge_surfaces"]["count"],
            "recommended_disposition": "operator_decision_required",
            "why_it_matters": "Sync/bridge surfaces can move generated state between PC/Mac or read-model boundaries.",
            "next_action": "Review safe canonical sync paths separately from launchers/watchers before any activation.",
        },
        {
            "group_id": "approval_hitl_surfaces",
            "display_name": "Approval/HITL surfaces",
            "count": groups["approval_hitl_surfaces"]["count"],
            "recommended_disposition": "replace_with_governed_path",
            "why_it_matters": "Approval/HITL surfaces affect authority and must converge on SQLite Operator Action / Guardian contract.",
            "next_action": "Reconcile legacy paths against current Guardian/HITL contract before any caller switch.",
        },
        {
            "group_id": "unknown_needs_deeper_review",
            "display_name": "Unknown / needs deeper review",
            "count": groups["unknown_needs_deeper_review"]["count"],
            "recommended_disposition": "operator_decision_required",
            "why_it_matters": "These rows have insufficient static evidence for a final disposition.",
            "next_action": "Leave untouched until a narrower static review lane is approved.",
        },
    ]


def build_disposition_payload(
    *,
    verification_path: str | Path = DEFAULT_VERIFICATION_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    verification = load_json(verification_path)
    high_risk = build_high_risk_dispositions(verification)
    group_rows = major_group_dispositions(verification)
    by_disposition = Counter(item["recommended_disposition"] for item in high_risk)
    affected = Counter(domain for item in high_risk for domain in item["affected_domains"])
    test_only_count = sum(1 for item in high_risk if item["is_test_only"])
    live_count = len(high_risk) - test_only_count
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "mode": "operator_disposition_review_only",
        "source_verification_path": display_path(rooted(verification_path)),
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "repo_b_executed": False,
        "scripts_executed": False,
        "agents_enabled": False,
        "sends_enabled": False,
        "daemons_enabled": False,
        "gemini_output_treated_as_truth": False,
        "module_registry_bound": False,
        "openclaw_nodes_bound": False,
        "counts": {
            "high_risk_items": len(high_risk),
            "high_risk_test_only_items": test_only_count,
            "high_risk_live_or_script_items": live_count,
            "major_groups": len(group_rows),
            "by_high_risk_disposition": dict(sorted(by_disposition.items())),
            "by_affected_domain": dict(sorted(affected.items())),
        },
        "high_risk_dispositions": high_risk,
        "major_machinery_group_dispositions": group_rows,
        "operator_decisions_needed": [
            "Approve which legacy listener/watcher surfaces should be replaced, retired, or blocked.",
            "Approve whether any send/API surface should receive a Guardian-wrapped no-send-to-send transition lane.",
            "Approve a separate sync/bridge disposition lane before any launcher or watcher is activated.",
            "Approve HITL surface convergence before any caller switch or old JSON retirement.",
        ],
        "next_safe_move": "Active Machinery High-Risk Quarantine Spec v0",
    }


def _brief_capabilities(capabilities: dict[str, Any]) -> str:
    parts = []
    for key in ("reads", "writes", "executes", "sends"):
        values = capabilities.get(key) or []
        parts.append(f"{key}: {values[0] if values else 'none proven'}")
    return "; ".join(parts)


def format_operator_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Active Machinery Operator Disposition v0",
        "",
        "Status:",
        "- Runtime changed: `false`.",
        "- Files moved or deleted: `false`.",
        "- Repo B executed: `false`.",
        "- Gemini output treated as truth: `false`.",
        "",
        "## Summary",
        f"- High-risk items reviewed: `{payload['counts']['high_risk_items']}`.",
        f"- Test-only high-risk items: `{payload['counts']['high_risk_test_only_items']}`.",
        f"- Live/script high-risk items: `{payload['counts']['high_risk_live_or_script_items']}`.",
        f"- Dispositions: `{payload['counts']['by_high_risk_disposition']}`.",
        "",
        "## High-Risk Item Dispositions",
    ]
    for item in payload["high_risk_dispositions"]:
        lines.extend(
            [
                f"### `{item['relative_path']}`",
                f"- Disposition: `{item['recommended_disposition']}`.",
                f"- Risk: `{item['current_authority_risk']}`; type: `{item['machinery_type']}`.",
                f"- Affects: {', '.join(item['affected_domains'])}.",
                f"- Why it matters: {item['why_it_matters']}",
                f"- Static evidence: {', '.join(item['signal_groups'])}.",
                f"- Capability posture: {_brief_capabilities(item['static_capabilities'])}.",
                f"- Before it can run: {item['what_must_happen_before_it_can_run']}",
                "",
            ]
        )

    lines.extend(["## Major Machinery Groups"])
    for group in payload["major_machinery_group_dispositions"]:
        lines.extend(
            [
                f"- `{group['group_id']}` ({group['count']}): `{group['recommended_disposition']}` - {group['next_action']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Operator Decisions Needed",
            *[f"- {decision}" for decision in payload["operator_decisions_needed"]],
            "",
            "## Next Safe Move",
            f"- {payload['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def format_doc(payload: dict[str, Any]) -> str:
    lines = [
        "# Active Machinery Operator Disposition v0",
        "",
        "This is a review-only disposition packet for verified active-machinery findings. It does not modify runtime behavior, move files, delete files, enable sends, enable daemons, or bind findings to `module_registry` / `openclaw_nodes`.",
        "",
        "## Disposition Vocabulary",
        "- `keep_canonical`: keep as canonical docs/generated/read-model/support surface.",
        "- `keep_test_only`: keep as test-only; do not treat as runtime machinery.",
        "- `keep_reference_only`: keep as reference, not authority.",
        "- `wrap_with_guardian`: may only run behind immutable Operator Action / Guardian approval and receipts.",
        "- `replace_with_governed_path`: legacy runtime shape should be replaced by current governed substrate.",
        "- `block_no_go`: do not run; needs explicit replacement or operator exception.",
        "- `retire_later`: likely superseded, but do not delete until replacement proof exists.",
        "- `operator_decision_required`: insufficient evidence or high consequence; decide later.",
        "",
        "## High-Risk Disposition Table",
        "| File | Disposition | Affects | What must happen before it can run |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload["high_risk_dispositions"]:
        domains = ", ".join(item["affected_domains"])
        before = item["what_must_happen_before_it_can_run"].replace("|", "/")
        lines.append(
            f"| `{item['relative_path']}` | `{item['recommended_disposition']}` | {domains} | {before} |"
        )
    lines.extend(
        [
            "",
            "## Major Group Disposition",
            "| Group | Count | Disposition | Next action |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for group in payload["major_machinery_group_dispositions"]:
        lines.append(
            f"| {group['display_name']} | {group['count']} | `{group['recommended_disposition']}` | {group['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries Preserved",
            "- Runtime changed: `false`.",
            "- Files moved or deleted: `false`.",
            "- Repo B executed: `false`.",
            "- Agents/sends/daemons enabled: `false`.",
            "- Gemini output treated as truth: `false`.",
            "",
            "## Next Recommended Lane",
            payload["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def run_disposition(
    *,
    verification_path: str | Path = DEFAULT_VERIFICATION_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    doc_path: str | Path = DEFAULT_DOC_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_disposition_payload(
        verification_path=verification_path,
        generated_at=generated_at,
    )
    read_root = rooted(read_model_root)
    json_path = read_root / "active_machinery_operator_disposition.json"
    operator_path = read_root / "active_machinery_operator_disposition_OPERATOR.md"
    written_json = write_json(json_path, payload)
    written_operator = write_text(operator_path, format_operator_packet(payload))
    written_doc = write_text(doc_path, format_doc(payload))
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_json_path": written_json,
        "read_model_operator_path": written_operator,
        "doc_path": written_doc,
        "high_risk_items": payload["counts"]["high_risk_items"],
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "repo_b_executed": False,
        "next_recommended_lane": payload["next_safe_move"],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build active machinery operator disposition packet.")
    parser.add_argument("--verification-path", default=DEFAULT_VERIFICATION_PATH.as_posix())
    parser.add_argument("--read-model-root", default=DEFAULT_READ_MODEL_ROOT.as_posix())
    parser.add_argument("--doc-path", default=DEFAULT_DOC_PATH.as_posix())
    parser.add_argument("--format", choices=("json", "operator"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = run_disposition(
        verification_path=args.verification_path,
        read_model_root=args.read_model_root,
        doc_path=args.doc_path,
    )
    if args.format == "operator":
        payload = load_json(Path(args.read_model_root) / "active_machinery_operator_disposition.json")
        print(format_operator_packet(payload), end="")
    else:
        print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
