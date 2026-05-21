import json
from pathlib import Path

import agent_memory_scope_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_agent_memory_scope_contract import main as export_main


FIXED_NOW = "2026-05-22T01:30:00+00:00"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    _write_text(root / "OPENCLAW_RUNTIME.md", "# Runtime Law\n")
    _write_text(root / "USER.md", "# Winship\n")
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
        "agent_package_preview_contract.json": {
            "schema_version": "agent_package_preview_contract_v0",
            "read_model_id": "agent_package_preview_contract",
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
        },
        "protected_evidence_reference_receipt.json": {
            "schema_version": "protected_evidence_reference_receipt_v0",
            "read_model_id": "protected_evidence_reference_receipt",
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "read_model_id": "guardian_protected_access_gate_spec",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_agent_memory_scope_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _actor_scopes(payload: dict) -> dict:
    return {item["actor_id"]: item for item in payload["actor_memory_scopes"]}


def _examples(payload: dict) -> dict:
    return {item["decision_id"]: item for item in payload["example_memory_scope_decisions"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "agent_memory_scope_contract"
    assert first["contract_status"] == "deterministic_memory_scope_metadata_only"
    assert first["runtime_authority"] is False
    assert first["model_memory_authority"] is False
    assert first["hidden_memory_authority"] is False
    assert first["autonomous_memory_capture"] is False
    assert first["raw_chat_ingestion_authority"] is False
    assert first["vector_memory_authority"] is False
    assert first["external_tool_memory_authority"] is False
    assert first["credential_memory_authority"] is False
    assert first["operator_final_authority"] is True


def test_memory_surface_taxonomy_and_canonical_surfaces_are_explicit(tmp_path):
    payload = _build(tmp_path)
    taxonomy = payload["memory_surface_taxonomy"]
    canonical = [item["surface_id"] for item in payload["canonical_memory_surfaces"]]

    assert taxonomy["surface_types"] == list(contract.MEMORY_SURFACE_TYPES)
    assert canonical == ["vault", "handoff", "mac_eyes", "polish_loop", "CLAUDE.md"]
    assert taxonomy["session_local_workspace_assistant_and_copilot_memory_have_zero_authority"] is True
    assert taxonomy["noncanonical_residue_must_be_labelled"] is True
    for item in payload["canonical_memory_surfaces"]:
        assert item["does_not_override_read_model_proof"] is True


def test_noncanonical_residue_and_blocked_memory_are_not_authoritative(tmp_path):
    payload = _build(tmp_path)
    residue = {item["surface_id"]: item for item in payload["noncanonical_residue_surfaces"]}
    blocked = {item["surface_id"]: item for item in payload["blocked_memory_surfaces"]}

    for expected in [
        "session-local memory",
        "workspace artifacts",
        "assistant checkpoint files",
        "Copilot workspace memory",
        "temporary scratch files",
        "unpromoted chat summaries",
        "unreceipted worker notes",
        "unverified generated artifacts",
    ]:
        assert residue[expected]["canonical_status"] == "non_authoritative_residue"
        assert residue[expected]["promotion_required_before_use_as_memory"] is True
    for expected in [
        "credentials",
        "OAuth tokens",
        "browser cookies/session data",
        "raw bank/remit/check/home-address material",
        "raw Gmail/calendar bodies unless specifically gated",
        "surveillance/background observation",
        "hidden personalization capture",
        "broad filesystem memory capture",
        "external model retained memory",
        "unverified claims treated as facts",
    ]:
        assert blocked[expected]["memory_result"] == "blocked"
        assert blocked[expected]["may_be_used_as_package_context_now"] is False


def test_actor_memory_scopes_cover_known_actors(tmp_path):
    payload = _build(tmp_path)
    scopes = _actor_scopes(payload)

    assert set(scopes) == set(contract.KNOWN_ACTOR_IDS)
    for scope in scopes.values():
        assert scope["readable_context_allowed"]
        assert scope["readable_context_blocked"]
        assert scope["writable_memory_candidates"]
        assert scope["writeback_blocked"]
        assert scope["can_write_canonical_memory_directly"] is False
        assert scope["can_silently_retain_memory"] is False
    assert scopes["operator_winship"]["requires_operator_promotion"] is False
    assert scopes["operator_winship"]["requires_guardian_review"] is False
    assert scopes["guardian"]["requires_operator_promotion"] is True
    assert scopes["cassandra"]["requires_guardian_review"] is True
    assert "raw Gmail bodies without gate" in scopes["cassandra"]["readable_context_blocked"]
    assert "Struna metadata refs" in scopes["niles"]["readable_context_allowed"]
    assert "scoped implementation package refs" in scopes["codex"]["readable_context_allowed"]
    assert "durable retained memory" in scopes["gemini_antigravity"]["readable_context_blocked"]


def test_context_read_and_writeback_policy_blocks_hidden_memory(tmp_path):
    payload = _build(tmp_path)
    read_policy = payload["context_read_policy"]
    write_policy = payload["memory_writeback_policy"]

    assert "deterministic read-model refs" in read_policy["allowed_context_forms"]
    assert "receipt IDs" in read_policy["allowed_context_forms"]
    assert "project capsule refs" in read_policy["allowed_context_forms"]
    assert read_policy["raw_private_bodies_allowed_by_default"] is False
    assert read_policy["unknown_context_result"] == "UNKNOWN_FAIL_CLOSED"
    assert write_policy["actors_may_only_propose_candidates"] is True
    assert write_policy["actors_may_directly_write_canonical_memory"] is False
    assert write_policy["models_may_silently_retain_or_promote_memory"] is False
    for field in [
        "source_refs",
        "claim_type",
        "sensitivity_classification",
        "proposed_canonical_surface",
        "why_it_matters",
        "expiration_or_review_posture",
        "operator_promotion_requirement",
        "receipt_requirement",
    ]:
        assert field in write_policy["candidate_required_fields"]
    assert "hidden memory writes" in write_policy["writeback_blocked"]
    assert "credential/token storage" in write_policy["writeback_blocked"]


def test_memory_candidates_operator_memory_and_promotion_are_bounded(tmp_path):
    payload = _build(tmp_path)
    candidate = payload["memory_candidate_policy"]
    promotion = payload["promotion_policy"]

    assert "needs_operator_promotion" in candidate["candidate_statuses"]
    assert "needs_guardian_review" in candidate["candidate_statuses"]
    assert "promoted_with_receipt" in candidate["candidate_statuses"]
    assert "identify missing terrain" in candidate["operator_memory_can"]
    assert "become proof by itself" in candidate["operator_memory_may_not"]
    assert "authorize execution" in candidate["operator_memory_may_not"]
    assert promotion["promotion_requires_operator"] is True
    assert promotion["promotion_requires_receipt_or_proof"] is True
    assert promotion["sensitive_or_protected_requires_guardian_review"] is True
    assert promotion["unverified_claims_are_not_facts"] is True


def test_redaction_revocation_sensitivity_and_receipts_are_explicit(tmp_path):
    payload = _build(tmp_path)
    redaction = payload["redaction_and_reference_policy"]
    revocation = payload["forgetting_and_revocation_policy"]
    sensitivity = payload["sensitivity_policy"]
    receipts = payload["receipt_requirements"]

    assert redaction["prefer_refs_over_bodies"] is True
    assert "credentials" in redaction["must_redact_or_exclude"]
    assert "Guardian gate" in redaction["protected_reference_only_requires"]
    assert "no raw private body" in redaction["protected_reference_only_requires"]
    assert "revoke promoted memory" in revocation["future_safe_operations"]
    assert "suppress sensitive memory from packages" in revocation["future_safe_operations"]
    assert revocation["revocation_requires_receipt"] is True
    assert revocation["rejected_memory_must_not_reappear_as_fact"] is True
    assert sensitivity["unknown_defaults_to"] == "unknown_fail_closed"
    assert sensitivity["credential_or_token_result"] == "blocked"
    assert sensitivity["external_model_memory_default"] == "blocked"
    assert "memory candidate receipt" in receipts["required_for_future_memory_promotion"]
    assert "operator promotion receipt" in receipts["required_for_future_memory_promotion"]
    assert receipts["natural_language_claims_count_as_proof"] is False


def test_mission_control_guidance_is_memory_scope_oriented(tmp_path):
    payload = _build(tmp_path)
    guidance = payload["mission_control_surface_guidance"]

    assert guidance["top_layer"] == "what memory would this actor see?"
    assert guidance["middle_layer"] == "what is excluded and why?"
    assert guidance["lower_layer"] == "promotion, sensitivity, proof, receipts"
    assert "fake model memory" in guidance["do_not_present_as"]
    assert "hidden personalization" in guidance["do_not_present_as"]
    assert "raw chat dump" in guidance["do_not_present_as"]
    assert guidance["show_noncanonical_residue_as"] == "non-authoritative until promoted"


def test_example_memory_scope_decisions_cover_required_cases(tmp_path):
    payload = _build(tmp_path)
    examples = _examples(payload)

    assert set(examples) == {
        "codex_backend_refs_no_secrets",
        "cassandra_capital_hilton_refs_no_raw_bodies",
        "niles_struna_project_capsule_refs",
        "guardian_protected_evidence_candidate",
        "chief_check_engine_posture_refs",
        "hermes_architecture_doctrine_refs",
        "gemini_antigravity_scoped_refactor_no_retention",
    }
    assert examples["codex_backend_refs_no_secrets"]["actor_id"] == "codex"
    assert "credentials" in examples["codex_backend_refs_no_secrets"]["readable_context_blocked"]
    assert examples["cassandra_capital_hilton_refs_no_raw_bodies"]["guardian_review_required"] is True
    assert "raw Gmail bodies" in examples["cassandra_capital_hilton_refs_no_raw_bodies"]["readable_context_blocked"]
    assert examples["niles_struna_project_capsule_refs"]["actor_id"] == "niles"
    assert examples["guardian_protected_evidence_candidate"]["actor_id"] == "guardian"
    assert examples["chief_check_engine_posture_refs"]["actor_id"] == "chief"
    assert examples["hermes_architecture_doctrine_refs"]["actor_id"] == "hermes"
    assert examples["gemini_antigravity_scoped_refactor_no_retention"]["actor_id"] == "gemini_antigravity"
    for example in examples.values():
        assert example["promotion_required"] is True
        assert example["canonical_memory_written_now"] is False
        assert example["model_memory_created_now"] is False


def test_blocked_memory_states_fail_closed(tmp_path):
    payload = _build(tmp_path)
    states = {item["state_id"]: item for item in payload["blocked_memory_states"]}

    for state_id in [
        "credential_or_token_present",
        "browser_session_material_present",
        "raw_private_body_present_without_gate",
        "raw_chat_dump_requested",
        "hidden_memory_capture_requested",
        "broad_filesystem_memory_requested",
        "external_model_retained_memory_requested",
        "operator_promotion_missing",
        "guardian_review_missing_for_sensitive",
        "unverified_claim_treated_as_fact",
    ]:
        assert states[state_id]["memory_result"] == "blocked"
        assert states[state_id]["canonical_memory_written_now"] is False


def test_evidence_sources_are_bounded_and_do_not_grant_authority(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    assert sources["openclaw_runtime_law"]["present"] is True
    assert sources["operator_preferences"]["present"] is True
    assert sources["agent_package_preview_contract"]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["credentials_or_secrets_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_recommended_next_lanes_match_memory_scope_maturity_path(tmp_path):
    payload = _build(tmp_path)
    lanes = [item["lane_id"] for item in payload["recommended_next_lanes"]]

    assert lanes == [
        "tool_protocol_adapter_registry_v0",
        "memory_candidate_receipt_v0",
        "mission_control_package_preview_surface_v0",
        "mission_control_actor_routing_surface_v0",
        "model_selection_receipt_v0",
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
    assert summary["actor_scope_count"] == len(contract.KNOWN_ACTOR_IDS)
    assert summary["canonical_surface_count"] == len(contract.CANONICAL_MEMORY_SURFACES)
    assert summary["example_count"] == 7
    assert summary["runtime_authority_added"] is False
    assert summary["hidden_memory_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "agent_memory_scope_contract"
    assert "Agent Memory Scope Contract v0" in operator
    assert "Non-Canonical Residue" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    contract.export_agent_memory_scope_contract(
        repo_root=tmp_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_network_or_system_drive_authority_strings():
    text = Path("agent_memory_scope_contract.py").read_text(encoding="utf-8").lower()
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
