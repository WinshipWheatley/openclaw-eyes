"""LM Readiness Dashboard v0.

Canonical integration read-model for the seeded LM readiness lanes. It builds a
representative non-live thread proof and summarizes what is ready, what is
blocked, and where the next floor-raising work should go.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import gate_chain_harness
import guardian_output_gate
import guardian_trust_ramp_simulator
import intent_ingest_gate
import live_lm_readiness_gate
import lm_intent_proposal_contract
import model_router_policy
import role_package_gate
import shadow_lm_mode
import token_vault
import universal_intake_contract
from machine_intent_candidate_validator import MachineIntentCandidate


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "lm_readiness_dashboard_v0"
READ_MODEL_ID = "lm_readiness_dashboard"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LM_READINESS_INTEGRATION_NO_LIVE_LM"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "provider_key_material_access_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "tool_execution_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "pdf_generation_allowed": False,
}


@dataclass(frozen=True)
class LM1ThreadContextPackage:
    package_id: str
    source_request_id: str
    user_message: str
    current_world_ref: str
    current_thread_ref: str
    universal_intake_inference: dict[str, Any]
    privacy: dict[str, Any]
    allowed_context_classes: tuple[str, ...]
    forbidden_context_classes: tuple[str, ...]
    output_schema: tuple[str, ...]
    raw_values_included: bool
    tools_allowed: tuple[str, ...]
    authority_granted: dict[str, bool]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def build_lm1_thread_context_package(*, source_request_id: str = "lm_readiness_capital_hilton_fixture") -> dict[str, Any]:
    user_message = "these are invoice workbooks for the clients named in the files"
    intake = universal_intake_contract.infer_universal_intake(
        {
            "intake_id": "lm_readiness_universal_intake_fixture",
            "source_request_id": source_request_id,
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "file_extension": ".xlsx",
            "file_type": "spreadsheet",
            "user_note": user_message,
            "current_world_ref": "finance",
        }
    )
    token_scope = "scope:finance:capital_hilton:lm_readiness_fixture"
    privacy = token_vault.role_package_tokenization_declaration(token_scope)
    package = LM1ThreadContextPackage(
        package_id=f"lm1_thread_context_package:{_short_hash(source_request_id, intake.get('candidate_id'))}",
        source_request_id=source_request_id,
        user_message=user_message,
        current_world_ref="finance",
        current_thread_ref="thread_ref:finance_capital_hilton",
        universal_intake_inference=intake,
        privacy={
            **privacy,
            "privacy_level": "metadata_only_tokenized_refs",
            "token_vault_ref": "generated/read_models/token_vault_status.json",
            "model_may_see_raw_values": False,
        },
        allowed_context_classes=("metadata_only_file_ref", "universal_intake_summary", "tokenized_fixture_refs", "thread_scope_refs"),
        forbidden_context_classes=("raw workbook body", "spreadsheet cells", "credentials", "raw private bodies", "unrelated client data"),
        output_schema=tuple(MachineIntentCandidate.__dataclass_fields__),
        raw_values_included=False,
        tools_allowed=(),
        authority_granted={
            "model_call": False,
            "tool_execution": False,
            "external_action": False,
            "send_submit": False,
            "workflow_execution": False,
        },
        next_safe_move="A future LM1 may propose MachineIntentCandidate JSON only; Gate 2 decides ingestion.",
    )
    return asdict(package)


def _candidate_from_lm1_package(package: Mapping[str, Any]) -> MachineIntentCandidate:
    intake = package.get("universal_intake_inference") if isinstance(package.get("universal_intake_inference"), Mapping) else {}
    return MachineIntentCandidate(
        intent_id=f"lm_readiness_candidate:{_short_hash(package.get('source_request_id'), intake.get('candidate_id'))}",
        source_request_id=str(package.get("source_request_id") or "lm_readiness_fixture"),
        original_operator_text=str(package.get("user_message") or ""),
        inferred_intent_type="ATTACH_SOURCE_REF",
        target_world_ref=str(intake.get("world_ref") or "finance"),
        target_folder_ref=str(intake.get("client_ref") or "capital_hilton"),
        target_thread_ref=str(package.get("current_thread_ref") or "thread_ref:finance_capital_hilton"),
        target_workflow_ref=str(intake.get("workflow_ref") or "capital_hilton_invoice_workflow"),
        target_agent_role="OPENCLAW_SYSTEM",
        target_worker_type="PC_CODEX",
        requested_action="Attach the running draft invoice workbook reference as metadata-only source context.",
        referenced_next_action="Next: register/resolve the workbook artifact through governed intake only.",
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=(str(intake.get("candidate_id") or "universal_intake_candidate"),),
        context_refs_used=("tenant_scope:fixture_business_ops", str((package.get("privacy") or {}).get("token_scope") or "")),
        source_refs_used=(f"universal_intake:{intake.get('candidate_id')}",),
        missing_requirements=(),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False, "workflow_execution": False},
        authority_granted={"send_submit": False, "external_action": False, "workflow_execution": False},
        validation_required=True,
        next_safe_move="Run Gate 2 ingest; do not execute.",
    )


def build_representative_flow(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    lm1_package = build_lm1_thread_context_package()
    lm1_model_decision = model_router_policy.select_for_lm1_thread_package(lm1_package)
    candidate = _candidate_from_lm1_package(lm1_package)
    package_payload = lm_intent_proposal_contract.build_payload(
        {
            "request_id": candidate.source_request_id,
            "operator_message": lm1_package["user_message"],
            "world_ref": candidate.target_world_ref,
            "client_ref": lm1_package["universal_intake_inference"]["client_ref"],
            "workflow_ref": candidate.target_workflow_ref,
        },
        generated_at=generated_at,
    )
    gate2_result = intent_ingest_gate.ingest_intent_proposal(candidate, package_payload=package_payload)
    gate3_result = role_package_gate.compile_role_package(gate2_result)
    role_package = gate3_result.get("role_execution_package") or {}
    lm2_model_decision = model_router_policy.select_for_lm2_role_package(role_package)
    lm2_response_candidate = {
        "source_request_id": candidate.source_request_id,
        "workflow_ref": candidate.target_workflow_ref,
        "client_ref": lm1_package["universal_intake_inference"]["client_ref"],
        "response_author": role_package.get("role_identity") or "OPENCLAW_SYSTEM",
        "selected_model_backend": "LM2_STUB_ONLY",
        "allowed_tools_plugins": (),
        "headline": "Capital Hilton workbook recognized",
        "one_line_answer": "OpenClaw can treat this as a draft workbook reference candidate.",
        "eliwinship": "OpenClaw recognized the Capital Hilton running invoice workbook as draft/source material only. Nothing was read, sent, posted, or marked final.",
        "next_action": "Next: keep this as metadata-only intake proof or run the governed workbook intake.",
        "readback_files": ("generated/read_models/lm_readiness_dashboard.json",),
    }
    gate4_result = guardian_output_gate.validate_response_payload(lm2_response_candidate)
    return {
        "lm1_thread_context_package": lm1_package,
        "lm1_model_decision": lm1_model_decision,
        "lm1_fixture_candidate": asdict(candidate),
        "gate2_result": gate2_result,
        "gate3_result": gate3_result,
        "gate3_tokenization": {
            "tokenization_applied": bool(role_package.get("tokenization_applied")),
            "token_scope": role_package.get("token_scope"),
            "raw_values_included": bool(role_package.get("raw_values_included")),
            "token_vault_ref": role_package.get("token_vault_ref"),
            "detokenization_policy_ref": role_package.get("detokenization_policy_ref"),
            "privacy_level": role_package.get("privacy_level"),
            "model_may_see_raw_values": bool(role_package.get("model_may_see_raw_values")),
        },
        "lm2_model_decision": lm2_model_decision,
        "lm2_response_candidate": lm2_response_candidate,
        "gate4_result": gate4_result,
    }


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    representative = build_representative_flow(generated_at=generated_at)
    gate_chain = gate_chain_harness.run_harness(generated_at=generated_at, persist=True)
    trust_ramp = guardian_trust_ramp_simulator.run_trust_ramp(generated_at=generated_at, persist=True)
    shadow = shadow_lm_mode.build_payload(generated_at=generated_at, persist=True)
    model_router = model_router_policy.build_payload(generated_at=generated_at)
    readiness = live_lm_readiness_gate.build_payload(generated_at=generated_at)
    token_status = token_vault.build_payload(generated_at=generated_at)
    universal = universal_intake_contract.build_payload(generated_at=generated_at)
    role_package = representative["gate3_result"].get("role_execution_package") or {}
    dashboard_summary = {
        "lm1_shadow": "READY" if readiness["machine_proof"]["lm1_shadow_ready"] else "NOT_READY",
        "lm1_live": "NOT_ACTIVE",
        "lm2_package_shadow": "READY" if readiness["machine_proof"]["lm2_shadow_ready"] else "NOT_READY",
        "lm2_live": "NOT_ACTIVE",
        "tokenization": "SEEDED_NOT_PRODUCTION",
        "universal_intake": "SEEDED",
        "model_router": "SEEDED",
        "gate2_ingest": representative["gate2_result"].get("outcome"),
        "gate3_package": representative["gate3_result"].get("package_status"),
        "gate4_guardian": (representative["gate4_result"].get("validation_result") or {}).get("verdict"),
        "trust_ramp_candidate_level": trust_ramp["score"]["candidate_trust_level"],
        "trust_ramp_active_level": trust_ramp["score"]["active_trust_level"],
        "next_blockers": (
            "live LM explicit enablement receipt",
            "live model/provider policy receipt",
            "production token vault readiness",
            "live receipt/promotion policy",
            "real LM shadow comparison runs",
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "dashboard_summary": dashboard_summary,
        "representative_request": {
            "filename": "Invoice Capitol Hilton Running.xlsx",
            "user_note": "these are invoice workbooks for the clients named in the files",
            "world_ref": "finance",
            "source_request_id": representative["lm1_thread_context_package"]["source_request_id"],
        },
        "representative_flow": {
            "universal_intake_inference": representative["lm1_thread_context_package"]["universal_intake_inference"],
            "privacy": representative["lm1_thread_context_package"]["privacy"],
            "lm1_thread_context_package": representative["lm1_thread_context_package"],
            "lm1_model_decision": representative["lm1_model_decision"],
            "gate2_result_summary": {
                "outcome": representative["gate2_result"].get("outcome"),
                "accepted_intent": representative["gate2_result"].get("accepted_intent"),
                "blocker_reasons": representative["gate2_result"].get("blocker_reasons"),
            },
            "gate3_package_summary": {
                "package_status": representative["gate3_result"].get("package_status"),
                "package_id": role_package.get("package_id"),
                "role_identity": role_package.get("role_identity"),
                "tokenization_applied": role_package.get("tokenization_applied"),
                "token_scope": role_package.get("token_scope"),
                "raw_values_included": role_package.get("raw_values_included"),
                "token_vault_ref": role_package.get("token_vault_ref"),
                "detokenization_policy_ref": role_package.get("detokenization_policy_ref"),
                "privacy_level": role_package.get("privacy_level"),
                "model_may_see_raw_values": role_package.get("model_may_see_raw_values"),
                "allowed_tools": (role_package.get("tool_policy") or {}).get("allowed_tools", ()),
                "forbidden_tools": (role_package.get("tool_policy") or {}).get("forbidden_tools", ()),
            },
            "lm2_model_decision": representative["lm2_model_decision"],
            "gate4_result_summary": representative["gate4_result"].get("validation_result"),
        },
        "aggregated_lanes": {
            "gate_chain_harness": {
                "read_model_id": gate_chain_harness.READ_MODEL_ID,
                "summary": gate_chain.get("summary", {}),
            },
            "guardian_trust_ramp_simulator": {
                "read_model_id": guardian_trust_ramp_simulator.READ_MODEL_ID,
                "score": trust_ramp.get("score", {}),
            },
            "model_router_policy": {
                "read_model_id": model_router_policy.READ_MODEL_ID,
                "machine_proof": model_router.get("machine_proof", {}),
            },
            "live_lm_readiness_gate": {
                "read_model_id": live_lm_readiness_gate.READ_MODEL_ID,
                "machine_proof": readiness.get("machine_proof", {}),
            },
            "shadow_lm_mode": {
                "read_model_id": shadow_lm_mode.READ_MODEL_ID,
                "machine_proof": shadow.get("machine_proof", {}),
            },
            "token_vault_status": {
                "read_model_id": token_vault.READ_MODEL_ID,
                "machine_proof": token_status.get("machine_proof", {}),
            },
            "universal_intake_contract": {
                "read_model_id": universal_intake_contract.READ_MODEL_ID,
                "machine_proof": universal.get("machine_proof", {}),
            },
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "dashboard_aggregates_seeded_lanes": True,
            "lm1_package_built": True,
            "lm1_package_raw_values_included": representative["lm1_thread_context_package"]["raw_values_included"],
            "gate3_tokenization_fields_present": bool(role_package.get("token_vault_ref")),
            "gate3_model_may_see_raw_values": bool(role_package.get("model_may_see_raw_values")),
            "lm1_model_class_selected": representative["lm1_model_decision"]["selected_model_class"],
            "lm2_model_class_selected": representative["lm2_model_decision"]["selected_model_class"],
            "live_lm_status": "NOT_ACTIVE",
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "model_call_performed": False,
            "network_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "production_state_mutation_performed": False,
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
    summary = payload.get("dashboard_summary", {})
    lines = [
        "# LM Readiness Dashboard",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 shadow: {summary.get('lm1_shadow')}",
        f"LM1 live: {summary.get('lm1_live')}",
        f"LM2 package shadow: {summary.get('lm2_package_shadow')}",
        f"LM2 live: {summary.get('lm2_live')}",
        f"Tokenization: {summary.get('tokenization')}",
        f"Gate 2: {summary.get('gate2_ingest')}",
        f"Gate 3: {summary.get('gate3_package')}",
        f"Gate 4: {summary.get('gate4_guardian')}",
        "",
        "This dashboard integrates readiness contracts only. Live LM calls remain off.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export LM readiness dashboard read-model.")
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
                    **payload["dashboard_summary"],
                    "lm1_model_class": payload["machine_proof"]["lm1_model_class_selected"],
                    "lm2_model_class": payload["machine_proof"]["lm2_model_class_selected"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
