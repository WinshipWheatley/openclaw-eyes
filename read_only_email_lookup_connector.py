"""Read-only email lookup connector boundary V0.

This module defines the governed boundary for `read_only_email_lookup`. It
does not send email, open Gmail/browser UI, mutate email state, read credential
files, store secrets, mark paid, touch ledgers/workbooks/PDFs, push, merge, or
invoke models. Production lookup remains blocked until a scoped authority grant
and externally configured read-only credential exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Read Only Email Lookup Connector.md")

SCHEMA_VERSION = "read_only_email_lookup_connector_v0"
READ_MODEL_ID = "read_only_email_lookup_connector"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_CONNECTOR_READY"

CAPABILITY_ID = "read_only_email_lookup"

READ_ONLY_EMAIL_LOOKUP_REQUEST_SCHEMA = "READ_ONLY_EMAIL_LOOKUP_REQUEST_V0"
READ_ONLY_EMAIL_LOOKUP_RESULT_SCHEMA = "READ_ONLY_EMAIL_LOOKUP_RESULT_V0"
EMAIL_EVIDENCE_SUMMARY_SCHEMA = "EMAIL_EVIDENCE_SUMMARY_V0"
EMAIL_CONNECTOR_STATUS_SCHEMA = "EMAIL_CONNECTOR_STATUS_V0"
EMAIL_CONNECTOR_SETUP_REQUIREMENT_SCHEMA = "EMAIL_CONNECTOR_SETUP_REQUIREMENT_V0"
OBJECTIVE_BLOCKER_SCHEMA = "OBJECTIVE_BLOCKER_V0"

READ_ONLY_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
FORBIDDEN_GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://mail.google.com/",
)

READ_ONLY_EMAIL_ACTIONS = (
    "search_relevant_email_evidence",
    "read_relevant_email_evidence",
    "summarize_relevant_email_evidence_with_receipt",
)

DENIED_ACTIONS = (
    "send_email",
    "compose_email",
    "create_email_draft",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "mark_email_unread",
    "modify_email_labels",
    "open_gmail_ui",
    "open_browser",
    "scrape_browser_session",
    "coupa_submit",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "git_push",
    "git_merge",
    "spawn_worker",
    "invoke_external_model",
    "lm2_tool_expansion",
    "store_secret_in_repo",
)

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "email_compose_allowed": False,
    "email_delete_allowed": False,
    "email_archive_allowed": False,
    "email_mark_read_allowed": False,
    "email_label_mutation_allowed": False,
    "gmail_allowed": False,
    "gmail_ui_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "worker_spawn_allowed": False,
    "external_model_allowed": False,
    "lm2_tool_expansion_allowed": False,
    "authority_granted_from_raw_text_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "authority_granted",
    "incoming_authority_granted_accepted",
    "raw_authority_granted_trusted",
    "email_checked",
    "email_received",
    "annette_replied",
    "accountant_identified",
    "glenn_acknowledged",
    "draft_sent",
    "contact_saved",
    "ledger_updated",
    "paid_marked",
    "workflow_package_request_v0_emitted",
}

CREDENTIAL_ENV_VARS = (
    "OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH",
    "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_CREDENTIAL_FILE",
    "OPENCLAW_READ_ONLY_GMAIL_CREDENTIAL_FILE",
    "OPENCLAW_READONLY_GMAIL_CREDENTIAL_FILE",
)
TOKEN_ENV_VARS = (
    "OPENCLAW_GMAIL_READONLY_TOKEN_PATH",
    "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_TOKEN_FILE",
    "OPENCLAW_READ_ONLY_GMAIL_TOKEN_FILE",
)
SETUP_STATUS_ENV_VAR = "OPENCLAW_GMAIL_READONLY_SETUP_STATUS"
GRANTED_SCOPES_STATUS_ENV_VAR = "OPENCLAW_GMAIL_READONLY_GRANTED_SCOPES_STATUS"
KEYCHAIN_REF_ENV_VAR = "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_KEYCHAIN_REF"
OPERATOR_CONFIG_ENV_VAR = "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_CONFIG_PATH"
BROKER_WRAPPER_ENV_VAR = "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_BROKER_WRAPPER_PATH"
BROKER_RUNTIME_DIR_ENV_VAR = "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_BROKER_RUNTIME_DIR"
DEFAULT_BROKER_WRAPPER_PATH = ROOT / "google_broker_readonly_wrapper.py"
DEFAULT_BROKER_RUNTIME_DIR = Path("/home/openclaw_external/openclaw-runtime")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if isinstance(part, (dict, list, tuple)):
            value = json.dumps(part, sort_keys=True, ensure_ascii=True)
        else:
            value = str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _repo_root() -> Path:
    try:
        return ROOT.resolve()
    except OSError:
        return ROOT


def _path_outside_repo(path_value: str) -> bool:
    if not path_value:
        return False
    try:
        resolved = Path(path_value).expanduser().resolve(strict=False)
        return not resolved.is_relative_to(_repo_root())
    except (OSError, RuntimeError, ValueError):
        return False


def _path_exists_without_read(path_value: str) -> bool:
    if not path_value:
        return False
    try:
        return Path(path_value).expanduser().exists()
    except OSError:
        return False


def requested_gmail_scopes() -> list[str]:
    return [READ_ONLY_GMAIL_SCOPE]


def validate_requested_scopes(scopes: Sequence[str]) -> dict[str, Any]:
    requested = [str(scope) for scope in scopes]
    forbidden = sorted(scope for scope in requested if scope in FORBIDDEN_GMAIL_SCOPES)
    missing = [] if requested == [READ_ONLY_GMAIL_SCOPE] else [READ_ONLY_GMAIL_SCOPE]
    return {
        "valid": not forbidden and requested == [READ_ONLY_GMAIL_SCOPE],
        "requested_scopes": requested,
        "required_scope": READ_ONLY_GMAIL_SCOPE,
        "forbidden_scopes": forbidden,
        "missing_required_scopes": missing,
    }


def _safe_read_code_file(path: Path) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def discover_existing_gmail_broker_candidate(
    *,
    env: Mapping[str, str] | None = None,
    wrapper_path: str | Path | None = None,
    runtime_dir: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Classify the existing local Google broker without reading credentials.

    The legacy broker is only a candidate source. This function reads source
    code and policy files, never token/credential files, and fails closed when
    broader scopes or repo-local credential paths are detected.
    """
    generated_at = generated_at or utc_now()
    env_map = dict(os.environ if env is None else env)
    wrapper = Path(
        wrapper_path
        or env_map.get(BROKER_WRAPPER_ENV_VAR)
        or DEFAULT_BROKER_WRAPPER_PATH
    )
    runtime = Path(
        runtime_dir
        or env_map.get(BROKER_RUNTIME_DIR_ENV_VAR)
        or DEFAULT_BROKER_RUNTIME_DIR
    )
    if not wrapper.is_absolute():
        wrapper = ROOT / wrapper
    broker = runtime / "google_access_broker.py"
    policy = runtime / "google_access_policy.py"

    wrapper_source = _safe_read_code_file(wrapper)
    broker_source = _safe_read_code_file(broker)
    policy_source = _safe_read_code_file(policy)
    local_broker_source = _safe_read_code_file(ROOT / "google_access_broker.py")
    combined = "\n".join((wrapper_source, broker_source, policy_source, local_broker_source))

    found = bool(wrapper_source or broker_source or policy_source or local_broker_source)
    supported_metadata = "google.gmail.read.metadata" in combined
    fixture_readback_available = all(
        token in wrapper_source
        for token in ("GOOGLE_READ_ONLY_FIXTURE", "gmail_metadata", "_fixture_broker_result")
    )
    wrapper_blocks_write = all(
        token in wrapper_source
        for token in ("BLOCKED_WRITE_CAPABILITY", "BLOCKED_BODY_READ", "Gmail send is blocked")
    )
    denied_scope_refs = sorted(scope for scope in FORBIDDEN_GMAIL_SCOPES if scope in combined)
    credential_paths_inside_repo = sorted(
        path
        for path in (
            "/home/openclaw/.google-secrets/credentials.json",
            "/home/openclaw/.google-secrets/token.json",
            "/home/openclaw/.google-secrets",
        )
        if path in combined
    )
    send_or_mutation_refs = sorted(
        ref
        for ref in (
            "_exec_gmail_send",
            "_exec_gmail_draft_create",
            "_exec_calendar_delete",
            "service.users().messages().send",
            "service.users().drafts().create",
        )
        if ref in combined
    )

    safe_direct = (
        found
        and supported_metadata
        and wrapper_blocks_write
        and not denied_scope_refs
        and not credential_paths_inside_repo
        and not send_or_mutation_refs
    )
    if safe_direct:
        classification = "SAFE_READ_ONLY_BROKER"
    elif found and supported_metadata and wrapper_blocks_write:
        classification = "RESTRICTABLE_BROKER"
    elif found:
        classification = "UNSAFE_BROKER"
    else:
        classification = "GMAIL_BROKER_NOT_FOUND"

    live_bridge_allowed = classification == "SAFE_READ_ONLY_BROKER"
    return {
        "schema_version": "GMAIL_BROKER_CANDIDATE_V0",
        "candidate_id": "existing_google_broker_readonly_wrapper",
        "classification": classification,
        "candidate_path": str(wrapper),
        "runtime_dir": str(runtime),
        "broker_path": str(broker),
        "policy_path": str(policy),
        "runtime_language": "python" if found else "unknown",
        "invocation_method": "python wrapper fixture/readback; live subprocess bridge disabled unless safe direct checks pass",
        "allowed_scopes": [READ_ONLY_GMAIL_SCOPE],
        "denied_scope_refs_found": denied_scope_refs,
        "credential_paths_inside_repo": credential_paths_inside_repo,
        "send_or_mutation_refs_found": send_or_mutation_refs,
        "supported_metadata_read": supported_metadata,
        "fixture_readback_available": fixture_readback_available,
        "wrapper_blocks_write_and_body": wrapper_blocks_write,
        "safe_read_only_direct": safe_direct,
        "live_bridge_allowed": live_bridge_allowed,
        "usable_for_read_only_lookup": bool(found and supported_metadata),
        "integration_effort": "small_adapter_scope_restriction_required" if classification == "RESTRICTABLE_BROKER" else "none" if safe_direct else "not_recommended",
        "credential_file_read": False,
        "secret_material_loaded": False,
        "external_call_performed": False,
        "created_at": generated_at,
        "notes": [
            "Source code was inspected; credential/token contents were not read.",
            "Production live bridge is disabled while denied scopes, send/draft executors, or repo-local credential paths are present.",
            "Fixture mode may be used for test evidence only and never proves production email facts.",
        ],
    }


def get_connector_status(
    *,
    env: Mapping[str, str] | None = None,
    operator_config_path: str = "",
    include_broker_discovery: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    env_map = dict(os.environ if env is None else env)
    credential_source = "none"
    configured = False
    missing_setup: list[str] = []

    keychain_ref = str(env_map.get(KEYCHAIN_REF_ENV_VAR) or "").strip()
    if keychain_ref:
        configured = True
        credential_source = "os_keychain"

    if not configured:
        for name in CREDENTIAL_ENV_VARS:
            path_value = str(env_map.get(name) or "").strip()
            if not path_value:
                continue
            if not _path_outside_repo(path_value):
                missing_setup.append("Credential path must be outside the OpenClaw repo.")
                continue
            if _path_exists_without_read(path_value):
                configured = True
                credential_source = "env_private_path"
                break
            missing_setup.append("Credential env var points to a missing private file.")

    config_path = operator_config_path or str(env_map.get(OPERATOR_CONFIG_ENV_VAR) or "").strip()
    if not configured and config_path:
        if _path_outside_repo(config_path) and _path_exists_without_read(config_path):
            configured = True
            credential_source = "operator_config_path"
        elif not _path_outside_repo(config_path):
            missing_setup.append("Operator config path must be outside the OpenClaw repo.")
        else:
            missing_setup.append("Operator config path does not exist.")

    if not configured:
        missing_setup.extend(
            [
                "Configure an OS keychain reference or private credential file outside the repo.",
                "Grant only https://www.googleapis.com/auth/gmail.readonly.",
                "Do not place client secrets, access tokens, or refresh tokens in the repo.",
            ]
        )

    setup_status = str(env_map.get(SETUP_STATUS_ENV_VAR) or "").strip()
    granted_scopes_status = str(env_map.get(GRANTED_SCOPES_STATUS_ENV_VAR) or "").strip()
    if not setup_status:
        setup_status = "credential_present_unvalidated" if configured else "human_setup_required"
    if not granted_scopes_status:
        granted_scopes_status = "unknown"
    validated_readonly = setup_status == "validated_readonly" and granted_scopes_status == "readonly_only"
    token_present = False
    for name in TOKEN_ENV_VARS:
        path_value = str(env_map.get(name) or "").strip()
        if path_value and _path_outside_repo(path_value) and _path_exists_without_read(path_value):
            token_present = True
            break

    status = {
        "schema_version": EMAIL_CONNECTOR_STATUS_SCHEMA,
        "connector_id": "email_connector:gmail_readonly_v0",
        "capability_id": CAPABILITY_ID,
        "configured": configured,
        "credential_source": credential_source,
        "setup_status": setup_status,
        "granted_scopes_status": granted_scopes_status,
        "validated_readonly": validated_readonly,
        "token_file_present": token_present,
        "scope_validation_required": not validated_readonly,
        "scopes": requested_gmail_scopes(),
        "denied_scopes": list(FORBIDDEN_GMAIL_SCOPES),
        "missing_setup": missing_setup,
        "denied_actions": list(DENIED_ACTIONS),
        "last_check_at": generated_at,
        "receipt_ref": f"email_connector_status_receipt:{_short_hash(configured, credential_source, generated_at)}",
        "secret_material_loaded": False,
        "credential_file_read": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    if include_broker_discovery:
        status["existing_broker_candidate"] = discover_existing_gmail_broker_candidate(
            env=env_map,
            generated_at=generated_at,
        )
    return status


def build_setup_requirement(status: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": EMAIL_CONNECTOR_SETUP_REQUIREMENT_SCHEMA,
        "requirement_id": f"email_connector_setup_requirement:{_short_hash(status.get('connector_id'), generated_at)}",
        "connector_id": str(status.get("connector_id") or "email_connector:gmail_readonly_v0"),
        "missing_items": list(status.get("missing_setup") or []),
        "human_setup_steps": [
            "Configure a read-only Gmail connector outside the repo using OS keychain, a private credential file path, or an operator-configured private path.",
            f"Use only {READ_ONLY_GMAIL_SCOPE}.",
            "Do not store client secrets, refresh tokens, access tokens, passwords, or API keys in the repo.",
            "Run the connector status check after setup; production lookup still needs scoped authority.",
        ],
        "no_repo_secret_policy": True,
        "required_scope": READ_ONLY_GMAIL_SCOPE,
        "denied_scopes": list(FORBIDDEN_GMAIL_SCOPES),
        "validation_command": "python3 -m pytest tests/test_read_only_email_lookup_connector.py -q",
        "receipt_ref": f"email_connector_setup_receipt:{_short_hash(status.get('connector_id'), generated_at)}",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _participant_hints(text: str) -> list[str]:
    lowered = text.lower()
    hints: list[str] = []
    for name in ("annette", "glenn", "capital hilton", "live arts", "st. anne", "st anne", "accountant"):
        if name in lowered:
            hints.append(name)
    return hints


def _search_terms(text: str) -> list[str]:
    terms = _participant_hints(text)
    lowered = text.lower()
    for token in ("payment", "paid", "invoice", "acknowledge", "acknowledged", "reply", "replied", "accountant"):
        if token in lowered and token not in terms:
            terms.append(token)
    return terms or ["email evidence"]


def build_lookup_request_from_operator_context(
    *,
    operator_text: str,
    world_ref: str,
    thread_ref: str,
    project_ref: str = "",
    run_mode_context: Mapping[str, Any] | None = None,
    authority_grant_ref: str = "",
    date_window: Mapping[str, Any] | None = None,
    max_results: int = 10,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    run_context = dict(run_mode_context or {"run_mode": "production", "test_run_id": "", "test_marker": ""})
    scope = {
        "target_world_ref": str(world_ref or ""),
        "target_thread_ref": str(thread_ref or ""),
        "target_project_ref": str(project_ref or ""),
    }
    return {
        "schema_version": READ_ONLY_EMAIL_LOOKUP_REQUEST_SCHEMA,
        "request_id": f"read_only_email_lookup_request:{_short_hash(operator_text, scope, generated_at)}",
        "lane": scope,
        "project_client": project_ref,
        "query_text": str(operator_text or ""),
        "search_terms": _search_terms(str(operator_text or "")),
        "participant_hints": _participant_hints(str(operator_text or "")),
        "date_window": dict(date_window or {}),
        "max_results": max(1, min(int(max_results or 10), 25)),
        "run_mode": str(run_context.get("run_mode") or "production"),
        "run_mode_context": run_context,
        "authority_grant_ref": authority_grant_ref,
        "denied_actions": list(DENIED_ACTIONS),
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def validate_authority_for_lookup(request: Mapping[str, Any], authority_grant: Mapping[str, Any] | None) -> dict[str, Any]:
    run_mode = str(request.get("run_mode") or "production")
    if run_mode == "test_dry_run":
        return {"valid": True, "reason": "test_dry_run_no_real_email_access", "authority_required": False}
    if not isinstance(authority_grant, Mapping):
        return {"valid": False, "reason": "missing_scoped_read_only_email_authority", "authority_required": True}
    capability = str(authority_grant.get("granted_capability_id") or "")
    if not capability and CAPABILITY_ID in set(map(str, authority_grant.get("granted_capabilities") or [])):
        capability = CAPABILITY_ID
    actions = set(map(str, authority_grant.get("granted_actions") or authority_grant.get("granted_enablement_actions") or []))
    if capability != CAPABILITY_ID:
        return {"valid": False, "reason": "authority_wrong_capability", "authority_required": True}
    if not {"search_relevant_email_evidence", "read_relevant_email_evidence"} <= actions:
        return {"valid": False, "reason": "authority_missing_read_actions", "authority_required": True}
    return {"valid": True, "reason": "scoped_read_only_email_authority_present", "authority_required": True}


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:24]


def _redact_email(value: str) -> str:
    raw = str(value or "").strip()
    if "@" not in raw:
        return "redacted"
    local, domain = raw.split("@", 1)
    prefix = local[:1] if local else "x"
    return f"{prefix}***@{domain}"


def _summary_text(value: str, limit: int = 96) -> str:
    clean = " ".join(str(value or "").replace("\n", " ").split())
    lowered = clean.lower()
    if "private body" in lowered or "raw body" in lowered or "full body" in lowered:
        return "redacted email snippet summary"
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def summarize_email_evidence(
    message: Mapping[str, Any],
    *,
    matched_terms: Sequence[str],
    proof_scope: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    subject = _summary_text(str(message.get("subject") or ""))
    snippet = _summary_text(str(message.get("snippet") or ""))
    return {
        "schema_version": EMAIL_EVIDENCE_SUMMARY_SCHEMA,
        "evidence_id": f"email_evidence_summary:{_short_hash(message.get('message_id'), proof_scope, matched_terms)}",
        "message_id_hash": _hash_identifier(str(message.get("message_id") or "")),
        "thread_id_hash": _hash_identifier(str(message.get("thread_id") or "")) if message.get("thread_id") else "",
        "from_redacted": _redact_email(str(message.get("from") or "")),
        "to_redacted": _redact_email(str(message.get("to") or "")),
        "subject_redacted_or_summary": subject,
        "date": str(message.get("date") or ""),
        "matched_terms": [str(term) for term in matched_terms],
        "snippet_summary": snippet,
        "raw_body_available": False,
        "proof_scope": dict(proof_scope),
        "receipt_ref": f"email_evidence_receipt:{_short_hash(message.get('message_id'), generated_at)}",
        "created_at": generated_at,
    }


def redact_email_evidence(message: Mapping[str, Any], *, proof_scope: Mapping[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    return summarize_email_evidence(
        message,
        matched_terms=[],
        proof_scope=proof_scope,
        generated_at=generated_at,
    )


def _existing_broker_fixture_messages(
    candidate: Mapping[str, Any],
    *,
    generated_at: str,
) -> list[dict[str, Any]]:
    if not candidate.get("fixture_readback_available"):
        return []
    try:
        import google_broker_readonly_wrapper as wrapper

        payload = wrapper.build_from_fixture("gmail_metadata", generated_at=generated_at)
    except Exception:
        return []

    readback = payload.get("readback") if isinstance(payload, Mapping) else {}
    tokenized = readback.get("tokenized_results") if isinstance(readback, Mapping) else []
    messages: list[dict[str, Any]] = []
    for index, item in enumerate(tokenized or [], start=1):
        if not isinstance(item, Mapping):
            continue
        messages.append(
            {
                "message_id": str(item.get("result_ref") or f"broker_fixture_message_{index}"),
                "thread_id": str(item.get("tokenized_message_ref") or ""),
                "from": str(item.get("tokenized_display_name") or "redacted"),
                "to": "redacted",
                "subject": str(item.get("tokenized_subject") or "redacted broker fixture subject"),
                "date": "",
                "snippet": str(item.get("tokenized_snippet") or "redacted broker fixture snippet"),
                "body": "",
            }
        )
    return messages


def _add_broker_context(result: dict[str, Any], candidate: Mapping[str, Any] | None) -> dict[str, Any]:
    if candidate:
        result["existing_broker_candidate"] = dict(candidate)
        result["broker_live_bridge_allowed"] = bool(candidate.get("live_bridge_allowed"))
    return result


def produce_missing_credential_blocker(
    objective: Mapping[str, Any],
    connector_status: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": OBJECTIVE_BLOCKER_SCHEMA,
        "blocker_id": f"objective_blocker:{_short_hash(objective.get('objective_id'), 'missing_read_only_email_connector')}",
        "objective_id": str(objective.get("objective_id") or ""),
        "capability_id": CAPABILITY_ID,
        "blocker_kind": "missing_read_only_email_connector",
        "human_summary": "A governed read-only Gmail connector is required before OpenClaw can check email evidence.",
        "required_next_input": "Configure the read-only Gmail connector outside the repo with gmail.readonly scope; do not store secrets in the repo.",
        "can_be_solved_by_make_it_so": False,
        "requires_human_secret_or_external_login": True,
        "already_explained": False,
        "email_connector_status_ref": str(connector_status.get("receipt_ref") or ""),
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _base_lookup_result(request: Mapping[str, Any], *, status: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": READ_ONLY_EMAIL_LOOKUP_RESULT_SCHEMA,
        "request_id": str(request.get("request_id") or ""),
        "status": status,
        "result_count": 0,
        "evidence_summaries": [],
        "evidence_refs": [],
        "redaction_applied": True,
        "denied_actions_preserved": True,
        "created_at": generated_at,
        "receipt_ref": f"read_only_email_lookup_receipt:{_short_hash(request.get('request_id'), status, generated_at)}",
        "real_email_access_performed": False,
        "email_checked": False,
        "raw_body_available": False,
        "business_action_performed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def perform_read_only_lookup(
    request: Mapping[str, Any],
    *,
    connector_status: Mapping[str, Any] | None = None,
    authority_grant: Mapping[str, Any] | None = None,
    fixture_messages: Sequence[Mapping[str, Any]] | None = None,
    existing_broker_candidate: Mapping[str, Any] | None = None,
    use_existing_broker_fixture: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    status = dict(connector_status or get_connector_status(generated_at=generated_at))
    broker_candidate = existing_broker_candidate or status.get("existing_broker_candidate")
    run_mode = str(request.get("run_mode") or "production")
    proof_scope = request.get("lane") if isinstance(request.get("lane"), Mapping) else {}

    if run_mode == "test_dry_run":
        result = _base_lookup_result(request, status="LOOKUP_DRY_RUN", generated_at=generated_at)
        result["dry_run_query"] = {
            "search_terms": list(request.get("search_terms") or []),
            "participant_hints": list(request.get("participant_hints") or []),
            "max_results": int(request.get("max_results") or 10),
        }
        return _add_broker_context(result, broker_candidate)

    authority = validate_authority_for_lookup(request, authority_grant)
    if not authority["valid"]:
        result = _base_lookup_result(request, status="BLOCKED_BY_AUTHORITY", generated_at=generated_at)
        result["blocker_reason"] = authority["reason"]
        return _add_broker_context(result, broker_candidate)

    if run_mode == "test_live" and fixture_messages:
        summaries = [
            summarize_email_evidence(
                message,
                matched_terms=list(request.get("search_terms") or []),
                proof_scope=proof_scope,
                generated_at=generated_at,
            )
            for message in fixture_messages[: int(request.get("max_results") or 10)]
        ]
        result = _base_lookup_result(request, status="LOOKUP_TEST_FIXTURE_USED", generated_at=generated_at)
        result["result_count"] = len(summaries)
        result["evidence_summaries"] = summaries
        result["evidence_refs"] = [str(item["evidence_id"]) for item in summaries]
        result["test_fixture_used"] = True
        return _add_broker_context(result, broker_candidate)

    if run_mode == "test_live" and use_existing_broker_fixture:
        candidate = broker_candidate or discover_existing_gmail_broker_candidate(generated_at=generated_at)
        fixture_messages = _existing_broker_fixture_messages(candidate, generated_at=generated_at)
        if fixture_messages:
            summaries = [
                summarize_email_evidence(
                    message,
                    matched_terms=list(request.get("search_terms") or []),
                    proof_scope=proof_scope,
                    generated_at=generated_at,
                )
                for message in fixture_messages[: int(request.get("max_results") or 10)]
            ]
            result = _base_lookup_result(request, status="LOOKUP_TEST_FIXTURE_USED", generated_at=generated_at)
            result["result_count"] = len(summaries)
            result["evidence_summaries"] = summaries
            result["evidence_refs"] = [str(item["evidence_id"]) for item in summaries]
            result["test_fixture_used"] = True
            result["existing_broker_fixture_used"] = True
            return _add_broker_context(result, candidate)

    if not status.get("configured"):
        result = _base_lookup_result(request, status="CONNECTOR_MISSING_CREDENTIAL", generated_at=generated_at)
        result["connector_status"] = status
        result["setup_requirement"] = build_setup_requirement(status, generated_at=generated_at)
        return _add_broker_context(result, broker_candidate)

    if not (
        status.get("validated_readonly") is True
        and str(status.get("setup_status") or "") == "validated_readonly"
        and str(status.get("granted_scopes_status") or "") == "readonly_only"
    ):
        result = _base_lookup_result(request, status="CONNECTOR_SCOPE_UNVALIDATED", generated_at=generated_at)
        result["blocker_reason"] = "gmail_readonly_scope_not_validated"
        result["connector_status"] = status
        result["active_next_step"] = "Run Gmail readonly scope validator before lookup."
        return _add_broker_context(result, broker_candidate)

    result = _base_lookup_result(request, status="CONNECTOR_READY", generated_at=generated_at)
    result["connector_status"] = status
    result["connector_scope_validated"] = True
    result["lookup_transport_note"] = "Credential boundary is configured; live Gmail lookup remains separately validated before LOOKUP_COMPLETED is emitted."
    return _add_broker_context(result, broker_candidate)


def build_contract_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    status = get_connector_status(generated_at=generated_at, include_broker_discovery=True)
    setup = build_setup_requirement(status, generated_at=generated_at)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contracts": [
            READ_ONLY_EMAIL_LOOKUP_REQUEST_SCHEMA,
            READ_ONLY_EMAIL_LOOKUP_RESULT_SCHEMA,
            EMAIL_EVIDENCE_SUMMARY_SCHEMA,
            EMAIL_CONNECTOR_STATUS_SCHEMA,
            EMAIL_CONNECTOR_SETUP_REQUIREMENT_SCHEMA,
        ],
        "capability_id": CAPABILITY_ID,
        "connector_status": status,
        "existing_broker_candidate": status.get("existing_broker_candidate"),
        "setup_requirement": setup,
        "requested_scopes": requested_gmail_scopes(),
        "forbidden_scopes": list(FORBIDDEN_GMAIL_SCOPES),
        "denied_actions": list(DENIED_ACTIONS),
        "policy": [
            "Production lookup requires scoped read_only_email_lookup authority.",
            "Credentials must live outside the repo or in OS keychain references.",
            "Existing Google broker code is classified before use and live bridge remains disabled when denied scopes or repo-local credentials are detected.",
            "Dry run never accesses real email.",
            "Existing broker fixture mode may support test-only redacted evidence; it never proves production email facts.",
            "Evidence summaries are redacted and raw bodies are unavailable by default.",
            "This connector never sends, drafts, deletes, archives, marks read, opens Gmail UI/browser, or mutates business state.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "email_send_enabled": False,
            "email_mutation_enabled": False,
            "gmail_ui_open_enabled": False,
            "browser_open_enabled": False,
            "credential_file_read": False,
            "secret_material_loaded": False,
            "production_lookup_completed": False,
            "workflow_package_request_v0_emitted": False,
        },
    }


def build_wiki(payload: Mapping[str, Any]) -> str:
    candidate = payload.get("existing_broker_candidate") or {}
    candidate_lines: list[str] = []
    if isinstance(candidate, Mapping) and candidate:
        candidate_lines = [
            "## Existing Broker Candidate",
            f"- Classification: `{candidate.get('classification')}`",
            f"- Candidate: `{candidate.get('candidate_path')}`",
            f"- Live bridge allowed: `{candidate.get('live_bridge_allowed')}`",
            "- Fixture/readback mode may be used for test-only redacted evidence.",
            "- Production live bridge remains disabled until denied scopes and repo-local credential paths are removed.",
            "",
        ]
    return "\n".join(
        [
            "# Read Only Email Lookup Connector",
            "",
            f"Status: `{payload['status']}`",
            "",
            "Defines the governed boundary for `read_only_email_lookup`.",
            "",
            "## Current Behavior",
            "- Production lookup requires scoped authority and an external read-only credential setup.",
            "- Missing credentials become a structured setup requirement, not generic failure.",
            "- `test_dry_run` records the query shape without real email access.",
            "- `test_live` can use local fixture evidence but does not become production proof.",
            "- Evidence summaries are redacted and raw bodies are unavailable by default.",
            "",
            "## Required Scope",
            f"- `{READ_ONLY_GMAIL_SCOPE}`",
            "",
            "## Denied",
            "- Send, draft/compose, delete, archive, mark read/unread, label mutation, Gmail UI/browser, Coupa, paid, ledger, workbook/PDF, push/merge, model/tool expansion, and repo secrets.",
            "",
            *candidate_lines,
        ]
    )


def export_read_only_email_lookup_connector(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_contract_read_model(generated_at=generated_at)
    export_path = _rooted(export_root) / JSON_EXPORT_NAME
    bridge_path = Path(bridge_root) / JSON_EXPORT_NAME
    _write_json(export_path, payload)
    _write_json(bridge_path, payload)
    wiki = _rooted(wiki_path)
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(build_wiki(payload), encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export read-only email lookup connector contract")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-root", type=Path, default=DEFAULT_BRIDGE_ROOT)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args(argv)
    payload = export_read_only_email_lookup_connector(
        export_root=args.export_root,
        bridge_root=args.bridge_root,
        wiki_path=args.wiki_path,
    )
    print(stable_json({"status": payload["status"], "path": str(args.export_root / JSON_EXPORT_NAME)}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
