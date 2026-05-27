"""Chief offline worker adapter v0.

This is a local, deterministic adapter that represents the shape of a future
Chief worker without starting Repo B services, calling models, or executing
tools/actions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping


SCHEMA_VERSION = "chief_offline_worker_adapter_v0"
ADAPTER_ID = "chief_offline_worker_adapter.local_status_v0"

AUTHORITY_BOUNDARY = {
    "live_model_call_allowed": False,
    "repo_b_runtime_start_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
    "credential_access_allowed": False,
    "network_allowed": False,
}


@dataclass(frozen=True)
class ChiefOfflineWorkerResult:
    schema_version: str
    worker_adapter_id: str
    result_id: str
    source_package_id: str
    source_request_id: str
    response_author: str
    headline: str
    one_line_answer: str
    eliwinship: str
    status_summary: str
    next_action: str
    next_safe_move: str
    action_taken: str
    requested_tool_calls: tuple[str, ...]
    requested_external_actions: tuple[str, ...]
    external_action: bool
    authority_used: bool
    authority_boundary: dict[str, bool]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def validate_chief_package(package: Mapping[str, Any]) -> tuple[str, ...]:
    """Return blocking reasons for packages this adapter must not run."""

    reasons: list[str] = []
    if str(package.get("role_identity") or "").upper() != "CHIEF":
        reasons.append("Package role is not Chief.")
    if str(package.get("task") or "").strip() == "":
        reasons.append("Package task is missing.")
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


def run_chief_offline_worker(package: Mapping[str, Any]) -> dict[str, Any]:
    """Run the deterministic Chief status adapter for a bounded Repo A package."""

    blocking_reasons = validate_chief_package(package)
    if blocking_reasons:
        raise ValueError("; ".join(blocking_reasons))

    source_request_id = str(package.get("source_request_id") or "")
    package_id = str(package.get("package_id") or "")
    workflow_ref = str(package.get("workflow_ref") or "current workflow")
    client_ref = str(package.get("client_ref") or "current client")
    result = ChiefOfflineWorkerResult(
        schema_version=SCHEMA_VERSION,
        worker_adapter_id=ADAPTER_ID,
        result_id=f"chief_offline_worker_result:{_short_hash(package_id, source_request_id, workflow_ref)}",
        source_package_id=package_id,
        source_request_id=source_request_id,
        response_author="CHIEF",
        headline="Next safe move",
        one_line_answer="Chief checked the bounded package and found the next safe move.",
        eliwinship=(
            f"Chief checked {client_ref} / {workflow_ref}. No tools ran and no outside action happened."
        ),
        status_summary="The package is bounded for a local status readback only.",
        next_action="Next: respond in the originating Mission Control thread with the safe status readback.",
        next_safe_move="Return this worker result to Repo A for Guardian validation and receipt recording.",
        action_taken="none",
        requested_tool_calls=(),
        requested_external_actions=(),
        external_action=False,
        authority_used=False,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )
    return asdict(result)


__all__ = [
    "ADAPTER_ID",
    "AUTHORITY_BOUNDARY",
    "ChiefOfflineWorkerResult",
    "run_chief_offline_worker",
    "validate_chief_package",
]
