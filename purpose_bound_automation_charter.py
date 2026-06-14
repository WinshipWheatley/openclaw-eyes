"""Purpose-bound automation charter v0.

This deterministic contract narrows automation intent to explicit workflow windows,
explicit data sources, and explicit receipts. It is metadata only: no live
sensing, device access, mailbox polling, invoice generation, ledger mutation,
or production action is performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "purpose_bound_automation_charter_v0"
READ_MODEL_ID = "purpose_bound_automation_charter"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_PURPOSE_BOUND_AUTOMATION_CONTRACT"

REQUIRED_CHARTER_FIELDS = (
    "charter_ref",
    "module_ref",
    "workflow_ref",
    "world_ref",
    "purpose",
    "desired_outcomes",
    "operator_value",
    "default_enabled",
    "activation_condition",
    "observation_window",
    "observation_trigger",
    "data_sources_allowed",
    "sensors_allowed",
    "raw_data_allowed",
    "data_minimization_required",
    "raw_data_retention",
    "derived_proof_retention",
    "proof_receipts",
    "automatic_actions_allowed",
    "approval_required_actions",
    "forbidden_actions",
    "forbidden_inferences",
    "creep_boundary",
    "operator_controls",
    "pause_path",
    "revoke_path",
    "inspect_path",
    "customer_visible_summary",
    "developer_visible_summary",
    "risk_level",
    "privacy_class",
    "access_class_allowed",
    "channel_support",
)

AUTHORITY_BOUNDARY = {
    "location_polling_performed": False,
    "phone_sensor_access_performed": False,
    "email_polling_performed": False,
    "device_network_access_performed": False,
    "device_credential_handoff_performed": False,
    "workbook_cell_read_performed": False,
    "invoice_generation_performed": False,
    "ledger_mutation_performed": False,
    "production_mutation_performed": False,
    "model_call_performed": False,
    "tool_execution_performed": False,
    "agent_activation_performed": False,
    "approval_submission_performed": False,
    "runtime_activation_performed": False,
    "network_access_performed": False,
    "live_model_execution_performed": False,
}

PRIORITY_RAIL_REFS = {
    "workflow_operating_mode_policy": "generated/read_models/workflow_operating_mode_policy.json",
    "operator_work_mode_schema_bandwidth_policy": (
        "generated/read_models/operator_work_mode_schema_bandwidth_policy.json"
    ),
    "hermes_gravity_controller": "generated/read_models/hermes_gravity_controller.json",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, set):
        return tuple(value)
    if isinstance(value, str):
        return (value,)
    return (str(value),)


def _all_authority_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


@dataclass(frozen=True)
class PurposeBoundAutomationCharter:
    charter_ref: str
    module_ref: str
    workflow_ref: str
    world_ref: str
    purpose: str
    desired_outcomes: tuple[str, ...]
    operator_value: str
    default_enabled: bool
    activation_condition: str
    observation_window: str
    observation_trigger: str
    data_sources_allowed: tuple[str, ...]
    sensors_allowed: tuple[str, ...]
    raw_data_allowed: bool
    data_minimization_required: bool
    raw_data_retention: str
    derived_proof_retention: str
    proof_receipts: tuple[str, ...]
    automatic_actions_allowed: tuple[str, ...]
    approval_required_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    forbidden_inferences: tuple[str, ...]
    creep_boundary: str
    operator_controls: tuple[str, ...]
    pause_path: str
    revoke_path: str
    inspect_path: str
    customer_visible_summary: str
    developer_visible_summary: str
    risk_level: str
    privacy_class: str
    access_class_allowed: tuple[str, ...]
    channel_support: tuple[str, ...]


@dataclass(frozen=True)
class PurposeBoundAutomationCharterExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    charter_count: int
    module_count: int
    risk_level_count: int
    authority_boundary_all_false: bool


def _example_charters() -> tuple[PurposeBoundAutomationCharter, ...]:
    return (
        PurposeBoundAutomationCharter(
            charter_ref="charter_gig_manager_v0",
            module_ref="gig_manager",
            workflow_ref="gig_manager_workflow",
            world_ref="operations",
            purpose="Track scheduled gigs, prep requirements, location proof, and invoice readiness.",
            desired_outcomes=(
                "Only check location during scheduled gig windows.",
                "Capture arrival and mileage proof for finance and logistics evidence.",
                "Surface missing-prep steps without exposing unrelated personal patterns.",
            ),
            operator_value="Keep the automation narrow to active gig work.",
            default_enabled=True,
            activation_condition="Calendar event exists and is marked paid, and module is enabled.",
            observation_window="Within each scheduled gig event window only.",
            observation_trigger="Calendar event start and finish for the active gig.",
            data_sources_allowed=("calendar_events", "invoice_state"),
            sensors_allowed=("phone_location_point",),
            raw_data_allowed=False,
            data_minimization_required=True,
            raw_data_retention="No permanent raw GPS retention by default.",
            derived_proof_retention="Keep proof-ready location/time snippets for 18 months minimum.",
            proof_receipts=(
                "gig_window_approval_receipt",
                "location_proof_receipt",
                "mileage_proof_receipt",
            ),
            automatic_actions_allowed=(
                "start_prep_reminders",
                "capture_checkin_checkout_proof",
                "capture_mileage_snippet",
                "mark_invoice_line_candidates_ready",
            ),
            approval_required_actions=(
                "enable_gig_location_tracking_receipt",
                "customer_module_pause_request",
            ),
            forbidden_actions=(
                "all_day_or_continuous_location_tracking",
                "infer_private_life_context",
            ),
            forbidden_inferences=(
                "daily_route patterning outside gig windows",
                "relationship inference outside gig context",
            ),
            creep_boundary="No background geofencing or all-day behavior outside explicit gig windows.",
            operator_controls=("pause", "revoke", "inspect"),
            pause_path="modules/gig_manager/pause_gig_tracking",
            revoke_path="modules/gig_manager/revoke_gig_window_access",
            inspect_path="modules/gig_manager/inspect_gig_window_proof",
            customer_visible_summary="This module checks location only during scheduled gig windows for check-in and mileage proof.",
            developer_visible_summary="Gig automation is event-window-only and proof-gated.",
            risk_level="medium",
            privacy_class="low_private_work_data",
            access_class_allowed=(
                "WINSHIP_DEVELOPER",
                "WINSHIP_OPERATOR",
                "CUSTOMER_OPERATOR",
                "CUSTOMER_ADMIN",
            ),
            channel_support=("APP", "CLI", "TASK_QUEUE"),
        ),
        PurposeBoundAutomationCharter(
            charter_ref="charter_gig_outfit_laundry_v0",
            module_ref="gig_outfit",
            workflow_ref="gig_outfit_workflow",
            world_ref="operations",
            purpose="Prepare stage/gig clothing and keep outfit logistics bounded.",
            desired_outcomes=(
                "Two-day reminder before gigs.",
                "Use integrated washer/dryer state for outfit prep.",
                "Avoid tracking beyond gig prep tasks and workflow scopes.",
            ),
            operator_value="Reduce last-minute misses without turning laundry into profiling.",
            default_enabled=True,
            activation_condition="A workflow has an active gig reference and module is enabled.",
            observation_window="Two-day pre-gig prep lookback and active gig-prep session only.",
            observation_trigger="Active gig-prep workflow step opens.",
            data_sources_allowed=("outfit_task_list", "washer_dryer_integration"),
            sensors_allowed=("outfit_task_state",),
            raw_data_allowed=False,
            data_minimization_required=True,
            raw_data_retention="Keep only task states and state-change timestamps for 30 days.",
            derived_proof_retention="Keep proof references for readiness and invoice traceability.",
            proof_receipts=(
                "outfit_prep_ready_receipt",
                "washer_dryer_state_receipt",
                "task_completion_receipt",
            ),
            automatic_actions_allowed=(
                "send_outfit_reminder",
                "mark_wash_task_ready",
                "request_hang_task_completion",
            ),
            approval_required_actions=(
                "enable_gig_outfit_workflow_receipt",
            ),
            forbidden_actions=(
                "judge_habitual_laundry_patterns",
                "track_clothing_choices_outside_gig_scope",
            ),
            forbidden_inferences=(
                "household_routine_inference",
                "long_term_preference_profileing",
            ),
            creep_boundary="Only outfit tasks tied to a specific gig workflow id.",
            operator_controls=("pause", "revoke", "inspect"),
            pause_path="modules/gig_outfit/pause_outfit_tracking",
            revoke_path="modules/gig_outfit/revoke_outfit_sources",
            inspect_path="modules/gig_outfit/inspect_outfit_readiness",
            customer_visible_summary="This module can remind for wash/dry/hang steps and mark gig clothing as ready.",
            developer_visible_summary="Outfit automation is scoped by workflow and approved integrations only.",
            risk_level="low",
            privacy_class="minimal_private_work_data",
            access_class_allowed=(
                "WINSHIP_DEVELOPER",
                "WINSHIP_OPERATOR",
                "CUSTOMER_OPERATOR",
                "CUSTOMER_ADMIN",
            ),
            channel_support=("APP", "CLI"),
        ),
        PurposeBoundAutomationCharter(
            charter_ref="charter_invoice_manager_v0",
            module_ref="invoice_manager",
            workflow_ref="invoice_manager_workflow",
            world_ref="finance",
            purpose="Generate, send, and watch invoice states with explicit receipts.",
            desired_outcomes=(
                "Track invoice state with scoped thread-safe updates.",
                "Capture payment watch and readiness after send proof.",
                "Keep actions receipt-gated and ledger-safe.",
            ),
            operator_value="Keep billing automation useful and scoped.",
            default_enabled=True,
            activation_condition="Invoice workflow is active and module is enabled.",
            observation_window="Only while invoice workflow steps are active.",
            observation_trigger="Invoice draft and workflow state transitions.",
            data_sources_allowed=("invoice_state", "invoice_thread_state"),
            sensors_allowed=("workflow_state_sensor",),
            raw_data_allowed=False,
            data_minimization_required=True,
            raw_data_retention="Retain workflow proof for audit windows only.",
            derived_proof_retention="Keep invoice proof receipts for 12 months.",
            proof_receipts=(
                "invoice_workflow_receipt",
                "manual_send_proof_receipt",
                "payment_watch_receipt",
            ),
            automatic_actions_allowed=(
                "stage_invoice_for_review",
                "watch_scoped_threads_for_reply",
                "mark_payment_watch_ready",
            ),
            approval_required_actions=(
                "invoice_send_receipt",
                "invoice_ready_receipt",
                "payment_status_receipt",
            ),
            forbidden_actions=(
                "mark_sent_without_receipt",
                "mark_paid_without_receipt",
                "mutate_ledger_silently",
            ),
            forbidden_inferences=(
                "infer_cashflow_capacity_from_unrelated_threads",
                "infer_client_financial_behavior_without_context",
            ),
            creep_boundary="Only scoped invoice data and workflow messages. No general mailbox mining.",
            operator_controls=("pause", "revoke", "inspect"),
            pause_path="modules/invoice_manager/pause_invoice_automation",
            revoke_path="modules/invoice_manager/revoke_invoice_receipt_access",
            inspect_path="modules/invoice_manager/inspect_invoice_receipts",
            customer_visible_summary="This module tracks scoped invoice workflow states and payment watch after proof.",
            developer_visible_summary="No sent/paid mutation without explicit receipts.",
            risk_level="low",
            privacy_class="finance_scope_metadata",
            access_class_allowed=(
                "WINSHIP_DEVELOPER",
                "WINSHIP_OPERATOR",
                "CUSTOMER_OPERATOR",
                "CUSTOMER_ADMIN",
            ),
            channel_support=("APP", "EMAIL", "CLI"),
        ),
        PurposeBoundAutomationCharter(
            charter_ref="charter_client_comms_clara_v0",
            module_ref="client_comms",
            workflow_ref="client_comms_workflow",
            world_ref="client_ops",
            purpose="Draft and respond inside owned client threads while blocking broad inference.",
            desired_outcomes=(
                "Watch only Clara-owned invoice threads.",
                "Draft with guarded pre-send approvals.",
                "Support outside-thread adoption offers without mailbox scans.",
            ),
            operator_value="Keep communication automation scoped to owned threads and explicit approvals.",
            default_enabled=True,
            activation_condition="Clara-owned thread and module enabled.",
            observation_window="Scoped thread-window context only.",
            observation_trigger="Incoming event in Clara-owned scope.",
            data_sources_allowed=("clara_owned_threads", "scoped_message_headers"),
            sensors_allowed=("thread_membership_sensor",),
            raw_data_allowed=False,
            data_minimization_required=True,
            raw_data_retention="Store only scoped headers and proof refs, no full thread bodies by default.",
            derived_proof_retention="Store approvals and thread state receipts for handoff.",
            proof_receipts=(
                "thread_watch_receipt",
                "guardian_approval_receipt",
                "send_readiness_receipt",
            ),
            automatic_actions_allowed=(
                "watch_clara_owned_threads",
                "route_offer_adoption_actions",
                "await_guardian_approval_before_send",
            ),
            approval_required_actions=(
                "guardian_approval",
                "send_approval_receipt",
            ),
            forbidden_actions=(
                "auto_reply_outside_owned_thread",
                "read_all_client_email_as_surveillance",
                "invent_contact_or_sender_data",
            ),
            forbidden_inferences=(
                "general_client_behavior_inference",
                "private_thread_preference_modeling",
            ),
            creep_boundary="Only explicit thread IDs and owned thread members. No full mailbox scans.",
            operator_controls=("pause", "revoke", "inspect"),
            pause_path="modules/client_comms/pause_thread_watch",
            revoke_path="modules/client_comms/revoke_thread_access",
            inspect_path="modules/client_comms/inspect_thread_scope",
            customer_visible_summary="This module watches only the approved Clara-owned threads and asks for approval before sending.",
            developer_visible_summary="Comms automation is limited to explicit ownership plus approvals.",
            risk_level="medium",
            privacy_class="client_ops_thread_scope",
            access_class_allowed=(
                "WINSHIP_DEVELOPER",
                "WINSHIP_OPERATOR",
                "CUSTOMER_OPERATOR",
                "CUSTOMER_ADMIN",
            ),
            channel_support=("APP", "EMAIL", "CLI"),
        ),
        PurposeBoundAutomationCharter(
            charter_ref="charter_phone_location_proof_v0",
            module_ref="phone_location_proof",
            workflow_ref="phone_location_proof_workflow",
            world_ref="operations",
            purpose="Produce arrival and mileage proofs without broad location tracking.",
            desired_outcomes=(
                "Create event-window, purpose-gated location proof.",
                "Store derived proof while minimizing raw telemetry.",
                "Enable manual fallback when proof cannot be produced safely.",
            ),
            operator_value="Protect location utility while preventing hidden tracking.",
            default_enabled=False,
            activation_condition="Gig proof request inside an active event window.",
            observation_window="Declared event/proof window only.",
            observation_trigger="Proof request from explicit proof action.",
            data_sources_allowed=("phone_location", "event_reference"),
            sensors_allowed=("phone_location_point", "location_precision_hint"),
            raw_data_allowed=False,
            data_minimization_required=True,
            raw_data_retention="Raw GPS is opt-in and never retained without explicit proof-mode approval.",
            derived_proof_retention="Keep derived proof token for 7 days and finance review copy for audit window.",
            proof_receipts=(
                "location_purpose_receipt",
                "location_window_receipt",
                "location_retention_receipt",
            ),
            automatic_actions_allowed=(
                "capture_arrival_point",
                "capture_mileage_snippet",
                "emit_proof_receipt",
            ),
            approval_required_actions=(
                "explicit_location_purpose_receipt",
                "explicit_window_receipt",
                "explicit_retention_receipt",
            ),
            forbidden_actions=(
                "continuous_background_location_tracking",
                "unscoped_geofence_recording",
                "customer_mode_hidden_tracking",
            ),
            forbidden_inferences=(
                "home_location_inference",
                "social_patterning_without_invoice_context",
            ),
            creep_boundary="Only with explicit event window + purpose token. No ambient traces.",
            operator_controls=("pause", "revoke", "inspect"),
            pause_path="modules/phone_location_proof/pause_location_proof",
            revoke_path="modules/phone_location_proof/revoke_location_proof_access",
            inspect_path="modules/phone_location_proof/inspect_location_evidence",
            customer_visible_summary="This module uses location for arrival/check-in proof only during declared event windows.",
            developer_visible_summary="No default background tracking. Requires purpose token and retention receipt.",
            risk_level="high",
            privacy_class="sensitive_location_proof",
            access_class_allowed=(
                "WINSHIP_DEVELOPER",
                "WINSHIP_OPERATOR",
                "CUSTOMER_OPERATOR",
                "CUSTOMER_ADMIN",
            ),
            channel_support=("APP", "CLI"),
        ),
        PurposeBoundAutomationCharter(
            charter_ref="charter_washer_dryer_integration_v0",
            module_ref="washer_dryer_integration",
            workflow_ref="washer_dryer_workflow",
            world_ref="ops_devices",
            purpose="Read workflow-owned washer/dryer state through approved integrations only.",
            desired_outcomes=(
                "Use device state only when attached to a recognized workflow.",
                "Keep credentials and integrations explicit.",
                "Do not introduce appliance scanning or unauthorized network behavior.",
            ),
            operator_value="Keep device automation explicit, workflow-owned, and auditable.",
            default_enabled=False,
            activation_condition="Workflow explicitly configures approved integration and owner permissions.",
            observation_window="Active workflow window only.",
            observation_trigger="Gig outfit readiness requests device state.",
            data_sources_allowed=("homekit", "home_assistant", "matter", "manufacturer_api"),
            sensors_allowed=("washer_state", "dryer_state", "cycle_state"),
            raw_data_allowed=False,
            data_minimization_required=True,
            raw_data_retention="Store only state transitions needed for proof; no raw packet capture.",
            derived_proof_retention="Keep proof-ready transitions by configured retention window.",
            proof_receipts=(
                "integration_authorization_receipt",
                "device_read_permission_receipt",
                "workflow_scope_receipt",
            ),
            automatic_actions_allowed=("read_device_state", "wait_for_gig_ready_cycle"),
            approval_required_actions=(
                "approved_integration_receipt",
                "integration_authority_receipt",
            ),
            forbidden_actions=(
                "scrape_private_devices",
                "credential_bypass",
                "network_intrusion",
                "cross_workflow_device_reuse",
            ),
            forbidden_inferences=("household_behavior_profileing", "unowned_device_lifecycle_tracking"),
            creep_boundary="Only approved connectors for configured workflow devices.",
            operator_controls=("pause", "revoke", "inspect"),
            pause_path="modules/washer_dryer_integration/pause_device_read",
            revoke_path="modules/washer_dryer_integration/revoke_device_permissions",
            inspect_path="modules/washer_dryer_integration/inspect_device_source",
            customer_visible_summary="Device state is read only through approved integrations when this workflow is active.",
            developer_visible_summary="No credential bypass, no network intrusion; only approved, scoped integration sources.",
            risk_level="high",
            privacy_class="device_state_scope",
            access_class_allowed=("WINSHIP_DEVELOPER", "WINSHIP_OPERATOR", "CUSTOMER_ADMIN"),
            channel_support=("APP", "CLI"),
        ),
    )


def build_purpose_bound_automation_charter(
    *,
    generated_at: str | None = None,
    charters: tuple[PurposeBoundAutomationCharter, ...] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload_charters = charters if charters is not None else _example_charters()
    charters_by_ref = {charter.charter_ref: asdict(charter) for charter in payload_charters}
    # Keep deterministic, one mapping per module and workflow for lookups.
    charters_by_module = {
        charter.module_ref: charter.charter_ref for charter in payload_charters
    }
    charters_by_workflow = {
        charter.workflow_ref: charter.charter_ref for charter in payload_charters
    }
    risk_levels = sorted({charter.risk_level for charter in payload_charters})
    privacy_classes = sorted({charter.privacy_class for charter in payload_charters})
    access_classes = sorted({access for charter in payload_charters for access in charter.access_class_allowed})

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "charter_rows": tuple(asdict(charter) for charter in payload_charters),
        "machine_proof": {
            "record_count": len(payload_charters),
            "all_authority_flags_false": _all_authority_false(),
            "required_charter_fields_present": all(
                set(REQUIRED_CHARTER_FIELDS) <= set(asdict(charter))
                for charter in payload_charters
            ),
            "has_gig_manager_example": any(
                charter["charter_ref"] == "charter_gig_manager_v0"
                for charter in charters_by_ref.values()
            ),
            "has_gig_outfit_example": any(
                charter["charter_ref"] == "charter_gig_outfit_laundry_v0"
                for charter in charters_by_ref.values()
            ),
            "has_invoice_example": any(
                charter["charter_ref"] == "charter_invoice_manager_v0"
                for charter in charters_by_ref.values()
            ),
            "has_client_comms_example": any(
                charter["charter_ref"] == "charter_client_comms_clara_v0"
                for charter in charters_by_ref.values()
            ),
            "has_phone_location_proof_example": any(
                charter["charter_ref"] == "charter_phone_location_proof_v0"
                for charter in charters_by_ref.values()
            ),
            "has_device_integration_example": any(
                charter["charter_ref"] == "charter_washer_dryer_integration_v0"
                for charter in charters_by_ref.values()
            ),
            "default_on_present": any(charter["default_enabled"] for charter in charters_by_ref.values()),
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "proof_refs": tuple(
                proof
                for row in payload_charters
                for proof in row.proof_receipts
            ),
            "content_hash": None,
        },
        "charters_by_ref": charters_by_ref,
        "charters_by_module": charters_by_module,
        "charters_by_workflow": charters_by_workflow,
        "relationship_to_existing_rails": PRIORITY_RAIL_REFS,
        "required_fields": REQUIRED_CHARTER_FIELDS,
        "required_charter_count": len(REQUIRED_CHARTER_FIELDS),
        "risk_levels": tuple(risk_levels),
        "privacy_classes": tuple(privacy_classes),
        "access_classes": tuple(access_classes),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_purpose_bound_charter(payload: Mapping[str, Any]) -> str:
    charter_rows = payload.get("charter_rows", ())
    default_modules = [
        row["module_ref"] for row in charter_rows if row["default_enabled"] and row["module_ref"]
    ]
    lines = [
        "# Purpose-Bound Automation Charter",
        "",
        "## Evidence:",
        f"- Charter count: `{payload['machine_proof']['record_count']}`",
        f"- High-level risk levels: `{', '.join(payload['risk_levels'])}`",
        f"- Default-on modules: `{', '.join(default_modules) if default_modules else 'none'}`",
        "",
        "## Purpose-bounded contracts:",
    ]
    for row in charter_rows:
        lines.extend(
            [
                "",
                f"### {row['charter_ref']}",
                f"Module/Workflow: `{row['module_ref']}` / `{row['workflow_ref']}`",
                f"Purpose: {row['purpose']}",
                f"Customer summary: {row['customer_visible_summary']}",
                f"Allowed windows: {row['observation_window']}",
                f"Data sources: {', '.join(row['data_sources_allowed']) or 'none'}.",
                f"Sensors: {', '.join(row['sensors_allowed']) or 'none'}.",
                f"Forbidden actions: {', '.join(row['forbidden_actions']) or 'none'}.",
                f"Forbidden inferences: {', '.join(row['forbidden_inferences']) or 'none'}.",
                f"- Required controls: `{', '.join(row['operator_controls'])}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Boundary:",
            "- Contracted paths are metadata only and scope-bound.",
            "- No live location polling, email polling, device intrusion, invoice generation, ledger writes.",
            "- No model/tool/agent/runtime execution is performed in this contract.",
            "- All external actions require receipts and explicit operator controls.",
            "",
            "## Machine proof:",
            f"- All authority flags false: `{str(payload['machine_proof']['all_authority_flags_false']).lower()}`",
            f"- Required fields present: `{str(payload['machine_proof']['required_charter_fields_present']).lower()}`",
            f"- Content hash: `{payload['machine_proof']['content_hash']}`",
            "",
            "## Next safe move:",
            "Keep automation bounded to purpose + workflow scope. Add new charters only by adding explicit examples, receipts, and controls.",
        ]
    )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class PurposeBoundAutomationCharterExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    charter_count: int
    module_count: int
    risk_level_count: int
    authority_boundary_all_false: bool


def export_purpose_bound_automation_charter(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> PurposeBoundAutomationCharterExportResult:
    payload = build_purpose_bound_automation_charter(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root

    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_purpose_bound_charter(payload), encoding="utf-8")

    return PurposeBoundAutomationCharterExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        charter_count=len(payload["charter_rows"]),
        module_count=len(payload["charters_by_module"]),
        risk_level_count=len(payload["risk_levels"]),
        authority_boundary_all_false=payload["machine_proof"]["all_authority_flags_false"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Purpose-Bound Automation Charter read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    parser.add_argument("--generated-at")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_purpose_bound_automation_charter(
        repo_root=args.repo_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    if args.format in {"summary", "json"}:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "charter_count": result.charter_count,
                    "module_count": result.module_count,
                    "risk_level_count": result.risk_level_count,
                    "authority_boundary_all_false": result.authority_boundary_all_false,
                }
            ),
            end="",
        )
    else:
        print("Purpose-Bound Automation Charter exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "CONTRACT_STATUS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "PurposeBoundAutomationCharter",
    "PurposeBoundAutomationCharterExportResult",
    "READ_MODEL_ID",
    "REQUIRED_CHARTER_FIELDS",
    "SCHEMA_VERSION",
    "build_purpose_bound_automation_charter",
    "export_purpose_bound_automation_charter",
    "format_operator_purpose_bound_charter",
    "main",
    "parse_args",
    "stable_json",
]
