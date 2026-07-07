"""Workflow package queue V0.

This module turns a human-style instruction into a gated workflow package record.
V0 is deliberately dry-run only: no Telegram live connection, email, browser,
Coupa, workbook mutation, PDF export, ledger mutation, paid marking, or submit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import agent_voice_router


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Workflow Package Queue.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/workflow_package_queue.sqlite")

SCHEMA_VERSION = "workflow_package_queue_v0"
READ_MODEL_ID = "workflow_package_queue_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
PROJECT_ROOM_COMPILER_READ_MODEL_ID = "project_room_package_compiler_integration"
PROJECT_ROOM_COMPILER_JSON_EXPORT_NAME = f"{PROJECT_ROOM_COMPILER_READ_MODEL_ID}.json"
PROJECT_ROOM_COMPILER_WIKI_PATH = Path("generated/wiki/openclaw/Project Room Package Compiler Integration.md")
PROJECT_ROOM_COMPILER_READY_STATUS = "PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY"
PROJECT_ROOM_COMPILER_NOT_READY_STATUS = "PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_NOT_READY"

SUPPORTED_PACKAGE_TYPES = (
    "st_annes_work_log_event",
    "st_annes_monthly_invoice_rollup",
    "capital_hilton_invoice_operator_assist",
    "capital_hilton_proposal_followup",
    "diagnostic_package_gate_smoke",
)

PIPELINE_STAGES = (
    "human_instruction",
    "privacy_pii_gate",
    "intent_classification",
    "workflow_package_record",
    "sqlite_package_registry",
    "capability_provider_gate",
    "worker_assignment",
    "result_receipt",
    "operator_review_gate",
    "business_action_gate",
)

AUTHORITY_BOUNDARY_DEFAULT = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_source_mutation_allowed": False,
    "paid": False,
    "sent": False,
}

PRIVACY_EVALUATOR_DEFAULT = {
    "provider_considered": "local_noop_worker",
    "data_exposure_class": "local_instruction_metadata",
    "local_alternative": "deterministic_local_classifier_and_sqlite_registry",
    "final_provider_decision": "local_only_noop_worker",
    "approval_required": True,
}

FIXTURE_INSTRUCTIONS = (
    ("mission_control", "Mark that I'm at church running sound."),
    ("mission_control", "Send St. Anne's invoice."),
    ("mission_control", "Follow up on Capital Hilton proposal."),
    ("mission_control", "Submit Capital Hilton invoice."),
    ("codex", "Run diagnostic package gate smoke."),
)

OPERATOR_DISPLAY_FIELDS = (
    "speaker_ref",
    "voice_profile_ref",
    "voice_mode",
    "audience",
    "routing_reason",
    "headline",
    "subheadline",
    "status_label",
    "tone",
    "plain_summary",
    "next_safe_action",
    "why_it_matters",
    "primary_fact",
    "secondary_facts",
    "proof_caption",
    "show_machine_details_by_default",
)

PROJECT_ROOM_REQUIRED_REFS = (
    "project_room_id",
    "source_inventory_ref",
    "conflict_log_ref",
    "missing_context_ref",
    "duplicate_report_ref",
    "decision_trace_ref",
    "freshness_gate_ref",
    "compaction_policy_ref",
)

PROJECT_ROOM_COMPILER_PRECONDITIONS = {
    "project_room_sourceset_contract": {
        "filename": "project_room_sourceset_contract.json",
        "accepted_statuses": ("PROJECT_ROOM_SOURCESET_CONTRACT_READY",),
    },
    "context_compaction_preview_policy": {
        "filename": "context_compaction_preview_policy.json",
        "accepted_statuses": ("CONTEXT_COMPACTION_PREVIEW_POLICY_READY",),
    },
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
    "workflow_composer": {
        "filename": "workflow_composer_latest.json",
        "accepted_statuses": ("WORKFLOW_COMPOSER_READY",),
    },
    "worker_package_staging": {
        "filename": "worker_package_staging_status.json",
        "accepted_statuses": ("WORKER_PACKAGE_STAGING_READY",),
    },
    "lm2_live_worker_pilot_boundary": {
        "filename": "lm2_live_worker_pilot_boundary_packet.json",
        "accepted_statuses": ("LM2_LIVE_WORKER_PILOT_BOUNDARY_READY",),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
}

PROJECT_ROOM_COMPILER_AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "local_model_runtime_allowed": False,
    "external_lm_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
    "business_action_allowed": False,
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
    "authority_grant_allowed": False,
    "raw_messy_folder_dump_allowed": False,
    "full_log_dump_allowed": False,
    "stale_source_current_truth_allowed": False,
    "missing_context_invention_allowed": False,
    "sent": False,
    "paid": False,
}

PROJECT_ROOM_COMPILER_UNSAFE_TRUE_KEYS = set(PROJECT_ROOM_COMPILER_AUTHORITY_BOUNDARY) | {
    "model_invoked",
    "runtime_connected",
    "local_model_runtime_connected",
    "external_provider_connected",
    "worker_spawn_performed",
    "worker_execution_performed",
    "business_action_performed",
    "email_send_performed",
    "gmail_opened",
    "browser_opened",
    "coupa_opened",
    "portal_submit_performed",
    "ledger_mutation_performed",
    "ledger_posting_performed",
    "paid_marking_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "git_push_performed",
    "authority_granted",
    "raw_messy_folder_dump_included",
    "full_log_dump_included",
    "stale_source_as_current_truth",
    "missing_context_invented",
    "unreviewed_duplicates_equal_evidence",
}


@dataclass(frozen=True)
class QueueConfig:
    st_annes_send_permission_ready: bool = False
    st_annes_approved_pdf_artifact_available: bool = False
    capital_hilton_operator_assist_provider_staged: bool = False
    capital_hilton_submit_gate_staged: bool = False


@dataclass(frozen=True)
class ExportResult:
    read_model_path: str
    bridge_read_model_path: str
    wiki_path: str
    sqlite_path: str
    package_count: int
    supported_package_types: tuple[str, ...]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short_hash(*parts: object) -> str:
    joined = "\u241f".join(str(part) for part in parts)
    return _sha256_text(joined)[:16]


def protected_text_hash(source_text: str) -> str:
    return "sha256:" + _sha256_text(source_text)


def _now_or_fixed(value: str | None) -> str:
    return value or utc_now()


def _load_read_model_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _observed_readiness(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("readiness_status") or payload.get("contract_status") or "")


def project_room_compiler_preconditions(read_model_root: Path = DEFAULT_EXPORT_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PROJECT_ROOM_COMPILER_PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_read_model_json(root / filename)
        observed = _observed_readiness(payload)
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


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def project_room_compiler_unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            key
            for key, value in _walk_values(payload)
            if key in PROJECT_ROOM_COMPILER_UNSAFE_TRUE_KEYS and value is True
        }
    )


def classify_package_source_requirements(
    package_type: str,
    *,
    uses_multiple_sources: bool = False,
    explicitly_trivial: bool = False,
) -> dict[str, Any]:
    package_type = str(package_type)
    if package_type == "simple_answer":
        return {
            "package_type": package_type,
            "project_room_required": False,
            "proof_bundle_required": False,
            "repair_room_allowed": False,
            "bypass_allowed": True,
            "requirement_reason": "Trivial readback/system question may bypass project room when current proof supports the answer.",
        }
    if package_type == "proof_to_response":
        return {
            "package_type": package_type,
            "project_room_required": False,
            "proof_bundle_required": True,
            "repair_room_allowed": False,
            "bypass_allowed": True,
            "requirement_reason": "Proof-to-response may use current proof bundle freshness/redaction without a full project room.",
        }
    if package_type == "client/business_draft":
        required = bool(uses_multiple_sources)
        return {
            "package_type": package_type,
            "project_room_required": required,
            "proof_bundle_required": False,
            "repair_room_allowed": False,
            "bypass_allowed": not required,
            "requirement_reason": "Client/business drafts require a project room when proposal/history or multiple sources are used.",
        }
    if package_type == "code/build/repair":
        return {
            "package_type": package_type,
            "project_room_required": True,
            "proof_bundle_required": False,
            "repair_room_allowed": True,
            "bypass_allowed": False,
            "requirement_reason": "Code/build/repair packages require a project room or repair room before synthesis.",
        }
    if package_type == "LM2 worker package":
        required = not explicitly_trivial
        return {
            "package_type": package_type,
            "project_room_required": required,
            "proof_bundle_required": required,
            "repair_room_allowed": False,
            "bypass_allowed": explicitly_trivial,
            "requirement_reason": "LM2 worker packages require a project/proof room unless explicitly trivial.",
        }
    return {
        "package_type": package_type,
        "project_room_required": True,
        "proof_bundle_required": False,
        "repair_room_allowed": False,
        "bypass_allowed": False,
        "requirement_reason": "Serious synthesis packages require a project room.",
    }


def _required_ref_values(package: Mapping[str, Any]) -> dict[str, str]:
    return {ref: str(package.get(ref) or "") for ref in PROJECT_ROOM_REQUIRED_REFS}


def compile_project_room_package_gate(package: Mapping[str, Any]) -> dict[str, Any]:
    package_type = str(package.get("package_type") or "serious_synthesis")
    requirements = classify_package_source_requirements(
        package_type,
        uses_multiple_sources=bool(package.get("uses_multiple_sources")),
        explicitly_trivial=bool(package.get("explicitly_trivial")),
    )
    required_refs = _required_ref_values(package)
    missing_refs = [ref for ref, value in required_refs.items() if not value]
    project_room_required = bool(requirements["project_room_required"])
    proof_bundle_required = bool(requirements["proof_bundle_required"])
    proof_bundle_ready = not proof_bundle_required or bool(package.get("current_proof_bundle_exists"))
    source_inventory_exists = bool(package.get("source_inventory_exists")) or bool(required_refs["source_inventory_ref"])
    duplicate_report_exists = bool(package.get("duplicate_report_exists")) or bool(required_refs["duplicate_report_ref"])
    decision_trace_exists = bool(package.get("decision_trace_exists")) or bool(required_refs["decision_trace_ref"])
    project_room_refs_present = not missing_refs
    blockers: list[str] = []

    if project_room_required and not project_room_refs_present:
        blockers.append("project_room_refs_missing")
    if project_room_required and not source_inventory_exists:
        blockers.append("source_inventory_missing")
    if proof_bundle_required and not proof_bundle_ready:
        blockers.append("proof_bundle_missing_or_not_current")
    if bool(package.get("unresolved_critical_conflict")):
        blockers.append("unresolved_critical_conflict")
    if bool(package.get("missing_context_blocks_supported_claim")):
        blockers.append("missing_context_blocks_supported_claim")
    if bool(package.get("stale_superseded_source_as_current")):
        blockers.append("stale_or_superseded_source_treated_as_current")
    if bool(package.get("version_families_exist")) and not duplicate_report_exists:
        blockers.append("duplicate_report_missing")
    if bool(package.get("repeated_or_failed_work")) and not decision_trace_exists:
        blockers.append("decision_trace_missing")
    if package_type == "code/build/repair" and not bool(package.get("validation_plan_ref")):
        blockers.append("validation_plan_missing")
    if package_type == "code/build/repair" and not bool(package.get("rollback_plan_ref")):
        blockers.append("rollback_plan_missing")
    if package_type == "LM2 worker package":
        if bool(package.get("raw_messy_folder_dump_included")):
            blockers.append("raw_messy_folder_dump_blocked")
        if bool(package.get("full_log_dump_included")):
            blockers.append("full_log_dump_blocked")
        if bool(package.get("unreviewed_duplicates_equal_evidence")):
            blockers.append("unreviewed_duplicates_equal_evidence_blocked")
        if bool(package.get("missing_context_invented")):
            blockers.append("missing_context_invention_blocked")
        if not bool(package.get("one_bounded_objective")):
            blockers.append("bounded_objective_missing")

    project_room_ready = (
        not project_room_required
        or (
            project_room_refs_present
            and source_inventory_exists
            and not bool(package.get("unresolved_critical_conflict"))
            and not bool(package.get("missing_context_blocks_supported_claim"))
            and not bool(package.get("stale_superseded_source_as_current"))
            and (not bool(package.get("version_families_exist")) or duplicate_report_exists)
            and (not bool(package.get("repeated_or_failed_work")) or decision_trace_exists)
        )
    )
    synthesis_allowed = not blockers
    if package_type == "proof_to_response" and proof_bundle_ready and not blockers:
        synthesis_allowed = True
    if package_type == "simple_answer" and not blockers:
        synthesis_allowed = True
    blocked_reason = ", ".join(blockers)
    if not blockers:
        next_safe_action = str(package.get("next_safe_action") or "Proceed within the approved source-room scope.")
    elif "source_inventory_missing" in blockers:
        next_safe_action = "Build the project room source inventory before synthesis."
    elif "unresolved_critical_conflict" in blockers:
        next_safe_action = "Surface the conflict and request an operator decision."
    elif "missing_context_blocks_supported_claim" in blockers:
        next_safe_action = "Name the missing context and avoid unsupported factual claims."
    elif "duplicate_report_missing" in blockers:
        next_safe_action = "Create the duplicate/version report before weighting sources."
    elif "decision_trace_missing" in blockers:
        next_safe_action = "Attach the decision trace before repeating failed work."
    elif "project_room_refs_missing" in blockers:
        next_safe_action = "Build the project room source inventory before synthesis."
    elif "proof_bundle_missing_or_not_current" in blockers:
        next_safe_action = "Attach a current proof bundle with freshness and redaction."
    elif "validation_plan_missing" in blockers or "rollback_plan_missing" in blockers:
        next_safe_action = "Add validation and rollback plans before proposing repair work."
    else:
        next_safe_action = "Remove blocked context and retry the package compile."
    return {
        "package_ref": str(package.get("package_ref") or package.get("package_id") or package_type),
        "package_type": package_type,
        "classification": requirements,
        "project_room_required": project_room_required,
        "proof_bundle_required": proof_bundle_required,
        "project_room_ready": project_room_ready,
        "synthesis_allowed": synthesis_allowed,
        "blocked_reason": blocked_reason,
        "next_safe_action": next_safe_action,
        "required_project_room_refs": required_refs,
        "missing_project_room_refs": missing_refs,
        "source_inventory_exists": source_inventory_exists,
        "duplicate_report_exists": duplicate_report_exists,
        "decision_trace_exists": decision_trace_exists,
        "current_proof_bundle_exists": bool(package.get("current_proof_bundle_exists")),
        "lm2_context_protections": {
            "raw_messy_folder_dump_allowed": False,
            "full_logs_artifacts_by_default_allowed": False,
            "stale_source_current_truth_allowed": False,
            "unreviewed_duplicates_equal_evidence_allowed": False,
            "missing_context_invention_allowed": False,
        },
        "authority_boundary": dict(PROJECT_ROOM_COMPILER_AUTHORITY_BOUNDARY),
        "blockers": blockers,
    }


def _privacy_gate(source_text: str, source_surface: str) -> dict[str, Any]:
    contains_email_like = "@" in source_text
    contains_phone_like = any(char.isdigit() for char in source_text) and "-" in source_text
    pii_status = "MINIMAL_BUSINESS_CONTEXT"
    if contains_email_like or contains_phone_like:
        pii_status = "PII_PRESENT_HASH_ONLY"
    return {
        "gate_ref": "privacy_gate:" + _short_hash(source_surface, source_text),
        "status": "PASS_HASH_ONLY",
        "pii_status": pii_status,
        "privacy_impact": {
            "raw_text_stored": False,
            "protected_text_hash_used": True,
            "pii_privacy_status": pii_status,
            "data_exposure_class": "local_instruction_metadata",
        },
    }


def _normalized_operator_text(source_text: str) -> str:
    text = source_text.lower().replace("’", "'")
    for char in ".,?!;:()[]{}\"":
        text = text.replace(char, " ")
    text = text.replace("'", "")
    return " ".join(text.split())


def _mentions_st_annes(text: str) -> bool:
    return any(
        term in text
        for term in (
            "st anne",
            "st annes",
            "stannes",
            "saint anne",
            "saint annes",
            "annes",
        )
    )


def _st_annes_invoice_related(text: str) -> bool:
    invoice_terms = ("invoice", "bill", "billing", "billed", "rollup")
    return any(term in text for term in invoice_terms) or ("workflow" in text and "invoice" in text)


def _st_annes_review_dry_run_semantics(text: str) -> bool:
    review_terms = ("test", "review", "preview", "proof", "show", "see", "look at")
    before_send_terms = ("before send", "before sending", "before it goes out", "before we send", "first")
    billing_question_terms = ("what would we bill", "what do we bill", "how much would we bill")
    return (
        any(term in text for term in review_terms)
        or any(term in text for term in before_send_terms)
        or any(term in text for term in billing_question_terms)
    )


def classify_intent(source_text: str) -> dict[str, Any]:
    text = _normalized_operator_text(source_text)
    st_annes_mentioned = _mentions_st_annes(text)
    service_event_terms = (
        "church",
        "running sound",
        "adult forum",
        "funeral",
        "wedding",
        "av tech",
        "worked",
        "sound support",
    )
    if any(term in text for term in service_event_terms) and (st_annes_mentioned or "church" in text or "running sound" in text):
        return {
            "workflow_ref": "st_annes_work_log_event",
            "world": "invoice_operations",
            "client_ref": "st_annes",
            "confidence": "high",
            "intent_reason": "Detected St. Anne's/church sound work-log instruction.",
        }
    if st_annes_mentioned and _st_annes_invoice_related(text):
        return {
            "workflow_ref": "st_annes_monthly_invoice_rollup",
            "world": "invoice_operations",
            "client_ref": "st_annes",
            "confidence": "high",
            "intent_reason": "Detected St. Anne's invoice instruction.",
            "st_annes_review_dry_run_requested": _st_annes_review_dry_run_semantics(text),
        }
    if "capital hilton" in text and "proposal" in text:
        return {
            "workflow_ref": "capital_hilton_proposal_followup",
            "world": "business_development",
            "client_ref": "capital_hilton",
            "confidence": "high",
            "intent_reason": "Detected Capital Hilton proposal follow-up instruction.",
        }
    if "capital hilton" in text and ("submit" in text or "invoice" in text):
        return {
            "workflow_ref": "capital_hilton_invoice_operator_assist",
            "world": "invoice_operations",
            "client_ref": "capital_hilton",
            "confidence": "high",
            "intent_reason": "Detected Capital Hilton invoice operator-assist instruction.",
        }
    return {
        "workflow_ref": "diagnostic_package_gate_smoke",
        "world": "diagnostic",
        "client_ref": None,
        "confidence": "medium",
        "intent_reason": "Fell back to diagnostic package gate smoke.",
    }


def _workflow_ref_from_lm1_intent(intent: str, client: str) -> str:
    intent_key = str(intent or "").strip().lower().replace("-", "_")
    client_key = str(client or "").strip().lower().replace("_", "-")
    if intent_key == "invoice_send":
        if client_key in {"st-annes", "st-anne", "st-anne-s", "st-annes-annapolis"}:
            return "st_annes_monthly_invoice_rollup"
        if client_key in {"capital-hilton", "capitalhilton"}:
            return "capital_hilton_invoice_operator_assist"
    if intent_key == "capture_gig" and client_key in {"st-annes", "st-anne", "st-anne-s", "st-annes-annapolis"}:
        return "st_annes_work_log_event"
    return ""


def _classify_intent_with_lm1_override(
    source_text: str,
    intent_override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    fallback = classify_intent(source_text)
    if not isinstance(intent_override, Mapping):
        return fallback
    route = str(intent_override.get("route") or "").upper()
    try:
        confidence = float(intent_override.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    workflow_ref = str(intent_override.get("workflow_ref") or "")
    intent = str(intent_override.get("intent") or "")
    client_ref = str(intent_override.get("client_ref") or intent_override.get("client") or "")
    if not workflow_ref:
        workflow_ref = _workflow_ref_from_lm1_intent(intent, client_ref)
    if route != "WORKFLOW" or confidence < 0.75 or not workflow_ref:
        return fallback
    if workflow_ref not in SUPPORTED_PACKAGE_TYPES:
        return fallback
    world = "invoice_operations"
    if workflow_ref == "capital_hilton_proposal_followup":
        world = "business_development"
    if workflow_ref == "diagnostic_package_gate_smoke":
        world = "diagnostic"
    if not client_ref:
        if workflow_ref.startswith("st_annes"):
            client_ref = "st_annes"
        elif workflow_ref.startswith("capital_hilton"):
            client_ref = "capital_hilton"
    return {
        "workflow_ref": workflow_ref,
        "world": world,
        "client_ref": client_ref or None,
        "confidence": "high",
        "intent_reason": str(intent_override.get("reason") or "LM1 shared seam resolved workflow intent."),
        "intent_source": str(intent_override.get("source") or "lm1_shared_interpreter"),
        "lm1_intent": intent,
        "lm1_contact": str(intent_override.get("contact") or ""),
        "lm1_description": str(intent_override.get("description") or ""),
        "lm1_date": str(intent_override.get("date") or ""),
    }


def _st_annes_review_dry_run_requested(source_text: str) -> bool:
    intent = classify_intent(source_text)
    if intent.get("workflow_ref") == "st_annes_monthly_invoice_rollup":
        return intent.get("st_annes_review_dry_run_requested") is True
    normalized = _normalized_operator_text(source_text)
    review_terms = ("test", "review", "preview", "dry-run", "dry run", "proof")
    return any(term in normalized for term in review_terms)


def _capability_gate(
    workflow_ref: str,
    config: QueueConfig,
    *,
    source_text: str = "",
) -> dict[str, Any]:
    if workflow_ref == "st_annes_work_log_event":
        return {
            "gate_ref": "capability_gate:st_annes_work_log_event",
            "status": "ALLOW_DRY_RUN",
            "reason": "Record-only work-log package can be staged locally.",
            "provider_policy": "local_noop_worker_only",
            "provider_required": False,
            "blocked_actions": (),
        }
    if workflow_ref == "st_annes_monthly_invoice_rollup":
        if _st_annes_review_dry_run_requested(source_text):
            return _st_annes_invoice_review_capability(config)
        if not config.st_annes_send_permission_ready:
            return {
                "gate_ref": "capability_gate:st_annes_invoice_send_permission",
                "status": "PERMISSION_REQUIRED",
                "reason": "Send permission registry is not ready for V0 package execution.",
                "provider_policy": "blocked_until_permission_registry_ready",
                "provider_required": True,
                "blocked_actions": ("email_send", "workbook_write", "pdf_export"),
                "actual_send_gate": _st_annes_actual_send_gate(config),
            }
        if not config.st_annes_approved_pdf_artifact_available:
            return {
                "gate_ref": "capability_gate:st_annes_invoice_artifact",
                "status": "ARTIFACT_REQUIRED",
                "reason": "No approved PDF artifact is available for a send package.",
                "provider_policy": "blocked_until_approved_artifact",
                "provider_required": True,
                "blocked_actions": ("email_send",),
                "actual_send_gate": _st_annes_actual_send_gate(config),
            }
        return _st_annes_invoice_review_capability(config)
    if workflow_ref == "capital_hilton_invoice_operator_assist":
        if not config.capital_hilton_operator_assist_provider_staged or not config.capital_hilton_submit_gate_staged:
            return {
                "gate_ref": "capability_gate:capital_hilton_operator_assist",
                "status": "PROVIDER_GATE_REQUIRED",
                "reason": "Operator-assist provider and final Submit gate are not explicitly staged.",
                "provider_policy": "operator_assist_provider_required_submit_gate_closed",
                "provider_required": True,
                "blocked_actions": ("coupa_submit", "browser_access", "email_send"),
            }
        return {
            "gate_ref": "capability_gate:capital_hilton_operator_assist_staged",
            "status": "ALLOW_DRY_RUN",
            "reason": "Operator-assist provider is staged, but V0 still performs no live Coupa action.",
            "provider_policy": "operator_assist_dry_run_only",
            "provider_required": True,
            "blocked_actions": ("coupa_submit", "email_send"),
        }
    if workflow_ref == "capital_hilton_proposal_followup":
        return {
            "gate_ref": "capability_gate:capital_hilton_proposal_followup",
            "status": "ALLOW_DRY_RUN",
            "reason": "Proposal follow-up package can be staged for operator review only.",
            "provider_policy": "local_noop_worker_only",
            "provider_required": False,
            "blocked_actions": ("email_send", "invoice_creation", "finance_handoff"),
        }
    return {
        "gate_ref": "capability_gate:diagnostic_package_gate_smoke",
        "status": "ALLOW_DRY_RUN",
        "reason": "Diagnostic smoke package is dry-run only.",
        "provider_policy": "local_noop_worker_only",
        "provider_required": False,
        "blocked_actions": (),
    }


def _package_status(workflow_ref: str, capability_status: str) -> str:
    if capability_status in {"PERMISSION_REQUIRED", "ARTIFACT_REQUIRED", "PROVIDER_GATE_REQUIRED"}:
        return capability_status
    if workflow_ref == "diagnostic_package_gate_smoke":
        return "PACKAGE_STAGED"
    return "OPERATOR_REVIEW_REQUIRED"


def _worker_result_status(package_status: str) -> str:
    if package_status in {"PERMISSION_REQUIRED", "ARTIFACT_REQUIRED", "PROVIDER_GATE_REQUIRED"}:
        return "NOOP_BLOCKED_BY_GATE"
    return "NOOP_RESULT_RECORDED"


def _st_annes_actual_send_gate(config: QueueConfig) -> dict[str, Any]:
    if not config.st_annes_send_permission_ready:
        status = "CLOSED_PERMISSION_REQUIRED"
        reason = "Send permission registry is not ready for actual email send."
    elif not config.st_annes_approved_pdf_artifact_available:
        status = "CLOSED_ARTIFACT_REQUIRED"
        reason = "No approved PDF artifact is available for actual email send."
    else:
        status = "CLOSED_GUARDIAN_REQUIRED"
        reason = "Guardian approval is required before actual email send."
    return {
        "gate_ref": "actual_send_gate:st_annes_invoice_email_send",
        "status": status,
        "reason": reason,
        "send_permission_ready": config.st_annes_send_permission_ready,
        "approved_pdf_artifact_available": config.st_annes_approved_pdf_artifact_available,
        "guardian_approval_required": True,
        "email_send_allowed": False,
        "blocked_actions": ("email_send",),
    }


def _st_annes_invoice_review_capability(config: QueueConfig) -> dict[str, Any]:
    return {
        "gate_ref": "capability_gate:st_annes_invoice_review_dry_run",
        "status": "ALLOW_DRY_RUN",
        "reason": "Invoice proof review can be staged locally before send permission.",
        "provider_policy": "local_noop_worker_only_actual_send_gate_closed",
        "provider_required": False,
        "allowed_dry_run_actions": ("local_pdf_proof_render", "clara_draft_render", "guardian_gate_preview"),
        "blocked_actions": ("email_send", "workbook_write", "external_pdf_export"),
        "actual_send_gate": _st_annes_actual_send_gate(config),
    }


def _proof_refs_for_source_room(source_room_context: Mapping[str, Any]) -> list[dict[str, str]]:
    if not source_room_context.get("source_inventory_exists"):
        return []
    source_inventory_ref = str(source_room_context.get("source_inventory_ref") or "")
    if not source_inventory_ref:
        return []
    workflow_ref = str(source_room_context.get("package_ref") or "")
    proof_refs: list[dict[str, str]] = []
    for artifact_kind in source_room_context.get("dry_run_artifact_order") or ():
        render_mode = "guardian_preview_closed" if artifact_kind == "guardian_gate" else "local_dry_run_review"
        proof_refs.append(
            {
                "artifact_ref": f"{artifact_kind}:{workflow_ref}",
                "artifact_kind": str(artifact_kind),
                "source_inventory_ref": source_inventory_ref,
                "render_mode": render_mode,
            }
        )
    return proof_refs


def _local_st_annes_proof_render_allowed(capability: Mapping[str, Any]) -> bool:
    return (
        capability.get("status") == "ALLOW_DRY_RUN"
        and "local_pdf_proof_render" in set(capability.get("allowed_dry_run_actions") or ())
    )


def _st_annes_dry_run_proof_bundle(
    source_room_context: Mapping[str, Any],
    capability: Mapping[str, Any],
) -> dict[str, Any]:
    if source_room_context.get("package_ref") != "st_annes_monthly_invoice_rollup":
        return {}
    if not _local_st_annes_proof_render_allowed(capability):
        return {}
    proof_refs = _proof_refs_for_source_room(source_room_context)
    if not proof_refs:
        return {}
    inventory = source_room_context.get("source_inventory")
    sources = list(inventory.get("sources") or []) if isinstance(inventory, Mapping) else []
    source_refs = [
        str(source.get("source_ref"))
        for source in sources
        if isinstance(source, Mapping) and source.get("exists") is True and source.get("source_ref")
    ]
    rendered_artifacts = [
        {
            "artifact_ref": ref["artifact_ref"],
            "artifact_kind": ref["artifact_kind"],
            "source_inventory_ref": ref["source_inventory_ref"],
            "render_mode": ref["render_mode"],
            "source_backed": bool(source_refs),
            "external_export_performed": False,
            "email_send_performed": False,
        }
        for ref in proof_refs
    ]
    return {
        "schema_version": "st_annes_dry_run_proof_bundle_v0",
        "proof_bundle_id": "dry_run_proof_bundle:st_annes_monthly_invoice_rollup",
        "emitter_ref": "workflow_package_queue:st_annes_dry_run_proof_bundle",
        "workflow_ref": "st_annes_monthly_invoice_rollup",
        "client_ref": "st_annes",
        "source_inventory_ref": str(source_room_context.get("source_inventory_ref") or ""),
        "conflict_log_ref": str(source_room_context.get("conflict_log_ref") or ""),
        "duplicate_report_ref": str(source_room_context.get("duplicate_report_ref") or ""),
        "decision_trace_ref": str(source_room_context.get("decision_trace_ref") or ""),
        "artifact_order": [ref["artifact_kind"] for ref in proof_refs],
        "proof_refs": proof_refs,
        "rendered_artifacts": rendered_artifacts,
        "source_refs": source_refs,
        "blocked_actions": ["email_send", "workbook_write", "external_pdf_export"],
        "authority_boundary": {
            "email_send_allowed": False,
            "workbook_write_allowed": False,
            "external_pdf_export_allowed": False,
            "ledger_posting_allowed": False,
            "paid": False,
            "sent": False,
        },
        "machine_proof": {
            "emitter_invoked": True,
            "source_inventory_exists": source_room_context.get("source_inventory_exists") is True,
            "source_backed": bool(source_refs),
            "pdf_proof_first": bool(proof_refs) and proof_refs[0]["artifact_kind"] == "pdf_proof",
            "live_worker_executed": False,
            "email_send_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
        },
    }


def _display_source_ref(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _source_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _inventory_source(
    path: str | Path,
    *,
    artifact_kind: str,
    required: bool = True,
    source_of_truth: bool = True,
) -> dict[str, Any]:
    source_path = _source_path(path)
    exists = source_path.exists()
    row: dict[str, Any] = {
        "source_ref": _display_source_ref(source_path),
        "artifact_kind": artifact_kind,
        "required": required,
        "exists": exists,
        "source_of_truth": source_of_truth,
    }
    if exists and source_path.is_file():
        row["file_size_bytes"] = source_path.stat().st_size
        row["sha256"] = _file_sha256(source_path)
        if source_path.suffix.lower() == ".json":
            payload = _json_object(source_path)
            for key in ("schema_version", "read_model_id", "status", "client_ref", "workflow_ref", "invoice_period"):
                if payload.get(key) not in (None, ""):
                    row[key] = payload[key]
    return row


def _st_annes_invoice_artifact_sources() -> list[dict[str, Any]]:
    try:
        import st_annes_invoice_status as invoice_status

        receipt_path = invoice_status.find_latest_manual_send_receipt(invoice_status.DEFAULT_RECEIPT_DIR)
        pdf_path = invoice_status.DEFAULT_PDF_PATH
    except Exception:  # noqa: BLE001 - fail closed by reporting missing refs.
        receipt_path = Path("/mnt/e/openclaw/artifacts/invoice_workbooks/st_annes/2026-05/st_annes_manual_invoice_sent_receipt_20260601T211257Z.json")
        pdf_path = Path("/mnt/e/openclaw/artifacts/invoice_workbooks/st_annes/2026-05/Invoice_St_Annes_May_2026_OPERATOR_SENT.pdf")
    return [
        _inventory_source(receipt_path, artifact_kind="manual_send_receipt_json", required=False),
        _inventory_source(pdf_path, artifact_kind="operator_provided_pdf_invoice", required=False),
    ]


def _st_annes_monthly_invoice_source_room_context() -> dict[str, Any]:
    scenario_ref = "st_annes_monthly_invoice_rollup"
    sources = [
        _inventory_source(DEFAULT_EXPORT_ROOT / "st_annes_work_log_events.json", artifact_kind="work_log_read_model"),
        _inventory_source(DEFAULT_EXPORT_ROOT / "st_annes_monthly_work_log_contract.json", artifact_kind="work_log_contract_read_model"),
        _inventory_source(DEFAULT_EXPORT_ROOT / "st_annes_work_log_review_surface.json", artifact_kind="operator_review_read_model"),
        _inventory_source(
            Path("generated/system_knowledge/st_annes_invoice_status_SEED.sql"),
            artifact_kind="invoice_status_seed_sql",
        ),
        *_st_annes_invoice_artifact_sources(),
    ]
    missing_source_refs = [row["source_ref"] for row in sources if row["required"] and not row["exists"]]
    source_inventory_exists = not missing_source_refs
    refs = _project_room_refs(scenario_ref)
    return {
        **refs,
        "package_ref": scenario_ref,
        "package_type": "client/business_draft",
        "uses_multiple_sources": True,
        "source_inventory_exists": source_inventory_exists,
        "duplicate_report_exists": source_inventory_exists,
        "decision_trace_exists": source_inventory_exists,
        "unresolved_critical_conflict": False,
        "version_families_exist": True,
        "repeated_or_failed_work": True,
        "missing_source_refs": missing_source_refs,
        "dry_run_artifact_order": ["pdf_proof", "clara_draft", "guardian_gate"],
        "source_inventory": {
            "source_inventory_ref": refs["source_inventory_ref"],
            "client_ref": "st_annes",
            "workflow_ref": "st_annes_monthly_invoice_rollup",
            "source_of_truth_policy": "project_invoice_source_of_truth",
            "sources": sources,
            "machine_proof": {
                "derived_from_existing_files": source_inventory_exists,
                "required_source_count": len([row for row in sources if row["required"]]),
                "missing_source_count": len(missing_source_refs),
                "pdf_proof_first": True,
                "live_worker_executed": False,
                "send_performed": False,
                "ledger_post_performed": False,
            },
        },
        "conflict_log": {
            "conflict_log_ref": refs["conflict_log_ref"],
            "status": "NO_UNRESOLVED_CRITICAL_CONFLICTS" if source_inventory_exists else "SOURCE_INVENTORY_INCOMPLETE",
            "conflicts": [],
        },
        "duplicate_report": {
            "duplicate_report_ref": refs["duplicate_report_ref"],
            "status": "VERSION_FAMILY_REVIEWED" if source_inventory_exists else "SOURCE_INVENTORY_INCOMPLETE",
            "current_source_refs": [row["source_ref"] for row in sources if row["exists"]],
            "stale_source_current_truth_allowed": False,
        },
        "decision_trace": {
            "decision_trace_ref": refs["decision_trace_ref"],
            "status": "PDF_PROOF_FIRST_DRY_RUN_ORDER_READY" if source_inventory_exists else "SOURCE_INVENTORY_INCOMPLETE",
            "artifact_order": ["pdf_proof", "clara_draft", "guardian_gate"],
            "live_worker_executed": False,
        },
    }


def _source_room_context_for_workflow(workflow_ref: str) -> dict[str, Any]:
    if workflow_ref == "capital_hilton_invoice_operator_assist":
        return {
            "package_ref": workflow_ref,
            "package_type": "proof_to_response",
            "current_proof_bundle_exists": True,
            "next_safe_action": "Explain the payment-watch state and request proof; do not mark paid or mutate ledger.",
        }
    if workflow_ref == "capital_hilton_proposal_followup":
        return {
            "package_ref": workflow_ref,
            "package_type": "client/business_draft",
            "uses_multiple_sources": True,
            "project_room_id": "project_room:business_development_capital_hilton_followup",
            "source_inventory_ref": "source_inventory:business_development_capital_hilton_followup",
            "conflict_log_ref": "conflict_log:business_development_capital_hilton_followup",
            "missing_context_ref": "missing_context:business_development_capital_hilton_followup",
            "duplicate_report_ref": "duplicate_report:business_development_capital_hilton_followup",
            "decision_trace_ref": "decision_trace:business_development_capital_hilton_followup",
            "freshness_gate_ref": "generated/read_models/context_freshness_decision_trace_gate.json",
            "compaction_policy_ref": "generated/read_models/context_compaction_preview_policy.json",
            "source_inventory_exists": True,
            "duplicate_report_exists": True,
            "decision_trace_exists": True,
            "unresolved_critical_conflict": True,
        }
    if workflow_ref == "st_annes_monthly_invoice_rollup":
        return _st_annes_monthly_invoice_source_room_context()
    return {
        "package_ref": workflow_ref,
        "package_type": "simple_answer",
        "explicitly_trivial": True,
    }


def operator_display_for_package(
    workflow_ref: str,
    package_status: str,
    *,
    blocker: str = "",
    source_text: str = "",
    source_surface: str = "",
    world: str = "",
    client_ref: str | None = None,
    authority_boundary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build calm operator-facing copy while keeping machine fields elsewhere."""
    voice_fields = agent_voice_router.route_agent_voice_dict(
        workflow_ref=workflow_ref,
        package_status=package_status,
        source_text=source_text,
        source_surface=source_surface,
        world=world,
        client_ref=client_ref,
        authority_boundary=authority_boundary or AUTHORITY_BOUNDARY_DEFAULT,
        blocker=blocker,
    )
    if workflow_ref == "st_annes_work_log_event":
        return {
            **voice_fields,
            "headline": "St. Anne's work log captured",
            "subheadline": "Church sound event saved for review.",
            "status_label": "Needs confirmation",
            "tone": "warning",
            "plain_summary": "Saved as a draft event until you confirm it.",
            "next_safe_action": "Confirm or discard.",
            "why_it_matters": "Confirmed work-log events become the source for the month-end invoice package.",
            "primary_fact": "No invoice was changed.",
            "secondary_facts": [
                "No email will be sent.",
                "No ledger entry was touched.",
            ],
            "proof_caption": "Proof available.",
            "show_machine_details_by_default": False,
        }
    if workflow_ref == "capital_hilton_proposal_followup":
        return {
            **voice_fields,
            "headline": "Proposal follow-up staged",
            "subheadline": "Business Development follow-up, no finance action.",
            "status_label": "Needs review",
            "tone": "calm",
            "plain_summary": "No email will be sent until approved.",
            "next_safe_action": "Review the follow-up.",
            "why_it_matters": "Proposal follow-up stays separate from finance until the client accepts.",
            "primary_fact": "No invoice was created.",
            "secondary_facts": [
                "No email will be sent.",
                "No finance handoff was opened.",
            ],
            "proof_caption": "Proof available.",
            "show_machine_details_by_default": False,
        }
    if workflow_ref == "capital_hilton_invoice_operator_assist":
        return {
            **voice_fields,
            "headline": "Capital Hilton needs operator assist",
            "subheadline": "Coupa requires a live submit gate.",
            "status_label": "Provider gate required",
            "tone": "blocked",
            "plain_summary": "Coupa cannot run unattended.",
            "next_safe_action": "Stage an operator-assist packet.",
            "why_it_matters": "Portal submission and email send are external actions that need a human gate.",
            "primary_fact": "No invoice was submitted.",
            "secondary_facts": [
                "No Coupa action ran.",
                "No email will be sent.",
            ],
            "proof_caption": "Proof available.",
            "show_machine_details_by_default": False,
        }
    if workflow_ref == "st_annes_monthly_invoice_rollup":
        missing = "the required invoice permission and artifact gates"
        if package_status == "ARTIFACT_REQUIRED":
            missing = "an approved invoice PDF artifact"
        elif package_status == "PERMISSION_REQUIRED":
            missing = "stable workbook/PDF permissions and an explicit send gate"
        if blocker:
            missing = blocker.rstrip(".")
        return {
            **voice_fields,
            "headline": "St. Anne's invoice is not ready to send",
            "subheadline": "Invoice work stays gated until proof is ready.",
            "status_label": "Missing prerequisite",
            "tone": "blocked",
            "plain_summary": f"Blocked because {missing}.",
            "next_safe_action": "Resolve the missing gate.",
            "why_it_matters": "Invoice sending must wait for approved artifacts and explicit operator authority.",
            "primary_fact": "No invoice was sent.",
            "secondary_facts": [
                "Excel was not touched.",
                "No ledger entry was touched.",
            ],
            "proof_caption": "Proof available.",
            "show_machine_details_by_default": False,
        }
    if package_status in {"PERMISSION_REQUIRED", "ARTIFACT_REQUIRED", "PROVIDER_GATE_REQUIRED"}:
        missing = blocker.rstrip(".") if blocker else "a required gate is missing"
        return {
            **voice_fields,
            "headline": "Workflow needs a gate",
            "subheadline": "A required permission is missing.",
            "status_label": "Blocked",
            "tone": "blocked",
            "plain_summary": f"Blocked because {missing}.",
            "next_safe_action": "Resolve the missing gate.",
            "why_it_matters": "OpenClaw keeps external actions closed until the right proof exists.",
            "primary_fact": "No business action ran.",
            "secondary_facts": [
                "No email will be sent.",
                "No ledger entry was touched.",
            ],
            "proof_caption": "Proof available.",
            "show_machine_details_by_default": False,
        }
    return {
        **voice_fields,
        "headline": "Workflow package staged",
            "subheadline": "Saved for operator review.",
            "status_label": "Needs review",
            "tone": "calm",
            "plain_summary": "Saved for review without running actions.",
            "next_safe_action": "Review the package.",
            "why_it_matters": "Operator review separates captured intent from live execution.",
            "primary_fact": "No external action ran.",
            "secondary_facts": [
                "No email will be sent.",
                "No ledger entry was touched.",
            ],
            "proof_caption": "Proof available.",
            "show_machine_details_by_default": False,
        }


def create_package(
    source_text: str,
    *,
    source_surface: str = "mission_control",
    created_at: str | None = None,
    config: QueueConfig | None = None,
    intent_override: Mapping[str, Any] | None = None,
    lm1_shared_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or QueueConfig()
    created_at = _now_or_fixed(created_at)
    privacy = _privacy_gate(source_text, source_surface)
    intent = _classify_intent_with_lm1_override(source_text, intent_override)
    protected_hash = protected_text_hash(source_text)
    workflow_ref = str(intent["workflow_ref"])
    capability = _capability_gate(workflow_ref, config, source_text=source_text)
    status = _package_status(workflow_ref, str(capability["status"]))
    operator_display = operator_display_for_package(
        workflow_ref,
        status,
        blocker=str(capability.get("reason") or ""),
        source_text=source_text,
        source_surface=source_surface,
        world=str(intent["world"]),
        client_ref=intent.get("client_ref"),
        authority_boundary=AUTHORITY_BOUNDARY_DEFAULT,
    )
    package_id = "workflow_package:" + _short_hash(source_surface, protected_hash, workflow_ref, created_at)
    worker_ref = "noop_worker:" + workflow_ref
    result_status = _worker_result_status(status)
    source_room_context = _source_room_context_for_workflow(workflow_ref)
    project_room_gate = compile_project_room_package_gate(source_room_context)
    dry_run_proof_bundle = _st_annes_dry_run_proof_bundle(source_room_context, capability)
    proof_refs = list(dry_run_proof_bundle.get("proof_refs") or [])
    business_action_gate = {
        "gate_ref": "business_action_gate:" + _short_hash(package_id),
        "status": "CLOSED",
        "reason": "V0 package queue records no live business actions.",
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "browser_access_allowed": False,
        "gmail_allowed": False,
        "coupa_allowed": False,
        "portal_submit_allowed": False,
        "workbook_source_mutation_allowed": False,
        "paid": False,
        "sent": False,
    }
    package = {
        "package_id": package_id,
        "workflow_ref": workflow_ref,
        "world": intent["world"],
        "client_ref": intent["client_ref"],
        "source_surface": source_surface,
        "source_text_ref": "protected_text_hash:" + protected_hash,
        "protected_text_hash": protected_hash,
        "pii_status": privacy["pii_status"],
        "privacy_impact": privacy["privacy_impact"],
        "provider_policy": capability["provider_policy"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY_DEFAULT),
        "operator_display": operator_display,
        "status": status,
        "project_room_required": project_room_gate["project_room_required"],
        "project_room_ready": project_room_gate["project_room_ready"],
        "synthesis_allowed": project_room_gate["synthesis_allowed"],
        "blocked_reason": project_room_gate["blocked_reason"],
        "next_safe_action": project_room_gate["next_safe_action"],
        "source_room_context": source_room_context,
        "proof_refs": proof_refs,
        "dry_run_proof_bundle": dry_run_proof_bundle,
        "project_room_gate_result": project_room_gate,
        "created_at": created_at,
        "updated_at": created_at,
        "privacy_redundancy_evaluator": dict(PRIVACY_EVALUATOR_DEFAULT),
        "privacy_gate_result": privacy,
        "intent_classification_result": intent,
        "lm1_shared_packet": dict(lm1_shared_packet or {}),
        "capability_gate_result": capability,
        "worker_assignment": {
            "assignment_ref": "worker_assignment:" + _short_hash(package_id, worker_ref),
            "worker_ref": worker_ref,
            "worker_kind": "dry_run_noop_worker",
            "assigned": True,
            "live_action_authority": False,
        },
        "worker_result": {
            "result_ref": "worker_result:" + _short_hash(package_id, result_status),
            "result_status": result_status,
            "summary": "Dry-run worker recorded package state only.",
            "live_worker_executed": False,
            "dry_run_proof_bundle_emitted": bool(dry_run_proof_bundle),
            "local_pdf_proof_rendered": any(ref["artifact_kind"] == "pdf_proof" for ref in proof_refs),
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
        },
        "operator_review_receipt": {
            "receipt_ref": "operator_review_receipt:" + _short_hash(package_id, status),
            "status": "OPERATOR_REVIEW_REQUIRED" if status in {"OPERATOR_REVIEW_REQUIRED", "PACKAGE_STAGED"} else "BLOCKED_PRE_REVIEW",
            "operator_review_required": True,
            "business_action_authority_granted": False,
        },
        "business_action_gate_result": business_action_gate,
    }
    return package


def build_contract_read_model(
    *,
    generated_at: str | None = None,
    config: QueueConfig | None = None,
) -> dict[str, Any]:
    generated_at = _now_or_fixed(generated_at)
    packages = [
        create_package(text, source_surface=surface, created_at=generated_at, config=config)
        for surface, text in FIXTURE_INSTRUCTIONS
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": "WORKFLOW_PACKAGE_QUEUE_V0_READY",
        "scope": "dry_run_noop_workers_only",
        "pipeline": list(PIPELINE_STAGES),
        "supported_package_types": list(SUPPORTED_PACKAGE_TYPES),
        "sqlite_path": str(DEFAULT_SQLITE_PATH),
        "authority_boundary_default": dict(AUTHORITY_BOUNDARY_DEFAULT),
        "privacy_redundancy_evaluator_required_fields": [
            "provider_considered",
            "data_exposure_class",
            "local_alternative",
            "final_provider_decision",
            "approval_required",
        ],
        "agent_voice_routing_contract_ref": "generated/read_models/agent_voice_routing_contract.json",
        "package_field_contract": [
            "package_id",
            "workflow_ref",
            "world",
            "client_ref",
            "source_surface",
            "source_text_ref",
            "protected_text_hash",
            "pii_status",
            "privacy_impact",
            "provider_policy",
            "authority_boundary",
            "operator_display",
            "status",
            "project_room_required",
            "project_room_ready",
            "synthesis_allowed",
            "blocked_reason",
            "next_safe_action",
            "source_room_context",
            "proof_refs",
            "project_room_gate_result",
            "created_at",
            "updated_at",
        ],
        "operator_display_schema": list(OPERATOR_DISPLAY_FIELDS),
        "packages": packages,
        "fixtures_summary": [
            {
                "workflow_ref": package["workflow_ref"],
                "client_ref": package["client_ref"],
                "world": package["world"],
                "status": package["status"],
                "capability_gate_status": package["capability_gate_result"]["status"],
            }
            for package in packages
        ],
        "machine_proof": {
            "dry_run_only": True,
            "sqlite_tables_required": [
                "packages",
                "package_inputs",
                "privacy_gate_results",
                "intent_classification_results",
                "capability_gate_results",
                "worker_assignments",
                "worker_results",
                "operator_review_receipts",
                "business_action_gate_results",
            ],
            "supported_package_type_count": len(SUPPORTED_PACKAGE_TYPES),
            "fixture_package_count": len(packages),
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY_DEFAULT.values()),
            "unsafe_true_grants_absent": True,
        },
    }


def _project_room_refs(scenario_ref: str) -> dict[str, str]:
    return {
        "project_room_id": f"project_room:{scenario_ref}",
        "source_inventory_ref": f"source_inventory:{scenario_ref}",
        "conflict_log_ref": f"conflict_log:{scenario_ref}",
        "missing_context_ref": f"missing_context:{scenario_ref}",
        "duplicate_report_ref": f"duplicate_report:{scenario_ref}",
        "decision_trace_ref": f"decision_trace:{scenario_ref}",
        "freshness_gate_ref": "generated/read_models/context_freshness_decision_trace_gate.json",
        "compaction_policy_ref": "generated/read_models/context_compaction_preview_policy.json",
    }


def project_room_compiler_requirement_examples() -> list[dict[str, Any]]:
    examples = [
        {
            "example_ref": "finance_capital_hilton_payment_watch",
            "title": "Finance / Capital Hilton payment watch",
            "package": {
                "package_ref": "package:finance:capital_hilton_payment_watch",
                "package_type": "proof_to_response",
                "current_proof_bundle_exists": True,
                "next_safe_action": "Explain payment evidence is missing and invite proof attachment; do not mark paid or touch ledger.",
            },
            "business_boundaries": {
                "paid_marking_allowed": False,
                "ledger_mutation_allowed": False,
            },
            "notes": ["simple/proof-to-response route", "current proof bundle required", "no paid or ledger action"],
        },
        {
            "example_ref": "business_development_capital_hilton_followup",
            "title": "Business Development / Capital Hilton follow-up",
            "package": {
                **_project_room_refs("business_development_capital_hilton_followup"),
                "package_ref": "package:bd:capital_hilton_followup",
                "package_type": "client/business_draft",
                "uses_multiple_sources": True,
                "source_inventory_exists": True,
                "duplicate_report_exists": True,
                "decision_trace_exists": True,
                "unresolved_critical_conflict": True,
            },
            "notes": ["proposal/history draft requires project room", "conflict must be surfaced", "no send authority"],
        },
        {
            "example_ref": "build_review_packet",
            "title": "Build review packet",
            "package": {
                **_project_room_refs("build_review_packet"),
                "package_ref": "package:build:review_packet",
                "package_type": "serious_synthesis",
                "source_inventory_exists": True,
                "duplicate_report_exists": True,
                "decision_trace_exists": True,
                "repeated_or_failed_work": True,
                "next_safe_action": "Summarize review history; keep resolved packet out of active work.",
            },
            "notes": ["decision trace required", "resolved packet remains history"],
        },
        {
            "example_ref": "niles_controller_mapping",
            "title": "Niles / Music controller mapping",
            "package": {
                **_project_room_refs("niles_music_controller_mapping"),
                "package_ref": "package:niles:controller_mapping_factual",
                "package_type": "serious_synthesis",
                "source_inventory_exists": True,
                "duplicate_report_exists": True,
                "decision_trace_exists": True,
                "missing_context_blocks_supported_claim": True,
            },
            "creative_options_allowed": True,
            "factual_mapping_allowed": False,
            "notes": ["target controller/software missing blocks factual mapping", "creative options remain allowed"],
        },
        {
            "example_ref": "self_heal_repair",
            "title": "Self-heal repair",
            "package": {
                **_project_room_refs("self_heal_repair"),
                "package_ref": "package:self_heal:repair",
                "package_type": "code/build/repair",
                "source_inventory_exists": True,
                "duplicate_report_exists": True,
                "decision_trace_exists": True,
                "repeated_or_failed_work": True,
                "validation_plan_ref": "validation_plan:self_heal_repair",
                "rollback_plan_ref": "rollback_plan:self_heal_repair",
                "next_safe_action": "Propose repair package with validation and rollback plan; do not spawn workers.",
            },
            "notes": ["repair room required", "blocker proof, validation plan, and rollback plan present"],
        },
        {
            "example_ref": "lm2_pilot",
            "title": "LM2 pilot",
            "package": {
                **_project_room_refs("lm2_pilot_bounded_objective"),
                "package_ref": "package:lm2:pilot_bounded_objective",
                "package_type": "LM2 worker package",
                "source_inventory_exists": True,
                "duplicate_report_exists": True,
                "decision_trace_exists": True,
                "current_proof_bundle_exists": True,
                "one_bounded_objective": True,
                "raw_messy_folder_dump_included": False,
                "full_log_dump_included": False,
                "unreviewed_duplicates_equal_evidence": False,
                "missing_context_invented": False,
                "next_safe_action": "Compile a bounded LM2 pilot package with project/proof refs only; do not spawn a worker.",
            },
            "notes": ["project/proof room required", "one bounded objective", "no raw messy folder dump"],
        },
    ]
    compiled: list[dict[str, Any]] = []
    for example in examples:
        gate = compile_project_room_package_gate(example["package"])
        compiled.append({**example, "compiler_gate": gate})
    return compiled


def build_project_room_package_compiler_integration_read_model(
    *,
    read_model_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = _now_or_fixed(generated_at)
    preconditions = project_room_compiler_preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    classifications = [
        classify_package_source_requirements("simple_answer"),
        classify_package_source_requirements("proof_to_response"),
        classify_package_source_requirements("serious_synthesis"),
        classify_package_source_requirements("client/business_draft", uses_multiple_sources=True),
        classify_package_source_requirements("code/build/repair"),
        classify_package_source_requirements("LM2 worker package"),
    ]
    examples = project_room_compiler_requirement_examples()
    classification_by_type = {row["package_type"]: row for row in classifications}
    project_room_refs_required_for_serious_packages = all(
        classification_by_type[package_type]["project_room_required"] is True
        for package_type in ("serious_synthesis", "client/business_draft", "code/build/repair", "LM2 worker package")
    )
    proof_to_response_may_use_current_proof_bundle_without_full_project_room = (
        classification_by_type["proof_to_response"]["project_room_required"] is False
        and classification_by_type["proof_to_response"]["proof_bundle_required"] is True
    )
    lm2_probe = compile_project_room_package_gate(
        {
            "package_ref": "probe:lm2_raw_context_blocks",
            "package_type": "LM2 worker package",
            **_project_room_refs("lm2_probe"),
            "source_inventory_exists": True,
            "duplicate_report_exists": True,
            "decision_trace_exists": True,
            "current_proof_bundle_exists": True,
            "one_bounded_objective": True,
            "raw_messy_folder_dump_included": True,
            "full_log_dump_included": True,
            "unreviewed_duplicates_equal_evidence": True,
            "missing_context_invented": True,
            "stale_superseded_source_as_current": True,
        }
    )
    lm2_raw_context_blocks_present = {
        "raw_messy_folder_dump_blocked",
        "full_log_dump_blocked",
        "unreviewed_duplicates_equal_evidence_blocked",
        "missing_context_invention_blocked",
        "stale_or_superseded_source_treated_as_current",
    }.issubset(set(lm2_probe["blockers"]))
    payload: dict[str, Any] = {
        "schema_version": "project_room_package_compiler_integration_v0",
        "read_model_id": PROJECT_ROOM_COMPILER_READ_MODEL_ID,
        "status": PROJECT_ROOM_COMPILER_READY_STATUS if preconditions_ready else PROJECT_ROOM_COMPILER_NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Require source rooms for serious workflow, worker, synthesis, and LM2 packages before synthesis or LM2 work.",
        "preconditions": preconditions,
        "required_project_room_refs": list(PROJECT_ROOM_REQUIRED_REFS),
        "package_source_requirement_classifications": classifications,
        "compiler_block_rules": [
            "Block serious synthesis when source inventory is missing.",
            "Block synthesis on unresolved critical conflicts.",
            "Block unsupported claims when missing context is unresolved.",
            "Block stale/superseded sources treated as current truth.",
            "Block version-family work when duplicate/version report is missing.",
            "Block repeated or failed work when decision trace is missing.",
            "Block LM2 worker packages from raw folder dumps, full logs by default, stale truth, unreviewed duplicate weighting, and invention from missing context.",
        ],
        "required_examples": examples,
        "package_status_fields": [
            "project_room_required",
            "project_room_ready",
            "synthesis_allowed",
            "blocked_reason",
            "next_safe_action",
        ],
        "authority_boundary": dict(PROJECT_ROOM_COMPILER_AUTHORITY_BOUNDARY),
        "implementation_boundary": {
            "model_invoked": False,
            "runtime_connected": False,
            "local_model_runtime_connected": False,
            "external_provider_connected": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "business_action_performed": False,
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
            "git_push_performed": False,
        },
        "machine_proof": {
            "contract_integration_only": True,
            "model_invocation_absent": True,
            "worker_spawn_absent": True,
            "business_action_absent": True,
            "preconditions_ready": preconditions_ready,
            "project_room_refs_required_for_serious_packages": project_room_refs_required_for_serious_packages,
            "proof_to_response_may_use_current_proof_bundle_without_full_project_room": proof_to_response_may_use_current_proof_bundle_without_full_project_room,
            "lm2_raw_context_blocks_present": lm2_raw_context_blocks_present,
            "all_blocks_return_human_next_safe_action": all(
                bool(example["compiler_gate"]["next_safe_action"]) for example in examples
            ),
            "unsafe_true_grants_absent": True,
        },
        "source_refs": [
            "generated/read_models/project_room_sourceset_contract.json",
            "generated/read_models/context_compaction_preview_policy.json",
            "generated/read_models/context_freshness_decision_trace_gate.json",
            "generated/read_models/proof_bundle_freshness_trace_status.json",
            "generated/read_models/workflow_composer_latest.json",
            "generated/read_models/worker_package_staging_status.json",
            "generated/read_models/lm2_live_worker_pilot_boundary_packet.json",
            "generated/read_models/universal_receipt_envelope_status.json",
            "generated/read_models/goldilocks_gate_calibration.json",
        ],
    }
    unsafe = project_room_compiler_unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if not all(value is True for value in payload["machine_proof"].values()):
        payload["status"] = PROJECT_ROOM_COMPILER_NOT_READY_STATUS
    if unsafe:
        payload["status"] = PROJECT_ROOM_COMPILER_NOT_READY_STATUS
    return payload


def build_project_room_package_compiler_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Project Room Package Compiler Integration",
        "",
        f"Status: `{read_model.get('status')}`",
        "",
        "Serious workflow, synthesis, repair, and LM2 packages must compile through source-room gates before synthesis or worker handoff.",
        "",
        "## Package Classes",
        "",
    ]
    for row in read_model.get("package_source_requirement_classifications") or []:
        lines.append(
            f"- `{row['package_type']}`: project room `{str(row['project_room_required']).lower()}`, proof bundle `{str(row['proof_bundle_required']).lower()}`. {row['requirement_reason']}"
        )
    lines.extend(["", "## Block Rules", ""])
    for rule in read_model.get("compiler_block_rules") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Examples", ""])
    for example in read_model.get("required_examples") or []:
        gate = example["compiler_gate"]
        status = "allowed" if gate["synthesis_allowed"] else "blocked"
        lines.append(f"- `{example['example_ref']}`: {status}; next safe action: {gate['next_safe_action']}")
    lines.extend(["", "## Boundary", ""])
    lines.append("No model invocation, local runtime connection, worker spawn, business action, email, browser/Gmail/Coupa, ledger/workbook mutation, paid marking, submission, PDF export, or push is granted.")
    return "\n".join(lines) + "\n"


def export_project_room_package_compiler_integration(
    *,
    read_model_root: Path = DEFAULT_EXPORT_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = PROJECT_ROOM_COMPILER_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_project_room_package_compiler_integration_read_model(
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / PROJECT_ROOM_COMPILER_JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / PROJECT_ROOM_COMPILER_JSON_EXPORT_NAME
        bridge_path.write_text(stable_json(read_model), encoding="utf-8")
        bridge_read_model_path = str(bridge_path)

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_project_room_package_compiler_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status")),
        "read_model_path": str(read_model_path),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": str(wiki_path),
    }


def sqlite_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS packages (
  package_id TEXT PRIMARY KEY,
  workflow_ref TEXT NOT NULL,
  world TEXT NOT NULL,
  client_ref TEXT,
  source_surface TEXT NOT NULL,
  source_text_ref TEXT NOT NULL,
  protected_text_hash TEXT NOT NULL,
  pii_status TEXT NOT NULL,
  privacy_impact_json TEXT NOT NULL,
  provider_policy TEXT NOT NULL,
  authority_boundary_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS package_inputs (
  package_id TEXT PRIMARY KEY,
  source_surface TEXT NOT NULL,
  source_text_ref TEXT NOT NULL,
  protected_text_hash TEXT NOT NULL,
  raw_text_stored INTEGER NOT NULL CHECK(raw_text_stored IN (0, 1)),
  FOREIGN KEY (package_id) REFERENCES packages(package_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS privacy_gate_results (
  package_id TEXT PRIMARY KEY,
  gate_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  pii_status TEXT NOT NULL,
  privacy_impact_json TEXT NOT NULL,
  FOREIGN KEY (package_id) REFERENCES packages(package_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS intent_classification_results (
  package_id TEXT PRIMARY KEY,
  workflow_ref TEXT NOT NULL,
  world TEXT NOT NULL,
  client_ref TEXT,
  confidence TEXT NOT NULL,
  intent_reason TEXT NOT NULL,
  FOREIGN KEY (package_id) REFERENCES packages(package_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS capability_gate_results (
  package_id TEXT PRIMARY KEY,
  gate_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT NOT NULL,
  provider_policy TEXT NOT NULL,
  provider_required INTEGER NOT NULL CHECK(provider_required IN (0, 1)),
  blocked_actions_json TEXT NOT NULL,
  FOREIGN KEY (package_id) REFERENCES packages(package_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS worker_assignments (
  package_id TEXT PRIMARY KEY,
  assignment_ref TEXT NOT NULL,
  worker_ref TEXT NOT NULL,
  worker_kind TEXT NOT NULL,
  assigned INTEGER NOT NULL CHECK(assigned IN (0, 1)),
  live_action_authority INTEGER NOT NULL CHECK(live_action_authority IN (0, 1)),
  FOREIGN KEY (package_id) REFERENCES packages(package_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS worker_results (
  package_id TEXT PRIMARY KEY,
  result_ref TEXT NOT NULL,
  result_status TEXT NOT NULL,
  summary TEXT NOT NULL,
  email_send_performed INTEGER NOT NULL CHECK(email_send_performed IN (0, 1)),
  ledger_mutation_performed INTEGER NOT NULL CHECK(ledger_mutation_performed IN (0, 1)),
  browser_access_performed INTEGER NOT NULL CHECK(browser_access_performed IN (0, 1)),
  gmail_access_performed INTEGER NOT NULL CHECK(gmail_access_performed IN (0, 1)),
  coupa_access_performed INTEGER NOT NULL CHECK(coupa_access_performed IN (0, 1)),
  workbook_mutation_performed INTEGER NOT NULL CHECK(workbook_mutation_performed IN (0, 1)),
  pdf_export_performed INTEGER NOT NULL CHECK(pdf_export_performed IN (0, 1)),
  paid_marking_performed INTEGER NOT NULL CHECK(paid_marking_performed IN (0, 1)),
  submit_performed INTEGER NOT NULL CHECK(submit_performed IN (0, 1)),
  FOREIGN KEY (package_id) REFERENCES packages(package_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS operator_review_receipts (
  package_id TEXT PRIMARY KEY,
  receipt_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  operator_review_required INTEGER NOT NULL CHECK(operator_review_required IN (0, 1)),
  business_action_authority_granted INTEGER NOT NULL CHECK(business_action_authority_granted IN (0, 1)),
  FOREIGN KEY (package_id) REFERENCES packages(package_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS business_action_gate_results (
  package_id TEXT PRIMARY KEY,
  gate_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT NOT NULL,
  email_send_allowed INTEGER NOT NULL CHECK(email_send_allowed IN (0, 1)),
  ledger_posting_allowed INTEGER NOT NULL CHECK(ledger_posting_allowed IN (0, 1)),
  browser_access_allowed INTEGER NOT NULL CHECK(browser_access_allowed IN (0, 1)),
  gmail_allowed INTEGER NOT NULL CHECK(gmail_allowed IN (0, 1)),
  coupa_allowed INTEGER NOT NULL CHECK(coupa_allowed IN (0, 1)),
  portal_submit_allowed INTEGER NOT NULL CHECK(portal_submit_allowed IN (0, 1)),
  workbook_source_mutation_allowed INTEGER NOT NULL CHECK(workbook_source_mutation_allowed IN (0, 1)),
  paid INTEGER NOT NULL CHECK(paid IN (0, 1)),
  sent INTEGER NOT NULL CHECK(sent IN (0, 1)),
  FOREIGN KEY (package_id) REFERENCES packages(package_id) ON DELETE CASCADE
);
""".strip() + "\n"


def init_sqlite(sqlite_path: Path) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(sqlite_schema_sql())
        conn.commit()
    finally:
        conn.close()


def record_package(sqlite_path: Path, package: Mapping[str, Any]) -> None:
    init_sqlite(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        package_id = str(package["package_id"])
        conn.execute(
            """
            INSERT OR REPLACE INTO packages (
              package_id, workflow_ref, world, client_ref, source_surface,
              source_text_ref, protected_text_hash, pii_status, privacy_impact_json,
              provider_policy, authority_boundary_json, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                package_id,
                str(package["workflow_ref"]),
                str(package["world"]),
                package.get("client_ref"),
                str(package["source_surface"]),
                str(package["source_text_ref"]),
                str(package["protected_text_hash"]),
                str(package["pii_status"]),
                stable_json(package["privacy_impact"]),
                str(package["provider_policy"]),
                stable_json(package["authority_boundary"]),
                str(package["status"]),
                str(package["created_at"]),
                str(package["updated_at"]),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO package_inputs (
              package_id, source_surface, source_text_ref, protected_text_hash, raw_text_stored
            ) VALUES (?, ?, ?, ?, 0)
            """,
            (
                package_id,
                str(package["source_surface"]),
                str(package["source_text_ref"]),
                str(package["protected_text_hash"]),
            ),
        )
        privacy = package["privacy_gate_result"]
        conn.execute(
            """
            INSERT OR REPLACE INTO privacy_gate_results (
              package_id, gate_ref, status, pii_status, privacy_impact_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                package_id,
                str(privacy["gate_ref"]),
                str(privacy["status"]),
                str(privacy["pii_status"]),
                stable_json(privacy["privacy_impact"]),
            ),
        )
        intent = package["intent_classification_result"]
        conn.execute(
            """
            INSERT OR REPLACE INTO intent_classification_results (
              package_id, workflow_ref, world, client_ref, confidence, intent_reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                package_id,
                str(intent["workflow_ref"]),
                str(intent["world"]),
                intent.get("client_ref"),
                str(intent["confidence"]),
                str(intent["intent_reason"]),
            ),
        )
        capability = package["capability_gate_result"]
        conn.execute(
            """
            INSERT OR REPLACE INTO capability_gate_results (
              package_id, gate_ref, status, reason, provider_policy, provider_required, blocked_actions_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                package_id,
                str(capability["gate_ref"]),
                str(capability["status"]),
                str(capability["reason"]),
                str(capability["provider_policy"]),
                int(bool(capability["provider_required"])),
                stable_json(list(capability["blocked_actions"])),
            ),
        )
        assignment = package["worker_assignment"]
        conn.execute(
            """
            INSERT OR REPLACE INTO worker_assignments (
              package_id, assignment_ref, worker_ref, worker_kind, assigned, live_action_authority
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                package_id,
                str(assignment["assignment_ref"]),
                str(assignment["worker_ref"]),
                str(assignment["worker_kind"]),
                int(bool(assignment["assigned"])),
                int(bool(assignment["live_action_authority"])),
            ),
        )
        result = package["worker_result"]
        conn.execute(
            """
            INSERT OR REPLACE INTO worker_results (
              package_id, result_ref, result_status, summary, email_send_performed,
              ledger_mutation_performed, browser_access_performed, gmail_access_performed,
              coupa_access_performed, workbook_mutation_performed, pdf_export_performed,
              paid_marking_performed, submit_performed
            ) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            """,
            (
                package_id,
                str(result["result_ref"]),
                str(result["result_status"]),
                str(result["summary"]),
            ),
        )
        review = package["operator_review_receipt"]
        conn.execute(
            """
            INSERT OR REPLACE INTO operator_review_receipts (
              package_id, receipt_ref, status, operator_review_required, business_action_authority_granted
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                package_id,
                str(review["receipt_ref"]),
                str(review["status"]),
                int(bool(review["operator_review_required"])),
                int(bool(review["business_action_authority_granted"])),
            ),
        )
        business_gate = package["business_action_gate_result"]
        conn.execute(
            """
            INSERT OR REPLACE INTO business_action_gate_results (
              package_id, gate_ref, status, reason, email_send_allowed,
              ledger_posting_allowed, browser_access_allowed, gmail_allowed, coupa_allowed,
              portal_submit_allowed, workbook_source_mutation_allowed, paid, sent
            ) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            """,
            (
                package_id,
                str(business_gate["gate_ref"]),
                str(business_gate["status"]),
                str(business_gate["reason"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def record_packages(sqlite_path: Path, packages: list[Mapping[str, Any]]) -> None:
    init_sqlite(sqlite_path)
    for package in packages:
        record_package(sqlite_path, package)


def build_operator_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Workflow Package Queue",
        "",
        "Status: `WORKFLOW_PACKAGE_QUEUE_V0_READY`",
        "",
        "This is the first durable package queue/status machine for turning human-style instructions from Mission Control, Telegram, Cassandra, manual entry, or Codex into gated workflow packages.",
        "",
        "V0 uses dry-run/no-op workers only. It does not connect Telegram live, send email, open Gmail/browser/Coupa, mutate ledgers, mutate workbooks, export PDFs, mark paid, or submit anything.",
        "",
        "## Pipeline",
        "",
    ]
    lines.extend(f"{index}. `{stage}`" for index, stage in enumerate(read_model["pipeline"], start=1))
    lines.extend(
        [
            "",
            "## Supported Package Types",
            "",
        ]
    )
    lines.extend(f"- `{item}`" for item in read_model["supported_package_types"])
    lines.extend(
        [
            "",
            "## Fixture Results",
            "",
        ]
    )
    for item in read_model["fixtures_summary"]:
        lines.append(
            f"- `{item['workflow_ref']}`: status `{item['status']}`, capability gate `{item['capability_gate_status']}`"
        )
    lines.extend(
        [
            "",
            "## Operator Display Layer",
            "",
            "Package responses include `operator_display` for Mission Control cards while retaining machine fields in proof/details.",
            "",
        ]
    )
    lines.extend(f"- `{field}`" for field in read_model["operator_display_schema"])
    lines.extend(
        [
            "",
            "Example display headlines:",
            "",
        ]
    )
    for package in read_model["packages"]:
        display = package["operator_display"]
        lines.append(
            f"- {display['headline']}: {display['status_label']} - {display['next_safe_action']}"
        )
    lines.extend(
        [
            "",
            "## Authority Boundary",
            "",
            "- Email send allowed: no",
            "- Ledger posting allowed: no",
            "- Browser/Gmail/Coupa/portal allowed: no",
            "- Workbook source mutation allowed: no",
            "- Paid marking allowed: no",
            "- Sent state granted: no",
            "",
            "## Notes",
            "",
            "- Telegram intake records work-log/package intent only in V0.",
            "- St. Anne's invoice send is blocked without permission/artifact gates.",
            "- Capital Hilton Coupa submission is blocked without an explicitly staged operator-assist provider and Submit gate.",
            "- Capital Hilton proposal follow-up is Business Development only and creates no invoice.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_workflow_package_queue(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    config: QueueConfig | None = None,
) -> ExportResult:
    read_model = build_contract_read_model(generated_at=generated_at, config=config)
    packages = list(read_model["packages"])
    local_root = _rooted(export_root)
    local_root.mkdir(parents=True, exist_ok=True)
    read_model_path = local_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = str(bridge_file)

    resolved_wiki_path = _rooted(wiki_path)
    resolved_wiki_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_wiki_path.write_text(build_operator_wiki(read_model), encoding="utf-8")

    resolved_sqlite_path = _rooted(sqlite_path)
    record_packages(resolved_sqlite_path, packages)

    return ExportResult(
        read_model_path=str(read_model_path),
        bridge_read_model_path=bridge_path,
        wiki_path=str(resolved_wiki_path),
        sqlite_path=str(resolved_sqlite_path),
        package_count=len(packages),
        supported_package_types=SUPPORTED_PACKAGE_TYPES,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Workflow Package Queue V0 contract.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_workflow_package_queue(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    payload = {
        "status": "WORKFLOW_PACKAGE_QUEUE_V0_READY",
        "read_model_path": result.read_model_path,
        "bridge_read_model_path": result.bridge_read_model_path,
        "wiki_path": result.wiki_path,
        "sqlite_path": result.sqlite_path,
        "package_count": result.package_count,
        "supported_package_types": list(result.supported_package_types),
    }
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
