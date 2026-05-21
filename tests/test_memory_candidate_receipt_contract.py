import json
from pathlib import Path

import memory_candidate_receipt_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_memory_candidate_receipt_contract import main as export_main


FIXED_NOW = "2026-05-22T03:30:00+00:00"


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
        "agent_package_preview_contract.json": {
            "schema_version": "agent_package_preview_contract_v0",
            "read_model_id": "agent_package_preview_contract",
        },
        "agent_memory_scope_contract.json": {
            "schema_version": "agent_memory_scope_contract_v0",
            "read_model_id": "agent_memory_scope_contract",
        },
        "tool_protocol_adapter_registry_contract.json": {
            "schema_version": "tool_protocol_adapter_registry_contract_v0",
            "read_model_id": "tool_protocol_adapter_registry_contract",
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "read_model_id": "guardian_protected_access_gate_spec",
        },
        "protected_evidence_reference_receipt.json": {
            "schema_version": "protected_evidence_reference_receipt_v0",
            "read_model_id": "protected_evidence_reference_receipt",
        },
        "operator_map_bundle_contract.json": {
            "schema_version": "operator_map_bundle_contract_v0",
            "read_model_id": "operator_map_bundle_contract",
        },
        "operator_threshold_map_contract.json": {
            "schema_version": "operator_threshold_map_contract_v0",
            "read_model_id": "operator_threshold_map_contract",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_memory_candidate_receipt_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _examples(payload: dict) -> dict:
    return {item["example_id"]: item for item in payload["example_candidate_receipts"]}


def _actors(payload: dict) -> dict:
    return {item["actor_id"]: item for item in payload["actor_candidate_rules"]}


def _sensitivity(payload: dict) -> dict:
    return {item["sensitivity"]: item for item in payload["sensitivity_policy"]["classes"]}


def _sources(payload: dict) -> dict:
    return {item["source_class"]: item for item in payload["source_class_policy"]["source_classes"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "memory_candidate_receipt_contract"
    assert first["contract_status"] == "deterministic_memory_candidate_receipt_metadata_only"
    assert first["runtime_authority"] is False
    assert first["model_memory_authority"] is False
    assert first["hidden_memory_authority"] is False
    assert first["autonomous_memory_capture"] is False
    assert first["raw_chat_ingestion_authority"] is False
    assert first["vector_memory_authority"] is False
    assert first["external_retained_memory_authority"] is False
    assert first["canonical_memory_promotion_authority"] is False
    assert first["operator_final_authority"] is True


def test_candidate_definition_keeps_candidates_noncanonical(tmp_path):
    payload = _build(tmp_path)
    definition = payload["memory_candidate_definition"]

    assert definition["candidate_is_canonical_memory"] is False
    assert definition["worker_output_is_truth"] is False
    assert definition["operator_memory_is_machine_proof"] is False
    assert definition["promotion_execution_authority_created"] is False
    assert definition["canonical_surfaces"] == list(contract.CANONICAL_MEMORY_SURFACES)
    for surface in [
        "vault",
        "handoff",
        "mac_eyes",
        "polish_loop",
        "CLAUDE.md",
        "generated_read_models",
        "stable_map_bundle",
        "approved_receipts_package_previews",
    ]:
        assert surface in definition["canonical_surfaces"]


def test_candidate_types_states_and_receipt_fields_are_explicit(tmp_path):
    payload = _build(tmp_path)
    states = {item["state_id"]: item for item in payload["candidate_states"]}
    schema = payload["candidate_receipt_schema"]

    assert [item["candidate_type"] for item in payload["candidate_types"]] == list(contract.MEMORY_CANDIDATE_TYPES)
    assert set(states) == set(contract.CANDIDATE_STATES)
    assert states["PROMOTED_CANONICAL"]["promotion_authority_created"] is False
    assert states["QUARANTINED"]["package_use_allowed"] is False
    assert schema["required_fields"] == list(contract.CANDIDATE_RECEIPT_FIELDS)
    assert schema["raw_body_included_must_default_false"] is True
    assert schema["receipt_hash_required"] is True
    assert schema["natural_language_claim_counts_as_proof"] is False
    for field in [
        "candidate_id",
        "receipt_id",
        "candidate_type",
        "source_reference",
        "source_class",
        "raw_body_included",
        "redaction_status",
        "sensitivity",
        "proof_status",
        "destination_canonical_surface",
        "promotion_allowed",
        "promotion_blockers",
        "receipt_hash",
        "what_would_make_it_canonical",
    ]:
        assert field in schema["required_fields"]


def test_source_classes_distinguish_allowed_from_blocked_residue(tmp_path):
    payload = _build(tmp_path)
    sources = _sources(payload)

    for source_class in contract.ALLOWED_SOURCE_CLASSES:
        assert sources[source_class]["allowed_for_candidate"] is True
        assert sources[source_class]["status"] == "allowed_bounded"
    for source_class in contract.BLOCKED_SOURCE_CLASSES:
        assert sources[source_class]["allowed_for_candidate"] is False
        assert sources[source_class]["status"] == "blocked_or_non_authoritative"
    assert sources["operator_provided_statement"]["proof_posture"] == "context_or_metadata_reference"
    assert sources["hidden_model_memory"]["proof_posture"] == "not_proof"
    assert sources["credentials_tokens_cookies"]["allowed_for_candidate"] is False
    assert payload["source_class_policy"]["unknown_source_result"] == "UNKNOWN_FAIL_CLOSED"


def test_proof_redaction_and_sensitivity_policies_fail_closed(tmp_path):
    payload = _build(tmp_path)
    proof = payload["proof_status_model"]
    redaction = payload["redaction_policy"]
    sensitivity = _sensitivity(payload)

    assert proof["proof_statuses"] == list(contract.PROOF_STATUSES)
    assert "Operator statement may be context but not machine proof." in proof["rules"]
    assert "Worker output may be receipt candidate but not proof without command/output/file-change evidence." in proof["rules"]
    assert "PROOF_CONFLICTED" in proof["promotion_blocked_by"]
    assert "PROOF_UNKNOWN_FAIL_CLOSED" in proof["promotion_blocked_by"]
    assert redaction["redaction_statuses"] == list(contract.REDACTION_STATUSES)
    assert "RAW_BODY_BLOCKED" in redaction["blocked_redaction_statuses"]
    assert "CREDENTIAL_SECRET_BLOCKED" in redaction["blocked_redaction_statuses"]
    assert sensitivity["FINANCE_PROTECTED"]["requires_guardian_gate"] is True
    assert sensitivity["FINANCE_PROTECTED"]["requires_operator_approval"] is True
    assert sensitivity["CREDENTIAL_OR_SECRET"]["promotion_rule"].startswith("must never be promoted")
    assert sensitivity["UNKNOWN_SENSITIVE_FAIL_CLOSED"]["external_model_eligibility"] == "blocked"


def test_promotion_gate_policy_blocks_authority_drift_and_missing_proof(tmp_path):
    payload = _build(tmp_path)
    policy = payload["promotion_gate_policy"]

    for required in [
        "valid source reference",
        "candidate classification",
        "sensitivity classification",
        "redaction status",
        "proof status",
        "destination canonical surface",
        "receipt hash",
        "no blocked source material",
        "no unresolved proof conflict",
    ]:
        assert required in policy["promotion_requires"]
    for blocked in [
        "source unknown",
        "raw private body included without gate",
        "credential/secret material present",
        "sensitivity unknown",
        "proof missing where proof required",
        "candidate contradicts existing canonical proof",
        "Guardian gate fails",
        "Operator approval required but absent",
        "external retained memory is involved",
        "candidate attempts to authorize runtime/tool/model/account access",
    ]:
        assert blocked in policy["promotion_blocked_if"]
    assert policy["this_contract_promotes_memory"] is False
    assert policy["PROMOTED_CANONICAL_is_future_state_only"] is True


def test_revocation_staleness_and_quarantine_are_non_destructive(tmp_path):
    payload = _build(tmp_path)
    policy = payload["revocation_staleness_quarantine_policy"]

    assert "operator_winship" in policy["who_can_request_revocation"]
    assert "guardian" in policy["who_can_request_revocation"]
    assert "candidate receipt" in policy["what_can_be_revoked"]
    assert "proof expired" in policy["stale_when"]
    assert policy["downstream_package_rule"].startswith("revoked, stale, or quarantined")
    for trigger in [
        "credential/secret exposure",
        "raw private body exposure",
        "source cannot be verified",
        "worker claims authority it did not have",
        "model claims hidden memory",
        "contradiction with canonical proof",
        "malformed receipt",
        "missing receipt hash",
        "suspicious broad capture",
    ]:
        assert trigger in policy["quarantine_triggers"]
    assert policy["quarantine_is_non_destructive"] is True


def test_actor_candidate_rules_cover_known_actor_boundaries(tmp_path):
    actors = _actors(_build(tmp_path))

    assert set(actors) == set(contract.KNOWN_ACTOR_IDS)
    assert "OPERATOR_CORRECTION_CANDIDATE" in actors["operator_winship"]["may_propose_candidate_types"]
    assert "make a fact machine-proof by statement alone" in actors["operator_winship"]["cannot_do"]
    assert "LANE_STATUS_CANDIDATE" in actors["chief"]["may_propose_candidate_types"]
    assert "self-authorize repairs" in actors["chief"]["cannot_do"]
    assert "SAFETY_BOUNDARY_CANDIDATE" in actors["guardian"]["may_propose_candidate_types"]
    assert "FINANCE_PROTECTED_CONTEXT_CANDIDATE" in actors["cassandra"]["may_propose_candidate_types"]
    assert "raw Coupa/Gmail/calendar bodies" in actors["cassandra"]["blocked_source_material"]
    assert "ARCHITECTURE_DOCTRINE_CANDIDATE" in actors["hermes"]["may_propose_candidate_types"]
    assert "CREATIVE_CONTEXT_CANDIDATE" in actors["niles"]["may_propose_candidate_types"]
    assert "BUILD_VERIFICATION_CANDIDATE" in actors["codex"]["may_propose_candidate_types"]
    assert "hidden IDE/Copilot memory" in actors["codex"]["blocked_source_material"]
    assert "external retained memory" in actors["gemini_antigravity"]["blocked_source_material"]
    for rule in actors.values():
        assert rule["can_write_canonical_memory_directly"] is False
        assert rule["can_self_promote"] is False


def test_example_candidate_receipts_cover_required_non_executing_cases(tmp_path):
    payload = _build(tmp_path)
    examples = _examples(payload)

    assert set(examples) == {
        "operator_capital_hilton_coupa_excel",
        "codex_build_succeeded",
        "gpt_doctrine_correction",
        "gemini_visual_polish_notes",
        "copilot_old_project_note",
        "private_email_body_mentioned",
        "niles_creative_preference",
        "coupa_future_gated_tool_adapter",
    }
    capital = examples["operator_capital_hilton_coupa_excel"]
    assert capital["candidate_type"] == "OPERATOR_CONTEXT_CANDIDATE"
    assert capital["proof_status"] == "NOT_PROOF_CONTEXT_ONLY"
    assert capital["sensitivity"] == "FINANCE_PROTECTED"
    assert capital["promotion_allowed"] is False
    assert "Guardian review required" in capital["promotion_blockers"]
    build = examples["codex_build_succeeded"]
    assert build["candidate_type"] == "BUILD_VERIFICATION_CANDIDATE"
    assert build["proof_status"] == "PROOF_RECEIPT_PRESENT"
    assert "Command, output, file-change refs" in build["what_would_make_it_canonical"]
    email = examples["private_email_body_mentioned"]
    assert email["source_class"] == "raw_gmail_calendar_coupa_telegram_body"
    assert email["redaction_status"] == "RAW_BODY_BLOCKED"
    assert email["promotion_allowed"] is False
    for example in examples.values():
        assert example["raw_body_included"] is False
        assert example["canonical_memory_written_now"] is False
        assert example["model_memory_created_now"] is False
        assert example["destination_canonical_surface"] in contract.CANONICAL_MEMORY_SURFACES


def test_relationships_mission_control_and_stable_map_guidance_are_present(tmp_path):
    payload = _build(tmp_path)
    relationships = payload["relationship_to_existing_contracts"]
    guidance = payload["mission_control_surface_guidance"]
    stable = payload["stable_map_integration"]

    for key in [
        "agent_platform_alignment",
        "agent_identity_actor_router_contract",
        "model_selection_policy_contract",
        "agent_package_preview_contract",
        "agent_memory_scope_contract",
        "tool_protocol_adapter_registry_contract",
        "stable_map_bundle",
        "threshold_map_contract",
        "guardian_protected_access_gate_spec",
    ]:
        assert key in relationships
    assert "pending candidates" in guidance["memory_candidate_inbox"]
    assert "proof vs context distinction" in guidance["candidate_detail"]
    assert "candidate context included" in guidance["package_preview_memory_section"]
    assert "credentials/secrets/tokens" in guidance["hide_or_block"]
    assert "raw Gmail/calendar/Coupa/Telegram bodies" in guidance["hide_or_block"]
    assert stable["registry_generated_as_read_model"] is True
    assert stable["summary_included_in_stable_map_bundle_now"] is False
    assert stable["safe_summary_to_include_next"]["candidate_types_count"] == len(contract.MEMORY_CANDIDATE_TYPES)
    assert "REVOKED" in stable["safe_summary_to_include_next"]["blocked_candidate_states"]


def test_evidence_sources_are_bounded_and_do_not_grant_authority(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    assert sources["agent_platform_alignment"]["present"] is True
    assert sources["agent_memory_scope_contract"]["present"] is True
    assert sources["tool_protocol_adapter_registry_contract"]["present"] is True
    assert sources["guardian_protected_access_gate_spec"]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["credentials_or_secrets_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_recommended_next_lanes_match_receipt_maturity_path(tmp_path):
    payload = _build(tmp_path)
    lanes = [item["lane_id"] for item in payload["recommended_next_lanes"]]

    assert lanes == [
        "model_selection_receipt_v0",
        "package_preview_receipt_v0",
        "mission_control_package_preview_actor_routing_surface_v0",
        "tool_adapter_receipt_v0",
        "memory_review_promotion_surface_v0",
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
    assert summary["candidate_type_count"] == len(contract.MEMORY_CANDIDATE_TYPES)
    assert summary["candidate_state_count"] == len(contract.CANDIDATE_STATES)
    assert summary["example_count"] == 8
    assert summary["canonical_memory_promotion_authority_added"] is False
    assert summary["hidden_memory_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "memory_candidate_receipt_contract"
    assert "Memory Candidate Receipt Contract v0" in operator
    assert "OPERATOR_CONTEXT_CANDIDATE" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    contract.export_memory_candidate_receipt_contract(repo_root=tmp_path, export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_network_delete_or_c_drive_authority_strings():
    text = Path("memory_candidate_receipt_contract.py").read_text(encoding="utf-8").lower()
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
