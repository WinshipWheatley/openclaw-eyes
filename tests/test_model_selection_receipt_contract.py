import json
from pathlib import Path

import model_selection_receipt_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_model_selection_receipt_contract import main as export_main


FIXED_NOW = "2026-05-22T04:30:00+00:00"


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
        "memory_candidate_receipt_contract.json": {
            "schema_version": "memory_candidate_receipt_contract_v0",
            "read_model_id": "memory_candidate_receipt_contract",
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "read_model_id": "guardian_protected_access_gate_spec",
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
    return contract.build_model_selection_receipt_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _models(payload: dict) -> dict:
    return {item["model_class_id"]: item for item in payload["model_classes"]}


def _actors(payload: dict) -> dict:
    return {item["actor_id"]: item for item in payload["actor_model_selection_rules"]}


def _sensitivity(payload: dict) -> dict:
    return {item["sensitivity"]: item for item in payload["sensitivity_routing_rules"]}


def _examples(payload: dict) -> dict:
    return {item["example_id"]: item for item in payload["example_model_selection_receipts"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "model_selection_receipt_contract"
    assert first["contract_status"] == "deterministic_model_selection_receipt_metadata_only"
    assert first["runtime_authority"] is False
    assert first["model_call_authority"] is False
    assert first["model_api_execution_authority"] is False
    assert first["model_router_runtime_authority"] is False
    assert first["agent_activation_authority"] is False
    assert first["tool_execution_authority"] is False
    assert first["hidden_model_routing_enabled"] is False
    assert first["external_retained_memory_enabled"] is False
    assert first["operator_final_authority"] is True


def test_core_doctrine_blocks_self_selection_and_policy_override(tmp_path):
    doctrine = _build(tmp_path)["core_doctrine"]

    assert doctrine["model_is_actor"] is True
    assert doctrine["agent_is_character"] is True
    assert doctrine["package_is_deterministic_mission_payload"] is True
    assert doctrine["model_cannot_choose_itself"] is True
    assert doctrine["agent_cannot_choose_its_own_model"] is True
    assert doctrine["package_cannot_override_model_policy"] is True
    assert doctrine["worker_cannot_upgrade_itself"] is True
    assert doctrine["sensitive_context_external_routing_requires_policy_gates_redaction_and_receipts"] is True


def test_decision_types_states_and_receipt_fields_are_explicit(tmp_path):
    payload = _build(tmp_path)
    schema = payload["selection_receipt_schema"]

    assert [item["decision_type"] for item in payload["decision_types"]] == list(contract.DECISION_TYPES)
    assert [item["selection_state"] for item in payload["selection_states"]] == list(contract.SELECTION_STATES)
    assert all(item["creates_live_model_call_authority"] is False for item in payload["decision_types"])
    assert all(item["runtime_dispatch_allowed"] is False for item in payload["selection_states"])
    assert schema["required_fields"] == list(contract.RECEIPT_FIELDS)
    assert schema["hard_defaults"]["runtime_dispatch_allowed"] is False
    assert schema["hard_defaults"]["model_call_performed"] is False
    assert schema["hard_defaults"]["authority_level_granted"] == "preview_only"
    assert schema["missing_required_field_result"] == "MODEL_UNKNOWN_FAIL_CLOSED"
    for field in [
        "model_selection_receipt_id",
        "package_id",
        "actor_id",
        "requested_model_class",
        "selected_model_class",
        "decision_type",
        "selection_state",
        "memory_candidate_receipt_refs",
        "requested_tool_adapters",
        "blocked_tool_adapters",
        "runtime_dispatch_allowed",
        "model_call_performed",
        "receipt_hash",
        "what_keeps_selection_blocked",
    ]:
        assert field in schema["required_fields"]


def test_model_classes_align_with_policy_and_default_blocked_no_model(tmp_path):
    models = _models(_build(tmp_path))

    assert set(models) == set(contract.MODEL_CLASSES)
    assert models["blocked_no_model"]["current_authority_posture"] == "active_safe_default"
    assert models["human_operator"]["current_authority_posture"] == "human_decision_authority_only"
    for model in models.values():
        assert model["model_callable_now"] is False
        assert model["may_self_select"] is False
        assert model["receipt_requirement"]
        assert model["external_retention_rule"]
    assert models["external_deep_reasoner"]["current_authority_posture"] == "blocked_no_external_model_call"
    assert "external retention blocked" in models["external_deep_reasoner"]["external_retention_rule"]
    assert "credential context" in models["local_sensitive"]["what_blocks_selection"]
    assert "broad context" in models["external_code_worker"]["what_blocks_selection"]


def test_policy_input_model_fails_closed_on_missing_inputs(tmp_path):
    model = _build(tmp_path)["policy_input_model"]

    assert model["required_policy_inputs"] == list(contract.POLICY_INPUTS_REQUIRED)
    assert model["missing_input_result"] == "MODEL_UNKNOWN_FAIL_CLOSED"
    assert model["missing_package_detail_result"] == "MODEL_REQUIRES_PACKAGE_RECOMPILE"
    assert model["fail_closed_reasons"] == list(contract.FAIL_CLOSED_REASONS)
    for reason in [
        "UNKNOWN_ACTOR",
        "UNKNOWN_MODEL_CLASS",
        "MISSING_PACKAGE_PREVIEW",
        "MISSING_MEMORY_SCOPE",
        "SENSITIVITY_UNKNOWN",
        "TOOL_ADAPTER_UNKNOWN",
        "EXTERNAL_RETENTION_BLOCKED",
        "RAW_PRIVATE_CONTEXT_BLOCKED",
        "CREDENTIAL_CONTEXT_BLOCKED",
        "AUTHORITY_NOT_GRANTED",
    ]:
        assert reason in model["fail_closed_reasons"]


def test_sensitivity_routing_blocks_credentials_accounts_and_unknowns(tmp_path):
    rules = _sensitivity(_build(tmp_path))

    assert rules["CREDENTIAL_OR_SECRET"]["default_result"] == "blocked_no_model"
    assert rules["ACCOUNT_ACCESS"]["default_result"] == "blocked_no_model"
    assert rules["UNKNOWN_SENSITIVE_FAIL_CLOSED"]["default_result"] == "blocked_no_model"
    assert rules["FINANCE_PROTECTED"]["guardian_gate_required"] is True
    assert rules["FINANCE_PROTECTED"]["operator_approval_required"] is True
    assert "Coupa/Excel raw bodies" in rules["FINANCE_PROTECTED"]["blocked_contexts"]
    assert rules["CLIENT_PRIVATE"]["external_model_rule"].startswith("external blocked")
    assert "external retention" in rules["LEGAL_OR_COMPLIANCE"]["blocked_contexts"]
    assert rules["PUBLIC_OR_LOW"]["external_model_rule"].startswith("external may be future-eligible")


def test_actor_model_selection_rules_cover_known_actor_postures(tmp_path):
    actors = _actors(_build(tmp_path))

    assert set(actors) == set(contract.KNOWN_ACTOR_IDS)
    assert actors["operator_winship"]["current_live_model_class"] == "human_operator"
    for actor_id in set(contract.KNOWN_ACTOR_IDS) - {"operator_winship"}:
        assert actors[actor_id]["current_live_model_class"] == "blocked_no_model"
        assert actors[actor_id]["can_self_select_model"] is False
        assert actors[actor_id]["can_upgrade_model_class"] is False
        assert actors[actor_id]["runtime_dispatch_allowed_now"] is False
    assert "local_sensitive" in actors["guardian"]["future_eligible_model_classes"]
    assert "local_sensitive" in actors["cassandra"]["future_eligible_model_classes"]
    assert "external_deep_reasoner" in actors["hermes"]["future_eligible_model_classes"]
    assert "external_multimodal" in actors["niles"]["future_eligible_model_classes"]
    assert "external_code_worker" in actors["codex"]["future_eligible_model_classes"]
    assert "external_fast_worker" in actors["gemini_antigravity"]["future_eligible_model_classes"]


def test_package_binding_requires_preview_policy_memory_tools_gates_and_receipts(tmp_path):
    binding = _build(tmp_path)["package_binding_rule"]

    for requirement in [
        "package preview exists",
        "actor/agent is known",
        "model policy exists",
        "memory scope permits included context",
        "sensitivity is classified",
        "requested tools/adapters are known and allowed or explicitly blocked",
        "Guardian/Operator gates are identified",
        "receipt requirements exist",
        "stop conditions exist",
        "runtime authority is explicit and currently false unless future-approved",
    ]:
        assert requirement in binding["package_may_receive_model_selection_receipt_only_if"]
    assert binding["fail_closed_reasons"] == list(contract.FAIL_CLOSED_REASONS)
    assert binding["unknown_package_result"] == "MODEL_UNKNOWN_FAIL_CLOSED"
    assert binding["model_or_actor_self_selection_allowed"] is False


def test_receipt_revocation_and_quarantine_policy_blocks_hidden_or_unsafe_selection(tmp_path):
    policy = _build(tmp_path)["receipt_revocation_quarantine_policy"]

    for trigger in [
        "model selected without policy reference",
        "model selected without package preview",
        "model selected with unknown sensitivity",
        "external model selected with private/protected context",
        "credential/account context included",
        "memory scope violation",
        "tool adapter violation",
        "actor self-selected model",
        "model call occurred without receipt",
        "external retained memory detected",
        "receipt malformed",
        "receipt hash missing",
        "output claims authority not granted",
    ]:
        assert trigger in policy["quarantine_triggers"]
    for trigger in [
        "policy changed",
        "sensitivity classification changed",
        "memory candidate revoked",
        "package preview revoked",
        "tool adapter quarantined",
        "Guardian gate revoked",
        "Operator approval revoked",
        "model provider no longer eligible",
        "receipt conflict discovered",
    ]:
        assert trigger in policy["revocation_triggers"]
    assert policy["missing_or_malformed_receipt_result"] == "SELECTION_QUARANTINED"
    assert policy["quarantine_is_non_destructive"] is True


def test_examples_cover_required_model_selection_scenarios(tmp_path):
    examples = _examples(_build(tmp_path))

    assert set(examples) == {
        "chief_check_engine_diagnostic_package",
        "cassandra_capital_hilton_invoice_review",
        "codex_backend_contract_implementation",
        "niles_creative_metadata_review",
        "guardian_protected_evidence_review",
        "gemini_antigravity_visual_polish",
        "unknown_tool_memory_package",
    }
    chief = examples["chief_check_engine_diagnostic_package"]
    assert chief["requested_model_class"] == "external_deep_reasoner"
    assert chief["selected_model_class"] == "blocked_no_model"
    assert chief["runtime_dispatch_allowed"] is False
    assert chief["model_call_performed"] is False
    capital = examples["cassandra_capital_hilton_invoice_review"]
    assert capital["sensitivity"] == "FINANCE_PROTECTED"
    assert "GUARDIAN_GATE_REQUIRED" in capital["blocked_reasons"]
    assert "TOOL_ADAPTER_BLOCKED" in capital["blocked_reasons"]
    codex = examples["codex_backend_contract_implementation"]
    assert codex["selection_state"] == "SELECTION_ALLOWED_PREVIEW_ONLY"
    unknown = examples["unknown_tool_memory_package"]
    assert unknown["decision_type"] == "MODEL_UNKNOWN_FAIL_CLOSED"
    assert unknown["selection_state"] == "UNKNOWN_FAIL_CLOSED"
    for example in examples.values():
        assert example["authority_level_granted"] == "preview_only"
        assert example["retention_policy"] == "no_external_retained_memory"
        assert example["runtime_dispatch_allowed"] is False
        assert example["model_call_performed"] is False
        assert example["selected_model_class"] in contract.MODEL_CLASSES


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
        "memory_candidate_receipt_contract",
        "stable_map_bundle",
        "threshold_map_contract",
        "guardian_protected_access_gate_spec",
    ]:
        assert key in relationships
    assert "requested model class" in guidance["model_selection_preview"]
    assert "runtime dispatch allowed yes/no" in guidance["model_selection_preview"]
    assert "current live model: blocked/no model unless explicitly future-gated" in guidance["actor_detail"]
    assert "model launch controls" in guidance["hide_or_block"]
    assert "provider credential prompts" in guidance["hide_or_block"]
    assert "agent chose its own model claims" in guidance["hide_or_block"]
    assert stable["registry_generated_as_read_model"] is True
    assert stable["summary_included_in_stable_map_bundle_now"] is False
    assert stable["safe_summary_to_include_next"]["model_classes_count"] == len(contract.MODEL_CLASSES)
    assert stable["safe_summary_to_include_next"]["next_recommended_lane"] == "package_preview_receipt_v0"


def test_evidence_sources_are_bounded_and_do_not_grant_authority(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    assert sources["agent_platform_alignment"]["present"] is True
    assert sources["model_selection_policy_contract"]["present"] is True
    assert sources["agent_package_preview_contract"]["present"] is True
    assert sources["memory_candidate_receipt_contract"]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["credentials_or_secrets_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_recommended_next_lanes_match_receipt_maturity_path(tmp_path):
    lanes = [item["lane_id"] for item in _build(tmp_path)["recommended_next_lanes"]]

    assert lanes == [
        "package_preview_receipt_v0",
        "tool_adapter_receipt_v0",
        "memory_review_promotion_surface_v0",
        "mission_control_package_preview_actor_routing_surface_v0",
        "model_router_implementation_plan_v0",
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
    assert summary["decision_type_count"] == len(contract.DECISION_TYPES)
    assert summary["model_class_count"] == len(contract.MODEL_CLASSES)
    assert summary["example_count"] == 7
    assert summary["model_call_authority_added"] is False
    assert summary["model_router_runtime_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "model_selection_receipt_contract"
    assert "Model Selection Receipt Contract v0" in operator
    assert "MODEL_BLOCKED" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    contract.export_model_selection_receipt_contract(repo_root=tmp_path, export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_network_delete_or_c_drive_authority_strings():
    text = Path("model_selection_receipt_contract.py").read_text(encoding="utf-8").lower()
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
