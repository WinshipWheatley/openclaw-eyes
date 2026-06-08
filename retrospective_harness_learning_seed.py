"""Retrospective harness learning seed V0.

This module publishes the first review-only learning seed for OpenClaw
retrospectives. It records failure classes, decision traces, and candidate
harness updates without invoking models, connecting runtimes, spawning workers,
touching business systems, or applying self-modifying behavior.
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

import context_freshness_decision_trace_gate as freshness_gate
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Retrospective Harness Learning Seed.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/retrospective_harness_learning_seed.sqlite")

SCHEMA_VERSION = "retrospective_harness_learning_seed_v0"
READ_MODEL_ID = "retrospective_harness_learning_seed"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "RETROSPECTIVE_HARNESS_LEARNING_SEED_READY"
NOT_READY_STATUS = "RETROSPECTIVE_HARNESS_LEARNING_SEED_NOT_READY"

PRECONDITIONS = {
    "context_freshness_decision_trace_gate": {
        "filename": freshness_gate.JSON_EXPORT_NAME,
        "accepted_statuses": (freshness_gate.READY_STATUS,),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "operator_session_timeline": {
        "filename": "operator_session_timeline.json",
        "accepted_statuses": ("OPERATOR_SESSION_TIMELINE_READY",),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "proof_to_response_runtime": {
        "filename": proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (proof_to_response_runtime.READY_STATUS,),
    },
    "proof_to_response_schema_adapter": {
        "filename": "proof_to_response_schema_adapter_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY",),
    },
    "local_lm_proof_response_pilot_postmortem": {
        "filename": "local_lm_proof_response_pilot_postmortem.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY",),
    },
    "self_heal_repair_doctrine": {
        "filename": "self_heal_repair_doctrine.json",
        "accepted_statuses": ("SELF_HEAL_REPAIR_DOCTRINE_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
}

TRAJECTORY_SOURCE_REFS = (
    "controller_events",
    "proof_to_response_attempts",
    "verifier_failures",
    "fallback_receipts",
    "workroom_review_decisions",
    "operator_session_timeline",
    "self_heal_repair_records",
    "stale_context_blocks",
)

FAILURE_CLASS_REFS = (
    "stale_context",
    "non_json_model_output",
    "unsupported_claim",
    "wrong_lane_response",
    "missing_proof",
    "overbroad_context",
    "protected_action_attempt",
    "tool_not_allowed",
    "premature_completion",
    "repeated_work_without_new_proof",
)

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "live_self_optimization_allowed": False,
    "auto_apply_allowed": False,
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
    "memory_promotion_allowed": False,
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
    "memory_promotion_performed": False,
    "self_modification_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(freshness_gate.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "approved",
        "paid",
        "sent",
        "submitted",
        "executed",
        "business_action_performed",
        "live_self_optimization_performed",
        "candidate_update_auto_applied",
        "generated_summary_overrode_receipt",
        "stale_context_entered_as_current_truth",
        "unpromoted_memory_used_as_truth",
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


def trajectory_sources() -> list[dict[str, Any]]:
    return [
        {
            "source_ref": "controller_events",
            "description": "Verified controller gestures, selected card/action refs, world/thread context, and route outcomes.",
            "allowed_use": "Identify route shape, lane, event type, and whether the response matched the selected context.",
            "raw_history_policy": "summarize_only",
        },
        {
            "source_ref": "proof_to_response_attempts",
            "description": "Candidate response attempts, adapter results, verifier results, and published fallback decisions.",
            "allowed_use": "Classify response quality, schema compliance, unsupported claims, and fallback behavior.",
            "raw_history_policy": "hide_raw_drafts_by_default",
        },
        {
            "source_ref": "verifier_failures",
            "description": "Deterministic rejection reasons from proof-to-response verifier and schema adapter.",
            "allowed_use": "Separate truth failures from shape, concision, or jargon failures.",
            "raw_history_policy": "preserve_error_codes",
        },
        {
            "source_ref": "fallback_receipts",
            "description": "Receipts proving a safe fallback was published when a draft was blocked.",
            "allowed_use": "Confirm fail-closed behavior and avoid reusing unsafe drafts.",
            "raw_history_policy": "preserve_receipt_refs",
        },
        {
            "source_ref": "workroom_review_decisions",
            "description": "Review decisions such as informational, request rework, approve, or deny.",
            "allowed_use": "Track packet lifecycle and avoid presenting resolved review work as active.",
            "raw_history_policy": "summarize_decision_only",
        },
        {
            "source_ref": "operator_session_timeline",
            "description": "Scene-level timeline events across worlds, lanes, cards, receipts, evidence, and review decisions.",
            "allowed_use": "Recover high-signal sequence without raw chat dumps.",
            "raw_history_policy": "no_raw_prompt_dumps",
        },
        {
            "source_ref": "self_heal_repair_records",
            "description": "Repair packages, blockers, validation results, and manual operator steps.",
            "allowed_use": "Learn smallest safe repair loops without black-box self-modification.",
            "raw_history_policy": "preserve_blocker_and_validation",
        },
        {
            "source_ref": "stale_context_blocks",
            "description": "Context freshness decisions that blocked stale, superseded, generated-only, or untraceable truth.",
            "allowed_use": "Demote stale context and route toward refresh/verification.",
            "raw_history_policy": "preserve_gate_reason",
        },
    ]


def failure_classes() -> list[dict[str, Any]]:
    definitions = {
        "stale_context": "A response or card relied on historical, superseded, unresolved, or untraceable context as if it were current.",
        "non_json_model_output": "A model response failed the required JSON/schema shape before factual verification could run.",
        "unsupported_claim": "A draft claimed paid, sent, submitted, executed, or another fact not supported by current proof.",
        "wrong_lane_response": "A response was safe in isolation but scoped to the wrong world, thread, card, gate, or objective.",
        "missing_proof": "The requested outcome needs evidence, receipt, or approval that is absent.",
        "overbroad_context": "Too much raw, private, or unrelated context entered a prompt, composer, or proof bundle.",
        "protected_action_attempt": "A route or draft tried to execute or promise a protected action without the required gate.",
        "tool_not_allowed": "A path needed or attempted a tool/runtime/resource outside the current authority boundary.",
        "premature_completion": "A task, response, or card marked work complete before proof, receipt, or validation supported completion.",
        "repeated_work_without_new_proof": "The system retried the same path without new evidence, changed context, or a new validation result.",
    }
    return [
        {
            "failure_class": ref,
            "definition": definitions[ref],
            "decision_trace_required": True,
            "candidate_update_allowed": "review_only",
            "auto_apply_allowed": False,
        }
        for ref in FAILURE_CLASS_REFS
    ]


def decision_trace_fields() -> list[str]:
    return [
        "what_was_attempted",
        "why_it_failed",
        "what_proof_said",
        "what_operator_decided",
        "what_receipt_was_recorded",
        "what_changed_afterward",
        "same_failure_recurred",
    ]


def required_examples() -> list[dict[str, Any]]:
    return [
        {
            "example_ref": "local_qwen_non_json_failure",
            "failure_class": "non_json_model_output",
            "issue_type": "schema_prompt_issue",
            "truth_issue": False,
            "trajectory_sources": ["proof_to_response_attempts", "verifier_failures", "fallback_receipts"],
            "decision_trace": {
                "what_was_attempted": "A one-time local Qwen proof-to-response pilot tried to draft Finance / Capital Hilton response text from a redacted freshness-gated proof bundle.",
                "why_it_failed": "The saved draft did not satisfy the required JSON response shape, so schema adaptation/verifier publication failed before factual truth checks could pass.",
                "what_proof_said": "Payment evidence was missing, payment processing was still processing, paid was false, and the ledger remained untouched.",
                "what_operator_decided": "Record a postmortem, require JSON-only schema prompting with a valid example, and require separate approval before any retry.",
                "what_receipt_was_recorded": "fallback_receipt and verifier_fail receipt in the local LM pilot/postmortem artifacts.",
                "what_changed_afterward": "Schema adapter and retry approval packets were created; verifier/fallback remained mandatory.",
                "same_failure_recurred": "not_yet_retested_by_this_seed",
            },
            "lesson": "Treat this as a schema/prompt issue, not a proof-truth issue. Do not loosen truth or authority checks to make the model pass.",
            "memory_status": "receipt_backed_lesson",
        },
        {
            "example_ref": "finance_payment_watch_wrong_coupa_gate_routing",
            "failure_class": "wrong_lane_response",
            "issue_type": "context_scoping_issue",
            "truth_issue": False,
            "trajectory_sources": ["controller_events", "proof_to_response_attempts", "stale_context_blocks"],
            "decision_trace": {
                "what_was_attempted": "Finance / Capital Hilton Ask Why surfaced the protected Coupa gate explanation as the primary lane answer.",
                "why_it_failed": "The gate response was safe but scoped too narrowly to protected Coupa submit detail rather than the payment-watch lane.",
                "what_proof_said": "The lane needed payment evidence while Coupa processing continued; paid marking and ledger mutation remained blocked.",
                "what_operator_decided": "Create lane-level payment-watch proof responses and expose lane-level ask_why, advance_objective, and attach_proof controls.",
                "what_receipt_was_recorded": "Controller/proof-to-response route and controller-map read models after payment watch fixes.",
                "what_changed_afterward": "Lane-level proof-to-response became primary; Coupa gate copy remained available only as gate-specific detail.",
                "same_failure_recurred": "should_be_detected_by_lane_scope_tests",
            },
            "lesson": "Safe copy can still be wrong if it is scoped to the wrong gate or lane.",
            "memory_status": "receipt_backed_lesson",
        },
        {
            "example_ref": "evidence_picker_file_path_leak_into_composer",
            "failure_class": "overbroad_context",
            "issue_type": "privacy_context_boundary_issue",
            "truth_issue": False,
            "trajectory_sources": ["controller_events", "operator_session_timeline", "self_heal_repair_records"],
            "decision_trace": {
                "what_was_attempted": "Evidence picker state leaked a raw local file path into a composer-facing context.",
                "why_it_failed": "The composer needed a protected artifact ref or redacted summary, not a raw path that could expose private machine context.",
                "what_proof_said": "Evidence intake and proof-bundle redaction policy allow artifact refs and redacted summaries while keeping raw paths out unless explicitly needed and redacted.",
                "what_operator_decided": "Keep path-bearing details behind proof/developer detail and use artifact refs in operator-facing text.",
                "what_receipt_was_recorded": "Evidence intake/proof-bundle redaction and later route smoke artifacts.",
                "what_changed_afterward": "Future bundles must exclude raw request paths and raw artifact/OCR text by default.",
                "same_failure_recurred": "unknown",
            },
            "lesson": "Composer and LM-visible context should receive proof refs and redacted summaries, not raw filesystem traces.",
            "memory_status": "operator_reported_needs_receipt_link",
        },
        {
            "example_ref": "stale_build_review_packet_ready_for_review",
            "failure_class": "stale_context",
            "issue_type": "lifecycle_freshness_issue",
            "truth_issue": False,
            "trajectory_sources": ["workroom_review_decisions", "operator_session_timeline", "stale_context_blocks"],
            "decision_trace": {
                "what_was_attempted": "A resolved or informational Build review packet was still shown like active ready-for-review work.",
                "why_it_failed": "Lifecycle and freshness state were not treated as the primary context gate for the card/response.",
                "what_proof_said": "Resolved or informational packets should be historical/resolved and hidden from active review unless reopened by a current receipt.",
                "what_operator_decided": "Normalize review context inference and keep resolved cards behind lifecycle/history policy.",
                "what_receipt_was_recorded": "Workroom review decision receipts and lifecycle/status read models.",
                "what_changed_afterward": "Build review context was inferable from selected packet/card, and unresolved context returns a human Needs lane context card.",
                "same_failure_recurred": "should_be_detected_by_lifecycle_tests",
            },
            "lesson": "Lifecycle/freshness beats generated summaries and stale UI memory.",
            "memory_status": "receipt_backed_lesson",
        },
        {
            "example_ref": "proof_to_response_wrong_lane_linger",
            "failure_class": "wrong_lane_response",
            "issue_type": "context_scoping_issue",
            "truth_issue": False,
            "trajectory_sources": ["controller_events", "proof_to_response_attempts", "fallback_receipts"],
            "decision_trace": {
                "what_was_attempted": "A Business Development response was generated safely, but proof_to_response_latest still looked like Finance / Capital Hilton.",
                "why_it_failed": "The latest read model lacked sufficient request-scoped freshness and context fields, so stale lane state could linger.",
                "what_proof_said": "Every controller response needs request-scoped proof_to_response and latest must match the last successful active lane/request.",
                "what_operator_decided": "Scope proof-to-response by request and mark latest stale on context mismatch.",
                "what_receipt_was_recorded": "Proof-to-response scoped response read models and bridge copies.",
                "what_changed_afterward": "Responses embed request-scoped proof_to_response and latest includes source_request_id, world_ref, thread_ref, and stale-if-mismatch fields.",
                "same_failure_recurred": "should_be_detected_by_latest_context_tests",
            },
            "lesson": "Latest read models are support state, not truth, unless their context matches the active request.",
            "memory_status": "receipt_backed_lesson",
        },
        {
            "example_ref": "remote_desktop_trace_log_leak_self_heal",
            "failure_class": "tool_not_allowed",
            "issue_type": "resource_self_heal_case",
            "truth_issue": False,
            "trajectory_sources": ["self_heal_repair_records", "operator_session_timeline", "stale_context_blocks"],
            "decision_trace": {
                "what_was_attempted": "Remote Desktop trace/log resource context became relevant to self-heal diagnosis.",
                "why_it_failed": "Raw trace logs are noisy and can leak resource, path, or session details if treated as operator-facing memory.",
                "what_proof_said": "Self-heal doctrine requires blocker name, proof, safe action now, action not allowed yet, smallest manual step, validation, and receipt.",
                "what_operator_decided": "Preserve high-signal blocker/validation lessons while hiding raw logs unless explicitly requested.",
                "what_receipt_was_recorded": "Self-heal/resource case should record a repair candidate rather than auto-apply or expose raw log history.",
                "what_changed_afterward": "This seed classifies trace log handling as a self-heal resource boundary lesson.",
                "same_failure_recurred": "unknown",
            },
            "lesson": "Trace logs should feed repair summaries and receipts, not raw operator or LM-visible history.",
            "memory_status": "operator_reported_needs_receipt_link",
        },
    ]


def candidate_harness_updates(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updates_by_example = {
        "local_qwen_non_json_failure": {
            "proposed_fix": "Add JSON-only prompt/schema adapter fixture checks before any approved local model retry.",
            "affected_component": "proof_to_response_schema_adapter",
            "validation_plan": "Replay saved non-JSON output and a valid JSON fixture; verify fallback remains mandatory on parse failure.",
            "rollback_plan": "Remove schema-adapter prompt fixture wiring and continue shadow-only deterministic responses.",
        },
        "finance_payment_watch_wrong_coupa_gate_routing": {
            "proposed_fix": "Prefer lane-level payment-watch intent when selected context is current-focus/payment-watch; keep Coupa gate detail scoped to gate controls.",
            "affected_component": "operator_controller_event_router",
            "validation_plan": "Run lane ask_why and gate ask_why fixtures and assert the primary text differs by control scope.",
            "rollback_plan": "Disable lane-level override and fall back to existing gate detail while marking Needs lane context.",
        },
        "evidence_picker_file_path_leak_into_composer": {
            "proposed_fix": "Normalize composer-visible evidence references to artifact refs and redacted summaries.",
            "affected_component": "proof_bundle_builder",
            "validation_plan": "Run redaction tests with path-bearing evidence picker fixtures and assert raw paths are absent.",
            "rollback_plan": "Block proof-to-response publishing for path-bearing evidence until manual redaction is confirmed.",
        },
        "stale_build_review_packet_ready_for_review": {
            "proposed_fix": "Gate Build review visibility on lifecycle/freshness state and latest review decision receipt.",
            "affected_component": "dynamic_card_lifecycle_policy",
            "validation_plan": "Run resolved/informational review packet fixtures and assert active review controls are hidden.",
            "rollback_plan": "Hide ambiguous Build review packets behind Needs lane context until a current receipt is attached.",
        },
        "proof_to_response_wrong_lane_linger": {
            "proposed_fix": "Require request-scoped proof_to_response in every controller response and mark latest stale if context mismatches.",
            "affected_component": "proof_to_response_runtime",
            "validation_plan": "Run Finance then Business Development smokes and assert latest matches the final lane.",
            "rollback_plan": "Ignore latest for Mac primary response and require response-scoped proof_to_response only.",
        },
        "remote_desktop_trace_log_leak_self_heal": {
            "proposed_fix": "Summarize trace logs into blocker/proof/validation receipts and keep raw trace material behind developer proof.",
            "affected_component": "self_heal_repair_doctrine",
            "validation_plan": "Run a synthetic trace-log repair fixture and assert no raw path/session dump enters primary response.",
            "rollback_plan": "Disable trace-log lesson promotion and require manual proof drawer inspection.",
        },
    }
    updates: list[dict[str, Any]] = []
    for index, example in enumerate(examples, start=1):
        ref = str(example["example_ref"])
        spec = updates_by_example[ref]
        updates.append(
            {
                "proposed_update_ref": f"retrospective_update:{index:02d}:{ref}",
                "source_example_ref": ref,
                "failure_class": str(example["failure_class"]),
                "proposed_fix": spec["proposed_fix"],
                "affected_component": spec["affected_component"],
                "validation_plan": spec["validation_plan"],
                "rollback_plan": spec["rollback_plan"],
                "operator_review_required": True,
                "auto_apply_allowed": False,
                "candidate_update_auto_applied": False,
            }
        )
    return updates


def context_maintenance_policy() -> dict[str, Any]:
    return {
        "stale_context_should_be_demoted": "Stale or unknown context becomes Needs verification or historical support, not current truth.",
        "superseded_receipts_excluded": "Superseded receipts stay available in trace but cannot enter LM bundles as current truth.",
        "summaries_cannot_override_receipts": "Generated summaries are explanations only; receipts, hashes, and source rows define truth.",
        "old_tool_output_logs_compacted": "Old tool output/logs should be compacted to high-signal blocker, validation, and receipt summaries.",
        "high_signal_lessons_preserved": "Preserve failure class, proof, operator decision, receipt, validation, and recurrence signal.",
        "raw_history_hidden_unless_requested": "Raw prompts, logs, file paths, private proof, and trace dumps remain hidden unless explicitly requested and allowed.",
    }


def selection_policy() -> dict[str, Any]:
    return {
        "full_rho_enabled": False,
        "policy_name": "seeded_review_only_selection",
        "candidate_dimensions": [
            "difficulty",
            "recurrence",
            "diversity",
            "operator_friction",
            "safety_relevance",
        ],
        "dimension_meaning": {
            "difficulty": "Prefer failures that are small enough to test but important enough to reduce future errors.",
            "recurrence": "Prioritize classes that recur across lanes or surfaces.",
            "diversity": "Keep examples across proof response, routing, review lifecycle, evidence, and self-heal.",
            "operator_friction": "Favor failures that confuse or slow the operator in live controller use.",
            "safety_relevance": "Favor failures that could cause stale truth, authority confusion, or private context exposure.",
        },
        "selection_output": "candidate_update_records_only",
        "operator_review_required": True,
        "auto_apply_allowed": False,
    }


def _init_sqlite(sqlite_path: Path) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("DROP TABLE IF EXISTS retrospective_learning_seed_records")
        conn.execute(
            """
CREATE TABLE retrospective_learning_seed_records (
  record_id TEXT PRIMARY KEY,
  record_kind TEXT NOT NULL,
  failure_class TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  review_only INTEGER NOT NULL,
  auto_apply_allowed INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  record_json TEXT NOT NULL
)
"""
        )
        conn.commit()


def write_sqlite_records(
    *,
    sqlite_path: Path,
    examples: list[dict[str, Any]],
    candidate_updates: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    sqlite_path = _rooted(sqlite_path)
    _init_sqlite(sqlite_path)
    rows: list[dict[str, Any]] = []
    for example in examples:
        rows.append(
            {
                "record_id": f"example:{example['example_ref']}",
                "record_kind": "required_example",
                "failure_class": str(example["failure_class"]),
                "source_ref": str(example["example_ref"]),
                "review_only": 1,
                "auto_apply_allowed": 0,
                "created_at": generated_at,
                "record_json": stable_json(example),
            }
        )
    for update in candidate_updates:
        rows.append(
            {
                "record_id": str(update["proposed_update_ref"]),
                "record_kind": "candidate_harness_update",
                "failure_class": str(update["failure_class"]),
                "source_ref": str(update["source_example_ref"]),
                "review_only": 1,
                "auto_apply_allowed": 0,
                "created_at": generated_at,
                "record_json": stable_json(update),
            }
        )
    with sqlite3.connect(sqlite_path) as conn:
        conn.executemany(
            """
INSERT INTO retrospective_learning_seed_records (
  record_id, record_kind, failure_class, source_ref, review_only,
  auto_apply_allowed, created_at, record_json
) VALUES (
  :record_id, :record_kind, :failure_class, :source_ref, :review_only,
  :auto_apply_allowed, :created_at, :record_json
)
""",
            rows,
        )
        conn.commit()
        counts = conn.execute(
            "SELECT record_kind, COUNT(*) FROM retrospective_learning_seed_records GROUP BY record_kind ORDER BY record_kind"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM retrospective_learning_seed_records").fetchone()[0]
    return {
        "sqlite_path": sqlite_path.as_posix(),
        "sqlite_row_count": int(total),
        "sqlite_record_kind_counts": {str(kind): int(count) for kind, count in counts},
    }


def sqlite_summary(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> dict[str, Any]:
    sqlite_path = _rooted(sqlite_path)
    if not sqlite_path.exists():
        return {"sqlite_path": sqlite_path.as_posix(), "sqlite_row_count": 0, "sqlite_record_kind_counts": {}}
    with sqlite3.connect(sqlite_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM retrospective_learning_seed_records").fetchone()[0]
        counts = conn.execute(
            "SELECT record_kind, COUNT(*) FROM retrospective_learning_seed_records GROUP BY record_kind ORDER BY record_kind"
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
    examples = required_examples()
    candidate_updates = candidate_harness_updates(examples)
    sqlite_info = (
        write_sqlite_records(sqlite_path=sqlite_path, examples=examples, candidate_updates=candidate_updates, generated_at=generated_at)
        if write_sqlite
        else sqlite_summary(sqlite_path)
    )
    required_sqlite_rows = len(examples) + len(candidate_updates)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Seed review-only retrospective harness learning from task trajectories, stale context failures, verifier failures, and operator decisions.",
        "preconditions": preconditions,
        "trajectory_sources": trajectory_sources(),
        "failure_classes": failure_classes(),
        "decision_trace_fields": decision_trace_fields(),
        "required_examples": examples,
        "context_maintenance_policy": context_maintenance_policy(),
        "candidate_harness_updates": candidate_updates,
        "selection_policy": selection_policy(),
        "sqlite_summary": sqlite_info,
        "source_refs": [
            "generated/read_models/context_freshness_decision_trace_gate.json",
            "generated/read_models/proof_bundle_freshness_trace_status.json",
            "generated/read_models/operator_session_timeline.json",
            "generated/read_models/universal_receipt_envelope_status.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/proof_to_response_schema_adapter_status.json",
            "generated/read_models/local_lm_proof_response_pilot_postmortem.json",
            "generated/read_models/self_heal_repair_doctrine.json",
            "generated/read_models/goldilocks_gate_calibration.json",
        ],
        "rules": [
            "This seed does not modify harness behavior automatically.",
            "This seed does not invoke models.",
            "This seed does not create live self-optimization.",
            "Candidate updates require operator review.",
            "Memory remains suspect until receipt/proof-backed.",
            "Context freshness beats generated summaries.",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "implementation_boundary": IMPLEMENTATION_BOUNDARY,
        "machine_proof": {
            "review_only_learning_seed": True,
            "model_invocation_absent": True,
            "live_self_optimization_absent": True,
            "all_required_failure_classes_present": True,
            "all_candidate_updates_review_only": True,
            "all_candidate_updates_auto_apply_false": True,
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
        "# Retrospective Harness Learning Seed",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This is a review-only learning seed. It records failure classes, decision traces, and candidate harness updates without invoking models or changing runtime behavior.",
        "",
        "## Trajectory Sources",
        "",
    ]
    for source in read_model.get("trajectory_sources") or []:
        lines.append(f"- `{source['source_ref']}`: {source['description']}")
    lines.extend(["", "## Failure Classes", ""])
    for failure in read_model.get("failure_classes") or []:
        lines.append(f"- `{failure['failure_class']}`: {failure['definition']}")
    lines.extend(["", "## Required Examples", ""])
    for example in read_model.get("required_examples") or []:
        trace = example.get("decision_trace") or {}
        lines.append(f"- `{example['example_ref']}` ({example['failure_class']}): {trace.get('why_it_failed')}")
    lines.extend(["", "## Context Maintenance", ""])
    policy = read_model.get("context_maintenance_policy") or {}
    for key, value in policy.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Candidate Updates", ""])
    for update in read_model.get("candidate_harness_updates") or []:
        lines.append(
            f"- `{update['proposed_update_ref']}` -> {update['affected_component']}: {update['proposed_fix']} "
            f"(review required: {str(update['operator_review_required']).lower()}, auto apply: {str(update['auto_apply_allowed']).lower()})"
        )
    lines.extend(
        [
            "",
            "## Selection Policy",
            "",
            f"- Full RHO enabled: `{str((read_model.get('selection_policy') or {}).get('full_rho_enabled')).lower()}`",
            "- Candidates are selected by difficulty, recurrence, diversity, operator friction, and safety relevance.",
            "- Candidate updates require review and cannot auto-apply.",
            "",
        ]
    )
    return "\n".join(lines)


def export_retrospective_harness_learning_seed(
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
    parser = argparse.ArgumentParser(description="Publish Retrospective Harness Learning Seed V0.")
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
    result = export_retrospective_harness_learning_seed(
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
