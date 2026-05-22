import json
from pathlib import Path

import security_pass_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_security_pass_contract import main as export_main


FIXED_NOW = "2026-05-22T15:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    for relative in contract.MARKDOWN_TERRAIN_SYSTEMS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n", encoding="utf-8")

    read_models = root / "generated" / "read_models"
    fixtures = {
        "openclaw_map_manifest.json": {
            "schema_version": "openclaw_map_manifest_v0",
            "read_model_id": "openclaw_map_manifest",
            "map_generation_id": "map_3cf7a1d5f26147ae993a",
            "bundle_hash": "sha256:3d59cfda37602e22a7cb02dab1afb899acb65fe043efadf032820d8f5bb7c1af",
        },
        "openclaw_map_snapshot.json": {
            "schema_version": "openclaw_map_snapshot_v0",
            "read_model_id": "openclaw_map_snapshot",
            "map_generation_id": "map_3cf7a1d5f26147ae993a",
            "security_audit_readiness": {
                "ready_for_security_pass": True,
                "security_approval_granted": False,
                "action_authority_granted": False,
                "coverage_gap_summary": {"coverage_gap_records_count": 5},
                "parked_breadcrumb_summary": {"parked_breadcrumb_count": 15},
            },
            "capital_hilton_proof_metadata": {
                "current_phase": "HELM_THRESHOLD_LANE",
                "target_world": "Finance",
                "lane_destiny": "MOVE_TO_WORLD_ACTION",
                "missing_proof": list(contract.CAPITAL_HILTON_PROOF_IDS),
                "missing_proof_count": 10,
                "protected_proof_required": True,
            },
            "package_preview_receipts": {"present": True},
            "tool_adapter_receipts": {"present": True},
            "agent_council": {"agent_dossier_cards_count": 12},
        },
        "sync_health.json": {
            "schema_version": "sync_health_v0",
            "app_visible_map_status": {
                "map_status": "map_current",
                "app_visible": True,
                "map_generation_id": "map_3cf7a1d5f26147ae993a",
                "bundle_hash": "sha256:3d59cfda37602e22a7cb02dab1afb899acb65fe043efadf032820d8f5bb7c1af",
            },
            "check_transmission_display": {"lamp_state": "QUIET"},
        },
        "security_audit_readiness_packet.json": {
            "schema_version": "security_audit_readiness_packet_v0_pass_2",
            "read_model_id": "security_audit_readiness_packet",
            "security_pass_readiness_criteria": {
                "ready_for_security_pass": True,
                "security_approval_granted": False,
                "action_authority_granted": False,
            },
        },
        "capital_hilton_proof_metadata_packet.json": {
            "schema_version": "capital_hilton_proof_metadata_packet_v0",
            "read_model_id": "capital_hilton_proof_metadata_packet",
            "machine_proof": {
                "missing_proof_count": 10,
                "protected_proof_required": True,
            },
        },
        "package_preview_receipt_contract.json": {"schema_version": "package_preview_receipt_contract_v0"},
        "tool_adapter_receipt_contract.json": {"schema_version": "tool_adapter_receipt_contract_v0"},
        "memory_candidate_receipt_contract.json": {"schema_version": "memory_candidate_receipt_contract_v0"},
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_security_pass_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _decisions(payload: dict) -> dict:
    return {item["decision_id"]: item for item in payload["surface_security_decisions"]}


def _actors(payload: dict) -> dict:
    return {item["actor_id"]: item for item in payload["agent_model_tool_security_decision"]["actors"]}


def _adapters(payload: dict) -> dict:
    return {item["adapter_id"]: item for item in payload["agent_model_tool_security_decision"]["tool_adapters"]}


def test_contract_is_deterministic_and_pass_1_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "security_pass_contract"
    assert first["pass_id"] == "pass_1_core_security_decisions_authority_boundaries"
    assert first["contract_status"] == "deterministic_security_pass_pass_1_read_only_preview_approval_only"
    assert first["machine_proof"]["map_generation_id"] == "map_3cf7a1d5f26147ae993a"
    assert first["machine_proof"]["app_visible_map_current"] is True
    assert first["machine_proof"]["check_transmission_quiet"] is True


def test_security_pass_output_approves_read_only_and_preview_without_action_authority(tmp_path):
    payload = _build(tmp_path)
    summary = payload["security_pass_output_summary"]

    assert payload["security_pass_completed"] is True
    assert summary["security_pass_completed"] is True
    assert summary["security_approval_granted_for_read_only_surfaces"] is True
    assert summary["security_approval_granted_for_preview_surfaces"] is True
    assert summary["security_approval_granted_for_metadata_only_surfaces"] is True
    assert summary["security_approval_granted_for_execution"] is False
    assert payload["action_authority_granted"] is False
    assert payload["runtime_execution_authority_granted"] is False
    assert payload["tool_execution_authority_granted"] is False
    assert payload["model_execution_authority_granted"] is False
    assert payload["queue_execution_authority_granted"] is False
    assert payload["account_authority_granted"] is False
    assert payload["send_submit_approval_authority_granted"] is False
    assert payload["core_rule"]["security_pass_approval_is_not_action_authority"] is True


def test_every_dangerous_authority_flag_remains_false(tmp_path):
    payload = _build(tmp_path)

    for key, expected in contract.NO_ACTION_AUTHORITY_FLAGS.items():
        if key == "operator_final_authority":
            assert payload[key] is True
        else:
            assert payload[key] is False
    assert payload["machine_proof"]["all_dangerous_authority_flags_false"] is True
    assert payload["machine_proof"]["network_git_sync_mac_app_mutation_authority_added"] is False


def test_decision_categories_schema_and_global_authority_matrix_are_explicit(tmp_path):
    payload = _build(tmp_path)
    matrix = payload["global_authority_matrix"]

    assert payload["security_decision_categories"] == list(contract.SECURITY_DECISION_CATEGORIES)
    assert payload["security_decision_schema"]["required_fields"] == list(contract.DECISION_REQUIRED_FIELDS)
    assert payload["security_decision_schema"]["unknown_or_missing_decision_result"] == "UNKNOWN_FAIL_CLOSED"
    for allowed in [
        "stable map display",
        "read-model display",
        "Markdown Knowledge Atlas metadata readback",
        "package preview display",
        "tool adapter receipt display",
        "Finance World preview",
        "Security Readiness display",
    ]:
        assert allowed in matrix["allowed_after_this_security_pass"]
    for blocked in [
        "live model calls",
        "model/API execution",
        "tool execution",
        "queue/autonomy execution",
        "browser/OAuth/account access",
        "Gmail/calendar/Coupa/Telegram access",
        "credentials/tokens/cookies/API keys",
        "send/submit/approval",
        "invoice generation",
        "raw finance/private body ingestion",
        "broad Markdown body ingestion",
        "Repo B execution",
        "file delete/move/cleanup/remount",
        "network operation",
        "automatic promotion",
        "automatic queueing",
        "C-drive artifact writes",
    ]:
        assert blocked in matrix["still_blocked"]
    assert matrix["authority_flags"]["operator_final_authority"] is True
    assert matrix["authority_flags"]["tool_execution_allowed"] is False


def test_surface_security_decisions_cover_current_app_surfaces(tmp_path):
    decisions = _decisions(_build(tmp_path))

    assert set(decisions) == {
        "stable_map_bundle_read_only",
        "mission_control_mac_app_read_only",
        "agent_council_dossier_cards_preview",
        "package_preview_tool_receipt_surface",
        "finance_world_capital_hilton_preview",
        "security_readiness_eliwinship_surface",
        "evidence_drawer_proof_rows",
    }
    assert decisions["stable_map_bundle_read_only"]["approval_status"] == "APPROVED_STABLE_MAP_SURFACE"
    assert "source truth claim" in decisions["stable_map_bundle_read_only"]["blocked_posture"]
    assert decisions["mission_control_mac_app_read_only"]["approval_status"] == "APPROVED_READ_ONLY"
    assert "direct backend execution" in decisions["mission_control_mac_app_read_only"]["blocked_posture"]
    assert decisions["agent_council_dossier_cards_preview"]["approval_status"] == "APPROVED_PREVIEW_ONLY"
    assert "live chat" in decisions["agent_council_dossier_cards_preview"]["blocked_posture"]
    assert decisions["package_preview_tool_receipt_surface"]["approval_status"] == "APPROVED_PREVIEW_ONLY"
    assert "dispatch" in decisions["package_preview_tool_receipt_surface"]["blocked_posture"]
    assert decisions["finance_world_capital_hilton_preview"]["approval_status"] == "APPROVED_WORLD_PREVIEW"
    assert "invoice generation" in decisions["finance_world_capital_hilton_preview"]["blocked_posture"]
    assert decisions["security_readiness_eliwinship_surface"]["approval_status"] == "APPROVED_READ_ONLY"
    assert decisions["evidence_drawer_proof_rows"]["approval_status"] == "APPROVED_PROOF_DETAIL_ONLY"
    for decision in decisions.values():
        assert decision["authority_flags"]["runtime_execution_authority_granted"] is False
        assert decision["authority_flags"]["tool_execution_allowed"] is False


def test_capital_hilton_security_decision_approves_preview_and_blocks_execution(tmp_path):
    decision = _build(tmp_path)["capital_hilton_security_pass_decision"]

    assert decision["current_phase"] == "HELM_THRESHOLD_LANE"
    assert decision["target_world"] == "Finance"
    assert decision["lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert decision["missing_proof_count"] == 10
    assert decision["protected_proof_required"] is True
    assert decision["candidate_facts_proven"] is False
    assert decision["finance_world_preview_exists"] is True
    assert decision["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
    assert decision["decision"]["finance_world_preview"] == "approved"
    assert decision["decision"]["candidate_facts_display"] == "approved_with_not_proven_label"
    assert decision["blocked"]["invoice_generation"] is True
    assert decision["blocked"]["coupa_access"] is True
    assert decision["blocked"]["credentials"] is True
    assert decision["blocked"]["excel_raw_body_ingestion"] is True
    assert decision["blocked"]["raw_finance_body_ingestion"] is True
    assert decision["blocked"]["send_submit_approval"] is True
    assert decision["required_gates"]["guardian_gate"] == "required_for_protected_proof_metadata"
    assert decision["required_gates"]["operator_final_authority"] == "required_for_future_action"


def test_markdown_terrain_decision_uses_existing_metadata_and_blocks_broad_body_or_file_mutation(tmp_path):
    decision = _build(tmp_path)["markdown_terrain_security_decision"]

    assert decision["markdown_backend_capability_status"] == "YES_READY"
    assert {item["path"] for item in decision["existing_systems"]} == set(contract.MARKDOWN_TERRAIN_SYSTEMS)
    assert all(item["present"] is True for item in decision["existing_systems"])
    assert all(item["authority_granted_by_presence"] is False for item in decision["existing_systems"])
    assert decision["safe_metadata_coverage"] == contract.MARKDOWN_METADATA_COUNTS
    assert decision["decision"]["metadata_only_markdown_atlas_readback"] == "approved"
    assert decision["decision"]["allowlisted_bounded_markdown_evidence_excerpts"] == "approved"
    assert decision["decision"]["app_visibility_for_markdown_terrain"] == "future_gated_visibility_gap_not_security_blocker"
    assert decision["blocked"]["broad_markdown_body_ingestion"] is True
    assert decision["blocked"]["broad_doc_reorganization"] is True
    assert decision["blocked"]["file_moves_deletes_renames"] is True
    assert decision["blocked"]["vector_index_creation"] is True
    assert decision["blocked"]["old_prompts_as_current_truth_unless_classified_proven"] is True
    assert decision["no_new_mapper_needed_now"] is True


def test_operator_answers_shared_paths_and_parked_breadcrumbs_remain_non_executing(tmp_path):
    payload = _build(tmp_path)
    answers = payload["operator_answer_capture_security_decision"]
    shared = payload["helm_focus_shared_path_security_decision"]
    parked = payload["parked_breadcrumb_security_decision"]

    assert answers["answer_schema"] == "approved"
    assert answers["future_capture_ui"] == "approved_as_capture_only_concept"
    assert answers["captured_answers"] == "Memory Candidate Receipts only"
    assert answers["operator_answers_as_proof"] == "blocked"
    assert answers["automatic_truth_promotion"] == "blocked"
    assert answers["automatic_lane_quieting_without_receipt_or_proof"] == "blocked"
    assert shared["helm_issue_focus_mode_model"] == "approved_for_read_only_ui"
    assert shared["shared_execution_paths"] == "approved_as_non_executing_consolidation"
    assert shared["blocked"]["live_execute_buttons"] is True
    assert shared["blocked"]["automatic_queueing_from_shared_path"] is True
    assert parked["parked_breadcrumb_review"] == "approved"
    assert parked["auto_promotion"] == "blocked"
    assert parked["queue_execution"] == "blocked"
    assert parked["holding_cell_creation"] == "future_gated_until_operator_attention_promotion_contract"


def test_agent_model_tool_decision_allows_display_but_blocks_activation_and_adapters(tmp_path):
    payload = _build(tmp_path)
    actors = _actors(payload)
    adapters = _adapters(payload)

    assert set(actors) == set(contract.ACTOR_IDS)
    for actor_id, actor in actors.items():
        assert actor["display_allowed"] is True
        assert actor["model_call_allowed"] is False
        assert actor["live_agent_activation_allowed"] is False
        assert actor["tool_use_allowed"] is False
        assert actor["self_authority_allowed"] is False
        assert actor["memory_write_allowed"] is False
        assert actor["operator_final_authority"] is (actor_id == "operator")
    assert adapters["stable_map_reader"]["posture"] == "read_only_approved"
    assert adapters["stable_map_reader"]["capability_granted"] == "READ_METADATA"
    assert adapters["package_preview_exporter"]["posture"] == "preview_receipt_metadata_approved"
    assert adapters["memory_candidate_receipt_writer"]["posture"] == "candidate_only_future_gated"
    assert adapters["codex_scoped_build_verifier"]["posture"] == "worker_prompt_only_not_openclaw_runtime"
    for blocked in [
        "browser_oauth_adapter",
        "gmail_calendar_adapter",
        "coupa_adapter",
        "telegram_adapter",
        "repo_b_planner_builder_adapter",
    ]:
        assert adapters[blocked]["capability_granted"] == "NONE"
        assert adapters[blocked]["tool_execution_allowed"] is False
        assert adapters[blocked]["network_allowed"] is False
        assert adapters[blocked]["account_access_allowed"] is False


def test_stable_map_integration_is_next_refresh_not_this_contract_lane(tmp_path):
    stable = _build(tmp_path)["stable_map_integration"]
    safe = stable["safe_summary_for_next_refresh"]

    assert stable["contract_generated_as_read_model"] is True
    assert stable["summary_included_in_stable_map_now"] is False
    assert stable["next_map_bundle_refresh_requirement"] == "Next stable-map refresh should include Security Pass Contract v0 Pass 1 summary."
    assert safe["security_pass_contract_id"] == "security_pass_contract"
    assert safe["security_pass_completed"] is True
    assert safe["read_only_surfaces_approved"] is True
    assert safe["preview_surfaces_approved"] is True
    assert safe["action_authority"] is False
    assert safe["capital_hilton_preview_approved"] is True
    assert safe["capital_hilton_execution_blocked"] is True
    assert safe["markdown_terrain_metadata_approved"] is True
    assert safe["broad_markdown_body_blocked"] is True


def test_export_script_writes_json_and_operator_outputs(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    assert export_main(["--repo-root", tmp_path.as_posix(), "--export-root", export_root.as_posix(), "--format", "summary"]) == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["decision_count"] == 7
    assert summary["security_pass_completed"] is True
    assert summary["read_only_surfaces_approved"] is True
    assert summary["preview_surfaces_approved"] is True
    assert summary["action_authority_granted"] is False
    assert summary["live_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "security_pass_contract"
    assert payload["machine_proof"]["content_hash"].startswith("sha256:")
    assert "Security Pass Contract v0 Pass 1" in operator
    assert "ELIWINSHIP" in operator


def test_generated_outputs_are_safe_canonical_read_model_files(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    assert export_main(["--repo-root", tmp_path.as_posix(), "--export-root", export_root.as_posix(), "--format", "summary"]) == 0
    capsys.readouterr()

    expected = canonical_generated_read_model_expected_files(export_root, repo_root=tmp_path)
    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_contract_source_avoids_runtime_network_sync_and_destructive_patterns():
    source = Path(contract.__file__).read_text(encoding="utf-8").lower()

    for forbidden in [
        "subprocess",
        "os.system",
        "shell=true",
        "requests.",
        "httpx.",
        "urllib.request",
        ".unlink(",
        "shutil.rmtree",
        "shutil.move",
        "/mnt/" + "c/",
        "file:///" + "c:",
    ]:
        assert forbidden not in source
