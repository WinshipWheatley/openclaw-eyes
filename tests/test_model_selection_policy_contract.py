import json
from pathlib import Path

import model_selection_policy_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_model_selection_policy_contract import main as export_main


FIXED_NOW = "2026-05-21T23:30:00+00:00"


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
            "actors": [{"actor_id": actor_id} for actor_id in contract.ACTOR_IDS],
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
            "package_types": [{"package_type": package_type} for package_type in contract.PACKAGE_TYPES],
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "read_model_id": "operator_workbench_actor_host_registry",
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
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_model_selection_policy_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _model_classes(payload: dict) -> dict:
    return {item["model_class_id"]: item for item in payload["model_classes"]}


def _actor_policies(payload: dict) -> dict:
    return {item["actor_id"]: item for item in payload["actor_model_policy"]}


def _package_policies(payload: dict) -> dict:
    return {item["package_type"]: item for item in payload["package_type_model_policy"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "model_selection_policy_contract"
    assert first["contract_status"] == "deterministic_model_selection_policy_metadata_only"
    assert first["runtime_authority"] is False
    assert first["model_call_authority"] is False
    assert first["external_model_authority"] is False
    assert first["local_model_authority"] is False
    assert first["tool_execution_authority"] is False
    assert first["credential_authority"] is False
    assert first["routing_execution_authority"] is False
    assert first["operator_final_authority"] is True


def test_model_classes_are_generic_and_policy_oriented(tmp_path):
    payload = _build(tmp_path)
    classes = _model_classes(payload)

    assert set(classes) == set(contract.MODEL_CLASSES)
    assert classes["blocked_no_model"]["current_authority"] == "active_safe_default"
    assert classes["human_operator"]["current_authority"] == "human_decision_authority_only"
    assert "finance_or_ap_sensitive" in classes["local_sensitive"]["sensitivity_allowed"]
    assert classes["external_deep_reasoner"]["current_authority"] == "blocked_no_external_model_call"
    assert "credential_or_oauth_related" in classes["external_fast_worker"]["unsuitable_package_types"]
    for model_class in classes.values():
        assert model_class["display_name"]
        assert model_class["intended_use"]
        assert model_class["model_callable_now"] is False
        assert model_class["may_self_select"] is False
        assert set(model_class["suitable_package_types"]).issubset(set(contract.PACKAGE_TYPES))
        assert set(model_class["unsuitable_package_types"]).issubset(set(contract.PACKAGE_TYPES))


def test_required_selection_inputs_fail_closed_when_missing_or_unknown(tmp_path):
    payload = _build(tmp_path)
    inputs = payload["selection_inputs_required"]

    for required in [
        "package_id",
        "package_type",
        "actor_id",
        "data_sensitivity",
        "clearance_level",
        "authority_boundary",
        "allowed_capabilities",
        "forbidden_capabilities",
        "proof_requirements",
        "receipt_requirements",
    ]:
        assert required in inputs["required_before_model_selection_is_valid"]
    assert inputs["invalid_if_missing"] is True
    assert inputs["unknown_sensitivity_result"] == "blocked_no_model"
    assert inputs["unknown_actor_result"] == "blocked_no_model"
    assert inputs["unknown_package_type_result"] == "blocked_no_model"


def test_sensitivity_policy_prefers_local_private_or_blocked(tmp_path):
    payload = _build(tmp_path)
    policy = payload["sensitivity_policy"]

    assert policy["default_for_unknown"] == "unknown_fail_closed"
    assert policy["sensitive_private_defaults_to"] == "local_sensitive_or_blocked_no_model"
    assert policy["client_legal_finance_defaults_to"] == "local_sensitive_or_blocked_no_model"
    assert policy["credential_or_oauth_related_defaults_to"] == "blocked_no_model"
    assert "unknown sensitivity" in policy["external_model_blocked_for"]
    assert "Operator preview/approval receipt exists" in policy["external_model_future_eligible_only_when"]
    assert "Guardian gate exists for sensitive/protected/approval-adjacent work" in policy["external_model_future_eligible_only_when"]


def test_actor_model_policy_covers_known_actors_and_blocks_self_routing(tmp_path):
    payload = _build(tmp_path)
    actors = _actor_policies(payload)

    assert set(actors) == set(contract.ACTOR_IDS)
    assert actors["operator_winship"]["allowed_current_model_classes"] == ["human_operator"]
    assert actors["operator_winship"]["blocked_model_classes"]
    for actor_id in set(contract.ACTOR_IDS) - {"operator_winship"}:
        assert actors[actor_id]["allowed_current_model_classes"] == ["blocked_no_model"]
        assert actors[actor_id]["requires_operator_preview"] is True
        assert actors[actor_id]["can_self_select_model"] is False
        assert actors[actor_id]["can_upgrade_model_class"] is False
        assert actors[actor_id]["routing_execution_allowed_now"] is False
    assert actors["guardian"]["requires_guardian_gate"] is True
    assert "local_sensitive" in actors["guardian"]["preferred_model_classes"]
    assert "external_code_worker" in actors["codex"]["future_eligible_model_classes"]
    assert "external_fast_worker" in actors["gemini_antigravity"]["future_eligible_model_classes"]
    for policy in actors.values():
        assert set(policy["preferred_model_classes"]).issubset(set(contract.MODEL_CLASSES))
        assert set(policy["allowed_current_model_classes"]).issubset(set(contract.MODEL_CLASSES))
        assert set(policy["future_eligible_model_classes"]).issubset(set(contract.MODEL_CLASSES))
        assert set(policy["blocked_model_classes"]).issubset(set(contract.MODEL_CLASSES))


def test_package_type_policy_blocks_sensitive_and_portal_work(tmp_path):
    payload = _build(tmp_path)
    policies = _package_policies(payload)

    assert set(policies) == set(contract.PACKAGE_TYPES)
    assert policies["finance_ap_review"]["sensitivity_default"] == "finance_or_ap_sensitive"
    assert policies["finance_ap_review"]["requires_guardian_gate"] is True
    assert policies["finance_ap_review"]["safe_default_result"] == "blocked_no_model_until_finance_proof_and_security_gate_exist"
    assert policies["credential_or_oauth_related"]["safe_default_result"] == "blocked_no_model"
    assert policies["browser_or_portal_related"]["safe_default_result"] == "blocked_no_model"
    assert "external_deep_reasoner" in policies["credential_or_oauth_related"]["blocked_model_classes"]
    for policy in policies.values():
        assert set(policy["preferred_model_classes"]).issubset(set(contract.MODEL_CLASSES))
        assert set(policy["allowed_current_model_classes"]).issubset(set(contract.MODEL_CLASSES))
        assert set(policy["future_eligible_model_classes"]).issubset(set(contract.MODEL_CLASSES))
        assert set(policy["blocked_model_classes"]).issubset(set(contract.MODEL_CLASSES))
        assert policy["allowed_current_model_classes"] == ["blocked_no_model"]
        assert policy["future_execution_allowed_now"] is False


def test_blocked_model_uses_cover_required_boundaries(tmp_path):
    payload = _build(tmp_path)
    blocked = {item["blocked_use_id"] for item in payload["blocked_model_uses"]}

    assert {
        "email_send",
        "calendar_mutation",
        "browser_coupa_portal_use",
        "credential_or_oauth_handling",
        "protected_file_access_without_gate",
        "broad_filesystem_indexing",
        "hidden_memory_capture",
        "surveillance_background_monitoring",
        "autonomous_tool_execution",
        "self_authorized_routing",
        "external_model_sensitive_data_without_gate",
    }.issubset(blocked)


def test_confidence_policy_and_mission_control_guidance_are_operator_first(tmp_path):
    payload = _build(tmp_path)
    confidence = payload["confidence_policy"]
    guidance = payload["mission_control_surface_guidance"]

    assert confidence["show_confidence_only_when"] == "uncertainty changes the operator's next safe move"
    assert confidence["unknown_or_missing_context"] == "UNKNOWN_FAIL_CLOSED"
    assert confidence["blocked_no_model_is_valid_result"] is True
    assert guidance["top_layer"] == "Recommended model posture"
    assert "models are currently callable" not in guidance["top_layer"]
    assert "live model availability" in guidance["do_not_present_as"]
    assert guidance["show_blocked_no_model_as"].startswith("safe fail-closed")


def test_future_receipts_are_required_before_future_execution(tmp_path):
    payload = _build(tmp_path)
    receipts = payload["future_receipt_requirements"]

    assert "model selection decision receipt" in receipts["required_before_future_model_execution"]
    assert "package compiler boundary validation receipt" in receipts["required_before_future_model_execution"]
    assert "Guardian gate receipt for sensitive/protected/approval-adjacent work" in receipts["required_before_future_model_execution"]
    assert "post-result receipt" in receipts["required_before_future_model_execution"]
    assert receipts["natural_language_claims_count_as_proof"] is False


def test_evidence_sources_are_bounded_and_do_not_grant_authority(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    assert sources["agent_platform_alignment"]["present"] is True
    assert sources["agent_identity_actor_router_contract"]["present"] is True
    assert sources["package_compiler_contract"]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["credentials_or_secrets_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_recommended_next_lanes_match_model_policy_maturity_path(tmp_path):
    payload = _build(tmp_path)
    lanes = [item["lane_id"] for item in payload["recommended_next_lanes"]]

    assert lanes == [
        "agent_package_preview_contract_v0",
        "agent_memory_scope_contract_v0",
        "tool_protocol_adapter_registry_v0",
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
    assert summary["model_class_count"] == len(contract.MODEL_CLASSES)
    assert summary["actor_policy_count"] == len(contract.ACTOR_IDS)
    assert summary["package_type_policy_count"] == len(contract.PACKAGE_TYPES)
    assert summary["runtime_authority_added"] is False
    assert summary["model_call_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "model_selection_policy_contract"
    assert "Model Selection Policy Contract v0" in operator
    assert "blocked_no_model" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    contract.export_model_selection_policy_contract(
        repo_root=tmp_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_network_or_c_drive_authority_strings():
    text = Path("model_selection_policy_contract.py").read_text(encoding="utf-8").lower()
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
