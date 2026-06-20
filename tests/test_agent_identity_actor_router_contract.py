import json
from pathlib import Path

import agent_identity_actor_router_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_agent_identity_actor_router_contract import main as export_main


FIXED_NOW = "2026-05-21T22:00:00+00:00"


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
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
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
        "cassandra_email_calendar_delta_detangle.json": {
            "schema_version": "cassandra_email_calendar_delta_detangle_v0",
            "read_model_id": "cassandra_email_calendar_delta_detangle",
        },
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "read_model_id": "operator_nested_lane_mission_package_spine",
        },
        "agent_platform_alignment_OPERATOR.md": {"schema_version": "operator_text_placeholder"},
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_agent_identity_actor_router_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _actors(payload: dict) -> dict:
    return {item["actor_id"]: item for item in payload["actors"]}


def _rules(payload: dict) -> dict:
    return {item["rule_id"]: item for item in payload["routing_decision_rules"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "agent_identity_actor_router_contract"
    assert first["contract_status"] == "deterministic_identity_and_routing_metadata_only"
    assert first["runtime_authority"] is False
    assert first["activation_allowed"] is False
    assert first["model_call_authority"] is False
    assert first["agent_call_authority"] is False
    assert first["external_tool_authority"] is False
    assert first["credential_authority"] is False
    assert first["actor_self_authority"] is False
    assert first["routing_execution_authority"] is False
    assert first["operator_final_authority"] is True


def test_known_actors_are_structured_for_mission_control(tmp_path):
    payload = _build(tmp_path)
    actors = _actors(payload)

    assert set(actors) == {
        "operator_winship",
        "chief",
        "guardian",
        "cassandra",
        "hermes",
        "niles",
        "codex",
        "gemini_antigravity",
    }
    for actor in actors.values():
        assert actor["display_name"]
        assert actor["class"] in contract.ACTOR_CLASSES
        assert actor["primary_role"]
        assert actor["self_identity"]
        assert actor["first_person_policy"]
        assert actor["operator_reference_policy"]
        assert isinstance(actor["suitable_domains"], list)
        assert isinstance(actor["unsuitable_domains"], list)
        assert actor["can_self_assign_authority"] is False
        assert actor["clearance_level"] in contract.CLEARANCE_LEVELS
        assert actor["notes_for_mission_control"]


def test_actor_roles_domains_packages_and_clearance_boundaries(tmp_path):
    payload = _build(tmp_path)
    actors = _actors(payload)

    assert "Security" in actors["guardian"]["suitable_domains"]
    assert actors["guardian"]["requires_guardian_gate"] is True
    assert "protected_access_review_package" in actors["guardian"]["package_types"]
    assert "Finance" in actors["cassandra"]["suitable_domains"]
    assert "send email" in actors["cassandra"]["blocked_current_actions"]
    assert "Music / Art" in actors["niles"]["suitable_domains"]
    assert "code_implementation_package" in actors["codex"]["package_types"]
    assert actors["gemini_antigravity"]["class"] == "implementation_worker"
    assert actors["operator_winship"]["clearance_level"] == "operator_final_authority"
    assert actors["operator_winship"]["requires_operator_preview"] is False


def test_routing_modes_and_decision_rules_cover_required_cases(tmp_path):
    payload = _build(tmp_path)
    modes = {item["routing_mode"]: item for item in payload["routing_modes"]}
    rules = _rules(payload)

    for mode in contract.ROUTING_MODES:
        assert mode in modes
        assert modes[mode]["live_chat_or_execution_allowed"] is False
    assert rules["safety_security_protected_access_first"]["deterministic_order"][0] == "guardian"
    assert rules["code_implementation_scoped_worker"]["routing_mode"] == "implementation_worker_lane"
    assert "codex" in rules["code_implementation_scoped_worker"]["primary_actor_ids"]
    assert "gemini_antigravity" in rules["code_implementation_scoped_worker"]["primary_actor_ids"]
    assert rules["music_art_creative_first"]["deterministic_order"][0] == "niles"
    assert rules["communications_finance_ap_first"]["deterministic_order"][:2] == ["cassandra", "guardian"]
    assert rules["big_picture_architecture_doctrine"]["deterministic_order"][:2] == ["hermes", "chief"]
    assert rules["work_board_check_engine_queue"]["deterministic_order"][0] == "chief"
    assert rules["final_action_authority"]["primary_actor_ids"] == ["operator_winship"]
    assert rules["whole_system_uncertainty"]["routing_mode"] == "all_agent_review"


def test_package_preview_and_receipts_are_required_before_future_execution(tmp_path):
    payload = _build(tmp_path)

    preview = payload["package_preview_requirements"]
    receipts = payload["future_receipt_requirements"]
    assert preview["required_before_any_future_route"] is True
    assert "actor_id" in preview["must_include"]
    assert "credentials" in preview["must_not_include"]
    assert "valid package compiler boundary receipt" in receipts["required_before_routing_executable"]
    assert "Guardian gate receipt for protected or approval-adjacent work" in receipts["required_before_routing_executable"]
    assert receipts["natural_language_success_claims_count_as_proof"] is False


def test_actor_perspective_policy_keeps_agent_self_distinct_from_operator(tmp_path):
    payload = _build(tmp_path)
    actors = _actors(payload)

    assert payload["machine_proof"]["required_agent_self_identities_present"] is True
    assert payload["machine_proof"]["all_actors_have_operator_reference_policy"] is True
    assert payload["machine_proof"]["operator_first_person_blur_allowed"] is False
    assert "maestro" in payload["perspective_registry"]["agents"]
    for actor_id in ("cassandra", "chief", "guardian", "hermes", "niles"):
        actor = actors[actor_id]
        assert actor["self_identity"]["display_name"] == actor["display_name"]
        assert "Winship" in actor["operator_reference_policy"]
        assert "never" in actor["forbidden_identity_blur"].lower()
    maestro = payload["perspective_registry"]["agents"]["maestro"]
    assert maestro["self_identity"]["display_name"] == "Maestro"
    assert "Winship" in maestro["operator_reference_policy"]
    assert "never" in maestro["forbidden_identity_blur"].lower()


def test_confidence_policy_is_not_confidence_theater(tmp_path):
    payload = _build(tmp_path)
    policy = payload["uncertainty_and_confidence_policy"]

    assert policy["show_confidence_only_when"] == "uncertainty changes the operator's next safe move"
    assert policy["hide_when"] == "routing is deterministic and no action is being dispatched"
    assert policy["unknown_actor_or_model"] == "UNKNOWN_FAIL_CLOSED"


def test_mission_control_guidance_is_helm_oriented(tmp_path):
    payload = _build(tmp_path)
    guidance = payload["mission_control_surface_guidance"]

    assert guidance["top_layer"] == "Who should look at this?"
    assert "what they must not do" in guidance["middle_layer"]
    assert "Package preview" in guidance["lower_layer"]
    assert "live agent presence" in guidance["do_not_present_as"]
    assert "fake availability" in guidance["do_not_present_as"]


def test_evidence_sources_are_bounded_and_do_not_grant_authority(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    assert sources["agent_platform_alignment"]["present"] is True
    assert sources["package_compiler_contract"]["present"] is True
    assert sources["operator_workbench_actor_host_registry"]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_recommended_next_lanes_match_router_contract_maturity_path(tmp_path):
    payload = _build(tmp_path)
    lanes = [item["lane_id"] for item in payload["recommended_next_lanes"]]

    assert lanes == [
        "model_selection_policy_contract_v0",
        "agent_package_preview_contract_v0",
        "mission_control_actor_routing_surface_v0",
        "tool_protocol_adapter_registry_v0",
        "agent_memory_scope_contract_v0",
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
    assert summary["actor_count"] == 8
    assert summary["routing_rule_count"] == 8
    assert summary["runtime_authority_added"] is False
    assert summary["model_call_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "agent_identity_actor_router_contract"
    assert "Agent Identity + Actor Router Contract v0" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    contract.export_agent_identity_actor_router_contract(
        repo_root=tmp_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_network_or_c_drive_authority_strings():
    text = Path("agent_identity_actor_router_contract.py").read_text(encoding="utf-8").lower()
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
