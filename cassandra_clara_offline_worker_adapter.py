"""Cassandra/Clara offline worker adapter v0.

Cassandra is the internal/operator voice. Clara is the client-facing draft
voice. This adapter is deterministic and local only: no email, Gmail, network,
model call, tool execution, or external delivery.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping


SCHEMA_VERSION = "cassandra_clara_offline_worker_adapter_v0"
ADAPTER_ID = "cassandra_clara_offline_worker_adapter.local_comms_v0"

AUTHORITY_BOUNDARY = {
    "live_model_call_allowed": False,
    "repo_b_runtime_start_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "email_send_allowed": False,
    "gmail_access_allowed": False,
    "send_submit_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
    "credential_access_allowed": False,
    "network_allowed": False,
}


@dataclass(frozen=True)
class CassandraClaraOfflineWorkerResult:
    schema_version: str
    worker_adapter_id: str
    result_id: str
    source_package_id: str
    source_request_id: str
    response_author: str
    role_family: str
    internal_role_identity: str
    external_voice_identity: str
    audience: str
    selected_voice: str
    response_kind: str
    headline: str
    one_line_answer: str
    eliwinship: str
    status_summary: str
    draft_text: str
    next_action: str
    next_safe_move: str
    action_taken: str
    requested_tool_calls: tuple[str, ...]
    requested_external_actions: tuple[str, ...]
    external_action: bool
    authority_used: bool
    send_performed: bool
    authority_boundary: dict[str, bool]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def validate_cassandra_clara_package(package: Mapping[str, Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    if str(package.get("role_family") or "").upper() != "CASSANDRA_CLARA":
        reasons.append("Package role_family is not CASSANDRA_CLARA.")
    if str(package.get("internal_role_identity") or "").upper() != "CASSANDRA":
        reasons.append("Package internal role is not Cassandra.")
    if str(package.get("external_voice_identity") or "").upper() != "CLARA":
        reasons.append("Package external voice is not Clara.")
    if str(package.get("selected_voice") or "").upper() not in {"CASSANDRA", "CLARA"}:
        reasons.append("Package selected voice is not Cassandra or Clara.")
    if str(package.get("audience") or "").lower() not in {"internal", "external"}:
        reasons.append("Package audience is not internal or external.")
    if str(package.get("task") or "") != "comms_draft_or_status":
        reasons.append("Package task is not comms_draft_or_status.")
    if bool(package.get("lm2_call_allowed")):
        reasons.append("Package allows LM2 calls.")

    tool_policy = _mapping(package.get("tool_policy"))
    if tuple(tool_policy.get("allowed_tools") or ()):
        reasons.append("Package allows tools.")

    authority_policy = _mapping(package.get("authority_policy"))
    authority_boundary = _mapping(authority_policy.get("authority_boundary"))
    if any(bool(value) for value in authority_boundary.values()):
        reasons.append("Package contains live authority.")
    for flag in (
        "tool_authority_granted",
        "external_action_authority_granted",
        "send_submit_authority_granted",
    ):
        if bool(authority_policy.get(flag)):
            reasons.append(f"Package grants {flag}.")

    if not bool(package.get("ready_for_gate_4")):
        reasons.append("Package is not marked ready for Guardian validation.")
    return tuple(reasons)


def run_cassandra_clara_offline_worker(package: Mapping[str, Any]) -> dict[str, Any]:
    blocking_reasons = validate_cassandra_clara_package(package)
    if blocking_reasons:
        raise ValueError("; ".join(blocking_reasons))

    package_id = str(package.get("package_id") or "")
    source_request_id = str(package.get("source_request_id") or "")
    selected_voice = str(package.get("selected_voice") or "CASSANDRA").upper()
    audience = str(package.get("audience") or "internal").lower()
    client_ref = str(package.get("client_ref") or "current client")
    workflow_ref = str(package.get("workflow_ref") or "current workflow")
    if selected_voice == "CLARA":
        response_kind = "draft"
        headline = "Draft prepared"
        one_line_answer = "Clara prepared client-safe draft language only."
        status_summary = ""
        draft_text = (
            "Hi Capital Hilton team - we are preparing the invoice package and will share it after final review."
        )
        eliwinship = "Clara drafted client-safe wording only. Nothing was sent."
        next_action = "Next: review the draft before any email or delivery step."
    else:
        response_kind = "status"
        headline = "Invoice status"
        one_line_answer = "Cassandra checked the bounded package and prepared an internal status readback."
        status_summary = f"{client_ref} / {workflow_ref} is still in safe preparation. No send or final status happened."
        draft_text = ""
        eliwinship = "Cassandra prepared an internal status readback only. Nothing was sent."
        next_action = "Next: review the status and choose the next safe local step."

    result = CassandraClaraOfflineWorkerResult(
        schema_version=SCHEMA_VERSION,
        worker_adapter_id=ADAPTER_ID,
        result_id=f"cassandra_clara_offline_worker_result:{_short_hash(package_id, source_request_id, selected_voice)}",
        source_package_id=package_id,
        source_request_id=source_request_id,
        response_author="CASSANDRA_CLARA",
        role_family="CASSANDRA_CLARA",
        internal_role_identity="CASSANDRA",
        external_voice_identity="CLARA",
        audience=audience,
        selected_voice=selected_voice,
        response_kind=response_kind,
        headline=headline,
        one_line_answer=one_line_answer,
        eliwinship=eliwinship,
        status_summary=status_summary,
        draft_text=draft_text,
        next_action=next_action,
        next_safe_move="Return this worker result to Repo A for Guardian validation and receipt recording.",
        action_taken="none",
        requested_tool_calls=(),
        requested_external_actions=(),
        external_action=False,
        authority_used=False,
        send_performed=False,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )
    return asdict(result)


__all__ = [
    "ADAPTER_ID",
    "AUTHORITY_BOUNDARY",
    "CassandraClaraOfflineWorkerResult",
    "run_cassandra_clara_offline_worker",
    "validate_cassandra_clara_package",
]
