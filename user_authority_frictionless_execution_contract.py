"""User Authority + Frictionless Execution Contract v0.

This read-model separates "do the safe local work without theater" from
"never cross the operator's hard authority rails." It is metadata-only: it
does not execute work, approve actions, call tools, send messages, touch
money, restart production, inspect Legal Discovery, or grant credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "user_authority_frictionless_execution_contract_v0"
JSON_EXPORT_NAME = "user_authority_frictionless_execution_contract.json"
OPERATOR_EXPORT_NAME = "user_authority_frictionless_execution_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "contract_only": True,
    "execution_authority_added": False,
    "approval_authority_added": False,
    "operator_authority_transferred": False,
    "external_send_authority_added": False,
    "money_authority_added": False,
    "production_restart_authority_added": False,
    "credential_authority_added": False,
    "legal_discovery_authority_added": False,
    "merge_to_master_authority_added": False,
    "force_push_authority_added": False,
    "browser_or_oauth_authority_added": False,
    "hidden_background_loop_authority_added": False,
    "operator_final_authority_preserved": True,
}

FRICTIONLESS_ACTION_KINDS = (
    "repo_read",
    "bounded_branch_edit",
    "focused_test",
    "local_generated_read_model_export",
    "orchestration_status_marker",
    "markdown_audit_non_legal",
)

HARD_STOP_ACTION_KINDS = (
    "real_external_send",
    "money_movement",
    "production_restart_or_deploy",
    "legal_discovery",
    "secret_value_print_or_edit",
    "merge_to_master",
    "force_push",
    "direct_google_access_broker_call",
)

UNKNOWN_FAIL_CLOSED = "UNKNOWN_FAIL_CLOSED"


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class AuthorityRail:
    rail_id: str
    action_kind: str
    default_status: str
    operator_prompt_policy: str
    required_proof: tuple[str, ...]
    hard_boundary: str


EVIDENCE_SOURCES = (
    EvidenceSource(
        "runtime_law",
        "OPENCLAW_RUNTIME.md",
        "canonical repo-local runtime law for authority and execution posture",
    ),
    EvidenceSource(
        "operator_preferences",
        "USER.md",
        "operator communication and engineering preferences",
    ),
    EvidenceSource(
        "operator_action_covenant",
        "operator_action_covenant.py",
        "existing local confirmation and approval covenant boundary",
    ),
    EvidenceSource(
        "agent_identity_actor_router_contract",
        "generated/read_models/agent_identity_actor_router_contract.json",
        "actor routing and self-authority boundary",
    ),
    EvidenceSource(
        "protected_evidence_reference_receipt",
        "generated/read_models/protected_evidence_reference_receipt.json",
        "protected evidence reference boundary; receipts do not grant raw access",
    ),
)

AUTHORITY_RAILS = (
    AuthorityRail(
        "frictionless_repo_local_work",
        "bounded_branch_edit",
        "ALLOW_WITH_LOCAL_PROOF",
        "do_not_ask_when_branch_scoped_and_reversible",
        ("claim_marker", "branch", "focused_test_or_diff_receipt", "done_evidence"),
        "branch/worktree only; no live runtime authority",
    ),
    AuthorityRail(
        "frictionless_read_and_audit",
        "repo_read",
        "ALLOW_WITH_SOURCE_REFS",
        "do_not_ask_for_safe_reads",
        ("file_line_or_artifact_ref", "finding_or_status_marker"),
        "Legal Discovery and secrets remain excluded",
    ),
    AuthorityRail(
        "external_send_hard_stop",
        "real_external_send",
        "BLOCKED",
        "operator_final_authority_required_and_SEND_HOLD_blocks",
        ("explicit_operator_final_send_approval", "send_safety_receipt"),
        "SEND_HOLD is absolute; this contract cannot override it",
    ),
    AuthorityRail(
        "money_hard_stop",
        "money_movement",
        "BLOCKED",
        "operator_final_authority_required",
        ("operator_final_money_approval", "money_safety_receipt"),
        "no money movement or billing authority",
    ),
    AuthorityRail(
        "production_runtime_hard_stop",
        "production_restart_or_deploy",
        "BLOCKED",
        "master_or_operator_runtime_baton_required",
        ("deployment_plan", "rollback_plan", "operator_or_master_runtime_baton"),
        "no prod restart, deploy, or daemon control from this contract",
    ),
    AuthorityRail(
        "legal_hard_stop",
        "legal_discovery",
        "BLOCKED",
        "off_limits",
        ("none",),
        "Legal Discovery is off-limits for this fleet loop",
    ),
    AuthorityRail(
        "secrets_hard_stop",
        "secret_value_print_or_edit",
        "BLOCKED",
        "never_print_secret_values",
        ("secret_char_count_only_if_explicitly_needed",),
        "no secret values printed, edited, or copied",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = Path(repo_root) / target
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_record(source: EvidenceSource, *, repo_root: str | Path) -> dict[str, Any]:
    path = Path(repo_root) / source.path
    payload = _read_json_if_present(source.path, repo_root=repo_root) if source.path.endswith(".json") else {}
    return {
        "source_id": source.source_id,
        "path": source.path,
        "role": source.role,
        "present": path.is_file(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "raw_private_body_imported": False,
        "authority_granted_by_source_presence": False,
    }


def _rail_record(rail: AuthorityRail) -> dict[str, Any]:
    return {
        "rail_id": rail.rail_id,
        "action_kind": rail.action_kind,
        "default_status": rail.default_status,
        "operator_prompt_policy": rail.operator_prompt_policy,
        "required_proof": list(rail.required_proof),
        "hard_boundary": rail.hard_boundary,
    }


def decide_frictionless_execution(
    action_kind: str,
    *,
    send_hold_present: bool = True,
    operator_final_approval_present: bool = False,
    branch_scoped: bool = True,
    reversible: bool = True,
    legal_discovery_in_scope: bool = False,
    secret_values_requested: bool = False,
) -> dict[str, Any]:
    """Return a deterministic boundary decision; execute nothing."""
    normalized = str(action_kind or "").strip()
    reasons: list[str] = []
    may_proceed = False

    if normalized in FRICTIONLESS_ACTION_KINDS:
        if not branch_scoped and normalized in {"bounded_branch_edit", "local_generated_read_model_export"}:
            reasons.append("branch_or_worktree_scope_required")
        if not reversible and normalized != "focused_test":
            reasons.append("reversibility_required_for_frictionless_execution")
        if legal_discovery_in_scope:
            reasons.append("legal_discovery_off_limits")
        if secret_values_requested:
            reasons.append("secret_values_must_not_be_printed_or_edited")
        may_proceed = not reasons
        status = "ALLOW_FRICTIONLESS_LOCAL" if may_proceed else "BLOCKED_UNTIL_BOUNDARY_FIXED"
    elif normalized in HARD_STOP_ACTION_KINDS:
        if normalized == "real_external_send" and send_hold_present:
            reasons.append("SEND_HOLD_blocks_real_external_send")
        if not operator_final_approval_present:
            reasons.append("operator_final_authority_required")
        if normalized == "legal_discovery":
            reasons.append("legal_discovery_off_limits")
        if normalized == "secret_value_print_or_edit":
            reasons.append("secret_values_must_not_be_printed")
        status = "BLOCKED"
    else:
        status = UNKNOWN_FAIL_CLOSED
        reasons.append("unknown_action_kind")

    return {
        "action_kind": normalized,
        "decision": status,
        "may_proceed_without_extra_operator_prompt": may_proceed,
        "operator_final_authority_required": normalized in HARD_STOP_ACTION_KINDS,
        "execution_authority_granted_by_contract": False,
        "approval_authority_granted_by_contract": False,
        "blocking_reasons": reasons,
    }


def build_user_authority_frictionless_execution_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    examples = [
        decide_frictionless_execution("bounded_branch_edit"),
        decide_frictionless_execution("focused_test"),
        decide_frictionless_execution("real_external_send", send_hold_present=True),
        decide_frictionless_execution("legal_discovery"),
        decide_frictionless_execution("secret_value_print_or_edit", secret_values_requested=True),
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "user_authority_frictionless_execution_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_user_authority_and_frictionless_execution_metadata_only",
        "operator_summary": (
            "OpenClaw may move quickly on safe, reversible, local work, but the operator keeps final authority "
            "over sends, money, production runtime, secrets, Legal Discovery, force-git, and merges."
        ),
        "frictionless_execution_doctrine": {
            "safe_local_work_should_not_wait_for_extra_prompt": True,
            "safe_local_work_must_still_leave_evidence": True,
            "external_or_irreversible_work_never_becomes_frictionless": True,
            "heartbeat_is_not_liveness": True,
        },
        "authority_rails": [_rail_record(rail) for rail in AUTHORITY_RAILS],
        "frictionless_action_kinds": list(FRICTIONLESS_ACTION_KINDS),
        "hard_stop_action_kinds": list(HARD_STOP_ACTION_KINDS),
        "hard_stop_rails_preserved": {
            "SEND_HOLD_absolute": True,
            "no_real_external_send": True,
            "no_money": True,
            "no_prod_restart_or_deploy": True,
            "legal_discovery_off_limits": True,
            "no_secret_values_printed": True,
            "no_merge_to_master": True,
            "no_force_push": True,
        },
        "claim_and_gate_requirements": {
            "claim_before_work": True,
            "one_green_gate_at_a_time_per_machine": True,
            "done_requires_evidence_bundle": True,
            "natural_language_done_is_not_proof": True,
        },
        "example_boundary_decisions": examples,
        "evidence_sources": evidence_sources,
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "authority_rail_count": len(AUTHORITY_RAILS),
            "frictionless_action_count": len(FRICTIONLESS_ACTION_KINDS),
            "hard_stop_action_count": len(HARD_STOP_ACTION_KINDS),
            "execution_authority_added": False,
            "approval_authority_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_user_authority_frictionless_execution_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# User Authority + Frictionless Execution Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Frictionless Local Work",
    ]
    for action in payload["frictionless_action_kinds"]:
        lines.append(f"- `{action}`")
    lines.extend(["", "## Hard Stops"])
    for key, value in payload["hard_stop_rails_preserved"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Proof Requirements"])
    reqs = payload["claim_and_gate_requirements"]
    for key, value in reqs.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    return "\n".join(lines).rstrip() + "\n"


@dataclass(frozen=True)
class UserAuthorityFrictionlessExecutionExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    authority_rail_count: int
    execution_authority_added: bool
    approval_authority_added: bool


def export_user_authority_frictionless_execution_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> UserAuthorityFrictionlessExecutionExportResult:
    payload = build_user_authority_frictionless_execution_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_user_authority_frictionless_execution_contract(payload), encoding="utf-8")
    return UserAuthorityFrictionlessExecutionExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        authority_rail_count=len(payload["authority_rails"]),
        execution_authority_added=bool(payload["execution_authority_added"]),
        approval_authority_added=bool(payload["approval_authority_added"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export User Authority + Frictionless Execution Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_user_authority_frictionless_execution_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(build_user_authority_frictionless_execution_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_user_authority_frictionless_execution_contract(repo_root=args.repo_root)
        print(format_user_authority_frictionless_execution_contract(payload), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0


__all__ = [
    "FRICTIONLESS_ACTION_KINDS",
    "HARD_STOP_ACTION_KINDS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_user_authority_frictionless_execution_contract",
    "decide_frictionless_execution",
    "export_user_authority_frictionless_execution_contract",
    "format_user_authority_frictionless_execution_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
