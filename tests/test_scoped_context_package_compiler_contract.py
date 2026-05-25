import json
import re
from pathlib import Path

import scoped_context_package_compiler_contract as compiler
from scripts.export_scoped_context_package_compiler_contract import main as export_main


FIXED_NOW = "2026-05-25T10:00:00+00:00"


def _build() -> dict:
    return compiler.build_scoped_context_package_compiler_contract(generated_at=FIXED_NOW)


def test_required_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert compiler.stable_json(first) == compiler.stable_json(second)
    assert first["schema_version"] == compiler.SCHEMA_VERSION
    assert first["read_model_id"] == compiler.READ_MODEL_ID
    proof = first["machine_proof"]
    assert proof["scoped_context_package_compiler_contract_model_present"] is True
    assert proof["scoped_context_package_model_present"] is True
    assert proof["context_package_coordinate_model_present"] is True
    assert proof["context_highlight_model_present"] is True
    assert proof["context_exclusion_model_present"] is True
    assert proof["role_context_policy_model_present"] is True
    assert proof["context_package_visual_artifact_need_model_present"] is True
    assert proof["context_package_blocker_model_present"] is True
    assert proof["scoped_context_package_elioperator_report_model_present"] is True


def test_required_field_lists_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["scoped_context_package_compiler_contract"]["required_fields"] == list(compiler.REQUIRED_CONTRACT_FIELDS)
    assert schemas["scoped_context_package"]["required_fields"] == list(compiler.REQUIRED_PACKAGE_FIELDS)
    assert schemas["context_package_coordinate"]["required_fields"] == list(compiler.REQUIRED_COORDINATE_FIELDS)
    assert schemas["context_highlight"]["required_fields"] == list(compiler.REQUIRED_HIGHLIGHT_FIELDS)
    assert schemas["context_exclusion"]["required_fields"] == list(compiler.REQUIRED_EXCLUSION_FIELDS)
    assert schemas["role_context_policy"]["required_fields"] == list(compiler.REQUIRED_ROLE_POLICY_FIELDS)
    assert schemas["context_package_visual_artifact_need"]["required_fields"] == list(compiler.REQUIRED_VISUAL_NEED_FIELDS)
    assert schemas["context_package_blocker"]["required_fields"] == list(compiler.REQUIRED_BLOCKER_FIELDS)
    assert schemas["scoped_context_package_elioperator_report"]["required_fields"] == list(compiler.REQUIRED_REPORT_FIELDS)


def test_contract_declares_scoped_context_not_raw_thread_sludge():
    payload = _build()
    contract = payload["scoped_context_package_compiler_contract"]

    assert "Agents receive scoped context packages, not vague memory." in contract["doctrine"]
    assert "Packages are generated from graph/projection coordinates, not guessed folder names alone." in contract["doctrine"]
    assert "Raw transcripts, raw file bodies, and raw secret values stay below deck." in contract["doctrine"]


def test_roles_source_ref_types_and_exclusion_reasons_exist():
    payload = _build()

    assert payload["machine_proof"]["target_agent_roles_present"] is True
    assert payload["machine_proof"]["source_ref_types_present"] is True
    assert payload["machine_proof"]["exclusion_reasons_present"] is True
    for role in ["MAC_CODEX", "PC_CODEX", "GEMINI_AGY", "CASSANDRA", "GUARDIAN", "NILES", "VISUAL_RENDER_AGENT", "UNKNOWN_NEEDS_ROUTING"]:
        assert role in payload["target_agent_roles"]
    for reason in ["RAW_TRANSCRIPT_EXCLUDED", "RAW_FILE_BODY_EXCLUDED", "SECRET_VALUE_EXCLUDED"]:
        assert reason in payload["exclusion_reasons"]


def test_packages_have_graph_projection_coordinates_and_topic_slices():
    payload = _build()
    packages = payload["scoped_context_packages_by_id"]

    assert payload["machine_proof"]["packages_have_coordinates"] is True
    assert payload["machine_proof"]["packages_from_graph_projection_coordinates_not_folder_guess"] is True
    assert payload["machine_proof"]["topic_slices_narrowed_when_present"] is True
    assert packages["context_package_mac_codex_chat_surface"]["folder_path"] == "build/mission_control/chat_surface"
    assert packages["context_package_cassandra_capital_hilton_invoice"]["topic_slice_refs"] == ("topic_slice_capital_hilton_invoice_specific",)


def test_each_package_lists_inclusions_exclusions_unknowns_and_actions():
    payload = _build()

    assert payload["machine_proof"]["all_packages_list_exclusions"] is True
    for package in payload["scoped_context_packages_by_id"].values():
        assert package["included_context"]
        assert package["excluded_context"]
        assert package["missing_items"]
        assert package["allowed_actions"]
        assert package["forbidden_actions"]
        assert package["truth_boundary"] == "Truth comes from cited receipts/readbacks and source refs, not from summary text."


def test_context_exclusions_have_reasons_and_cover_raw_transcripts_files_and_secrets():
    payload = _build()

    assert payload["machine_proof"]["exclusions_have_reasons"] is True
    assert payload["machine_proof"]["raw_transcript_excluded"] is True
    assert payload["machine_proof"]["raw_file_body_excluded"] is True
    assert payload["machine_proof"]["raw_secret_excluded"] is True
    reasons = {item["reason"] for item in payload["context_exclusions_by_id"].values()}
    assert "RAW_TRANSCRIPT_EXCLUDED" in reasons
    assert "RAW_FILE_BODY_EXCLUDED" in reasons
    assert "SECRET_VALUE_EXCLUDED" in reasons


def test_mac_codex_example_and_validation_expectations_exist():
    payload = _build()
    example = payload["examples"]["mac_codex_chat_surface"]
    package = payload["scoped_context_packages_by_id"][example["package_ref"]]

    assert payload["machine_proof"]["mac_codex_example_exists"] is True
    assert package["target_agent_role"] == "MAC_CODEX"
    assert package["target_machine"] == "MAC"
    assert "Xcode build/run validation" in package["validation_expectations"]
    assert "screenshot validation" in package["validation_expectations"]
    assert payload["machine_proof"]["mac_codex_validation_expectations_present"] is True


def test_pc_codex_example_and_backend_validation_expectations_exist():
    payload = _build()
    example = payload["examples"]["pc_codex_chat_request_processor"]
    package = payload["scoped_context_packages_by_id"][example["package_ref"]]

    assert payload["machine_proof"]["pc_codex_example_exists"] is True
    assert package["target_agent_role"] == "PC_CODEX"
    assert package["target_machine"] == "PC_WSL"
    assert "pytest" in package["validation_expectations"]
    assert "export summary" in package["validation_expectations"]
    assert "JSON parse" in package["validation_expectations"]
    assert payload["machine_proof"]["pc_codex_validation_expectations_present"] is True


def test_gemini_agy_example_is_read_only():
    payload = _build()
    example = payload["examples"]["gemini_agy_audit"]
    package = payload["scoped_context_packages_by_id"][example["package_ref"]]

    assert payload["machine_proof"]["gemini_agy_example_exists"] is True
    assert example["read_only"] is True
    assert package["target_agent_role"] == "GEMINI_AGY"
    assert "read-only audit" in package["allowed_actions"]
    assert "file edits" in package["forbidden_actions"]
    assert "commits" in package["forbidden_actions"]
    assert payload["machine_proof"]["gemini_agy_read_only"] is True


def test_niles_x32_cassandra_guardian_and_visual_examples_exist():
    payload = _build()
    packages = payload["scoped_context_packages_by_id"]

    assert payload["machine_proof"]["niles_x32_example_exists"] is True
    assert packages["context_package_niles_x32_routing"]["target_agent_role"] == "NILES"
    assert packages["context_package_niles_x32_routing"]["folder_path"] == "music/live_music/x32/routing"
    assert "finance/client/private unrelated data" in packages["context_package_niles_x32_routing"]["excluded_context"]

    assert payload["machine_proof"]["cassandra_capital_hilton_example_exists"] is True
    assert packages["context_package_cassandra_capital_hilton_invoice"]["target_agent_role"] == "CASSANDRA"
    assert "send authority" in packages["context_package_cassandra_capital_hilton_invoice"]["excluded_context"]

    assert payload["machine_proof"]["guardian_example_exists"] is True
    assert packages["context_package_guardian_approval_boundary"]["target_agent_role"] == "GUARDIAN"
    assert "proof refs" in packages["context_package_guardian_approval_boundary"]["included_context"]

    assert payload["machine_proof"]["visual_render_example_exists"] is True
    assert packages["context_package_visual_invoice_workflow"]["target_agent_role"] == "VISUAL_RENDER_AGENT"
    assert packages["context_package_visual_invoice_workflow"]["visual_artifact_needed"] is True


def test_ambiguous_package_blocks_or_asks_clarification():
    payload = _build()
    example = payload["examples"]["ambiguous_keep_going_blocked"]
    package = payload["scoped_context_packages_by_id"][example["package_ref"]]
    coordinate = payload["context_package_coordinates_by_id"]["coord_ambiguous_keep_going"]

    assert payload["machine_proof"]["ambiguous_package_blocked_example_exists"] is True
    assert payload["machine_proof"]["ambiguous_scope_blocks_or_asks_clarification"] is True
    assert coordinate["ambiguity_status"] == "AMBIGUOUS_NEEDS_CLARIFICATION"
    assert package["target_agent_role"] == "UNKNOWN_NEEDS_ROUTING"
    assert "which thread to resume" in package["missing_items"]
    assert "stuff all recent threads into context" in package["forbidden_actions"]


def test_visual_artifact_need_requires_truth_refs_and_prioritizes_detail():
    payload = _build()
    needs = payload["context_package_visual_artifact_needs_by_id"]
    invoice_need = needs["visual_need_capital_hilton_invoice_workflow"]

    assert payload["machine_proof"]["visual_artifact_needs_have_truth_refs"] is True
    assert payload["machine_proof"]["visual_artifact_detail_priority_outranks_style"] is True
    assert invoice_need["needed"] is True
    assert invoice_need["source_truth_refs"]
    assert invoice_need["detail_priority"] == "HIGH"
    assert invoice_need["style_priority"] == "LOW"


def test_role_context_policies_are_role_specific():
    payload = _build()
    policies = payload["role_context_policies_by_id"]

    assert policies["role_policy_mac_codex"]["target_agent_role"] == "MAC_CODEX"
    assert "Xcode build/run validation" in policies["role_policy_mac_codex"]["allowed_actions"]
    assert policies["role_policy_pc_codex"]["target_agent_role"] == "PC_CODEX"
    assert "pytest" in policies["role_policy_pc_codex"]["allowed_actions"]
    assert policies["role_policy_visual_render_agent"]["target_agent_role"] == "VISUAL_RENDER_AGENT"
    assert "style-only prompts" in policies["role_policy_visual_render_agent"]["forbidden_context_types"]


def test_blockers_exist_for_cross_client_broad_context_visual_truth_and_missing_exclusions():
    payload = _build()
    blocker_types = {blocker["blocker_type"] for blocker in payload["context_package_blockers_by_id"].values()}

    assert payload["machine_proof"]["blockers_present"] is True
    assert payload["machine_proof"]["cross_client_leak_blocked"] is True
    assert payload["machine_proof"]["context_too_broad_blocked"] is True
    assert payload["machine_proof"]["visual_artifact_without_truth_refs_blocked"] is True
    assert payload["machine_proof"]["package_missing_exclusions_blocked"] is True
    assert payload["machine_proof"]["overfilled_unrelated_thread_blocked"] is True
    assert payload["machine_proof"]["ambiguous_scope_not_flagged_blocked"] is True
    for expected in compiler.BLOCKER_TYPES:
        assert expected in blocker_types
    assert payload["context_package_blockers_by_id"]["context_package_blocker_raw_secret_included"]["severity"] == "CRITICAL"


def test_all_live_authority_false_and_no_dispatch_or_retrieval():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["context_package_dispatch_performed"] is False
    assert payload["machine_proof"]["agent_dispatch_performed"] is False
    assert payload["machine_proof"]["model_call_performed"] is False
    assert payload["machine_proof"]["workflow_run_performed"] is False
    assert payload["machine_proof"]["memory_retrieval_performed"] is False
    assert payload["machine_proof"]["raw_transcript_ingested"] is False
    assert payload["machine_proof"]["raw_file_body_ingested"] is False
    assert payload["machine_proof"]["secret_revealed"] is False
    assert payload["machine_proof"]["visual_artifact_spawned"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_export_writes_parseable_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["mac_codex_example_exists"] is True
    assert summary["pc_codex_example_exists"] is True
    assert summary["gemini_agy_example_exists"] is True
    assert summary["ambiguous_package_blocked_example_exists"] is True
    assert summary["visual_artifact_needs_have_truth_refs"] is True
    assert data["machine_proof"]["all_live_authority_flags_false"] is True
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_generated_outputs_have_no_raw_pii_or_secret_like_values(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "private key" not in combined.lower()
    assert "raw transcript:" not in combined.lower()
    assert "raw body:" not in combined.lower()


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "scoped_context_package_compiler_contract.py",
            "scripts/export_scoped_context_package_compiler_contract.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
