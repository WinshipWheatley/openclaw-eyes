import json
from pathlib import Path

import openclaw_capability_index as index


def _payload():
    return index.build_payload()


def _capabilities(payload):
    return {cap["capability_id"]: cap for cap in payload["generic_capabilities"]}


def _profiles(payload):
    return {profile["capability_ref"]: profile for profile in payload["authority_profiles"]}


def _queries(payload):
    return {query["query_id"]: query for query in payload["query_examples"]}


def test_required_models_exist():
    schemas = _payload()["model_schemas"]
    for model_name in (
        "CapabilityIndexCompiler",
        "GenericCapability",
        "WorkflowCapabilityBinding",
        "CapabilityFixture",
        "CapabilityInputRequirement",
        "CapabilityOutputArtifact",
        "CapabilityAuthorityProfile",
        "DoctrineGateRef",
        "CapabilityProposalCandidate",
        "CapabilityPromotionGate",
        "CapabilityLifecycleRecord",
        "CapabilityGapRecord",
        "CapabilityIndexQueryExample",
        "CapabilityIndexReadback",
        "CapabilityIndexBlocker",
    ):
        assert model_name in schemas


def test_required_generic_capabilities_are_indexed_when_sources_exist():
    caps = _capabilities(_payload())
    required = {
        "request_processing",
        "request_response_service",
        "route_aware_heartbeat",
        "file_metadata_intake",
        "protected_secret_intake",
        "status_readback",
        "workflow_package_compilation",
        "dry_run",
        "completion_proof_aggregation",
        "outbound_message_draft",
        "outbound_message_send_gate",
        "portal_transaction_package",
        "portal_transaction_submit_gate",
        "agent_voice_compilation",
        "spoken_script_generation",
        "visual_event_compilation",
        "worker_routing",
        "scoped_context_package",
        "machine_intent_validation",
        "human_dignity_doctrine_gate",
        "private_hmac_pii_tokenization",
        "client_cockpit_handoff",
    }
    assert required.issubset(caps)


def test_generic_capabilities_are_portable_and_not_fixture_specific():
    payload = _payload()
    assert payload["machine_proof"]["generic_capabilities_user_agnostic"] is True
    forbidden_terms = ("winship", "capital hilton", "capital_hilton", "coupa", "x32", "struna")
    for cap in payload["generic_capabilities"]:
        assert cap["portability_scope"] in {"USER_AGNOSTIC", "TENANT_SCOPED"}
        serialized = json.dumps(cap, sort_keys=True).lower()
        for term in forbidden_terms:
            assert term not in serialized


def test_workflow_specific_examples_are_bindings_or_fixtures_only():
    payload = _payload()
    binding_text = json.dumps(payload["workflow_bindings"], sort_keys=True).lower()
    fixture_text = json.dumps(payload["fixtures"], sort_keys=True).lower()
    query_text = json.dumps(payload["query_examples"], sort_keys=True).lower()
    assert "capital_hilton" in binding_text
    assert "coupa" in binding_text or "coupa" in fixture_text or "coupa" in query_text
    assert "x32" in binding_text
    assert "struna" in binding_text
    assert "capital_hilton" in fixture_text


def test_contract_only_and_future_gated_capabilities_do_not_claim_live_execution():
    payload = _payload()
    profiles = _profiles(payload)
    for cap in payload["generic_capabilities"]:
        profile = profiles[cap["capability_id"]]
        if cap["capability_status"] in {
            "CONTRACT_ONLY",
            "READ_MODEL_ONLY",
            "FIXTURE_ONLY",
            "FUTURE_GATED",
            "BLOCKED_UNSAFE",
            "UNKNOWN_FAIL_CLOSED",
        }:
            assert profile["live_execution_allowed"] is False
            assert index.capability_is_live_usable(
                index.GenericCapability(**cap),
                index.CapabilityAuthorityProfile(**profile),
            ) is False
        assert cap["lifecycle_status"] != "PROPOSED_CANDIDATE"


def test_unknown_authority_fails_closed_blocker_exists():
    blockers = {blocker["blocker_type"]: blocker for blocker in _payload()["blockers"]}
    assert blockers["UNKNOWN_AUTHORITY"]["fail_closed"] is True
    assert blockers["CAPABILITY_CLAIMS_UNPROVEN_AUTHORITY"]["fail_closed"] is True
    assert blockers["PROPOSED_CANDIDATE_USED_AS_LIVE_CAPABILITY"]["fail_closed"] is True
    assert blockers["CANDIDATE_SELF_PROMOTION_ATTEMPTED"]["fail_closed"] is True


def test_invalid_tenant_query_returns_no_tenant_or_client_bindings():
    payload = _payload()
    result = index.filter_index_for_tenant(payload, "tenant_scope:not_valid")
    assert result["valid_tenant_scope"] is False
    assert result["generic_capabilities"]
    assert result["workflow_bindings"] == []
    assert result["fixtures"] == []
    assert "proposal_candidates" not in result


def test_valid_tenant_query_returns_only_matching_bindings_and_fixtures():
    payload = _payload()
    result = index.filter_index_for_tenant(payload, "tenant_scope:fixture_business_ops")
    assert result["valid_tenant_scope"] is True
    assert result["workflow_bindings"]
    assert all(binding["tenant_scope"] == "tenant_scope:fixture_business_ops" for binding in result["workflow_bindings"])
    binding_ids = {binding["binding_id"] for binding in result["workflow_bindings"]}
    assert all(fixture["binding_ref"] in binding_ids for fixture in result["fixtures"])


def test_query_examples_exist_and_preserve_authority_boundaries():
    queries = _queries(_payload())
    expected = {
        "query:generic_next": "CONTINUE_CURRENT_WORKFLOW",
        "query:generic_missing_input": "CAPTURE_MISSING_INPUT",
        "query:generic_draft": "PREPARE_DRAFT",
        "query:generic_read_aloud": "READ_ALOUD",
        "query:generic_blocking_status": "ANSWER_STATUS",
        "query:generic_creative_project": "ROUTE_TO_AGENT",
        "query:generic_send_submit": "REQUEST_APPROVAL",
        "query:generic_visual_video": "SHOW_VISUAL_WORKSPACE",
        "query:generic_dignity_labor": "ASK_CLARIFICATION",
        "query:missing_visual_renderer": "CREATE_BUILD_CUE",
        "query:missing_cassandra_draft_adapter": "PREPARE_DRAFT",
        "query:missing_source_ref_parser": "CREATE_CONTEXT_GAP",
    }
    assert set(expected).issubset(queries)
    for query_id, intent_type in expected.items():
        assert queries[query_id]["recommended_intent_type"] == intent_type
        assert queries[query_id]["validation_required"] is True

    assert "exact approval" in queries["query:generic_send_submit"]["next_safe_move"].lower()
    assert "do not call a provider" in queries["query:generic_visual_video"]["next_safe_move"].lower()
    assert "dignity" in queries["query:generic_dignity_labor"]["matched_capabilities"][0]
    assert "do not render" in queries["query:missing_visual_renderer"]["next_safe_move"].lower()
    assert "do not send" in queries["query:missing_cassandra_draft_adapter"]["next_safe_move"].lower()
    assert "do not ingest" in queries["query:missing_source_ref_parser"]["next_safe_move"].lower()


def test_human_dignity_doctrine_is_gate_wrapper():
    payload = _payload()
    doctrine_gates = {gate["doctrine_ref"]: gate for gate in payload["doctrine_gates"]}
    assert "HUMAN_DIGNITY_DOCTRINE" in doctrine_gates
    assert doctrine_gates["HUMAN_DIGNITY_DOCTRINE"]["decision_check_required"] is True
    assert doctrine_gates["HUMAN_DIGNITY_DOCTRINE"]["operator_review_required"] is True


def test_all_live_authority_false():
    payload = _payload()
    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert all(value is False for value in payload["compiler"]["authority_boundary"].values())
    for profile in payload["authority_profiles"]:
        assert profile["live_authority_allowed"] is False
        assert profile["live_execution_allowed"] is False
        assert profile["live_external_action_allowed"] is False
        assert profile["live_model_call_allowed"] is False
        assert profile["live_agent_dispatch_allowed"] is False
        assert profile["live_outbound_message_send_allowed"] is False
        assert profile["live_portal_access_allowed"] is False
        assert profile["live_portal_submit_allowed"] is False
        assert profile["credential_handling_allowed"] is False
        assert profile["raw_body_ingestion_allowed"] is False
    for candidate in payload["proposal_candidates"]:
        assert all(value is False for value in candidate["authority_boundary"].values())


def test_proposed_candidates_are_quarantined_not_usable_capabilities():
    payload = _payload()
    cap_ids = set(_capabilities(payload))
    candidate_ids = {candidate["proposal_id"] for candidate in payload["proposal_candidates"]}
    assert len(candidate_ids) == 3
    assert candidate_ids.isdisjoint(cap_ids)
    assert payload["readback"]["proposal_candidate_count"] == 3
    assert set(payload["readback"]["proposed_capabilities"]) == candidate_ids
    for candidate in payload["proposal_candidates"]:
        assert candidate["candidate_status"] != "PROMOTED_AFTER_VALIDATION"
        assert candidate["validation_required"] is True
        assert candidate["authority_boundary"]["live_candidate_promotion_allowed"] is False
        assert candidate["authority_boundary"]["live_capability_execution_allowed"] is False


def test_promotion_gates_block_self_promotion_and_require_tests_authority():
    payload = _payload()
    gates = {gate["proposal_ref"]: gate for gate in payload["promotion_gates"]}
    candidates = {candidate["proposal_id"]: candidate for candidate in payload["proposal_candidates"]}
    assert set(gates) == set(candidates)
    for gate in gates.values():
        assert gate["promotion_allowed"] is False
        assert gate["developer_review_required"] is True
        assert gate["operator_approval_required"] is True
        assert gate["required_tests"]
        assert gate["required_authority_profile"]
        assert gate["promotion_status"] == "BLOCKED_UNTIL_VALIDATED"


def test_lifecycle_records_include_capabilities_and_candidates():
    payload = _payload()
    records = {record["capability_ref"]: record for record in payload["lifecycle_records"]}
    for cap in payload["generic_capabilities"]:
        assert records[cap["capability_id"]]["lifecycle_status"] == cap["lifecycle_status"]
    for candidate in payload["proposal_candidates"]:
        record = records[candidate["proposal_id"]]
        assert record["lifecycle_status"] == "PROPOSED_CANDIDATE"
        assert "cannot be promoted" in record["promoted_at_policy"]


def test_missing_growth_proposals_have_expected_boundaries():
    payload = _payload()
    candidates = {candidate["proposal_id"]: candidate for candidate in payload["proposal_candidates"]}
    visual = candidates["proposal:client_cockpit_visual_event_renderer"]
    assert visual["proposed_capability_name"] == "CLIENT_COCKPIT_VISUAL_EVENT_RENDERER"
    assert visual["candidate_status"] == "NEEDS_DEVELOPER_BUILD"
    assert visual["authority_boundary"]["live_visual_generation_allowed"] is False

    draft = candidates["proposal:outbound_message_draft_binding_adapter"]
    assert draft["proposed_taxonomy_type"] == "OUTBOUND_MESSAGE_DRAFT"
    assert draft["authority_boundary"]["live_outbound_message_send_allowed"] is False

    parser = candidates["proposal:source_ref_parser_fixture_binding"]
    assert parser["authority_boundary"]["raw_body_ingestion_allowed"] is False
    assert "raw-body approval decision" in parser["required_receipts"]


def test_generated_output_contains_no_credentials_or_private_bodies(tmp_path):
    json_path, operator_path, _ = index.write_exports(tmp_path)
    text = json_path.read_text() + "\n" + operator_path.read_text()
    forbidden_patterns = (
        "-----BEGIN PRIVATE KEY-----",
        "Bearer ",
        "raw private body value",
        "private raw body content",
        "oauth_token:",
        "password:",
        "api_key:",
    )
    for pattern in forbidden_patterns:
        assert pattern not in text


def test_exported_json_parses(tmp_path):
    json_path, operator_path, payload = index.write_exports(tmp_path)
    assert json.loads(json_path.read_text())["read_model_id"] == "openclaw_capability_index"
    assert operator_path.read_text().startswith("# OpenClaw Capability Index")
    assert payload["readback"]["status"] == "CAPABILITY_INDEX_READY"


def test_query_api_loads_generated_index_from_path(tmp_path):
    json_path, _operator_path, payload = index.write_exports(tmp_path)
    query = index.CapabilityIndexQuery.load_index_from_generated_readmodel(json_path)

    assert query.payload["read_model_id"] == "openclaw_capability_index"
    assert len(query.payload["generic_capabilities"]) == len(payload["generic_capabilities"])


def test_query_find_by_intent_type_returns_generic_missing_input_capabilities():
    query = index.CapabilityIndexQuery(_payload())
    records = query.find_by_intent_type("CAPTURE_MISSING_INPUT")
    ids = {record["capability_id"] for record in records}

    assert {"file_metadata_intake", "source_ref_management"}.issubset(ids)
    assert "capital_hilton_invoice_operator_readback" not in ids
    assert not any("capital_hilton" in json.dumps(record).lower() for record in records)


def test_query_find_by_task_type_supports_make_video_without_provider_claim():
    query = index.CapabilityIndexQuery(_payload())
    records = query.find_by_task_type("make video")
    ids = {record["capability_id"] for record in records}
    gaps = {gap["missing_capability"] for gap in query.payload["capability_gaps"]}

    assert "visual_event_compilation" in ids
    assert not any("provider" in capability_id or "generation_provider" in capability_id for capability_id in ids)
    assert "live visual/video provider generation" in gaps


def test_query_get_workflow_bindings_respects_valid_tenant_scope():
    query = index.CapabilityIndexQuery(_payload())
    bindings = query.get_workflow_bindings(
        "tenant_scope:fixture_business_ops",
        "capital_hilton_invoice_workflow",
    )

    assert bindings
    assert all(binding["tenant_scope"] == "tenant_scope:fixture_business_ops" for binding in bindings)
    assert all(binding["scope_type"] == "WORKFLOW_SCOPED" for binding in bindings)
    assert {binding["capability_ref"] for binding in bindings}.issuperset(
        {"status_readback", "portal_transaction_package", "outbound_message_draft"}
    )


def test_query_get_workflow_bindings_invalid_tenant_leaks_no_fixture_records():
    query = index.CapabilityIndexQuery(_payload())

    assert query.get_workflow_bindings("tenant_scope:not_valid", "capital_hilton_invoice_workflow") == []


def test_query_find_missing_requirements_uses_required_inputs():
    query = index.CapabilityIndexQuery(_payload())
    missing = query.find_missing_requirements("file_metadata_intake", provided_inputs={})

    assert missing
    assert missing[0]["capability_ref"] == "file_metadata_intake"
    assert missing[0]["required"] is True


def test_query_authority_profile_blocks_send_submit_authority():
    query = index.CapabilityIndexQuery(_payload())
    result = query.validate_authority_profile(
        "outbound_message_send_gate",
        {"live_outbound_message_send_allowed": True, "live_external_action_allowed": True},
    )

    assert result["allowed"] is False
    assert "false live authority" in result["reason"]
    assert "exact approval" in result["reason"]
    assert not any(result["authority_granted"].values())


def test_query_rejects_fixture_proposed_and_future_gated_records_as_usable():
    payload = _payload()
    query = index.CapabilityIndexQuery(payload)
    future_capability = next(
        capability for capability in payload["generic_capabilities"] if capability["capability_id"] == "record_keeping_write"
    )
    records = [
        payload["fixtures"][0],
        payload["proposal_candidates"][0],
        future_capability,
    ]

    usable, rejected = query.reject_unusable_capabilities(records)

    assert usable == []
    rejected_ids = {record["record_id"] for record in rejected}
    assert {
        payload["fixtures"][0]["fixture_id"],
        payload["proposal_candidates"][0]["proposal_id"],
        "record_keeping_write",
    } == rejected_ids
    assert any("PROPOSED_CANDIDATE_USED_AS_LIVE_CAPABILITY" in record["rejection_reasons"] for record in rejected)


def test_query_methods_do_not_mutate_index_payload():
    payload = _payload()
    before = json.dumps(payload, sort_keys=True)
    query = index.CapabilityIndexQuery(payload)

    query.find_by_intent_type("CAPTURE_MISSING_INPUT")
    query.find_by_task_type("make video")
    query.get_workflow_bindings("tenant_scope:fixture_business_ops", "capital_hilton_invoice_workflow")
    query.find_missing_requirements("file_metadata_intake", {})
    query.validate_authority_profile("outbound_message_send_gate", {"live_outbound_message_send_allowed": True})
    query.reject_unusable_capabilities(payload["proposal_candidates"])

    assert json.dumps(payload, sort_keys=True) == before
