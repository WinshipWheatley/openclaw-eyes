"""Hermes purpose-bound gravity controller v0.

This module evaluates proposed capabilities against
`purpose_bound_automation_charter.py` and returns a compact decision shape.
It is deterministic, metadata-only contract logic: no live sensing, no
execution, no polling, and no model/tool/runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import purpose_bound_automation_charter

from purpose_bound_automation_charter import REQUIRED_CHARTER_FIELDS

ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "hermes_gravity_controller_v0"
READ_MODEL_ID = "hermes_gravity_controller"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_PURPOSE_BOUND_GRAVITY_CONTROLLER"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-28T12:00:00+00:00"
DEFAULT_DEADLINE_LOCAL = "2026-05-28T16:00:00-04:00"
LOCAL_TZ = ZoneInfo("America/New_York")

GRAVITY_STATUSES = (
    "PURPOSE_BOUND_OK",
    "NEEDS_NARROWING",
    "NEEDS_OPERATOR_OPT_IN",
    "SURVEILLANCE_RISK",
    "BLOCKED_NO_CLEAR_PURPOSE",
    "CUSTOMER_SAFE",
    "DEVELOPER_ONLY",
)

TIME_CONSTRAINT_STATUSES = (
    "NO_URGENCY",
    "PRESSURE",
    "URGENT",
    "EXPIRED",
)

GRAVITY_DECISION_REQUIRED_FIELDS = (
    "gravity_status",
    "operator_summary",
    "reason_codes",
    "required_scope_limits",
    "required_receipts",
    "required_operator_controls",
    "allowed_default_on",
    "not_allowed_reasons",
    "safer_alternative",
    "proof_refs",
    "time_constraint_status",
    "deadline_local",
    "manual_fallback_required_by",
    "recommended_steel_thread",
    "do_not_spend_time_on",
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

APPROVED_DEVICE_INTEGRATIONS = (
    "homekit",
    "home_assistant",
    "matter",
    "manufacturer_api",
)

VALID_LOCATION_WINDOWS = ("event_window", "event", "window", "gig_window", "scheduled_gig")
LOCATION_REQUEST_KEYWORDS = (
    "location",
    "arrival",
    "checkin",
    "checkout",
    "check-in",
    "mileage",
    "geofence",
    "proof",
    "gps",
    "geo",
)
CONTINUOUS_LOCATION_TERMS = (
    "continuous",
    "all_day",
    "always",
    "always-on",
    "background",
)


@dataclass(frozen=True)
class GravityDecision:
    gravity_status: str
    operator_summary: str
    reason_codes: tuple[str, ...]
    required_scope_limits: tuple[str, ...]
    required_receipts: tuple[str, ...]
    required_operator_controls: tuple[str, ...]
    allowed_default_on: bool
    not_allowed_reasons: tuple[str, ...]
    safer_alternative: str
    proof_refs: tuple[str, ...]
    time_constraint_status: str
    deadline_local: str | None
    manual_fallback_required_by: str | None
    recommended_steel_thread: str
    do_not_spend_time_on: tuple[str, ...]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n"


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _to_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(_as_str(item) for item in value)
    if isinstance(value, list):
        return tuple(_as_str(item) for item in value)
    return (_as_str(value),)


def _as_str(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _as_lower(value: object) -> str:
    return _as_str(value).strip().lower()


def _all_authority_false() -> bool:
    return all(v is False for v in AUTHORITY_BOUNDARY.values())


def _merge_unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _dedupe(values: list[str] | tuple[str, ...], *, preserve_case: bool = True) -> tuple[str, ...]:
    if preserve_case:
        return tuple(dict.fromkeys(values))
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = _as_lower(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(_as_str(value))
    return tuple(out)


def _parse_time(value: str, default_tz: ZoneInfo = LOCAL_TZ) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(default_tz)


def _time_constraint(*, generated_at: str, deadline_local: str | None) -> dict[str, Any]:
    if not deadline_local:
        return {
            "status": "NO_URGENCY",
            "deadline_local": None,
            "manual_fallback_required_by": None,
            "recommended_steel_thread": (
                "Use a short steel-thread implementation only: default-on toggle, receipts, and explicit stop conditions."
            ),
            "do_not_spend_time_on": (
                "new integrations",
                "non-critical refactors",
                "bigger architecture churn",
            ),
        }

    now = _parse_time(generated_at)
    deadline = _parse_time(deadline_local)
    remaining_minutes = int((deadline - now).total_seconds() // 60)

    if remaining_minutes <= 0:
        return {
            "status": "EXPIRED",
            "deadline_local": deadline.isoformat(),
            "manual_fallback_required_by": deadline.isoformat(),
            "recommended_steel_thread": (
                "Do not continue automation. Run manual fallback with proof capture and record outcomes."
            ),
            "do_not_spend_time_on": (
                "new modules",
                "non-critical workflow expansion",
                "research or broad refactoring",
            ),
        }
    if remaining_minutes <= 15:
        fallback = (deadline - timedelta(minutes=5)).isoformat()
        return {
            "status": "URGENT",
            "deadline_local": deadline.isoformat(),
            "manual_fallback_required_by": fallback,
            "recommended_steel_thread": (
                "Only execute critical-path proof work and ask for manual fallback before expiry."
            ),
            "do_not_spend_time_on": (
                "nice-to-have tracking",
                "new connector exploration",
                "additional data collection",
                "non-critical schema expansion",
            ),
        }
    if remaining_minutes <= 45:
        fallback = (deadline - timedelta(minutes=20)).isoformat()
        return {
            "status": "PRESSURE",
            "deadline_local": deadline.isoformat(),
            "manual_fallback_required_by": fallback,
            "recommended_steel_thread": (
                "Keep to critical path and a minimal steel thread. Pause at first new-risk signal."
            ),
            "do_not_spend_time_on": (
                "new telemetry surfaces",
                "large refactors",
                "non-blocking UX cleanup",
            ),
        }
    return {
        "status": "NO_URGENCY",
        "deadline_local": deadline.isoformat(),
        "manual_fallback_required_by": None,
        "recommended_steel_thread": (
            "Use on/off scoped controls and a tiny safe default with explicit receipts."
        ),
        "do_not_spend_time_on": (
            "new dashboards",
            "bigger architecture changes",
            "unbounded polling",
        ),
    }


def _load_charters() -> tuple[Mapping[str, Any], ...]:
    payload = purpose_bound_automation_charter.build_purpose_bound_automation_charter()
    return tuple(payload["charter_rows"])


def _find_charter(
    *,
    module_ref: str | None,
    workflow_ref: str | None,
    charters: tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any] | None:
    module_ref = _as_lower(module_ref)
    workflow_ref = _as_lower(workflow_ref)
    if module_ref:
        for row in charters:
            if _as_lower(row["module_ref"]) == module_ref:
                return row
    if workflow_ref:
        for row in charters:
            if _as_lower(row["workflow_ref"]) == workflow_ref:
                return row
    return None


def _is_continuous_location_request(action: str, observation_window: str) -> bool:
    action = _as_lower(action)
    window = _as_lower(observation_window)
    return any(term in action for term in CONTINUOUS_LOCATION_TERMS) or any(
        term in window for term in CONTINUOUS_LOCATION_TERMS
    )


def _is_location_action(action: str) -> bool:
    action = _as_lower(action)
    return any(term in action for term in LOCATION_REQUEST_KEYWORDS)


def _is_all_email_read(action: str, data_sources: tuple[str, ...], thread_scope: str | None) -> bool:
    action = _as_lower(action)
    thread_scope = _as_lower(thread_scope)
    sources = tuple(_as_lower(item) for item in data_sources)
    if "all" in action and ("email" in action or "mail" in action) and "read" in action:
        return True
    if "read_all" in action and "thread" in action:
        return True
    if any(item in ("read_all", "all_email", "all_client_email") for item in sources):
        return True
    return bool("all_email" in thread_scope or "all_client" in thread_scope)


def _is_clara_owned_thread(thread_scope: str | None, thread_owner: str | None) -> bool:
    return (
        _as_lower(thread_scope) == "clara_owned"
        or "clara_owned" in _as_lower(thread_scope)
        or _as_lower(thread_owner) == "clara"
    )


def _safer_alternative(action: str, status: str, module_ref: str) -> str:
    action = _as_lower(action)
    module_ref = _as_lower(module_ref)
    if status == "SURVEILLANCE_RISK":
        if module_ref in {"gig_manager", "phone_location_proof"} and _is_location_action(action):
            return (
                "Use an event-window location request only during the declared gig/proof window and "
                "do not retain raw GPS outside that window."
            )
        if module_ref == "client_comms" and ("email" in action or "thread" in action):
            return "Watch only Clara-owned thread IDs and collect only scope-specific headers/receipts."
        return (
            "Narrow this capability to a single declared module, workflow, and allowed data source."
        )
    if status == "NEEDS_NARROWING":
        if module_ref == "gig_outfit":
            return "Limit to gig-ready tasks and explicit reminder/task actions."
        if module_ref == "washer_dryer_integration":
            return "Use only approved washer/dryer integrations tied to the configured module scope."
        if module_ref == "invoice_manager":
            return "Restrict invoice automation to scoped workflow threads and required receipts."
        return "Declare the action in a module purpose charter and require explicit receipts."
    if status == "NEEDS_OPERATOR_OPT_IN":
        if module_ref == "washer_dryer_integration":
            return (
                "Use only official integration paths and keep device reads behind an approval receipt."
            )
        if module_ref == "phone_location_proof":
            return (
                "Require explicit purpose, event window, and raw retention minimization approvals."
            )
        return "Use the operator opt-in path for this action before activation."
    return ""


def _status_priority(status: str) -> int:
    order = {
        "PURPOSE_BOUND_OK": 0,
        "CUSTOMER_SAFE": 0,
        "NEEDS_NARROWING": 1,
        "NEEDS_OPERATOR_OPT_IN": 2,
        "SURVEILLANCE_RISK": 3,
        "DEVELOPER_ONLY": 4,
        "BLOCKED_NO_CLEAR_PURPOSE": 5,
    }
    return order.get(status, 10)


def _better_status(*, current: str, candidate: str) -> str:
    if _status_priority(candidate) > _status_priority(current):
        return candidate
    return current


def _summary_for_customer(
    *, module_summary: str, controls: tuple[str, ...], status: str
) -> str:
    label_map = {"pause": "Pause", "revoke": "Turn off", "inspect": "Inspect"}
    control_copy = " ".join(label_map.get(action, action.title()) for action in controls)
    if not control_copy:
        control_copy = "Pause Inspect Turn off"
    if "pause" not in _as_lower(control_copy):
        control_copy = f"{control_copy} Pause Inspect Turn off"
    summary = f"{module_summary} {control_copy}."
    if status == "SURVEILLANCE_RISK":
        summary += " This request is currently narrowed for safety."
    return summary


def _summary_for_operator(
    *, charter_ref: str, status: str, reason_codes: tuple[str, ...], reason_lines: tuple[str, ...]
) -> str:
    reason_sentence = "; ".join(reason_lines) if reason_lines else "meets current scope checks"
    return (
        f"{charter_ref}: status={status}. Decision rationale: {reason_sentence}. "
        f"Reason codes: {', '.join(reason_codes) if reason_codes else 'none'}."
    )


def _evaluate_charter(
    proposal: Mapping[str, Any],
    charter: Mapping[str, Any],
    access_class: str,
    time_limit: Mapping[str, Any],
    is_customer: bool,
) -> GravityDecision:
    action = _as_lower(proposal.get("action"))
    purpose = _as_lower(proposal.get("purpose"))
    observation_window = _as_lower(proposal.get("observation_window"))
    raw_data_retention = _as_lower(proposal.get("raw_data_retention"))
    module_enabled = bool(proposal.get("module_enabled"))
    data_sources = _to_tuple(proposal.get("data_sources"))
    thread_scope = _as_lower(proposal.get("thread_scope"))
    thread_owner = _as_lower(proposal.get("thread_owner"))
    integration_source = _as_lower(proposal.get("integration_source"))
    module_ref = _as_lower(charter["module_ref"])
    status = "PURPOSE_BOUND_OK"
    reason_codes: list[str] = []
    reason_lines: list[str] = []
    required_scope_limits: list[str] = [
        "module_or_workflow_match",
        f"access_class={access_class}",
    ]
    required_receipts: list[str] = list(_to_tuple(charter["proof_receipts"]))
    required_controls = list(_to_tuple(charter["operator_controls"]))
    not_allowed: list[str] = []

    if access_class not in tuple(_as_upper for _as_upper in [a.upper() for a in _to_tuple(charter["access_class_allowed"])]):
        status = _better_status(current=status, candidate="DEVELOPER_ONLY")
        reason_codes.append("ACCESS_CLASS_RESTRICTED")
        reason_lines.append("Access class cannot use this module in current mode.")
        required_scope_limits.append("access_class_upgrade_required")
        required_receipts.append("access_upgrade_or_admin_receipt")
        not_allowed.append("This capability is restricted to higher-privilege runtime modes.")

    if module_enabled is False and _as_lower(str(charter["default_enabled"])) == "true":
        status = _better_status(current=status, candidate="NEEDS_OPERATOR_OPT_IN")
        reason_codes.append("MODULE_NOT_ENABLED")
        required_scope_limits.append("module_enabled_required")
        required_controls.append("pause")
        not_allowed.append("Default-on module is disabled.")
        required_receipts.append("module_enable_receipt")

    if module_ref in {"gig_manager", "phone_location_proof"} and _is_location_action(action):
        if _is_continuous_location_request(action=action, observation_window=observation_window):
            status = _better_status(current=status, candidate="SURVEILLANCE_RISK")
            reason_codes.append("CONTINUOUS_LOCATION_TRACKING")
            reason_lines.append("Continuous or background location tracking is disallowed by default.")
            required_scope_limits.append("event_window_required")
            required_scope_limits.append("raw_data_minimization_required")
            not_allowed.append("Raw continuous location is not permitted.")
            if module_ref == "gig_manager":
                reason_codes.append("LOCATION_WINDOW_MUST_BE_DECLARED")
                reason_lines.append("Location work must be constrained to the gig event window.")
                required_scope_limits.append("declared_gig_window_required")
                not_allowed.append("Location work outside declared window is blocked.")
        elif module_ref == "gig_manager" and observation_window not in VALID_LOCATION_WINDOWS:
            status = _better_status(current=status, candidate="NEEDS_NARROWING")
            reason_codes.append("LOCATION_WINDOW_MUST_BE_DECLARED")
            reason_lines.append("Location work must be constrained to the gig event window.")
            required_scope_limits.append("declared_gig_window_required")
            not_allowed.append("Location work outside declared window is blocked.")
        elif module_ref == "phone_location_proof":
            if not purpose:
                status = _better_status(current=status, candidate="NEEDS_OPERATOR_OPT_IN")
                reason_codes.append("MISSING_LOCATION_PURPOSE")
                reason_lines.append("Purpose must be explicit for phone location proof.")
                required_scope_limits.append("location_purpose_required")
                not_allowed.append("No location purpose specified.")
            if not observation_window:
                status = _better_status(current=status, candidate="NEEDS_OPERATOR_OPT_IN")
                reason_codes.append("MISSING_LOCATION_WINDOW")
                reason_lines.append("Phone proof requests require a declared window.")
                required_scope_limits.append("location_window_required")
                not_allowed.append("No declared proof window supplied.")
            if not raw_data_retention or raw_data_retention in {"", "true", "on", "yes", "full"}:
                status = _better_status(current=status, candidate="NEEDS_OPERATOR_OPT_IN")
                reason_codes.append("MISSING_RAW_RETENTION_CONTROL")
                reason_lines.append("Raw location retention policy must be minimized.")
                required_scope_limits.append("raw_data_minimization_required")
                not_allowed.append("Raw retention policy must be explicit and minimized.")
                required_receipts.append("location_retention_receipt")

    if module_ref == "washer_dryer_integration":
        if not integration_source:
            status = _better_status(current=status, candidate="NEEDS_OPERATOR_OPT_IN")
            reason_codes.append("NO_INTEGRATION_SOURCE")
            reason_lines.append("Device reads require an approved integration source.")
            required_scope_limits.append("approved_integration_required")
            required_receipts.append("integration_authorization_receipt")
            not_allowed.append("No device integration path supplied.")
        elif integration_source not in APPROVED_DEVICE_INTEGRATIONS:
            status = _better_status(current=status, candidate="NEEDS_OPERATOR_OPT_IN")
            reason_codes.append("UNAPPROVED_INTEGRATION_PATH")
            reason_lines.append("Only approved integration channels are allowed.")
            required_scope_limits.append("integration_whitelist_required")
            required_receipts.append("approved_integration_receipt")
            not_allowed.append("Unapproved integration path blocked.")

    if module_ref == "client_comms":
        if _is_all_email_read(action=action, data_sources=data_sources, thread_scope=thread_scope):
            if _is_clara_owned_thread(thread_scope=thread_scope, thread_owner=thread_owner):
                status = _better_status(current=status, candidate="PURPOSE_BOUND_OK")
            else:
                status = _better_status(current=status, candidate="NEEDS_NARROWING")
                reason_codes.append("UNOWNED_EMAIL_SURVEILLANCE")
                reason_lines.append("Email reads must be restricted to Clara-owned threads.")
                required_scope_limits.append("thread_scope_required")
                required_scope_limits.append("clara_owned_filter_required")
                not_allowed.append("General inbox watching is blocked.")
                required_receipts.append("thread_watch_receipt")
        if action and action not in set(_to_tuple(charter["automatic_actions_allowed"])) and (
            "watch_clara_owned_threads" in action or "thread" in action
        ):
            status = _better_status(current=status, candidate="NEEDS_NARROWING")
            reason_codes.append("UNDECLARED_THREAD_ACTION")
            reason_lines.append("Thread watch action not declared in charter.")
            required_scope_limits.append("declared_action_required")

    automatic_actions = set(_to_tuple(charter["automatic_actions_allowed"]))
    approval_actions = set(_to_tuple(charter["approval_required_actions"]))
    forbidden_actions = set(_to_tuple(charter["forbidden_actions"]))
    if action:
        if action in forbidden_actions:
            status = _better_status(current=status, candidate="SURVEILLANCE_RISK")
            reason_codes.append("FORBIDDEN_ACTION")
            reason_lines.append("Action is forbidden by the module charter.")
            not_allowed.append("Forbidden action currently blocked.")
            required_receipts.append("charter_violation_receipt")
        elif action not in automatic_actions:
            if action in approval_actions:
                status = _better_status(current=status, candidate="NEEDS_OPERATOR_OPT_IN")
                reason_codes.append("ACTION_REQUIRES_OPT_IN")
                reason_lines.append("Action requires explicit operator opt-in.")
                required_scope_limits.append("action_receipt_required")
                required_receipts.append("action_opt_in_receipt")
                required_controls.append("pause")
            elif module_ref in {"invoice_manager", "client_comms", "washer_dryer_integration", "gig_outfit", "gig_manager"}:
                status = _better_status(current=status, candidate="NEEDS_NARROWING")
                reason_codes.append("UNDECLARED_ACTION")
                reason_lines.append("Action is not declared in this charter.")
                required_scope_limits.append("action_declared_in_charter")
                not_allowed.append("Only declared charter actions are allowed.")

    if status == "PURPOSE_BOUND_OK" and action and action not in automatic_actions:
        required_scope_limits.append("declared_action_required")

    if status == "SURVEILLANCE_RISK":
        required_scope_limits.append("operator_in_loop_required")
        required_controls.append("inspect")

    allowed_default_on = bool(module_enabled and bool(charter["default_enabled"]))
    required_controls = _dedupe(required_controls)

    required_receipts = _merge_unique(required_receipts + [
        f"{_as_lower(module_ref)}_charter_receipt",
    ])

    if status in {"NEEDS_NARROWING", "NEEDS_OPERATOR_OPT_IN", "SURVEILLANCE_RISK"}:
        required_receipts = _merge_unique(required_receipts + (f"{_as_lower(module_ref)}_review_receipt",))
        reason_lines = [line for line in reason_lines if line]
    if status == "PURPOSE_BOUND_OK":
        not_allowed.append("None")
    elif not not_allowed:
        not_allowed.append("Action blocked by governance policy.")

    if module_ref == "gig_outfit" and any(
        token in action for token in ("laundry", "habit", "pattern")
    ):
        status = _better_status(current=status, candidate="NEEDS_NARROWING")
        reason_codes.append("GIG_OUTFIT_SURVEILLANCE")
        reason_lines.append("Laundry preference/ patterning is outside gig-only scope.")
        required_scope_limits.append("gig_task_scope_only")
        if "Only declared charter actions are allowed." not in not_allowed:
            not_allowed.append("Only declared charter actions are allowed.")
        if "gig_task_scope_only" not in required_scope_limits:
            required_scope_limits.append("gig_task_scope_only")

    summary_source = _as_str(charter["customer_visible_summary" if is_customer else "developer_visible_summary"])
    if is_customer:
        operator_summary = _summary_for_customer(
            module_summary=summary_source,
            controls=required_controls,
            status=status if status != "PURPOSE_BOUND_OK" else "CUSTOMER_SAFE",
        )
    else:
        operator_summary = _summary_for_operator(
            charter_ref=_as_str(charter["charter_ref"]),
            status="CUSTOMER_SAFE" if status == "PURPOSE_BOUND_OK" and _as_lower(access_class).startswith("customer") else status,
            reason_codes=_dedupe(reason_codes),
            reason_lines=_dedupe(reason_lines),
        )

    customer_status = "CUSTOMER_SAFE" if is_customer and status == "PURPOSE_BOUND_OK" else status
    if is_customer and status == "PURPOSE_BOUND_OK":
        status = "CUSTOMER_SAFE"

    return GravityDecision(
        gravity_status=status if not is_customer else customer_status,
        operator_summary=operator_summary,
        reason_codes=_dedupe(reason_codes),
        required_scope_limits=_merge_unique(required_scope_limits),
        required_receipts=_dedupe(required_receipts),
        required_operator_controls=required_controls,
        allowed_default_on=allowed_default_on,
        not_allowed_reasons=_merge_unique(not_allowed),
        safer_alternative=_safer_alternative(
            action=action,
            status=status if status != "CUSTOMER_SAFE" else "PURPOSE_BOUND_OK",
            module_ref=module_ref,
        ),
        proof_refs=(
            "generated/read_models/purpose_bound_automation_charter.json",
        ),
        time_constraint_status=time_limit["status"],
        deadline_local=time_limit["deadline_local"],
        manual_fallback_required_by=time_limit["manual_fallback_required_by"],
        recommended_steel_thread=time_limit["recommended_steel_thread"],
        do_not_spend_time_on=time_limit["do_not_spend_time_on"],
    )


def evaluate_purpose_bound_capability(
    proposal: Mapping[str, Any],
    *,
    access_class: str = "WINSHIP_DEVELOPER",
    generated_at: str | None = None,
    deadline_local: str | None = None,
    charters: tuple[Mapping[str, Any], ...] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    access_class = _as_lower(access_class).upper()
    is_customer = access_class.startswith("CUSTOMER_")
    proposal = dict(proposal)
    module_ref = _as_lower(proposal.get("module_ref"))
    workflow_ref = _as_lower(proposal.get("workflow_ref"))
    action = _as_lower(proposal.get("action"))
    if not deadline_local:
        deadline_local = DEFAULT_DEADLINE_LOCAL

    time_limit = _time_constraint(generated_at=generated_at, deadline_local=deadline_local)
    rows = charters or _load_charters()
    charter = _find_charter(
        module_ref=module_ref,
        workflow_ref=workflow_ref,
        charters=rows,
    )

    if not module_ref and not workflow_ref and not action:
        decision = GravityDecision(
            gravity_status="BLOCKED_NO_CLEAR_PURPOSE",
            operator_summary="Provide module_ref, workflow_ref, or explicit action to evaluate a proposal.",
            reason_codes=("NO_CONTEXT",),
            required_scope_limits=("module_or_workflow", "action"),
            required_receipts=("purpose_bound_charter_reference_required",),
            required_operator_controls=("pause", "revoke", "inspect"),
            allowed_default_on=False,
            not_allowed_reasons=("Missing module/workflow/action context."),
            safer_alternative="Submit proposal context so the decision can match a declared charter.",
            proof_refs=("generated/read_models/purpose_bound_automation_charter.json",),
            time_constraint_status=time_limit["status"],
            deadline_local=time_limit["deadline_local"],
            manual_fallback_required_by=time_limit["manual_fallback_required_by"],
            recommended_steel_thread=time_limit["recommended_steel_thread"],
            do_not_spend_time_on=time_limit["do_not_spend_time_on"],
        )
        return decision.__dict__

    if charter is None:
        decision = GravityDecision(
            gravity_status="BLOCKED_NO_CLEAR_PURPOSE",
            operator_summary="No purpose-bound charter matches this module/workflow.",
            reason_codes=("NO_CHARTER_MATCH",),
            required_scope_limits=("module_or_workflow",),
            required_receipts=("purpose_bound_charter_reference_required",),
            required_operator_controls=("pause", "inspect"),
            allowed_default_on=False,
            not_allowed_reasons=("Cannot map proposal to declared purpose-bounded scope."),
            safer_alternative="Attach this action to one of the declared charters or create a new explicit charter.",
            proof_refs=("generated/read_models/purpose_bound_automation_charter.json",),
            time_constraint_status=time_limit["status"],
            deadline_local=time_limit["deadline_local"],
            manual_fallback_required_by=time_limit["manual_fallback_required_by"],
            recommended_steel_thread=time_limit["recommended_steel_thread"],
            do_not_spend_time_on=time_limit["do_not_spend_time_on"],
        )
        return decision.__dict__

    decision = _evaluate_charter(
        proposal=proposal,
        charter=charter,
        access_class=access_class,
        time_limit=time_limit,
        is_customer=is_customer,
    )

    return decision.__dict__


def _lookup_stats(charters: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    modules = sorted({_as_lower(row["module_ref"]) for row in charters})
    workflows = sorted({_as_lower(row["workflow_ref"]) for row in charters})
    return {
        "charter_count": len(charters),
        "module_count": len(modules),
        "workflow_count": len(workflows),
        "modules": tuple(modules),
        "workflows": tuple(workflows),
        "references": (
            "generated/read_models/purpose_bound_automation_charter.json",
            "generated/read_models/workflow_operating_mode_policy.json",
        ),
    }


def _example_decisions(*, generated_at: str, deadline_local: str) -> tuple[dict[str, Any], ...]:
    return (
        evaluate_purpose_bound_capability(
            {
                "module_ref": "gig_manager",
                "workflow_ref": "gig_manager_workflow",
                "action": "capture_checkin_checkout_proof",
                "purpose": "scheduled_gig_arrival_proof",
                "observation_window": "event_window",
                "raw_data_retention": "none",
                "module_enabled": True,
            },
            access_class="WINSHIP_DEVELOPER",
            generated_at=generated_at,
            deadline_local=deadline_local,
        ),
        evaluate_purpose_bound_capability(
            {
                "module_ref": "gig_manager",
                "workflow_ref": "gig_manager_workflow",
                "action": "continuous_location_tracking",
                "observation_window": "all_day",
                "purpose": "gig_tracking",
                "module_enabled": True,
            },
            access_class="WINSHIP_DEVELOPER",
            generated_at=generated_at,
            deadline_local=deadline_local,
        ),
        evaluate_purpose_bound_capability(
            {
                "module_ref": "gig_outfit",
                "workflow_ref": "gig_outfit_workflow",
                "action": "send_outfit_reminder",
                "module_enabled": True,
            },
            access_class="WINSHIP_DEVELOPER",
            generated_at=generated_at,
            deadline_local=deadline_local,
        ),
        evaluate_purpose_bound_capability(
            {
                "module_ref": "client_comms",
                "workflow_ref": "client_comms_workflow",
                "action": "watch_clara_owned_threads",
                "thread_scope": "clara_owned",
                "thread_owner": "Clara",
                "module_enabled": True,
            },
            access_class="CUSTOMER_OPERATOR",
            generated_at=generated_at,
            deadline_local=deadline_local,
        ),
        evaluate_purpose_bound_capability(
            {
                "module_ref": "client_comms",
                "workflow_ref": "client_comms_workflow",
                "action": "read_all_client_email",
                "module_enabled": True,
            },
            access_class="WINSHIP_DEVELOPER",
            generated_at=generated_at,
            deadline_local=deadline_local,
        ),
        evaluate_purpose_bound_capability(
            {
                "module_ref": "phone_location_proof",
                "workflow_ref": "phone_location_proof_workflow",
                "action": "capture_arrival_point",
                "module_enabled": True,
            },
            access_class="WINSHIP_DEVELOPER",
            generated_at=generated_at,
            deadline_local=deadline_local,
        ),
        evaluate_purpose_bound_capability(
            {
                "module_ref": "washer_dryer_integration",
                "workflow_ref": "washer_dryer_workflow",
                "action": "read_device_state",
                "integration_source": "scraper",
                "module_enabled": True,
            },
            access_class="WINSHIP_DEVELOPER",
            generated_at=generated_at,
            deadline_local=deadline_local,
        ),
    )


def build_hermes_gravity_controller(
    *,
    generated_at: str | None = None,
    deadline_local: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    deadline_local = deadline_local or DEFAULT_DEADLINE_LOCAL
    charters = _load_charters()
    time_limit = _time_constraint(generated_at=generated_at, deadline_local=deadline_local)
    lookup = _lookup_stats(charters)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "deadline_local": deadline_local,
        "gravity_statuses": tuple(GRAVITY_STATUSES),
        "time_constraint_statuses": tuple(TIME_CONSTRAINT_STATUSES),
        "required_model_fields": tuple(REQUIRED_CHARTER_FIELDS),
        "required_decision_fields": tuple(GRAVITY_DECISION_REQUIRED_FIELDS),
        "charter_lookup": lookup,
        "time_constraint": {
            "status": time_limit["status"],
            "deadline_local": time_limit["deadline_local"],
            "manual_fallback_required_by": time_limit["manual_fallback_required_by"],
            "recommended_steel_thread": time_limit["recommended_steel_thread"],
            "do_not_spend_time_on": time_limit["do_not_spend_time_on"],
        },
        "example_decisions": _example_decisions(generated_at=generated_at, deadline_local=deadline_local),
        "proof_refs": (
            "generated/read_models/purpose_bound_automation_charter.json",
            "generated/read_models/workflow_operating_mode_policy.json",
            "generated/read_models/operator_work_mode_schema_bandwidth_policy.json",
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "read_model_only": True,
            "all_authority_flags_false": _all_authority_false(),
            "samples_total": len(lookup["modules"]),
            "example_count": 7,
            "time_constraint_status": time_limit["status"],
            "content_hash": None,
        },
        "operator_summary": {
            "developer_view": "Hermes evaluates purpose-bound capability proposals and returns narrowness, risks, and receipts.",
            "customer_view": "Hermes shows module purpose and controls for approved scopes only.",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_hermes_gravity_controller(payload: Mapping[str, Any]) -> str:
    proof = payload["machine_proof"]
    lines = [
        "# Hermes Gravity Controller v0",
        "",
        "## Evidence:",
        f"- Gravity status set: `{', '.join(payload['gravity_statuses'])}`",
        f"- Time constraint status: `{payload['time_constraint']['status']}`",
        f"- Samples: `{proof['samples_total']}` example decisions.",
        f"- Example count: `{proof['example_count']}`",
        "",
        "## Boundary:",
        "- No live location polling or email polling in this layer.",
        "- No invoice generation, ledger mutation, production mutation, model call, or tool execution.",
        "- No credential bypass, workbook cell reads, or network intrusion authority.",
        "",
        "## Next safe move:",
        "- Keep automation on bounded scope, declared windows, and receipt proofs.",
        "- Prefer explicit on/off controls and short steel-thread actions.",
    ]
    return "\n".join(lines) + "\n"


def export_hermes_gravity_controller(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    deadline_local: str | None = None,
) -> tuple[str, str]:
    payload = build_hermes_gravity_controller(
        generated_at=generated_at,
        deadline_local=deadline_local,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_hermes_gravity_controller(payload), encoding="utf-8")
    return json_path.as_posix(), operator_path.as_posix()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Hermes gravity controller read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--deadline-local", default=DEFAULT_DEADLINE_LOCAL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    json_path, operator_path = export_hermes_gravity_controller(
        repo_root=args.repo_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
        deadline_local=args.deadline_local,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "json_path": json_path,
        "operator_path": operator_path,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(payload), end="")
    else:
        print("Hermes Gravity Controller exported")
        print(f"- JSON: `{json_path}`")
        print(f"- Operator: `{operator_path}`")
    return 0


__all__ = [
    "GRAVITY_DECISION_REQUIRED_FIELDS",
    "GRAVITY_STATUSES",
    "AUTHORITY_BOUNDARY",
    "SCHEMA_VERSION",
    "READ_MODEL_ID",
    "build_hermes_gravity_controller",
    "evaluate_purpose_bound_capability",
    "export_hermes_gravity_controller",
    "format_operator_hermes_gravity_controller",
    "main",
    "parse_args",
    "stable_json",
]
