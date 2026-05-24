import json
import re
from pathlib import Path

import agent_execution_packet_compiler_contract as contract
from scripts.export_agent_execution_packet_compiler_contract import main as export_main


FIXED_NOW = "2026-05-23T22:00:00+00:00"


def _build() -> dict:
    return contract.build_agent_execution_packet_compiler_contract(generated_at=FIXED_NOW)


def _packets(payload: dict) -> dict:
    return payload["execution_packets_by_id"]


def _compilers(payload: dict) -> dict:
    return payload["compilers_by_id"]


def _contexts(payload: dict) -> dict:
    return payload["context_policies_by_id"]


def _capabilities(payload: dict) -> dict:
    return payload["capability_policies_by_id"]


def _returns(payload: dict) -> dict:
    return payload["return_shapes_by_id"]


def _chains(payload: dict) -> dict:
    return payload["packet_chains_by_id"]


def _hints(payload: dict) -> dict:
    return payload["operator_context_hints_by_id"]


def _upstream(payload: dict) -> dict:
    return payload["upstream_substrate_context_selection_refs_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["systems_engineering_not_vibes"] is True
    assert first["doctrine"]["packet_is_assignment_not_authority"] is True
    assert first["doctrine"]["no_runtime_compiler_implemented"] is True
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_implement_live_execution"] is True
    assert first["hard_rule"]["does_not_call_models"] is True
    assert first["hard_rule"]["does_not_run_tools_mcps_scripts_hooks"] is True
    assert first["hard_rule"]["does_not_write_receipts"] is True
    assert first["hard_rule"]["does_not_mutate_workflow_state"] is True
    assert first["hard_rule"]["may_grant_authority"] is False


def test_existing_build_boundary_acknowledges_context_selection_substrate():
    payload = _build()
    boundary = payload["existing_build_boundary"]

    assert boundary["inspected_existing_substrate"] == "context_selection_knowledge_packet_v0"
    assert boundary["structured_upstream_ref"] == "context_selection_knowledge_packet_v0"
    assert boundary["upstream_classification"] == "UPSTREAM_SUBSTRATE_CONTEXT_SELECTION"
    assert set(boundary["future_packet_compiler_may_consume"]) == {
        "allowed_context_refs",
        "read_model_refs",
        "source_card_refs",
        "proof_refs",
    }
    assert boundary["does_not_replace_context_selection"] is True
    assert boundary["does_not_mutate_context_selection"] is True
    assert boundary["does_not_replace_handoff_contract"] is True
    assert boundary["does_not_build_runtime_compiler"] is True
    assert payload["machine_proof"]["inspected_existing_context_selection_substrate"] is True
    assert payload["machine_proof"]["does_not_duplicate_existing_context_selection"] is True
    assert payload["machine_proof"]["does_not_replace_existing_context_selection"] is True
    assert payload["machine_proof"]["does_not_mutate_existing_context_selection"] is True
    assert "context_selection_knowledge_packet_v0_existing_substrate" in payload["relationship_refs"]


def test_upstream_context_selection_ref_is_structured_substrate_only():
    payload = _build()
    upstream = _upstream(payload)["context_selection_knowledge_packet_v0"]

    assert payload["upstream_substrate_context_selection_ref_schema"]["required_fields"] == list(
        contract.REQUIRED_UPSTREAM_CONTEXT_SELECTION_FIELDS
    )
    assert upstream["display_name"] == "Context Selection / Knowledge Packet v0"
    assert upstream["classification"] == "UPSTREAM_SUBSTRATE_CONTEXT_SELECTION"
    assert upstream["source_module_ref"] == "context_selection.py"
    assert upstream["source_read_model_ref"] == "generated/read_models/context_selection.json"
    assert upstream["source_operator_read_model_ref"] == "generated/read_models/context_selection_OPERATOR.md"
    assert {
        "allowed_context_refs",
        "read_model_refs",
        "source_card_refs",
        "proof_refs",
    } <= set(upstream["consumable_ref_types"])
    assert "AgentExecutionPacket.allowed_context_refs" in upstream["consumed_by_contract_fields"]
    assert "PacketContextSelectionPolicy.read_model_refs_allowed" in upstream["consumed_by_contract_fields"]
    assert "PacketContextSelectionPolicy.source_card_refs_allowed" in upstream["consumed_by_contract_fields"]
    assert "PacketContextSelectionPolicy.proof_refs_allowed" in upstream["consumed_by_contract_fields"]
    assert upstream["may_supply_allowed_context_refs"] is True
    assert upstream["may_supply_read_model_refs"] is True
    assert upstream["may_supply_source_card_refs"] is True
    assert upstream["may_supply_proof_refs"] is True
    assert upstream["may_grant_tool_authority"] is False
    assert upstream["may_grant_runtime_authority"] is False
    assert upstream["may_execute_packets"] is False
    assert upstream["may_mutate_workflow_state"] is False
    assert upstream["may_mutate_old_compiler"] is False
    assert upstream["is_replaced_by_this_contract"] is False
    assert upstream["is_duplicated_by_this_contract"] is False
    for value in upstream["authority_boundary"].values():
        assert value is False
    assert payload["machine_proof"]["upstream_compiler_referenced"] is True
    assert payload["machine_proof"]["upstream_compiler_classified_as_substrate_context_selection"] is True
    assert payload["machine_proof"]["upstream_compiler_sources_required_refs"] is True
    assert payload["machine_proof"]["upstream_compiler_grants_no_tool_runtime_execution_authority"] is True


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["agent_execution_packet_model_present"] is True
    assert payload["machine_proof"]["agent_execution_packet_compiler_model_present"] is True
    assert payload["machine_proof"]["packet_context_selection_policy_model_present"] is True
    assert payload["machine_proof"]["packet_capability_selection_policy_model_present"] is True
    assert payload["machine_proof"]["agent_packet_return_shape_model_present"] is True
    assert payload["machine_proof"]["agent_packet_chain_model_present"] is True
    assert payload["machine_proof"]["operator_context_hint_model_present"] is True
    assert payload["machine_proof"]["upstream_context_selection_ref_count"] == 1
    assert payload["agent_execution_packet_schema"]["required_fields"] == list(contract.REQUIRED_EXECUTION_PACKET_FIELDS)
    assert payload["agent_execution_packet_compiler_schema"]["required_fields"] == list(contract.REQUIRED_COMPILER_FIELDS)
    assert payload["packet_context_selection_policy_schema"]["required_fields"] == list(contract.REQUIRED_CONTEXT_POLICY_FIELDS)
    assert payload["packet_capability_selection_policy_schema"]["required_fields"] == list(contract.REQUIRED_CAPABILITY_POLICY_FIELDS)
    assert payload["agent_packet_return_shape_schema"]["required_fields"] == list(contract.REQUIRED_RETURN_SHAPE_FIELDS)
    assert payload["agent_packet_chain_schema"]["required_fields"] == list(contract.REQUIRED_PACKET_CHAIN_FIELDS)
    assert payload["operator_context_hint_schema"]["required_fields"] == list(contract.REQUIRED_OPERATOR_HINT_FIELDS)
    assert set(payload["packet_types"]) == set(contract.PACKET_TYPES)
    assert set(payload["compile_triggers"]) == set(contract.COMPILE_TRIGGERS)
    assert set(payload["context_categories"]) == set(contract.CONTEXT_CATEGORIES)
    assert set(payload["capability_categories"]) == set(contract.CAPABILITY_CATEGORIES)


def test_capital_hilton_dates_packet_is_narrow_and_non_executing():
    payload = _build()
    packet = _packets(payload)["capital_hilton_performance_dates_execution_packet"]
    compiler = _compilers(payload)["capital_hilton_performance_dates_packet_compiler"]

    assert set(contract.REQUIRED_EXECUTION_PACKET_FIELDS) <= set(packet)
    assert packet["packet_type"] == "BLOCK_FILL"
    assert packet["block_ref"] == "performance_dates"
    assert packet["packet_objective"].startswith("Normalize added performance dates")
    assert "current candidate dates" in packet["allowed_context_refs"]
    assert "active local draft" in packet["allowed_context_refs"]
    assert "whole-system context" in packet["excluded_context_refs"]
    assert "RAW_PRIVATE_BODY" in packet["excluded_context_refs"]
    assert packet["allowed_tools"] == ()
    assert "email or Telegram send" not in packet["allowed_tools"]
    assert "tool execution" in packet["blocked_tools"]
    assert packet["expected_return_shape_ref"] == "normalized_field_update_return_shape"
    assert compiler["compile_trigger"] == "BLOCK_BECAME_ACTIVE"
    assert compiler["compiled_packet_refs"] == ("capital_hilton_performance_dates_execution_packet",)
    assert payload["machine_proof"]["capital_hilton_dates_example_present"] is True


def test_capital_hilton_po_proof_packet_blocks_live_coupa_browser_credentials():
    payload = _build()
    packet = _packets(payload)["capital_hilton_po_proof_discovery_execution_packet"]
    policy = _capabilities(payload)["proof_discovery_capability_policy"]

    assert packet["packet_type"] == "PROOF_DISCOVERY"
    assert packet["block_ref"] == "proof_po_reference"
    assert "source cards if available" in packet["allowed_context_refs"]
    assert "Coupa live access" in packet["excluded_context_refs"]
    assert "browser automation" in packet["excluded_context_refs"]
    assert "credentials" in packet["excluded_context_refs"]
    assert "Coupa portal MCP" in packet["blocked_mcp_refs"]
    assert "portal scraping scripts" in packet["blocked_script_refs"]
    assert policy["allowed_capability_categories"] == ("SOURCE_CARD_LOOKUP", "PROOF_REF_LOOKUP", "READ_ONLY_CONTEXT_QUERY")
    assert "COUPA_PORTAL_ACCESS" in policy["blocked_capability_categories"]
    assert "BROWSER_AUTOMATION" in policy["blocked_capability_categories"]
    assert "CREDENTIAL_ACCESS" in policy["blocked_capability_categories"]
    assert payload["machine_proof"]["capital_hilton_po_proof_example_present"] is True


def test_invoice_preview_packet_models_future_gate_without_rendering():
    payload = _build()
    packet = _packets(payload)["capital_hilton_invoice_preview_execution_packet"]
    policy = _capabilities(payload)["artifact_preview_capability_policy"]
    shape = _returns(payload)["artifact_preview_prep_return_shape"]

    assert packet["packet_type"] == "ARTIFACT_PREVIEW_PREP"
    assert packet["block_state"] == "future_gate_required"
    assert "invoice generator scripts" in packet["blocked_script_refs"]
    assert "file write path" in packet["excluded_context_refs"]
    assert policy["allowed_capability_categories"] == ("INVOICE_PREVIEW_RENDER",)
    assert "invoice_preview_render_allowed future gate" in policy["authority_required"]
    assert policy["operator_approval_required"] is True
    assert policy["guardian_gate_required"] is True
    assert "invoice_generated" in shape["rejected_result_types"]
    assert "file_written" in shape["rejected_result_types"]
    assert payload["authority_boundary"]["invoice_preview_render_allowed"] is False
    assert payload["machine_proof"]["invoice_preview_example_present"] is True


def test_telegram_cassandra_request_chain_is_progressive_and_send_blocked():
    payload = _build()
    chain = _chains(payload)["telegram_cassandra_invoice_request_packet_chain"]
    compiler = _compilers(payload)["telegram_cassandra_invoice_request_chain_compiler"]

    assert chain["originating_request"] == "Send Capital Hilton an invoice for this week's and last week's job."
    assert chain["packet_sequence"][0] == "telegram_cassandra_invoice_intent_execution_packet"
    assert "capital_hilton_performance_dates_execution_packet" in chain["packet_sequence"]
    assert "capital_hilton_invoice_preview_execution_packet" in chain["packet_sequence"]
    assert "send_packet_blocked_future" in chain["blocked_packet_refs"]
    assert "capital_hilton_missing_dates_operator_handoff" in chain["pending_operator_handoff_refs"]
    assert "never one huge packet" in chain["context_budget_strategy"]
    assert compiler["packet_selection_policy"] == "dispatch multiple focused packets rather than one huge packet"
    assert "send packet rejected because send authority false" in compiler["rejected_packet_reasons"]
    assert payload["machine_proof"]["telegram_cassandra_chain_example_present"] is True
    assert payload["machine_proof"]["multi_step_chain_present"] is True


def test_chief_check_engine_packet_blocks_repair_shell_and_broad_scan():
    payload = _build()
    packet = _packets(payload)["chief_check_engine_diagnostic_execution_packet"]
    compiler = _compilers(payload)["chief_check_engine_packet_compiler"]

    assert packet["packet_type"] == "CHIEF_DIAGNOSTIC"
    assert "current read-model/test refs only" in packet["packet_objective"]
    assert "broad private scan" in packet["excluded_context_refs"]
    assert "repair execution" in packet["excluded_context_refs"]
    assert "shell execution" in packet["blocked_tools"]
    assert "broad scan" in packet["blocked_tools"]
    assert "repair scripts" in packet["blocked_script_refs"]
    assert compiler["compile_trigger"] == "CHECK_ENGINE_REQUESTED"
    assert "repair execution blocked" in compiler["rejected_packet_reasons"]
    assert payload["machine_proof"]["chief_check_engine_example_present"] is True


def test_context_selection_policy_excludes_raw_private_and_protected_by_default():
    payload = _build()

    assert payload["packet_context_selection_policy_schema"]["raw_private_bodies_false_by_default"] is True
    assert payload["packet_context_selection_policy_schema"]["protected_context_requires_future_gate"] is True
    for policy in payload["context_policies"]:
        assert policy["raw_body_allowed"] is False
        assert policy["protected_context_allowed"] is False
        assert "RAW_PRIVATE_BODY" in policy["exclude_context_categories"]
    assert payload["machine_proof"]["raw_private_body_excluded_by_default"] is True
    assert payload["machine_proof"]["protected_context_requires_future_gate"] is True


def test_capability_policy_lists_allowed_and_blocked_capabilities_without_authority():
    payload = _build()

    assert payload["packet_capability_selection_policy_schema"]["tools_are_capabilities_not_authority"] is True
    assert payload["packet_capability_selection_policy_schema"]["blocked_categories_explicit"] is True
    assert payload["packet_capability_selection_policy_schema"]["executes_capability_in_this_contract"] is False
    for policy in payload["capability_policies"]:
        assert policy["blocked_capability_categories"]
        assert policy["allowed_tools"] == ()
        assert policy["allowed_mcp_refs"] == ()
        assert policy["allowed_script_refs"] == ()
        assert policy["allowed_hook_refs"] == ()
    assert payload["machine_proof"]["packets_include_allowed_and_blocked_capabilities"] is True


def test_return_shape_rejects_freeform_only_and_execution_claims():
    payload = _build()

    assert payload["agent_packet_return_shape_schema"]["freeform_prose_alone_sufficient"] is False
    assert payload["agent_packet_return_shape_schema"]["ambiguity_flags_required_when_unsure"] is True
    assert payload["agent_packet_return_shape_schema"]["agent_may_request_next_packet"] is True
    assert payload["agent_packet_return_shape_schema"]["agent_may_claim_execution_done_without_authority"] is False
    for shape in payload["return_shapes"]:
        assert "freeform_only" in shape["rejected_result_types"]
        assert shape["completion_status_values"] == contract.COMPLETION_STATUSES
    assert payload["machine_proof"]["return_shapes_reject_freeform_only"] is True


def test_operator_context_hint_is_compact_non_patronizing_and_supportive():
    payload = _build()
    hint = _hints(payload)["operator_context_hint_winship"]
    support = _packets(payload)["operator_out_of_depth_support_packet"]

    assert "music production" in hint["strong_domains"]
    assert "finance/AP/Coupa" in hint["weaker_or_context_dependent_domains"]
    assert "studio signal-flow analogy" in hint["preferred_explanation_modes"]
    assert "do not patronize" in hint["support_style"]
    assert "include compact hints by default" in hint["support_style"]
    assert hint["include_by_default"] is True
    assert hint["deeper_support_packet_ref"] == "operator_out_of_depth_support_packet"
    assert "personal dossier" in support["excluded_context_refs"]
    assert "do not assume ignorance" in support["validation_requirements"]
    assert payload["operator_context_hint_schema"]["do_not_flood_personal_dossier"] is True
    assert payload["operator_context_hint_schema"]["unfamiliar_domain_support_becomes_workflow_options"] is True
    assert payload["machine_proof"]["out_of_depth_support_example_present"] is True
    assert payload["machine_proof"]["operator_context_hint_compact_non_patronizing"] is True


def test_relationship_refs_and_starship_alignment_exist():
    payload = _build()
    refs = payload["relationship_refs"]
    starship = payload["starship_operating_model_alignment"]

    for ref_id in [
        "workflow_block_intent_live_draft_contract",
        "agent_conversation_handoff_step_packet_contract",
        "bridge_routing_operator_attention_contract",
        "operator_solve_path_decision_node_contract",
        "guided_capture_protected_evidence_path_contract",
        "automation_readiness_feasibility_evaluator_contract",
        "workflow_session_channel_projection_approval_bus_contract",
    ]:
        assert ref_id in refs
        assert refs[ref_id]["path"].endswith(".json")
        assert "present" in refs[ref_id]
    assert starship["bridge"] == "compiles focused orders"
    assert starship["crew"] == "receives packets, not the whole ship"
    assert "below deck" in starship["engineering"]
    assert starship["core_rule"] == "The crew does not roam the whole ship looking for things to do."


def test_no_live_authority_credentials_or_raw_private_bodies():
    payload = _build()
    text = contract.stable_json(payload)

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for packet in payload["execution_packets"]:
        for key, value in packet["authority_boundary"].items():
            assert value is False, key
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    for key in [
        "packet_execution_allowed",
        "live_agent_execution_allowed",
        "model_call_allowed",
        "tool_execution_allowed",
        "mcp_execution_allowed",
        "script_execution_allowed",
        "hook_execution_allowed",
        "receipt_write_allowed",
        "state_write_allowed",
        "invoice_generation_allowed",
        "invoice_preview_render_allowed",
        "email_draft_allowed",
        "email_send_allowed",
        "browser_automation_allowed",
        "coupa_access_allowed",
        "gmail_access_allowed",
        "telegram_send_allowed",
        "credential_handling_allowed",
        "approval_submission_allowed",
        "queue_execution_allowed",
        "runtime_dispatch_allowed",
        "file_write_allowed",
        "raw_body_ingestion_allowed",
    ]:
        assert payload["authority_boundary"][key] is False
    secret_patterns = [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_-]{20,}",
        r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY",
    ]
    for pattern in secret_patterns:
        assert re.search(pattern, text) is None


def test_exporter_writes_json_and_eliwinship_operator_markdown(tmp_path):
    result = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            "generated/read_models",
            "--format",
            "summary",
            "--generated-at",
            FIXED_NOW,
        ]
    )

    assert result == 0
    json_path = tmp_path / "generated" / "read_models" / contract.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / contract.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["machine_proof"]["execution_packet_count"] == 6
    assert payload["machine_proof"]["packet_chain_count"] == 2
    assert "ELIWINSHIP Summary" in operator
    assert "existing Context Selection / Knowledge Packet layer" in operator
    assert "Tools, MCPs, scripts, and hooks are capabilities, not authority." in operator
    assert "No live execution exists yet" in operator
    assert "All authority flags false" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("agent_execution_packet_compiler_contract.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "urllib",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
    ]:
        assert token not in text
