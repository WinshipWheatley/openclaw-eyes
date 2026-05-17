"""Verify Gemini active-machinery classifications against safe shard metadata.

Gemini output is treated as low-confidence hypothesis input. This verifier
reconciles each row back to the original shard metadata and uses only safe
header excerpts already present in the shard packets for deterministic checks.
It does not execute code, import discovered modules, inspect private roots, or
read candidate file bodies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "active_machinery_gemini_verification_v0"
DEFAULT_AUDIT_ROOT = Path("generated/audit_shards/active_machinery_v0")
DEFAULT_SHARD_ROOT = DEFAULT_AUDIT_ROOT / "shards"
DEFAULT_WORKER_OUTPUT_PATH = DEFAULT_AUDIT_ROOT / "mock_worker_outputs/full_classification.json"
DEFAULT_DRY_RUN_PATH = DEFAULT_AUDIT_ROOT / "privacy_inclusion_dry_run.json"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_DOC_PATH = Path("docs/operations/ACTIVE_MACHINERY_GEMINI_VERIFICATION_V0.md")

ACTIVE_MACHINERY_TYPES = {
    "daemon_listener",
    "scheduler_watchdog",
    "sync_bridge",
    "importer_exporter",
    "approval_hitl",
    "send_external_api",
    "mcp_tool_plugin_surface",
    "state_mutator",
}

HIGH_RISK_TYPES = {
    "daemon_listener",
    "scheduler_watchdog",
    "approval_hitl",
    "send_external_api",
    "state_mutator",
}

GROUP_ORDER = (
    "verified_high_risk_active_machinery",
    "likely_active_machinery_needing_operator_review",
    "false_positives_safe_docs_generated_files",
    "repo_b_reference_only_machinery",
    "send_api_surfaces",
    "sync_bridge_surfaces",
    "approval_hitl_surfaces",
    "unknown_needs_deeper_review",
)

GROUP_TITLES = {
    "verified_high_risk_active_machinery": "Verified High-Risk Active Machinery",
    "likely_active_machinery_needing_operator_review": "Likely Active Machinery Needing Operator Review",
    "false_positives_safe_docs_generated_files": "False Positives / Safe Docs And Generated Files",
    "repo_b_reference_only_machinery": "Repo B Reference-Only Machinery",
    "send_api_surfaces": "Send/API Surfaces",
    "sync_bridge_surfaces": "Sync/Bridge Surfaces",
    "approval_hitl_surfaces": "Approval/HITL Surfaces",
    "unknown_needs_deeper_review": "Unknown / Needs Deeper Review",
}

SIGNAL_TERMS = {
    "daemon_listener": (
        "listener",
        "while true",
        "while 1",
        "run_forever",
        "poll",
        "polling",
        "listen",
        "watch",
        "watcher",
        "daemon",
        "asyncio.run",
    ),
    "scheduler_watchdog": (
        "schedule",
        "scheduler",
        "watchdog",
        "cron",
        "sleep(",
        "timer",
    ),
    "sync_bridge": (
        "sync",
        "mirror",
        "shuttle",
        "manifest",
        "import task",
        "export_read_model",
        "read_model",
    ),
    "importer_exporter": (
        "import",
        "export",
        "write_json",
        "write_text",
        "read_model",
        "generated/",
        "json.dump",
    ),
    "approval_hitl": (
        "hitl",
        "approval",
        "guardian",
        "operator_action",
        "pending action",
        "approval_id",
    ),
    "send_external_api": (
        "send_message",
        "send_email",
        "gmail",
        "smtp",
        "smtplib",
        "telegram",
        "requests.",
        "urllib",
        "httpx",
        "portal",
        "coupa",
        "network",
    ),
    "mcp_tool_plugin_surface": (
        "mcp",
        "plugin",
        "tool",
        "connector",
    ),
    "state_mutator": (
        "insert into",
        "update ",
        "delete from",
        "create table",
        "sqlite",
        "write_text",
        "write_bytes",
        "json.dump",
        ".write(",
    ),
    "shell_or_process": (
        "subprocess",
        "os.system",
        "popen",
        "shell=true",
        "exec(",
        "eval(",
    ),
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


def load_json_object(path: str | Path) -> dict[str, Any]:
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


def load_shard_index(shard_root: str | Path = DEFAULT_SHARD_ROOT) -> dict[str, dict[str, Any]]:
    root = rooted(shard_root)
    if not root.is_dir():
        raise FileNotFoundError(f"missing shard directory: {display_path(root)}")
    index: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("active_machinery_v0_shard_*.json"), key=lambda item: item.name):
        shard = load_json_object(path)
        shard_id = str(shard.get("shard_id") or path.stem)
        for item in shard.get("items", []):
            if not isinstance(item, dict):
                continue
            relative_path = str(item.get("relative_path") or "").strip()
            if not relative_path:
                continue
            index[relative_path] = {
                **item,
                "shard_id": shard_id,
                "shard_path": display_path(path),
            }
    return index


def load_reference_only_rows(dry_run_path: str | Path = DEFAULT_DRY_RUN_PATH) -> list[dict[str, Any]]:
    target = rooted(dry_run_path)
    if not target.is_file():
        return []
    dry_run = load_json_object(target)
    rows: list[dict[str, Any]] = []
    for candidate in dry_run.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("eligibility") == "reference_only":
            rows.append(
                {
                    "repo_root": candidate.get("repo_root"),
                    "repo_role": candidate.get("repo_role"),
                    "relative_path": candidate.get("relative_path"),
                    "machinery_type": "legacy_reference_only",
                    "verification_status": "reference_only_not_runtime_verified",
                    "verification_basis": "privacy inclusion dry-run metadata",
                    "recommended_fate": "keep_reference_only",
                    "authority_risk": "high_if_executed",
                    "one_sentence_evidence": "Repo B is pre-split reference-only and was not header-read or executed.",
                }
            )
    return rows


def _unknownish(value: Any) -> bool:
    return value in (None, "", "unknown", "<copy>", "UNKNOWN")


def _lower_text(record: dict[str, Any]) -> str:
    return str(record.get("content_header_excerpt") or "").lower()


def _matched_terms(text: str, terms: Iterable[str]) -> list[str]:
    return sorted({term for term in terms if term in text})


def deterministic_signals(shard_record: dict[str, Any] | None) -> dict[str, Any]:
    if not shard_record:
        return {
            "source": "no_shard_record",
            "matched_signal_groups": [],
            "matched_terms": {},
            "header_lines_read": 0,
            "body_read_allowed": False,
        }

    text = _lower_text(shard_record)
    relative_path = str(shard_record.get("relative_path") or "").lower()
    matched: dict[str, list[str]] = {}
    for group, terms in SIGNAL_TERMS.items():
        found = _matched_terms(text, terms)
        if found:
            matched[group] = found

    path_groups = []
    if relative_path.startswith("generated/read_models/"):
        path_groups.append("generated_read_model_artifact")
    if relative_path.startswith("docs/") or relative_path.endswith(".md"):
        path_groups.append("documentation")
    if "listener" in relative_path or "watcher" in relative_path or "worker" in relative_path:
        path_groups.append("path_daemon_listener_hint")
    if "approval" in relative_path or "hitl" in relative_path or "guardian" in relative_path:
        path_groups.append("path_approval_hitl_hint")
    if "sync" in relative_path or "mirror" in relative_path or "shuttle" in relative_path:
        path_groups.append("path_sync_bridge_hint")
    if "send" in relative_path or "email" in relative_path or "gmail" in relative_path:
        path_groups.append("path_send_api_hint")

    return {
        "source": "safe_shard_header_excerpt",
        "matched_signal_groups": sorted(set(matched) | set(path_groups)),
        "matched_terms": matched,
        "header_lines_read": int(shard_record.get("header_lines_read") or 0),
        "body_read_allowed": bool(shard_record.get("body_read_allowed")),
        "no_execution": bool(shard_record.get("no_execution")),
    }


def _has_signal(signals: dict[str, Any], machinery_type: str) -> bool:
    groups = set(signals.get("matched_signal_groups") or [])
    if machinery_type in groups:
        return True
    if machinery_type == "daemon_listener":
        return bool(groups & {"path_daemon_listener_hint", "daemon_listener", "scheduler_watchdog"})
    if machinery_type == "approval_hitl":
        return bool(groups & {"path_approval_hitl_hint", "approval_hitl"})
    if machinery_type == "send_external_api":
        return bool(groups & {"path_send_api_hint", "send_external_api"})
    if machinery_type == "sync_bridge":
        return bool(groups & {"path_sync_bridge_hint", "sync_bridge"})
    if machinery_type == "state_mutator":
        return "state_mutator" in groups
    if machinery_type == "importer_exporter":
        return "importer_exporter" in groups
    if machinery_type == "scheduler_watchdog":
        return bool(groups & {"scheduler_watchdog", "path_daemon_listener_hint"})
    if machinery_type == "mcp_tool_plugin_surface":
        return "mcp_tool_plugin_surface" in groups
    return bool(groups)


def _safe_doc_or_generated_path(relative_path: str, machinery_type: str) -> bool:
    return (
        machinery_type in {"canonical_doctrine_docs", "generated_read_model_artifact"}
        or relative_path.startswith("docs/")
        or relative_path.startswith("generated/read_models/")
        or relative_path.endswith(".md")
    )


def reconcile_worker_item(
    item: dict[str, Any],
    shard_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    relative_path = str(item.get("relative_path") or "").strip()
    shard_record = shard_index.get(relative_path)
    reconciled = dict(item)
    if shard_record:
        reconciled["repo_root"] = shard_record.get("repo_root")
        reconciled["repo_role"] = shard_record.get("repo_role")
        reconciled["shard_id"] = shard_record.get("shard_id")
        reconciled["source_role"] = shard_record.get("source_role")
        reconciled["source_category"] = shard_record.get("source_category")
        reconciled["reconciliation_status"] = "matched_shard_metadata"
    else:
        reconciled["repo_root"] = None if _unknownish(item.get("repo_root")) else item.get("repo_root")
        reconciled["repo_role"] = None if _unknownish(item.get("repo_role")) else item.get("repo_role")
        reconciled["shard_id"] = None
        reconciled["source_role"] = None
        reconciled["source_category"] = None
        reconciled["reconciliation_status"] = "missing_shard_metadata_operator_review"

    signals = deterministic_signals(shard_record)
    machinery_type = str(item.get("machinery_type") or "unknown_operator_review")
    authority_risk = str(item.get("authority_risk") or "unknown")
    sends_external = str(item.get("sends_external") or "unknown")
    repo_role = str(reconciled.get("repo_role") or "unknown")
    gemini_high_risk = authority_risk in {"high", "critical"}
    gemini_active_claim = item.get("is_active_machinery") is True or machinery_type in ACTIVE_MACHINERY_TYPES
    signal_match = _has_signal(signals, machinery_type)

    if repo_role == "pre_split_capability_tree_reference_only":
        verification_status = "reference_only_not_runtime_verified"
        primary_group = "repo_b_reference_only_machinery"
    elif _safe_doc_or_generated_path(relative_path, machinery_type):
        verification_status = "safe_doc_or_generated_false_positive"
        primary_group = "false_positives_safe_docs_generated_files"
    elif gemini_high_risk and gemini_active_claim and signal_match:
        verification_status = "deterministically_verified_from_safe_header"
        primary_group = "verified_high_risk_active_machinery"
    elif gemini_high_risk or (gemini_active_claim and machinery_type in HIGH_RISK_TYPES):
        verification_status = "hypothesis_needs_operator_review"
        primary_group = "likely_active_machinery_needing_operator_review"
    elif gemini_active_claim and signal_match:
        verification_status = "likely_active_from_safe_header_needs_review"
        primary_group = "likely_active_machinery_needing_operator_review"
    else:
        verification_status = "unknown_or_low_signal_needs_deeper_review"
        primary_group = "unknown_needs_deeper_review"

    surface_groups: list[str] = []
    if machinery_type == "send_external_api" or sends_external not in {"none", "no"}:
        surface_groups.append("send_api_surfaces")
    if machinery_type == "sync_bridge" or "sync_bridge" in signals.get("matched_signal_groups", []):
        surface_groups.append("sync_bridge_surfaces")
    if machinery_type == "approval_hitl" or "approval_hitl" in signals.get("matched_signal_groups", []):
        surface_groups.append("approval_hitl_surfaces")

    return {
        "repo_root": reconciled.get("repo_root"),
        "repo_role": reconciled.get("repo_role"),
        "relative_path": relative_path,
        "shard_id": reconciled.get("shard_id"),
        "source_role": reconciled.get("source_role"),
        "source_category": reconciled.get("source_category"),
        "reconciliation_status": reconciled["reconciliation_status"],
        "gemini_hypothesis": {
            "is_active_machinery": item.get("is_active_machinery"),
            "machinery_type": machinery_type,
            "source_fate": item.get("source_fate"),
            "reads": item.get("reads"),
            "writes": item.get("writes"),
            "executes": item.get("executes"),
            "sends_external": item.get("sends_external"),
            "touches_private_data": item.get("touches_private_data"),
            "authority_risk": authority_risk,
            "recommended_fate": item.get("recommended_fate"),
            "confidence": item.get("confidence"),
            "one_sentence_evidence": item.get("one_sentence_evidence"),
        },
        "deterministic_verification": {
            "verification_status": verification_status,
            "verified_as_high_risk_active_machinery": primary_group == "verified_high_risk_active_machinery",
            "gemini_output_treated_as_truth": False,
            "body_read_allowed": False,
            "signals": signals,
        },
        "primary_group": primary_group,
        "surface_groups": sorted(surface_groups),
    }


def _compact_item(item: dict[str, Any]) -> dict[str, Any]:
    hypothesis = item["gemini_hypothesis"]
    verification = item["deterministic_verification"]
    return {
        "repo_root": item.get("repo_root"),
        "repo_role": item.get("repo_role"),
        "relative_path": item["relative_path"],
        "shard_id": item.get("shard_id"),
        "reconciliation_status": item["reconciliation_status"],
        "machinery_type": hypothesis.get("machinery_type"),
        "authority_risk": hypothesis.get("authority_risk"),
        "sends_external": hypothesis.get("sends_external"),
        "verification_status": verification["verification_status"],
        "verified_as_high_risk_active_machinery": verification["verified_as_high_risk_active_machinery"],
        "signal_groups": verification["signals"].get("matched_signal_groups", []),
        "recommended_fate": hypothesis.get("recommended_fate"),
        "one_sentence_evidence": hypothesis.get("one_sentence_evidence"),
    }


def build_verification_payload(
    *,
    worker_output_path: str | Path = DEFAULT_WORKER_OUTPUT_PATH,
    shard_root: str | Path = DEFAULT_SHARD_ROOT,
    dry_run_path: str | Path = DEFAULT_DRY_RUN_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    worker = load_json_object(worker_output_path)
    shard_index = load_shard_index(shard_root)
    worker_items = [item for item in worker.get("items", []) if isinstance(item, dict)]
    reconciled = [reconcile_worker_item(item, shard_index) for item in worker_items]

    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in GROUP_ORDER}
    for item in reconciled:
        groups[item["primary_group"]].append(_compact_item(item))
        if item["primary_group"] not in {
            "false_positives_safe_docs_generated_files",
            "repo_b_reference_only_machinery",
        }:
            for group in item["surface_groups"]:
                groups[group].append(_compact_item(item))

    for row in load_reference_only_rows(dry_run_path):
        groups["repo_b_reference_only_machinery"].append(row)

    all_items_by_status = Counter(
        item["deterministic_verification"]["verification_status"] for item in reconciled
    )
    all_items_by_machinery_type = Counter(
        str(item["gemini_hypothesis"]["machinery_type"]) for item in reconciled
    )
    unreconciled_count = sum(
        1 for item in reconciled if item["reconciliation_status"] != "matched_shard_metadata"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "mode": "gemini_hypothesis_reconciliation_and_static_header_verification",
        "gemini_output_treated_as_truth": False,
        "classification_claims_final": False,
        "runtime_authority_changed": False,
        "sqlite_written": False,
        "llm_calls_made_by_codex": False,
        "api_calls_made_by_codex": False,
        "raw_private_content_read": False,
        "repo_b_executed": False,
        "no_code_execution": True,
        "source_files": {
            "worker_output_path": display_path(rooted(worker_output_path)),
            "shard_root": display_path(rooted(shard_root)),
            "dry_run_path": display_path(rooted(dry_run_path)),
        },
        "worker_output_summary": {
            "schema_version": worker.get("schema_version"),
            "worker_model": worker.get("worker_model"),
            "shard_id": worker.get("shard_id"),
            "worker_claimed_llm_or_worker_calls_made": worker.get("llm_or_worker_calls_made"),
            "worker_claimed_raw_private_content_read": worker.get("raw_private_content_read"),
            "worker_claimed_repo_b_executed": worker.get("repo_b_executed"),
            "item_count": len(worker_items),
        },
        "counts": {
            "worker_items": len(worker_items),
            "shard_items_indexed": len(shard_index),
            "reconciled_items": len(reconciled) - unreconciled_count,
            "unreconciled_items": unreconciled_count,
            "verified_high_risk_count": len(groups["verified_high_risk_active_machinery"]),
            "likely_active_needing_operator_review_count": len(
                groups["likely_active_machinery_needing_operator_review"]
            ),
            "false_positive_or_safe_artifact_count": len(
                groups["false_positives_safe_docs_generated_files"]
            ),
            "repo_b_reference_only_count": len(groups["repo_b_reference_only_machinery"]),
            "send_api_surface_count": len(groups["send_api_surfaces"]),
            "sync_bridge_surface_count": len(groups["sync_bridge_surfaces"]),
            "approval_hitl_surface_count": len(groups["approval_hitl_surfaces"]),
            "unknown_needs_deeper_review_count": len(groups["unknown_needs_deeper_review"]),
            "by_verification_status": dict(sorted(all_items_by_status.items())),
            "by_gemini_machinery_type": dict(sorted(all_items_by_machinery_type.items())),
        },
        "groups": {
            key: {
                "display_name": GROUP_TITLES[key],
                "count": len(groups[key]),
                "items": groups[key],
            }
            for key in GROUP_ORDER
        },
        "boundaries": {
            "repo_b_executed": False,
            "raw_private_content_read": False,
            "candidate_file_bodies_read": False,
            "code_executed": False,
            "subprocess_or_shell_used_by_verifier": False,
            "network_calls_made": False,
            "gemini_output_treated_as_truth": False,
            "module_registry_bound": False,
            "openclaw_nodes_bound": False,
        },
        "next_safe_move": "Operator reviews verified high-risk and likely active surfaces before any binding to modules, nodes, or authority state.",
    }


def _format_items(items: list[dict[str, Any]], *, limit: int = 25) -> list[str]:
    if not items:
        return ["- None."]
    lines = []
    for item in items[:limit]:
        path = item.get("relative_path")
        machinery_type = item.get("machinery_type", item.get("source_fate", "unknown"))
        status = item.get("verification_status", "reference_only")
        signals = ", ".join(item.get("signal_groups", [])[:5])
        detail = f"; signals: {signals}" if signals else ""
        lines.append(f"- `{path}` -> `{machinery_type}` / `{status}`{detail}")
    if len(items) > limit:
        lines.append(f"- ...{len(items) - limit} more omitted from this operator view.")
    return lines


def format_operator_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Active Machinery Gemini Verification v0",
        "",
        "Status:",
        "- Gemini output treated as truth: `false`.",
        f"- Worker rows reconciled: `{payload['counts']['reconciled_items']}`.",
        f"- Worker rows unreconciled: `{payload['counts']['unreconciled_items']}`.",
        f"- Verified high-risk rows: `{payload['counts']['verified_high_risk_count']}`.",
        f"- Likely active rows needing operator review: `{payload['counts']['likely_active_needing_operator_review_count']}`.",
        f"- False-positive or safe artifact rows: `{payload['counts']['false_positive_or_safe_artifact_count']}`.",
        f"- Repo B reference-only rows: `{payload['counts']['repo_b_reference_only_count']}`.",
        "",
        "## What This Means",
        "Gemini hypotheses were joined back to the original safe shard metadata. High-risk claims were only promoted when the safe header excerpt or path metadata had matching deterministic signals. Nothing was bound to modules, nodes, or authority state.",
        "",
    ]
    for group in GROUP_ORDER:
        section = payload["groups"][group]
        lines.append(f"## {section['display_name']}")
        lines.append(f"Count: `{section['count']}`")
        lines.extend(_format_items(section["items"]))
        lines.append("")

    lines.extend(
        [
            "## Boundaries",
            "- No code was executed.",
            "- No Repo B code was run.",
            "- No raw private/no-go content was read.",
            "- Gemini output remains hypothesis input, not truth.",
            "- No `openclaw_nodes` or `module_registry` binding was created.",
            "",
            "## Next Safe Move",
            f"{payload['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def format_doc(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        "# Active Machinery Gemini Verification v0",
        "",
        "This document records the deterministic verification pass over Gemini active-machinery classifications. The worker output is treated as low-confidence hypothesis input, not repository truth.",
        "",
        "## Method",
        "- Load Gemini `full_classification.json`.",
        "- Load the original active-machinery shard packets.",
        "- Reconcile rows by `relative_path` so `repo_root`, `repo_role`, source category, and shard ID come from the original safe shard metadata.",
        "- Verify high-risk hypotheses using only shard header excerpts, path metadata, and static text signals.",
        "- Keep Repo B as reference-only.",
        "- Do not bind results to `openclaw_nodes`, `module_registry`, runtime services, or authority state.",
        "",
        "## Counts",
        f"- Worker items: `{counts['worker_items']}`",
        f"- Reconciled items: `{counts['reconciled_items']}`",
        f"- Unreconciled items: `{counts['unreconciled_items']}`",
        f"- Verified high-risk active machinery: `{counts['verified_high_risk_count']}`",
        f"- Likely active machinery needing operator review: `{counts['likely_active_needing_operator_review_count']}`",
        f"- Send/API surfaces: `{counts['send_api_surface_count']}`",
        f"- Sync/bridge surfaces: `{counts['sync_bridge_surface_count']}`",
        f"- Approval/HITL surfaces: `{counts['approval_hitl_surface_count']}`",
        "",
        "## Verification Doctrine",
        "A Gemini high-risk claim is not confirmed unless the original shard metadata contains deterministic header/path signals consistent with the claim. Missing signals route the row to operator review.",
        "",
    ]
    for group in GROUP_ORDER:
        section = payload["groups"][group]
        lines.append(f"## {section['display_name']}")
        lines.append(f"Count: `{section['count']}`")
        lines.extend(_format_items(section["items"], limit=40))
        lines.append("")

    lines.extend(
        [
            "## Remaining Limits",
            "- Header excerpts are enough for triage, not final architectural truth.",
            "- Rows marked likely or unknown need a later operator-approved inspection lane before any module/node binding.",
            "- Repo B remains reference-only.",
            "",
            "## Next Recommended Lane",
            "Active Machinery Operator Disposition v0",
            "",
        ]
    )
    return "\n".join(lines)


def run_verification(
    *,
    worker_output_path: str | Path = DEFAULT_WORKER_OUTPUT_PATH,
    shard_root: str | Path = DEFAULT_SHARD_ROOT,
    dry_run_path: str | Path = DEFAULT_DRY_RUN_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    doc_path: str | Path = DEFAULT_DOC_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_verification_payload(
        worker_output_path=worker_output_path,
        shard_root=shard_root,
        dry_run_path=dry_run_path,
        generated_at=generated_at,
    )
    read_root = rooted(read_model_root)
    json_path = read_root / "active_machinery_gemini_verification.json"
    operator_path = read_root / "active_machinery_gemini_verification_OPERATOR.md"
    written_json = write_json(json_path, payload)
    written_operator = write_text(operator_path, format_operator_packet(payload))
    written_doc = write_text(doc_path, format_doc(payload))
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_json_path": written_json,
        "read_model_operator_path": written_operator,
        "doc_path": written_doc,
        "worker_items": payload["counts"]["worker_items"],
        "verified_high_risk_count": payload["counts"]["verified_high_risk_count"],
        "likely_active_needing_operator_review_count": payload["counts"][
            "likely_active_needing_operator_review_count"
        ],
        "repo_b_executed": False,
        "raw_private_content_read": False,
        "gemini_output_treated_as_truth": False,
        "next_recommended_lane": "Active Machinery Operator Disposition v0",
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Gemini active-machinery classifications.")
    parser.add_argument("--worker-output", default=DEFAULT_WORKER_OUTPUT_PATH.as_posix())
    parser.add_argument("--shard-root", default=DEFAULT_SHARD_ROOT.as_posix())
    parser.add_argument("--dry-run", default=DEFAULT_DRY_RUN_PATH.as_posix())
    parser.add_argument("--read-model-root", default=DEFAULT_READ_MODEL_ROOT.as_posix())
    parser.add_argument("--doc-path", default=DEFAULT_DOC_PATH.as_posix())
    parser.add_argument("--format", choices=("json", "operator"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = run_verification(
        worker_output_path=args.worker_output,
        shard_root=args.shard_root,
        dry_run_path=args.dry_run,
        read_model_root=args.read_model_root,
        doc_path=args.doc_path,
    )
    if args.format == "operator":
        payload = load_json_object(Path(args.read_model_root) / "active_machinery_gemini_verification.json")
        print(format_operator_packet(payload), end="")
    else:
        print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
