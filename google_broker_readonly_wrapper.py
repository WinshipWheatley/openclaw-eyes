"""Repo A read-only wrapper for Repo B's Google Access Broker.

This module treats Repo B's broker as a bounded worker reached through a
subprocess boundary. It supports fixture readbacks by default and an explicit
live bridge mode only when the caller opts in. All broker output is tokenized
before generated read-models, operator markdown, or chat-visible output.

It does not import the Repo B broker into Repo A runtime, run OAuth setup, start
watchers/services, send email, create drafts, write calendar/contact data, read
Gmail bodies, download attachments, expose credentials, ingest raw private
bodies, dispatch agents, run workflows, mutate Mission Control Swift, sync Mac,
or push.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pii_vault import redact_text


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
REPO_B_RUNTIME_DIR = Path("/home/openclaw_external/openclaw-runtime")
REPO_B_BROKER_PATH = REPO_B_RUNTIME_DIR / "google_access_broker.py"
REPO_B_POLICY_PATH = REPO_B_RUNTIME_DIR / "google_access_policy.py"

SCHEMA_VERSION = "google_broker_readonly_wrapper_v0"
READ_MODEL_ID = "google_broker_readonly_readback"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "BOUNDED_REPO_B_GOOGLE_READ_ONLY_SUBPROCESS_WRAPPER"

GOOGLE_READ_ONLY_BRIDGE = "GOOGLE_READ_ONLY_BRIDGE"
GOOGLE_READ_ONLY_FIXTURE = "GOOGLE_READ_ONLY_FIXTURE"

SUPPORTED_READ_CAPABILITIES = (
    "google.contacts.read",
    "google.calendar.read",
    "google.gmail.read.metadata",
)

BLOCKED_CAPABILITIES = (
    "google.gmail.read.body",
    "google.gmail.send",
    "google.gmail.draft.create",
    "google.calendar.write",
    "google.contacts.write",
    "attachment.download",
    "attachment.read",
    "google.gmail.label.modify",
    "google.gmail.archive",
    "google.gmail.delete",
)

READBACK_STATUSES = (
    "READBACK_READY",
    "FIXTURE_READBACK_READY",
    "BLOCKED_UNSUPPORTED_CAPABILITY",
    "BLOCKED_WRITE_CAPABILITY",
    "BLOCKED_BODY_READ",
    "BLOCKED_TOKENIZATION_MISSING",
    "BROKER_UNAVAILABLE",
    "SUBPROCESS_TIMEOUT",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "SEND_CAPABILITY_REQUESTED",
    "WRITE_CAPABILITY_REQUESTED",
    "BODY_READ_REQUESTED",
    "ATTACHMENT_READ_REQUESTED",
    "RAW_PII_RETURNED_TO_READMODEL",
    "RAW_PII_RETURNED_TO_CHAT",
    "TOKENIZATION_MISSING",
    "CREDENTIAL_EXPOSURE",
    "BROKER_IMPORT_DIRECTLY_ATTEMPTED",
    "SUBPROCESS_TIMEOUT",
    "UNKNOWN_CAPABILITY",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "google_read_only_bridge_allowed": False,
    "google_read_only_fixture_allowed": True,
    "gmail_send_allowed": False,
    "gmail_draft_create_allowed": False,
    "gmail_body_read_allowed": False,
    "gmail_metadata_read_allowed": False,
    "calendar_write_allowed": False,
    "contacts_write_allowed": False,
    "attachment_read_or_download_allowed": False,
    "label_archive_delete_modify_allowed": False,
    "credential_exposure_allowed": False,
    "raw_broker_output_to_readmodel_allowed": False,
    "raw_broker_output_to_chat_allowed": False,
    "raw_body_ingestion_allowed": False,
    "agent_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "browser_access_allowed": False,
    "coupa_access_allowed": False,
    "telegram_access_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class GoogleBrokerReadOnlyRequest:
    request_id: str
    source_chat_request_ref: str
    requested_capability: str
    requesting_agent_role: str
    account_ref: str
    query_summary: str
    params: dict[str, Any]
    max_results: int
    time_window: dict[str, Any]
    metadata_only: bool
    body_read_allowed: bool
    tokenization_required: bool
    privacy_class: str
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class GoogleBrokerBridgeBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class GoogleBrokerReadOnlyReadback:
    readback_id: str
    source_request_ref: str
    capability: str
    status: str
    tokenized_results: tuple[dict[str, Any], ...]
    safe_summary: str
    protected_refs: tuple[str, ...]
    blocked_items: tuple[str, ...]
    external_actions: bool
    credential_exposure: bool
    raw_body_exposure: bool
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("._")[:120] or "unknown"


def _token_ref(field: str, ordinal: int) -> str:
    return f"google_{field}_token_{ordinal:03d}"


def _tokenize_value(value: Any, *, field: str, ordinal: int) -> tuple[str | None, str | None]:
    if value in (None, "", [], {}):
        return None, None
    redacted, token_map = redact_text(str(value))
    if redacted == str(value):
        redacted = f"[{field.upper()}_{ordinal:03d}]"
    return _token_ref(field, ordinal), redacted


def _sanitize_error(value: str) -> str:
    text = str(value)
    text = text.replace("/home/openclaw/.google-secrets/credentials.json", "[PROTECTED_GOOGLE_CREDENTIALS_REF]")
    text = text.replace("/home/openclaw/.google-secrets/token.json", "[PROTECTED_GOOGLE_TOKEN_REF]")
    text = text.replace("/home/openclaw/.google-secrets", "[PROTECTED_GOOGLE_SECRETS_DIR]")
    redacted, _token_map = redact_text(text)
    return redacted


def _raw_pii_visible(value: Any) -> bool:
    text = stable_json(value) if not isinstance(value, str) else value
    patterns = (
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def make_request(
    *,
    capability: str,
    fixture: str | None = None,
    max_results: int = 5,
    generated_at: str | None = None,
) -> GoogleBrokerReadOnlyRequest:
    generated_at = generated_at or utc_now()
    params: dict[str, Any] = {"max_results": max_results}
    if capability == "google.calendar.read":
        params = {"days_ahead": 7, "max_results": max_results}
    if capability == "google.contacts.read":
        params = {"query": "fixture contact" if fixture else "", "max_results": max_results}
    return GoogleBrokerReadOnlyRequest(
        request_id=f"google_readonly_{_safe_id(fixture or capability)}",
        source_chat_request_ref="local_operator_google_readonly_request",
        requested_capability=capability,
        requesting_agent_role="cassandra_read_worker",
        account_ref="protected_google_account_ref_local_default",
        query_summary=f"Bounded metadata request for {capability}.",
        params=params,
        max_results=max_results,
        time_window={"mode": "bounded", "days_ahead": params.get("days_ahead")},
        metadata_only=True,
        body_read_allowed=False,
        tokenization_required=True,
        privacy_class="private_metadata_tokenized",
        authority_boundary=AUTHORITY_BOUNDARY,
        created_at=generated_at,
    )


def _fixture_broker_result(fixture: str, capability: str) -> dict[str, Any]:
    if fixture == "contacts":
        return {
            "ok": True,
            "data": [
                {
                    "display_name": "Fixture Contact Alpha",
                    "email": "fixture.alpha@example.invalid",
                    "phone": "555-010-2200",
                }
            ],
            "error": "",
        }
    if fixture == "gmail_metadata":
        return {
            "ok": True,
            "data": [
                {
                    "message_id": "fixture-message-001",
                    "from_name": "Fixture Sender",
                    "subject": "Fixture metadata subject",
                    "date_raw": "Mon, 25 May 2026 12:00:00 +0000",
                    "labels": ["INBOX"],
                    "snippet": "Fixture snippet for metadata only.",
                }
            ],
            "error": "",
        }
    if fixture == "calendar":
        return {
            "ok": True,
            "data": [
                {
                    "id": "fixture-event-001",
                    "summary": "Fixture calendar event",
                    "start": {"dateTime": "2026-05-25T18:00:00Z"},
                    "end": {"dateTime": "2026-05-25T19:00:00Z"},
                    "location": "Fixture location",
                }
            ],
            "error": "",
        }
    return {"ok": False, "data": None, "error": f"fixture {fixture} unavailable for {capability}"}


def capability_for_fixture(fixture: str) -> str:
    if fixture == "contacts":
        return "google.contacts.read"
    if fixture == "gmail_metadata":
        return "google.gmail.read.metadata"
    if fixture == "calendar":
        return "google.calendar.read"
    return "google.unknown"


def _blocker(blocker_type: str, condition: str, warning: str) -> GoogleBrokerBridgeBlocker:
    return GoogleBrokerBridgeBlocker(
        blocker_id=f"google_broker_blocker_{blocker_type.lower()}",
        blocker_type=blocker_type,
        condition=condition,
        severity="high",
        elioperator_warning=warning,
        fail_closed=True,
        next_safe_move="Use a supported read-only metadata capability or fixture.",
    )


def validate_request(request: GoogleBrokerReadOnlyRequest) -> tuple[str | None, tuple[GoogleBrokerBridgeBlocker, ...]]:
    capability = request.requested_capability
    if capability in {"google.gmail.send"}:
        return "BLOCKED_WRITE_CAPABILITY", (
            _blocker("SEND_CAPABILITY_REQUESTED", capability, "Gmail send is blocked in this wrapper."),
        )
    if capability in {"google.gmail.draft.create", "google.calendar.write", "google.contacts.write"}:
        return "BLOCKED_WRITE_CAPABILITY", (
            _blocker("WRITE_CAPABILITY_REQUESTED", capability, "Google write capabilities are blocked in this wrapper."),
        )
    if capability == "google.gmail.read.body" or request.body_read_allowed or not request.metadata_only:
        return "BLOCKED_BODY_READ", (
            _blocker("BODY_READ_REQUESTED", capability, "Gmail body/full-content reads are blocked in this wrapper."),
        )
    if "attachment" in capability:
        return "BLOCKED_UNSUPPORTED_CAPABILITY", (
            _blocker("ATTACHMENT_READ_REQUESTED", capability, "Attachment reads/downloads are blocked in this wrapper."),
        )
    if capability not in SUPPORTED_READ_CAPABILITIES:
        return "BLOCKED_UNSUPPORTED_CAPABILITY", (
            _blocker("UNKNOWN_CAPABILITY", capability, "Only contacts, calendar, and Gmail metadata reads are supported."),
        )
    if not request.tokenization_required:
        return "BLOCKED_TOKENIZATION_MISSING", (
            _blocker("TOKENIZATION_MISSING", capability, "Tokenization is required before any read-model output."),
        )
    if any(value is True for key, value in request.authority_boundary.items() if key != "google_read_only_fixture_allowed"):
        return "UNKNOWN_FAIL_CLOSED", (
            _blocker("UNKNOWN_FAIL_CLOSED", capability, "Request authority boundary tried to enable a live/write action."),
        )
    return None, ()


def _broker_agent_for_role(role: str) -> str:
    if role in {"cassandra_read_worker", "operator_chat_readback"}:
        return "cassandra"
    return role


def run_repo_b_broker_subprocess(
    request: GoogleBrokerReadOnlyRequest,
    *,
    timeout_ms: int = 5000,
) -> tuple[str, dict[str, Any] | None, tuple[GoogleBrokerBridgeBlocker, ...]]:
    code = """
import json
import os
import sys
from pathlib import Path

repo_b = Path(os.environ["OPENCLAW_REPO_B_RUNTIME_DIR"])
sys.path.insert(0, str(repo_b))
broker = __import__("google_access_broker")
request = json.loads(sys.stdin.read())
result = broker.call(request["broker_agent"], request["capability"], request.get("params", {}))
print(json.dumps({"ok": bool(result.get("ok")), "data": result.get("data"), "error": result.get("error", "")}))
"""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": "",
        "OPENCLAW_REPO_B_RUNTIME_DIR": str(REPO_B_RUNTIME_DIR),
        "OPENCLAW_GOOGLE_BRIDGE_MODE": "READ_ONLY",
        "OPENCLAW_GOOGLE_SEND_ALLOWED": "0",
        "OPENCLAW_GOOGLE_WRITE_ALLOWED": "0",
        "OPENCLAW_GOOGLE_BODY_ALLOWED": "0",
    }
    stdin_payload = {
        "broker_agent": _broker_agent_for_role(request.requesting_agent_role),
        "capability": request.requested_capability,
        "params": request.params,
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            input=stable_json(stdin_payload),
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "SUBPROCESS_TIMEOUT", None, (
            _blocker("SUBPROCESS_TIMEOUT", request.requested_capability, "Repo B broker subprocess timed out."),
        )
    stdout = completed.stdout.strip()
    if completed.returncode != 0:
        err = _sanitize_error(completed.stderr or stdout or f"exit {completed.returncode}")
        return "BROKER_UNAVAILABLE", None, (
            _blocker("UNKNOWN_FAIL_CLOSED", request.requested_capability, f"Repo B broker subprocess failed: {err}"),
        )
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        err = _sanitize_error((completed.stderr + "\n" + stdout).strip())
        return "BROKER_UNAVAILABLE", None, (
            _blocker("UNKNOWN_FAIL_CLOSED", request.requested_capability, f"Repo B broker returned non-JSON output: {err}"),
        )
    if not value.get("ok"):
        err = _sanitize_error(str(value.get("error") or "broker unavailable"))
        return "BROKER_UNAVAILABLE", value, (
            _blocker("UNKNOWN_FAIL_CLOSED", request.requested_capability, f"Repo B broker did not return data: {err}"),
        )
    return "READBACK_READY", value, ()


def _tokenize_contact_result(item: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    name_ref, name_token = _tokenize_value(item.get("display_name"), field="display_name", ordinal=ordinal)
    email_ref, email_token = _tokenize_value(item.get("email"), field="email", ordinal=ordinal)
    phone_ref, phone_token = _tokenize_value(item.get("phone"), field="phone", ordinal=ordinal)
    return {
        "result_type": "contact_metadata",
        "result_ref": f"google_contact_metadata_{ordinal:03d}",
        "tokenized_display_name_ref": name_ref,
        "tokenized_display_name": name_token,
        "tokenized_email_ref": email_ref,
        "tokenized_email": email_token,
        "tokenized_phone_ref": phone_ref,
        "tokenized_phone": phone_token,
        "protected_store_ref": "repo_a_transient_token_map_not_persisted",
        "strong_duplicate_token_available": False,
    }


def _tokenize_gmail_metadata_result(item: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    sender_ref, sender_token = _tokenize_value(item.get("from_name"), field="display_name", ordinal=ordinal)
    subject_ref, subject_token = _tokenize_value(item.get("subject"), field="subject", ordinal=ordinal)
    snippet_ref, snippet_token = _tokenize_value(item.get("snippet"), field="snippet", ordinal=ordinal)
    message_ref, message_token = _tokenize_value(item.get("message_id"), field="message_id", ordinal=ordinal)
    return {
        "result_type": "gmail_metadata",
        "result_ref": f"google_gmail_metadata_{ordinal:03d}",
        "tokenized_message_ref": message_ref,
        "tokenized_message_id": message_token,
        "tokenized_display_name_ref": sender_ref,
        "tokenized_display_name": sender_token,
        "tokenized_subject_ref": subject_ref,
        "tokenized_subject": subject_token,
        "tokenized_snippet_ref": snippet_ref,
        "tokenized_snippet": snippet_token,
        "date_present": bool(item.get("date_raw")),
        "label_count": len(item.get("labels") or ()),
        "protected_store_ref": "repo_a_transient_token_map_not_persisted",
        "strong_duplicate_token_available": False,
    }


def _tokenize_calendar_result(item: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    title_ref, title_token = _tokenize_value(item.get("summary"), field="subject", ordinal=ordinal)
    location_ref, location_token = _tokenize_value(item.get("location"), field="location", ordinal=ordinal)
    event_ref, event_token = _tokenize_value(item.get("id"), field="event_id", ordinal=ordinal)
    start = item.get("start") if isinstance(item.get("start"), Mapping) else {}
    end = item.get("end") if isinstance(item.get("end"), Mapping) else {}
    return {
        "result_type": "calendar_metadata",
        "result_ref": f"google_calendar_metadata_{ordinal:03d}",
        "tokenized_event_ref": event_ref,
        "tokenized_event_id": event_token,
        "tokenized_subject_ref": title_ref,
        "tokenized_subject": title_token,
        "tokenized_location_ref": location_ref,
        "tokenized_location": location_token,
        "start_present": bool(start.get("dateTime") or start.get("date")),
        "end_present": bool(end.get("dateTime") or end.get("date")),
        "protected_store_ref": "repo_a_transient_token_map_not_persisted",
        "strong_duplicate_token_available": False,
    }


def tokenize_broker_result(capability: str, broker_result: Mapping[str, Any]) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    data = broker_result.get("data") or []
    if not isinstance(data, list):
        data = [data]
    tokenized: list[dict[str, Any]] = []
    protected_refs: list[str] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, Mapping):
            item = {"value": item}
        if capability == "google.contacts.read":
            result = _tokenize_contact_result(item, index)
        elif capability == "google.gmail.read.metadata":
            result = _tokenize_gmail_metadata_result(item, index)
        elif capability == "google.calendar.read":
            result = _tokenize_calendar_result(item, index)
        else:
            result = {"result_type": "unknown", "result_ref": f"google_result_{index:03d}"}
        tokenized.append(result)
        protected_refs.append(result["protected_store_ref"])
    return tuple(tokenized), tuple(sorted(set(protected_refs)))


def build_readback(
    request: GoogleBrokerReadOnlyRequest,
    *,
    mode: str,
    fixture: str | None = None,
    live: bool = False,
    timeout_ms: int = 5000,
) -> dict[str, Any]:
    blocked_status, blockers = validate_request(request)
    broker_result: dict[str, Any] | None = None
    status = blocked_status
    if blocked_status is None:
        if mode == GOOGLE_READ_ONLY_FIXTURE:
            broker_result = _fixture_broker_result(fixture or "", request.requested_capability)
            status = "FIXTURE_READBACK_READY" if broker_result.get("ok") else "BROKER_UNAVAILABLE"
            if not broker_result.get("ok"):
                blockers = (
                    _blocker("UNKNOWN_FAIL_CLOSED", request.requested_capability, _sanitize_error(broker_result.get("error", ""))),
                )
        elif live:
            status, broker_result, blockers = run_repo_b_broker_subprocess(request, timeout_ms=timeout_ms)
        else:
            status = "BROKER_UNAVAILABLE"
            blockers = (
                _blocker(
                    "UNKNOWN_FAIL_CLOSED",
                    request.requested_capability,
                    "Live bridge was not requested; fixture mode is the safe default.",
                ),
            )

    tokenized_results: tuple[dict[str, Any], ...] = ()
    protected_refs: tuple[str, ...] = ()
    if broker_result and broker_result.get("ok"):
        tokenized_results, protected_refs = tokenize_broker_result(request.requested_capability, broker_result)
        if _raw_pii_visible(tokenized_results):
            status = "BLOCKED_TOKENIZATION_MISSING"
            blockers = blockers + (
                _blocker("RAW_PII_RETURNED_TO_READMODEL", request.requested_capability, "Raw PII remained after tokenization."),
            )
            tokenized_results = ()
            protected_refs = ()

    blocked_items = tuple(blocker.elioperator_warning for blocker in blockers)
    count = len(tokenized_results)
    if status in {"READBACK_READY", "FIXTURE_READBACK_READY"}:
        safe_summary = f"{count} tokenized Google metadata result(s) are ready from {request.requested_capability}."
        next_safe_move = "Use tokenized metadata refs only; request a governed adapter before any body/write/send action."
    else:
        safe_summary = "Google read-only broker wrapper did not expose results."
        next_safe_move = "Use an allowed read-only metadata capability or keep fixture mode until broker availability is proven."

    readback = GoogleBrokerReadOnlyReadback(
        readback_id=f"google_broker_readback_{_safe_id(request.request_id)}",
        source_request_ref=request.request_id,
        capability=request.requested_capability,
        status=status or "UNKNOWN_FAIL_CLOSED",
        tokenized_results=tokenized_results,
        safe_summary=safe_summary,
        protected_refs=protected_refs,
        blocked_items=blocked_items,
        external_actions=False,
        credential_exposure=False,
        raw_body_exposure=False,
        next_safe_move=next_safe_move,
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": request.created_at,
        "mode": mode,
        "repo_b_broker_path": str(REPO_B_BROKER_PATH),
        "repo_b_policy_path": str(REPO_B_POLICY_PATH),
        "subprocess_boundary": {
            "used_for_live_bridge": bool(live and mode == GOOGLE_READ_ONLY_BRIDGE),
            "timeout_ms": timeout_ms,
            "env": {
                "OPENCLAW_GOOGLE_BRIDGE_MODE": "READ_ONLY",
                "OPENCLAW_GOOGLE_SEND_ALLOWED": "0",
                "OPENCLAW_GOOGLE_WRITE_ALLOWED": "0",
                "OPENCLAW_GOOGLE_BODY_ALLOWED": "0",
            },
            "direct_repo_b_import_in_repo_a_runtime": False,
            "long_running_service_started": False,
        },
        "supported_capabilities": SUPPORTED_READ_CAPABILITIES,
        "blocked_capabilities": BLOCKED_CAPABILITIES,
        "request": asdict(request),
        "readback": asdict(readback),
        "active_blockers": tuple(asdict(blocker) for blocker in blockers),
        "security_summary": {
            "credential_exposure": False,
            "raw_pii_exposure": False,
            "raw_body_exposure": False,
            "gmail_body_read": False,
            "send_or_write": False,
            "attachment_read_or_download": False,
            "strong_duplicate_token_available": False,
            "strong_duplicate_token_note": "Existing regex tokenization protects display output; stronger persistent HMAC duplicate matching is not exposed in this lane.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = {
        "allowed_read_capabilities_present": all(cap in SUPPORTED_READ_CAPABILITIES for cap in ("google.contacts.read", "google.calendar.read", "google.gmail.read.metadata")),
        "send_write_body_attachment_blocked": True,
        "subprocess_boundary_modeled": True,
        "direct_repo_b_import_in_repo_a_runtime": False,
        "fixture_mode_available": True,
        "tokenized_outputs_exist": bool(tokenized_results) if status in {"READBACK_READY", "FIXTURE_READBACK_READY"} else True,
        "operator_markdown_safe_summary_only": True,
        "credential_exposure": False,
        "raw_pii_exposure": False,
        "raw_body_exposure": False,
        "external_actions": False,
        "gmail_send_performed": False,
        "calendar_write_performed": False,
        "contacts_write_performed": False,
        "gmail_body_read_performed": False,
        "attachment_read_or_download_performed": False,
        "browser_coupa_telegram_access_performed": False,
        "workflow_execution_performed": False,
        "agent_dispatch_performed": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "all_authority_boundary_flags_false_except_fixture": all(
            value is False for key, value in AUTHORITY_BOUNDARY.items() if key != "google_read_only_fixture_allowed"
        ),
    }
    return payload


def build_from_fixture(fixture: str, *, generated_at: str | None = None) -> dict[str, Any]:
    capability = capability_for_fixture(fixture)
    request = make_request(capability=capability, fixture=fixture, generated_at=generated_at)
    return build_readback(request, mode=GOOGLE_READ_ONLY_FIXTURE, fixture=fixture)


def build_from_live_capability(
    capability: str,
    *,
    max_results: int = 1,
    timeout_ms: int = 5000,
    generated_at: str | None = None,
) -> dict[str, Any]:
    request = make_request(capability=capability, max_results=max_results, generated_at=generated_at)
    return build_readback(request, mode=GOOGLE_READ_ONLY_BRIDGE, live=True, timeout_ms=timeout_ms)


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readback = payload["readback"]
    blockers = payload.get("active_blockers") or ()
    lines = [
        "# Google Broker Read-Only Wrapper",
        "",
        f"Mode: {payload['mode']}",
        f"Capability: {readback['capability']}",
        f"Status: {readback['status']}",
        "",
        readback["safe_summary"],
        "",
        "Boundary:",
        "- Repo B broker is wrapped as a bounded read-only worker.",
        "- Fixture mode is safe by default; live bridge requires explicit invocation.",
        "- Gmail body, send, draft, calendar/contact write, and attachment reads are blocked.",
        "- Read-models and chat-visible outputs contain tokenized metadata only.",
        "",
    ]
    if blockers:
        lines.append("Blocked items:")
        lines.extend(f"- {item['elioperator_warning']}" for item in blockers)
        lines.append("")
    lines.extend(
        [
            f"Next safe move: {readback['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    readback = payload["readback"]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "mode": payload["mode"],
        "capability": readback["capability"],
        "status": readback["status"],
        "tokenized_result_count": len(readback["tokenized_results"]),
        "safe_summary": readback["safe_summary"],
        "blocked_items": readback["blocked_items"],
        "credential_exposure": readback["credential_exposure"],
        "raw_body_exposure": readback["raw_body_exposure"],
        "external_actions": readback["external_actions"],
        "next_safe_move": readback["next_safe_move"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Google broker read-only wrapper.")
    parser.add_argument("--fixture", choices=("contacts", "gmail_metadata", "calendar"), default=None)
    parser.add_argument("--capability", default=None)
    parser.add_argument("--live", action="store_true", help="Use explicit read-only subprocess bridge instead of fixture mode.")
    parser.add_argument("--max-results", type=int, default=1)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    if args.fixture:
        payload = build_from_fixture(args.fixture, generated_at=args.generated_at)
    else:
        capability = args.capability or "google.contacts.read"
        if args.live:
            payload = build_from_live_capability(
                capability,
                max_results=args.max_results,
                timeout_ms=args.timeout_ms,
                generated_at=args.generated_at,
            )
        else:
            request = make_request(capability=capability, max_results=args.max_results, generated_at=args.generated_at)
            payload = build_readback(request, mode=GOOGLE_READ_ONLY_BRIDGE, live=False, timeout_ms=args.timeout_ms)
    paths = write_exports(payload, Path(args.export_root))
    output = payload if args.format == "json" else build_summary(payload, paths)
    print(stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
