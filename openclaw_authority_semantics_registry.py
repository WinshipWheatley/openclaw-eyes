"""OpenClaw Authority Semantics Registry v0.

This registry is the canonical deterministic source for authority field
polarity, safe positive templates, drift signals, and remediation policy.
It does not start services, call models, open browsers/accounts, read
workbooks, export PDFs, send email, mutate ledgers, or mutate production state.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")

SCHEMA_VERSION = "openclaw_authority_semantics_registry_v0"
READ_MODEL_ID = "openclaw_authority_semantics_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
SQLITE_EXPORT_NAME = f"{READ_MODEL_ID}.sqlite"
SCHEMA_EXPORT_NAME = f"{READ_MODEL_ID}_SCHEMA.sql"
SEED_EXPORT_NAME = f"{READ_MODEL_ID}_SEED.sql"
CONTRACT_STATUS = "DETERMINISTIC_AUTHORITY_SEMANTICS_REGISTRY_NO_EXECUTION"

AUTHORITY_SEMANTICS_VERSION = "authority_semantics_v0"
EVENT_BRIDGE_FINANCE_PROFILE_REF = "event_bridge_finance_workflow_action_v0"
EVENT_BRIDGE_FINANCE_TEMPLATE_REF = "event_bridge_finance_workflow_action_template"

FIELD_FAMILIES = (
    "PROHIBITION_FLAG",
    "AUTHORITY_GRANT",
    "SAFETY_GUARD",
    "RECEIPT_REQUIREMENT",
    "MUTATION_GATE",
    "LEGACY_COMPATIBILITY_GUARD",
)

LOCATIONS = (
    "TOP_LEVEL",
    "SAFETY_FLAGS",
    "AUTHORITY_BOUNDARY",
    "PAYLOAD",
    "MACHINE_PROOF",
    "RESULT_RECEIPT",
)

GROWTH_STAGES = (
    "UNSAFE_GROWTH_SEED",
    "EARLY_DRIFT",
    "ACTIVE_DRIFT",
    "ENTRENCHED_DRIFT",
    "MATURE_WEED",
)

SEVERITIES = ("INFO", "WARNING", "BLOCKER", "CRITICAL")

DRIFT_TYPES = (
    "AMBIGUOUS_AUTHORITY_FIELD",
    "WRONG_BOOLEAN_POLARITY",
    "WRONG_LOCATION",
    "MISSING_REQUIRED_FIELD",
    "UNSAFE_TRUE_GRANT",
    "LEGACY_CHAT_ACTION_ALLOWED",
    "MUTATION_WITHOUT_RECEIPT",
    "UNKNOWN_AUTHORITY_FIELD",
    "STALE_GENERATED_VIEW",
    "DUPLICATED_AUTHORITY_SEMANTICS",
    "MISSING_POSITIVE_TEMPLATE",
    "POSITIVE_STRUCTURE_ABSENT",
)

DETERMINISTIC_DRIFT_OUTPUTS = (
    "AUTHORITY_SEMANTICS_DRIFT",
    "AMBIGUOUS_AUTHORITY_FIELD",
    "WRONG_BOOLEAN_POLARITY",
    "WRONG_LOCATION",
    "UNSAFE_TRUE_GRANT",
    "LEGACY_CHAT_ACTION_ALLOWED",
    "MUTATION_WITHOUT_RECEIPT",
    "UNKNOWN_AUTHORITY_FIELD",
    "ENTRENCHED_DRIFT",
    "MATURE_WEED",
    "MISSING_POSITIVE_TEMPLATE",
    "POSITIVE_STRUCTURE_ABSENT",
)

REMEDIATION_RESPONSES = (
    "DETECT_ONLY",
    "BLOCK_ACTION",
    "QUARANTINE_PAYLOAD",
    "AUTO_REGENERATE_DERIVED_VIEW",
    "PROPOSE_FIX",
    "APPLY_DETERMINISTIC_FIX",
    "REQUIRE_OPERATOR_APPROVAL",
    "ESCALATE_TO_GUARDIAN",
    "CREATE_CHIEF_WORK_PACKAGE",
    "FREEZE_RAIL",
    "INSTALL_POSITIVE_TEMPLATE",
    "REQUIRE_GOLDEN_PATH_MIGRATION",
)

REQUIRED_SQLITE_TABLES = (
    "authority_field_semantics",
    "authority_profile",
    "authority_validation_rule",
    "device_authority_shard",
    "authority_drift_signal",
    "authority_remediation_policy",
    "positive_occupation_template",
    "golden_path_fixture",
)

PROHIBITION_TO_GRANT = {
    "no_email_send": "email_send_allowed",
    "no_gmail": "gmail_access_allowed",
    "no_browser": "browser_access_allowed",
    "no_ledger_post": "ledger_post_allowed",
    "no_coupa": "coupa_access_allowed",
    "no_workbook_cell_read": "workbook_cell_read_allowed",
    "no_physical_printing": "physical_printing_allowed",
    "no_source_workbook_mutation": "source_workbook_mutation_allowed",
}

PROHIBITION_FIELDS = tuple(PROHIBITION_TO_GRANT)

AUTHORITY_GRANT_FIELDS = (
    "email_send_allowed",
    "gmail_access_allowed",
    "browser_access_allowed",
    "ledger_post_allowed",
    "coupa_access_allowed",
    "workbook_cell_read_allowed",
    "physical_printing_allowed",
    "source_workbook_mutation_allowed",
    "business_mutation_allowed",
)

LEGACY_DENIED_AUTHORITY_FIELDS = (
    "browser_automation_allowed",
    "coupa_submit_allowed",
    "pdf_export_allowed",
    "artifact_attachment_allowed",
    "production_state_mutation_allowed",
    "external_action_allowed",
    "network_operation_allowed",
    "tool_execution_allowed",
    "workflow_execution_allowed",
    "agent_dispatch_allowed",
    "model_call_allowed",
    "credential_handling_allowed",
)

DANGEROUS_AUTHORITY_GRANTS = tuple(dict.fromkeys(AUTHORITY_GRANT_FIELDS + LEGACY_DENIED_AUTHORITY_FIELDS))

REQUIRED_TRUE_SAFETY_FLAGS = (
    "hot_path_event",
    "structured_action_required",
    "operator_receipt_required_before_mutation",
    "no_email_send",
    "no_gmail",
    "no_browser",
    "no_ledger_post",
    "no_coupa",
    "no_workbook_cell_read",
    "no_physical_printing",
)

REQUIRED_FALSE_SAFETY_FLAGS = (
    "old_chat_card_live_action_source_allowed",
    "legacy_chat_card_live_action_source_allowed",
    "business_mutation_without_receipt_allowed",
)

REQUIRED_FALSE_AUTHORITY_GRANTS = AUTHORITY_GRANT_FIELDS


@dataclass(frozen=True)
class AuthoritySemanticsValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    drift_signals: tuple[dict[str, Any], ...]
    positive_replacement_guidance: dict[str, Any]
    authority_profile_ref: str
    positive_occupation_template_ref: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _short_hash(*parts: object) -> str:
    return hashlib.sha256(_compact_json(parts).encode("utf-8")).hexdigest()[:20]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def default_safety_flags() -> dict[str, bool]:
    return {
        "hot_path_event": True,
        "structured_action_required": True,
        "result_receipt_required": True,
        "operator_receipt_required_before_mutation": True,
        "old_chat_card_live_action_source_allowed": False,
        "legacy_chat_card_live_action_source_allowed": False,
        "business_mutation_without_receipt_allowed": False,
        "telegram_compact_surface": False,
        "change_sentinel_cold_path": False,
        **{field: True for field in PROHIBITION_FIELDS},
    }


def denied_authority_boundary(extra_denied_fields: Mapping[str, bool] | None = None) -> dict[str, bool]:
    boundary = {field: False for field in DANGEROUS_AUTHORITY_GRANTS}
    if extra_denied_fields:
        boundary.update({str(key): bool(value) for key, value in extra_denied_fields.items()})
    return boundary


def positive_replacement_guidance(
    *,
    template_ref: str = EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
    profile_ref: str = EVENT_BRIDGE_FINANCE_PROFILE_REF,
) -> dict[str, Any]:
    return {
        "remediation_status": "REMEDIATION_REQUIRED",
        "positive_occupation": "POSITIVE_OCCUPATION",
        "positive_replacement": template_ref,
        "authority_profile_ref": profile_ref,
        "safe_remediation_path": (
            "Move no_* true guards to safety_flags. Use denied *_allowed=false grants "
            "inside authority_boundary. Do not rewrite live payloads silently."
        ),
        "correct_safety_flags": default_safety_flags(),
        "correct_authority_boundary": denied_authority_boundary(),
        "golden_path_template_ref": template_ref,
    }


def _signal(
    *,
    field_name: str,
    drift_type: str,
    growth_stage: str,
    severity: str,
    operator_summary: str,
    developer_summary: str,
    recommended_action: str,
    positive_replacement: str,
    component_ref: str = "event_bridge",
    profile_ref: str = EVENT_BRIDGE_FINANCE_PROFILE_REF,
    source_ref: str = "runtime_payload",
) -> dict[str, Any]:
    return {
        "drift_ref": f"authority_drift:{_short_hash(field_name, drift_type, component_ref, profile_ref, source_ref)}",
        "detected_at": "",
        "field_name": field_name,
        "component_ref": component_ref,
        "profile_ref": profile_ref,
        "drift_type": drift_type,
        "growth_stage": growth_stage,
        "severity": severity,
        "operator_summary": operator_summary,
        "developer_summary": developer_summary,
        "recommended_action": recommended_action,
        "positive_replacement": positive_replacement,
        "source_ref": source_ref,
    }


def detect_authority_drift(
    envelope: Mapping[str, Any],
    *,
    profile_ref: str = EVENT_BRIDGE_FINANCE_PROFILE_REF,
    component_ref: str = "event_bridge",
    source_ref: str = "runtime_payload",
) -> tuple[dict[str, Any], ...]:
    safety = _as_mapping(envelope.get("safety_flags"))
    authority = _as_mapping(envelope.get("authority_boundary"))
    signals: list[dict[str, Any]] = []
    replacement = EVENT_BRIDGE_FINANCE_TEMPLATE_REF

    for field, value in authority.items():
        field_name = str(field)
        if field_name in PROHIBITION_FIELDS:
            if value is True:
                signals.append(
                    _signal(
                        field_name=f"authority_boundary.{field_name}",
                        drift_type="WRONG_BOOLEAN_POLARITY",
                        growth_stage="UNSAFE_GROWTH_SEED",
                        severity="BLOCKER",
                        operator_summary="A prohibition flag appeared inside authority_boundary as a true value.",
                        developer_summary=f"{field_name}=true means prohibited, not granted authority.",
                        recommended_action="Block the envelope and use the Event Bridge finance golden template.",
                        positive_replacement=replacement,
                        component_ref=component_ref,
                        profile_ref=profile_ref,
                        source_ref=source_ref,
                    )
                )
            else:
                signals.append(
                    _signal(
                        field_name=f"authority_boundary.{field_name}",
                        drift_type="WRONG_LOCATION",
                        growth_stage="UNSAFE_GROWTH_SEED",
                        severity="BLOCKER",
                        operator_summary="A prohibition flag appeared in authority_boundary.",
                        developer_summary=f"{field_name} belongs in safety_flags or a machine-proof section.",
                        recommended_action="Move the prohibition flag to safety_flags and keep authority grants explicit.",
                        positive_replacement=replacement,
                        component_ref=component_ref,
                        profile_ref=profile_ref,
                        source_ref=source_ref,
                    )
                )
            continue
        if field_name in DANGEROUS_AUTHORITY_GRANTS and value is True:
            signals.append(
                _signal(
                    field_name=f"authority_boundary.{field_name}",
                    drift_type="UNSAFE_TRUE_GRANT",
                    growth_stage="ACTIVE_DRIFT",
                    severity="CRITICAL",
                    operator_summary="A dangerous authority grant was true in a finance hot-path event.",
                    developer_summary=f"{field_name}=true is not allowed for this v0 Event Bridge finance path.",
                    recommended_action="Block the envelope until an explicit receipt-gated authority profile exists.",
                    positive_replacement="denied authority profile with *_allowed=false until receipt is present",
                    component_ref=component_ref,
                    profile_ref=profile_ref,
                    source_ref=source_ref,
                )
            )
        elif field_name not in DANGEROUS_AUTHORITY_GRANTS and value is True:
            signals.append(
                _signal(
                    field_name=f"authority_boundary.{field_name}",
                    drift_type="UNKNOWN_AUTHORITY_FIELD",
                    growth_stage="UNSAFE_GROWTH_SEED",
                    severity="BLOCKER",
                    operator_summary="An unknown authority field was true.",
                    developer_summary=f"{field_name} is not registered in the authority semantics registry.",
                    recommended_action="Register the field semantics before any route can rely on it.",
                    positive_replacement=replacement,
                    component_ref=component_ref,
                    profile_ref=profile_ref,
                    source_ref=source_ref,
                )
            )

    for field in REQUIRED_TRUE_SAFETY_FLAGS:
        if safety.get(field) is not True:
            signals.append(
                _signal(
                    field_name=f"safety_flags.{field}",
                    drift_type="MISSING_REQUIRED_FIELD",
                    growth_stage="UNSAFE_GROWTH_SEED",
                    severity="BLOCKER",
                    operator_summary="A required finance hot-path safety guard is missing or false.",
                    developer_summary=f"safety_flags.{field} must be true for this profile.",
                    recommended_action="Use the Event Bridge finance workflow action template.",
                    positive_replacement=replacement,
                    component_ref=component_ref,
                    profile_ref=profile_ref,
                    source_ref=source_ref,
                )
            )

    if envelope.get("result_receipt_required") is not True:
        signals.append(
            _signal(
                field_name="result_receipt_required",
                drift_type="MISSING_REQUIRED_FIELD",
                growth_stage="UNSAFE_GROWTH_SEED",
                severity="BLOCKER",
                operator_summary="The event does not require a result receipt.",
                developer_summary="result_receipt_required must be true for finance hot-path events.",
                recommended_action="Require a result receipt before downstream mutation can be considered.",
                positive_replacement=replacement,
                component_ref=component_ref,
                profile_ref=profile_ref,
                source_ref=source_ref,
            )
        )

    for field in REQUIRED_FALSE_SAFETY_FLAGS:
        if safety.get(field) is True:
            drift_type = (
                "MUTATION_WITHOUT_RECEIPT"
                if field == "business_mutation_without_receipt_allowed"
                else "LEGACY_CHAT_ACTION_ALLOWED"
            )
            signals.append(
                _signal(
                    field_name=f"safety_flags.{field}",
                    drift_type=drift_type,
                    growth_stage="ACTIVE_DRIFT" if drift_type == "MUTATION_WITHOUT_RECEIPT" else "EARLY_DRIFT",
                    severity="CRITICAL" if drift_type == "MUTATION_WITHOUT_RECEIPT" else "BLOCKER",
                    operator_summary="A blocked legacy or mutation path was marked allowed.",
                    developer_summary=f"safety_flags.{field} must be false.",
                    recommended_action="Block the route and migrate to the registered positive template.",
                    positive_replacement=(
                        "guardian_receipt_required_mutation_template"
                        if drift_type == "MUTATION_WITHOUT_RECEIPT"
                        else replacement
                    ),
                    component_ref=component_ref,
                    profile_ref=profile_ref,
                    source_ref=source_ref,
                )
            )

    for field in REQUIRED_FALSE_AUTHORITY_GRANTS:
        if field not in authority:
            signals.append(
                _signal(
                    field_name=f"authority_boundary.{field}",
                    drift_type="MISSING_REQUIRED_FIELD",
                    growth_stage="UNSAFE_GROWTH_SEED",
                    severity="BLOCKER",
                    operator_summary="A denied authority grant is missing from authority_boundary.",
                    developer_summary=f"authority_boundary.{field}=false must be explicit.",
                    recommended_action="Use the Event Bridge finance workflow action template.",
                    positive_replacement=replacement,
                    component_ref=component_ref,
                    profile_ref=profile_ref,
                    source_ref=source_ref,
                )
            )
        elif authority.get(field) is not False:
            signals.append(
                _signal(
                    field_name=f"authority_boundary.{field}",
                    drift_type="UNSAFE_TRUE_GRANT",
                    growth_stage="ACTIVE_DRIFT",
                    severity="CRITICAL",
                    operator_summary="A required denied authority grant was not false.",
                    developer_summary=f"authority_boundary.{field} must be false for this profile.",
                    recommended_action="Block the event and require explicit receipt-gated approval before any future grant.",
                    positive_replacement="denied authority profile with *_allowed=false until receipt is present",
                    component_ref=component_ref,
                    profile_ref=profile_ref,
                    source_ref=source_ref,
                )
            )

    return tuple(signals)


def validate_authority_semantics(
    envelope: Mapping[str, Any],
    *,
    profile_ref: str = EVENT_BRIDGE_FINANCE_PROFILE_REF,
    component_ref: str = "event_bridge",
    source_ref: str = "runtime_payload",
) -> AuthoritySemanticsValidation:
    signals = detect_authority_drift(
        envelope,
        profile_ref=profile_ref,
        component_ref=component_ref,
        source_ref=source_ref,
    )
    errors: list[str] = []
    warnings: list[str] = []
    for signal in signals:
        code = (
            f"AUTHORITY_SEMANTICS_DRIFT:{signal['drift_type']}:{signal['field_name']}"
        )
        if signal["severity"] in {"BLOCKER", "CRITICAL"}:
            errors.append(code)
        else:
            warnings.append(code)

    authority = _as_mapping(envelope.get("authority_boundary"))
    known = set(DANGEROUS_AUTHORITY_GRANTS) | set(PROHIBITION_FIELDS)
    for field in authority:
        if str(field) not in known and authority.get(field) is False:
            warnings.append(f"UNKNOWN_AUTHORITY_FIELD:authority_boundary.{field}")

    return AuthoritySemanticsValidation(
        valid=not errors,
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
        drift_signals=signals,
        positive_replacement_guidance=positive_replacement_guidance(
            profile_ref=profile_ref,
            template_ref=EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
        ),
        authority_profile_ref=profile_ref,
        positive_occupation_template_ref=EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
    )


def _field_semantics_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for field_name, replacement in PROHIBITION_TO_GRANT.items():
        rows.append(
        {
            "field_ref": f"field:{field_name}",
                "field_name": field_name,
                "field_family": "PROHIBITION_FLAG",
                "true_meaning": "The action is prohibited and must not happen.",
                "false_meaning": "The prohibition is not asserted; this does not grant authority.",
                "allowed_locations": ("TOP_LEVEL", "SAFETY_FLAGS", "MACHINE_PROOF"),
                "forbidden_locations": ("AUTHORITY_BOUNDARY",),
                "required_for_event_bridge": field_name != "no_source_workbook_mutation",
                "required_for_finance": True,
                "default_value": True,
                "risk_if_wrong": "Wrong polarity can turn a prohibition into apparent authority.",
                "operator_copy": f"{field_name}=true blocks that action.",
                "developer_copy": f"Keep {field_name} out of authority_boundary; use {replacement}=false there.",
                "positive_replacement_field": replacement,
                "golden_path_example_ref": "live_arts_prepare_pdf_event_fixture",
            }
        )
    for field_name in AUTHORITY_GRANT_FIELDS:
        rows.append(
            {
                "field_ref": f"field:{field_name}",
                "field_name": field_name,
                "field_family": "AUTHORITY_GRANT",
                "true_meaning": "The action is explicitly allowed by the active authority profile.",
                "false_meaning": "The action is denied.",
                "allowed_locations": ("AUTHORITY_BOUNDARY",),
                "forbidden_locations": ("SAFETY_FLAGS", "PAYLOAD"),
                "required_for_event_bridge": True,
                "required_for_finance": True,
                "default_value": False,
                "risk_if_wrong": "Unsafe true grants can create hidden mutation or external-action paths.",
                "operator_copy": f"{field_name}=false denies that authority.",
                "developer_copy": f"Do not set {field_name}=true without an explicit receipt-gated profile.",
                "positive_replacement_field": "",
                "golden_path_example_ref": "live_arts_prepare_pdf_event_fixture",
            }
        )
    for field_name, family, default in (
        ("hot_path_event", "SAFETY_GUARD", True),
        ("structured_action_required", "SAFETY_GUARD", True),
        ("result_receipt_required", "RECEIPT_REQUIREMENT", True),
        ("operator_receipt_required_before_mutation", "MUTATION_GATE", True),
        ("old_chat_card_live_action_source_allowed", "LEGACY_COMPATIBILITY_GUARD", False),
        ("legacy_chat_card_live_action_source_allowed", "LEGACY_COMPATIBILITY_GUARD", False),
        ("business_mutation_without_receipt_allowed", "MUTATION_GATE", False),
    ):
        rows.append(
            {
                "field_ref": f"field:{field_name}",
                "field_name": field_name,
                "field_family": family,
                "true_meaning": "Required guard asserted." if default else "Unsafe legacy or mutation bypass allowed.",
                "false_meaning": "Guard absent." if default else "Unsafe legacy or mutation bypass denied.",
                "allowed_locations": ("TOP_LEVEL", "SAFETY_FLAGS"),
                "forbidden_locations": ("AUTHORITY_BOUNDARY",),
                "required_for_event_bridge": True,
                "required_for_finance": True,
                "default_value": default,
                "risk_if_wrong": "Finance hot-path routing can become ambiguous or unsafe.",
                "operator_copy": f"{field_name} default is {str(default).lower()}.",
                "developer_copy": "Use the finance Event Bridge authority profile for exact polarity.",
                "positive_replacement_field": "",
                "golden_path_example_ref": "event_bridge_finance_workflow_action_fixture",
            }
        )
    return tuple(rows)


def _profile_rows() -> tuple[dict[str, Any], ...]:
    return (
        {
            "profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
            "profile_name": "Event Bridge finance workflow action v0",
            "applies_to": ("EVENT_BRIDGE", "MAC_APP", "PC_BACKEND", "TELEGRAM", "INVOICE_REVIEW"),
            "purpose": "Validate finance hot-path workflow action envelopes before routing.",
            "required_fields": (
                "safety_flags.hot_path_event",
                "safety_flags.structured_action_required",
                "safety_flags.operator_receipt_required_before_mutation",
                "result_receipt_required",
                *tuple(f"safety_flags.{field}" for field in REQUIRED_TRUE_SAFETY_FLAGS if field.startswith("no_")),
                *tuple(f"authority_boundary.{field}" for field in REQUIRED_FALSE_AUTHORITY_GRANTS),
            ),
            "forbidden_fields": tuple(f"authority_boundary.{field}" for field in PROHIBITION_FIELDS),
            "default_deny": True,
            "receipts_required": ("selected_invoice_pdf_export_requested_receipt", "result_receipt"),
            "dangerous_authorities": DANGEROUS_AUTHORITY_GRANTS,
            "allowed_actions": (
                "route workflow action",
                "emit structured response",
                "write route receipt",
                "reject invalid envelope",
            ),
            "blocked_actions": (
                "execute PDF export",
                "send email",
                "access Gmail",
                "access browser",
                "access Coupa",
                "post ledger",
                "read workbook cells",
                "physically print",
                "mutate source workbook",
                "execute legacy chat-card action",
            ),
            "positive_structure_refs": (
                "event_bridge_finance_workflow_action_template",
                "event_bridge_finance_response_template",
                "guardian_receipt_required_mutation_template",
            ),
            "golden_path_template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
        },
    )


def _validation_rule_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for field in REQUIRED_TRUE_SAFETY_FLAGS:
        rows.append(
            {
                "rule_ref": f"rule:require_true:safety_flags.{field}",
                "profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
                "rule_type": "REQUIRE_TRUE",
                "field_name": f"safety_flags.{field}",
                "expected_value": True,
                "message": f"safety_flags.{field} must be true.",
                "severity": "BLOCKER",
                "growth_stage": "UNSAFE_GROWTH_SEED",
                "remediation": "Use the Event Bridge finance workflow action template.",
                "positive_replacement": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
                "golden_path_template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            }
        )
    rows.append(
        {
            "rule_ref": "rule:require_true:result_receipt_required",
            "profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
            "rule_type": "REQUIRE_TRUE",
            "field_name": "result_receipt_required",
            "expected_value": True,
            "message": "result_receipt_required must be true.",
            "severity": "BLOCKER",
            "growth_stage": "UNSAFE_GROWTH_SEED",
            "remediation": "Require a result receipt before any downstream mutation.",
            "positive_replacement": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            "golden_path_template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
        }
    )
    for field in REQUIRED_FALSE_AUTHORITY_GRANTS:
        rows.append(
            {
                "rule_ref": f"rule:require_false:authority_boundary.{field}",
                "profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
                "rule_type": "REQUIRE_FALSE",
                "field_name": f"authority_boundary.{field}",
                "expected_value": False,
                "message": f"authority_boundary.{field} must be false.",
                "severity": "CRITICAL",
                "growth_stage": "ACTIVE_DRIFT",
                "remediation": "Keep dangerous grants denied until an explicit receipt-gated profile exists.",
                "positive_replacement": "denied authority profile with *_allowed=false until receipt is present",
                "golden_path_template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            }
        )
    for field in PROHIBITION_FIELDS:
        rows.append(
            {
                "rule_ref": f"rule:legacy_field_banned:authority_boundary.{field}",
                "profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
                "rule_type": "LEGACY_FIELD_BANNED",
                "field_name": f"authority_boundary.{field}",
                "expected_value": "",
                "message": f"{field} is prohibited from authority_boundary.",
                "severity": "BLOCKER",
                "growth_stage": "UNSAFE_GROWTH_SEED",
                "remediation": f"Move {field}=true to safety_flags and use {PROHIBITION_TO_GRANT[field]}=false.",
                "positive_replacement": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
                "golden_path_template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            }
        )
    for field in REQUIRED_FALSE_SAFETY_FLAGS:
        rows.append(
            {
                "rule_ref": f"rule:require_false:safety_flags.{field}",
                "profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
                "rule_type": "REQUIRE_FALSE",
                "field_name": f"safety_flags.{field}",
                "expected_value": False,
                "message": f"safety_flags.{field} must be false.",
                "severity": "CRITICAL" if field == "business_mutation_without_receipt_allowed" else "BLOCKER",
                "growth_stage": "ACTIVE_DRIFT" if field == "business_mutation_without_receipt_allowed" else "EARLY_DRIFT",
                "remediation": "Route through positive Event Bridge/Guardian receipt templates.",
                "positive_replacement": (
                    "guardian_receipt_required_mutation_template"
                    if field == "business_mutation_without_receipt_allowed"
                    else EVENT_BRIDGE_FINANCE_TEMPLATE_REF
                ),
                "golden_path_template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            }
        )
    return tuple(rows)


def _template_rows() -> tuple[dict[str, Any], ...]:
    common_forbidden = tuple(f"authority_boundary.{field}" for field in PROHIBITION_FIELDS)
    common_required = (
        "event_kind",
        "source_channel",
        "world_ref",
        "client_ref",
        "workflow_ref",
        "thread_ref",
        "actor_ref",
        "idempotency_key",
        "correlation_id",
        "created_at",
        "expires_at",
        "expected_response_kind",
        "result_receipt_required",
        "safety_flags",
        "authority_boundary",
    )
    return (
        {
            "template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            "template_name": "Event Bridge finance workflow action",
            "applies_to": ("EVENT_BRIDGE", "MAC_APP", "TELEGRAM", "INVOICE_REVIEW"),
            "purpose": "Canonical hot-path finance workflow event envelope.",
            "replaces_bad_pattern": "Prohibition flags in authority_boundary or legacy chat-card live actions.",
            "required_fields": common_required,
            "forbidden_fields": common_forbidden,
            "example_payload": _example_finance_event_payload(),
            "validation_profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
            "owner_component": "PC_BACKEND",
            "generated_fixture_path": "generated/read_models/openclaw_authority_semantics_registry.json#golden_path_fixture.event_bridge_finance_workflow_action_fixture",
            "operator_summary": "Use one finance workflow event envelope for Mac app, Telegram, and PC service intake.",
            "developer_summary": "Safety flags carry no_* prohibitions; authority_boundary carries denied *_allowed grants.",
            "status": "ACTIVE",
        },
        {
            "template_ref": "event_bridge_finance_response_template",
            "template_name": "Event Bridge finance response",
            "applies_to": ("EVENT_BRIDGE", "PC_BACKEND", "MAC_APP", "TELEGRAM"),
            "purpose": "Canonical routed workflow response.",
            "replaces_bad_pattern": "Unscoped or action-ambiguous response payloads.",
            "required_fields": (
                "response_id",
                "event_id",
                "correlation_id",
                "route_status",
                "workflow_status",
                "selected_handler_id",
                "operator_copy",
                "stale_event",
                "receipt_refs",
                "machine_proof",
            ),
            "forbidden_fields": (),
            "example_payload": _example_response_payload(),
            "validation_profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
            "owner_component": "PC_BACKEND",
            "generated_fixture_path": "generated/read_models/openclaw_authority_semantics_registry.json#golden_path_fixture.event_bridge_finance_response_fixture",
            "operator_summary": "Response remains scoped to the original event, workflow, client, and thread.",
            "developer_summary": "Machine proof must show no dangerous action performed by adapter routing.",
            "status": "ACTIVE",
        },
        {
            "template_ref": "live_arts_prepare_pdf_event_template",
            "template_name": "Live Arts Prepare PDF event",
            "applies_to": ("EVENT_BRIDGE", "MAC_APP", "INVOICE_REVIEW"),
            "purpose": "Golden example for Live Arts Prepare invoice PDF.",
            "replaces_bad_pattern": "Mac app granting PDF/export/email/ledger authority directly.",
            "required_fields": common_required + ("payload.action_kind",),
            "forbidden_fields": common_forbidden + ("authority_boundary.pdf_export_allowed",),
            "example_payload": _example_live_arts_prepare_pdf_payload(),
            "validation_profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
            "owner_component": "PC_BACKEND",
            "generated_fixture_path": "generated/read_models/openclaw_authority_semantics_registry.json#golden_path_fixture.live_arts_prepare_pdf_event_fixture",
            "operator_summary": "Live Arts Prepare PDF routes intent only; it does not execute export.",
            "developer_summary": "Selected invoice context can be present, but PDF execution authority remains false.",
            "status": "ACTIVE",
        },
        {
            "template_ref": "telegram_finance_command_template",
            "template_name": "Telegram finance command",
            "applies_to": ("TELEGRAM", "EVENT_BRIDGE"),
            "purpose": "Telegram compact surface emits the same event shape.",
            "replaces_bad_pattern": "Telegram-specific workflow logic or mutation bypass.",
            "required_fields": common_required + ("payload.command",),
            "forbidden_fields": common_forbidden,
            "example_payload": {
                **_example_finance_event_payload(),
                "event_kind": "TELEGRAM_COMMAND",
                "source_channel": "TELEGRAM",
                "payload": {"command": "/prepare_live_arts_pdf", "action_kind": "prepare_selected_invoice_pdf_artifact"},
            },
            "validation_profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
            "owner_component": "TELEGRAM",
            "generated_fixture_path": "generated/read_models/openclaw_authority_semantics_registry.json#golden_path_fixture.telegram_finance_command_fixture",
            "operator_summary": "Telegram emits workflow intent only.",
            "developer_summary": "Telegram is not workflow brain and cannot bypass Event Bridge or receipt gates.",
            "status": "ACTIVE",
        },
        {
            "template_ref": "mac_app_event_bridge_writer_template",
            "template_name": "Mac app Event Bridge writer",
            "applies_to": ("MAC_APP", "EVENT_BRIDGE"),
            "purpose": "Mac app writer emits canonical event envelope and receives response.",
            "replaces_bad_pattern": "Mac app main process owning Excel Automation authority.",
            "required_fields": common_required,
            "forbidden_fields": common_forbidden + ("authority_boundary.pdf_export_allowed",),
            "example_payload": _example_live_arts_prepare_pdf_payload(),
            "validation_profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
            "owner_component": "MAC_APP",
            "generated_fixture_path": "generated/read_models/openclaw_authority_semantics_registry.json#golden_path_fixture.mac_app_writer_fixture",
            "operator_summary": "Mac app emits intent and reads response.",
            "developer_summary": "Excel export belongs to a future helper rail, not the main Mac app.",
            "status": "ACTIVE",
        },
        {
            "template_ref": "mac_excel_helper_authority_template",
            "template_name": "Mac Excel helper authority",
            "applies_to": ("MAC_EDGE_HELPER", "INVOICE_REVIEW"),
            "purpose": "Future helper authority profile for scoped PDF export packages.",
            "replaces_bad_pattern": "Unscoped Excel Automation permission in UI or backend.",
            "required_fields": ("scoped_export_package_ref", "result_receipt", "authority_boundary"),
            "forbidden_fields": (
                "authority_boundary.email_send_allowed",
                "authority_boundary.ledger_post_allowed",
                "authority_boundary.browser_access_allowed",
                "authority_boundary.workbook_cell_read_allowed",
                "authority_boundary.physical_printing_allowed",
            ),
            "example_payload": {
                "helper_may_control_excel_for_scoped_pdf_export_package": True,
                "email_send_allowed": False,
                "ledger_post_allowed": False,
                "browser_access_allowed": False,
                "workbook_cell_read_allowed": False,
                "physical_printing_allowed": False,
                "emits_result_receipt_only": True,
            },
            "validation_profile_ref": "future_mac_excel_helper_scoped_pdf_export_v0",
            "owner_component": "MAC_EDGE_HELPER",
            "generated_fixture_path": "generated/read_models/openclaw_authority_semantics_registry.json#golden_path_fixture.mac_excel_helper_authority_fixture",
            "operator_summary": "Future helper can be scoped to PDF export only.",
            "developer_summary": "Helper cannot send email, touch ledger, use browser, read workbook cells into OpenClaw, or print.",
            "status": "PLANNED",
        },
        {
            "template_ref": "guardian_receipt_required_mutation_template",
            "template_name": "Guardian receipt-required mutation",
            "applies_to": ("RUNTIME_ACTOR", "LEDGER", "PAYMENT_WATCH", "INVOICE_REVIEW"),
            "purpose": "Canonical pattern for any future business mutation.",
            "replaces_bad_pattern": "Business mutation without required receipts.",
            "required_fields": ("guardian_receipt_ref", "operator_receipt_ref", "machine_proof", "rollback_or_fallback"),
            "forbidden_fields": ("business_mutation_allowed_without_receipt",),
            "example_payload": {
                "guardian_receipt_required": True,
                "operator_receipt_required": True,
                "business_mutation_allowed": False,
                "machine_proof_required": True,
                "rollback_or_fallback_required": True,
            },
            "validation_profile_ref": "guardian_receipt_required_mutation_v0",
            "owner_component": "GUARDIAN",
            "generated_fixture_path": "generated/read_models/openclaw_authority_semantics_registry.json#golden_path_fixture.guardian_receipt_required_mutation_fixture",
            "operator_summary": "Future mutation requires explicit receipts.",
            "developer_summary": "Mutation authority remains false unless required receipts are present and verified.",
            "status": "ACTIVE",
        },
    )


def _device_shard_rows() -> tuple[dict[str, Any], ...]:
    return (
        {
            "device_ref": "device:pc_backend",
            "device_name": "PC backend",
            "device_class": "PC_BACKEND",
            "repo_ref": "/home/openclaw",
            "local_path": "/home/openclaw",
            "authority_profiles": (EVENT_BRIDGE_FINANCE_PROFILE_REF,),
            "known_limitations": ("Does not execute Mac Excel.", "Does not own email/Gmail/browser/Coupa authority."),
            "positive_structures_required": (EVENT_BRIDGE_FINANCE_TEMPLATE_REF, "event_bridge_finance_response_template"),
            "last_seen_status": "ACTIVE",
            "source_refs": ("openclaw_event_bridge_adapter.py", "openclaw_authority_semantics_registry.py"),
            "status": "ACTIVE",
        },
        {
            "device_ref": "device:mac_app",
            "device_name": "Mac app",
            "device_class": "MAC_APP",
            "repo_ref": "openclaw-mission-control",
            "local_path": "/Users/winship/Eyes/OpenClaw",
            "authority_profiles": (EVENT_BRIDGE_FINANCE_PROFILE_REF,),
            "known_limitations": ("Should not own Excel Automation authority in main app.",),
            "positive_structures_required": ("mac_app_event_bridge_writer_template",),
            "last_seen_status": "OBSERVED_VIA_BRIDGE",
            "source_refs": ("mission_control_capture_requests/inbox",),
            "status": "ACTIVE",
        },
        {
            "device_ref": "device:mac_excel_helper_planned",
            "device_name": "Mac Excel helper planned",
            "device_class": "MAC_EDGE_HELPER",
            "repo_ref": "openclaw-mission-control",
            "local_path": "",
            "authority_profiles": ("future_mac_excel_helper_scoped_pdf_export_v0",),
            "known_limitations": ("Future owner only; not active in this registry task.",),
            "positive_structures_required": ("mac_excel_helper_authority_template",),
            "last_seen_status": "PLANNED",
            "source_refs": ("openclaw_authority_semantics_registry.py",),
            "status": "PLANNED",
        },
        {
            "device_ref": "device:telegram_compact_surface",
            "device_name": "Telegram compact surface",
            "device_class": "TELEGRAM",
            "repo_ref": "future",
            "local_path": "",
            "authority_profiles": (EVENT_BRIDGE_FINANCE_PROFILE_REF,),
            "known_limitations": ("Must not become workflow brain.", "Must not bypass structured action routing."),
            "positive_structures_required": ("telegram_finance_command_template",),
            "last_seen_status": "CONTRACT_ONLY",
            "source_refs": ("openclaw_event_bridge_contract.py",),
            "status": "CONTRACT_ONLY",
        },
        {
            "device_ref": "device:runtime_actors",
            "device_name": "Runtime actors",
            "device_class": "RUNTIME_ACTOR",
            "repo_ref": "/home/openclaw",
            "local_path": "/home/openclaw",
            "authority_profiles": ("guardian_receipt_required_mutation_v0",),
            "known_limitations": ("Chief/Cassandra/Guardian cannot bypass receipts or the authority registry.",),
            "positive_structures_required": ("guardian_receipt_required_mutation_template",),
            "last_seen_status": "PARTIAL",
            "source_refs": ("OPENCLAW_RUNTIME.md",),
            "status": "PARTIAL",
        },
    )


def _policy_rows() -> tuple[dict[str, Any], ...]:
    return (
        {
            "policy_ref": "policy:authority_boundary_no_star_true",
            "drift_type": "WRONG_BOOLEAN_POLARITY",
            "growth_stage": "UNSAFE_GROWTH_SEED",
            "severity": "BLOCKER",
            "default_response": "BLOCK_ACTION",
            "auto_fix_allowed": False,
            "auto_remove_allowed": False,
            "quarantine_allowed": False,
            "positive_occupation_required": True,
            "requires_receipt": False,
            "requires_guardian_review": False,
            "requires_operator_approval": False,
            "safe_remediation_path": "Move no_* true guards to safety_flags. Use denied *_allowed=false grants in authority_boundary.",
            "forbidden_remediation": "Do not silently rewrite live envelope. Do not loosen PC validation.",
        },
        {
            "policy_ref": "policy:legacy_chat_card_live_action_allowed",
            "drift_type": "LEGACY_CHAT_ACTION_ALLOWED",
            "growth_stage": "EARLY_DRIFT",
            "severity": "BLOCKER",
            "default_response": "BLOCK_ACTION",
            "auto_fix_allowed": False,
            "auto_remove_allowed": False,
            "quarantine_allowed": False,
            "positive_occupation_required": True,
            "requires_receipt": False,
            "requires_guardian_review": False,
            "requires_operator_approval": False,
            "safe_remediation_path": "Route through Event Bridge structured action.",
            "forbidden_remediation": "Do not let legacy chat cards become live finance action sources.",
        },
        {
            "policy_ref": "policy:business_mutation_without_receipt",
            "drift_type": "MUTATION_WITHOUT_RECEIPT",
            "growth_stage": "ACTIVE_DRIFT",
            "severity": "CRITICAL",
            "default_response": "QUARANTINE_PAYLOAD",
            "auto_fix_allowed": False,
            "auto_remove_allowed": False,
            "quarantine_allowed": True,
            "positive_occupation_required": True,
            "requires_receipt": True,
            "requires_guardian_review": True,
            "requires_operator_approval": False,
            "safe_remediation_path": "Quarantine payload, preserve evidence, require Guardian/Hermes review.",
            "forbidden_remediation": "Do not route or mutate without the required receipt.",
        },
        {
            "policy_ref": "policy:dangerous_authority_true_without_approval",
            "drift_type": "UNSAFE_TRUE_GRANT",
            "growth_stage": "ACTIVE_DRIFT",
            "severity": "CRITICAL",
            "default_response": "BLOCK_ACTION",
            "auto_fix_allowed": False,
            "auto_remove_allowed": False,
            "quarantine_allowed": False,
            "positive_occupation_required": True,
            "requires_receipt": False,
            "requires_guardian_review": True,
            "requires_operator_approval": False,
            "safe_remediation_path": "Use denied authority profile with *_allowed=false until receipt is present.",
            "forbidden_remediation": "Do not infer approval from a true authority field.",
        },
        {
            "policy_ref": "policy:generated_view_stale",
            "drift_type": "STALE_GENERATED_VIEW",
            "growth_stage": "UNSAFE_GROWTH_SEED",
            "severity": "WARNING",
            "default_response": "AUTO_REGENERATE_DERIVED_VIEW",
            "auto_fix_allowed": True,
            "auto_remove_allowed": False,
            "quarantine_allowed": False,
            "positive_occupation_required": True,
            "requires_receipt": False,
            "requires_guardian_review": False,
            "requires_operator_approval": False,
            "safe_remediation_path": "Regenerate derived view from source registry.",
            "forbidden_remediation": "Do not source-fix generated drift by editing canonical code silently.",
        },
        {
            "policy_ref": "policy:duplicated_authority_semantics",
            "drift_type": "DUPLICATED_AUTHORITY_SEMANTICS",
            "growth_stage": "ENTRENCHED_DRIFT",
            "severity": "CRITICAL",
            "default_response": "CREATE_CHIEF_WORK_PACKAGE",
            "auto_fix_allowed": False,
            "auto_remove_allowed": False,
            "quarantine_allowed": False,
            "positive_occupation_required": True,
            "requires_receipt": False,
            "requires_guardian_review": False,
            "requires_operator_approval": False,
            "safe_remediation_path": "Create bounded remediation package to adopt central authority semantics registry.",
            "forbidden_remediation": "Do not silently rewrite source truth.",
        },
        {
            "policy_ref": "policy:mature_unsafe_authority_architecture",
            "drift_type": "ENTRENCHED_DRIFT",
            "growth_stage": "MATURE_WEED",
            "severity": "CRITICAL",
            "default_response": "FREEZE_RAIL",
            "auto_fix_allowed": False,
            "auto_remove_allowed": False,
            "quarantine_allowed": False,
            "positive_occupation_required": True,
            "requires_receipt": False,
            "requires_guardian_review": True,
            "requires_operator_approval": True,
            "safe_remediation_path": "Disable unsafe rail and create approved replacement architecture work package.",
            "forbidden_remediation": "Do not remove relied-on architecture without approval or migration contract.",
        },
    )


def _fixture_rows() -> tuple[dict[str, Any], ...]:
    return (
        {
            "fixture_ref": "event_bridge_finance_workflow_action_fixture",
            "template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            "fixture_name": "Event Bridge finance workflow action",
            "fixture_kind": "EVENT_ENVELOPE",
            "payload_json": _example_finance_event_payload(),
            "expected_validation_status": "VALID",
            "expected_route": "invoice_review_action_request.live_arts_md",
            "forbidden_side_effects": ("email", "gmail", "browser", "coupa", "ledger", "workbook_cell_read", "pdf_export", "physical_printing"),
            "source_ref": "openclaw_authority_semantics_registry.py",
        },
        {
            "fixture_ref": "event_bridge_finance_response_fixture",
            "template_ref": "event_bridge_finance_response_template",
            "fixture_name": "Event Bridge finance response",
            "fixture_kind": "RESPONSE_ENVELOPE",
            "payload_json": _example_response_payload(),
            "expected_validation_status": "VALID",
            "expected_route": "ROUTE_MATCHED",
            "forbidden_side_effects": ("handler_execution", "business_mutation"),
            "source_ref": "openclaw_authority_semantics_registry.py",
        },
        {
            "fixture_ref": "live_arts_prepare_pdf_event_fixture",
            "template_ref": "live_arts_prepare_pdf_event_template",
            "fixture_name": "Live Arts Prepare PDF event",
            "fixture_kind": "EVENT_ENVELOPE",
            "payload_json": _example_live_arts_prepare_pdf_payload(),
            "expected_validation_status": "VALID",
            "expected_route": "invoice_review_action_request.live_arts_md",
            "forbidden_side_effects": ("pdf_export", "email", "ledger", "workbook_cell_read"),
            "source_ref": "openclaw_authority_semantics_registry.py",
        },
        {
            "fixture_ref": "telegram_finance_command_fixture",
            "template_ref": "telegram_finance_command_template",
            "fixture_name": "Telegram finance command",
            "fixture_kind": "EVENT_ENVELOPE",
            "payload_json": {
                **_example_finance_event_payload(),
                "event_kind": "TELEGRAM_COMMAND",
                "source_channel": "TELEGRAM",
                "payload": {"command": "/prepare_live_arts_pdf", "action_kind": "prepare_selected_invoice_pdf_artifact"},
            },
            "expected_validation_status": "VALID",
            "expected_route": "invoice_review_action_request.live_arts_md",
            "forbidden_side_effects": ("telegram_runtime", "business_mutation"),
            "source_ref": "openclaw_authority_semantics_registry.py",
        },
        {
            "fixture_ref": "mac_app_writer_fixture",
            "template_ref": "mac_app_event_bridge_writer_template",
            "fixture_name": "Mac app writer",
            "fixture_kind": "EVENT_ENVELOPE",
            "payload_json": _example_live_arts_prepare_pdf_payload(),
            "expected_validation_status": "VALID",
            "expected_route": "invoice_review_action_request.live_arts_md",
            "forbidden_side_effects": ("excel_automation_main_app", "pdf_export"),
            "source_ref": "openclaw_authority_semantics_registry.py",
        },
        {
            "fixture_ref": "mac_excel_helper_authority_fixture",
            "template_ref": "mac_excel_helper_authority_template",
            "fixture_name": "Mac Excel helper authority",
            "fixture_kind": "AUTHORITY_BOUNDARY",
            "payload_json": denied_authority_boundary({"scoped_excel_pdf_export_allowed": True}),
            "expected_validation_status": "PLANNED_PROFILE_ONLY",
            "expected_route": "HELPER_RESULT_RECEIPT_ONLY",
            "forbidden_side_effects": ("email", "ledger", "browser", "workbook_cell_read", "physical_printing"),
            "source_ref": "openclaw_authority_semantics_registry.py",
        },
        {
            "fixture_ref": "guardian_receipt_required_mutation_fixture",
            "template_ref": "guardian_receipt_required_mutation_template",
            "fixture_name": "Guardian receipt-required mutation",
            "fixture_kind": "RESULT_RECEIPT",
            "payload_json": {
                "guardian_receipt_required": True,
                "operator_receipt_required": True,
                "business_mutation_allowed": False,
                "machine_proof_required": True,
            },
            "expected_validation_status": "VALID_WHEN_RECEIPTS_PRESENT",
            "expected_route": "MUTATION_BLOCKED_UNTIL_RECEIPTS",
            "forbidden_side_effects": ("business_mutation_without_receipt",),
            "source_ref": "openclaw_authority_semantics_registry.py",
        },
    )


def _drift_signal_rows() -> tuple[dict[str, Any], ...]:
    return (
        _signal(
            field_name="authority_boundary.no_browser",
            drift_type="WRONG_BOOLEAN_POLARITY",
            growth_stage="UNSAFE_GROWTH_SEED",
            severity="BLOCKER",
            operator_summary="A no_* prohibition flag appeared in authority_boundary with true polarity.",
            developer_summary="no_browser=true means browser use is prohibited; use safety_flags.no_browser=true and authority_boundary.browser_access_allowed=false.",
            recommended_action="Block the event and use the finance Event Bridge golden template.",
            positive_replacement=EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            source_ref="registry_definition",
        ),
        _signal(
            field_name="safety_flags.legacy_chat_card_live_action_source_allowed",
            drift_type="LEGACY_CHAT_ACTION_ALLOWED",
            growth_stage="EARLY_DRIFT",
            severity="BLOCKER",
            operator_summary="Legacy chat-card action was marked live.",
            developer_summary="Finance hot-path actions must route through Event Bridge structured action templates.",
            recommended_action="Block live action and migrate to Event Bridge template.",
            positive_replacement=EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
            source_ref="registry_definition",
        ),
        _signal(
            field_name="safety_flags.business_mutation_without_receipt_allowed",
            drift_type="MUTATION_WITHOUT_RECEIPT",
            growth_stage="ACTIVE_DRIFT",
            severity="CRITICAL",
            operator_summary="Business mutation without receipt was marked allowed.",
            developer_summary="Mutation authority must remain false without Guardian/operator receipts.",
            recommended_action="Quarantine payload and require Guardian/Hermes review.",
            positive_replacement="guardian_receipt_required_mutation_template",
            source_ref="registry_definition",
        ),
        _signal(
            field_name="authority_boundary.ledger_post_allowed",
            drift_type="UNSAFE_TRUE_GRANT",
            growth_stage="ACTIVE_DRIFT",
            severity="CRITICAL",
            operator_summary="Dangerous finance authority grant was true.",
            developer_summary="ledger_post_allowed=true is blocked for Event Bridge finance v0.",
            recommended_action="Block action until a receipt-gated authority profile exists.",
            positive_replacement="denied authority profile with *_allowed=false until receipt is present",
            source_ref="registry_definition",
        ),
        _signal(
            field_name="generated/read_models/openclaw_authority_semantics_registry.json",
            drift_type="STALE_GENERATED_VIEW",
            growth_stage="UNSAFE_GROWTH_SEED",
            severity="WARNING",
            operator_summary="Generated authority semantics view is stale.",
            developer_summary="Regenerate derived registry views from source.",
            recommended_action="Run the authority semantics registry export script.",
            positive_replacement="fresh generated view from source registry",
            source_ref="registry_definition",
        ),
        _signal(
            field_name="duplicated_authority_semantics",
            drift_type="DUPLICATED_AUTHORITY_SEMANTICS",
            growth_stage="ENTRENCHED_DRIFT",
            severity="CRITICAL",
            operator_summary="Authority semantics are duplicated inconsistently.",
            developer_summary="Adopt the central authority semantics registry.",
            recommended_action="Create a bounded remediation package.",
            positive_replacement="central authority semantics registry",
            source_ref="registry_definition",
        ),
    )


def _example_finance_event_payload() -> dict[str, Any]:
    return {
        "authority_semantics_version": AUTHORITY_SEMANTICS_VERSION,
        "authority_profile_ref": EVENT_BRIDGE_FINANCE_PROFILE_REF,
        "positive_occupation_template_ref": EVENT_BRIDGE_FINANCE_TEMPLATE_REF,
        "event_id": "event_bridge_finance_workflow_action_fixture",
        "event_kind": "WORKFLOW_ACTION_REQUEST",
        "source_channel": "MAC_APP",
        "world_ref": "finance",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "thread_ref": "live_arts_md_invoice_workflow:2026-1001",
        "actor_ref": "operator:winship",
        "idempotency_key": "idempotency:event_bridge_finance_workflow_action_fixture",
        "correlation_id": "correlation:event_bridge_finance_workflow_action_fixture",
        "parent_event_id": "current_live_arts_md_prepare_pdf_action",
        "created_at": "2026-05-31T14:00:00+00:00",
        "expires_at": "2026-05-31T14:05:00+00:00",
        "expected_response_kind": "WORKFLOW_ACTION_RESPONSE",
        "result_receipt_required": True,
        "payload": {"action_kind": "prepare_selected_invoice_pdf_artifact"},
        "safety_flags": default_safety_flags(),
        "authority_boundary": denied_authority_boundary(),
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_ledger_post": True,
        "no_coupa": True,
        "no_workbook_cell_read": True,
        "no_physical_printing": True,
    }


def _example_live_arts_prepare_pdf_payload() -> dict[str, Any]:
    payload = _example_finance_event_payload()
    payload["event_id"] = "live_arts_prepare_pdf_event_fixture"
    payload["payload"] = {
        "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
        "action_kind": "prepare_selected_invoice_pdf_artifact",
        "intended_use": "prepare_selected_invoice_pdf_artifact",
        "invoice_id": "2026-1001",
        "selected_sheet_label": "June 2026 Speaker Rental",
        "selected_print_areas": ("A1:H42",),
        "pdf_export_execution_authority": False,
    }
    return payload


def _example_response_payload() -> dict[str, Any]:
    return {
        "response_id": "response:event_bridge_finance_response_fixture",
        "event_id": "event_bridge_finance_workflow_action_fixture",
        "correlation_id": "correlation:event_bridge_finance_workflow_action_fixture",
        "route_status": "ROUTE_MATCHED",
        "workflow_status": "WORKFLOW_ACTION_ROUTED",
        "selected_handler_id": "invoice_review_action_request.live_arts_md",
        "operator_copy": "Event Bridge envelope routed without executing a business action.",
        "stale_event": False,
        "receipt_refs": (),
        "machine_proof": {
            "handler_execution_performed": False,
            "pdf_export_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_post_performed": False,
            "workbook_cell_read_performed": False,
            "production_state_mutation_performed": False,
        },
    }


def build_registry_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated = generated_at or utc_now()
    field_rows = _field_semantics_rows()
    profile_rows = _profile_rows()
    rule_rows = _validation_rule_rows()
    device_rows = _device_shard_rows()
    drift_rows = _drift_signal_rows()
    policy_rows = _policy_rows()
    template_rows = _template_rows()
    fixture_rows = _fixture_rows()
    no_browser = next(row for row in field_rows if row["field_name"] == "no_browser")
    browser_allowed = next(row for row in field_rows if row["field_name"] == "browser_access_allowed")
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated,
        "authority_semantics_version": AUTHORITY_SEMANTICS_VERSION,
        "authority_field_semantics": field_rows,
        "authority_profiles": profile_rows,
        "authority_validation_rules": rule_rows,
        "device_authority_shards": device_rows,
        "authority_drift_signals": drift_rows,
        "active_drift_signals": (),
        "authority_remediation_policies": policy_rows,
        "positive_occupation_templates": template_rows,
        "golden_path_fixtures": fixture_rows,
        "positive_replacement_guidance": positive_replacement_guidance(),
        "remediation_doctrine": {
            "detect": "Identify and record unsafe authority patterns early.",
            "block": "Prevent unsafe routing, execution, promotion, readiness, or mutation.",
            "quarantine": "Preserve unsafe payload evidence where policy allows.",
            "fix": "Apply bounded deterministic repair only to generated or derived artifacts.",
            "remove": "Deletion or deprecation requires explicit approval or migration contract.",
            "positive_occupation": "Every blocked unsafe pattern names the correct template, fixture, validation profile, or generated structure.",
            "never_silent_delete": True,
            "never_silent_source_rewrite": True,
            "never_business_mutation_without_receipt": True,
            "never_guess_authority_ambiguity": True,
        },
        "growth_stages": GROWTH_STAGES,
        "drift_types": DRIFT_TYPES,
        "deterministic_drift_outputs": DETERMINISTIC_DRIFT_OUTPUTS,
        "source_code_remediation_policy": {
            "default_response": "PROPOSE_FIX",
            "auto_fix_allowed": False,
            "auto_remove_allowed": False,
            "requires_tests": True,
            "requires_bounded_commit": True,
            "safe_remediation_path": "Propose bounded source-code fixes with tests and commits; do not silently rewrite source truth.",
        },
        "field_semantics_summary": {
            "no_browser_family": no_browser["field_family"],
            "no_browser_true_meaning": no_browser["true_meaning"],
            "browser_access_allowed_family": browser_allowed["field_family"],
            "browser_access_allowed_true_meaning": browser_allowed["true_meaning"],
        },
        "machine_proof": {
            "registry_is_canonical_source": True,
            "generated_artifacts_are_derived": True,
            "no_policy_allows_silent_deletion": all(row["auto_remove_allowed"] is False for row in policy_rows),
            "no_policy_allows_business_mutation_without_receipt": True,
            "positive_templates_seeded": len(template_rows) == 7,
            "required_tables_present": tuple(REQUIRED_SQLITE_TABLES),
            "lm_called": False,
            "services_started": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "workbook_cell_read_performed": False,
            "pdf_export_performed": False,
            "ledger_post_performed": False,
            "production_state_mutation_performed": False,
        },
    }


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple, dict)):
        value = _compact_json(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (list, tuple, dict)):
        return _compact_json(value)
    return value


def sqlite_schema_sql() -> str:
    return """
CREATE TABLE authority_field_semantics (
    field_ref TEXT PRIMARY KEY,
    field_name TEXT NOT NULL,
    field_family TEXT NOT NULL,
    true_meaning TEXT NOT NULL,
    false_meaning TEXT NOT NULL,
    allowed_locations TEXT NOT NULL,
    forbidden_locations TEXT NOT NULL,
    required_for_event_bridge INTEGER NOT NULL CHECK(required_for_event_bridge IN (0, 1)),
    required_for_finance INTEGER NOT NULL CHECK(required_for_finance IN (0, 1)),
    default_value TEXT NOT NULL,
    risk_if_wrong TEXT NOT NULL,
    operator_copy TEXT NOT NULL,
    developer_copy TEXT NOT NULL,
    positive_replacement_field TEXT NOT NULL,
    golden_path_example_ref TEXT NOT NULL
);

CREATE TABLE authority_profile (
    profile_ref TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL,
    applies_to TEXT NOT NULL,
    purpose TEXT NOT NULL,
    required_fields TEXT NOT NULL,
    forbidden_fields TEXT NOT NULL,
    default_deny INTEGER NOT NULL CHECK(default_deny IN (0, 1)),
    receipts_required TEXT NOT NULL,
    dangerous_authorities TEXT NOT NULL,
    allowed_actions TEXT NOT NULL,
    blocked_actions TEXT NOT NULL,
    positive_structure_refs TEXT NOT NULL,
    golden_path_template_ref TEXT NOT NULL
);

CREATE TABLE authority_validation_rule (
    rule_ref TEXT PRIMARY KEY,
    profile_ref TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    growth_stage TEXT NOT NULL,
    remediation TEXT NOT NULL,
    positive_replacement TEXT NOT NULL,
    golden_path_template_ref TEXT NOT NULL
);

CREATE TABLE device_authority_shard (
    device_ref TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    device_class TEXT NOT NULL,
    repo_ref TEXT NOT NULL,
    local_path TEXT NOT NULL,
    authority_profiles TEXT NOT NULL,
    known_limitations TEXT NOT NULL,
    positive_structures_required TEXT NOT NULL,
    last_seen_status TEXT NOT NULL,
    source_refs TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE authority_drift_signal (
    drift_ref TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    field_name TEXT NOT NULL,
    component_ref TEXT NOT NULL,
    profile_ref TEXT NOT NULL,
    drift_type TEXT NOT NULL,
    growth_stage TEXT NOT NULL,
    severity TEXT NOT NULL,
    operator_summary TEXT NOT NULL,
    developer_summary TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    positive_replacement TEXT NOT NULL,
    source_ref TEXT NOT NULL
);

CREATE TABLE authority_remediation_policy (
    policy_ref TEXT PRIMARY KEY,
    drift_type TEXT NOT NULL,
    growth_stage TEXT NOT NULL,
    severity TEXT NOT NULL,
    default_response TEXT NOT NULL,
    auto_fix_allowed INTEGER NOT NULL CHECK(auto_fix_allowed IN (0, 1)),
    auto_remove_allowed INTEGER NOT NULL CHECK(auto_remove_allowed IN (0, 1)),
    quarantine_allowed INTEGER NOT NULL CHECK(quarantine_allowed IN (0, 1)),
    positive_occupation_required INTEGER NOT NULL CHECK(positive_occupation_required IN (0, 1)),
    requires_receipt INTEGER NOT NULL CHECK(requires_receipt IN (0, 1)),
    requires_guardian_review INTEGER NOT NULL CHECK(requires_guardian_review IN (0, 1)),
    requires_operator_approval INTEGER NOT NULL CHECK(requires_operator_approval IN (0, 1)),
    safe_remediation_path TEXT NOT NULL,
    forbidden_remediation TEXT NOT NULL
);

CREATE TABLE positive_occupation_template (
    template_ref TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    applies_to TEXT NOT NULL,
    purpose TEXT NOT NULL,
    replaces_bad_pattern TEXT NOT NULL,
    required_fields TEXT NOT NULL,
    forbidden_fields TEXT NOT NULL,
    example_payload TEXT NOT NULL,
    validation_profile_ref TEXT NOT NULL,
    owner_component TEXT NOT NULL,
    generated_fixture_path TEXT NOT NULL,
    operator_summary TEXT NOT NULL,
    developer_summary TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE golden_path_fixture (
    fixture_ref TEXT PRIMARY KEY,
    template_ref TEXT NOT NULL,
    fixture_name TEXT NOT NULL,
    fixture_kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    expected_validation_status TEXT NOT NULL,
    expected_route TEXT NOT NULL,
    forbidden_side_effects TEXT NOT NULL,
    source_ref TEXT NOT NULL
);
""".lstrip()


def _rows_by_table(payload: Mapping[str, Any]) -> dict[str, tuple[dict[str, Any], ...]]:
    return {
        "authority_field_semantics": tuple(payload["authority_field_semantics"]),
        "authority_profile": tuple(payload["authority_profiles"]),
        "authority_validation_rule": tuple(payload["authority_validation_rules"]),
        "device_authority_shard": tuple(payload["device_authority_shards"]),
        "authority_drift_signal": tuple(payload["authority_drift_signals"]),
        "authority_remediation_policy": tuple(payload["authority_remediation_policies"]),
        "positive_occupation_template": tuple(payload["positive_occupation_templates"]),
        "golden_path_fixture": tuple(payload["golden_path_fixtures"]),
    }


def sqlite_seed_sql(payload: Mapping[str, Any]) -> str:
    statements: list[str] = []
    for table in REQUIRED_SQLITE_TABLES:
        for row in _rows_by_table(payload)[table]:
            columns = list(row)
            statements.append(
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(_sql_literal(row[column]) for column in columns)});"
            )
    return "\n".join(statements) + "\n"


def create_sqlite_registry(payload: Mapping[str, Any], sqlite_path: str | Path) -> None:
    path = Path(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rows_by_table = _rows_by_table(payload)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sqlite_schema_sql())
        for table in REQUIRED_SQLITE_TABLES:
            for row in rows_by_table[table]:
                columns = list(row)
                placeholders = ", ".join("?" for _ in columns)
                connection.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    [_sqlite_value(row[column]) for column in columns],
                )
        connection.commit()
    finally:
        connection.close()


def format_operator_readback(payload: Mapping[str, Any]) -> str:
    summary = payload["field_semantics_summary"]
    templates = payload["positive_occupation_templates"]
    lines = [
        "# OpenClaw Authority Semantics Registry",
        "",
        f"- Status: {payload['contract_status']}",
        f"- Semantics version: {payload['authority_semantics_version']}",
        "- Prohibition flags: `no_* = true` means the action is prohibited.",
        "- Authority grants: `*_allowed = true` means the action is allowed only by the active profile.",
        "- Event Bridge finance profile: safety flags assert prohibitions; authority_boundary carries denied grants.",
        f"- `no_browser`: {summary['no_browser_family']} ({summary['no_browser_true_meaning']})",
        f"- `browser_access_allowed`: {summary['browser_access_allowed_family']} ({summary['browser_access_allowed_true_meaning']})",
        "",
        "## Positive Templates",
    ]
    for template in templates:
        lines.append(f"- `{template['template_ref']}`: {template['purpose']}")
    lines.extend(
        [
            "",
            "## Remediation",
            "",
            "- Unsafe envelopes are blocked before routing.",
            "- Live payloads are not silently rewritten.",
            "- Generated views may be regenerated from this registry.",
            "- Source-code fixes must be proposed as bounded work with tests and commits.",
            "- Business mutation remains blocked without required receipts and authority.",
            "",
            "## Boundary",
            "",
            "- Deterministic registry/export only.",
            "- No service start, Chief run, LM call, email, Gmail, browser, Coupa, workbook read, PDF export, ledger mutation, production mutation, or push.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def export_openclaw_authority_semantics_registry(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], Path, Path, Path, Path, Path]:
    read_root = Path(read_model_root)
    system_root = Path(system_knowledge_root)
    read_root.mkdir(parents=True, exist_ok=True)
    system_root.mkdir(parents=True, exist_ok=True)
    payload = build_registry_payload(generated_at=generated_at)
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_readback(payload), encoding="utf-8")
    schema_path.write_text(sqlite_schema_sql(), encoding="utf-8")
    seed_path.write_text(sqlite_seed_sql(payload), encoding="utf-8")
    create_sqlite_registry(payload, sqlite_path)
    return payload, json_path, operator_path, sqlite_path, schema_path, seed_path


__all__ = [
    "AUTHORITY_GRANT_FIELDS",
    "AUTHORITY_SEMANTICS_VERSION",
    "CONTRACT_STATUS",
    "DANGEROUS_AUTHORITY_GRANTS",
    "DETERMINISTIC_DRIFT_OUTPUTS",
    "DEFAULT_READ_MODEL_ROOT",
    "DEFAULT_SYSTEM_KNOWLEDGE_ROOT",
    "EVENT_BRIDGE_FINANCE_PROFILE_REF",
    "EVENT_BRIDGE_FINANCE_TEMPLATE_REF",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "PROHIBITION_FIELDS",
    "PROHIBITION_TO_GRANT",
    "READ_MODEL_ID",
    "REQUIRED_FALSE_AUTHORITY_GRANTS",
    "REQUIRED_FALSE_SAFETY_FLAGS",
    "REQUIRED_SQLITE_TABLES",
    "REQUIRED_TRUE_SAFETY_FLAGS",
    "SCHEMA_EXPORT_NAME",
    "SCHEMA_VERSION",
    "SEED_EXPORT_NAME",
    "SQLITE_EXPORT_NAME",
    "AuthoritySemanticsValidation",
    "build_registry_payload",
    "create_sqlite_registry",
    "default_safety_flags",
    "denied_authority_boundary",
    "detect_authority_drift",
    "export_openclaw_authority_semantics_registry",
    "format_operator_readback",
    "positive_replacement_guidance",
    "sqlite_schema_sql",
    "sqlite_seed_sql",
    "stable_json",
    "utc_now",
    "validate_authority_semantics",
]
