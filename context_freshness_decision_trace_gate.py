"""Context freshness and decision trace gate V0.

Contract/read-model gate preventing stale, superseded, generated-only, test-only,
or untraceable context from entering future proof-to-response LM bundles as
current truth. This module writes generated read-model/wiki artifacts only. It
does not invoke models, connect runtimes, spawn workers, send email, open
browser/Gmail/Coupa, mutate ledgers or workbooks, export PDFs, mark paid,
submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Context Freshness Decision Trace Gate.md")

SCHEMA_VERSION = "context_freshness_decision_trace_gate_v0"
READ_MODEL_ID = "context_freshness_decision_trace_gate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY"
NOT_READY_STATUS = "CONTEXT_FRESHNESS_DECISION_TRACE_GATE_NOT_READY"

FRESHNESS_STATES = ("current", "waiting_external", "historical", "superseded", "stale", "unknown")

PRECONDITIONS = {
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "operator_session_timeline": {
        "filename": "operator_session_timeline.json",
        "accepted_statuses": ("OPERATOR_SESSION_TIMELINE_READY",),
    },
    "evidence_confidence_scoring": {
        "filename": "evidence_confidence_scoring.json",
        "accepted_statuses": ("EVIDENCE_CONFIDENCE_SCORING_READY",),
    },
    "dynamic_card_lifecycle_policy": {
        "filename": "dynamic_card_lifecycle_policy.json",
        "accepted_statuses": ("DYNAMIC_CARD_LIFECYCLE_POLICY_READY",),
    },
    "memory_promotion_gate": {
        "filename": "memory_promotion_gate.json",
        "accepted_statuses": ("MEMORY_PROMOTION_GATE_READY",),
    },
}

CONFIDENCE_SCORES = {
    "receipt_backed": 0.95,
    "operator_reported_candidate": 0.72,
    "historical_resolved": 0.64,
    "generated_summary": 0.55,
    "stale": 0.2,
    "test_only": 0.1,
    "unknown": 0.0,
    "rejected": 0.0,
    "unpromoted_memory": 0.0,
}

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "proof_bundle_builder_may_ignore_gate": False,
    "stale_context_current_truth_allowed": False,
    "generated_summary_override_allowed": False,
    "unpromoted_memory_truth_allowed": False,
    "test_only_primary_truth_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
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
    "ledger_posting_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "submit_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | {
        "paid",
        "sent",
        "submitted",
        "executed",
        "authority_granted",
        "model_invoked",
        "runtime_connected",
        "external_provider_used",
        "business_action_performed",
        "stale_context_entered_as_current_truth",
        "generated_summary_overrode_receipt",
        "test_only_used_as_primary_truth",
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


def safe_human_response_if_blocked(freshness_state: str, stale_reason: str = "") -> str:
    if freshness_state in {"stale", "superseded", "unknown"}:
        return "Needs verification. I need a current receipt or traceable proof before using this as context."
    if freshness_state == "historical":
        return "This is historical context, not an active current item."
    if stale_reason:
        return f"Needs verification. {stale_reason}"
    return "Needs verification."


def _gate_row(
    *,
    context_ref: str,
    world_ref: str,
    thread_ref: str,
    objective_ref: str,
    source_refs: list[str],
    receipt_refs: list[str],
    decision_trace_refs: list[str],
    latest_receipt_ref: str,
    superseded_receipt_refs: list[str],
    freshness_state: str,
    confidence_class: str,
    decision_trace_summary: str,
    prior_attempts: list[dict[str, Any]] | None = None,
    prior_rejections: list[dict[str, Any]] | None = None,
    operator_decisions: list[dict[str, Any]] | None = None,
    allowed_for_lm_bundle: bool = False,
    stale_reason: str = "",
    required_refresh_action: str = "",
    canonical_claims: dict[str, Any] | None = None,
    blocked_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if freshness_state not in FRESHNESS_STATES:
        freshness_state = "unknown"
    confidence_score = CONFIDENCE_SCORES.get(confidence_class, 0.0)
    blocked_response = "" if allowed_for_lm_bundle else safe_human_response_if_blocked(freshness_state, stale_reason)
    return {
        "context_ref": context_ref,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "objective_ref": objective_ref,
        "source_refs": source_refs,
        "receipt_refs": receipt_refs,
        "decision_trace_refs": decision_trace_refs,
        "latest_receipt_ref": latest_receipt_ref,
        "superseded_receipt_refs": superseded_receipt_refs,
        "freshness_state": freshness_state,
        "confidence_class": confidence_class,
        "confidence_score": confidence_score,
        "stale_reason": stale_reason,
        "decision_trace_summary": decision_trace_summary,
        "prior_attempts": prior_attempts or [],
        "prior_rejections": prior_rejections or [],
        "operator_decisions": operator_decisions or [],
        "allowed_for_lm_bundle": allowed_for_lm_bundle,
        "required_refresh_action": required_refresh_action,
        "safe_human_response_if_blocked": blocked_response,
        "canonical_claims": canonical_claims or {},
        "blocked_claims": blocked_claims or [],
        "lm_bundle_policy": {
            "may_enter_as_current_truth": allowed_for_lm_bundle and freshness_state == "current",
            "must_preserve_confidence_label": confidence_class in {"operator_reported_candidate", "historical_resolved", "test_only"},
            "must_not_override_receipts": True,
            "must_not_claim_paid_sent_submitted_without_receipt": True,
        },
    }


def build_gate_rows() -> list[dict[str, Any]]:
    capital_prior_rejection = {
        "attempt_ref": "attempt:capital_hilton_coupa_submit_without_payment_evidence",
        "attempt_summary": "Protected Coupa/payment route was considered before payment evidence existed.",
        "rejection_reason": "Payment proof missing and protected action approval absent.",
        "what_changed": "Lane-level proof response now asks for payment evidence instead of treating Coupa gate text as primary.",
    }
    return [
        _gate_row(
            context_ref="context:finance:capital_hilton:payment_watch",
            world_ref="finance",
            thread_ref="capital_hilton",
            objective_ref="objective:capital_hilton_payment_watch",
            source_refs=[
                "generated/read_models/proof_to_response_latest.json",
                "generated/read_models/gate_decision_ledger.json",
                "generated/read_models/universal_receipt_envelope_status.json",
            ],
            receipt_refs=[
                "receipt:capital_hilton_payment_watch_current",
                "receipt:capital_hilton_ledger_untouched",
            ],
            decision_trace_refs=[
                "gate:capital_hilton_payment_evidence_missing",
                "gate:coupa_submit_protected_action",
            ],
            latest_receipt_ref="receipt:capital_hilton_payment_watch_current",
            superseded_receipt_refs=[],
            freshness_state="current",
            confidence_class="receipt_backed",
            decision_trace_summary="Current receipt says Coupa is processing, payment evidence is missing, paid marking is not proven, and ledger remains untouched.",
            prior_attempts=[
                {
                    "attempt_ref": "attempt:capital_hilton_payment_watch_ask_why",
                    "attempt_summary": "Operator asked why the lane remains on payment watch.",
                    "outcome": "lane_response_payment_evidence_needed",
                }
            ],
            prior_rejections=[capital_prior_rejection],
            operator_decisions=[
                {
                    "decision_ref": "operator_decision:attach_payment_evidence_next",
                    "decision_summary": "Operator next safe control is Attach proof.",
                }
            ],
            allowed_for_lm_bundle=True,
            canonical_claims={
                "coupa_state": "processing",
                "payment_evidence": "missing",
                "paid_status": "not_proven_false_until_payment_receipt_exists",
                "ledger_state": "untouched",
            },
        ),
        _gate_row(
            context_ref="context:finance:live_arts_md:payment_evidence",
            world_ref="finance",
            thread_ref="live_arts_md",
            objective_ref="objective:live_arts_md_payment_processing_evidence",
            source_refs=[
                "generated/read_models/evidence_intake_status.json",
                "generated/read_models/evidence_confidence_scoring.json",
            ],
            receipt_refs=["receipt:live_arts_md_candidate_evidence_recorded"],
            decision_trace_refs=["trace:live_arts_candidate_payment_processing_not_paid_truth"],
            latest_receipt_ref="receipt:live_arts_md_candidate_evidence_recorded",
            superseded_receipt_refs=[],
            freshness_state="current",
            confidence_class="operator_reported_candidate",
            decision_trace_summary="Evidence intake recorded candidate payment-processing evidence; it is not paid truth.",
            allowed_for_lm_bundle=True,
            canonical_claims={
                "evidence_label": "operator_reported_candidate",
                "payment_processing_evidence": "candidate",
                "paid_status": "not_proven",
            },
        ),
        _gate_row(
            context_ref="context:build:review_packet:informational_resolved",
            world_ref="build",
            thread_ref="build_openclaw_backend",
            objective_ref="objective:build_review_packet",
            source_refs=[
                "generated/read_models/workroom_review_decision_status.json",
                "generated/read_models/dynamic_card_lifecycle_policy.json",
            ],
            receipt_refs=["receipt:build_review_packet_marked_informational"],
            decision_trace_refs=["trace:workroom_review_decision_informational"],
            latest_receipt_ref="receipt:build_review_packet_marked_informational",
            superseded_receipt_refs=[],
            freshness_state="historical",
            confidence_class="historical_resolved",
            decision_trace_summary="Review packet was marked informational/resolved and must not appear as active ready-for-review.",
            allowed_for_lm_bundle=False,
            required_refresh_action="open_history_or_select_active_review_packet",
        ),
        _gate_row(
            context_ref="context:business_development:capital_hilton:followup",
            world_ref="business_development",
            thread_ref="capital_hilton",
            objective_ref="objective:capital_hilton_followup",
            source_refs=[
                "generated/read_models/proof_to_response_latest.json",
                "generated/read_models/universal_receipt_envelope_status.json",
            ],
            receipt_refs=["receipt:capital_hilton_followup_proposal_current"],
            decision_trace_refs=["trace:capital_hilton_followup_stage_only_no_send"],
            latest_receipt_ref="receipt:capital_hilton_followup_proposal_current",
            superseded_receipt_refs=[],
            freshness_state="current",
            confidence_class="receipt_backed",
            decision_trace_summary="Latest proposal receipt supports follow-up staging; no send authority exists.",
            allowed_for_lm_bundle=True,
            canonical_claims={
                "proposal_state": "current",
                "followup_action": "stage_draft_only",
                "send_authority": "not_granted",
            },
        ),
        _gate_row(
            context_ref="context:finance:capital_hilton:superseded_payment_source",
            world_ref="finance",
            thread_ref="capital_hilton",
            objective_ref="objective:capital_hilton_payment_watch",
            source_refs=["generated/read_models/older_payment_watch_summary.json"],
            receipt_refs=["receipt:capital_hilton_old_payment_watch"],
            decision_trace_refs=["trace:superseded_by_latest_payment_watch_receipt"],
            latest_receipt_ref="receipt:capital_hilton_payment_watch_current",
            superseded_receipt_refs=["receipt:capital_hilton_old_payment_watch"],
            freshness_state="superseded",
            confidence_class="stale",
            stale_reason="A newer payment-watch receipt supersedes this source.",
            decision_trace_summary="Superseded receipt is retained for history only and cannot enter the LM bundle as current truth.",
            allowed_for_lm_bundle=False,
            required_refresh_action="refresh_from_latest_receipt",
        ),
        _gate_row(
            context_ref="context:system:stale_or_unknown_source",
            world_ref="system",
            thread_ref="unknown",
            objective_ref="objective:unknown_context",
            source_refs=["generated/read_models/stale_generated_context.json"],
            receipt_refs=[],
            decision_trace_refs=[],
            latest_receipt_ref="",
            superseded_receipt_refs=[],
            freshness_state="stale",
            confidence_class="unknown",
            stale_reason="No current receipt, timeline event, or decision trace supports this context.",
            decision_trace_summary="Untraceable stale source must produce Needs verification instead of confident response text.",
            allowed_for_lm_bundle=False,
            required_refresh_action="request_current_lane_context_or_receipt",
        ),
        _gate_row(
            context_ref="context:finance:capital_hilton:generated_summary_conflict",
            world_ref="finance",
            thread_ref="capital_hilton",
            objective_ref="objective:capital_hilton_payment_watch",
            source_refs=[
                "generated/read_models/proof_to_response_latest.json",
                "generated/read_models/generated_finance_summary.json",
            ],
            receipt_refs=["receipt:capital_hilton_payment_watch_current"],
            decision_trace_refs=["trace:generated_summary_conflict_rejected"],
            latest_receipt_ref="receipt:capital_hilton_payment_watch_current",
            superseded_receipt_refs=[],
            freshness_state="current",
            confidence_class="receipt_backed",
            decision_trace_summary="A generated summary conflicted with the current receipt; receipt truth wins and the summary claim is blocked.",
            prior_rejections=[
                {
                    "attempt_ref": "generated_summary:capital_hilton_paid_claim",
                    "attempt_summary": "Generated summary suggested paid/safe-to-close.",
                    "rejection_reason": "No payment receipt or ledger evidence supports the claim.",
                    "what_changed": "Use current receipt: payment evidence missing and ledger untouched.",
                }
            ],
            allowed_for_lm_bundle=True,
            canonical_claims={
                "payment_evidence": "missing",
                "paid_status": "not_proven",
                "ledger_state": "untouched",
            },
            blocked_claims=[
                {
                    "claim_ref": "generated_summary_claim:capital_hilton_paid",
                    "claim_summary": "Generated summary claimed paid/currently closed.",
                    "blocked_by": "receipt:capital_hilton_payment_watch_current",
                }
            ],
        ),
        _gate_row(
            context_ref="context:test_only:evidence_fixture",
            world_ref="system",
            thread_ref="test_fixture",
            objective_ref="objective:test_only_evidence",
            source_refs=["generated/read_models/evidence_confidence_scoring.json"],
            receipt_refs=["receipt:test_only_fixture_evidence"],
            decision_trace_refs=["trace:test_only_not_primary_truth"],
            latest_receipt_ref="receipt:test_only_fixture_evidence",
            superseded_receipt_refs=[],
            freshness_state="unknown",
            confidence_class="test_only",
            stale_reason="Evidence is marked test-only.",
            decision_trace_summary="Test-only evidence may validate UI/test behavior but cannot be primary truth for LM proof bundles.",
            allowed_for_lm_bundle=False,
            required_refresh_action="attach_live_receipt_backed_evidence",
        ),
        _gate_row(
            context_ref="context:memory:unpromoted_operator_memory",
            world_ref="system",
            thread_ref="memory",
            objective_ref="objective:operator_memory_candidate",
            source_refs=["generated/read_models/memory_promotion_gate.json"],
            receipt_refs=[],
            decision_trace_refs=["trace:memory_candidate_not_promoted"],
            latest_receipt_ref="",
            superseded_receipt_refs=[],
            freshness_state="unknown",
            confidence_class="unpromoted_memory",
            stale_reason="Operator memory candidate has not been promoted to canonical truth.",
            decision_trace_summary="Unpromoted memory can inform review only after promotion; it cannot become canonical truth in a proof bundle.",
            allowed_for_lm_bundle=False,
            required_refresh_action="request_memory_promotion_or_current_receipt",
        ),
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    gate_rows = build_gate_rows()
    preconditions_ready = all(row.get("ready") is True for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Prevent stale, superseded, generated-only, test-only, or untraceable context from entering future LM proof bundles as current truth.",
        "freshness_states": list(FRESHNESS_STATES),
        "rules": [
            "Current receipts beat generated summaries.",
            "Superseded receipts cannot enter proof bundles as current truth.",
            "Generated summaries cannot override receipts.",
            "Candidate/operator-reported evidence must be labeled as such.",
            "Test-only evidence cannot be primary truth.",
            "Stale sources produce Needs verification, not confident response text.",
            "Prior attempts and rejections are included when relevant.",
            "Operator memory is not canonical truth unless promoted.",
            "If no current proof exists, proof bundle builder blocks or marks context unknown.",
            "The LM must not receive stale context as if current.",
        ],
        "gate_rows": gate_rows,
        "summary": {
            "contexts_total": len(gate_rows),
            "allowed_for_lm_bundle_count": sum(1 for row in gate_rows if row.get("allowed_for_lm_bundle") is True),
            "blocked_or_historical_count": sum(1 for row in gate_rows if row.get("allowed_for_lm_bundle") is False),
            "stale_or_superseded_count": sum(1 for row in gate_rows if row.get("freshness_state") in {"stale", "superseded"}),
        },
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "contract_only": True,
            "model_invoked": False,
            "runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "stale_context_entered_as_current_truth": False,
            "generated_summary_overrode_receipt": False,
            "test_only_used_as_primary_truth": False,
            "unpromoted_memory_used_as_truth": False,
            "unsafe_true_grants_absent": True,
        },
        "source_refs": [
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/universal_receipt_envelope_status.json",
            "generated/read_models/operator_session_timeline.json",
            "generated/read_models/evidence_confidence_scoring.json",
            "generated/read_models/dynamic_card_lifecycle_policy.json",
            "generated/read_models/memory_promotion_gate.json",
        ],
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "gate_rows": _content_hash(gate_rows),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    summary = read_model.get("summary") if isinstance(read_model.get("summary"), Mapping) else {}
    lines = [
        "# Context Freshness Decision Trace Gate",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This is a contract gate for future LM proof bundles. It blocks stale, superseded, test-only, generated-only, and untraceable context from being treated as current truth.",
        "",
        "## Summary",
        "",
        f"- Contexts total: `{summary.get('contexts_total')}`",
        f"- Allowed for LM bundle: `{summary.get('allowed_for_lm_bundle_count')}`",
        f"- Blocked or historical: `{summary.get('blocked_or_historical_count')}`",
        f"- Stale or superseded: `{summary.get('stale_or_superseded_count')}`",
        "",
        "## Rules",
        "",
    ]
    for rule in read_model.get("rules") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Gate Rows", ""])
    for row in read_model.get("gate_rows") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- `{row.get('context_ref')}`: freshness `{row.get('freshness_state')}`, "
            f"confidence `{row.get('confidence_class')}`, allowed `{str(row.get('allowed_for_lm_bundle')).lower()}`. "
            f"{row.get('decision_trace_summary')}"
        )
    lines.append("")
    return "\n".join(lines)


def export_context_freshness_decision_trace_gate(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
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
        "contexts_total": str(read_model.get("summary", {}).get("contexts_total") or 0),
        "allowed_for_lm_bundle_count": str(read_model.get("summary", {}).get("allowed_for_lm_bundle_count") or 0),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Context Freshness Decision Trace Gate V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_context_freshness_decision_trace_gate(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
