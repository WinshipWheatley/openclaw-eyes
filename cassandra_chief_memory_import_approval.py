"""Cassandra/Chief memory import approval receipt v0.

This module records the operator-approved memory import decisions as a
metadata-only read-model receipt. It does not import legacy data, read raw
source contents, modify runtime behavior, or grant send/runtime authority.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cassandra_chief_memory_authority import (
    STRUCTURED_IMPORT_PLAN_JSON_EXPORT_NAME,
    build_cassandra_chief_structured_import_plan,
    stable_json,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
SCHEMA_VERSION = "cassandra_chief_memory_import_approval_v0"
JSON_EXPORT_NAME = "cassandra_chief_memory_import_approval.json"
OPERATOR_EXPORT_NAME = "cassandra_chief_memory_import_approval_OPERATOR.md"
DEFAULT_HITL_PROOF_NAME = "guardian_hitl_cassandra_proposal_shadow.json"

IMPORT_LATER_STRUCTURED_FACTS = (
    "contacts and nicknames",
    "company/contact relationships",
    "allowed email recipients / email permission posture",
    "invoice facts",
    "receivable/payment tracking",
)
EVIDENCE_SOURCE_ONLY = (
    "Chief session/task memory",
    "Windows-side logs",
)
SUMMARIZE_EXTRACT_ONLY = (
    "Cassandra notes",
    "correspondence metadata",
    "calendar/event notes metadata",
    "billing tracker CSV/PDF paths",
)
RECONCILE_FIRST = (
    "old HITL JSON/JSONL state",
)
CLEANUP_LATER_ONLY = (
    "untracked polish_loop Cassandra failure tasks",
)
DEFER = (
    "album/song progress state",
    "dirty generated agent_presence snapshots",
)

APPROVED_STRUCTURED_SOURCE_FATE = "import_structured_facts_to_sqlite"
EVIDENCE_SOURCE_FATE = "register_as_evidence_source_only"
SUMMARIZE_EXTRACT_FATE = "summarize_or_extract_only"
RECONCILE_FIRST_FATE = "authority_conflict_reconcile_first"
CLEANUP_LATER_FATE = "delete_local_residue_later"
DEFER_FATE = "defer_operator_review"

NO_AUTHORITY_FLAGS = {
    "data_imported": False,
    "raw_data_imported": False,
    "raw_content_read": False,
    "runtime_authority_changed": False,
    "runtime_authority": False,
    "send_authority_granted": False,
    "send_allowed": False,
    "telegram_send_allowed": False,
    "gmail_send_allowed": False,
    "email_send_allowed": False,
    "repo_b_execution_allowed": False,
    "old_hitl_imported": False,
    "agent_presence_imported": False,
    "cleanup_files_deleted": False,
    "old_files_are_truth": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _default_generated_path(file_name: str) -> Path:
    return ROOT / DEFAULT_EXPORT_ROOT / file_name


def _load_structured_import_plan(path: str | Path | None = None) -> dict[str, Any]:
    plan_path = Path(path) if path else _default_generated_path(STRUCTURED_IMPORT_PLAN_JSON_EXPORT_NAME)
    if plan_path.exists():
        return _read_json(plan_path)
    return build_cassandra_chief_structured_import_plan()


def _load_hitl_proof(path: str | Path | None = None) -> dict[str, Any]:
    proof_path = Path(path) if path else _default_generated_path(DEFAULT_HITL_PROOF_NAME)
    return _read_json(proof_path)


def _hitl_proof_satisfied(hitl_proof: dict[str, Any]) -> bool:
    return (
        hitl_proof.get("safe_to_import_cassandra_chief_memory") is True
        and hitl_proof.get("runtime_authority_changed") is False
        and hitl_proof.get("caller_switched") is False
        and hitl_proof.get("old_hitl_deleted") is False
        and hitl_proof.get("raw_payload_stored") is False
        and hitl_proof.get("callback_decision_shadow_support") is True
    )


def _category_by_display_name(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    categories = plan.get("categories")
    if not isinstance(categories, list):
        raise ValueError("structured import plan must contain categories")
    by_name: dict[str, dict[str, Any]] = {}
    for item in categories:
        if not isinstance(item, dict):
            raise ValueError("structured import plan categories must be objects")
        display_name = str(item.get("display_name") or "").strip()
        if not display_name:
            raise ValueError("structured import plan category is missing display_name")
        by_name[display_name] = item
    return by_name


def _require_categories(by_name: dict[str, dict[str, Any]], names: tuple[str, ...]) -> list[dict[str, Any]]:
    missing = [name for name in names if name not in by_name]
    if missing:
        raise ValueError("structured import plan missing categories: " + ", ".join(missing))
    return [by_name[name] for name in names]


def _receipt_category(
    source: dict[str, Any],
    *,
    approved_fate: str,
    import_allowed_later: bool,
    operator_decision: str,
) -> dict[str, Any]:
    return {
        "category_id": source["category_id"],
        "display_name": source["display_name"],
        "source_plan_fate": source["recommended_fate"],
        "approved_fate": approved_fate,
        "operator_decision": operator_decision,
        "proposed_target_table_or_surface": source["proposed_target_table_or_surface"],
        "import_allowed_now": False,
        "import_allowed_later": import_allowed_later,
        "raw_content_allowed": False,
        "approval_required_before_import": True,
        "evidence_status_for_later_import": "parsed_evidence_not_truth",
        "trust_status_for_later_import": "needs_operator_confirmation",
        "no_send_authority": True,
        "no_runtime_authority": True,
        "reason": source["reason"],
        "risk": source["risk"],
        "next_safe_move": source["next_safe_move"],
    }


def build_cassandra_chief_memory_import_approval(
    *,
    structured_import_plan: dict[str, Any] | None = None,
    hitl_proof: dict[str, Any] | None = None,
    structured_import_plan_path: str | Path | None = None,
    hitl_proof_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the operator approval receipt for a later bounded import lane."""
    plan = structured_import_plan or _load_structured_import_plan(structured_import_plan_path)
    proof = hitl_proof or _load_hitl_proof(hitl_proof_path)
    by_name = _category_by_display_name(plan)

    if plan.get("data_imported") is not False:
        raise ValueError("structured import plan must have data_imported=false")
    if plan.get("raw_content_read") is not False:
        raise ValueError("structured import plan must have raw_content_read=false")
    if plan.get("old_files_are_truth") is not False:
        raise ValueError("structured import plan must have old_files_are_truth=false")

    approved = [
        _receipt_category(
            item,
            approved_fate=APPROVED_STRUCTURED_SOURCE_FATE,
            import_allowed_later=True,
            operator_decision="approved_for_later_bounded_structured_import",
        )
        for item in _require_categories(by_name, IMPORT_LATER_STRUCTURED_FACTS)
    ]
    evidence_only = [
        _receipt_category(
            item,
            approved_fate=EVIDENCE_SOURCE_FATE,
            import_allowed_later=False,
            operator_decision="approved_evidence_source_only",
        )
        for item in _require_categories(by_name, EVIDENCE_SOURCE_ONLY)
    ]
    summarize_only = [
        _receipt_category(
            item,
            approved_fate=SUMMARIZE_EXTRACT_FATE,
            import_allowed_later=False,
            operator_decision="approved_summarize_or_extract_only",
        )
        for item in _require_categories(by_name, SUMMARIZE_EXTRACT_ONLY)
    ]
    reconcile_first = [
        _receipt_category(
            item,
            approved_fate=RECONCILE_FIRST_FATE,
            import_allowed_later=False,
            operator_decision="not_approved_for_import_reconcile_first",
        )
        for item in _require_categories(by_name, RECONCILE_FIRST)
    ]
    cleanup_later = [
        _receipt_category(
            item,
            approved_fate=CLEANUP_LATER_FATE,
            import_allowed_later=False,
            operator_decision="approved_cleanup_candidate_later_only",
        )
        for item in _require_categories(by_name, CLEANUP_LATER_ONLY)
    ]
    deferred = [
        _receipt_category(
            item,
            approved_fate=DEFER_FATE,
            import_allowed_later=False,
            operator_decision="deferred_not_approved_for_cassandra_chief_import",
        )
        for item in _require_categories(by_name, DEFER)
    ]

    proof_satisfied = _hitl_proof_satisfied(proof)
    safe_to_import_structured_facts = bool(proof_satisfied and len(approved) == 5)
    decision_basis = {
        "approved": [item["display_name"] for item in approved],
        "evidence_source_only": [item["display_name"] for item in evidence_only],
        "summarize_extract_only": [item["display_name"] for item in summarize_only],
        "reconcile_first": [item["display_name"] for item in reconcile_first],
        "cleanup_later": [item["display_name"] for item in cleanup_later],
        "deferred": [item["display_name"] for item in deferred],
        "hitl_proof_satisfied": proof_satisfied,
    }
    approval_receipt_id = _row_id("ccmem_import_approval", SCHEMA_VERSION, stable_json(decision_basis))
    now = generated_at or utc_now()

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "approval_receipt_id": approval_receipt_id,
        "source_basis": [
            "operator_prompt_explicit_category_decisions",
            "generated/read_models/guardian_hitl_cassandra_proposal_shadow.json",
            "generated/read_models/cassandra_chief_structured_import_plan.json",
        ],
        "data_imported": False,
        "raw_data_imported": False,
        "raw_content_read": False,
        "runtime_authority_changed": False,
        "hitl_proof_required": True,
        "hitl_proof_satisfied": proof_satisfied,
        "safe_to_import_structured_facts": safe_to_import_structured_facts,
        "approved_categories": approved,
        "evidence_source_only_categories": evidence_only,
        "summarize_extract_only_categories": summarize_only,
        "reconcile_first_categories": reconcile_first,
        "cleanup_later_categories": cleanup_later,
        "deferred_categories": deferred,
        "approved_category_count": len(approved),
        "structured_import_constraints": {
            "evidence_status": "parsed_evidence_not_truth",
            "trust_status": "needs_operator_confirmation",
            "no_send_authority": True,
            "no_runtime_authority": True,
            "approval_required": True,
            "raw_content_allowed": False,
        },
        "blocked_actions": [
            "real data import in this receipt lane",
            "raw private content reading",
            "old HITL JSON/JSONL import",
            "agent_presence snapshot import",
            "album/song progress import",
            "log import",
            "send authority",
            "runtime authority",
            "Repo B execution",
            "automatic deletion of cleanup candidates",
        ],
        "boundaries": {
            **NO_AUTHORITY_FLAGS,
            "hitl_proof_required": True,
            "hitl_proof_satisfied": proof_satisfied,
            "safe_to_import_structured_facts": safe_to_import_structured_facts,
        },
        "next_safe_lane": (
            "Cassandra/Chief Structured Fact Import v0"
            if safe_to_import_structured_facts
            else "Resolve Cassandra HITL proof before structured fact import"
        ),
        **NO_AUTHORITY_FLAGS,
    }


def _category_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- None."]
    return [
        f"- {item['display_name']}: `{item['operator_decision']}`; later import now=`{str(item['import_allowed_now']).lower()}`."
        for item in items
    ]


def format_cassandra_chief_memory_import_approval(payload: dict[str, Any]) -> str:
    lines = [
        "# Cassandra/Chief Memory Import Approval Receipt v0",
        "",
        "Plain-English status:",
        "- The operator approved category fates for the next bounded import lane.",
        "- No data was imported.",
        "- No raw content was read.",
        "- Old files are not truth.",
        "- Runtime authority did not change.",
        "",
        "## Approved for later structured import",
        *_category_lines(payload["approved_categories"]),
        "",
        "## Evidence-source-only",
        *_category_lines(payload["evidence_source_only_categories"]),
        "",
        "## Summarize/extract-only",
        *_category_lines(payload["summarize_extract_only_categories"]),
        "",
        "## Reconcile-first / not imported",
        *_category_lines(payload["reconcile_first_categories"]),
        "",
        "## Cleanup later only",
        *_category_lines(payload["cleanup_later_categories"]),
        "",
        "## Deferred",
        *_category_lines(payload["deferred_categories"]),
        "",
        "## What did not happen",
        "- No legacy file bodies were opened or imported.",
        "- Old HITL JSON/JSONL was not imported.",
        "- Agent presence snapshots were not treated as truth.",
        "- Cleanup candidates were not deleted.",
        "- No send or runtime authority was granted.",
        "",
        "## Next safe move",
        f"- HITL proof satisfied: `{str(payload['hitl_proof_satisfied']).lower()}`.",
        f"- Structured fact import safe now: `{str(payload['safe_to_import_structured_facts']).lower()}`.",
        f"- Next lane: {payload['next_safe_lane']}.",
    ]
    return "\n".join(lines) + "\n"


def export_cassandra_chief_memory_import_approval(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    structured_import_plan_path: str | Path | None = None,
    hitl_proof_path: str | Path | None = None,
    structured_import_plan: dict[str, Any] | None = None,
    hitl_proof: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    export_path = _export_root_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_cassandra_chief_memory_import_approval(
        structured_import_plan=structured_import_plan,
        hitl_proof=hitl_proof,
        structured_import_plan_path=structured_import_plan_path,
        hitl_proof_path=hitl_proof_path,
        generated_at=generated_at,
    )
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_cassandra_chief_memory_import_approval(payload), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "approval_receipt_id": payload["approval_receipt_id"],
        "safe_to_import_structured_facts": payload["safe_to_import_structured_facts"],
        "data_imported": False,
        "raw_content_read": False,
        "runtime_authority_changed": False,
        "old_hitl_imported": False,
    }


__all__ = [
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_cassandra_chief_memory_import_approval",
    "export_cassandra_chief_memory_import_approval",
    "format_cassandra_chief_memory_import_approval",
]
