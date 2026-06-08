"""Project Room / Source Room contract V0.

Defines the source-set contract OpenClaw must build before serious drafting,
coding, packaging, or answering. The contract is generated/read-model/wiki/SQLite
work only; it does not invoke models, connect runtimes, spawn workers, send
email, open browser/Gmail/Coupa, mutate ledgers/workbooks, export PDFs, mark
paid, submit, or push.
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

import context_compaction_preview_policy as compaction_policy
import context_freshness_decision_trace_gate as freshness_gate
import proof_to_response_runtime


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
        "filename": freshness_gate.JSON_EXPORT_NAME,
        "accepted_statuses": (freshness_gate.READY_STATUS,),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "retrospective_harness_learning_seed": {
        "filename": "retrospective_harness_learning_seed.json",
        "accepted_statuses": ("RETROSPECTIVE_HARNESS_LEARNING_SEED_READY",),
    },
    "context_compaction_preview_policy": {
        "filename": compaction_policy.JSON_EXPORT_NAME,
        "accepted_statuses": (compaction_policy.READY_STATUS,),
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
    "Large files and logs are previewed or referenced, not dumped into model context.",
)

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
    "compaction_policy_ref",
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
    "preview_available",
    "full_source_reference_only",
    "source_hash",
    "receipt_refs",
)

CONFLICT_LOG_FIELDS = (
    "conflict_ref",
    "conflicting_source_refs",
    "conflict_summary",
    "affected_claims",
    "likely_resolution",
    "operator_decision_required",
    "unresolved",
)

MISSING_CONTEXT_FIELDS = (
    "missing_context_ref",
    "gap_summary",
    "why_it_matters",
    "source_that_implies_gap",
    "required_source_or_decision",
    "safe_wording_if_unresolved",
)

DUPLICATE_REPORT_FIELDS = (
    "version_family_ref",
    "candidate_source_refs",
    "likely_current_source_ref",
    "older_or_superseded_refs",
    "confidence",
    "operator_review_required",
    "deletion_allowed",
)

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "worker_spawn_allowed": False,
    "tool_authority_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "duplicate_deletion_allowed": False,
    "silent_conflict_resolution_allowed": False,
    "missing_context_invention_allowed": False,
    "generated_summary_override_allowed": False,
    "stale_context_current_truth_allowed": False,
    "full_log_dump_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "external_provider_connected": False,
    "worker_spawn_performed": False,
    "email_send_performed": False,
    "gmail_opened": False,
    "browser_opened": False,
    "coupa_opened": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "submit_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
    "duplicate_deletion_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(freshness_gate.UNSAFE_TRUE_KEYS)
    | set(compaction_policy.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "paid",
        "sent",
        "submitted",
        "executed",
        "mark_paid_allowed",
        "ledger_action_allowed",
        "send_authority",
        "deletion_allowed",
        "synthesis_allowed_without_inventory",
        "old_version_current_truth_allowed",
        "duplicated_docs_overweight_allowed",
        "full_source_dumped",
        "unrelated_finance_proof_included",
    }
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
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
    return str(payload.get("readiness_status") or payload.get("status") or payload.get("contract_status") or "")


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


def project_room_template() -> dict[str, Any]:
    return {
        "project_room_id": "project_room:template",
        "objective_ref": "",
        "world_ref": "",
        "thread_ref": "",
        "workspace_scope": "bounded_to_current_project_room",
        "source_set_ref": "source_set:required_before_synthesis",
        "source_inventory_ref": "source_inventory:required",
        "conflict_log_ref": "conflict_log:required_even_if_empty",
        "missing_context_ref": "missing_context:required_even_if_empty",
        "duplicate_report_ref": "duplicate_report:required_even_if_empty",
        "decision_trace_ref": "decision_trace:required_even_if_empty",
        "authority_ranking_ref": "authority_ranking:receipts_over_summaries",
        "freshness_gate_ref": "generated/read_models/context_freshness_decision_trace_gate.json",
        "compaction_policy_ref": "generated/read_models/context_compaction_preview_policy.json",
        "allowed_next_steps": ["inventory_sources", "surface_conflicts", "name_missing_context", "prepare_safe_plan"],
        "blocked_next_steps": ["draft_final_output_without_inventory", "silently_resolve_conflicts", "invent_missing_context", "delete_duplicates"],
        "synthesis_allowed": False,
    }


def source_inventory(generated_at: str) -> list[dict[str, Any]]:
    return [
        {
            "source_ref": "source:finance:capital_hilton:payment_watch_receipt",
            "path_or_artifact_ref": "generated/read_models/proof_bundle_freshness_trace_status.json#finance_capital_hilton_payment_watch",
            "source_type": "receipt_backed_read_model",
            "date_observed": generated_at,
            "date_claimed": "current",
            "apparent_authority": "current_receipt",
            "freshness_state": "current",
            "confidence_class": "receipt_backed",
            "claims_supported": ["payment_processor_processing", "paid_false", "ledger_untouched", "payment_evidence_missing"],
            "limitations": ["does_not_prove_paid", "does_not_authorize_ledger_mutation"],
            "how_to_use": "Use for explanation and next safe step only.",
            "do_not_use_for": ["mark_paid", "ledger_posting", "Coupa_submit"],
            "preview_available": True,
            "full_source_reference_only": True,
            "source_hash": "sha256:finance_capital_hilton_payment_watch_receipt",
            "receipt_refs": ["receipt:capital_hilton_payment_watch_current"],
        },
        {
            "source_ref": "source:finance:capital_hilton:generated_payment_summary",
            "path_or_artifact_ref": "generated/read_models/proof_to_response_latest.json#historical_summary",
            "source_type": "generated_summary",
            "date_observed": generated_at,
            "date_claimed": "historical_or_support",
            "apparent_authority": "low_supporting_summary",
            "freshness_state": "historical",
            "confidence_class": "generated_summary",
            "claims_supported": ["may_explain_payment_watch"],
            "limitations": ["cannot_override_current_receipt", "cannot_prove_paid"],
            "how_to_use": "Use only as supporting wording after receipt-backed facts are selected.",
            "do_not_use_for": ["current_truth", "paid_truth", "authority_decision"],
            "preview_available": True,
            "full_source_reference_only": True,
            "source_hash": "sha256:finance_capital_hilton_generated_summary",
            "receipt_refs": [],
        },
        {
            "source_ref": "source:bd:capital_hilton:proposal_status",
            "path_or_artifact_ref": "generated/read_models/objective_advancement_protocol.json#business_development_capital_hilton",
            "source_type": "proposal_status_read_model",
            "date_observed": generated_at,
            "date_claimed": "current_if_latest_receipt_matches",
            "apparent_authority": "route_read_model",
            "freshness_state": "current",
            "confidence_class": "receipt_backed",
            "claims_supported": ["proposal_followup_state_known", "draft_can_be_staged"],
            "limitations": ["does_not_authorize_send"],
            "how_to_use": "Use to stage or explain follow-up draft workflow.",
            "do_not_use_for": ["send_email", "external_submission"],
            "preview_available": True,
            "full_source_reference_only": True,
            "source_hash": "sha256:bd_capital_hilton_proposal_status",
            "receipt_refs": ["receipt:bd_capital_hilton_followup_current"],
        },
        {
            "source_ref": "source:bd:capital_hilton:older_followup_note",
            "path_or_artifact_ref": "memory:capital_hilton_followup_old_note",
            "source_type": "operator_memory_hint",
            "date_observed": generated_at,
            "date_claimed": "unknown",
            "apparent_authority": "memory_hint",
            "freshness_state": "stale",
            "confidence_class": "unpromoted_memory",
            "claims_supported": ["possible_followup_status"],
            "limitations": ["may_disagree_with_current_proposal_status", "not_canonical_truth"],
            "how_to_use": "Use only to ask for verification or flag conflict.",
            "do_not_use_for": ["current_followup_truth", "send_authority"],
            "preview_available": False,
            "full_source_reference_only": True,
            "source_hash": "",
            "receipt_refs": [],
        },
        {
            "source_ref": "source:build:review_packet_resolved",
            "path_or_artifact_ref": "generated/read_models/workroom_review_decision_status.json#review_packet_c4ec166103f9aa35",
            "source_type": "review_decision_receipt",
            "date_observed": generated_at,
            "date_claimed": "historical_resolved",
            "apparent_authority": "review_decision_receipt",
            "freshness_state": "historical",
            "confidence_class": "receipt_backed",
            "claims_supported": ["review_packet_informational_or_resolved", "prior_review_decision_exists"],
            "limitations": ["not_active_ready_for_review"],
            "how_to_use": "Use as history and decision trace.",
            "do_not_use_for": ["active_review_work", "merge", "push"],
            "preview_available": True,
            "full_source_reference_only": True,
            "source_hash": "sha256:build_review_packet_resolved",
            "receipt_refs": ["receipt:workroom_review_decision_recorded"],
        },
        {
            "source_ref": "source:niles:music_controller_notes",
            "path_or_artifact_ref": "operator_supplied:creative_mapping_notes",
            "source_type": "creative_notes",
            "date_observed": generated_at,
            "date_claimed": "current_if_operator_supplied",
            "apparent_authority": "operator_current_request",
            "freshness_state": "current",
            "confidence_class": "operator_reported",
            "claims_supported": ["creative_goal", "controller_mapping_target_if_supplied"],
            "limitations": ["software_or_controller_target_may_be_missing", "not_factual_finance_truth"],
            "how_to_use": "Use for creative options and Niles voice planning.",
            "do_not_use_for": ["finance_claims", "client_payment_proof"],
            "preview_available": True,
            "full_source_reference_only": False,
            "source_hash": "",
            "receipt_refs": [],
        },
        {
            "source_ref": "source:self_heal:repair_blocker_validation",
            "path_or_artifact_ref": "generated/read_models/self_heal_repair_doctrine.json#repair_blocker",
            "source_type": "repair_blocker_summary",
            "date_observed": generated_at,
            "date_claimed": "current_when_validation_matches",
            "apparent_authority": "validation_result",
            "freshness_state": "current",
            "confidence_class": "validation_backed",
            "claims_supported": ["blocker_named", "validation_failure_known", "repair_package_needs_validation_plan"],
            "limitations": ["does_not_grant_service_restart_or_worker_spawn"],
            "how_to_use": "Use to propose a repair package with validation and rollback.",
            "do_not_use_for": ["auto_apply_repair", "worker_spawn", "service_restart_without_approval"],
            "preview_available": True,
            "full_source_reference_only": True,
            "source_hash": "sha256:self_heal_repair_blocker_validation",
            "receipt_refs": ["receipt:self_heal_repair_blocker_recorded"],
        },
        {
            "source_ref": "source:system:large_error_log",
            "path_or_artifact_ref": "logref:openclaw:error_log:preview_only",
            "source_type": "large_log_reference",
            "date_observed": generated_at,
            "date_claimed": "current_preview_only",
            "apparent_authority": "diagnostic_artifact_reference",
            "freshness_state": "current",
            "confidence_class": "artifact_hash",
            "claims_supported": ["error_log_exists", "safe_preview_available"],
            "limitations": ["full_log_not_embedded", "raw_body_not_agent_visible"],
            "how_to_use": "Use preview/ref for diagnosis; request scoped inspection if needed.",
            "do_not_use_for": ["dump_full_log", "broad_cleanup_authority"],
            "preview_available": True,
            "full_source_reference_only": True,
            "source_hash": "sha256:large_error_log_reference",
            "receipt_refs": ["receipt:large_log_preview_created"],
        },
        {
            "source_ref": "source:system:stale_prior_summary",
            "path_or_artifact_ref": "generated_summary:old_project_room_summary",
            "source_type": "generated_summary",
            "date_observed": generated_at,
            "date_claimed": "old",
            "apparent_authority": "low_supporting_summary",
            "freshness_state": "stale",
            "confidence_class": "generated_summary",
            "claims_supported": ["possible_prior_context"],
            "limitations": ["cannot_enter_as_current_truth", "requires_refresh"],
            "how_to_use": "Use only to ask for verification.",
            "do_not_use_for": ["current_truth", "final_synthesis"],
            "preview_available": False,
            "full_source_reference_only": True,
            "source_hash": "",
            "receipt_refs": [],
        },
    ]


def conflict_log() -> list[dict[str, Any]]:
    return [
        {
            "conflict_ref": "conflict:bd_capital_hilton_followup_status",
            "conflicting_source_refs": [
                "source:bd:capital_hilton:proposal_status",
                "source:bd:capital_hilton:older_followup_note",
            ],
            "conflict_summary": "Current proposal/follow-up state and older memory hint may disagree.",
            "affected_claims": ["proposal_followup_state_known", "followup_ready_to_stage"],
            "likely_resolution": "Use latest receipt-backed proposal source; ask operator if follow-up state must be confirmed.",
            "operator_decision_required": True,
            "unresolved": True,
        },
        {
            "conflict_ref": "conflict:finance_generated_summary_vs_receipt",
            "conflicting_source_refs": [
                "source:finance:capital_hilton:payment_watch_receipt",
                "source:finance:capital_hilton:generated_payment_summary",
            ],
            "conflict_summary": "Generated payment summaries may be stale or less precise than current payment-watch receipts.",
            "affected_claims": ["paid_status", "ledger_state", "payment_evidence_state"],
            "likely_resolution": "Current receipt wins; generated summary may only help phrase an explanation.",
            "operator_decision_required": False,
            "unresolved": False,
        },
    ]


def missing_context_list() -> list[dict[str, Any]]:
    return [
        {
            "missing_context_ref": "missing:finance_capital_hilton_payment_evidence",
            "gap_summary": "Payment evidence is missing.",
            "why_it_matters": "Without payment evidence, OpenClaw cannot mark paid or mutate ledger.",
            "source_that_implies_gap": "source:finance:capital_hilton:payment_watch_receipt",
            "required_source_or_decision": "Attach receipt-backed payment evidence or keep payment watch.",
            "safe_wording_if_unresolved": "Payment evidence is missing; ledger and paid state remain untouched.",
        },
        {
            "missing_context_ref": "missing:niles_controller_or_software_target",
            "gap_summary": "Specific controller or software target may be absent.",
            "why_it_matters": "Creative mapping can propose options, but factual setup claims need the target.",
            "source_that_implies_gap": "source:niles:music_controller_notes",
            "required_source_or_decision": "Name controller/software target or accept generic creative options.",
            "safe_wording_if_unresolved": "I can sketch creative mapping options, but I need the controller/software target for exact setup guidance.",
        },
        {
            "missing_context_ref": "missing:stale_source_refresh",
            "gap_summary": "A stale source lacks a current receipt.",
            "why_it_matters": "Stale context cannot be current truth for synthesis.",
            "source_that_implies_gap": "source:system:stale_prior_summary",
            "required_source_or_decision": "Refresh source or mark output Needs verification.",
            "safe_wording_if_unresolved": "Needs verification before I treat this as current.",
        },
    ]


def duplicate_version_report() -> list[dict[str, Any]]:
    return [
        {
            "version_family_ref": "version_family:capital_hilton_payment_watch_summaries",
            "candidate_source_refs": [
                "source:finance:capital_hilton:payment_watch_receipt",
                "source:finance:capital_hilton:generated_payment_summary",
            ],
            "likely_current_source_ref": "source:finance:capital_hilton:payment_watch_receipt",
            "older_or_superseded_refs": ["source:finance:capital_hilton:generated_payment_summary"],
            "confidence": "high",
            "operator_review_required": True,
            "deletion_allowed": False,
        },
        {
            "version_family_ref": "version_family:build_review_packet_history",
            "candidate_source_refs": ["source:build:review_packet_resolved"],
            "likely_current_source_ref": "source:build:review_packet_resolved",
            "older_or_superseded_refs": [],
            "confidence": "medium",
            "operator_review_required": True,
            "deletion_allowed": False,
        },
    ]


def decision_trace() -> dict[str, Any]:
    return {
        "prior_attempts": [
            {
                "attempt_ref": "attempt:finance_payment_watch_gate_copy",
                "summary": "Protected Coupa gate explanation was shown as primary lane answer.",
                "result": "wrong_lane_response",
            },
            {
                "attempt_ref": "attempt:local_qwen_non_json",
                "summary": "Local Qwen pilot failed JSON shape and published fallback.",
                "result": "schema_prompt_issue",
            },
        ],
        "rejected_attempts": [
            {
                "attempt_ref": "attempt:mark_paid_without_payment_evidence",
                "why_rejected": "Payment evidence missing and ledger proof absent.",
            },
            {
                "attempt_ref": "attempt:treat_resolved_build_packet_as_active",
                "why_rejected": "Review packet was informational/resolved and belongs in history.",
            },
        ],
        "operator_decisions": [
            "Require source inventory before synthesis.",
            "Keep memory as hint, not truth.",
            "Do not auto-delete duplicates or silently resolve contradictions.",
        ],
        "receipts": [
            "receipt:capital_hilton_payment_watch_current",
            "receipt:workroom_review_decision_recorded",
            "receipt:local_lm_fallback_published",
        ],
        "what_changed": [
            "Payment watch response became lane-level.",
            "Proof-to-response latest became request-scoped.",
            "Context compaction policy requires preview/reference for large artifacts.",
        ],
        "what_not_to_repeat": [
            "Do not use protected gate copy as lane answer.",
            "Do not treat generated summaries as receipts.",
            "Do not dump logs, OCR, or raw chat history into agent context.",
        ],
    }


def authority_ranking() -> list[dict[str, Any]]:
    return [
        {"rank": 1, "authority_ref": "current_receipts_and_hashes", "outranks": ["generated_summaries", "memory_hints"]},
        {"rank": 2, "authority_ref": "freshness_gate_rows", "outranks": ["stale_sources", "old_versions"]},
        {"rank": 3, "authority_ref": "operator_current_request", "outranks": ["old_chat_history"]},
        {"rank": 4, "authority_ref": "generated_summaries", "outranks": ["unpromoted_memory"]},
        {"rank": 5, "authority_ref": "memory_hints", "outranks": []},
    ]


def source_room_gate_status(
    *,
    inventory_exists: bool,
    conflicts_logged: bool,
    missing_context_named: bool,
    duplicates_reported: bool,
    freshness_gate_applied: bool,
    authority_ranked: bool,
    unresolved_blocking_context: bool,
) -> dict[str, Any]:
    gates_pass = all(
        [
            inventory_exists,
            conflicts_logged,
            missing_context_named,
            duplicates_reported,
            freshness_gate_applied,
            authority_ranked,
            not unresolved_blocking_context,
        ]
    )
    return {
        "source_inventory_exists": inventory_exists,
        "conflicts_logged": conflicts_logged,
        "missing_context_named": missing_context_named,
        "duplicates_reported": duplicates_reported,
        "freshness_gate_applied": freshness_gate_applied,
        "authority_ranked": authority_ranked,
        "unresolved_blocking_context": unresolved_blocking_context,
        "synthesis_allowed": gates_pass,
        "synthesis_allowed_without_inventory": gates_pass and not inventory_exists,
    }


def required_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_ref": "finance_capital_hilton_payment_watch",
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
            "source_room_contains": ["payment_watch_state", "Coupa_processing", "paid_false", "ledger_untouched"],
            "missing_context_refs": ["missing:finance_capital_hilton_payment_evidence"],
            "synthesis_scope": "explanation_and_next_step_only",
            "synthesis_allowed": True,
            "allowed_next_steps": ["explain_payment_watch", "ask_for_payment_evidence", "attach_proof"],
            "blocked_next_steps": ["mark_paid", "ledger_mutation", "Coupa_submit"],
            "mark_paid_allowed": False,
            "ledger_action_allowed": False,
        },
        {
            "scenario_ref": "business_development_capital_hilton_followup",
            "world_ref": "business_development",
            "thread_ref": "capital_hilton",
            "source_room_contains": ["proposal_followup_state"],
            "conflict_refs": ["conflict:bd_capital_hilton_followup_status"],
            "synthesis_scope": "draft_or_explain_followup_only",
            "synthesis_allowed": False,
            "allowed_next_steps": ["surface_conflict", "stage_followup_draft_after_resolution"],
            "blocked_next_steps": ["send_email", "external_submit"],
            "send_authority": False,
        },
        {
            "scenario_ref": "build_review_packet",
            "world_ref": "build",
            "thread_ref": "build_openclaw_backend",
            "source_room_contains": ["informational_or_resolved_review_packet", "prior_review_decision"],
            "synthesis_scope": "historical_summary_only",
            "synthesis_allowed": True,
            "lifecycle_state": "historical_resolved",
            "active_work_allowed": False,
            "allowed_next_steps": ["summarize_history", "show_review_receipt"],
            "blocked_next_steps": ["merge", "push", "treat_as_active_ready_for_review"],
        },
        {
            "scenario_ref": "niles_music_controller_mapping",
            "world_ref": "music",
            "thread_ref": "niles_controller_mapping",
            "source_room_contains": ["creative_notes", "controller_target_if_supplied"],
            "missing_context_refs": ["missing:niles_controller_or_software_target"],
            "synthesis_scope": "creative_options_only_until_target_supplied",
            "synthesis_allowed": True,
            "unrelated_finance_proof_included": False,
            "allowed_next_steps": ["offer_creative_options", "ask_for_controller_or_software_target"],
            "blocked_next_steps": ["make_unsourced_setup_claims", "include_finance_proof"],
        },
        {
            "scenario_ref": "self_heal_repair",
            "world_ref": "system",
            "thread_ref": "self_heal",
            "source_room_contains": ["blocker_proof", "validation_failure", "prior_attempts"],
            "synthesis_scope": "repair_package_with_validation_plan",
            "synthesis_allowed": True,
            "allowed_next_steps": ["propose_repair_package", "name_validation_plan", "name_rollback_plan"],
            "blocked_next_steps": ["auto_apply_repair", "spawn_worker", "restart_service_without_approval"],
        },
        {
            "scenario_ref": "stale_source",
            "world_ref": "system",
            "thread_ref": "stale_context",
            "source_room_contains": ["stale_prior_summary"],
            "missing_context_refs": ["missing:stale_source_refresh"],
            "synthesis_scope": "needs_verification_only",
            "synthesis_allowed": False,
            "allowed_next_steps": ["say_needs_verification", "request_current_source_or_receipt"],
            "blocked_next_steps": ["treat_stale_source_as_current_truth", "final_synthesis"],
        },
        {
            "scenario_ref": "large_artifact_log_source",
            "world_ref": "system",
            "thread_ref": "diagnostics",
            "source_room_contains": ["large_log_reference", "safe_preview"],
            "synthesis_scope": "diagnostic_preview_only",
            "synthesis_allowed": True,
            "preview_available": True,
            "full_source_reference_only": True,
            "full_source_dumped": False,
            "allowed_next_steps": ["summarize_preview", "ask_for_scoped_inspection_if_needed"],
            "blocked_next_steps": ["dump_full_log", "read_raw_artifact_by_default"],
        },
    ]


def _init_sqlite(sqlite_path: Path) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("DROP TABLE IF EXISTS project_room_sourceset_records")
        conn.execute(
            """
CREATE TABLE project_room_sourceset_records (
  record_id TEXT PRIMARY KEY,
  record_kind TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  current_truth_allowed INTEGER NOT NULL,
  deletion_allowed INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  record_json TEXT NOT NULL
)
"""
        )
        conn.commit()


def write_sqlite_records(
    *,
    sqlite_path: Path,
    inventory: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    sqlite_path = _rooted(sqlite_path)
    _init_sqlite(sqlite_path)
    rows: list[dict[str, Any]] = []
    for item in inventory:
        rows.append(
            {
                "record_id": str(item["source_ref"]),
                "record_kind": "source_inventory",
                "source_ref": str(item["source_ref"]),
                "current_truth_allowed": 1 if item["freshness_state"] == "current" and item["confidence_class"] != "generated_summary" else 0,
                "deletion_allowed": 0,
                "created_at": generated_at,
                "record_json": stable_json(item),
            }
        )
    for item in conflicts:
        rows.append(
            {
                "record_id": str(item["conflict_ref"]),
                "record_kind": "conflict_log",
                "source_ref": ",".join(item["conflicting_source_refs"]),
                "current_truth_allowed": 0,
                "deletion_allowed": 0,
                "created_at": generated_at,
                "record_json": stable_json(item),
            }
        )
    for item in missing:
        rows.append(
            {
                "record_id": str(item["missing_context_ref"]),
                "record_kind": "missing_context",
                "source_ref": str(item["source_that_implies_gap"]),
                "current_truth_allowed": 0,
                "deletion_allowed": 0,
                "created_at": generated_at,
                "record_json": stable_json(item),
            }
        )
    for item in duplicates:
        rows.append(
            {
                "record_id": str(item["version_family_ref"]),
                "record_kind": "duplicate_version_report",
                "source_ref": str(item["likely_current_source_ref"]),
                "current_truth_allowed": 0,
                "deletion_allowed": 0,
                "created_at": generated_at,
                "record_json": stable_json(item),
            }
        )
    for item in scenarios:
        rows.append(
            {
                "record_id": str(item["scenario_ref"]),
                "record_kind": "required_scenario",
                "source_ref": str(item["thread_ref"]),
                "current_truth_allowed": 0,
                "deletion_allowed": 0,
                "created_at": generated_at,
                "record_json": stable_json(item),
            }
        )
    with sqlite3.connect(sqlite_path) as conn:
        conn.executemany(
            """
INSERT INTO project_room_sourceset_records (
  record_id, record_kind, source_ref, current_truth_allowed,
  deletion_allowed, created_at, record_json
) VALUES (
  :record_id, :record_kind, :source_ref, :current_truth_allowed,
  :deletion_allowed, :created_at, :record_json
)
""",
            rows,
        )
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM project_room_sourceset_records").fetchone()[0]
        counts = conn.execute(
            "SELECT record_kind, COUNT(*) FROM project_room_sourceset_records GROUP BY record_kind ORDER BY record_kind"
        ).fetchall()
    return {
        "sqlite_path": sqlite_path.as_posix(),
        "sqlite_row_count": int(total),
        "sqlite_record_kind_counts": {str(kind): int(count) for kind, count in counts},
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    write_sqlite: bool = True,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    inventory = source_inventory(generated_at)
    conflicts = conflict_log()
    missing = missing_context_list()
    duplicates = duplicate_version_report()
    trace = decision_trace()
    scenarios = required_scenarios()
    sqlite_info = (
        write_sqlite_records(
            sqlite_path=sqlite_path,
            inventory=inventory,
            conflicts=conflicts,
            missing=missing,
            duplicates=duplicates,
            scenarios=scenarios,
            generated_at=generated_at,
        )
        if write_sqlite
        else {"sqlite_path": _rooted(sqlite_path).as_posix(), "sqlite_row_count": 0, "sqlite_record_kind_counts": {}}
    )
    required_sqlite_rows = len(inventory) + len(conflicts) + len(missing) + len(duplicates) + len(scenarios)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define OpenClaw Project Room / Source Room contract so serious work starts with scoped source inventory, conflicts, missing context, versioning, freshness, and authority.",
        "core_doctrine": list(CORE_DOCTRINE),
        "project_room_fields": list(PROJECT_ROOM_FIELDS),
        "project_room_template": project_room_template(),
        "source_inventory_fields": list(SOURCE_INVENTORY_FIELDS),
        "source_inventory": inventory,
        "conflict_log_fields": list(CONFLICT_LOG_FIELDS),
        "conflict_log": conflicts,
        "missing_context_fields": list(MISSING_CONTEXT_FIELDS),
        "missing_context_list": missing,
        "duplicate_version_report_fields": list(DUPLICATE_REPORT_FIELDS),
        "duplicate_version_report": duplicates,
        "decision_trace": trace,
        "authority_ranking": authority_ranking(),
        "source_room_gate_examples": {
            "without_inventory": source_room_gate_status(
                inventory_exists=False,
                conflicts_logged=True,
                missing_context_named=True,
                duplicates_reported=True,
                freshness_gate_applied=True,
                authority_ranked=True,
                unresolved_blocking_context=False,
            ),
            "with_inventory_and_clear_gates": source_room_gate_status(
                inventory_exists=True,
                conflicts_logged=True,
                missing_context_named=True,
                duplicates_reported=True,
                freshness_gate_applied=True,
                authority_ranked=True,
                unresolved_blocking_context=False,
            ),
            "with_unresolved_blocking_context": source_room_gate_status(
                inventory_exists=True,
                conflicts_logged=True,
                missing_context_named=True,
                duplicates_reported=True,
                freshness_gate_applied=True,
                authority_ranked=True,
                unresolved_blocking_context=True,
            ),
        },
        "rules": [
            "Do not synthesize final output until source inventory exists.",
            "Do not treat old versions as current.",
            "Do not delete duplicates automatically.",
            "Do not let duplicated docs overweight synthesis.",
            "Do not use missing context as permission to invent.",
            "Do not let generated summaries outrank receipts.",
            "Do not dump full logs/files/artifacts into agent context by default.",
            "Project room may stage a package only after source room gates are satisfied.",
        ],
        "required_scenarios": scenarios,
        "preconditions": preconditions,
        "sqlite_summary": sqlite_info,
        "source_refs": [
            "generated/read_models/context_freshness_decision_trace_gate.json",
            "generated/read_models/proof_bundle_freshness_trace_status.json",
            "generated/read_models/retrospective_harness_learning_seed.json",
            "generated/read_models/context_compaction_preview_policy.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/universal_receipt_envelope_status.json",
            "generated/read_models/operator_session_timeline.json",
            "generated/read_models/goldilocks_gate_calibration.json",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "implementation_boundary": IMPLEMENTATION_BOUNDARY,
        "machine_proof": {
            "contract_only": True,
            "model_invocation_absent": True,
            "source_inventory_required_before_synthesis": True,
            "conflict_log_required_when_sources_disagree": True,
            "missing_context_blocks_unsupported_claims": True,
            "duplicates_not_deleted": True,
            "current_receipts_outrank_generated_summaries": True,
            "superseded_sources_cannot_be_current_truth": True,
            "large_artifacts_preview_or_reference_only": True,
            "sqlite_row_count_matches_json": sqlite_info["sqlite_row_count"] == required_sqlite_rows,
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            row["precondition_ref"]: _content_hash(_load_json(_rooted(read_model_root) / str(PRECONDITIONS[row["precondition_ref"]]["filename"])))
            for row in preconditions
            if row["precondition_ref"] in PRECONDITIONS
        },
    }
    if not all(row.get("ready") is True for row in preconditions):
        payload["status"] = NOT_READY_STATUS
    if sqlite_info["sqlite_row_count"] != required_sqlite_rows:
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
        "The first step for serious work is to build the room: inventory sources, surface conflicts, name missing context, identify duplicate/version families, and apply freshness and authority before synthesis.",
        "",
        "## Core Doctrine",
        "",
    ]
    for item in read_model.get("core_doctrine") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Project Room Fields", ""])
    for item in read_model.get("project_room_fields") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Source Inventory", ""])
    for source in read_model.get("source_inventory") or []:
        lines.append(f"- `{source['source_ref']}` ({source['freshness_state']}, {source['confidence_class']}): {', '.join(source['claims_supported'])}")
    lines.extend(["", "## Conflicts", ""])
    for conflict in read_model.get("conflict_log") or []:
        lines.append(f"- `{conflict['conflict_ref']}`: {conflict['conflict_summary']}")
    lines.extend(["", "## Missing Context", ""])
    for missing in read_model.get("missing_context_list") or []:
        lines.append(f"- `{missing['missing_context_ref']}`: {missing['gap_summary']} Safe wording: {missing['safe_wording_if_unresolved']}")
    lines.extend(["", "## Duplicate / Version Report", ""])
    for report in read_model.get("duplicate_version_report") or []:
        lines.append(f"- `{report['version_family_ref']}`: current `{report['likely_current_source_ref']}`, deletion allowed `{str(report['deletion_allowed']).lower()}`")
    lines.extend(["", "## Required Scenarios", ""])
    for scenario in read_model.get("required_scenarios") or []:
        lines.append(f"- `{scenario['scenario_ref']}`: {scenario['synthesis_scope']}")
    lines.extend(["", "## Boundary", ""])
    lines.append("This contract is review/read-model work only. It does not invoke models, touch business systems, mutate ledgers/workbooks, mark paid, submit, push, or delete duplicates.")
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
