import json
from pathlib import Path

import package_preview_receipt_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_package_preview_receipt_contract import main as export_main


FIXED_NOW = "2026-05-22T06:15:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "agent_platform_alignment.json": {"schema_version": "agent_platform_alignment_v0", "read_model_id": "agent_platform_alignment"},
        "agent_identity_actor_router_contract.json": {"schema_version": "agent_identity_actor_router_contract_v0", "read_model_id": "agent_identity_actor_router_contract"},
        "model_selection_policy_contract.json": {"schema_version": "model_selection_policy_contract_v0", "read_model_id": "model_selection_policy_contract"},
        "model_selection_receipt_contract.json": {"schema_version": "model_selection_receipt_contract_v0", "read_model_id": "model_selection_receipt_contract"},
        "agent_package_preview_contract.json": {"schema_version": "agent_package_preview_contract_v0", "read_model_id": "agent_package_preview_contract"},
        "agent_memory_scope_contract.json": {"schema_version": "agent_memory_scope_contract_v0", "read_model_id": "agent_memory_scope_contract"},
        "memory_candidate_receipt_contract.json": {"schema_version": "memory_candidate_receipt_contract_v0", "read_model_id": "memory_candidate_receipt_contract"},
        "tool_protocol_adapter_registry_contract.json": {"schema_version": "tool_protocol_adapter_registry_contract_v0", "read_model_id": "tool_protocol_adapter_registry_contract"},
        "agent_terrain_awareness_readback_contract.json": {"schema_version": "agent_terrain_awareness_readback_contract_v0", "read_model_id": "agent_terrain_awareness_readback_contract"},
        "openclaw_map_manifest.json": {
            "schema_version": "openclaw_map_manifest_v0",
            "read_model_id": "openclaw_map_manifest",
            "map_generation_id": "map_fixture",
            "bundle_hash": "sha256:fixture",
        },
        "operator_threshold_map_contract.json": {"schema_version": "operator_threshold_map_contract_v0", "read_model_id": "operator_threshold_map_contract"},
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_package_preview_receipt_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _examples(payload: dict) -> dict:
    return {item["example_id"]: item for item in payload["example_package_preview_receipts"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "package_preview_receipt_contract"
    assert first["contract_status"] == "deterministic_package_preview_receipt_metadata_only"
    assert first["runtime_authority"] is False
    assert first["live_dispatch_authority"] is False
    assert first["model_call_authority"] is False
    assert first["model_api_execution_authority"] is False
    assert first["actor_agent_activation_authority"] is False
    assert first["tool_execution_authority"] is False
    assert first["queue_autonomy_execution_authority"] is False
    assert first["browser_oauth_account_access_enabled"] is False
    assert first["gmail_calendar_coupa_telegram_enabled"] is False
    assert first["credential_authority"] is False
    assert first["send_submit_approval_enabled"] is False
    assert first["operator_final_authority"] is True


def test_core_doctrine_blocks_preview_from_becoming_dispatch(tmp_path):
    doctrine = _build(tmp_path)["core_doctrine"]

    assert doctrine["model_is_actor"] is True
    assert doctrine["agent_is_character"] is True
    assert doctrine["package_is_deterministic_mission_payload"] is True
    assert doctrine["package_preview_is_not_dispatch"] is True
    assert doctrine["package_preview_is_not_approval"] is True
    assert doctrine["package_preview_is_not_execution"] is True
    assert doctrine["package_preview_does_not_grant_tools"] is True
    assert doctrine["package_preview_does_not_grant_model_access"] is True
    assert doctrine["package_preview_does_not_write_canonical_memory"] is True
    assert doctrine["package_preview_does_not_authorize_account_or_send_submit_approval"] is True


def test_receipt_types_states_and_fields_are_explicit(tmp_path):
    payload = _build(tmp_path)
    schema = payload["package_preview_receipt_schema"]

    assert [item["receipt_type"] for item in payload["receipt_types"]] == list(contract.RECEIPT_TYPES)
    assert [item["preview_state"] for item in payload["preview_states"]] == list(contract.PREVIEW_STATES)
    assert all(item["runtime_dispatch_allowed"] is False for item in payload["receipt_types"])
    assert all(item["runtime_dispatch_allowed"] is False for item in payload["preview_states"])
    assert schema["required_fields"] == list(contract.RECEIPT_FIELDS)
    assert schema["hard_defaults"]["runtime_dispatch_allowed"] is False
    assert schema["hard_defaults"]["model_call_allowed"] is False
    assert schema["hard_defaults"]["tool_execution_allowed"] is False
    assert schema["hard_defaults"]["agent_activation_allowed"] is False
    assert schema["hard_defaults"]["queue_execution_allowed"] is False
    assert schema["hard_defaults"]["account_access_allowed"] is False
    assert schema["hard_defaults"]["send_submit_approval_allowed"] is False
    assert schema["hard_defaults"]["raw_body_included"] is False
    assert schema["missing_required_display_field_result"] == "PACKAGE_PREVIEW_INCOMPLETE"
    for field in [
        "package_preview_receipt_id",
        "package_id",
        "actor_id",
        "model_selection_receipt_reference",
        "requested_tool_adapters",
        "context_included_refs",
        "context_excluded_refs",
        "raw_body_included",
        "runtime_dispatch_allowed",
        "model_call_allowed",
        "tool_execution_allowed",
        "receipt_hash",
    ]:
        assert field in schema["required_fields"]


def test_field_completeness_separates_display_from_future_dispatch(tmp_path):
    model = _build(tmp_path)["package_field_completeness_model"]

    assert model["required_for_display"] == list(contract.DISPLAY_REQUIRED_FIELDS)
    assert model["required_for_future_dispatch"] == list(contract.FUTURE_DISPATCH_REQUIRED_FIELDS)
    assert model["display_missing_result"] == "fail_closed_or_render_incomplete"
    assert model["dispatch_missing_result"] == "preview_may_render_but_dispatch_blocked_future_gated"
    assert model["preview_ready_means_displayable_not_executable"] is True
    assert "package_id" in model["required_for_display"]
    assert "model_selection_receipt" in " ".join(model["required_for_future_dispatch"])
    assert "security_audit_gate" in model["required_for_future_dispatch"]


def test_context_and_authority_policies_block_raw_private_and_live_actions(tmp_path):
    payload = _build(tmp_path)
    context = payload["context_inclusion_exclusion_policy"]
    authority = payload["authority_boundary_policy"]

    assert context["included_context_must_be_reference_based"] is True
    assert context["raw_private_bodies_blocked_by_default"] is True
    assert context["credential_account_session_data_always_blocked"] is True
    assert context["operator_memory_is_candidate_context_not_proof"] is True
    assert context["worker_output_is_receipt_candidate_not_truth"] is True
    assert "credentials/tokens/cookies/API keys" in context["blocked_context"]
    for blocked in [
        "live model calls",
        "actor/agent activation",
        "tool execution",
        "queue/autonomy execution",
        "browser/OAuth/account access",
        "Gmail/calendar/Coupa/Telegram access",
        "send/submit/approval",
        "C-drive artifact writes",
    ]:
        assert blocked in authority["blocked_now"]
    assert authority["package_or_actor_self_authorization_allowed"] is False


def test_examples_cover_required_package_preview_receipts(tmp_path):
    examples = _examples(_build(tmp_path))

    assert set(examples) == {
        "cassandra_capital_hilton_invoice_review",
        "chief_check_engine_diagnostic",
        "guardian_protected_evidence_review",
        "niles_struna_creative_metadata_review",
        "hermes_architecture_doctrine_review",
        "codex_backend_contract_implementation",
        "gemini_antigravity_visual_polish",
        "agentic_loop_classification",
    }
    capital = examples["cassandra_capital_hilton_invoice_review"]
    assert capital["actor_id"] == "cassandra"
    assert capital["target_world"] == "Finance"
    assert capital["sensitivity"] == "FINANCE_PROTECTED"
    assert "Coupa protected proof metadata" in capital["missing_proof"]
    assert "coupa_adapter" in capital["blocked_tool_adapters"]
    assert "GUARDIAN_GATE_REQUIRED" in capital["blocked_reasons"]
    chief = examples["chief_check_engine_diagnostic"]
    assert "remount" in chief["blocked_tool_adapters"]
    guardian = examples["guardian_protected_evidence_review"]
    assert guardian["guardian_gate_status"] == "guardian_review_required_but_not_self_authorizing"
    niles = examples["niles_struna_creative_metadata_review"]
    assert niles["target_world"] == "Music / Art"
    hermes = examples["hermes_architecture_doctrine_review"]
    assert hermes["package_type"] == "architecture_review"
    codex = examples["codex_backend_contract_implementation"]
    assert "network" in codex["blocked_tool_adapters"]
    gemini = examples["gemini_antigravity_visual_polish"]
    assert "external_retained_memory" in gemini["blocked_tool_adapters"]
    loop = examples["agentic_loop_classification"]
    assert "repo_b_execution" in loop["blocked_tool_adapters"]
    for example in examples.values():
        assert example["authority_level_granted"] == "preview_only"
        assert example["runtime_dispatch_allowed"] is False
        assert example["model_call_allowed"] is False
        assert example["tool_execution_allowed"] is False
        assert example["agent_activation_allowed"] is False
        assert example["queue_execution_allowed"] is False
        assert example["account_access_allowed"] is False
        assert example["send_submit_approval_allowed"] is False
        assert example["raw_body_included"] is False
        assert example["preview_ready_means_displayable_not_executable"] is True


def test_revocation_quarantine_policy_blocks_unsafe_packages(tmp_path):
    policy = _build(tmp_path)["revocation_quarantine_policy"]

    for trigger in [
        "package claims live authority",
        "package includes raw private bodies without gate",
        "package includes credentials/secrets/account/session data",
        "package references unknown actor/model/tool",
        "package skips memory scope",
        "package skips model selection",
        "package skips tool adapter gates",
        "package lacks stop conditions",
        "package tries to self-authorize",
        "malformed receipt",
        "missing receipt hash",
    ]:
        assert trigger in policy["quarantine_triggers"]
    for trigger in [
        "source contract changes",
        "stable map generation replaced",
        "model policy changed",
        "memory candidate revoked",
        "tool adapter quarantined",
        "Guardian gate revoked",
        "Operator approval revoked",
        "security audit blocks lane",
    ]:
        assert trigger in policy["revocation_triggers"]
    assert policy["missing_or_malformed_receipt_result"] == "PACKAGE_PREVIEW_QUARANTINED"
    assert policy["revocation_blocks_future_dispatch"] is True


def test_evidence_sources_are_bounded_and_source_presence_grants_no_authority(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    for source_id in [
        "agent_platform_alignment",
        "agent_identity_actor_router_contract",
        "model_selection_policy_contract",
        "model_selection_receipt_contract",
        "agent_package_preview_contract",
        "agent_memory_scope_contract",
        "memory_candidate_receipt_contract",
        "tool_protocol_adapter_registry_contract",
        "agent_terrain_awareness_readback_contract",
        "stable_map_bundle",
        "operator_threshold_map_contract",
    ]:
        assert sources[source_id]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["credentials_or_secrets_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_mission_control_and_stable_map_guidance_are_present(tmp_path):
    payload = _build(tmp_path)
    guidance = payload["mission_control_surface_guidance"]
    stable = payload["stable_map_integration"]

    assert "mission" in guidance["package_preview_card"]
    assert "authority boundary" in guidance["package_preview_card"]
    assert "Layer 1: operator orientation" in guidance["package_detail_layers"]
    assert "package types supported" in guidance["dossier_integration"]
    assert "package previews ready for that world" in guidance["world_integration"]
    assert "live dispatch buttons" in guidance["hide_or_block"]
    assert "model launch controls" in guidance["hide_or_block"]
    assert "tool execution controls" in guidance["hide_or_block"]
    assert "Gmail/calendar/Coupa/Telegram controls" in guidance["hide_or_block"]
    assert "agent chose its own package claims" in guidance["hide_or_block"]
    assert stable["contract_generated_as_read_model"] is True
    assert stable["summary_included_in_stable_map_bundle_now"] is False
    assert stable["safe_summary_to_include_next"]["contract_id"] == "package_preview_receipt_contract"
    assert stable["safe_summary_to_include_next"]["receipt_types_count"] == len(contract.RECEIPT_TYPES)
    assert stable["safe_summary_to_include_next"]["example_package_previews_count"] == 8
    assert stable["safe_summary_to_include_next"]["current_dispatch_authority"] is False


def test_recommended_next_lanes_match_package_preview_receipt_maturity_path(tmp_path):
    lanes = [item["lane_id"] for item in _build(tmp_path)["recommended_next_lanes"]]

    assert lanes == [
        "tool_adapter_receipt_v0",
        "package_preview_surface_mission_control_integration_v0",
        "memory_review_promotion_surface_v0",
        "model_router_implementation_plan_v0",
        "capital_hilton_proof_metadata_packet_v0",
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
    assert summary["receipt_type_count"] == len(contract.RECEIPT_TYPES)
    assert summary["preview_state_count"] == len(contract.PREVIEW_STATES)
    assert summary["example_count"] == 8
    assert summary["runtime_dispatch_authority_added"] is False
    assert summary["model_call_authority_added"] is False
    assert summary["tool_execution_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "package_preview_receipt_contract"
    assert "Package Preview Receipt Contract v0" in operator
    assert "PACKAGE_PREVIEW_COMPILED" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    contract.export_package_preview_receipt_contract(repo_root=tmp_path, export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_network_delete_or_c_drive_authority_strings():
    text = Path("package_preview_receipt_contract.py").read_text(encoding="utf-8").lower()
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
