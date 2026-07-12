"""First-class capability gap and authority loop V0.

This module defines deterministic contracts for missing capabilities. It does
not invoke tools, call providers, open Gmail/browser UI, or grant authority from
raw prompt text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import global_run_mode_context
import capability_registry_build_provenance
from email_intent import email_intent_requires_draft, email_intent_requires_read

ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/First Class Capability Authority Loop.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/first_class_capability_authority_loop.sqlite")

SCHEMA_VERSION = "first_class_capability_authority_loop_v0"
READ_MODEL_ID = "first_class_capability_authority_loop"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_FIRST_CLASS_CAPABILITY_AUTHORITY_LOOP_READY"
NOT_READY_STATUS = "OPENCLAW_FIRST_CLASS_CAPABILITY_AUTHORITY_LOOP_NOT_READY"

CAPABILITY_GAP_SCHEMA = "CAPABILITY_GAP_V0"
AUTHORITY_REQUEST_SCHEMA = "OPERATOR_AUTHORITY_REQUEST_V0"
AUTHORITY_GRANT_SCHEMA = "OPERATOR_AUTHORITY_GRANT_V0"
CAPABILITY_BUILD_REQUEST_SCHEMA = "CAPABILITY_BUILD_REQUEST_V0"
CAPABILITY_BUILD_AUTHORITY_REQUEST_SCHEMA = "CAPABILITY_BUILD_AUTHORITY_REQUEST_V0"
CAPABILITY_ACTIVATION_RECEIPT_SCHEMA = "CAPABILITY_ACTIVATION_RECEIPT_V0"

READ_ONLY_EMAIL_LOOKUP = "openclaw.read_only_email_lookup"
FOLLOW_UP_DRAFT_GENERATOR = "openclaw.follow_up_draft_generator"
CONTACT_IDENTITY_EXTRACTION = "openclaw.contact_identity_extraction"
PAYMENT_UNCERTAINTY_SUMMARIZER = "openclaw.payment_uncertainty_summarizer"

READ_ONLY_EMAIL_ACTIONS = (
    "search_relevant_email_evidence",
    "read_relevant_email_evidence",
    "summarize_relevant_email_evidence_with_receipt",
)

PROHIBITED_EMAIL_ACTIONS = (
    "send_email",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "open_gmail_ui",
    "open_browser",
    "coupa_submit",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "git_push",
    "git_merge",
)

COMMON_DENIED_ACTIONS = (
    "send_email",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "open_gmail_ui",
    "open_browser",
    "mutate_contacts",
    "promote_contact_memory",
    "infer_identity_without_proof",
    "coupa_submit",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "claim_receipt_without_evidence",
    "git_push",
    "git_merge",
)

BUILD_ACTIONS = (
    "inspect_local_connector_contracts",
    "write_local_adapter_code",
    "write_tests",
    "publish_read_model_contract",
)

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "gmail_ui_allowed": False,
    "email_delete_allowed": False,
    "email_archive_allowed": False,
    "email_mark_read_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "external_model_allowed": False,
    "lm2_tool_expansion_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "authority_granted",
    "incoming_authority_granted_accepted",
    "raw_authority_granted_trusted",
    "email_checked",
    "email_received",
    "draft_sent",
    "contact_saved",
    "ledger_updated",
    "paid_marked",
    "workflow_package_request_v0_emitted",
}

CONTACT_IDENTITY_TERMS = (
    "knows her name",
    "name, email",
    "email, and role",
    "new accountant",
    "record this contact",
    "save this contact",
    "contact details",
)

PAYMENT_UNCERTAINTY_TERMS = (
    "expected payment",
    "expected an april check",
    "have not received",
    "haven't received",
    "summarize what we know",
    "what proof would resolve",
    "combined check",
    "assume",
)

GRANT_INTENT_PHRASES = (
    "i grant",
    "grant you access",
    "grant read-only email lookup",
    "authorize that",
    "authorize this",
    "you can build that capability",
    "grant access",
    "grant it",
    "ok, grant access to build that",
    "authorize you to build",
    "permission to implement",
    "make the system able",
)

BUILD_AUTHORITY_INTENT_PHRASES = (
    "grant access to build",
    "build the email lookup capability",
    "authorize you to build",
    "permission to implement",
    "permission to build",
    "make the system able",
    "yes, make the system able",
    "ok, i authorize you to build that",
    "ok, grant access to build that",
)

CAPABILITY_SPECS: dict[str, dict[str, Any]] = {
    READ_ONLY_EMAIL_LOOKUP: {
        "label": "Read-only email lookup",
        "blocked_reason": "read-only email lookup is not available with verified scoped authority in this lane",
        "required_authority": "scoped read-only email lookup build authority, then separate live read-only email access authority",
        "allowed_now": ["use pasted or attached email evidence", "prepare a draft-only follow-up"],
        "safe_alternative_now": "Paste or attach the relevant email evidence.",
        "next_safe_step": "Paste or attach the email evidence, or authorize a scoped read-only email lookup build request.",
        "proof_or_context_needed": ["operator-provided email evidence", "scoped build request", "later live read-only authority grant"],
        "denied_actions": [
            "send_email",
            "delete_email",
            "archive_email",
            "mark_email_read",
            "open_gmail_ui",
            "open_browser",
            "mutate_contacts",
            "claim_receipt_without_evidence",
        ],
        "operator_message": "I don't have read-only email lookup yet. I don't have read-only email lookup access yet, so I can't check Gmail or claim whether a reply exists. Paste or attach the email evidence, or authorize a scoped read-only email lookup build request.",
    },
    FOLLOW_UP_DRAFT_GENERATOR: {
        "label": "Follow-up draft generator",
        "blocked_reason": "live sending and mailbox access are denied; draft-only text is allowed",
        "required_authority": "send authority is required for delivery; no live send authority is present",
        "allowed_now": ["draft text for operator review"],
        "safe_alternative_now": "Prepare draft text only for operator review.",
        "next_safe_step": "Review the draft before any separate send path.",
        "proof_or_context_needed": ["operator-provided recipient/context", "separate send authority before delivery"],
        "denied_actions": ["send_email", "add_recipients_silently", "open_gmail_ui", "open_browser", "coupa_submit", "mark_paid", "mutate_ledger"],
        "operator_message": "I can draft a follow-up for review only. I will not send it, open Gmail, claim delivery, submit anything, mark paid, or mutate the ledger.",
    },
    CONTACT_IDENTITY_EXTRACTION: {
        "label": "Contact identity extraction",
        "blocked_reason": "verified source proof and separate memory/contact-promotion authority are required before permanent contact promotion",
        "required_authority": "verified contact proof plus explicit memory/contact-promotion authority",
        "allowed_now": ["record a candidate contact note from operator-provided details"],
        "safe_alternative_now": "Paste or attach the source email, or provide exact contact details.",
        "next_safe_step": "Paste or attach source proof for the contact details.",
        "proof_or_context_needed": ["source email or exact operator-provided contact details", "contact-promotion authority"],
        "denied_actions": ["open_gmail_ui", "open_browser", "gmail_lookup", "promote_contact_memory", "mutate_contacts", "infer_identity_without_proof"],
        "operator_message": "I can hold this as a candidate contact note only. I will not fabricate her name, email, or role, and I will not permanently save contact memory without verified proof and separate authority.",
    },
    PAYMENT_UNCERTAINTY_SUMMARIZER: {
        "label": "Payment uncertainty summarizer",
        "blocked_reason": "payment status cannot be confirmed without proof; summary-only handling is allowed",
        "required_authority": "payment evidence is required before paid marking or ledger mutation",
        "allowed_now": ["summarize known facts, assumptions, and proof needed"],
        "safe_alternative_now": "Separate known facts, assumptions, and proof needed.",
        "next_safe_step": "Verify acknowledgment or payment evidence.",
        "proof_or_context_needed": ["payment acknowledgment", "check receipt", "ledger-safe payment proof"],
        "denied_actions": ["mark_paid", "mutate_ledger", "claim_check_received_without_proof", "confirm_payment_without_proof"],
        "operator_message": "I can summarize what is known, what is assumed, and what proof would resolve it. I will not mark paid, mutate the ledger, or claim a check was received without proof.",
    },
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: object, length: int = 16) -> str:
    joined = "\0".join(stable_json(part) if isinstance(part, (dict, list)) else str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _walk(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def scope_from_context(world_ref: str, thread_ref: str, project_ref: str = "") -> dict[str, str]:
    return {
        "target_world_ref": str(world_ref or "").strip(),
        "target_thread_ref": str(thread_ref or "").strip(),
        "target_project_ref": str(project_ref or "").strip(),
    }


def detects_read_only_email_lookup_intent(text: str, *, world_ref: str = "", thread_ref: str = "") -> bool:
    return email_intent_requires_read(
        text,
        context=" ".join((str(world_ref or ""), str(thread_ref or ""))).strip(),
    )


def detect_capability_intent(text: str, *, world_ref: str = "", thread_ref: str = "") -> str:
    lowered = " ".join([str(text or ""), world_ref, thread_ref]).lower()
    if any(term in lowered for term in CONTACT_IDENTITY_TERMS):
        return CONTACT_IDENTITY_EXTRACTION
    if any(term in lowered for term in PAYMENT_UNCERTAINTY_TERMS):
        return PAYMENT_UNCERTAINTY_SUMMARIZER
    context = " ".join((str(world_ref or ""), str(thread_ref or ""))).strip()
    if detects_read_only_email_lookup_intent(text, world_ref=world_ref, thread_ref=thread_ref):
        return READ_ONLY_EMAIL_LOOKUP
    if email_intent_requires_draft(text, context=context):
        return FOLLOW_UP_DRAFT_GENERATOR
    return ""


def capability_gap_id(capability_id: str, scope: Mapping[str, Any], reason: str) -> str:
    return f"capability_gap:{_short_hash(capability_id, scope, reason)}"


def build_capability_gap(
    *,
    capability_id: str = READ_ONLY_EMAIL_LOOKUP,
    reason: str,
    requested_for_lane: str,
    requested_for_project: str = "",
    run_mode_context: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    run_context = dict(run_mode_context or global_run_mode_context.default_run_mode_context(generated_at=generated_at))
    scope = scope_from_context(*(requested_for_lane.split("/", 1) + [""])[:2], project_ref=requested_for_project)
    scope["run_mode"] = str(run_context.get("run_mode") or global_run_mode_context.PRODUCTION)
    scope["test_run_id"] = str(run_context.get("test_run_id") or "")
    spec = CAPABILITY_SPECS.get(capability_id, CAPABILITY_SPECS[READ_ONLY_EMAIL_LOOKUP])
    gap = {
        "schema_version": CAPABILITY_GAP_SCHEMA,
        "gap_id": capability_gap_id(capability_id, scope, reason),
        "capability_id": capability_id,
        "capability_label": spec["label"],
        "requested_intent": reason,
        "lane_context": dict(scope),
        "blocked_reason": spec["blocked_reason"],
        "required_authority": spec["required_authority"],
        "allowed_now": list(spec["allowed_now"]),
        "denied_actions": list(dict.fromkeys(spec["denied_actions"] + list(COMMON_DENIED_ACTIONS))),
        "safe_alternative_now": spec["safe_alternative_now"],
        "next_safe_step": spec["next_safe_step"],
        "can_request_build": capability_id == READ_ONLY_EMAIL_LOOKUP,
        "can_request_live_authority": False,
        "proof_or_context_needed": list(spec["proof_or_context_needed"]),
        "freshness_status": "not_checked_no_live_access",
        "operator_message": spec["operator_message"],
        "details": {
            "developer_refs": [
                "capability_authority_loop.py",
                "operator_conversation_router.py",
                "openclaw_plugin_contract.py",
            ],
            "raw_authority_granted_trusted": False,
        },
        "reason": reason,
        "requested_for_lane": requested_for_lane,
        "requested_for_project": requested_for_project,
        "requested_scope": dict(scope),
        "allowed_if_granted": list(READ_ONLY_EMAIL_ACTIONS),
        "prohibited_always": list(dict.fromkeys(spec["denied_actions"] + list(COMMON_DENIED_ACTIONS))),
        "proof_needed": [
            "scoped operator authority grant",
            "connector or local adapter activation receipt",
            "read-only email search/read receipt",
        ],
        "freshness_requirement": "current relevant email evidence only",
        "privacy_boundary": {
            "private_email_body_external_send_allowed": False,
            "scope_limited_search_required": True,
            "receipt_required": True,
            "no_private_data_external_model": True,
        },
        "can_request_access": False,
        "safe_fallback_available": True,
        "safe_fallback_kind": "draft_only_followup_or_checklist",
        "created_at": generated_at,
        "run_mode_context": run_context,
        "test_artifact_marker": str(run_context.get("test_marker") or ""),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    gap["unsafe_true_grants"] = unsafe_true_grants(gap)
    return gap


def authority_request_id(capability_id: str, gap_id: str, scope: Mapping[str, Any]) -> str:
    return f"operator_authority_request:{_short_hash(capability_id, gap_id, scope)}"


def build_authority_request(
    gap: Mapping[str, Any],
    *,
    requested_scope: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    scope = dict(requested_scope or {})
    if not scope:
        scope = dict(gap.get("requested_scope") or {})
    if not scope:
        lane = str(gap.get("requested_for_lane") or "")
        world, _, thread = lane.partition("/")
        scope = scope_from_context(world, thread, str(gap.get("requested_for_project") or ""))
    request = {
        "schema_version": AUTHORITY_REQUEST_SCHEMA,
        "request_id": authority_request_id(str(gap.get("capability_id") or ""), str(gap.get("gap_id") or ""), scope),
        "requested_capability_id": str(gap.get("capability_id") or ""),
        "requested_scope": scope,
        "requested_actions": list(gap.get("allowed_if_granted") or []),
        "denied_actions": list(gap.get("prohibited_always") or PROHIBITED_EMAIL_ACTIONS),
        "duration_scope": "session_or_until_revoked",
        "human_summary": "Grant read-only email lookup for this lane only.",
        "risk_summary": "This allows scoped search/read of relevant email evidence only. It does not allow sending, deleting, archiving, mark-read, browser/Gmail UI, ledger, paid, Coupa, workbook, PDF, push, or merge actions.",
        "requires_explicit_operator_grant": True,
        "generated_from_gap_id": str(gap.get("gap_id") or ""),
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    request["unsafe_true_grants"] = unsafe_true_grants(request)
    return request


def _ensure_authority_state_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS proof_to_response_receipts (
            receipt_id text primary key,
            created_at text not null,
            scenario_id text not null,
            proof_bundle_id text not null,
            response_id text not null,
            verification_status text not null,
            fallback_reason text not null,
            response_content_hash text not null,
            receipt_json text not null
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_authority_requests (
          request_id TEXT PRIMARY KEY,
          capability_id TEXT NOT NULL,
          target_world_ref TEXT NOT NULL,
          target_thread_ref TEXT NOT NULL,
          status TEXT NOT NULL,
          source_request_ref TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          request_json TEXT NOT NULL,
          gap_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_authority_grants (
          grant_id TEXT PRIMARY KEY,
          request_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          target_world_ref TEXT NOT NULL,
          target_thread_ref TEXT NOT NULL,
          created_at TEXT NOT NULL,
          grant_json TEXT NOT NULL
        )
        """
    )


def persist_active_authority_request(
    sqlite_path: Path,
    *,
    authority_request: Mapping[str, Any],
    capability_gap: Mapping[str, Any],
    source_request_ref: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request_id = str(authority_request.get("request_id") or "")
    scope = authority_request.get("requested_scope") if isinstance(authority_request.get("requested_scope"), Mapping) else {}
    world = str(scope.get("target_world_ref") or "")
    thread = str(scope.get("target_thread_ref") or "")
    capability_id = str(authority_request.get("requested_capability_id") or "")
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_authority_state_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO active_authority_requests
              (request_id, capability_id, target_world_ref, target_thread_ref, status, source_request_ref,
               created_at, updated_at, request_json, gap_json)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                capability_id,
                world,
                thread,
                source_request_ref,
                generated_at,
                generated_at,
                stable_json(authority_request),
                stable_json(capability_gap),
            ),
        )
    return {
        "receipt_type": "ACTIVE_AUTHORITY_REQUEST_STORED",
        "request_id": request_id,
        "capability_id": capability_id,
        "target_world_ref": world,
        "target_thread_ref": thread,
        "status": "pending",
        "sqlite_path": sqlite_path.as_posix(),
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def load_active_authority_request(
    sqlite_path: Path,
    *,
    capability_id: str = READ_ONLY_EMAIL_LOOKUP,
    world_ref: str = "",
    thread_ref: str = "",
) -> dict[str, Any] | None:
    sqlite_path = _rooted(sqlite_path)
    if not sqlite_path.exists():
        return None
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_authority_state_tables(conn)
        row = conn.execute(
            """
            SELECT request_json
            FROM active_authority_requests
            WHERE status = 'pending'
              AND (? = '' OR capability_id = ?)
              AND (? = '' OR target_world_ref = ?)
              AND (? = '' OR target_thread_ref = ?)
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (capability_id, capability_id, world_ref, world_ref, thread_ref, thread_ref),
        ).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(str(row[0]))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def persist_authority_grant(
    sqlite_path: Path,
    *,
    authority_grant: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if authority_grant.get("schema_version") != AUTHORITY_GRANT_SCHEMA or authority_grant.get("authority_grant_created") is not True:
        return {
            "receipt_type": "AUTHORITY_GRANT_NOT_STORED",
            "stored": False,
            "reason": "not a created authority grant",
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    scope = authority_grant.get("granted_scope") if isinstance(authority_grant.get("granted_scope"), Mapping) else {}
    request_id = str(authority_grant.get("request_id") or "")
    grant_id = str(authority_grant.get("grant_id") or "")
    capability_id = str(authority_grant.get("granted_capability_id") or "")
    world = str(scope.get("target_world_ref") or "")
    thread = str(scope.get("target_thread_ref") or "")
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_authority_state_tables(conn)
        conn.execute(
            "UPDATE active_authority_requests SET status = 'granted', updated_at = ? WHERE request_id = ?",
            (generated_at, request_id),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO operator_authority_grants
              (grant_id, request_id, capability_id, target_world_ref, target_thread_ref, created_at, grant_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (grant_id, request_id, capability_id, world, thread, generated_at, stable_json(authority_grant)),
        )
    return {
        "receipt_type": "OPERATOR_AUTHORITY_GRANT_STORED",
        "stored": True,
        "grant_id": grant_id,
        "request_id": request_id,
        "capability_id": capability_id,
        "target_world_ref": world,
        "target_thread_ref": thread,
        "sqlite_path": sqlite_path.as_posix(),
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def classify_authority_grant_intent(text: str) -> dict[str, Any]:
    lowered = str(text or "").lower()
    is_grant = any(phrase in lowered for phrase in GRANT_INTENT_PHRASES)
    is_build = any(phrase in lowered for phrase in BUILD_AUTHORITY_INTENT_PHRASES) or "build" in lowered or "wire" in lowered or "add connector" in lowered
    is_data_access = "email" in lowered or "access" in lowered or "that" in lowered or "this" in lowered
    return {
        "is_authority_grant_intent": is_grant,
        "requests_build_authority": is_build,
        "requests_data_access_authority": is_data_access and not is_build,
    }


def classify_build_authority_request_intent(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(phrase in lowered for phrase in BUILD_AUTHORITY_INTENT_PHRASES) or (
        ("build" in lowered or "implement" in lowered) and any(term in lowered for term in ("capability", "that", "email lookup", "read-only email"))
    )


def _is_active_authority_request(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("schema_version") == AUTHORITY_REQUEST_SCHEMA and bool(value.get("request_id"))


def compile_authority_grant(
    operator_confirmation_text: str,
    *,
    active_authority_request: Mapping[str, Any] | None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    intent = classify_authority_grant_intent(operator_confirmation_text)
    if not intent["is_authority_grant_intent"]:
        return {
            "schema_version": AUTHORITY_GRANT_SCHEMA,
            "grant_status": "NOT_GRANT_INTENT",
            "authority_grant_created": False,
            "reason": "operator text did not match authority grant intent",
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    if not _is_active_authority_request(active_authority_request):
        return {
            "schema_version": AUTHORITY_GRANT_SCHEMA,
            "grant_status": "NEEDS_ACTIVE_AUTHORITY_REQUEST",
            "authority_grant_created": False,
            "reason": "no active authority request was supplied",
            "operator_confirmation_text": operator_confirmation_text,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }

    request = dict(active_authority_request or {})
    grant = {
        "schema_version": AUTHORITY_GRANT_SCHEMA,
        "grant_id": f"operator_authority_grant:{_short_hash(request.get('request_id'), operator_confirmation_text, generated_at)}",
        "request_id": str(request.get("request_id") or ""),
        "granted_capability_id": str(request.get("requested_capability_id") or ""),
        "granted_scope": dict(request.get("requested_scope") or {}),
        "granted_actions": list(request.get("requested_actions") or []),
        "denied_actions": list(request.get("denied_actions") or []),
        "expiration_scope": str(request.get("duration_scope") or "session_or_until_revoked"),
        "operator_confirmation_text": operator_confirmation_text,
        "created_at": generated_at,
        "receipt_ref": f"receipt:{_short_hash(request.get('request_id'), 'authority_grant', generated_at)}",
        "verifier_status": "VERIFIER_READABLE_SCOPED_GRANT",
        "authority_grant_created": True,
        "raw_authority_granted_trusted": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    grant["unsafe_true_grants"] = unsafe_true_grants(grant)
    return grant


def build_capability_build_request(
    *,
    capability_id: str,
    build_authority_grant: Mapping[str, Any] | None,
    target_component: str = "operator_email_lookup_adapter",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if not (
        isinstance(build_authority_grant, Mapping)
        and build_authority_grant.get("schema_version") == AUTHORITY_GRANT_SCHEMA
        and build_authority_grant.get("authority_grant_created") is True
        and "write_local_adapter_code" in build_authority_grant.get("granted_actions", [])
    ):
        return {
            "schema_version": CAPABILITY_BUILD_REQUEST_SCHEMA,
            "build_request_status": "BUILD_AUTHORITY_REQUIRED",
            "build_request_created": False,
            "capability_id": capability_id,
            "reason": "build permission is separate from data-access permission",
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    request = {
        "schema_version": CAPABILITY_BUILD_REQUEST_SCHEMA,
        "build_request_id": f"capability_build_request:{_short_hash(capability_id, build_authority_grant.get('grant_id'), target_component)}",
        "capability_id": capability_id,
        "authority_grant_id": str(build_authority_grant.get("grant_id") or ""),
        "target_repo_component": target_component,
        "allowed_build_actions": list(BUILD_ACTIONS),
        "denied_build_actions": list(PROHIBITED_EMAIL_ACTIONS),
        "validation_required": ["focused_tests", "py_compile", "unsafe_true_grant_scan", "no_live_provider_smoke"],
        "unsafe_scan_required": True,
        "human_summary": "Build or wire the missing read-only email lookup capability without using it on private data yet.",
        "rollback_disable_expectation": "Capability can remain disabled unless activation receipt and data-access authority are both present.",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "build_request_created": True,
    }
    request["unsafe_true_grants"] = unsafe_true_grants(request)
    return request


def build_capability_build_authority_request(
    *,
    capability_id: str,
    requested_by_context: Mapping[str, Any],
    prior_capability_gap: Mapping[str, Any] | None = None,
    sqlite_path: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    spec = CAPABILITY_SPECS.get(capability_id, CAPABILITY_SPECS[READ_ONLY_EMAIL_LOOKUP])
    scope = dict(requested_by_context)
    resolution = capability_registry_build_provenance.resolve_capability(
        capability_id,
        requested_intent=str(scope.get("operator_text") or spec["label"]),
        lane_context=scope,
        sqlite_path=sqlite_path or capability_registry_build_provenance.DEFAULT_SQLITE_PATH,
        persist=sqlite_path is not None,
        generated_at=generated_at,
    )
    selected_resolution = str(resolution.get("selected_resolution") or "")
    if selected_resolution == "mature_existing":
        build_goal = f"Mature existing first-class {spec['label']} capability in test/shadow mode behind authority gates."
        operator_resolution_message = (
            f"I found an existing {spec['label']} descriptor or fixture, but it is not mature enough for scoped live use. "
            "I can create a build request to mature that existing capability in test/shadow mode."
        )
    elif selected_resolution == "build_new":
        build_goal = f"Implement new first-class {spec['label']} test/shadow capability behind authority gates."
        operator_resolution_message = (
            f"I do not find an existing {spec['label']} capability. "
            "I can create a scoped build request for a new test/shadow capability."
        )
    elif selected_resolution == "conflict":
        build_goal = f"Resolve capability identity conflict before building {spec['label']}."
        operator_resolution_message = "I found overlapping capability records. Review and consolidate before creating a redundant build."
    elif selected_resolution == "blocked":
        build_goal = f"Resolve blocked {spec['label']} capability state before building."
        operator_resolution_message = "The capability is blocked or deprecated; resolve that state before building."
    else:
        build_goal = f"Reuse existing {spec['label']} capability only after request-specific authority checks."
        operator_resolution_message = f"{spec['label']} exists, but request-specific authority still controls whether it can be used."
    request = {
        "schema_version": CAPABILITY_BUILD_AUTHORITY_REQUEST_SCHEMA,
        "request_id": f"capability_build_authority_request:{_short_hash(capability_id, scope, generated_at)}",
        "capability_id": capability_id,
        "source_resolution_id": str(resolution.get("resolution_id") or ""),
        "selected_resolution": selected_resolution,
        "capability_resolution": resolution,
        "build_goal": build_goal,
        "requested_by_context": scope,
        "allowed_build_actions": [
            "inspect_repo_local_contracts",
            "edit_code_inside_declared_scope",
            "add_or_update_tests",
            "add_fixture_descriptors",
            "run_local_targeted_tests",
            "write_local_receipts_or_read_models",
        ],
        "denied_build_actions": list(
            dict.fromkeys(
                [
                    "live_gmail_access",
                    "open_gmail_ui",
                    "open_browser",
                    "send_email",
                    "delete_email",
                    "archive_email",
                    "mark_email_read",
                    "coupa_access",
                    "coupa_submit",
                    "mark_paid",
                    "mutate_ledger",
                    "mutate_workbook",
                    "export_pdf",
                    "run_excel",
                    "invoke_external_model",
                    "invoke_local_model",
                    "git_push",
                    "git_merge",
                    "production_enablement",
                    "store_secret_in_repo",
                ]
            )
        ),
        "allowed_paths_or_repo_scope": [
            "capability_authority_loop.py",
            "operator_conversation_router.py",
            "openclaw_plugin_contract.py",
            "tests/test_capability_gap_build_authority.py",
            "tests/test_openclaw_plugin_contract.py",
        ],
        "test_mode_required": True,
        "production_enablement_allowed": False,
        "live_data_access_allowed": False,
        "external_services_allowed": False,
        "required_tests": [
            "capability gap routing tests",
            "build-authority request tests",
            "raw authority text ignored test",
            "plugin contract validator tests",
        ],
        "required_receipts": [
            "git diff --check",
            "git diff --cached --check",
            "staged unsafe scan explanation",
        ],
        "required_review": "operator review of scoped build request before implementation or production enablement",
        "expiry": "single_use_this_capability_build_scope_only",
        "operator_confirmation_required": True,
        "prior_capability_gap_id": str((prior_capability_gap or {}).get("gap_id") or ""),
        "operator_message": (
            f"{operator_resolution_message} "
            "That allows code and test work only, not live Gmail access, sending, Coupa, paid marking, or ledger changes."
        ),
        "next_safe_step": "Review and approve the build request scope.",
        "raw_authority_granted_trusted": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "created_at": generated_at,
    }
    request["unsafe_true_grants"] = unsafe_true_grants(request)
    if sqlite_path is not None:
        capability_registry_build_provenance.persist_build_request(
            request,
            sqlite_path=sqlite_path,
            status="pending_review",
        )
    return request


def build_activation_receipt(
    *,
    capability_id: str,
    build_request_id: str,
    validation_result: str,
    activated: bool,
    authority_scope: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    receipt = {
        "schema_version": CAPABILITY_ACTIVATION_RECEIPT_SCHEMA,
        "capability_id": capability_id,
        "build_request_id": build_request_id,
        "validation_result": validation_result,
        "activated": bool(activated),
        "authority_scope": dict(authority_scope),
        "denied_actions_preserved": list(PROHIBITED_EMAIL_ACTIONS),
        "receipt_ref": f"capability_activation_receipt:{_short_hash(capability_id, build_request_id, generated_at)}",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    receipt["unsafe_true_grants"] = unsafe_true_grants(receipt)
    return receipt


def build_email_lookup_gap_response(
    operator_text: str,
    *,
    world_ref: str,
    thread_ref: str,
    project_ref: str = "",
    run_mode_context: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    force_read_only_email_lookup: bool = False,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    run_context = dict(run_mode_context or global_run_mode_context.default_run_mode_context(generated_at=generated_at))
    lane = f"{world_ref}/{thread_ref}".strip("/")
    capability_id = READ_ONLY_EMAIL_LOOKUP if force_read_only_email_lookup else detect_capability_intent(operator_text, world_ref=world_ref, thread_ref=thread_ref) or READ_ONLY_EMAIL_LOOKUP
    gap = build_capability_gap(
        capability_id=capability_id,
        reason=operator_text,
        requested_for_lane=lane,
        requested_for_project=project_ref,
        run_mode_context=run_context,
        generated_at=generated_at,
    )
    authority_request = build_authority_request(gap, generated_at=generated_at)
    dry_run_prefix = "Dry-run: " if run_context.get("run_mode") == global_run_mode_context.TEST_DRY_RUN else ""
    spec = CAPABILITY_SPECS.get(capability_id, CAPABILITY_SPECS[READ_ONLY_EMAIL_LOOKUP])
    build_path_note = (
        " Grant read-only email lookup only through a scoped build/live authority path."
        if capability_id == READ_ONLY_EMAIL_LOOKUP
        else ""
    )
    return {
        "response_status": "CAPABILITY_GAP_AUTHORITY_REQUEST_READY",
        "capability_gap": gap,
        "operator_authority_request": authority_request,
        "operator_display": {
            "speaker_ref": "guardian",
            "voice_profile_ref": "agent_voice_profile:guardian",
            "voice_mode": "safety",
            "headline": f"{dry_run_prefix}{spec['label']} bounded",
            "plain_summary": f"{dry_run_prefix}{gap['operator_message']}{build_path_note}",
            "next_safe_action": gap["next_safe_step"],
            "proof_refs_collapsed": True,
        },
        "safe_fallback": {
            "fallback_kind": "draft_only_followup_or_checklist",
            "can_prepare_draft": capability_id in {READ_ONLY_EMAIL_LOOKUP, FOLLOW_UP_DRAFT_GENERATOR},
            "can_send": False,
            "can_claim_email_checked": False,
        },
        "workflow_package_request_v0_emitted": False,
        "raw_authority_granted_trusted": False,
        "run_mode_context": run_context,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "created_at": generated_at,
        "operator_text_hash": f"sha256:{hashlib.sha256(operator_text.encode('utf-8')).hexdigest()}",
    }


def unsupported_email_lookup_claims(response: Mapping[str, Any]) -> list[str]:
    text = " ".join(
        str(response.get(key) or "")
        for key in ("headline", "body", "next_step", "draft_headline", "draft_body", "draft_next_step")
    ).lower()
    claim_phrases = {
        "email_checked": ("checked email", "checked gmail", "looked in gmail", "searched your inbox"),
        "email_received": ("email was received", "received an email", "annette replied", "glenn acknowledged"),
        "draft_sent": ("draft sent", "draft was sent", "i sent", "sent the follow-up"),
        "contact_saved": ("contact saved", "saved the contact", "the contact was saved"),
        "paid_marked": ("marked paid", "paid was marked", "is paid", "has been paid"),
        "ledger_updated": ("ledger updated", "ledger was updated", "updated the ledger", "posted to ledger"),
    }
    negatives = ("cannot", "can't", "not", "no ", "did not", "do not", "stays untouched", "remains untouched")
    failures: list[str] = []
    for claim, phrases in claim_phrases.items():
        if any(phrase in text for phrase in phrases) and not any(negative in text for negative in negatives):
            failures.append(claim)
    return sorted(set(failures))


def build_contract_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    samples = [
        build_email_lookup_gap_response(
            "Have we received any emails from Annette? If not, make a follow-up email for tomorrow.",
            world_ref="finance",
            thread_ref="capital_hilton",
            generated_at=generated_at,
        ),
        build_email_lookup_gap_response(
            "Can you check my email and see the new accountant's name, email, and role?",
            world_ref="finance",
            thread_ref="live_arts_md",
            generated_at=generated_at,
        ),
        build_email_lookup_gap_response(
            "Did Glenn acknowledge the invoice or payment timing?",
            world_ref="finance",
            thread_ref="st_annes",
            generated_at=generated_at,
        ),
    ]
    grant = compile_authority_grant(
        "OK, I grant you access to do that.",
        active_authority_request=samples[0]["operator_authority_request"],
        generated_at=generated_at,
    )
    build_without_authority = build_capability_build_request(
        capability_id=READ_ONLY_EMAIL_LOOKUP,
        build_authority_grant=grant,
        generated_at=generated_at,
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contracts": [
            CAPABILITY_GAP_SCHEMA,
            AUTHORITY_REQUEST_SCHEMA,
            AUTHORITY_GRANT_SCHEMA,
            CAPABILITY_BUILD_REQUEST_SCHEMA,
            CAPABILITY_ACTIVATION_RECEIPT_SCHEMA,
        ],
        "vertical_slice": READ_ONLY_EMAIL_LOOKUP,
        "sample_gap_responses": samples,
        "sample_authority_grant": grant,
        "sample_build_without_build_authority": build_without_authority,
        "rules": [
            "Capability gaps are reusable objects, not lane-specific fallback copy.",
            "Incoming raw authority_granted fields are never trusted.",
            "Natural-language grants only compile against an active authority request.",
            "Active authority requests persist in SQLite so the next controller turn can resolve scoped grants after service restart.",
            "Capability-authority routes stay primary and do not receive generic payment-watch proof-to-response overlays.",
            "Build permission and data-access permission are separate.",
            "Read-only email lookup does not allow sending, deleting, archiving, mark-read, browser/Gmail UI, ledger, paid, Coupa, workbook, PDF, push, or merge actions.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    payload["unsafe_true_grants"] = unsafe_true_grants(payload)
    if payload["unsafe_true_grants"]:
        payload["status"] = NOT_READY_STATUS
    return payload


def _write_sqlite(sqlite_path: Path, payload: Mapping[str, Any]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        _ensure_authority_state_tables(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capability_authority_loop (
              read_model_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              generated_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO capability_authority_loop VALUES (?, ?, ?, ?)",
            (
                str(payload.get("read_model_id") or READ_MODEL_ID),
                str(payload.get("status") or ""),
                str(payload.get("generated_at") or ""),
                stable_json(payload),
            ),
        )


def build_wiki(payload: Mapping[str, Any]) -> str:
    lines = [
        "# First Class Capability Authority Loop",
        "",
        f"Status: `{payload.get('status', NOT_READY_STATUS)}`",
        "",
        "Defines the reusable path from missing capability to scoped authority request, deterministic grant, build request, and activation receipt.",
        "",
        "## Contracts",
        "",
    ]
    for contract in payload.get("contracts", []):
        lines.append(f"- `{contract}`")
    lines.extend(
        [
            "",
            "## Read-Only Email Lookup Slice",
            "",
            "- Missing email evidence emits `CAPABILITY_GAP_V0`.",
            "- The gap emits `OPERATOR_AUTHORITY_REQUEST_V0` for scoped read-only email lookup.",
            "- Natural-language confirmation compiles `OPERATOR_AUTHORITY_GRANT_V0` only when an active request exists.",
            "- Active requests are stored in SQLite for the next controller turn.",
            "- Capability-authority route output remains the primary display; generic proof-to-response overlays do not replace it.",
            "- Build permission remains separate from data-access permission.",
            "- Denied actions preserve send/delete/archive/mark-read/browser/Gmail UI/Coupa/ledger/paid/workbook/PDF/push/merge blocks.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_first_class_capability_authority_loop(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    payload = build_contract_read_model(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, payload)
    _write_sqlite(sqlite_path, payload)

    bridge_path = ""
    if bridge_root is not None:
        bridge = _rooted(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        bridge_target = bridge / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_target)
        bridge_path = bridge_target.as_posix()

    wiki = _rooted(wiki_path)
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(build_wiki(payload), encoding="utf-8")

    return {
        "status": str(payload.get("status") or NOT_READY_STATUS),
        "read_model_path": read_model_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish first-class capability authority loop contract.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args(argv)
    result = export_first_class_capability_authority_loop(
        export_root=Path(args.export_root),
        bridge_root=Path(args.bridge_root) if args.bridge_root else None,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
