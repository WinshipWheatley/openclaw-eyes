"""Self-heal repair doctrine V0.

This module defines the no-black-box repair contract for OpenClaw. It can
diagnose, plan, and stage safe internal repair packages as deterministic
read-model data. It does not execute repairs, restart services, run loops,
invoke LMs, connect local model runtimes, spawn workers, send email, open
browser/Gmail/Coupa, mutate ledgers/workbooks, export PDFs, mark paid, submit
anything, or push git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Self Heal Repair Doctrine.md")

SCHEMA_VERSION = "self_heal_repair_doctrine_v0"
READ_MODEL_ID = "self_heal_repair_doctrine"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "SELF_HEAL_REPAIR_DOCTRINE_READY"
NOT_READY_STATUS = "SELF_HEAL_REPAIR_DOCTRINE_NOT_READY"

REPAIR_PACKAGE_STATES = (
    "detected",
    "diagnosed",
    "repair_plan_ready",
    "safe_internal_repair_ready",
    "operator_action_required",
    "repair_staged",
    "validation_required",
    "validation_passed",
    "validation_failed",
    "receipt_recorded",
    "blocked_by_gate",
)

REPAIR_PACKAGE_FIELDS = (
    "repair_ref",
    "blocker_summary",
    "proof_refs",
    "affected_surface",
    "affected_route",
    "affected_world_thread",
    "severity",
    "safe_internal_actions",
    "forbidden_actions",
    "required_operator_action",
    "validation_plan",
    "rollback_plan",
    "receipt_requirement",
    "dynamic_response_copy",
    "proof_meter_updates",
)

REQUIRED_SCENARIOS = (
    "mac_controller_response_stale_after_lane_switch",
    "evidence_picker_path_leaked_into_composer",
    "excel_export_blocked_by_file_access",
    "remote_desktop_trace_log_leak",
    "missing_proof_for_payment",
)

CORE_DOCTRINE = (
    "If OpenClaw detects a blocker, stale state, failed validation, missing proof, broken route, UI inconsistency, permissions issue, or workflow break, it names the blocker in human language.",
    "Every blocker claim cites the proof/source that proves it.",
    "The response states what OpenClaw can safely do now.",
    "The response states what OpenClaw cannot do yet.",
    "If manual work is unavoidable, the response asks Winship for the smallest required action.",
    "The response produces or points to the next repair/update package.",
    "No repair/update success claim is allowed without validation and receipt.",
)

SOURCE_REFS = {
    "operator_controller_design_brief": "generated/read_models/operator_controller_design_brief.json",
    "proof_to_response": "generated/read_models/proof_to_response_tdd_spec.json",
    "objective_advancement": "generated/read_models/objective_advancement_protocol.json",
    "universal_receipt_contract": "generated/read_models/universal_receipt_envelope_contract.json",
    "dynamic_card_contract": "generated/read_models/dynamic_card_packet_contract.json",
    "dynamic_card_latest": "generated/read_models/dynamic_card_packet_latest.json",
    "proof_meter_normalization": "generated/read_models/proof_meter_normalization.json",
    "operator_controller_router": "generated/read_models/operator_controller_event_router_status.json",
    "workflow_composer": "generated/read_models/workflow_composer_latest.json",
    "evidence_intake": "generated/read_models/evidence_intake_status.json",
    "workbook_registry": "generated/read_models/client_invoice_workbook_registry.json",
    "protected_evidence_receipt": "generated/read_models/protected_evidence_reference_receipt.json",
    "service_keeper": "generated/read_models/openclaw_service_keeper_status.json",
    "sync_health": "generated/read_models/sync_health.json",
    "capital_hilton_run": "generated/read_models/capital_hilton_invoice_operator_run_status.json",
    "gate_decision_ledger": "generated/read_models/gate_decision_ledger.json",
}

PRECONDITIONS = {
    "operator_controller_design_brief": {
        "filename": "operator_controller_design_brief.json",
        "accepted_statuses": ("OPERATOR_CONTROLLER_DESIGN_BRIEF_READY",),
    },
    "proof_to_response_tdd_spec": {
        "filename": "proof_to_response_tdd_spec.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_TDD_SPEC_READY",),
    },
    "objective_advancement_protocol": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ("OBJECTIVE_ADVANCEMENT_PROTOCOL_READY", "OBJECTIVE_ADVANCEMENT_CONTROLLER_ROUTE_READY"),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_contract.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_contract.json",
        "accepted_statuses": ("DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"),
    },
    "proof_meter_normalization": {
        "filename": "proof_meter_normalization.json",
        "accepted_statuses": ("PROOF_METER_NORMALIZATION_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "authority_grant_allowed": False,
    "live_repair_execution_allowed": False,
    "repair_loop_allowed": False,
    "service_restart_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "worker_spawn_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_read_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "file_delete_allowed": False,
    "trace_cleanup_execution_allowed": False,
    "unknown_file_delete_allowed": False,
    "active_file_delete_allowed": False,
    "payment_submission_allowed": False,
    "git_push_allowed": False,
    "external_action_allowed": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "authority_granted",
    "protected_action_performed",
    "repair_executed",
    "repair_loop_started",
    "service_restarted",
    "external_llm_invoked",
    "local_model_runtime_connected",
    "worker_spawn_performed",
    "email_send_performed",
    "gmail_opened",
    "browser_opened",
    "coupa_opened",
    "portal_submit_performed",
    "ledger_mutation_performed",
    "workbook_read_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "file_delete_performed",
    "trace_cleanup_executed",
    "unknown_file_delete_performed",
    "active_file_delete_performed",
    "payment_submission_performed",
    "git_push_performed",
    "success_claim_allowed_without_receipt",
    "success_claimed",
}


@dataclass(frozen=True)
class RepairPackage:
    repair_ref: str
    blocker_summary: str
    proof_refs: tuple[str, ...]
    affected_surface: str
    affected_route: str
    affected_world_thread: str
    severity: str
    safe_internal_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    required_operator_action: dict[str, Any]
    validation_plan: tuple[str, ...]
    rollback_plan: tuple[str, ...]
    receipt_requirement: dict[str, Any]
    dynamic_response_copy: dict[str, Any]
    proof_meter_updates: tuple[dict[str, Any], ...]

    def to_admit_task_kwargs(
        self,
        *,
        acceptance_path: str | Path = "tests/test_pc4_self_healing.py",
        repo_ref: str = "HEAD",
    ) -> dict[str, Any]:
        from polish_loop.pc4_heal_emitter import admit_task_kwargs_for_payload

        payload = {
            "source_surface": self.affected_surface,
            "bad_exchange": {
                "repair_ref": self.repair_ref,
                "summary": self.blocker_summary,
                "dynamic_response_copy": self.dynamic_response_copy,
            },
            "expected_behavior": self.validation_plan[0] if self.validation_plan else self.blocker_summary,
            "truth_inputs": list(self.proof_refs),
            "bounds": {"OPENCLAW_TEST_MODE": "1", "OPENCLAW_SEND_HOLD": "1"},
            "allowed_tools_class": "read_only_readmodels",
            "pii_rules": "no vault, no LegalPrivate, no FinancePrivate, no .chief.env",
            "repro_prompts": [self.blocker_summary],
            "acceptance_tests": [str(acceptance_path)],
            "rollback_no_send": True,
            "agent_id": self.affected_surface,
            "claim_type": "repair_package_validation",
            "claim_value": self.validation_plan[0] if self.validation_plan else self.blocker_summary,
        }
        return admit_task_kwargs_for_payload(payload, acceptance_path=acceptance_path, repo_ref=repo_ref)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _observed_status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        filename = str(contract["filename"])
        accepted = [str(status) for status in contract["accepted_statuses"]]
        observed = _observed_status(_load_json(root / filename))
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


def _operator_action(
    *,
    manual_required: bool,
    smallest_action: str,
    reason: str,
    expected_receipt: str,
) -> dict[str, Any]:
    return {
        "manual_required": manual_required,
        "smallest_action": smallest_action,
        "reason": reason,
        "expected_receipt": expected_receipt,
        "forbidden_broad_ask": (
            "grant broad system authority",
            "provide credentials",
            "give full disk access",
            "approve unrelated cleanup",
            "approve protected business action",
        ),
    }


def _receipt_requirement(*receipt_refs: str) -> dict[str, Any]:
    return {
        "validation_required": True,
        "receipt_required": True,
        "success_claim_allowed_without_receipt": False,
        "success_claim_requires_states": ("validation_passed", "receipt_recorded"),
        "required_receipt_refs": receipt_refs,
        "plain_rule": "Do not claim repair/update success until validation passes and a receipt is recorded.",
    }


def _response_copy(
    *,
    speaker_ref: str,
    headline: str,
    body: str,
    proof_citation: str,
    can_do_now: tuple[str, ...],
    cannot_do_yet: tuple[str, ...],
    required_operator_action: str,
    next_step: str,
    repair_ref: str,
) -> dict[str, Any]:
    return {
        "speaker_ref": speaker_ref,
        "headline": headline,
        "body": body,
        "proof_citation": proof_citation,
        "what_i_can_do_now": can_do_now,
        "what_i_cannot_do_yet": cannot_do_yet,
        "required_operator_action": required_operator_action,
        "next_step": next_step,
        "repair_package_ref": repair_ref,
    }


def _proof_meter(card_id: str, meter_ref: str, meter_state: str, source_ref: str) -> dict[str, Any]:
    return {
        "card_id": card_id,
        "meter_ref": meter_ref,
        "meter_state": meter_state,
        "source_ref": source_ref,
        "opens_details": True,
    }


def _package(state: str, package: RepairPackage) -> dict[str, Any]:
    payload = asdict(package)
    payload["repair_state"] = state
    payload["next_step"] = package.dynamic_response_copy["next_step"]
    payload["authority_boundary"] = dict(AUTHORITY_BOUNDARY)
    return payload


def repair_packages() -> list[dict[str, Any]]:
    stale_ref = "self_heal:mac_controller_response_stale_after_lane_switch"
    picker_ref = "self_heal:evidence_picker_path_leaked_into_composer"
    excel_ref = "self_heal:excel_export_blocked_by_file_access"
    trace_ref = "self_heal:remote_desktop_trace_log_leak"
    payment_ref = "self_heal:missing_proof_for_payment"

    return [
        _package(
            "repair_plan_ready",
            RepairPackage(
                repair_ref=stale_ref,
                blocker_summary="Mac controller response is stale because the request/card scope does not match the active lane.",
                proof_refs=(
                    SOURCE_REFS["operator_controller_design_brief"],
                    SOURCE_REFS["dynamic_card_latest"],
                    SOURCE_REFS["proof_to_response"],
                ),
                affected_surface="Mac controller response surface",
                affected_route="lane_scoped_card_renderer",
                affected_world_thread="build/mac_controller",
                severity="medium",
                safe_internal_actions=(
                    "stage a scoped renderer fix package",
                    "add a lane-scope validation check to the renderer contract",
                    "prepare release validation and smoke-test requirements",
                ),
                forbidden_actions=(
                    "claim the response is fixed before release validation passes",
                    "claim the response is fixed before Mac smoke passes",
                    "rewrite active lane state without a receipt",
                    "restart controller services from doctrine work",
                ),
                required_operator_action=_operator_action(
                    manual_required=False,
                    smallest_action="No manual action is required unless Winship wants to choose a different active lane.",
                    reason="The safe next move is an internal scoped renderer package.",
                    expected_receipt="scoped renderer package receipt plus release validation receipt",
                ),
                validation_plan=(
                    "unit-test stale request/card scope mismatch",
                    "run release validation for the renderer package",
                    "run Mac controller smoke with active lane switch",
                ),
                rollback_plan=(
                    "keep existing renderer active until the scoped package validates",
                    "revert the staged renderer package if smoke fails",
                ),
                receipt_requirement=_receipt_requirement(
                    "receipt:scoped_renderer_package_staged",
                    "receipt:release_validation_passed",
                    "receipt:mac_controller_smoke_passed",
                ),
                dynamic_response_copy=_response_copy(
                    speaker_ref="chief",
                    headline="Mac controller response is stale",
                    body="The request/card scope does not match the active lane, so I can stage a scoped renderer fix but cannot call it fixed yet.",
                    proof_citation=f"Cites {SOURCE_REFS['operator_controller_design_brief']}, {SOURCE_REFS['dynamic_card_latest']}, and {SOURCE_REFS['proof_to_response']}.",
                    can_do_now=("stage a scoped renderer fix", "prepare release validation and smoke checks"),
                    cannot_do_yet=("claim fixed", "rewrite lane state without receipt", "restart services"),
                    required_operator_action="No manual action unless you want a different active lane selected.",
                    next_step="Stage scoped renderer fix",
                    repair_ref=stale_ref,
                ),
                proof_meter_updates=(
                    _proof_meter("self_heal.mac_controller.stale_scope", "truth", "stale_needs_validation", SOURCE_REFS["dynamic_card_latest"]),
                    _proof_meter("self_heal.mac_controller.stale_scope", "authority", "no_grant", SOURCE_REFS["proof_meter_normalization"]),
                    _proof_meter("self_heal.mac_controller.stale_scope", "risk", "watch", SOURCE_REFS["proof_meter_normalization"]),
                ),
            ),
        ),
        _package(
            "safe_internal_repair_ready",
            RepairPackage(
                repair_ref=picker_ref,
                blocker_summary="Evidence picker proof file path was routed as chat input into the workflow composer.",
                proof_refs=(
                    SOURCE_REFS["operator_controller_router"],
                    SOURCE_REFS["evidence_intake"],
                    SOURCE_REFS["workflow_composer"],
                ),
                affected_surface="operator evidence picker and composer",
                affected_route="evidence_picker_to_composer_route",
                affected_world_thread="finance/evidence_intake",
                severity="high",
                safe_internal_actions=(
                    "stage an evidence-picker isolation package",
                    "separate proof path events from composer chat text events",
                    "add a route test proving proof paths cannot become workflow-package prompts",
                ),
                forbidden_actions=(
                    "stage a workflow package from the proof path",
                    "treat the leaked file path as operator chat intent",
                    "read proof file bodies from the leaked path",
                    "submit or send anything from the leaked path",
                ),
                required_operator_action=_operator_action(
                    manual_required=False,
                    smallest_action="No manual action is required; the route isolation package can be staged internally.",
                    reason="The safe fix is an internal event-route boundary package.",
                    expected_receipt="evidence picker isolation package receipt and route test receipt",
                ),
                validation_plan=(
                    "simulate evidence picker path selection",
                    "assert composer receives no chat body from the proof path",
                    "assert evidence intake receives only a proof reference envelope",
                ),
                rollback_plan=(
                    "keep current evidence intake receipt model",
                    "disable only the staged isolation change if route tests fail",
                ),
                receipt_requirement=_receipt_requirement(
                    "receipt:evidence_picker_isolation_package_staged",
                    "receipt:evidence_route_test_passed",
                ),
                dynamic_response_copy=_response_copy(
                    speaker_ref="chief",
                    headline="Proof path leaked into composer",
                    body="The proof file path was routed as chat input. I can stage route isolation, but I cannot build a workflow package from that path.",
                    proof_citation=f"Cites {SOURCE_REFS['operator_controller_router']}, {SOURCE_REFS['evidence_intake']}, and {SOURCE_REFS['workflow_composer']}.",
                    can_do_now=("stage evidence-picker isolation", "add route tests"),
                    cannot_do_yet=("stage a workflow package from the proof path", "read proof file bodies", "submit anything"),
                    required_operator_action="No manual action is required for the internal route isolation package.",
                    next_step="Isolate evidence picker from composer",
                    repair_ref=picker_ref,
                ),
                proof_meter_updates=(
                    _proof_meter("self_heal.evidence_picker.composer_leak", "truth", "trusted_current", SOURCE_REFS["operator_controller_router"]),
                    _proof_meter("self_heal.evidence_picker.composer_leak", "authority", "blocked_gate", SOURCE_REFS["proof_meter_normalization"]),
                    _proof_meter("self_heal.evidence_picker.composer_leak", "risk", "protected", SOURCE_REFS["proof_meter_normalization"]),
                ),
            ),
        ),
        _package(
            "operator_action_required",
            RepairPackage(
                repair_ref=excel_ref,
                blocker_summary="Excel file access is blocked, so workbook cells and PDF export are not available.",
                proof_refs=(
                    SOURCE_REFS["workbook_registry"],
                    SOURCE_REFS["protected_evidence_receipt"],
                    SOURCE_REFS["universal_receipt_contract"],
                ),
                affected_surface="client invoice workbook export",
                affected_route="workbook_reference_to_pdf_export",
                affected_world_thread="finance/client_invoice",
                severity="high",
                safe_internal_actions=(
                    "record the file-access blocker",
                    "prepare an access-proof request for the named workbook",
                    "stage validation that waits for permission proof before any workbook read",
                ),
                forbidden_actions=(
                    "export PDF before file-access proof exists",
                    "read workbook cells before file-access proof exists",
                    "mutate workbook before file-access proof exists",
                    "infer workbook values from filename or stale memory",
                    "mark invoice paid or mutate ledger from this blocker",
                ),
                required_operator_action=_operator_action(
                    manual_required=True,
                    smallest_action="Grant access to the named workbook or choose a different workbook reference.",
                    reason="OpenClaw cannot prove workbook access from the current state.",
                    expected_receipt="file-access proof receipt for the selected workbook reference",
                ),
                validation_plan=(
                    "wait for file-access proof receipt",
                    "validate the selected workbook reference matches the proof",
                    "only after proof, allow a separate export package to validate workbook read and PDF export gates",
                ),
                rollback_plan=(
                    "keep the previous workbook reference unchanged",
                    "discard any staged export package if access proof does not match",
                ),
                receipt_requirement=_receipt_requirement(
                    "receipt:file_access_proof_recorded",
                    "receipt:workbook_reference_validated",
                    "receipt:export_gate_validated",
                ),
                dynamic_response_copy=_response_copy(
                    speaker_ref="chief",
                    headline="Excel file access is blocked",
                    body="I do not have proof that the workbook is accessible. I can record the blocker, but I cannot read cells or export a PDF yet.",
                    proof_citation=f"Cites {SOURCE_REFS['workbook_registry']}, {SOURCE_REFS['protected_evidence_receipt']}, and {SOURCE_REFS['universal_receipt_contract']}.",
                    can_do_now=("record the access blocker", "prepare the workbook access proof request"),
                    cannot_do_yet=("read workbook cells", "export PDF", "mutate workbook", "mark paid"),
                    required_operator_action="Grant access to the named workbook or choose a different workbook reference.",
                    next_step="Provide workbook access proof or choose another workbook",
                    repair_ref=excel_ref,
                ),
                proof_meter_updates=(
                    _proof_meter("self_heal.excel.file_access_blocked", "truth", "needs_verification", SOURCE_REFS["workbook_registry"]),
                    _proof_meter("self_heal.excel.file_access_blocked", "authority", "blocked_gate", SOURCE_REFS["proof_meter_normalization"]),
                    _proof_meter("self_heal.excel.file_access_blocked", "risk", "protected", SOURCE_REFS["proof_meter_normalization"]),
                ),
            ),
        ),
        _package(
            "operator_action_required",
            RepairPackage(
                repair_ref=trace_ref,
                blocker_summary="Remote Desktop trace logs are filling C:, but cleanup must be targeted and receipt-backed.",
                proof_refs=(
                    SOURCE_REFS["service_keeper"],
                    SOURCE_REFS["sync_health"],
                    SOURCE_REFS["universal_receipt_contract"],
                ),
                affected_surface="PC storage and Remote Desktop diagnostics",
                affected_route="rdp_trace_log_cleanup_or_disable_tracing",
                affected_world_thread="system/pc_storage",
                severity="high",
                safe_internal_actions=(
                    "stage an explicit trace-log cleanup package for known inactive trace log paths only",
                    "stage an explicit tracing-disable package if tracing should be turned off",
                    "prepare validation that confirms target paths and free-space receipt",
                ),
                forbidden_actions=(
                    "delete unknown temp files",
                    "delete active trace logs",
                    "delete active swap or vhdx files",
                    "delete files outside the named trace-log target set",
                    "disable tracing without an explicit package and receipt",
                ),
                required_operator_action=_operator_action(
                    manual_required=True,
                    smallest_action="Approve one named trace-log cleanup package or one named tracing-disable package.",
                    reason="Deleting files or changing tracing settings crosses a protected system-change gate.",
                    expected_receipt="targeted cleanup or tracing-disable receipt plus validation receipt",
                ),
                validation_plan=(
                    "inventory only named Remote Desktop trace-log paths",
                    "prove targets are inactive and inside the package target set",
                    "record before/after free-space and tracing-state receipts",
                ),
                rollback_plan=(
                    "do not touch unknown temp files or active swap/vhdx files",
                    "if disable package fails, keep existing tracing state and report validation failure",
                ),
                receipt_requirement=_receipt_requirement(
                    "receipt:rdp_trace_cleanup_package_approved",
                    "receipt:trace_targets_validated_inactive",
                    "receipt:cleanup_or_disable_validation_passed",
                ),
                dynamic_response_copy=_response_copy(
                    speaker_ref="chief",
                    headline="Remote Desktop trace logs are filling C:",
                    body="I can stage a targeted cleanup or tracing-disable package. I cannot delete unknown temp files or active swap/vhdx files.",
                    proof_citation=f"Cites {SOURCE_REFS['service_keeper']}, {SOURCE_REFS['sync_health']}, and {SOURCE_REFS['universal_receipt_contract']}.",
                    can_do_now=("stage targeted trace-log cleanup", "stage tracing-disable package", "prepare validation"),
                    cannot_do_yet=("delete unknown temp files", "delete active swap/vhdx", "change tracing without package receipt"),
                    required_operator_action="Approve one named cleanup package or one named tracing-disable package.",
                    next_step="Choose targeted trace cleanup or disable tracing package",
                    repair_ref=trace_ref,
                ),
                proof_meter_updates=(
                    _proof_meter("self_heal.rdp.trace_log_leak", "truth", "needs_verification", SOURCE_REFS["service_keeper"]),
                    _proof_meter("self_heal.rdp.trace_log_leak", "authority", "blocked_gate", SOURCE_REFS["proof_meter_normalization"]),
                    _proof_meter("self_heal.rdp.trace_log_leak", "risk", "protected", SOURCE_REFS["proof_meter_normalization"]),
                ),
            ),
        ),
        _package(
            "operator_action_required",
            RepairPackage(
                repair_ref=payment_ref,
                blocker_summary="Payment evidence is missing, so paid state and ledger mutation are blocked.",
                proof_refs=(
                    SOURCE_REFS["capital_hilton_run"],
                    SOURCE_REFS["proof_meter_normalization"],
                    SOURCE_REFS["universal_receipt_contract"],
                ),
                affected_surface="finance payment watch",
                affected_route="payment_evidence_to_paid_state",
                affected_world_thread="finance/capital_hilton",
                severity="critical",
                safe_internal_actions=(
                    "keep payment on watch",
                    "prepare an attach-proof request",
                    "show the blocked payment gate",
                ),
                forbidden_actions=(
                    "mark paid without payment evidence",
                    "mutate ledger without payment evidence",
                    "export PDF as a substitute for payment proof",
                    "submit Coupa or send email from missing proof",
                ),
                required_operator_action=_operator_action(
                    manual_required=True,
                    smallest_action="Attach payment evidence.",
                    reason="Guardian/Chief cannot prove paid state without evidence.",
                    expected_receipt="payment evidence receipt bound to the invoice/payment thread",
                ),
                validation_plan=(
                    "validate attached proof is payment evidence",
                    "bind proof to the invoice/payment thread",
                    "only after validation, require a separate receipt for any paid-state or ledger update",
                ),
                rollback_plan=(
                    "leave current payment watch unchanged",
                    "discard any paid-state candidate if proof validation fails",
                ),
                receipt_requirement=_receipt_requirement(
                    "receipt:payment_evidence_attached",
                    "receipt:payment_evidence_validated",
                    "receipt:paid_state_update_if_later_authorized",
                ),
                dynamic_response_copy=_response_copy(
                    speaker_ref="guardian",
                    headline="Payment evidence is missing",
                    body="I can hold the payment watch and ask for proof. I cannot mark paid or touch the ledger until evidence validates.",
                    proof_citation=f"Cites {SOURCE_REFS['capital_hilton_run']}, {SOURCE_REFS['proof_meter_normalization']}, and {SOURCE_REFS['universal_receipt_contract']}.",
                    can_do_now=("hold payment watch", "ask for proof", "show the blocked gate"),
                    cannot_do_yet=("mark paid", "mutate ledger", "submit Coupa", "send email"),
                    required_operator_action="Attach payment evidence.",
                    next_step="Attach payment proof",
                    repair_ref=payment_ref,
                ),
                proof_meter_updates=(
                    _proof_meter("self_heal.payment.missing_proof", "truth", "no_evidence", SOURCE_REFS["capital_hilton_run"]),
                    _proof_meter("self_heal.payment.missing_proof", "authority", "blocked_gate", SOURCE_REFS["proof_meter_normalization"]),
                    _proof_meter("self_heal.payment.missing_proof", "risk", "protected", SOURCE_REFS["proof_meter_normalization"]),
                ),
            ),
        ),
    ]


def package_by_scenario(read_model: Mapping[str, Any], scenario_id: str) -> dict[str, Any]:
    for package in read_model.get("repair_packages") or []:
        if package.get("scenario_id") == scenario_id:
            return dict(package)
    raise KeyError(scenario_id)


def _package_text(package: Mapping[str, Any]) -> str:
    values = [
        package.get("blocker_summary"),
        package.get("next_step"),
        " ".join(str(item) for item in package.get("safe_internal_actions") or []),
        " ".join(str(item) for item in package.get("forbidden_actions") or []),
    ]
    response = package.get("dynamic_response_copy")
    if isinstance(response, Mapping):
        values.extend(str(response.get(key) or "") for key in ("headline", "body", "next_step", "required_operator_action"))
        values.extend(str(item) for item in response.get("what_i_can_do_now") or [])
        values.extend(str(item) for item in response.get("what_i_cannot_do_yet") or [])
    return " ".join(str(value or "") for value in values).lower()


def package_grants_protected_authority(package: Mapping[str, Any]) -> bool:
    boundary = package.get("authority_boundary")
    if isinstance(boundary, Mapping):
        for key, value in boundary.items():
            if (key.endswith("_allowed") or key.endswith("_granted")) and value is not False:
                return True
    return bool(unsafe_true_grants(package))


def manual_action_is_smallest_required(package: Mapping[str, Any]) -> bool:
    action = package.get("required_operator_action")
    if not isinstance(action, Mapping):
        return False
    smallest = str(action.get("smallest_action") or "").lower()
    if not smallest:
        return False
    broad_terms = ("full disk", "admin", "credentials", "all files", "anything", "blanket", "broad authority")
    return not any(term in smallest for term in broad_terms)


def validate_repair_package(package: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REPAIR_PACKAGE_FIELDS:
        if field not in package:
            errors.append(f"missing_field:{field}")
    if package.get("repair_state") not in REPAIR_PACKAGE_STATES:
        errors.append(f"unknown_repair_state:{package.get('repair_state')}")
    for field in ("blocker_summary", "affected_surface", "affected_route", "affected_world_thread", "severity", "next_step"):
        if not str(package.get(field) or ""):
            errors.append(f"empty_field:{field}")
    for field in ("proof_refs", "safe_internal_actions", "forbidden_actions", "validation_plan", "rollback_plan", "proof_meter_updates"):
        value = package.get(field)
        if not isinstance(value, (list, tuple)) or not value:
            errors.append(f"empty_list:{field}")
    response = package.get("dynamic_response_copy")
    if not isinstance(response, Mapping):
        errors.append("dynamic_response_copy_missing")
    else:
        for field in ("headline", "body", "proof_citation", "what_i_can_do_now", "what_i_cannot_do_yet", "required_operator_action", "next_step", "repair_package_ref"):
            if field not in response:
                errors.append(f"dynamic_response_copy_missing:{field}")
        if not response.get("proof_citation"):
            errors.append("dynamic_response_copy_missing:proof_citation")
        if not response.get("what_i_can_do_now"):
            errors.append("dynamic_response_copy_empty:what_i_can_do_now")
        if not response.get("what_i_cannot_do_yet"):
            errors.append("dynamic_response_copy_empty:what_i_cannot_do_yet")
    receipt = package.get("receipt_requirement")
    if not isinstance(receipt, Mapping):
        errors.append("receipt_requirement_missing")
    else:
        if receipt.get("validation_required") is not True:
            errors.append("receipt_requirement_validation_not_required")
        if receipt.get("receipt_required") is not True:
            errors.append("receipt_requirement_receipt_not_required")
        if receipt.get("success_claim_allowed_without_receipt") is not False:
            errors.append("receipt_requirement_allows_success_without_receipt")
        required_states = set(str(item) for item in receipt.get("success_claim_requires_states") or [])
        if not {"validation_passed", "receipt_recorded"}.issubset(required_states):
            errors.append("receipt_requirement_missing_validation_or_receipt_state")
    if not manual_action_is_smallest_required(package):
        errors.append("manual_action_not_smallest_required")
    if package_grants_protected_authority(package):
        errors.append("protected_authority_granted")
    return errors


def excel_blocks_pdf_and_workbook_reads_until_permission_proof(package: Mapping[str, Any]) -> bool:
    text = _package_text(package)
    validation = " ".join(str(item) for item in package.get("validation_plan") or []).lower()
    return (
        "export pdf before file-access proof exists" in text
        and "read workbook cells before file-access proof exists" in text
        and "file-access proof" in validation
    )


def trace_cleanup_does_not_delete_unknown_active_files(package: Mapping[str, Any]) -> bool:
    forbidden = " ".join(str(item) for item in package.get("forbidden_actions") or []).lower()
    safe = " ".join(str(item) for item in package.get("safe_internal_actions") or []).lower()
    return (
        "delete unknown temp files" in forbidden
        and "active swap or vhdx" in forbidden
        and "known inactive trace log paths only" in safe
        and "delete unknown" not in safe
        and "delete active" not in safe
    )


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    packages = repair_packages()
    for scenario_id, package in zip(REQUIRED_SCENARIOS, packages, strict=True):
        package["scenario_id"] = scenario_id
    package_validation_errors: list[str] = []
    for package in packages:
        package_validation_errors.extend(f"{package.get('scenario_id')}:{error}" for error in validate_repair_package(package))

    scenario_ids = {str(package.get("scenario_id")) for package in packages}
    excel = next(package for package in packages if package["scenario_id"] == "excel_export_blocked_by_file_access")
    trace = next(package for package in packages if package["scenario_id"] == "remote_desktop_trace_log_leak")

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "mode": "doctrine_contract_test_only_no_live_repair",
        "repair_package_states": list(REPAIR_PACKAGE_STATES),
        "repair_package_fields": list(REPAIR_PACKAGE_FIELDS),
        "repair_package_schema": {
            "dataclass_fields": [field.name for field in fields(RepairPackage)],
            "state_field": "repair_state",
            "next_step_source": "dynamic_response_copy.next_step",
        },
        "doctrine": list(CORE_DOCTRINE),
        "rules": {
            "self_heal_may_diagnose_and_plan": True,
            "self_heal_may_stage_safe_internal_repair_packages": True,
            "self_heal_cannot_cross_protected_gates": True,
            "manual_work_must_be_plain": True,
            "no_black_box_repair_claims": True,
            "every_fix_requires_validation_and_receipt": True,
            "repair_success_requires_validation_and_receipt": True,
            "smallest_operator_action_only": True,
        },
        "source_refs": dict(SOURCE_REFS),
        "preconditions": preconditions,
        "repair_packages": packages,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": {
            "protected_action_performed": False,
            "repair_executed": False,
            "repair_loop_started": False,
            "service_restarted": False,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "email_send_performed": False,
            "gmail_opened": False,
            "browser_opened": False,
            "coupa_opened": False,
            "portal_submit_performed": False,
            "ledger_mutation_performed": False,
            "workbook_read_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "file_delete_performed": False,
            "trace_cleanup_executed": False,
            "payment_submission_performed": False,
            "git_push_performed": False,
            "success_claimed": False,
        },
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "package_validation_errors": package_validation_errors,
            "scenario_count": len(packages),
            "all_required_scenarios_present": set(REQUIRED_SCENARIOS) == scenario_ids,
            "every_package_has_blocker_proof_safe_forbidden_next_step": all(
                package.get("blocker_summary")
                and package.get("proof_refs")
                and package.get("safe_internal_actions")
                and package.get("forbidden_actions")
                and package.get("next_step")
                for package in packages
            ),
            "manual_work_uses_smallest_required_operator_action": all(manual_action_is_smallest_required(package) for package in packages),
            "no_scenario_grants_protected_authority": not any(package_grants_protected_authority(package) for package in packages),
            "repair_success_requires_validation_and_receipt": all(
                (package.get("receipt_requirement") or {}).get("validation_required") is True
                and (package.get("receipt_requirement") or {}).get("receipt_required") is True
                and (package.get("receipt_requirement") or {}).get("success_claim_allowed_without_receipt") is False
                for package in packages
            ),
            "excel_blocks_pdf_and_workbook_reads_until_permission_proof": excel_blocks_pdf_and_workbook_reads_until_permission_proof(excel),
            "trace_cleanup_does_not_delete_unknown_active_files": trace_cleanup_does_not_delete_unknown_active_files(trace),
            "authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": None,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    if not preconditions_ready or package_validation_errors or unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Self Heal Repair Doctrine",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "Self Heal Repair Doctrine V0 defines how OpenClaw diagnoses blockers, plans safe repairs, stages safe internal packages, and asks Winship only for the smallest required manual action.",
        "",
        "It is doctrine/contract/test work only. It does not execute live repairs.",
        "",
        "## Core Doctrine",
        "",
    ]
    for rule in read_model.get("doctrine") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Repair Package States", ""])
    for state in read_model.get("repair_package_states") or []:
        lines.append(f"- `{state}`")
    lines.extend(["", "## Required Fields", ""])
    for field_name in read_model.get("repair_package_fields") or []:
        lines.append(f"- `{field_name}`")
    lines.extend(["", "## Scenario Contracts", ""])
    for package in read_model.get("repair_packages") or []:
        response = package.get("dynamic_response_copy") if isinstance(package.get("dynamic_response_copy"), Mapping) else {}
        lines.append(
            f"- `{package.get('scenario_id')}`: `{package.get('repair_state')}` - {response.get('headline')} -> {response.get('next_step')}"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Self-heal may diagnose and plan.",
            "- Self-heal may stage safe internal repair packages.",
            "- Self-heal cannot cross protected gates.",
            "- Manual work must be explained plainly.",
            "- No black-box repair claims.",
            "- Every fix requires validation and receipt.",
            "- No live repair execution, repair loops, service restart, worker spawn, model call, email send, browser/Gmail/Coupa opening, ledger/workbook mutation, PDF export, paid marking, submit, push, or protected authority grant.",
            "",
            "## Proof",
            "",
            f"- Preconditions ready: `{str((read_model.get('machine_proof') or {}).get('preconditions_ready')).lower()}`",
            f"- Scenario count: `{(read_model.get('machine_proof') or {}).get('scenario_count')}`",
            f"- Package validation errors: `{len((read_model.get('machine_proof') or {}).get('package_validation_errors') or [])}`",
            f"- Unsafe true grants absent: `{str((read_model.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            f"- Repair success requires validation and receipt: `{str((read_model.get('machine_proof') or {}).get('repair_success_requires_validation_and_receipt')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_self_heal_repair_doctrine(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_path = export_root / JSON_EXPORT_NAME
    _write_json(export_path, read_model)

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root = bridge_export_root if bridge_export_root.is_absolute() else _rooted(bridge_export_root)
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(export_path, bridge)
        bridge_path = bridge.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": export_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "scenario_count": str(read_model["machine_proof"]["scenario_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Self Heal Repair Doctrine V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_self_heal_repair_doctrine(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
