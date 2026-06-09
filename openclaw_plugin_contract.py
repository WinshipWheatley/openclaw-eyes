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
    "openclaw.read_only_email_lookup",
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
        "openclaw.read_only_email_lookup": _base_descriptor(
            "openclaw.read_only_email_lookup",
            "Read-only email lookup",
            ["search_fixture_email_metadata", "summarize_fixture_email_evidence"],
            ["send_email", "open_gmail_ui", "open_browser", "delete_email", "archive_email", "mark_email_read", "mutate_contacts"],
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
