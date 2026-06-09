"""OPENCLAW_PLUGIN_CONTRACT_V0 fixture validator.

This module validates repo-local fixture descriptors only. It does not create a
Codex plugin, invoke tools, open browsers, access Gmail/Coupa, send, submit,
mark paid, mutate ledgers, or enable production side effects.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping


SCHEMA_VERSION = "OPENCLAW_PLUGIN_CONTRACT_V0"

FIXTURE_PLUGIN_IDS = (
    "openclaw.google_workspace_broker",
    "openclaw.read_only_email_lookup",
    "openclaw.gmail_metadata_read",
    "openclaw.gmail_body_read",
    "openclaw.gmail_draft_generator",
    "openclaw.gmail_send_mail",
    "openclaw.contacts_readonly_lookup",
    "openclaw.calendar_event_manager",
    "openclaw.follow_up_draft_generator",
    "openclaw.contact_identity_extraction",
    "openclaw.payment_uncertainty_summarizer",
    "openclaw.verifier_proof_checker",
)

REQUIRED_FIELDS = (
    "schema_version",
    "plugin_id",
    "capability_id",
    "allowed_actions",
    "denied_actions",
    "required_authority",
    "run_mode_behavior",
    "test_mode_behavior",
    "production_behavior",
    "proof_outputs",
    "receipt_requirements",
    "verifier_rules",
    "redaction_policy",
    "freshness_policy",
    "failure_modes",
    "active_next_step_on_failure",
    "package_targets",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _base_descriptor(plugin_id: str, label: str, allowed_actions: list[str], denied_actions: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": plugin_id,
        "plugin_label": label,
        "capability_id": plugin_id,
        "allowed_actions": allowed_actions,
        "denied_actions": denied_actions,
        "required_authority": {
            "authority_profile_ref": f"authority.{plugin_id}.scoped",
            "requires_explicit_operator_grant": True,
            "raw_authority_granted_trusted": False,
            "authority_defaults_false": True,
        },
        "run_mode_behavior": {
            "dry_run": "fixture-only validation",
            "shadow": "no side effects",
            "live": "blocked unless later separate authority exists",
        },
        "test_mode_behavior": {
            "uses_fixtures": True,
            "writes_test_artifacts_only": True,
            "external_side_effects_allowed": False,
        },
        "production_behavior": {
            "requires_authority_grant": True,
            "requires_freshness_check": True,
            "requires_receipts": True,
            "side_effects_default_denied": True,
            "production_side_effects_allowed": False,
        },
        "proof_outputs": [
            {"proof_type": "redacted_fixture_receipt", "path_or_ref_policy": "receipt_ref", "operator_visible": "details"}
        ],
        "receipt_requirements": [
            {"receipt_type": "fixture_validation_receipt", "required": True, "verifier": "openclaw.plugin_contract_validator"}
        ],
        "verifier_rules": [
            {
                "rule_id": "deny_by_default",
                "description": "Production side effects and raw text authority are denied by default.",
                "fail_closed": True,
                "active_next_step_on_failure": "Review the descriptor scope.",
            }
        ],
        "redaction_policy": {
            "policy_ref": "proof_bundle_redaction_policy_v0",
            "forbidden_material": ["secrets", "raw_email_bodies", "client_private_body_dumps"],
            "secret_handling": "never include; reference only by scoped receipt",
        },
        "freshness_policy": {
            "freshness_requirement": "fixture",
            "stale_behavior": "block",
            "source_timestamp_fields": ["fixture_generated_at"],
        },
        "failure_modes": [
            {"failure_id": "missing_authority", "operator_message": "Capability remains blocked.", "machine_code": "FAIL_CLOSED"}
        ],
        "active_next_step_on_failure": "Review the descriptor scope.",
        "package_targets": ["deterministic_python_adapter", "codex_skill_candidate", "mcp_tool_bridge_candidate"],
    }


def fixture_descriptors() -> dict[str, dict[str, Any]]:
    descriptors = {
        "openclaw.google_workspace_broker": _base_descriptor(
            "openclaw.google_workspace_broker",
            "Google Workspace broker",
            ["request_task_specific_authority_envelope", "request_scoped_credential_lease", "emit_redacted_receipt"],
            [
                "ambient_mailbox_scan",
                "google_workspace_broker_ambient_use",
                "send_email",
                "create_email_draft",
                "delete_email",
                "archive_email",
                "mark_email_read",
                "mutate_contacts",
                "promote_contact_memory",
                "calendar_mutation_without_calendar_authority",
                "mark_paid",
                "mutate_ledger",
                "coupa_submit",
            ],
        ),
        "openclaw.read_only_email_lookup": _base_descriptor(
            "openclaw.read_only_email_lookup",
            "Read-only email lookup",
            ["search_fixture_email_metadata", "summarize_fixture_email_evidence"],
            [
                "compose_email",
                "send_email",
                "create_email_draft",
                "open_gmail_ui",
                "open_browser",
                "delete_email",
                "archive_email",
                "mark_email_read",
                "mutate_contacts",
                "promote_contact_memory",
                "calendar_access",
                "contacts_read",
            ],
        ),
        "openclaw.gmail_metadata_read": _base_descriptor(
            "openclaw.gmail_metadata_read",
            "Gmail metadata read",
            ["scoped_gmail_metadata_search", "emit_redacted_metadata_receipt"],
            [
                "read_raw_email_body_without_body_authority",
                "compose_email",
                "send_email",
                "create_email_draft",
                "delete_email",
                "archive_email",
                "mark_email_read",
                "mutate_contacts",
                "calendar_access",
            ],
        ),
        "openclaw.gmail_body_read": _base_descriptor(
            "openclaw.gmail_body_read",
            "Gmail body read",
            ["bounded_gmail_body_read", "emit_redacted_body_receipt"],
            [
                "ambient_mailbox_scan",
                "compose_email",
                "send_email",
                "create_email_draft",
                "delete_email",
                "archive_email",
                "mark_email_read",
                "mutate_contacts",
                "calendar_access",
            ],
        ),
        "openclaw.gmail_draft_generator": _base_descriptor(
            "openclaw.gmail_draft_generator",
            "Gmail draft generator",
            ["create_review_only_gmail_draft", "emit_draft_receipt"],
            [
                "send_email",
                "gmail_send_without_send_authority",
                "delete_email",
                "archive_email",
                "mark_email_read",
                "mutate_contacts",
                "calendar_access",
                "mark_paid",
                "mutate_ledger",
                "coupa_submit",
            ],
        ),
        "openclaw.gmail_send_mail": _base_descriptor(
            "openclaw.gmail_send_mail",
            "Gmail send mail",
            ["prepare_class_c_send_authority_packet"],
            [
                "send_email",
                "send_without_class_c_authority",
                "send_without_operator_review",
                "delete_email",
                "archive_email",
                "mark_email_read",
                "mutate_contacts",
                "calendar_access",
                "mark_paid",
                "mutate_ledger",
                "coupa_submit",
            ],
        ),
        "openclaw.contacts_readonly_lookup": _base_descriptor(
            "openclaw.contacts_readonly_lookup",
            "Contacts read-only lookup",
            ["scoped_contacts_readonly_lookup", "emit_redacted_contact_receipt"],
            [
                "mutate_contacts",
                "promote_contact_memory",
                "contact_memory_promotion",
                "send_email",
                "create_email_draft",
                "calendar_access",
                "mark_paid",
                "mutate_ledger",
                "coupa_submit",
            ],
        ),
        "openclaw.calendar_event_manager": _base_descriptor(
            "openclaw.calendar_event_manager",
            "Calendar event manager",
            ["classify_calendar_event_action", "emit_calendar_action_split_receipt"],
            [
                "calendar_write_without_action_authority",
                "calendar_delete_without_action_authority",
                "calendar_mutation_without_calendar_authority",
                "send_email",
                "create_email_draft",
                "mutate_contacts",
                "mark_paid",
                "mutate_ledger",
                "coupa_submit",
            ],
        ),
        "openclaw.follow_up_draft_generator": _base_descriptor(
            "openclaw.follow_up_draft_generator",
            "Follow-up draft generator",
            ["generate_draft_text"],
            ["send_email", "add_recipients_silently", "open_gmail_ui", "submit", "mark_paid", "mutate_ledger"],
        ),
        "openclaw.contact_identity_extraction": _base_descriptor(
            "openclaw.contact_identity_extraction",
            "Contact identity extraction",
            ["extract_candidate_contact_from_fixture"],
            ["gmail_lookup", "mutate_contacts", "promote_contact_memory", "infer_identity_without_proof"],
        ),
        "openclaw.payment_uncertainty_summarizer": _base_descriptor(
            "openclaw.payment_uncertainty_summarizer",
            "Payment uncertainty summarizer",
            ["summarize_known_assumed_proof_needed"],
            ["mark_paid", "mutate_ledger", "claim_check_received_without_proof", "confirm_payment_without_proof"],
        ),
        "openclaw.verifier_proof_checker": _base_descriptor(
            "openclaw.verifier_proof_checker",
            "Verifier proof checker",
            ["validate_fixture_proof_packet"],
            ["trust_raw_authority_granted", "accept_unredacted_secret", "enable_production_side_effects"],
        ),
    }
    descriptors["openclaw.google_workspace_broker"].update(
        {
            "credential_backed": True,
            "policy_gated": True,
            "not_ambient_production_use": True,
            "actor_policy_restrictions": {
                "policy_gated_actors": ["cassandra"],
                "denied_actors": ["chief"],
                "notes": "Existing Chief/Cassandra boundaries are preserved for this fixture.",
            },
        }
    )
    for capability_id in (
        "openclaw.google_workspace_broker",
        "openclaw.gmail_metadata_read",
        "openclaw.gmail_body_read",
        "openclaw.gmail_draft_generator",
        "openclaw.gmail_send_mail",
        "openclaw.contacts_readonly_lookup",
        "openclaw.calendar_event_manager",
    ):
        descriptors[capability_id]["required_authority"].update(
            {
                "requires_task_specific_authority_envelope": True,
                "requires_credential_lease": True,
                "credential_handle_existence_implies_use_authority": False,
            }
        )
        descriptors[capability_id]["policy_gated"] = True
        descriptors[capability_id]["credential_candidates"] = ["credential.google_workspace_broker.current"]
        descriptors[capability_id]["live_lookup_enabled_by_default"] = False

    descriptors["openclaw.read_only_email_lookup"].update(
        {
            "policy_gated": True,
            "credential_candidates": [
                "future_dedicated_readonly_gmail_credential",
                "credential.google_workspace_broker.current",
            ],
            "credential_candidate_relationships": {
                "future_dedicated_readonly_gmail_credential": "preferred_dedicated_readonly_only_material_when_available",
                "credential.google_workspace_broker.current": "candidate_dependency_only_scoped_readonly_lease_required",
            },
            "live_lookup_enabled_by_default": False,
        }
    )
    descriptors["openclaw.read_only_email_lookup"]["required_authority"].update(
        {
            "requires_task_specific_authority_envelope": True,
            "requires_credential_lease": True,
            "credential_handle_existence_implies_use_authority": False,
        }
    )
    return {key: copy.deepcopy(value) for key, value in descriptors.items()}


def validate_descriptor(descriptor: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in descriptor:
            errors.append(f"missing required field: {field}")
    if descriptor.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be OPENCLAW_PLUGIN_CONTRACT_V0")
    plugin_id = str(descriptor.get("plugin_id") or "")
    if plugin_id not in FIXTURE_PLUGIN_IDS:
        errors.append("plugin_id must be a known fixture descriptor id")
    if not descriptor.get("denied_actions"):
        errors.append("denied_actions must be explicit and non-empty")
    authority = descriptor.get("required_authority")
    if not isinstance(authority, Mapping):
        errors.append("required_authority must be present")
    else:
        if authority.get("raw_authority_granted_trusted") is not False:
            errors.append("raw_authority_granted_trusted must be false")
        if authority.get("authority_defaults_false") is not True:
            errors.append("authority_defaults_false must be true")
    production = descriptor.get("production_behavior")
    if not isinstance(production, Mapping):
        errors.append("production_behavior must be present")
    else:
        if production.get("side_effects_default_denied") is not True:
            errors.append("production side effects must default denied")
        if production.get("production_side_effects_allowed") is not False:
            errors.append("production side effects must not be allowed in fixtures")
    for field in ("receipt_requirements", "verifier_rules", "redaction_policy", "freshness_policy", "active_next_step_on_failure"):
        if not descriptor.get(field):
            errors.append(f"{field} is required")
    return errors


def validate_fixture_descriptors() -> dict[str, Any]:
    descriptors = fixture_descriptors()
    results = {plugin_id: validate_descriptor(descriptor) for plugin_id, descriptor in descriptors.items()}
    return {
        "schema_version": SCHEMA_VERSION,
        "descriptor_count": len(descriptors),
        "validated_plugin_ids": sorted(descriptors),
        "valid": all(not errors for errors in results.values()),
        "errors": results,
    }
