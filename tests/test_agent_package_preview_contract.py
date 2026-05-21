import json
from pathlib import Path

import agent_package_preview_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_agent_package_preview_contract import main as export_main


FIXED_NOW = "2026-05-22T00:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "agent_platform_alignment.json": {
            "schema_version": "agent_platform_alignment_v0",
            "read_model_id": "agent_platform_alignment",
        },
        "agent_identity_actor_router_contract.json": {
            "schema_version": "agent_identity_actor_router_contract_v0",
            "read_model_id": "agent_identity_actor_router_contract",
        },
        "model_selection_policy_contract.json": {
            "schema_version": "model_selection_policy_contract_v0",
            "read_model_id": "model_selection_policy_contract",
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
        },
        "capability_skill_registry_metadata_delta.json": {
            "schema_version": "capability_skill_registry_metadata_delta_v0",
            "read_model_id": "capability_skill_registry_metadata_delta",
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "read_model_id": "guardian_protected_access_gate_spec",
        },
        "protected_evidence_reference_receipt.json": {
            "schema_version": "protected_evidence_reference_receipt_v0",
            "read_model_id": "protected_evidence_reference_receipt",
        },
        "cassandra_email_calendar_delta_detangle.json": {
            "schema_version": "cassandra_email_calendar_delta_detangle_v0",
            "read_model_id": "cassandra_email_calendar_delta_detangle",
        },
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "read_model_id": "operator_awareness_agent_package_spine",
        },
        "chief_check_engine_diagnostic_package.json": {
            "schema_version": "chief_check_engine_diagnostic_package_v0",
            "read_model_id": "chief_check_engine_diagnostic_package",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_agent_package_preview_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _examples(payload: dict) -> dict:
    return {item["package_id"]: item for item in payload["example_package_previews"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "agent_package_preview_contract"
    assert first["contract_status"] == "deterministic_package_preview_metadata_only"
    assert first["runtime_authority"] is False
    assert first["model_call_authority"] is False
    assert first["agent_call_authority"] is False
    assert first["tool_execution_authority"] is False
    assert first["external_tool_authority"] is False
    assert first["credential_authority"] is False
    assert first["routing_execution_authority"] is False
    assert first["package_send_authority"] is False
    assert first["operator_final_authority"] is True


def test_package_preview_schema_contains_required_fields_and_sections(tmp_path):
    payload = _build(tmp_path)
    schema = payload["package_preview_schema"]

    assert schema["schema_name"] == "AgentPackagePreview"
    assert schema["required_fields"] == list(contract.REQUIRED_PACKAGE_FIELDS)
    assert schema["sections"] == list(contract.PACKAGE_SECTIONS)
    assert schema["unknown_required_field_fails_closed"] is True
    assert schema["raw_private_bodies_allowed_by_default"] is False
    assert schema["package_preview_is_dispatch"] is False
    for required in [
        "package_id",
        "package_type",
        "proposed_actor_id",
        "proposed_model_class",
        "model_selection_status",
        "included_context_refs",
        "excluded_context_refs",
        "sensitivity_classification",
        "requested_authority",
        "blocked_authority",
        "required_gates",
        "future_pre_action_receipts",
        "future_post_action_receipts",
    ]:
        assert required in payload["required_package_fields"]
    assert [section["section_id"] for section in payload["package_sections"]] == list(contract.PACKAGE_SECTIONS)


def test_actor_and_model_binding_policies_fail_closed(tmp_path):
    payload = _build(tmp_path)
    actor = payload["actor_binding_policy"]
    model = payload["model_binding_policy"]

    assert actor["source_contract"] == "agent_identity_actor_router_contract"
    assert actor["unknown_actor_result"] == "blocked"
    assert actor["actor_may_not_self_assign_authority"] is True
    assert actor["operator_final_authority"] is True
    assert model["source_contract"] == "model_selection_policy_contract"
    assert model["unknown_model_class_result"] == "blocked_no_model"
    assert model["model_may_not_self_select"] is True
    assert model["model_call_allowed_now"] is False
    assert model["blocked_no_model_is_valid"] is True


def test_context_and_sensitivity_boundaries_block_private_raw_inputs(tmp_path):
    payload = _build(tmp_path)
    inclusion = payload["context_inclusion_policy"]
    exclusion = payload["context_exclusion_policy"]
    sensitivity = payload["sensitivity_classification_policy"]

    assert "deterministic read-model refs" in inclusion["allowed_context_forms"]
    assert "receipt IDs" in inclusion["allowed_context_forms"]
    assert inclusion["raw_private_bodies_allowed_by_default"] is False
    assert inclusion["must_use_refs_not_secret_payloads"] is True
    for blocked in [
        "hidden_memory",
        "broad_filesystem_indexing",
        "private_raw_body_ingestion",
        "credential_or_token_inclusion",
        "browser_or_session_cookies",
        "unredacted_client_legal_finance_private_documents",
        "email_calendar_raw_bodies_without_gate",
        "tool_outputs_without_receipts",
    ]:
        assert blocked in exclusion["blocked_categories"]
    assert "Guardian gate" in exclusion["protected_metadata_exception_requires"]
    assert sensitivity["default_for_unknown"] == "unknown_fail_closed"
    assert sensitivity["credential_or_oauth_defaults_to"] == "blocked"
    assert sensitivity["classification_required_before_future_action"] is True


def test_authority_gates_tools_and_receipts_are_non_live(tmp_path):
    payload = _build(tmp_path)
    authority = payload["authority_request_policy"]
    gates = payload["gate_requirements"]
    tools = payload["tool_protocol_preview_policy"]
    receipts = payload["receipt_requirements"]

    assert authority["valid_current_authority"] == ["review_only", "inspect_only", "blocked"]
    assert authority["requested_future_authority_must_be_inactive"] is True
    assert authority["active_authority_never_from_prompt_text"] is True
    for blocked in [
        "model_call",
        "agent_activation",
        "tool_execution",
        "browser_or_portal_use",
        "oauth_or_credential_handling",
        "gmail_email_send",
        "calendar_mutation",
        "coupa_submit_or_approval",
        "telegram_send",
        "autonomous_queue_or_planner_builder",
        "package_dispatch",
    ]:
        assert blocked in authority["blocked_active_authorities"]
    assert "guardian_protected_access_gate" in gates["known_gate_ids"]
    assert "model_selection_policy" in gates["known_gate_ids"]
    assert tools["all_tools_inactive_by_default"] is True
    assert tools["tool_protocols_are_metadata_only"] is True
    assert "OAuth authority" in tools["must_not_imply"]
    assert "package preview receipt" in receipts["future_pre_action_receipts"]
    assert "result receipt" in receipts["future_post_action_receipts"]
    assert receipts["natural_language_success_claim_counts_as_proof"] is False


def test_example_package_previews_cover_required_actor_lanes(tmp_path):
    payload = _build(tmp_path)
    examples = _examples(payload)

    assert set(examples) == {
        "example_codex_backend_read_model_implementation",
        "example_gemini_antigravity_refactor_proof",
        "example_cassandra_capital_hilton_invoice_review",
        "example_guardian_protected_evidence_review",
        "example_niles_struna_tracking_creative",
        "example_hermes_architecture_review",
        "example_chief_check_engine_diagnostic",
    }
    assert examples["example_codex_backend_read_model_implementation"]["proposed_actor_id"] == "codex"
    assert examples["example_gemini_antigravity_refactor_proof"]["proposed_actor_id"] == "gemini_antigravity"
    assert examples["example_cassandra_capital_hilton_invoice_review"]["proposed_actor_id"] == "cassandra"
    assert examples["example_guardian_protected_evidence_review"]["proposed_actor_id"] == "guardian"
    assert examples["example_niles_struna_tracking_creative"]["proposed_actor_id"] == "niles"
    assert examples["example_hermes_architecture_review"]["proposed_actor_id"] == "hermes"
    assert examples["example_chief_check_engine_diagnostic"]["proposed_actor_id"] == "chief"


def test_examples_are_complete_preview_payloads_not_dispatches(tmp_path):
    payload = _build(tmp_path)

    for example in payload["example_package_previews"]:
        for field in contract.REQUIRED_PACKAGE_FIELDS:
            assert field in example
        assert example["current_authority"] in contract.CURRENT_AUTHORITY_STATES
        assert example["model_selection_status"] in {
            "recommended_future_eligible",
            "blocked_no_model",
            "human_operator_only",
            "unknown_fail_closed",
        }
        assert example["sensitivity_classification"] in contract.SENSITIVITY_CLASSES
        assert example["included_context_refs"]
        assert example["excluded_context_refs"]
        assert example["blocked_authority"]
        assert example["required_gates"]
        assert example["expected_outputs"]
        assert example["stop_conditions"]
        assert example["live_dispatch_allowed"] is False
        assert example["model_call_allowed"] is False
        assert example["agent_activation_allowed"] is False
        assert example["tool_execution_allowed"] is False


def test_capital_hilton_preview_blocks_coupa_credentials_and_submission(tmp_path):
    payload = _build(tmp_path)
    capital = _examples(payload)["example_cassandra_capital_hilton_invoice_review"]

    assert capital["package_type"] == "finance_ap_review"
    assert capital["proposed_model_class"] == "local_sensitive"
    assert capital["model_selection_status"] == "blocked_no_model"
    assert capital["current_authority"] == "blocked"
    assert capital["sensitivity_classification"] == "finance_or_ap_sensitive"
    assert "Coupa portal access" in capital["excluded_context_refs"]
    assert "raw Excel/PDF proof bodies" in capital["excluded_context_refs"]
    assert "approval or submit authority" in capital["excluded_context_refs"]
    assert "coupa_submit_or_approval" in capital["blocked_authority"]
    assert "credential_or_oauth_handling" in capital["blocked_authority"]
    assert "guardian_protected_access_gate" in capital["required_gates"]


def test_mission_control_guidance_is_layered_and_non_executing(tmp_path):
    payload = _build(tmp_path)
    guidance = payload["mission_control_surface_guidance"]
    confidence = payload["confidence_policy"]

    assert guidance["top_layer"] == "what would be sent, to whom, and why"
    assert guidance["middle_layer"] == "what context/evidence is included and excluded"
    assert guidance["lower_layer"] == "gates, authority, proof, and receipts"
    assert "live agent presence" in guidance["do_not_present_as"]
    assert "execution button" in guidance["do_not_present_as"]
    assert "command path" in guidance["do_not_present_as"]
    assert confidence["show_confidence_only_when"] == "uncertainty changes the operator's next safe move"
    assert confidence["unknown_context"] == "UNKNOWN_FAIL_CLOSED"
    assert confidence["do_not_display_fake_model_availability"] is True


def test_blocked_package_states_fail_closed(tmp_path):
    payload = _build(tmp_path)
    states = {item["state_id"]: item for item in payload["blocked_package_states"]}

    for state_id in [
        "missing_required_package_field",
        "unknown_actor",
        "unknown_model_class",
        "unknown_sensitivity",
        "raw_private_body_included",
        "credential_or_token_requested",
        "active_tool_protocol_requested",
        "future_authority_marked_active",
        "missing_required_gate",
        "missing_required_receipt",
        "operator_approval_required_but_absent",
    ]:
        assert states[state_id]["current_result"] == "blocked"
        assert states[state_id]["live_dispatch_allowed"] is False


def test_evidence_sources_are_bounded_and_do_not_grant_authority(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    assert sources["agent_platform_alignment"]["present"] is True
    assert sources["agent_identity_actor_router_contract"]["present"] is True
    assert sources["model_selection_policy_contract"]["present"] is True
    assert sources["package_compiler_contract"]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["credentials_or_secrets_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_recommended_next_lanes_match_preview_maturity_path(tmp_path):
    payload = _build(tmp_path)
    lanes = [item["lane_id"] for item in payload["recommended_next_lanes"]]

    assert lanes == [
        "agent_memory_scope_contract_v0",
        "tool_protocol_adapter_registry_v0",
        "model_selection_receipt_v0",
        "mission_control_actor_routing_surface_v0",
        "package_preview_receipt_v0",
    ]


def test_export_script_writes_json_and_operator_outputs(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    exit_code = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            export_root.as_posix(),
            "--format",
            "summary",
        ]
    )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["package_field_count"] == len(contract.REQUIRED_PACKAGE_FIELDS)
    assert summary["package_section_count"] == len(contract.PACKAGE_SECTIONS)
    assert summary["example_count"] == 7
    assert summary["runtime_authority_added"] is False
    assert summary["package_send_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "agent_package_preview_contract"
    assert "Agent Package Preview Contract v0" in operator
    assert "example_cassandra_capital_hilton_invoice_review" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    contract.export_agent_package_preview_contract(
        repo_root=tmp_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_network_or_c_drive_authority_strings():
    text = Path("agent_package_preview_contract.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "import requests",
        "httpx.",
        "urllib.request",
        "/mnt/" + "c/openclaw",
        "c:\\openclaw",
        ".unlink(",
        "shutil.rmtree",
        "shutil.move",
    ]:
        assert token not in text
