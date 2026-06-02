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


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Workflow Package Queue.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/workflow_package_queue.sqlite")

SCHEMA_VERSION = "workflow_package_queue_v0"
READ_MODEL_ID = "workflow_package_queue_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"

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


def classify_intent(source_text: str) -> dict[str, Any]:
    text = source_text.lower()
    st_annes_mentioned = "st. anne" in text or "st anne" in text or "anne's" in text or "annes" in text
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
    if st_annes_mentioned and ("invoice" in text or "send" in text or "rollup" in text):
        return {
            "workflow_ref": "st_annes_monthly_invoice_rollup",
            "world": "invoice_operations",
            "client_ref": "st_annes",
            "confidence": "high",
            "intent_reason": "Detected St. Anne's invoice instruction.",
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


def _capability_gate(workflow_ref: str, config: QueueConfig) -> dict[str, Any]:
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
        if not config.st_annes_send_permission_ready:
            return {
                "gate_ref": "capability_gate:st_annes_invoice_send_permission",
                "status": "PERMISSION_REQUIRED",
                "reason": "Send permission registry is not ready for V0 package execution.",
                "provider_policy": "blocked_until_permission_registry_ready",
                "provider_required": True,
                "blocked_actions": ("email_send", "workbook_write", "pdf_export"),
            }
        if not config.st_annes_approved_pdf_artifact_available:
            return {
                "gate_ref": "capability_gate:st_annes_invoice_artifact",
                "status": "ARTIFACT_REQUIRED",
                "reason": "No approved PDF artifact is available for a send package.",
                "provider_policy": "blocked_until_approved_artifact",
                "provider_required": True,
                "blocked_actions": ("email_send",),
            }
        return {
            "gate_ref": "capability_gate:st_annes_invoice_rollup",
            "status": "ALLOW_DRY_RUN",
            "reason": "Invoice rollup can be staged for operator review only.",
            "provider_policy": "local_noop_worker_only",
            "provider_required": False,
            "blocked_actions": ("email_send", "workbook_write", "pdf_export"),
        }
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


def operator_display_for_package(
    workflow_ref: str,
    package_status: str,
    *,
    blocker: str = "",
) -> dict[str, Any]:
    """Build calm operator-facing copy while keeping machine fields elsewhere."""
    if workflow_ref == "st_annes_work_log_event":
        return {
            "headline": "St. Anne's work log captured",
            "subheadline": "Church sound event saved for review.",
            "status_label": "Needs confirmation",
            "tone": "warning",
            "plain_summary": "I saved this as a draft work event. Confirm it before it counts toward the monthly invoice.",
            "next_safe_action": "Review and confirm the event.",
            "why_it_matters": "Confirmed work-log events become the source for the month-end invoice package.",
            "primary_fact": "No invoice was changed.",
            "secondary_facts": [
                "No email will be sent.",
                "No ledger entry was touched.",
            ],
            "proof_caption": "Proof available",
            "show_machine_details_by_default": False,
        }
    if workflow_ref == "capital_hilton_proposal_followup":
        return {
            "headline": "Capital Hilton proposal follow-up staged",
            "subheadline": "Business Development follow-up, no finance action.",
            "status_label": "Needs review",
            "tone": "calm",
            "plain_summary": "I staged this as a proposal follow-up. No email will be sent until you approve it.",
            "next_safe_action": "Review the follow-up plan.",
            "why_it_matters": "Proposal follow-up stays separate from finance until the client accepts.",
            "primary_fact": "No invoice was created.",
            "secondary_facts": [
                "No email will be sent.",
                "No finance handoff was opened.",
            ],
            "proof_caption": "Proof available",
            "show_machine_details_by_default": False,
        }
    if workflow_ref == "capital_hilton_invoice_operator_assist":
        return {
            "headline": "Capital Hilton invoice needs operator assist",
            "subheadline": "Coupa requires a live submit gate.",
            "status_label": "Provider gate required",
            "tone": "blocked",
            "plain_summary": "This cannot run unattended. Coupa submission requires an operator-present workflow and a final Submit confirmation.",
            "next_safe_action": "Stage an operator-assist packet when you are ready.",
            "why_it_matters": "Portal submission and email send are external actions that need a human gate.",
            "primary_fact": "No invoice was submitted.",
            "secondary_facts": [
                "No Coupa action ran.",
                "No email will be sent.",
            ],
            "proof_caption": "Proof available",
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
            "headline": "St. Anne's invoice is not ready to send",
            "subheadline": "Invoice work stays gated until proof is ready.",
            "status_label": "Missing prerequisite",
            "tone": "blocked",
            "plain_summary": f"This is blocked because {missing}. No email will be sent.",
            "next_safe_action": "Resolve the missing gate, then review the package again.",
            "why_it_matters": "Invoice sending must wait for approved artifacts and explicit operator authority.",
            "primary_fact": "No invoice was sent.",
            "secondary_facts": [
                "Excel was not touched.",
                "No ledger entry was touched.",
            ],
            "proof_caption": "Proof available",
            "show_machine_details_by_default": False,
        }
    if package_status in {"PERMISSION_REQUIRED", "ARTIFACT_REQUIRED", "PROVIDER_GATE_REQUIRED"}:
        missing = blocker.rstrip(".") if blocker else "a required gate is missing"
        return {
            "headline": "Workflow needs a gate",
            "subheadline": "A required permission is missing.",
            "status_label": "Blocked",
            "tone": "blocked",
            "plain_summary": f"This is blocked because {missing}. Nothing ran.",
            "next_safe_action": "Resolve the missing gate, then review the package again.",
            "why_it_matters": "OpenClaw keeps external actions closed until the right proof exists.",
            "primary_fact": "No business action ran.",
            "secondary_facts": [
                "No email will be sent.",
                "No ledger entry was touched.",
            ],
            "proof_caption": "Proof available",
            "show_machine_details_by_default": False,
        }
    return {
        "headline": "Workflow package staged",
        "subheadline": "Saved for operator review.",
        "status_label": "Needs review",
        "tone": "calm",
        "plain_summary": "I staged this as a dry-run package. No business action ran.",
        "next_safe_action": "Review the staged package.",
        "why_it_matters": "Operator review separates captured intent from live execution.",
        "primary_fact": "No external action ran.",
        "secondary_facts": [
            "No email will be sent.",
            "No ledger entry was touched.",
        ],
        "proof_caption": "Proof available",
        "show_machine_details_by_default": False,
    }


def create_package(
    source_text: str,
    *,
    source_surface: str = "mission_control",
    created_at: str | None = None,
    config: QueueConfig | None = None,
) -> dict[str, Any]:
    config = config or QueueConfig()
    created_at = _now_or_fixed(created_at)
    privacy = _privacy_gate(source_text, source_surface)
    intent = classify_intent(source_text)
    protected_hash = protected_text_hash(source_text)
    workflow_ref = str(intent["workflow_ref"])
    capability = _capability_gate(workflow_ref, config)
    status = _package_status(workflow_ref, str(capability["status"]))
    operator_display = operator_display_for_package(
        workflow_ref,
        status,
        blocker=str(capability.get("reason") or ""),
    )
    package_id = "workflow_package:" + _short_hash(source_surface, protected_hash, workflow_ref, created_at)
    worker_ref = "noop_worker:" + workflow_ref
    result_status = _worker_result_status(status)
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
        "created_at": created_at,
        "updated_at": created_at,
        "privacy_redundancy_evaluator": dict(PRIVACY_EVALUATOR_DEFAULT),
        "privacy_gate_result": privacy,
        "intent_classification_result": intent,
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
