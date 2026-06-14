"""Operator Skill Registry v0.

Formal OPERATOR_SKILL_V0 rows for local operator skills. This is a source
registry only: it creates no queue, approval store, dashboard, network call,
or external execution path.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SCHEMA_VERSION = "OPERATOR_SKILL_V0"

LOCAL_LOG_SKILL_ACTION_TYPES = (
    "income_payment_log",
    "expense_log",
    "gig_event_log",
    "identity_signature_preference",
)

_LOCAL_SKILL_ROWS: dict[str, dict[str, Any]] = {
    "income_payment_log": {
        "schema_version": SCHEMA_VERSION,
        "skill_id": "operator_skill:income_payment_log:v0",
        "action_type": "income_payment_log",
        "owner_agent": "cassandra",
        "owner_lane": "cassandra_ar",
        "risk_tier": "low",
        "external": False,
        "required_fields": ["amount", "payer"],
        "optional_fields": ["currency", "invoice/project link", "payment method", "associated_gig_intake_id"],
        "safe_local_action": "record_local_income_payment_receipt",
        "approval_action": None,
        "receipt_schema": "income_payment_log_receipt_v0",
        "watch_desk_lane": "cassandra_ar",
        "push_class": "info",
        "must_not": [
            "mark AR invoice paid",
            "touch Coupa",
            "mutate bank or external ledger",
            "create Gmail draft",
            "send email",
        ],
        "clarify_when": ["amount", "payer"],
        "reference_data_needed": ["payer/client roster", "venue list", "Coupa/portal policy"],
    },
    "expense_log": {
        "schema_version": SCHEMA_VERSION,
        "skill_id": "operator_skill:expense_log:v0",
        "action_type": "expense_log",
        "owner_agent": "cassandra",
        "owner_lane": "cassandra_ar",
        "risk_tier": "low",
        "external": False,
        "required_fields": ["amount", "purchase_label"],
        "optional_fields": ["currency", "vendor", "product_or_service", "category_label", "associated_gig_intake_id"],
        "safe_local_action": "record_local_expense_receipt",
        "approval_action": None,
        "receipt_schema": "expense_log_receipt_v0",
        "watch_desk_lane": "cassandra_ar",
        "push_class": "info",
        "must_not": [
            "give tax advice",
            "store receipt-image body",
            "mutate bank or external ledger",
            "read private payment files",
        ],
        "clarify_when": ["amount", "purchase_label"],
        "reference_data_needed": ["expense categories", "tax category labels"],
    },
    "gig_event_log": {
        "schema_version": SCHEMA_VERSION,
        "skill_id": "operator_skill:gig_event_log:v0",
        "action_type": "gig_event_log",
        "owner_agent": "cassandra",
        "owner_lane": "cassandra_ar",
        "risk_tier": "low",
        "external": False,
        "required_fields": ["venue", "event_date"],
        "optional_fields": ["payment amount", "payer", "setlist_ref", "music_metadata_ref"],
        "safe_local_action": "record_local_gig_event_receipt",
        "approval_action": None,
        "receipt_schema": "gig_event_log_receipt_v0",
        "watch_desk_lane": "niles_creative",
        "push_class": "info",
        "must_not": [
            "write Calendar without approval",
            "create invoice",
            "mark invoice paid",
            "mutate DAW/session/media files",
        ],
        "clarify_when": ["venue", "event_date"],
        "reference_data_needed": ["venue list", "payer/client roster", "music metadata"],
    },
    "identity_signature_preference": {
        "schema_version": SCHEMA_VERSION,
        "skill_id": "operator_skill:identity_signature_preference:v0",
        "action_type": "identity_signature_preference",
        "owner_agent": "chief",
        "owner_lane": "chief_runtime",
        "risk_tier": "low",
        "external": False,
        "required_fields": ["requested_identity"],
        "optional_fields": ["scope", "referent"],
        "safe_local_action": "record_local_identity_preference_stage",
        "approval_action": None,
        "receipt_schema": "identity_signature_preference_receipt_v0",
        "watch_desk_lane": "chief_runtime",
        "push_class": "info",
        "must_not": [
            "apply new outbound identity unsurfaced",
            "change email from-name",
            "reveal Fundo real id",
            "send external message",
        ],
        "clarify_when": ["requested_identity", "referent"],
        "reference_data_needed": ["persona policy", "business entity identity"],
    },
}

REFERENCE_DATA_NEEDS = (
    "rate card",
    "payer/client roster",
    "venue list",
    "expense categories",
    "persona policy",
    "business entity identity",
    "music metadata",
    "Coupa/portal policy",
    "tax category labels",
)


def operator_skill_rows() -> list[dict[str, Any]]:
    return [deepcopy(_LOCAL_SKILL_ROWS[action_type]) for action_type in LOCAL_LOG_SKILL_ACTION_TYPES]


def get_operator_skill(action_type: str) -> dict[str, Any]:
    row = _LOCAL_SKILL_ROWS.get(action_type)
    if row is not None:
        return deepcopy(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "skill_id": f"operator_skill:unknown:{action_type or 'empty'}:blocked",
        "action_type": action_type,
        "owner_agent": "guardian",
        "owner_lane": "guardian_approval",
        "risk_tier": "high",
        "external": True,
        "required_fields": [],
        "optional_fields": [],
        "safe_local_action": "",
        "approval_action": None,
        "receipt_schema": "unknown_operator_skill_receipt_v0",
        "watch_desk_lane": "guardian_approval",
        "push_class": "failure",
        "must_not": ["execute unknown operator skill", "default unknown action to low risk"],
        "clarify_when": ["action_type"],
        "reference_data_needed": [],
        "blocked": True,
    }


def operator_skill_reference_data_needs_manifest() -> dict[str, Any]:
    return {
        "schema_version": "operator_skill_reference_data_needs_v0",
        "purpose": "Safe placeholders for Data Room items needed by OPERATOR_SKILL_V0 rows.",
        "private_data_ingested": False,
        "secrets_requested": False,
        "raw_bank_tax_legal_docs_ingested": False,
        "private_music_media_session_files_ingested": False,
        "missing_reference_data": list(REFERENCE_DATA_NEEDS),
        "skills": {
            row["action_type"]: {
                "skill_id": row["skill_id"],
                "reference_data_needed": list(row["reference_data_needed"]),
            }
            for row in operator_skill_rows()
        },
    }
