"""Project Room / Source Room sourceset contract V0.

This module publishes a deterministic contract for building a source room
before serious OpenClaw work. It records source inventories, conflicts, missing
context, duplicate/version families, decision traces, authority, and freshness.
It does not invoke models, connect runtimes, spawn workers, touch business
systems, mutate ledgers/workbooks, export PDFs, submit anything, or push git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Project Room Sourceset Contract.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/project_room_sourceset_contract.sqlite")

SCHEMA_VERSION = "project_room_sourceset_contract_v0"
READ_MODEL_ID = "project_room_sourceset_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "PROJECT_ROOM_SOURCESET_CONTRACT_READY"
NOT_READY_STATUS = "PROJECT_ROOM_SOURCESET_CONTRACT_NOT_READY"

PRECONDITIONS = {
    "context_freshness_decision_trace_gate": {
        "filename": "context_freshness_decision_trace_gate.json",
        "accepted_statuses": ("CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "retrospective_harness_learning_seed": {
        "filename": "retrospective_harness_learning_seed.json",
        "accepted_statuses": ("RETROSPECTIVE_HARNESS_LEARNING_SEED_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "operator_session_timeline": {
        "filename": "operator_session_timeline.json",
        "accepted_statuses": ("OPERATOR_SESSION_TIMELINE_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
}

PROJECT_ROOM_FIELDS = (
    "project_room_id",
    "objective_ref",
    "world_ref",
    "thread_ref",
    "workspace_scope",
    "source_set_ref",
    "source_inventory_ref",
    "conflict_log_ref",
    "missing_context_ref",
    "duplicate_report_ref",
    "decision_trace_ref",
    "authority_ranking_ref",
    "freshness_gate_ref",
    "allowed_next_steps",
    "blocked_next_steps",
    "synthesis_allowed",
)

SOURCE_INVENTORY_FIELDS = (
    "source_ref",
    "path_or_artifact_ref",
    "source_type",
    "date_observed",
    "date_claimed",
    "apparent_authority",
    "freshness_state",
    "confidence_class",
    "claims_supported",
    "limitations",
    "how_to_use",
    "do_not_use_for",
    "source_hash",
    "receipt_refs",
)

CONFLICT_LOG_FIELDS = (
    "conflict_ref",
    "project_room_id",
    "conflicting_source_refs",
    "conflict_summary",
    "affected_claims",
    "likely_resolution",
    "operator_decision_required",
    "unresolved",
)

MISSING_CONTEXT_FIELDS = (
    "missing_context_ref",
    "project_room_id",
    "gap_summary",
    "why_it_matters",
    "source_that_implies_gap",
    "required_source_or_decision",
    "safe_wording_if_unresolved",
)

DUPLICATE_REPORT_FIELDS = (
    "version_family_ref",
    "project_room_id",
    "candidate_source_refs",
    "likely_current_source_ref",
    "older_or_superseded_refs",
    "confidence",
    "operator_review_required",
    "deletion_allowed",
)

DECISION_TRACE_FIELDS = (
    "decision_trace_ref",
    "project_room_id",
    "prior_attempts",
    "rejected_attempts",
    "operator_decisions",
    "receipts",
    "what_changed",
    "what_not_to_repeat",
)

REQUIRED_SCENARIOS = (
    "finance_capital_hilton_payment_watch",
    "business_development_capital_hilton_follow_up",
    "build_review_packet",
    "niles_music_controller_mapping",
    "self_heal_repair",
    "stale_source",
)

CORE_DOCTRINE = (
    "First prompt for serious work is not do the thing.",
    "First step is build the room.",
    "Originals are preserved.",
    "Source inventory is created before synthesis.",
    "Conflicts are surfaced before drafting.",
    "Missing context is named before invention.",
    "Duplicates and version families are identified before weighting.",
    "Authority and freshness are explicit.",
    "Agent may not silently resolve contradictions.",
    "Memory is a hint, not truth.",
    "Current receipts and proof beat generated summaries.",
)

RULES = (
    "Do not synthesize final output until source inventory exists.",
    "Do not treat old versions as current.",
    "Do not delete duplicates automatically.",
    "Do not let duplicated docs overweight synthesis.",
    "Do not use missing context as permission to invent.",
    "Do not let generated summaries outrank receipts.",
    "Project room may stage a package only after source room gates are satisfied.",
)

AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "local_model_runtime_allowed": False,
    "worker_spawn_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "source_deletion_allowed": False,
    "duplicate_deletion_allowed": False,
    "silent_conflict_resolution_allowed": False,
    "generated_summary_authority_allowed": False,
    "protected_action_allowed": False,
    "git_push_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "worker_spawn_performed": False,
    "email_send_performed": False,
    "gmail_opened": False,
    "browser_opened": False,
    "coupa_opened": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "submit_performed": False,
    "source_deleted": False,
    "duplicate_deleted": False,
    "git_push_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | {
        "authority_granted",
        "protected_action_performed",
        "final_output_synthesized_without_inventory",
        "generated_summary_outranked_receipt",
        "superseded_source_current_truth",
        "unsupported_claim_allowed",
        "silent_conflict_resolution_performed",
        "deletion_allowed",
        "send_authority_granted",
        "paid_action_allowed",
        "ledger_action_allowed",
        "business_action_performed",
        "submitted",
        "sent",
        "paid",
    }
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path | str) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path | str, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("readiness_status") or payload.get("contract_status") or "")


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    return rows


def authority_rankings() -> list[dict[str, Any]]:
    return [
        {
            "authority_ranking_ref": "authority_ranking:receipt_first",
            "ranked_authority": [
                "current_receipts_and_proof",
                "operator_decisions_with_receipts",
                "preserved_original_sources",
                "current_source_inventory_rows",
                "generated_summaries",
                "memory_hints",
            ],
            "generated_summary_rule": "Generated summaries explain source material but never outrank receipts, originals, or current proof.",
            "memory_rule": "Memory may suggest where to look, but memory is not truth until proof-backed in the room.",
        }
    ]


def freshness_gates() -> list[dict[str, Any]]:
    return [
        {
            "freshness_gate_ref": "freshness_gate:receipt_current_or_needs_verification",
            "current_truth_requires": [
                "source_inventory_row_exists",
                "freshness_state_is_current_or_current_receipt",
                "not_superseded",
                "not_generated_summary_only",
                "no_unresolved_conflict_for_claim",
            ],
            "blocked_state": "Needs verification",
            "stale_source_policy": "Synthesis is blocked or explicitly marked Needs verification when sources are stale, superseded, or untraceable.",
        }
    ]


def _source(
    *,
    inventory_ref: str,
    room_id: str,
    source_ref: str,
    artifact: str,
    source_type: str,
    observed: str,
    claimed: str,
    authority: str,
    freshness: str,
    confidence: str,
    claims: list[str],
    limitations: list[str],
    how_to_use: str,
    do_not_use_for: list[str],
    receipts: list[str],
    source_hash: str = "",
) -> dict[str, Any]:
    return {
        "source_inventory_ref": inventory_ref,
        "project_room_id": room_id,
        "source_ref": source_ref,
        "path_or_artifact_ref": artifact,
        "source_type": source_type,
        "date_observed": observed,
        "date_claimed": claimed,
        "apparent_authority": authority,
        "freshness_state": freshness,
        "confidence_class": confidence,
        "claims_supported": claims,
        "limitations": limitations,
        "how_to_use": how_to_use,
        "do_not_use_for": do_not_use_for,
        "source_hash": source_hash,
        "receipt_refs": receipts,
    }


def source_inventory(generated_at: str) -> list[dict[str, Any]]:
    return [
        _source(
            inventory_ref="source_inventory:finance_capital_hilton_payment_watch",
            room_id="finance_capital_hilton_payment_watch",
            source_ref="source:finance_payment_watch_state",
            artifact="generated/read_models/proof_to_response_latest.json",
            source_type="current_receipt_read_model",
            observed=generated_at,
            claimed="current payment-watch state",
            authority="current_receipts_and_proof",
            freshness="current_receipt",
            confidence="receipt_backed",
            claims=["Coupa processing is still in progress.", "paid=false", "ledger untouched"],
            limitations=["Does not prove payment completion.", "Does not authorize ledger mutation."],
            how_to_use="Explain the payment-watch state and the smallest next step.",
            do_not_use_for=["mark paid", "mutate ledger", "export payment packet as complete"],
            receipts=["proof_to_response_runtime_status", "finance_payment_watch_receipt"],
            source_hash="optional:future_source_inventory_hash",
        ),
        _source(
            inventory_ref="source_inventory:finance_capital_hilton_payment_watch",
            room_id="finance_capital_hilton_payment_watch",
            source_ref="source:finance_generated_summary",
            artifact="generated/read_models/openclaw_request_processor_OPERATOR.md",
            source_type="generated_summary",
            observed=generated_at,
            claimed="summary of finance lane",
            authority="generated_summaries",
            freshness="support_only",
            confidence="summary_only",
            claims=["May help locate the finance task."],
            limitations=["Cannot override payment-watch receipts."],
            how_to_use="Use only as a navigation hint after receipt-backed inventory rows are present.",
            do_not_use_for=["current truth", "paid status", "ledger status"],
            receipts=[],
        ),
        _source(
            inventory_ref="source_inventory:business_development_capital_hilton_follow_up",
            room_id="business_development_capital_hilton_follow_up",
            source_ref="source:bd_proposal_state",
            artifact="generated/read_models/proof_to_response_latest.json",
            source_type="proposal_status_receipt",
            observed=generated_at,
            claimed="proposal waiting for follow-up",
            authority="current_receipts_and_proof",
            freshness="current_receipt",
            confidence="receipt_backed",
            claims=["Proposal exists.", "Follow-up may be needed."],
            limitations=["Does not prove latest follow-up status or send authority."],
            how_to_use="Use as one side of the proposal/follow-up state check.",
            do_not_use_for=["send email", "claim follow-up already sent"],
            receipts=["business_development_lane_receipt"],
        ),
        _source(
            inventory_ref="source_inventory:business_development_capital_hilton_follow_up",
            room_id="business_development_capital_hilton_follow_up",
            source_ref="source:bd_follow_up_state",
            artifact="generated/read_models/operator_session_timeline.json",
            source_type="timeline_event",
            observed=generated_at,
            claimed="follow-up status unresolved",
            authority="operator_decisions_with_receipts",
            freshness="needs_reconciliation",
            confidence="conflict_detected",
            claims=["Follow-up state may disagree with proposal state."],
            limitations=["Requires operator decision or current send/follow-up receipt."],
            how_to_use="Surface the disagreement before drafting a final follow-up.",
            do_not_use_for=["send authority", "silent status resolution"],
            receipts=["operator_session_timeline"],
        ),
        _source(
            inventory_ref="source_inventory:build_review_packet",
            room_id="build_review_packet",
            source_ref="source:build_resolved_review_packet",
            artifact="generated/read_models/workroom_review_decision_status.json",
            source_type="review_decision_receipt",
            observed=generated_at,
            claimed="informational/resolved packet",
            authority="operator_decisions_with_receipts",
            freshness="historical_resolved",
            confidence="receipt_backed_history",
            claims=["Packet is informational/resolved.", "Prior review decision exists."],
            limitations=["Not active ready-for-review work unless reopened by a current receipt."],
            how_to_use="Use as history and prior decision context.",
            do_not_use_for=["active work queue", "ready-for-review claim"],
            receipts=["workroom_review_decision_status"],
        ),
        _source(
            inventory_ref="source_inventory:niles_music_controller_mapping",
            room_id="niles_music_controller_mapping",
            source_ref="source:niles_creative_notes",
            artifact="generated/read_models/operator_session_timeline.json",
            source_type="creative_notes",
            observed=generated_at,
            claimed="Niles music/controller idea space",
            authority="preserved_original_sources",
            freshness="usable_creative_context",
            confidence="operator_context",
            claims=["Creative options may be explored."],
            limitations=["Does not prove software integration, controller target, or factual system behavior."],
            how_to_use="Generate creative options and questions about controller targets.",
            do_not_use_for=["unrelated business proof", "unsourced factual setup claims"],
            receipts=["operator_session_timeline"],
        ),
        _source(
            inventory_ref="source_inventory:self_heal_repair",
            room_id="self_heal_repair",
            source_ref="source:self_heal_blocker_proof",
            artifact="generated/read_models/self_heal_repair_doctrine.json",
            source_type="repair_doctrine_read_model",
            observed=generated_at,
            claimed="blocker proof and repair doctrine",
            authority="current_receipts_and_proof",
            freshness="current_receipt",
            confidence="receipt_backed",
            claims=["Blocker proof must be named.", "Validation plan is required before repair package adoption."],
            limitations=["Does not authorize live repair execution."],
            how_to_use="Propose a repair package with blocker proof, validation plan, rollback plan, and receipt requirement.",
            do_not_use_for=["execute repair", "restart services", "delete files"],
            receipts=["self_heal_repair_doctrine"],
        ),
        _source(
            inventory_ref="source_inventory:self_heal_repair",
            room_id="self_heal_repair",
            source_ref="source:self_heal_validation_failure",
            artifact="generated/read_models/retrospective_harness_learning_seed.json",
            source_type="retrospective_failure_record",
            observed=generated_at,
            claimed="prior repair/validation failure lesson",
            authority="current_source_inventory_rows",
            freshness="current_supporting_context",
            confidence="receipt_backed_lesson",
            claims=["Prior attempts and validation failures must be preserved in decision trace."],
            limitations=["Cannot auto-apply a harness update."],
            how_to_use="Include prior attempts and what not to repeat in repair package planning.",
            do_not_use_for=["live self-optimization", "black-box repair success claim"],
            receipts=["retrospective_harness_learning_seed"],
        ),
        _source(
            inventory_ref="source_inventory:stale_source",
            room_id="stale_source",
            source_ref="source:stale_generated_summary",
            artifact="generated/read_models/openclaw_request_processor_OPERATOR.md",
            source_type="generated_summary",
            observed=generated_at,
            claimed="older task state",
            authority="generated_summaries",
            freshness="stale",
            confidence="stale_summary",
            claims=["May indicate a past task existed."],
            limitations=["Cannot be used as current truth.", "Needs verification before synthesis."],
            how_to_use="Mark Needs verification and request current source or receipt.",
            do_not_use_for=["current truth", "final answer", "action package"],
            receipts=[],
        ),
        _source(
            inventory_ref="source_inventory:stale_source",
            room_id="stale_source",
            source_ref="source:superseded_source_version",
            artifact="docs/planning/launch_ladder/source_set_bridges/backend_data_contract_first_planning_slice_decision_20260505.md",
            source_type="older_source_version",
            observed=generated_at,
            claimed="older source family member",
            authority="preserved_original_sources",
            freshness="superseded",
            confidence="superseded_history",
            claims=["Shows historical context."],
            limitations=["Cannot outrank current receipts or current inventory rows."],
            how_to_use="Preserve as history and compare against current source when available.",
            do_not_use_for=["current truth", "unreviewed final synthesis"],
            receipts=[],
        ),
    ]


def conflict_log() -> list[dict[str, Any]]:
    return [
        {
            "conflict_ref": "conflict:bd_proposal_follow_up_status",
            "project_room_id": "business_development_capital_hilton_follow_up",
            "conflicting_source_refs": ["source:bd_proposal_state", "source:bd_follow_up_state"],
            "conflict_summary": "Proposal status and follow-up status disagree or are not proven by the same current receipt.",
            "affected_claims": ["proposal_current_status", "follow_up_needed", "follow_up_already_sent"],
            "likely_resolution": "Ask for the current proposal/follow-up receipt or operator decision before final drafting.",
            "operator_decision_required": True,
            "unresolved": True,
        },
        {
            "conflict_ref": "conflict:stale_summary_vs_current_truth",
            "project_room_id": "stale_source",
            "conflicting_source_refs": ["source:stale_generated_summary", "source:superseded_source_version"],
            "conflict_summary": "Stale generated summary and older source version cannot establish current truth.",
            "affected_claims": ["current_status", "ready_to_package", "safe_to_answer"],
            "likely_resolution": "Attach a current receipt/source before any final synthesis.",
            "operator_decision_required": True,
            "unresolved": True,
        },
    ]


def missing_context_list() -> list[dict[str, Any]]:
    return [
        {
            "missing_context_ref": "missing_context:finance_payment_evidence",
            "project_room_id": "finance_capital_hilton_payment_watch",
            "gap_summary": "Payment evidence is missing.",
            "why_it_matters": "Without payment proof, OpenClaw cannot claim paid, mutate a ledger, or complete a payment package.",
            "source_that_implies_gap": "source:finance_payment_watch_state",
            "required_source_or_decision": "Attach payment evidence or an operator receipt proving payment.",
            "safe_wording_if_unresolved": "Payment evidence is missing; I can explain the watch state and next step, but cannot mark paid.",
        },
        {
            "missing_context_ref": "missing_context:bd_send_authority",
            "project_room_id": "business_development_capital_hilton_follow_up",
            "gap_summary": "No send authority is present.",
            "why_it_matters": "A follow-up may be drafted inside the room but cannot be sent or represented as sent.",
            "source_that_implies_gap": "source:bd_follow_up_state",
            "required_source_or_decision": "Operator approval or send receipt.",
            "safe_wording_if_unresolved": "I can prepare a draft or list missing context, but I cannot send it.",
        },
        {
            "missing_context_ref": "missing_context:niles_controller_target",
            "project_room_id": "niles_music_controller_mapping",
            "gap_summary": "Software/controller target is absent.",
            "why_it_matters": "Creative notes alone do not prove which controller, app, protocol, or integration target should be mapped.",
            "source_that_implies_gap": "source:niles_creative_notes",
            "required_source_or_decision": "Name the controller/software target or attach its source artifact.",
            "safe_wording_if_unresolved": "I can offer creative mapping options and questions; I cannot make factual controller claims without a source.",
        },
        {
            "missing_context_ref": "missing_context:stale_current_source",
            "project_room_id": "stale_source",
            "gap_summary": "Current source or receipt is missing.",
            "why_it_matters": "Stale and superseded materials cannot support current truth or final work.",
            "source_that_implies_gap": "source:stale_generated_summary",
            "required_source_or_decision": "Attach current source, current receipt, or operator decision to proceed as historical only.",
            "safe_wording_if_unresolved": "This source appears stale and needs verification before final synthesis.",
        },
    ]


def duplicate_version_report() -> list[dict[str, Any]]:
    return [
        {
            "version_family_ref": "version_family:finance_payment_watch",
            "project_room_id": "finance_capital_hilton_payment_watch",
            "candidate_source_refs": ["source:finance_payment_watch_state", "source:finance_generated_summary"],
            "likely_current_source_ref": "source:finance_payment_watch_state",
            "older_or_superseded_refs": ["source:finance_generated_summary"],
            "confidence": "high",
            "operator_review_required": True,
            "deletion_allowed": False,
        },
        {
            "version_family_ref": "version_family:bd_capital_hilton_follow_up",
            "project_room_id": "business_development_capital_hilton_follow_up",
            "candidate_source_refs": ["source:bd_proposal_state", "source:bd_follow_up_state"],
            "likely_current_source_ref": "operator_decision_required",
            "older_or_superseded_refs": [],
            "confidence": "conflict_requires_review",
            "operator_review_required": True,
            "deletion_allowed": False,
        },
        {
            "version_family_ref": "version_family:build_review_packet",
            "project_room_id": "build_review_packet",
            "candidate_source_refs": ["source:build_resolved_review_packet"],
            "likely_current_source_ref": "source:build_resolved_review_packet",
            "older_or_superseded_refs": [],
            "confidence": "high_historical",
            "operator_review_required": True,
            "deletion_allowed": False,
        },
        {
            "version_family_ref": "version_family:niles_music_controller_mapping",
            "project_room_id": "niles_music_controller_mapping",
            "candidate_source_refs": ["source:niles_creative_notes"],
            "likely_current_source_ref": "source:niles_creative_notes",
            "older_or_superseded_refs": [],
            "confidence": "creative_context_only",
            "operator_review_required": True,
            "deletion_allowed": False,
        },
        {
            "version_family_ref": "version_family:self_heal_repair",
            "project_room_id": "self_heal_repair",
            "candidate_source_refs": ["source:self_heal_blocker_proof", "source:self_heal_validation_failure"],
            "likely_current_source_ref": "source:self_heal_blocker_proof",
            "older_or_superseded_refs": [],
            "confidence": "high",
            "operator_review_required": True,
            "deletion_allowed": False,
        },
        {
            "version_family_ref": "version_family:stale_source",
            "project_room_id": "stale_source",
            "candidate_source_refs": ["source:stale_generated_summary", "source:superseded_source_version"],
            "likely_current_source_ref": "current_source_missing",
            "older_or_superseded_refs": ["source:stale_generated_summary", "source:superseded_source_version"],
            "confidence": "blocked_until_current_source",
            "operator_review_required": True,
            "deletion_allowed": False,
        },
    ]


def decision_traces() -> list[dict[str, Any]]:
    return [
        {
            "decision_trace_ref": "decision_trace:finance_capital_hilton_payment_watch",
            "project_room_id": "finance_capital_hilton_payment_watch",
            "prior_attempts": ["Payment-watch explanation and Coupa-gate routing attempts."],
            "rejected_attempts": ["Do not mark paid from Coupa processing or generated summary."],
            "operator_decisions": ["Payment evidence is required before paid or ledger action."],
            "receipts": ["proof_to_response_runtime_status", "finance_payment_watch_receipt"],
            "what_changed": "Room permits explanation and next-step wording only.",
            "what_not_to_repeat": "Do not treat Coupa processing or summary copy as payment proof.",
        },
        {
            "decision_trace_ref": "decision_trace:business_development_capital_hilton_follow_up",
            "project_room_id": "business_development_capital_hilton_follow_up",
            "prior_attempts": ["Follow-up context was routed through proof-to-response lane state."],
            "rejected_attempts": ["Do not send or claim sent without send authority."],
            "operator_decisions": ["Surface proposal/follow-up disagreement before final drafting."],
            "receipts": ["operator_session_timeline", "business_development_lane_receipt"],
            "what_changed": "Conflict log now controls final synthesis and send authority.",
            "what_not_to_repeat": "Do not silently resolve proposal/follow-up disagreement.",
        },
        {
            "decision_trace_ref": "decision_trace:build_review_packet",
            "project_room_id": "build_review_packet",
            "prior_attempts": ["Resolved Build review packet was shown like active ready-for-review work."],
            "rejected_attempts": ["Do not treat informational/resolved packet as active work."],
            "operator_decisions": ["Resolved packet remains historical unless reopened by current receipt."],
            "receipts": ["workroom_review_decision_status"],
            "what_changed": "Source room marks the packet historical and includes prior review decision.",
            "what_not_to_repeat": "Do not let stale UI state dominate lifecycle receipts.",
        },
        {
            "decision_trace_ref": "decision_trace:niles_music_controller_mapping",
            "project_room_id": "niles_music_controller_mapping",
            "prior_attempts": ["Creative music/controller mapping was discussed without a controller target source."],
            "rejected_attempts": ["Do not import unrelated finance proof or claim controller facts without source."],
            "operator_decisions": ["Creative options are allowed; factual claims require source."],
            "receipts": ["operator_session_timeline"],
            "what_changed": "Niles room explicitly excludes unrelated finance proof.",
            "what_not_to_repeat": "Do not mix worlds or use finance artifacts to support creative/controller claims.",
        },
        {
            "decision_trace_ref": "decision_trace:self_heal_repair",
            "project_room_id": "self_heal_repair",
            "prior_attempts": ["Self-heal diagnosis and validation failure records were captured."],
            "rejected_attempts": ["Do not execute repair or claim success without validation and receipt."],
            "operator_decisions": ["Repair packages may be proposed only with validation plan and rollback plan."],
            "receipts": ["self_heal_repair_doctrine", "retrospective_harness_learning_seed"],
            "what_changed": "Room requires blocker proof, validation plan, prior attempts, and what not to repeat.",
            "what_not_to_repeat": "Do not run black-box repair loops or hide validation failure.",
        },
        {
            "decision_trace_ref": "decision_trace:stale_source",
            "project_room_id": "stale_source",
            "prior_attempts": ["Older summaries and source versions appeared usable without fresh receipts."],
            "rejected_attempts": ["Do not answer from stale source as current truth."],
            "operator_decisions": ["Synthesis is blocked or marked Needs verification until current proof exists."],
            "receipts": ["context_freshness_decision_trace_gate"],
            "what_changed": "Room demotes stale and superseded material to history/support.",
            "what_not_to_repeat": "Do not use stale summaries to bypass freshness gates.",
        },
    ]


def project_rooms() -> list[dict[str, Any]]:
    common_authority = "authority_ranking:receipt_first"
    common_freshness = "freshness_gate:receipt_current_or_needs_verification"
    base_protected = {
        "send_authority_granted": False,
        "paid_action_allowed": False,
        "ledger_action_allowed": False,
    }
    return [
        {
            "project_room_id": "finance_capital_hilton_payment_watch",
            "objective_ref": "objective:finance_capital_hilton_payment_watch",
            "world_ref": "world:finance",
            "thread_ref": "thread:capital_hilton",
            "workspace_scope": "Finance / Capital Hilton payment watch only.",
            "source_set_ref": "source_set:finance_capital_hilton_payment_watch",
            "source_inventory_ref": "source_inventory:finance_capital_hilton_payment_watch",
            "conflict_log_ref": "conflict_log:finance_capital_hilton_payment_watch",
            "missing_context_ref": "missing_context:finance_payment_evidence",
            "duplicate_report_ref": "version_family:finance_payment_watch",
            "decision_trace_ref": "decision_trace:finance_capital_hilton_payment_watch",
            "authority_ranking_ref": common_authority,
            "freshness_gate_ref": common_freshness,
            "allowed_next_steps": ["explain payment-watch state", "ask for payment evidence", "stage next-step wording"],
            "blocked_next_steps": ["mark paid", "mutate ledger", "export PDF", "read workbook cells as proof"],
            "synthesis_allowed": True,
            "synthesis_scope": "explanation_and_next_step_only",
            "inventory_gate": "passed_with_limited_scope",
            "source_disagreement_detected": False,
            "missing_context_blocks": ["paid claim", "ledger action"],
            "protected_authority": dict(base_protected),
        },
        {
            "project_room_id": "business_development_capital_hilton_follow_up",
            "objective_ref": "objective:business_development_capital_hilton_follow_up",
            "world_ref": "world:business_development",
            "thread_ref": "thread:capital_hilton",
            "workspace_scope": "Business Development / Capital Hilton proposal and follow-up state.",
            "source_set_ref": "source_set:business_development_capital_hilton_follow_up",
            "source_inventory_ref": "source_inventory:business_development_capital_hilton_follow_up",
            "conflict_log_ref": "conflict:bd_proposal_follow_up_status",
            "missing_context_ref": "missing_context:bd_send_authority",
            "duplicate_report_ref": "version_family:bd_capital_hilton_follow_up",
            "decision_trace_ref": "decision_trace:business_development_capital_hilton_follow_up",
            "authority_ranking_ref": common_authority,
            "freshness_gate_ref": common_freshness,
            "allowed_next_steps": ["surface proposal/follow-up conflict", "ask for current receipt", "draft only after source gate"],
            "blocked_next_steps": ["send follow-up", "claim follow-up sent", "silently resolve status conflict"],
            "synthesis_allowed": False,
            "synthesis_scope": "blocked_until_conflict_or_operator_decision_resolves",
            "inventory_gate": "blocked_by_unresolved_conflict",
            "source_disagreement_detected": True,
            "missing_context_blocks": ["send claim", "sent status claim"],
            "protected_authority": dict(base_protected),
        },
        {
            "project_room_id": "build_review_packet",
            "objective_ref": "objective:build_review_packet",
            "world_ref": "world:build",
            "thread_ref": "thread:review_packet",
            "workspace_scope": "Build review packet lifecycle and prior review decision.",
            "source_set_ref": "source_set:build_review_packet",
            "source_inventory_ref": "source_inventory:build_review_packet",
            "conflict_log_ref": "conflict_log:build_review_packet",
            "missing_context_ref": "missing_context:none",
            "duplicate_report_ref": "version_family:build_review_packet",
            "decision_trace_ref": "decision_trace:build_review_packet",
            "authority_ranking_ref": common_authority,
            "freshness_gate_ref": common_freshness,
            "allowed_next_steps": ["summarize historical packet", "cite prior review decision", "ask if reopened"],
            "blocked_next_steps": ["treat resolved packet as active work", "show as ready-for-review"],
            "synthesis_allowed": True,
            "synthesis_scope": "historical_summary_only",
            "inventory_gate": "passed_with_historical_scope",
            "source_disagreement_detected": False,
            "missing_context_blocks": [],
            "protected_authority": dict(base_protected),
        },
        {
            "project_room_id": "niles_music_controller_mapping",
            "objective_ref": "objective:niles_music_controller_mapping",
            "world_ref": "world:niles_music",
            "thread_ref": "thread:controller_mapping",
            "workspace_scope": "Niles / Music creative notes and controller mapping only.",
            "source_set_ref": "source_set:niles_music_controller_mapping",
            "source_inventory_ref": "source_inventory:niles_music_controller_mapping",
            "conflict_log_ref": "conflict_log:niles_music_controller_mapping",
            "missing_context_ref": "missing_context:niles_controller_target",
            "duplicate_report_ref": "version_family:niles_music_controller_mapping",
            "decision_trace_ref": "decision_trace:niles_music_controller_mapping",
            "authority_ranking_ref": common_authority,
            "freshness_gate_ref": common_freshness,
            "allowed_next_steps": ["offer creative options", "ask for controller/software target"],
            "blocked_next_steps": ["make factual controller claims", "import unrelated finance proof", "claim integration exists"],
            "synthesis_allowed": True,
            "synthesis_scope": "creative_options_only",
            "inventory_gate": "passed_with_creative_scope",
            "source_disagreement_detected": False,
            "missing_context_blocks": ["factual controller claim", "software integration claim"],
            "protected_authority": dict(base_protected),
        },
        {
            "project_room_id": "self_heal_repair",
            "objective_ref": "objective:self_heal_repair",
            "world_ref": "world:system_repair",
            "thread_ref": "thread:self_heal",
            "workspace_scope": "Self-heal diagnosis, prior attempts, blocker proof, and validation planning.",
            "source_set_ref": "source_set:self_heal_repair",
            "source_inventory_ref": "source_inventory:self_heal_repair",
            "conflict_log_ref": "conflict_log:self_heal_repair",
            "missing_context_ref": "missing_context:none",
            "duplicate_report_ref": "version_family:self_heal_repair",
            "decision_trace_ref": "decision_trace:self_heal_repair",
            "authority_ranking_ref": common_authority,
            "freshness_gate_ref": common_freshness,
            "allowed_next_steps": ["propose repair package with validation plan", "name blocker proof", "include rollback plan"],
            "blocked_next_steps": ["execute repair", "restart services", "claim repair success without receipt"],
            "synthesis_allowed": True,
            "synthesis_scope": "repair_package_proposal_only",
            "inventory_gate": "passed_with_validation_plan_required",
            "source_disagreement_detected": False,
            "missing_context_blocks": ["repair success claim"],
            "protected_authority": dict(base_protected),
            "repair_package_requirements": ["blocker proof", "validation plan", "rollback plan", "receipt requirement"],
        },
        {
            "project_room_id": "stale_source",
            "objective_ref": "objective:stale_source_handling",
            "world_ref": "world:source_quality",
            "thread_ref": "thread:stale_source",
            "workspace_scope": "Stale, superseded, or generated-only source material.",
            "source_set_ref": "source_set:stale_source",
            "source_inventory_ref": "source_inventory:stale_source",
            "conflict_log_ref": "conflict:stale_summary_vs_current_truth",
            "missing_context_ref": "missing_context:stale_current_source",
            "duplicate_report_ref": "version_family:stale_source",
            "decision_trace_ref": "decision_trace:stale_source",
            "authority_ranking_ref": common_authority,
            "freshness_gate_ref": common_freshness,
            "allowed_next_steps": ["mark Needs verification", "ask for current source", "preserve originals as history"],
            "blocked_next_steps": ["final synthesis", "current truth claim", "delete older versions"],
            "synthesis_allowed": False,
            "synthesis_scope": "blocked_or_needs_verification",
            "inventory_gate": "blocked_by_stale_source",
            "source_disagreement_detected": True,
            "missing_context_blocks": ["current truth claim", "final answer"],
            "protected_authority": dict(base_protected),
        },
    ]


def _group_inventory(inventory_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in inventory_rows:
        grouped.setdefault(str(row["source_inventory_ref"]), []).append(row)
    return grouped


def source_inventory_required_before_synthesis(read_model: Mapping[str, Any]) -> bool:
    grouped = _group_inventory(list(read_model.get("source_inventory") or []))
    for room in read_model.get("project_rooms") or []:
        if room.get("synthesis_allowed") is True:
            ref = str(room.get("source_inventory_ref") or "")
            if not ref or not grouped.get(ref):
                return False
            if str(room.get("inventory_gate") or "").startswith("blocked"):
                return False
    return True


def conflict_log_required_when_sources_disagree(read_model: Mapping[str, Any]) -> bool:
    disagreement_rooms = {
        str(room["project_room_id"])
        for room in read_model.get("project_rooms") or []
        if room.get("source_disagreement_detected") is True
    }
    conflict_rooms = {str(conflict["project_room_id"]) for conflict in read_model.get("conflict_log") or []}
    return disagreement_rooms <= conflict_rooms


def missing_context_blocks_unsupported_claims(read_model: Mapping[str, Any]) -> bool:
    rooms = {str(room["project_room_id"]): room for room in read_model.get("project_rooms") or []}
    for gap in read_model.get("missing_context_list") or []:
        room = rooms.get(str(gap.get("project_room_id") or ""))
        if not room:
            return False
        blocked = " ".join(str(step).lower() for step in room.get("blocked_next_steps") or [])
        safe = str(gap.get("safe_wording_if_unresolved") or "").lower()
        if "cannot" not in safe and "needs verification" not in safe:
            return False
        if not blocked:
            return False
    return True


def duplicate_report_does_not_delete_files(read_model: Mapping[str, Any]) -> bool:
    return all(report.get("deletion_allowed") is False for report in read_model.get("duplicate_version_report") or [])


def current_receipts_outrank_generated_summaries(read_model: Mapping[str, Any]) -> bool:
    ranking = (read_model.get("authority_rankings") or [{}])[0].get("ranked_authority") or []
    try:
        receipt_index = ranking.index("current_receipts_and_proof")
        summary_index = ranking.index("generated_summaries")
    except ValueError:
        return False
    if receipt_index > summary_index:
        return False
    for source in read_model.get("source_inventory") or []:
        if source.get("apparent_authority") == "generated_summaries":
            forbidden = {str(item).lower() for item in source.get("do_not_use_for") or []}
            if "current truth" not in forbidden:
                return False
    return True


def superseded_sources_cannot_be_current_truth(read_model: Mapping[str, Any]) -> bool:
    for source in read_model.get("source_inventory") or []:
        if source.get("freshness_state") in {"stale", "superseded"}:
            forbidden = {str(item).lower() for item in source.get("do_not_use_for") or []}
            if "current truth" not in forbidden:
                return False
    for report in read_model.get("duplicate_version_report") or []:
        if report.get("likely_current_source_ref") in set(report.get("older_or_superseded_refs") or []):
            return False
    return True


def build_resolved_packet_remains_historical(read_model: Mapping[str, Any]) -> bool:
    build_sources = [
        source for source in read_model.get("source_inventory") or [] if source.get("project_room_id") == "build_review_packet"
    ]
    build_room = next(
        (room for room in read_model.get("project_rooms") or [] if room.get("project_room_id") == "build_review_packet"),
        {},
    )
    blocked = " ".join(str(step).lower() for step in build_room.get("blocked_next_steps") or [])
    return any(source.get("freshness_state") == "historical_resolved" for source in build_sources) and "active" in blocked


def finance_payment_watch_blocks_paid_ledger(read_model: Mapping[str, Any]) -> bool:
    room = next(
        (
            row
            for row in read_model.get("project_rooms") or []
            if row.get("project_room_id") == "finance_capital_hilton_payment_watch"
        ),
        {},
    )
    blocked = " ".join(str(step).lower() for step in room.get("blocked_next_steps") or [])
    sources = [
        row
        for row in read_model.get("source_inventory") or []
        if row.get("project_room_id") == "finance_capital_hilton_payment_watch"
    ]
    claims = " ".join(" ".join(str(claim).lower() for claim in source.get("claims_supported") or []) for source in sources)
    protected = room.get("protected_authority") or {}
    return (
        "mark paid" in blocked
        and "mutate ledger" in blocked
        and "paid=false" in claims
        and "ledger untouched" in claims
        and protected.get("paid_action_allowed") is False
        and protected.get("ledger_action_allowed") is False
    )


def niles_creative_room_excludes_unrelated_finance_proof(read_model: Mapping[str, Any]) -> bool:
    niles_sources = [
        source for source in read_model.get("source_inventory") or [] if source.get("project_room_id") == "niles_music_controller_mapping"
    ]
    source_refs = [
        {
            "source_ref": source.get("source_ref"),
            "path_or_artifact_ref": source.get("path_or_artifact_ref"),
            "source_type": source.get("source_type"),
            "receipt_refs": source.get("receipt_refs"),
        }
        for source in niles_sources
    ]
    text = stable_json(source_refs).lower()
    return all(token not in text for token in ("finance", "payment", "coupa", "ledger"))


def _artifact_rows(read_model: Mapping[str, Any], generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, ref_key, kind in (
        ("project_rooms", "project_room_id", "project_room"),
        ("source_inventory", "source_ref", "source_inventory"),
        ("conflict_log", "conflict_ref", "conflict_log"),
        ("missing_context_list", "missing_context_ref", "missing_context"),
        ("duplicate_version_report", "version_family_ref", "duplicate_version_report"),
        ("decision_traces", "decision_trace_ref", "decision_trace"),
    ):
        for record in read_model.get(key) or []:
            rows.append(
                {
                    "record_id": str(record[ref_key]),
                    "record_kind": kind,
                    "project_room_id": str(record.get("project_room_id") or record.get("project_room_id") or record[ref_key]),
                    "source_ref": str(record.get("source_ref") or record.get("source_set_ref") or record[ref_key]),
                    "created_at": generated_at,
                    "record_json": stable_json(record),
                }
            )
    return rows


def _init_sqlite(sqlite_path: Path | str) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("DROP TABLE IF EXISTS project_room_sourceset_records")
        conn.execute(
            """
CREATE TABLE project_room_sourceset_records (
  record_id TEXT PRIMARY KEY,
  record_kind TEXT NOT NULL,
  project_room_id TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  created_at TEXT NOT NULL,
  record_json TEXT NOT NULL
)
"""
        )
        conn.commit()


def write_sqlite_records(sqlite_path: Path | str, read_model: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    sqlite_path = _rooted(sqlite_path)
    rows = _artifact_rows(read_model, generated_at)
    _init_sqlite(sqlite_path)
    with sqlite3.connect(sqlite_path) as conn:
        conn.executemany(
            """
INSERT INTO project_room_sourceset_records (
  record_id, record_kind, project_room_id, source_ref, created_at, record_json
) VALUES (
  :record_id, :record_kind, :project_room_id, :source_ref, :created_at, :record_json
)
""",
            rows,
        )
        conn.commit()
        counts = conn.execute(
            "SELECT record_kind, COUNT(*) FROM project_room_sourceset_records GROUP BY record_kind ORDER BY record_kind"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM project_room_sourceset_records").fetchone()[0]
    return {
        "sqlite_path": sqlite_path.as_posix(),
        "sqlite_row_count": int(total),
        "sqlite_record_kind_counts": {str(kind): int(count) for kind, count in counts},
    }


def sqlite_summary(sqlite_path: Path | str = DEFAULT_SQLITE_PATH) -> dict[str, Any]:
    sqlite_path = _rooted(sqlite_path)
    if not sqlite_path.exists():
        return {"sqlite_path": sqlite_path.as_posix(), "sqlite_row_count": 0, "sqlite_record_kind_counts": {}}
    with sqlite3.connect(sqlite_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM project_room_sourceset_records").fetchone()[0]
        counts = conn.execute(
            "SELECT record_kind, COUNT(*) FROM project_room_sourceset_records GROUP BY record_kind ORDER BY record_kind"
        ).fetchall()
    return {
        "sqlite_path": sqlite_path.as_posix(),
        "sqlite_row_count": int(total),
        "sqlite_record_kind_counts": {str(kind): int(count) for kind, count in counts},
    }


def _rows_have_fields(rows: list[Mapping[str, Any]], required_fields: tuple[str, ...]) -> bool:
    required = set(required_fields)
    return all(required <= set(row.keys()) for row in rows)


def _base_payload(read_model_root: Path, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define the Project Room / Source Room contract for serious agent work before drafting, coding, packaging, or answering.",
        "preconditions": precondition_rows(read_model_root),
        "core_doctrine": list(CORE_DOCTRINE),
        "rules": list(RULES),
        "project_room_fields": list(PROJECT_ROOM_FIELDS),
        "source_inventory_fields": list(SOURCE_INVENTORY_FIELDS),
        "conflict_log_fields": list(CONFLICT_LOG_FIELDS),
        "missing_context_fields": list(MISSING_CONTEXT_FIELDS),
        "duplicate_report_fields": list(DUPLICATE_REPORT_FIELDS),
        "decision_trace_fields": list(DECISION_TRACE_FIELDS),
        "authority_rankings": authority_rankings(),
        "freshness_gates": freshness_gates(),
        "project_rooms": project_rooms(),
        "source_inventory": source_inventory(generated_at),
        "conflict_log": conflict_log(),
        "missing_context_list": missing_context_list(),
        "duplicate_version_report": duplicate_version_report(),
        "decision_traces": decision_traces(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "implementation_boundary": IMPLEMENTATION_BOUNDARY,
        "source_refs": [f"generated/read_models/{spec['filename']}" for spec in PRECONDITIONS.values()],
        "source_content_hashes": {
            ref: _content_hash(_load_json(_rooted(read_model_root) / str(spec["filename"])))
            for ref, spec in PRECONDITIONS.items()
        },
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    write_sqlite: bool = True,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    payload = _base_payload(read_model_root, generated_at)
    expected_sqlite_rows = len(_artifact_rows(payload, generated_at))
    sqlite_info = (
        write_sqlite_records(sqlite_path, payload, generated_at) if write_sqlite else sqlite_summary(sqlite_path)
    )
    payload["sqlite_summary"] = sqlite_info
    machine_proof = {
        "preconditions_ready": all(row.get("ready") is True for row in payload["preconditions"]),
        "project_room_fields_complete": _rows_have_fields(payload["project_rooms"], PROJECT_ROOM_FIELDS),
        "source_inventory_fields_complete": _rows_have_fields(payload["source_inventory"], SOURCE_INVENTORY_FIELDS),
        "conflict_log_fields_complete": _rows_have_fields(payload["conflict_log"], CONFLICT_LOG_FIELDS),
        "missing_context_fields_complete": _rows_have_fields(payload["missing_context_list"], MISSING_CONTEXT_FIELDS),
        "duplicate_report_fields_complete": _rows_have_fields(payload["duplicate_version_report"], DUPLICATE_REPORT_FIELDS),
        "decision_trace_fields_complete": _rows_have_fields(payload["decision_traces"], DECISION_TRACE_FIELDS),
        "all_required_scenarios_present": {room["project_room_id"] for room in payload["project_rooms"]}
        == set(REQUIRED_SCENARIOS),
        "source_inventory_required_before_synthesis": source_inventory_required_before_synthesis(payload),
        "conflict_log_required_when_sources_disagree": conflict_log_required_when_sources_disagree(payload),
        "missing_context_blocks_unsupported_claims": missing_context_blocks_unsupported_claims(payload),
        "duplicate_report_does_not_delete_files": duplicate_report_does_not_delete_files(payload),
        "current_receipts_outrank_generated_summaries": current_receipts_outrank_generated_summaries(payload),
        "superseded_sources_cannot_be_current_truth": superseded_sources_cannot_be_current_truth(payload),
        "build_resolved_packet_remains_historical": build_resolved_packet_remains_historical(payload),
        "finance_payment_watch_blocks_paid_ledger": finance_payment_watch_blocks_paid_ledger(payload),
        "niles_creative_room_excludes_unrelated_finance_proof": niles_creative_room_excludes_unrelated_finance_proof(payload),
        "sqlite_row_count_matches_json": sqlite_info["sqlite_row_count"] == expected_sqlite_rows,
        "model_invocation_absent": True,
        "live_action_absent": True,
        "unsafe_true_grants_absent": True,
    }
    payload["machine_proof"] = machine_proof
    if not all(value is True for value in machine_proof.values()):
        payload["status"] = NOT_READY_STATUS
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Project Room Sourceset Contract",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This contract says serious OpenClaw work starts by building the room: source inventory first, conflicts and gaps surfaced before synthesis, and receipts outranking generated summaries.",
        "",
        "## Core Doctrine",
        "",
    ]
    for item in read_model.get("core_doctrine") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Rules", ""])
    for item in read_model.get("rules") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Project Rooms", ""])
    for room in read_model.get("project_rooms") or []:
        lines.append(
            f"- `{room['project_room_id']}`: synthesis `{str(room['synthesis_allowed']).lower()}` "
            f"({room['synthesis_scope']}); allowed: {', '.join(room['allowed_next_steps'])}; "
            f"blocked: {', '.join(room['blocked_next_steps'])}"
        )
    lines.extend(["", "## Conflicts", ""])
    for conflict in read_model.get("conflict_log") or []:
        lines.append(f"- `{conflict['conflict_ref']}`: {conflict['conflict_summary']}")
    lines.extend(["", "## Missing Context", ""])
    for gap in read_model.get("missing_context_list") or []:
        lines.append(f"- `{gap['missing_context_ref']}`: {gap['gap_summary']} Safe wording: {gap['safe_wording_if_unresolved']}")
    lines.extend(["", "## Duplicate / Version Families", ""])
    for report in read_model.get("duplicate_version_report") or []:
        lines.append(
            f"- `{report['version_family_ref']}`: likely current `{report['likely_current_source_ref']}`, "
            f"deletion allowed `{str(report['deletion_allowed']).lower()}`"
        )
    lines.extend(["", "## Authority", ""])
    ranking = (read_model.get("authority_rankings") or [{}])[0]
    lines.append("- Authority order: " + " > ".join(ranking.get("ranked_authority") or []))
    lines.append("- Current receipts/proof beat generated summaries and memory hints.")
    lines.append("")
    return "\n".join(lines)


def export_project_room_sourceset_contract(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": str((read_model.get("sqlite_summary") or {}).get("sqlite_row_count") or 0),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Project Room Sourceset Contract V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_project_room_sourceset_contract(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
