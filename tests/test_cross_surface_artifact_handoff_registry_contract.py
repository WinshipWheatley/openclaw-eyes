import json
import re
from pathlib import Path

import cross_surface_artifact_handoff_registry_contract as contract
from scripts.export_cross_surface_artifact_handoff_registry_contract import main as export_main


FIXED_NOW = "2026-05-24T17:30:00+00:00"


def _build() -> dict:
    return contract.build_cross_surface_artifact_handoff_registry_contract(generated_at=FIXED_NOW)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["post_office_contract_not_live_bus"] is True
    assert first["doctrine"]["rendered_does_not_mean_sent_or_submitted"] is True
    assert first["doctrine"]["surfaces_are_not_state_owners"] is True


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["cross_surface_artifact_handoff_model_present"] is True
    assert proof["handoff_lifecycle_policy_model_present"] is True
    assert proof["handoff_schema_validation_rule_model_present"] is True
    assert proof["handoff_routing_rule_model_present"] is True
    assert proof["handoff_authority_boundary_model_present"] is True
    assert proof["handoff_privacy_boundary_model_present"] is True
    assert proof["handoff_readback_contract_model_present"] is True
    assert proof["handoff_compatibility_matrix_model_present"] is True
    assert proof["handoff_builder_blocker_model_present"] is True
    assert proof["handoff_post_office_concept_model_present"] is True
    assert schemas["cross_surface_artifact_handoff"]["required_fields"] == list(
        contract.REQUIRED_HANDOFF_FIELDS
    )
    assert schemas["handoff_lifecycle_policy"]["required_fields"] == list(
        contract.REQUIRED_LIFECYCLE_POLICY_FIELDS
    )
    assert schemas["handoff_schema_validation_rule"]["required_fields"] == list(
        contract.REQUIRED_SCHEMA_RULE_FIELDS
    )
    assert schemas["handoff_authority_boundary"]["required_fields"] == list(
        contract.REQUIRED_AUTHORITY_BOUNDARY_FIELDS
    )


def test_lifecycle_states_and_operator_visible_messages_exist():
    payload = _build()
    policy = payload["lifecycle_policy"]

    assert set(policy["allowed_lifecycle_states"]) == set(contract.LIFECYCLE_STATES)
    assert "EMITTED" in policy["operator_visible_states"]
    assert "RECEIVED" in policy["operator_visible_states"]
    assert "WRITTEN" in policy["operator_visible_states"]
    assert "DUPLICATE_NOOP" in policy["operator_visible_states"]
    assert "READBACK_READY" in policy["operator_visible_states"]
    assert "RENDERED" in policy["operator_visible_states"]
    assert "payload hash checks" in policy["below_deck_states"]
    assert payload["machine_proof"]["all_required_lifecycle_states_present"] is True


def test_schema_validation_requires_visual_agnostic_handoff_and_blocks_raw_fields():
    payload = _build()
    rule = payload["schema_validation_rule"]

    assert "workflow_session_ref" in rule["required_fields"]
    assert "artifact_type" in rule["required_fields"]
    assert "schema_ref" in rule["required_fields"]
    assert "idempotency_key" in rule["required_fields"]
    assert "payload_hash" in rule["required_fields"]
    assert "authority_boundary" in rule["required_fields"]
    assert "screen_x" in rule["forbidden_fields"]
    assert "button_frame" in rule["forbidden_fields"]
    assert "swift_view_path" in rule["forbidden_fields"]
    assert "raw_email" in rule["forbidden_fields"]
    assert "raw_po_reference" in rule["forbidden_fields"]
    assert rule["raw_value_forbidden"] is True
    assert rule["validation_failure_state"] == "REJECTED"


def test_capital_hilton_performance_dates_example_exists():
    payload = _build()
    handoff = payload["handoffs_by_id"]["handoff_capital_hilton_performance_dates_capture"]
    route = payload["routing_rules_by_id"]["route_capital_hilton_performance_dates_capture"]
    readback = payload["readbacks_by_id"]["readback_capital_hilton_performance_dates_capture"]

    assert handoff["artifact_type"] == "CAPTURE_REQUEST"
    assert handoff["origin_surface"] == "Mission Control Mac"
    assert handoff["target_handler"] == "mission_control_capture_request_intake"
    assert handoff["block_id"] == "performance_dates"
    assert handoff["operation"] == "add_dates"
    assert route["target_handler"] == handoff["target_handler"]
    assert "add_dates" in route["supported_operations"]
    assert tuple(readback["written_receipt_refs"]) == ("mc_receipt_45620b4bce5c87a6b208",)
    assert "WRITTEN" in readback["lifecycle_transition"]
    assert payload["machine_proof"]["capital_hilton_performance_dates_example_present"] is True


def test_capital_hilton_po_coupa_example_exists_and_does_not_confirm_reference():
    payload = _build()
    handoff = payload["handoffs_by_id"]["handoff_capital_hilton_po_coupa_delivery_facts_capture"]
    route = payload["routing_rules_by_id"]["route_capital_hilton_po_coupa_delivery_facts_capture"]
    readback = payload["readbacks_by_id"]["readback_capital_hilton_po_coupa_delivery_facts"]
    example = payload["examples"]["capital_hilton_po_coupa_delivery_facts_capture"]

    assert handoff["artifact_type"] == "CAPTURE_REQUEST"
    assert handoff["block_id"] == "proof_po_reference"
    assert handoff["operation"] == "set_needs_discovery"
    assert handoff["target_handler"] == "capital_hilton_delivery_facts_capture_writer"
    assert "set_needs_discovery" in route["supported_operations"]
    assert "coupa_login" in route["unsupported_operations"]
    assert "NEEDS_DISCOVERY" in readback["safe_display_summary"]
    assert "no PO/reference falsely confirmed" in example["false_claims_blocked"]
    assert payload["machine_proof"]["capital_hilton_po_coupa_example_present"] is True


def test_reusable_fact_example_references_tokenization_compatibility():
    payload = _build()
    handoff = payload["handoffs_by_id"]["handoff_reusable_fact_tokenized_ap_route"]
    privacy = payload["privacy_boundaries_by_id"]["privacy_boundary_reusable_fact_tokenized"]
    example = payload["examples"]["reusable_fact_handoff"]

    assert handoff["artifact_type"] == "REUSABLE_FACT"
    assert handoff["schema_ref"] == "cross_lane_reusable_block_registry_contract.CrossLaneReusableFactBlock"
    assert tuple(handoff["tokenized_value_refs"]) == ("tokref:local-only:capital_hilton:ap_route:v1",)
    assert privacy["raw_value_allowed"] is False
    assert privacy["tokenized_value_ref_allowed"] is True
    assert privacy["de_tokenization_allowed"] is False
    assert example["raw_value_forbidden"] is True
    assert payload["machine_proof"]["reusable_fact_example_tokenization_compatible"] is True


def test_telegram_cassandra_example_preserves_fronting_role_distinction():
    payload = _build()
    handoff = payload["handoffs_by_id"]["handoff_telegram_cassandra_delivery_facts_entry"]
    example = payload["examples"]["telegram_cassandra_entry"]

    assert handoff["origin_surface"] == "Telegram"
    assert handoff["addressed_actor"] == "Cassandra"
    assert handoff["fronting_agent"] == "Cassandra"
    assert handoff["assigned_role"] == "delivery_readiness_role"
    assert handoff["target_handler"] == "capital_hilton_delivery_facts_capture_writer"
    assert example["workflow_owner"] == "backend receipt/state/readback substrate"
    assert payload["machine_proof"]["telegram_cassandra_fronting_role_distinct"] is True


def test_builder_blockers_exist_for_ui_raw_and_send_gate_cases():
    payload = _build()
    blockers = payload["builder_blockers_by_id"]

    assert blockers["blocker_ui_coupled_payload"]["blocker_type"] == "UI_COUPLED_PAYLOAD"
    assert blockers["blocker_raw_protected_value_in_payload"]["blocker_type"] == "RAW_PROTECTED_VALUE_IN_PAYLOAD"
    assert blockers["blocker_send_ready_without_approval_gate"]["blocker_type"] == (
        "SEND_READY_WITHOUT_APPROVAL_GATE"
    )
    assert blockers["blocker_ui_coupled_payload"]["fail_closed"] is True
    assert blockers["blocker_raw_protected_value_in_payload"]["fail_closed"] is True
    assert blockers["blocker_send_ready_without_approval_gate"]["fail_closed"] is True
    assert "ELIOPERATOR" in blockers["blocker_ui_coupled_payload"]["elioperator_warning"]
    assert payload["machine_proof"]["ui_coupled_payload_blocker_present"] is True
    assert payload["machine_proof"]["raw_protected_payload_blocker_present"] is True
    assert payload["machine_proof"]["send_ready_without_approval_blocker_present"] is True


def test_authority_boundaries_keep_external_actions_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["all_external_authority_flags_false_in_boundaries"] is True
    for value in payload["authority_boundary"].values():
        assert value is False
    for boundary in payload["authority_boundaries_by_id"].values():
        for field in contract.EXTERNAL_AUTHORITY_FIELDS:
            assert boundary[field] is False
    assert payload["authority_boundaries_by_id"]["authority_boundary_performance_dates_capture"][
        "local_receipt_write_allowed"
    ] is True
    assert payload["authority_boundaries_by_id"]["authority_boundary_reusable_fact_preview"][
        "guardian_review_required"
    ] is True


def test_compatibility_matrix_keeps_surfaces_from_owning_truth():
    payload = _build()
    matrix = payload["compatibility_matrix"]

    assert "Mission Control Mac" in matrix["surfaces"]
    assert "Telegram" in matrix["surfaces"]
    assert "Cassandra" in matrix["compatible_agents"]
    assert matrix["workflow_owner"] == "backend receipt/state/readback substrate"
    assert matrix["state_owner"] == "backend receipt/state/readback substrate"
    assert "Mac-only canonical workflow state" in matrix["blocked_split_brain_patterns"]
    assert "Telegram-owned workflow truth" in matrix["blocked_split_brain_patterns"]


def test_post_office_concept_states_no_live_runtime_or_big_bang_rewrite():
    payload = _build()
    concept = payload["post_office_concept"]

    assert "No live bus." in concept["what_it_does_not_do_yet"]
    assert "No file watcher." in concept["what_it_does_not_do_yet"]
    assert "No automatic Mac import." in concept["what_it_does_not_do_yet"]
    assert "one adapter at a time" in concept["migration_strategy"]
    assert "Existing steel-thread adapters keep working" in concept["no_big_bang_rewrite_policy"]


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
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "cross_surface_artifact_handoff_registry_contract.py",
            "scripts/export_cross_surface_artifact_handoff_registry_contract.py",
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
