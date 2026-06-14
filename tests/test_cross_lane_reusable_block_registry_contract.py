import json
import re
from pathlib import Path

import cross_lane_reusable_block_registry_contract as contract
from scripts.export_cross_lane_reusable_block_registry_contract import main as export_main


FIXED_NOW = "2026-05-24T16:30:00+00:00"


def _build() -> dict:
    return contract.build_cross_lane_reusable_block_registry_contract(generated_at=FIXED_NOW)


def _facts(payload: dict) -> dict:
    return payload["reusable_fact_blocks_by_id"]


def _decisions(payload: dict) -> dict:
    return payload["reuse_decisions_by_id"]


def _conflicts(payload: dict) -> dict:
    return payload["conflicts_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["reusable_fact_does_not_mean_raw_value"] is True
    assert first["doctrine"]["tokenized_value_does_not_mean_proof"] is True
    assert first["doctrine"]["calculated_state_must_derive_not_copy"] is True


def test_required_models_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert payload["machine_proof"]["cross_lane_reusable_fact_block_model_present"] is True
    assert payload["machine_proof"]["reusable_fact_scope_model_present"] is True
    assert payload["machine_proof"]["reusable_fact_policy_model_present"] is True
    assert payload["machine_proof"]["protected_value_tokenization_policy_model_present"] is True
    assert payload["machine_proof"]["reusable_fact_reuse_decision_model_present"] is True
    assert payload["machine_proof"]["reusable_fact_conflict_model_present"] is True
    assert payload["machine_proof"]["reusable_fact_impact_preview_model_present"] is True
    assert payload["machine_proof"]["operator_workbench_concept_model_present"] is True
    assert payload["machine_proof"]["handoff_compatibility_model_present"] is True
    assert schemas["cross_lane_reusable_fact_block"]["required_fields"] == list(
        contract.REQUIRED_REUSABLE_FACT_FIELDS
    )
    assert schemas["reusable_fact_scope"]["required_fields"] == list(contract.REQUIRED_SCOPE_FIELDS)
    assert schemas["reusable_fact_policy"]["required_fields"] == list(contract.REQUIRED_POLICY_FIELDS)
    assert schemas["protected_value_tokenization_policy"]["required_fields"] == list(
        contract.REQUIRED_TOKENIZATION_POLICY_FIELDS
    )
    assert schemas["reusable_fact_handoff_compatibility"]["required_fields"] == list(
        contract.REQUIRED_HANDOFF_FIELDS
    )


def test_rate_reuse_is_non_sensitive_and_does_not_copy_subtotal():
    payload = _build()
    facts = _facts(payload)
    rate = facts["fact_capital_hilton_rate_400_show_may_2026"]
    subtotal = facts["fact_invoice_subtotal_calculated_state_blocked_copy"]
    decision = _decisions(payload)["decision_subtotal_copy_blocked"]

    assert rate["value_kind"] == "rate_amount"
    assert rate["value_posture"] == "SAFE_NON_SENSITIVE_VALUE"
    assert rate["raw_value_allowed_in_read_model"] is True
    assert rate["reuse_policy"] == "SUGGEST_APPLY_COMPATIBLE_SCOPE"
    assert "derive" in rate["value_match_ref_policy"]
    assert subtotal["value_kind"] == "calculated_state"
    assert subtotal["reuse_policy"] == "UNKNOWN_FAIL_CLOSED"
    assert decision["decision"] == "BLOCKED_CALCULATED_STATE_COPY"
    assert payload["machine_proof"]["rate_reuse_does_not_copy_subtotal"] is True


def test_ap_email_route_example_uses_tokenized_ref_and_no_raw_email():
    payload = _build()
    ap = _facts(payload)["fact_capital_hilton_ap_route_token_v1"]
    serialized = json.dumps(ap, sort_keys=True)

    assert ap["value_kind"] == "ap_email_route"
    assert ap["value_posture"] == "TOKENIZED_PROTECTED_VALUE"
    assert ap["tokenized_value_ref"].startswith("tokref:")
    assert ap["protected_store_ref"].startswith("pii_vault_ref:")
    assert ap["raw_value_allowed_in_read_model"] is False
    assert ap["central_sync_allowed"] is False
    assert "@" not in serialized
    assert payload["machine_proof"]["ap_route_uses_tokenized_value_ref"] is True


def test_po_reference_example_uses_tokenized_ref_and_no_raw_po():
    payload = _build()
    po = _facts(payload)["fact_capital_hilton_po_reference_token_v1"]
    serialized = json.dumps(po, sort_keys=True).lower()

    assert po["value_kind"] == "po_reference"
    assert po["tokenized_value_ref"].startswith("tokref:")
    assert po["raw_value_allowed_in_read_model"] is False
    assert po["central_sync_allowed"] is False
    assert po["reuse_policy"] == "BLOCK_CROSS_TENANT"
    assert "po-" not in serialized
    assert "payment reference captured" in po["safe_display_label"].lower()
    assert payload["machine_proof"]["po_reference_uses_tokenized_value_ref"] is True


def test_tokenization_policy_blocks_public_hash_and_raw_values():
    payload = _build()
    policy = payload["protected_value_tokenization_policy"]

    assert policy["raw_value_allowed_in_read_model"] is False
    assert policy["public_hash_allowed"] is False
    assert "scoped/keyed local HMAC-style" in policy["value_match_strategy"]
    assert "SHA-256" in policy["value_match_strategy"]
    assert policy["allowed_surfaces_for_raw_value"] in ([], ())
    assert "credentials" in policy["forbidden_material"]
    assert payload["machine_proof"]["public_hash_allowed_false_for_sensitive_values"] is True


def test_scope_blocks_cross_tenant_reuse():
    payload = _build()
    scope = payload["reusable_fact_scope"]
    decision = _decisions(payload)["decision_cross_tenant_po_blocked"]

    assert scope["cross_tenant_reuse_allowed"] is False
    assert decision["decision"] == "BLOCKED_CROSS_TENANT"
    assert "cross-tenant" in decision["privacy_boundary"]
    assert payload["machine_proof"]["cross_tenant_reuse_blocked"] is True


def test_conflict_examples_do_not_expose_raw_protected_values():
    payload = _build()
    conflicts = _conflicts(payload)

    assert conflicts["conflict_rate_400_vs_450"]["conflict_type"] == "VALUE_MISMATCH"
    assert conflicts["conflict_two_ap_route_tokens_disagree"]["conflict_type"] == "TOKENIZED_VALUE_MISMATCH"
    assert conflicts["conflict_two_ap_route_tokens_disagree"]["safe_display_summary"] == "Two AP route tokens disagree."
    assert all(conflict["raw_value_exposed"] is False for conflict in conflicts.values())
    assert payload["machine_proof"]["conflict_example_raw_value_exposed_false"] is True


def test_stale_fact_becomes_inform_only():
    payload = _build()
    decision = _decisions(payload)["decision_prior_year_rate_inform_only"]

    assert decision["decision"] == "INFORM_ONLY"
    assert decision["stale_ref"] == "stale_prior_year_rate_2025"
    assert "context only" in decision["readback_message"]
    assert payload["machine_proof"]["stale_example_inform_only"] is True


def test_protected_evidence_reference_has_raw_body_forbidden():
    payload = _build()
    protected = _facts(payload)["fact_protected_evidence_ref_metadata_only_v1"]

    assert protected["value_kind"] == "protected_evidence_ref"
    assert protected["value_posture"] == "PROTECTED_REFERENCE_ONLY"
    assert protected["raw_value_allowed_in_read_model"] is False
    assert protected["central_sync_allowed"] is False
    assert protected["reuse_policy"] == "REQUIRE_PROOF_OR_GUARDIAN_REVIEW"
    assert payload["machine_proof"]["protected_evidence_raw_body_forbidden"] is True


def test_workbench_concept_and_impact_preview_exist():
    payload = _build()
    workbench = payload["workbench_concept"]
    impact = payload["impact_preview"]

    assert set(workbench["buckets"]) == set(contract.WORKBENCH_BUCKETS)
    assert "low effort" in workbench["sorting_policy"]
    assert impact["suggest_apply_count"] == 2
    assert impact["privacy_blocked_count"] == 1
    assert "low-hanging fruit" in impact["elioperator_summary"]


def test_handoff_compatibility_forbids_raw_values_and_supports_future_agents():
    payload = _build()
    handoff = payload["handoff_compatibility"]
    telegram = payload["examples"]["telegram_cassandra_entry"]

    assert handoff["artifact_type"] == "REUSABLE_FACT"
    assert handoff["workflow_session_ref_required"] is True
    assert handoff["idempotency_key_required"] is True
    assert handoff["payload_hash_required"] is True
    assert handoff["tokenized_value_ref_allowed"] is True
    assert handoff["raw_value_forbidden"] is True
    assert telegram["addressed_actor"] == "Cassandra"
    assert telegram["truth_owner"] == "receipt_backed_backend_state_not_telegram"
    assert telegram["safe_payload_shape"]["raw_value"] == "FORBIDDEN"
    assert payload["machine_proof"]["handoff_forbids_raw_values"] is True


def test_relationship_inventory_verifies_existing_substrate_without_invocation():
    payload = _build()
    substrate = payload["verified_existing_pii_substrate"]

    assert substrate["pii_vault"] is True
    assert substrate["cassandra_pii_hooks"] is True
    assert substrate["business_ops_ledger"] is True
    assert substrate["openclaw_sensitive_policy"] is True
    assert substrate["invoked_or_mutated_by_this_contract"] is False
    assert payload["relationship_inventory"]["CrossSurfaceArtifactHandoffRegistry"]["present"] is False


def test_all_live_authority_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for value in payload["authority_boundary"].values():
        assert value is False


def test_generated_outputs_have_no_raw_pii_or_secret_like_values(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])

    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")
    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_sensitive_fixture_values_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "PO-" not in combined
    assert "PUBLIC_SHA256_OF_RAW_VALUE" not in combined


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "cross_lane_reusable_block_registry_contract.py",
            "scripts/export_cross_lane_reusable_block_registry_contract.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
