"""Role package gate v0.

Gate 3 in the OpenClaw chain receives an accepted Gate 2 intent and compiles a
bounded package for a future LM2/role worker. It is a package compiler only: it
does not call LM2, dispatch roles, execute tools, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import guardian_output_gate
import intent_ingest_gate
import machine_intent_candidate_validator as intent_validator


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "role_package_gate_v0"
READ_MODEL_ID = "role_package_gate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_ROLE_PACKAGE_GATE_NO_EXECUTION"
GATE_ID = "gate_3:role_package"

PACKAGE_COMPILED = "ROLE_PACKAGE_COMPILED"
PACKAGE_NOT_COMPILED = "PACKAGE_NOT_COMPILED_GATE2_NOT_ACCEPTED"
PACKAGE_BLOCKED_AUTHORITY = "PACKAGE_BLOCKED_AUTHORITY"
UNKNOWN_FAIL_CLOSED = "UNKNOWN_FAIL_CLOSED"

AUTHORITY_BOUNDARY = {
    "live_lm2_call_allowed": False,
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_worker_dispatch_allowed": False,
    "live_workflow_execution_allowed": False,
    "live_tool_execution_allowed": False,
    "live_external_action_allowed": False,
    "live_send_submit_allowed": False,
    "live_approval_execution_allowed": False,
    "live_candidate_promotion_allowed": False,
    "live_file_body_read_allowed": False,
    "live_workbook_body_read_allowed": False,
    "live_spreadsheet_cell_read_allowed": False,
    "live_file_mutation_allowed": False,
    "live_pdf_generation_allowed": False,
    "live_browser_allowed": False,
    "live_coupa_access_allowed": False,
    "live_email_send_allowed": False,
    "live_ledger_posting_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
}

FORBIDDEN_ACTIONS = (
    "send_email",
    "send_gmail",
    "submit_to_coupa",
    "open_browser",
    "access_network",
    "read_workbook_body",
    "read_spreadsheet_cells",
    "mutate_file",
    "write_excel",
    "generate_pdf",
    "post_ledger_entry",
    "mark_invoice_sent",
    "mark_invoice_paid",
    "execute_workflow",
    "dispatch_agent",
    "dispatch_worker",
    "handle_credentials",
)

FORBIDDEN_TOOLS = (
    "gmail",
    "coupa",
    "browser",
    "network",
    "excel_writer",
    "pdf_generator",
    "ledger_writer",
    "credential_vault",
    "raw_body_reader",
    "workflow_runner",
    "agent_dispatcher",
    "worker_dispatcher",
)

ALLOWED_ACTIONS = (
    "respond_to_originating_device_thread",
    "ask_clarifying_question",
    "prepare_readback_text",
    "compile_nonexecuting_package",
)


@dataclass(frozen=True)
class RoleBindingDecision:
    role_binding_decision_id: str
    source_ingest_result_ref: str
    source_intent_ref: str
    selected_role: str
    actor_label: str
    selection_reason: str
    voice_profile_ref: str
    vibe_profile_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class RoleContextPacket:
    context_packet_id: str
    allowed_context_refs: tuple[str, ...]
    forbidden_context_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    raw_body_allowed: bool
    credential_material_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class RoleToolPolicy:
    tool_policy_id: str
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    receipt_required_for_blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class RoleOutputDestination:
    output_destination_id: str
    destination_type: str
    source_request_id: str
    thread_ref: str
    device_ref: str
    gate_4_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class PackageAuthorityPolicy:
    authority_policy_id: str
    authority_boundary: dict[str, bool]
    required_receipts_before_tools: tuple[str, ...]
    tool_authority_granted: bool
    external_action_authority_granted: bool
    send_submit_authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class RoleExecutionPackage:
    package_id: str
    source_request_id: str
    source_ingest_result_ref: str
    source_intent_ref: str
    role_identity: str
    actor_label: str
    task: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    role_binding_decision: dict[str, Any]
    context_packet: dict[str, Any]
    tool_policy: dict[str, Any]
    output_destination: dict[str, Any]
    authority_policy: dict[str, Any]
    tokenization_applied: bool
    token_scope: str
    raw_values_included: bool
    token_vault_ref: str
    detokenization_policy_ref: str
    privacy_level: str
    model_may_see_raw_values: bool
    output_contract_ref: str
    validation_required: bool
    ready_for_gate_4: bool
    lm2_call_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class PackageCompilerResult:
    compiler_result_id: str
    gate_id: str
    package_status: str
    source_ingest_result_ref: str
    source_request_id: str
    role_execution_package: dict[str, Any] | None
    blocked_reasons: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _all_false_authority() -> dict[str, bool]:
    return {
        "lm2_call": False,
        "model_call": False,
        "agent_dispatch": False,
        "worker_dispatch": False,
        "workflow_execution": False,
        "tool_execution": False,
        "external_action": False,
        "send_submit": False,
        "approval_execution": False,
        "candidate_promotion": False,
        "file_body_read": False,
        "workbook_body_read": False,
        "spreadsheet_cell_read": False,
        "file_mutation": False,
        "pdf_generation": False,
        "ledger_posting": False,
        "credential_handling": False,
        "raw_body_ingestion": False,
    }


def _accepted_intent(ingest_result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    accepted = ingest_result.get("accepted_intent")
    return accepted if isinstance(accepted, Mapping) else None


def _role_for_intent(accepted: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    intent_type = str(accepted.get("intent_type") or "")
    requested_role = str(accepted.get("target_agent_role") or "").upper()
    action = str(accepted.get("requested_action") or "").lower()
    world = str(accepted.get("world_ref") or "").lower()
    workflow = str(accepted.get("workflow_ref") or "").lower()

    if requested_role == "NILES" or "x32" in workflow:
        return ("NILES", "Niles", "music/audio/source-ref work", "voice:niles:creative_technical", "vibe:niles:studio_precise")
    if requested_role == "GUARDIAN" or intent_type == "REQUEST_APPROVAL":
        return ("GUARDIAN", "Guardian", "protected boundary review", "voice:guardian:proof_gate", "vibe:guardian:strict_proof")
    if requested_role == "CASSANDRA" and intent_type == "PREPARE_DRAFT":
        return ("CASSANDRA", "Cassandra", "communications draft preparation", "voice:cassandra:admin", "vibe:cassandra:calm_comms")
    if ("finance" in world or "invoice" in workflow or "invoice" in action) and intent_type in {
        "CAPTURE_MISSING_INPUT",
        "ATTACH_SOURCE_REF",
        "RUN_DRY_RUN",
    }:
        return ("CASSANDRA_CLARA", "Cassandra/Clara", "finance invoice preparation support", "voice:cassandra:finance", "vibe:clara:finance_precise")
    if intent_type == "ANSWER_STATUS":
        return ("CHIEF", "Chief", "operator status/readback", "voice:chief:operational", "vibe:chief:command_center")
    if requested_role in {"CHIEF", "CASSANDRA", "HERMES", "OPENCLAW_SYSTEM"}:
        label = "OpenClaw System" if requested_role == "OPENCLAW_SYSTEM" else requested_role.title()
        return (requested_role, label, "bounded role response", f"voice:{requested_role.lower()}:default", f"vibe:{requested_role.lower()}:default")
    return ("OPENCLAW_SYSTEM", "OpenClaw System", "neutral bounded response", "voice:system:neutral", "vibe:system:steady")


def _blocked_result(
    ingest_result: Mapping[str, Any],
    *,
    package_status: str = PACKAGE_NOT_COMPILED,
    reason: str,
) -> dict[str, Any]:
    source_request_id = str(ingest_result.get("source_request_id") or "unknown_source_request")
    source_ingest_ref = str(ingest_result.get("ingest_result_id") or "")
    result = PackageCompilerResult(
        compiler_result_id=f"role_package_compiler_result:{_short_hash(source_ingest_ref, package_status, reason)}",
        gate_id=GATE_ID,
        package_status=package_status,
        source_ingest_result_ref=source_ingest_ref,
        source_request_id=source_request_id,
        role_execution_package=None,
        blocked_reasons=(reason,),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Do not compile a role package until Gate 2 accepts the intent.",
    )
    return asdict(result)


def compile_role_package(ingest_result: Mapping[str, Any]) -> dict[str, Any]:
    """Compile a bounded role package from an accepted Gate 2 result only."""

    if str(ingest_result.get("outcome") or "") != intent_ingest_gate.ACCEPTED_INTENT:
        return _blocked_result(ingest_result, reason="Gate 2 outcome is not ACCEPTED_INTENT.")
    accepted = _accepted_intent(ingest_result)
    if accepted is None:
        return _blocked_result(ingest_result, reason="Gate 2 accepted intent payload is missing.")

    authority = accepted.get("authority_granted") if isinstance(accepted.get("authority_granted"), Mapping) else {}
    if any(bool(value) for value in authority.values()):
        return _blocked_result(
            ingest_result,
            package_status=PACKAGE_BLOCKED_AUTHORITY,
            reason="Accepted intent contained live authority; package compiler fails closed.",
        )

    role, actor_label, reason, voice_ref, vibe_ref = _role_for_intent(accepted)
    source_request_id = str(accepted.get("source_request_id") or ingest_result.get("source_request_id") or "")
    source_intent_ref = str(accepted.get("source_candidate_ref") or ingest_result.get("source_candidate_ref") or "")
    source_ingest_ref = str(ingest_result.get("ingest_result_id") or "")
    task = str(accepted.get("requested_action") or accepted.get("safe_action_type") or "Prepare bounded response.")
    client_ref = str(accepted.get("client_ref") or "unknown")
    workflow_ref = str(accepted.get("workflow_ref") or "unknown")
    world_ref = str(accepted.get("world_ref") or "unknown")
    token_scope = f"scope:{world_ref}:{client_ref}:{workflow_ref}"
    safe_refs = tuple(
        str(ref)
        for ref in (
            tuple(accepted.get("context_refs_used") or ())
            + tuple(accepted.get("evidence_refs_used") or ())
            + tuple(accepted.get("source_refs_used") or ())
        )
        if ref
    )
    binding = RoleBindingDecision(
        role_binding_decision_id=f"role_binding_decision:{_short_hash(source_intent_ref, role)}",
        source_ingest_result_ref=source_ingest_ref,
        source_intent_ref=source_intent_ref,
        selected_role=role,
        actor_label=actor_label,
        selection_reason=reason,
        voice_profile_ref=voice_ref,
        vibe_profile_ref=vibe_ref,
        next_safe_move="Use this role identity only inside a bounded package; do not dispatch yet.",
    )
    context = RoleContextPacket(
        context_packet_id=f"role_context_packet:{_short_hash(source_intent_ref, safe_refs)}",
        allowed_context_refs=safe_refs,
        forbidden_context_refs=("credentials", "tokens", "raw private bodies", "unrelated client data", "unapproved file bodies"),
        evidence_refs=tuple(str(ref) for ref in accepted.get("evidence_refs_used") or ()),
        source_refs=tuple(str(ref) for ref in accepted.get("source_refs_used") or ()),
        raw_body_allowed=False,
        credential_material_allowed=False,
        next_safe_move="Provide only safe refs/summaries to a future LM2 role call.",
    )
    tool_policy = RoleToolPolicy(
        tool_policy_id=f"role_tool_policy:{_short_hash(source_intent_ref, role)}",
        allowed_tools=(),
        forbidden_tools=FORBIDDEN_TOOLS,
        allowed_actions=ALLOWED_ACTIONS,
        forbidden_actions=FORBIDDEN_ACTIONS,
        receipt_required_for_blocked_actions=(
            "guardian_approval_receipt",
            "exact_operator_approval_receipt",
            "provider_or_adapter_receipt",
            "post_action_proof_receipt",
        ),
        next_safe_move="Treat all tools and external actions as blocked until a later gate provides receipts.",
    )
    destination = RoleOutputDestination(
        output_destination_id=f"role_output_destination:{_short_hash(source_request_id, 'mission_control')}",
        destination_type="MISSION_CONTROL_SCOPED_RESPONSE",
        source_request_id=source_request_id,
        thread_ref=source_request_id,
        device_ref="mission_control",
        gate_4_ref=guardian_output_gate.READ_MODEL_ID,
        next_safe_move="A future LM2 response candidate must pass Guardian output gate before publication/action.",
    )
    authority_policy = PackageAuthorityPolicy(
        authority_policy_id=f"package_authority_policy:{_short_hash(source_intent_ref, role)}",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        required_receipts_before_tools=tool_policy.receipt_required_for_blocked_actions,
        tool_authority_granted=False,
        external_action_authority_granted=False,
        send_submit_authority_granted=False,
        next_safe_move="No live authority is available in this package.",
    )
    package = RoleExecutionPackage(
        package_id=f"role_execution_package:{_short_hash(source_ingest_ref, source_intent_ref, role)}",
        source_request_id=source_request_id,
        source_ingest_result_ref=source_ingest_ref,
        source_intent_ref=source_intent_ref,
        role_identity=role,
        actor_label=actor_label,
        task=task,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
        role_binding_decision=asdict(binding),
        context_packet=asdict(context),
        tool_policy=asdict(tool_policy),
        output_destination=asdict(destination),
        authority_policy=asdict(authority_policy),
        tokenization_applied=True,
        token_scope=token_scope,
        raw_values_included=False,
        token_vault_ref="generated/read_models/token_vault_status.json",
        detokenization_policy_ref="detokenization_denied_without_explicit_policy_receipt",
        privacy_level="metadata_only_tokenized_refs",
        model_may_see_raw_values=False,
        output_contract_ref=guardian_output_gate.SCHEMA_VERSION,
        validation_required=True,
        ready_for_gate_4=True,
        lm2_call_allowed=False,
        next_safe_move="When a future lane enables LM2, send only this package; validate the response with Guardian output gate.",
    )
    result = PackageCompilerResult(
        compiler_result_id=f"role_package_compiler_result:{_short_hash(package.package_id, PACKAGE_COMPILED)}",
        gate_id=GATE_ID,
        package_status=PACKAGE_COMPILED,
        source_ingest_result_ref=source_ingest_ref,
        source_request_id=source_request_id,
        role_execution_package=asdict(package),
        blocked_reasons=(),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=package.next_safe_move,
    )
    return asdict(result)


def _accepted_example(
    *,
    intent_id: str,
    source_request_id: str,
    intent_type: str,
    requested_action: str,
    role: str,
    world_ref: str = "finance",
    workflow_ref: str = "capital_hilton_invoice_workflow",
) -> dict[str, Any]:
    candidate = intent_validator.MachineIntentCandidate(
        intent_id=intent_id,
        source_request_id=source_request_id,
        original_operator_text=requested_action,
        inferred_intent_type=intent_type,
        target_world_ref=world_ref,
        target_folder_ref="capital_hilton" if "capital_hilton" in workflow_ref else "folder_ref:current",
        target_thread_ref="thread_ref:finance_capital_hilton",
        target_workflow_ref=workflow_ref,
        target_agent_role=role,
        target_worker_type="PC_CODEX",
        requested_action=requested_action,
        referenced_next_action="",
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=(),
        context_refs_used=("tenant_scope:fixture_business_ops",),
        source_refs_used=(),
        missing_requirements=(),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False},
        authority_granted={"send_submit": False, "external_action": False},
        validation_required=True,
        next_safe_move="Validate before packaging.",
    )
    return intent_ingest_gate.ingest_intent_proposal(candidate)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    chief_ingest = _accepted_example(
        intent_id="role_package_gate_fixture_status",
        source_request_id="role_package_gate_status_request",
        intent_type="ANSWER_STATUS",
        requested_action="Answer the Capital Hilton workflow status.",
        role="CHIEF",
    )
    cassandra_ingest = _accepted_example(
        intent_id="role_package_gate_fixture_draft",
        source_request_id="role_package_gate_draft_request",
        intent_type="PREPARE_DRAFT",
        requested_action="Prepare review language for the invoice email draft.",
        role="CASSANDRA",
    )
    blocked_ingest = {
        **chief_ingest,
        "outcome": intent_ingest_gate.BLOCKED_AUTHORITY,
        "accepted_intent": None,
        "blocker_reasons": ("fixture blocked authority",),
    }
    chief_package = compile_role_package(chief_ingest)
    cassandra_package = compile_role_package(cassandra_ingest)
    blocked_package = compile_role_package(blocked_ingest)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "examples": {
            "chief_status_package": chief_package,
            "cassandra_draft_package": cassandra_package,
            "blocked_gate2_result": blocked_package,
        },
        "machine_proof": {
            "gate_3_present": True,
            "gate_2_required_before_gate_3": True,
            "chief_package_compiled": chief_package["package_status"] == PACKAGE_COMPILED,
            "cassandra_package_compiled": cassandra_package["package_status"] == PACKAGE_COMPILED,
            "blocked_gate2_not_compiled": blocked_package["package_status"] == PACKAGE_NOT_COMPILED,
            "ready_for_gate_4": bool((chief_package.get("role_execution_package") or {}).get("ready_for_gate_4")),
            "tokenization_fields_present": bool((chief_package.get("role_execution_package") or {}).get("token_vault_ref")),
            "raw_values_included": bool((chief_package.get("role_execution_package") or {}).get("raw_values_included")),
            "model_may_see_raw_values": bool((chief_package.get("role_execution_package") or {}).get("model_may_see_raw_values")),
            "lm2_call_performed": False,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "worker_dispatch_performed": False,
            "workflow_execution_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "approval_execution_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    proof = payload.get("machine_proof", {})
    lines = [
        "# Role Package Gate",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Chief package compiled: {str(proof.get('chief_package_compiled')).lower()}",
        f"Blocked Gate 2 result compiled: {str(not proof.get('blocked_gate2_not_compiled')).lower()}",
        f"Tokenization fields present: {str(proof.get('tokenization_fields_present')).lower()}",
        "",
        "Gate 3 compiles bounded role packages only from Gate 2 accepted intents.",
        "",
        "Boundary: no LM2 call, no role dispatch, no tools, no send/submit, no authority grant.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Role Package Gate read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "chief_package_compiled": payload["machine_proof"]["chief_package_compiled"],
                    "blocked_gate2_not_compiled": payload["machine_proof"]["blocked_gate2_not_compiled"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
