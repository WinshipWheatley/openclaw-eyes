"""Bundle Blueprint Planner v0.

This module turns a high-level pain point into a local bundle manifest using
approved module registry metadata. It is deterministic and non-executing: no
LLM calls, no network, no repo creation, no deployment, no private-data reads,
and no filesystem scanning.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from module_registry import DEFAULT_MODULE_SEEDS, ModuleSeed


BUNDLE_BLUEPRINT_VERSION = "bundle_blueprint_planner_v0"
READ_MODEL_VERSION = "bundle_blueprint_planner_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "bundle_blueprint_planner.json"
OPERATOR_EXPORT_NAME = "bundle_blueprint_planner_OPERATOR.md"

TARGET_CONTEXTS = {"personal", "friend", "company", "client", "internal_test"}

NO_AUTHORITY_FLAGS = {
    "github_packaging_allowed": False,
    "deployment_allowed": False,
    "runtime_authority": False,
    "external_api_allowed": False,
    "model_call_allowed": False,
    "send_allowed": False,
    "repo_creation_allowed": False,
    "private_data_export_allowed": False,
}

SENSITIVE_MARKERS = {
    "bank",
    "client",
    "customer",
    "employee",
    "email",
    "finance",
    "invoice",
    "legal",
    "patient",
    "payable",
    "private",
    "receivable",
    "spreadsheet",
    "tax",
    "vendor",
}


@dataclass(frozen=True)
class BundleBlueprintResult:
    bundle_id: str
    bundle_name: str
    target_context: str
    selected_modules: tuple[str, ...]
    blocked_modules: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    runtime_authority: bool = False
    deployment_allowed: bool = False
    github_packaging_allowed: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _normalize(text: str) -> str:
    lowered = text.lower().replace("_", " ")
    lowered = re.sub(r"[^a-z0-9\s-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _catalog() -> dict[str, ModuleSeed]:
    return {seed.module_id: seed for seed in DEFAULT_MODULE_SEEDS}


def _module_status(module_id: str, catalog: dict[str, ModuleSeed]) -> str:
    seed = catalog.get(module_id)
    return seed.status if seed else "missing"


def _add_module(
    module_id: str,
    *,
    catalog: dict[str, ModuleSeed],
    selected: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    missing: list[str],
    rationale: str,
) -> None:
    seed = catalog.get(module_id)
    if seed is None:
        if module_id not in missing:
            missing.append(module_id)
        return
    item = {
        "module_id": module_id,
        "status": seed.status,
        "authority_level": seed.allowed_authority_level or seed.authority_level,
        "rationale": rationale,
        "runtime_authority": False,
    }
    if seed.status == "blocked":
        blocked.append({**item, "blocked_reason": "module_status_blocked"})
    else:
        selected.append(item)


def _target_context(value: str) -> str:
    normalized = (value or "internal_test").strip().lower()
    if normalized not in TARGET_CONTEXTS:
        return "internal_test"
    return normalized


def _sensitive_hits(normalized: str) -> tuple[str, ...]:
    return tuple(sorted(marker for marker in SENSITIVE_MARKERS if marker in normalized))


def _mapping_for(normalized: str) -> list[tuple[str, str]]:
    mappings: list[tuple[str, str]] = []
    has = lambda *terms: any(term in normalized for term in terms)

    if has("invoice", "receivable", "receivables", "payable", "payment"):
        mappings.extend(
            [
                ("project_capsule_bundle_blueprint", "finance pain point needs a local project/capsule plan"),
                ("report_bridge_sanitized_summary", "finance status should return through sanitized report summaries"),
                ("cassandra_clara_fact_intake", "operator finance facts can enter governed intake"),
            ]
        )
    if has("album", "song", "mix", "music", "production"):
        mappings.append(("niles_album_matrix", "music/art progress maps to Niles album matrix"))
    if has("approval", "approve", "safe", "before emails", "email"):
        mappings.extend(
            [
                ("guardian_hitl_gate", "send-sensitive work needs a Guardian/HITL gate"),
                ("cassandra_clara_fact_intake", "draft/fact intake can prepare metadata before approval"),
            ]
        )
    if has("status report", "client-safe", "private files", "without exposing", "report"):
        mappings.append(("report_bridge_sanitized_summary", "status-only reporting maps to Report Bridge"))
    if has("next best", "next coding", "coding lane", "next lane", "best coding lane"):
        mappings.extend(
            [
                ("hermes_next_lane_advisory", "next-lane sorting maps to advisory synthesis"),
                ("planner_runner_registry", "runner registry concept remains blocked in v0"),
            ]
        )
    if has("client", "company", "friend", "bundle", "project"):
        mappings.append(("project_capsule_bundle_blueprint", "project/client language needs a bundle blueprint"))
    if not mappings:
        mappings.append(("chief_intent_routing", "unknown pain point should become governed triage"))
    return mappings


def plan_bundle_blueprint(
    *,
    pain_point: str,
    target_context: str = "internal_test",
    bundle_name: str | None = None,
) -> dict[str, Any]:
    if not pain_point or not pain_point.strip():
        raise ValueError("pain_point is required")
    resolved_context = _target_context(target_context)
    normalized = _normalize(pain_point)
    catalog = _catalog()
    selected: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    missing_modules: list[str] = []
    seen: set[str] = set()
    for module_id, rationale in _mapping_for(normalized):
        if module_id in seen:
            continue
        seen.add(module_id)
        _add_module(
            module_id,
            catalog=catalog,
            selected=selected,
            blocked=blocked,
            missing=missing_modules,
            rationale=rationale,
        )

    if any(term in normalized for term in ("invoice", "receivable", "receivables", "payable")):
        if "finance_receivables_packet" not in catalog:
            missing_modules.append("finance_receivables_packet")

    sensitive_hits = _sensitive_hits(normalized)
    local_only_required = bool(sensitive_hits) or resolved_context in {"company", "client"}
    missing_inputs = ["operator-approved sanitized pain-point summary"]
    if missing_modules:
        missing_inputs.append("approved module record for " + ", ".join(sorted(set(missing_modules))))
    if local_only_required:
        missing_inputs.append("local-only sensitive data boundary and sanitized Report Bridge summary")

    bundle_id = _row_id("bundleblueprint", resolved_context, normalized)
    manifest = {
        "schema_version": BUNDLE_BLUEPRINT_VERSION,
        "bundle_id": bundle_id,
        "bundle_name": bundle_name or f"{resolved_context.replace('_', ' ').title()} Bundle Blueprint",
        "target_context": resolved_context,
        "pain_point_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "pain_point_category": _category_label(normalized),
        "selected_modules": selected,
        "missing_inputs": tuple(dict.fromkeys(missing_inputs)),
        "missing_modules": tuple(sorted(set(missing_modules))),
        "blocked_modules": blocked,
        "sensitive_data_policy": {
            "local_only_required": local_only_required,
            "needs_operator_review": local_only_required or bool(blocked),
            "sensitive_markers_detected": sensitive_hits,
            "raw_sensitive_data_requested": False,
            "core_receives_private_content": False,
            "policy": "private data stays local; Core receives sanitized status/proof only",
        },
        "report_bridge_policy": {
            "summary_allowed": True,
            "raw_content_allowed": False,
            "client_private_content_allowed": False,
            "allowed_summary_fields": ("status", "proof", "version", "health", "blockers", "receipt_summary"),
        },
        "authority_level": "planning_only",
        "local_only_requirements": tuple(
            ["sanitized_report_bridge_summary"]
            + (["client_or_sensitive_data_stays_local"] if local_only_required else [])
        ),
        "github_packaging_allowed": False,
        "deployment_allowed": False,
        "runtime_authority": False,
        "notes_for_operator": _notes_for_operator(selected, blocked, missing_modules, local_only_required),
        **NO_AUTHORITY_FLAGS,
    }
    return manifest


def _category_label(normalized: str) -> str:
    if any(term in normalized for term in ("invoice", "receivable", "payable", "payment")):
        return "finance_operations"
    if any(term in normalized for term in ("album", "song", "mix", "music", "production")):
        return "music_art"
    if "approval" in normalized or "email" in normalized:
        return "approval_sensitive_comms"
    if "report" in normalized or "private files" in normalized:
        return "sanitized_reporting"
    if "next" in normalized and "lane" in normalized:
        return "advisory_planning"
    return "operator_triage"


def _notes_for_operator(
    selected: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    missing_modules: list[str],
    local_only_required: bool,
) -> tuple[str, ...]:
    notes = [
        "Local planning manifest only; no repo creation, deployment, send, API call, or runtime activation.",
    ]
    if selected:
        notes.append("Selected modules are capability posture, not activation.")
    if blocked:
        notes.append("Blocked modules require a later explicit lane before use.")
    if missing_modules:
        notes.append("Missing modules should be added to the approved registry before relying on them.")
    if local_only_required:
        notes.append("Sensitive or client-like inputs must stay local and return only sanitized Report Bridge summaries.")
    return tuple(notes)


def build_bundle_blueprint_status_read_model() -> dict[str, Any]:
    examples = (
        ("internal_test", "I need help tracking invoices and receivables"),
        ("internal_test", "I need a system to track album progress"),
        ("internal_test", "I need safe approval before emails go out"),
        ("client", "I need a client-safe status report without exposing private files"),
        ("internal_test", "I need the system to pick the next best coding lane"),
    )
    manifests = [
        plan_bundle_blueprint(target_context=context, pain_point=pain_point)
        for context, pain_point in examples
    ]
    selected_counts = Counter(
        module["module_id"]
        for manifest in manifests
        for module in manifest["selected_modules"]
    )
    blocked_counts = Counter(
        module["module_id"]
        for manifest in manifests
        for module in manifest["blocked_modules"]
    )
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "generated_at": utc_now(),
        "mode": "local_bundle_blueprint_planning_only",
        "example_count": len(manifests),
        "selected_module_counts": dict(sorted(selected_counts.items())),
        "blocked_module_counts": dict(sorted(blocked_counts.items())),
        "examples": manifests,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_bundle_blueprint_status_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Bundle Blueprint Planner Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over deterministic local bundle-planning examples.",
        "",
        "What this is not:",
        "- It is not GitHub packaging, deployment, runtime activation, external integration, or client data transfer.",
        "",
        "Summary:",
        f"- Example manifests: {read_model['example_count']}.",
        f"- Selected modules: {_count_line(read_model['selected_module_counts'])}.",
        f"- Blocked modules: {_count_line(read_model['blocked_module_counts'])}.",
        "",
        "Boundary:",
        "- `github_packaging_allowed=false`; `deployment_allowed=false`; `runtime_authority=false`.",
        "- Private/client data stays local; Core receives sanitized status/proof only.",
    ]
    return "\n".join(lines) + "\n"


def _count_line(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def export_bundle_blueprint_planner_read_model(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent / root
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_bundle_blueprint_status_read_model()
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_bundle_blueprint_status_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "example_count": read_model["example_count"],
        **NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "BUNDLE_BLUEPRINT_VERSION",
    "NO_AUTHORITY_FLAGS",
    "READ_MODEL_VERSION",
    "BundleBlueprintResult",
    "build_bundle_blueprint_status_read_model",
    "export_bundle_blueprint_planner_read_model",
    "format_bundle_blueprint_status_read_model",
    "plan_bundle_blueprint",
    "stable_json",
]
