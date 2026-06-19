import json
from pathlib import Path

import openclaw_work_terrain_query_contract as contract
from scripts.export_openclaw_work_terrain_query_contract import main as export_main


FIXED_NOW = "2026-05-23T14:00:00+00:00"


def _build() -> dict:
    return contract.build_openclaw_work_terrain_query_contract(generated_at=FIXED_NOW)


def test_query_model_result_shape_and_policy_exist():
    payload = _build()

    assert contract.stable_json(payload) == contract.stable_json(_build())
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["contract_status"] == "metadata_only_query_contract"
    assert payload["query_domain_model"]["model_name"] == "WorkTerrainQuery"
    assert payload["terrain_result_shape"]["model_name"] == "WorkTerrainQueryResultShape"
    assert payload["work_terrain_query_policy"]["metadata_first"] is True
    assert payload["machine_proof"]["query_model_exists"] is True
    assert payload["machine_proof"]["result_shape_exists"] is True
    assert payload["machine_proof"]["policy_exists"] is True
    assert "agent_map_binding_ids" in payload["query_domain_model"]["fields"]
    assert "unresolved_target_actors" in payload["query_domain_model"]["fields"]


def test_default_query_examples_cover_required_terrain_questions():
    payload = _build()
    queries = {query["query_id"]: query for query in payload["default_query_examples"]}

    assert set(queries) == {
        "chief_related_work_terrain",
        "capital_hilton_related_work_terrain",
        "security_pass_related_work_terrain",
        "niles_struna_related_work_terrain",
        "repo_b_planner_builder_related_work_terrain",
    }
    assert "Chief" in queries["chief_related_work_terrain"]["target_actors"]
    assert "cross-off" in queries["chief_related_work_terrain"]["target_concepts"]
    assert "Capital Hilton" in queries["capital_hilton_related_work_terrain"]["target_concepts"]
    assert "Finance" in queries["capital_hilton_related_work_terrain"]["target_worlds"]
    assert "security delta" in queries["security_pass_related_work_terrain"]["target_concepts"]
    assert "Niles" in queries["niles_struna_related_work_terrain"]["target_actors"]
    assert "Repo B" in queries["repo_b_planner_builder_related_work_terrain"]["target_concepts"]
    assert payload["machine_proof"]["chief_example_exists"] is True
    assert payload["machine_proof"]["capital_hilton_example_exists"] is True


def test_agent_map_wiring_binds_default_queries_to_existing_agent_lanes():
    payload = _build()
    wiring = payload["agent_map_wiring"]
    bindings = {binding["binding_id"]: binding for binding in wiring["bindings"]}
    queries = {query["query_id"]: query for query in payload["default_query_examples"]}

    assert wiring["binding_model"]["model_name"] == "WorkTerrainQueryAgentMapBinding"
    assert wiring["mode"] == "query_target_actor_to_agent_lane_context_only"
    assert wiring["context_only"] is True
    assert wiring["unknowns_fail_closed"] is True
    assert wiring["action_authority_granted"] is False
    assert wiring["runtime_dispatch_allowed"] is False
    assert "agent_lane_registry.py::DEFAULT_AGENT_LANE_SEEDS" in wiring["source_refs"]

    assert payload["machine_proof"]["agent_map_wiring_exists"] is True
    assert payload["machine_proof"]["agent_map_binding_model_exists"] is True
    assert payload["machine_proof"]["all_default_queries_have_agent_map_bindings"] is True
    assert payload["machine_proof"]["known_agent_bindings_from_agent_lane_registry"] is True
    assert set(payload["machine_proof"]["bound_agent_ids"]) == {"cassandra", "chief", "guardian", "hermes", "niles"}

    for query in queries.values():
        assert query["agent_map_binding_ids"], query["query_id"]
        for binding_id in query["agent_map_binding_ids"]:
            assert binding_id in bindings
            binding = bindings[binding_id]
            assert binding["query_id"] == query["query_id"]
            assert binding["context_only"] is True
            assert binding["action_authority_granted"] is False
            assert binding["runtime_dispatch_allowed"] is False
            assert binding["source_refs"] == contract.AGENT_MAP_SOURCE_REFS

    chief_binding = bindings["chief_related_work_terrain::chief"]
    assert chief_binding["lane_id"] == "system_orchestration"
    assert chief_binding["binding_basis"] == "target_actor_to_agent_lane_registry"
    assert "routing_decision" in chief_binding["allowed_output_kinds"]

    capital_binding_ids = set(queries["capital_hilton_related_work_terrain"]["agent_map_binding_ids"])
    assert capital_binding_ids == {
        "capital_hilton_related_work_terrain::cassandra",
        "capital_hilton_related_work_terrain::guardian",
    }
    assert bindings["capital_hilton_related_work_terrain::cassandra"]["lane_id"] == "operator_comms"
    assert bindings["capital_hilton_related_work_terrain::guardian"]["lane_id"] == "safety_security"


def test_agent_map_wiring_unknown_actors_fail_closed_without_runtime_authority():
    payload = _build()
    wiring = payload["agent_map_wiring"]
    unresolved = wiring["unresolved_target_actors_by_query_id"]
    queries = {query["query_id"]: query for query in payload["default_query_examples"]}

    assert unresolved["niles_struna_related_work_terrain"] == ["Struna"]
    assert unresolved["repo_b_planner_builder_related_work_terrain"] == ["Operator"]
    assert queries["niles_struna_related_work_terrain"]["unresolved_target_actors"] == ["Struna"]
    assert queries["repo_b_planner_builder_related_work_terrain"]["unresolved_target_actors"] == ["Operator"]
    assert payload["machine_proof"]["unknown_target_actors_fail_closed"] is True
    assert payload["machine_proof"]["struna_actor_unresolved_fail_closed"] is True
    assert payload["machine_proof"]["operator_actor_unresolved_fail_closed"] is True
    assert payload["authority_boundary"]["agent_activation_allowed"] is False
    assert payload["authority_boundary"]["runtime_dispatch_allowed"] is False


def test_allowed_and_blocked_sources_are_metadata_first_and_fail_closed():
    payload = _build()
    model = payload["query_domain_model"]

    for source in [
        "SQLITE_METADATA",
        "CORPUS_ATLAS_METADATA",
        "MARKDOWN_ATLAS_METADATA",
        "GENERATED_READ_MODELS",
        "OPERATOR_MARKDOWN_SUMMARIES",
        "STABLE_MAP_SECTIONS",
        "RECEIPT_METADATA",
        "SCRIPT_TEST_FILE_METADATA",
        "COMMIT_METADATA_IF_AVAILABLE",
        "VALIDATION_ARTIFACT_METADATA",
    ]:
        assert source in model["allowed_sources"]
    for source in [
        "BROAD_RAW_MARKDOWN_BODIES",
        "BROAD_PRIVATE_ROOTS",
        "MAC_PRIVATE_HOME",
        "PC_C_DRIVE",
        "EMAIL_ACCOUNT_BODIES",
        "COUPA_BROWSER_SESSIONS",
        "CREDENTIAL_STORES",
        "RAW_FINANCE_PRIVATE_BODIES",
    ]:
        assert source in model["blocked_sources"]
    assert payload["machine_proof"]["private_broad_roots_blocked"] is True
    assert payload["machine_proof"]["c_drive_blocked"] is True


def test_query_examples_never_grant_body_semantic_or_action_authority():
    payload = _build()

    for query in payload["default_query_examples"]:
        assert query["body_ingestion_allowed"] is False
        assert query["semantic_review_allowed"] is False
        assert query["authority_granted"] is False
        assert "BROAD_RAW_MARKDOWN_BODIES" in query["blocked_sources"]
        assert "PC_C_DRIVE" in query["blocked_sources"]
    assert payload["machine_proof"]["body_ingestion_disabled"] is True
    assert payload["machine_proof"]["semantic_review_disabled"] is True
    assert payload["machine_proof"]["no_action_authority"] is True


def test_source_types_and_result_shape_are_broad_but_non_executing():
    payload = _build()

    for source_type in [
        "MARKDOWN_FILE",
        "OPERATOR_MARKDOWN",
        "GENERATED_READ_MODEL_JSON",
        "PYTHON_CONTRACT",
        "EXPORT_SCRIPT",
        "TEST_FILE",
        "SQLITE_TABLE",
        "STABLE_MAP_SECTION",
        "MAC_SWIFT_SOURCE",
        "WORKER_REPORT",
        "HANDOFF_FILE",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert source_type in payload["work_terrain_source_types"]
    shape = payload["terrain_result_shape"]["example_shape"]
    assert shape["body_ingestion_status"] == "NOT_INGESTED_METADATA_ONLY"
    assert shape["semantic_review_status"] == "NOT_ALLOWED_IN_THIS_CONTRACT"
    assert payload["terrain_result_shape"]["live_result"] is False


def test_policy_blocks_private_roots_repo_b_mutation_and_stable_map_source_truth():
    payload = _build()
    policy = payload["work_terrain_query_policy"]

    assert policy["metadata_first"] is True
    assert policy["body_ingestion_default"] is False
    assert policy["semantic_review_default"] is False
    assert "blocked" in policy["private_root_policy"]
    assert "blocked" in policy["c_drive_policy"]
    assert "reference-only" in policy["repo_b_policy"]
    assert "require operator approval" in policy["mac_root_policy"]
    assert "Generated artifacts" in policy["generated_artifact_policy"]
    assert policy["stable_map_policy"] == "Stable map is app-facing reflection, not source truth."
    assert payload["machine_proof"]["repo_b_reference_only"] is True
    assert payload["machine_proof"]["stable_map_not_source_truth"] is True


def test_questions_enabled_for_later_relationship_and_classification_lanes():
    payload = _build()

    for question in [
        "Which Chief docs exist?",
        "Which are current?",
        "Which are old prompts?",
        "Which are superseded?",
        "Which concepts overlap?",
        "Which files are missing stable-map representation?",
        "Which built artifacts lack a source note?",
        "Which source notes describe things already built?",
        "Which items need Hermes review?",
        "Which items need Chief reconciliation?",
        "Which items should become consolidation candidates?",
    ]:
        assert question in payload["questions_enabled_later"]


def test_authority_boundary_blocks_mutation_runtime_network_git_and_mac_sync():
    payload = _build()
    boundary = payload["authority_boundary"]

    assert boundary["all_action_authority_flags_false"] is True
    for key, value in contract.AUTHORITY_BOUNDARY.items():
        assert value is False
        assert boundary[key] is False, key


def test_no_credentials_raw_private_bodies_or_literal_c_drive_paths_are_included():
    payload = _build()
    text = contract.stable_json(payload)

    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["machine_proof"]["raw_private_body_included"] is False
    assert "/" + "mnt" + "/" + "c" not in text
    assert "c:" + "\\" not in text.lower()
    assert "sk-" not in text
    assert "BEGIN " + "PRIVATE KEY" not in text


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    result = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            "generated/read_models",
            "--format",
            "summary",
        ]
    )

    assert result == 0
    json_path = tmp_path / "generated" / "read_models" / contract.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / contract.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert len(payload["default_query_examples"]) == 5
    assert "ELIWINSHIP Summary" in operator
    assert "What It Can Ask Later" in operator


def test_source_does_not_contain_broad_scan_mutation_or_runtime_calls():
    text = Path("openclaw_work_terrain_query_contract.py").read_text(encoding="utf-8").lower()
    for token in [
        "os.walk",
        ".rglob(",
        ".glob(",
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
    ]:
        assert token not in text
