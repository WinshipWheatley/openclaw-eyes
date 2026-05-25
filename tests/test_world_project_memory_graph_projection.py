import json
import re
from pathlib import Path

import world_project_memory_graph_projection as projection
from scripts.export_world_project_memory_graph_projection import main as export_main


FIXED_NOW = "2026-05-25T10:00:00+00:00"


def _build() -> dict:
    return projection.build_world_project_memory_graph_projection(generated_at=FIXED_NOW)


def test_required_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert projection.stable_json(first) == projection.stable_json(second)
    assert first["schema_version"] == projection.SCHEMA_VERSION
    assert first["read_model_id"] == projection.READ_MODEL_ID
    proof = first["machine_proof"]
    assert proof["semantic_memory_graph_contract_model_present"] is True
    assert proof["semantic_memory_node_model_present"] is True
    assert proof["semantic_memory_relationship_model_present"] is True
    assert proof["folder_tree_projection_model_present"] is True
    assert proof["folder_projection_node_model_present"] is True
    assert proof["scope_partition_policy_model_present"] is True
    assert proof["folder_projection_blocker_model_present"] is True
    assert proof["world_project_memory_graph_elioperator_report_model_present"] is True


def test_required_field_lists_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["semantic_memory_graph_contract"]["required_fields"] == list(projection.REQUIRED_CONTRACT_FIELDS)
    assert schemas["semantic_memory_node"]["required_fields"] == list(projection.REQUIRED_NODE_FIELDS)
    assert schemas["semantic_memory_relationship"]["required_fields"] == list(projection.REQUIRED_RELATIONSHIP_FIELDS)
    assert schemas["folder_tree_projection"]["required_fields"] == list(projection.REQUIRED_PROJECTION_FIELDS)
    assert schemas["folder_projection_node"]["required_fields"] == list(projection.REQUIRED_PROJECTION_NODE_FIELDS)
    assert schemas["scope_partition_policy"]["required_fields"] == list(projection.REQUIRED_SCOPE_POLICY_FIELDS)
    assert schemas["folder_projection_blocker"]["required_fields"] == list(projection.REQUIRED_BLOCKER_FIELDS)
    assert schemas["world_project_memory_graph_elioperator_report"]["required_fields"] == list(projection.REQUIRED_REPORT_FIELDS)


def test_graph_vs_folder_doctrine_and_existing_semantic_schema_rail():
    payload = _build()
    contract = payload["semantic_memory_graph_contract"]

    assert payload["machine_proof"]["graph_vs_folder_doctrine_exists"] is True
    assert "Semantic graph is truth." in contract["doctrine"]
    assert "Folder tree is a human projection." in contract["doctrine"]
    assert payload["machine_proof"]["sqlite_graph_tables_available_in_schema_contract"] is True
    assert payload["db_rail_status"]["live_db_write_supported_in_this_lane"] is False
    assert payload["db_rail_status"]["live_db_migration_supported_in_this_lane"] is False


def test_node_and_relationship_types_exist():
    payload = _build()

    assert payload["machine_proof"]["node_types_present"] is True
    assert payload["machine_proof"]["relationship_types_present"] is True
    for node_type in ["WORLD", "PROJECT_FOLDER", "CHAT_THREAD", "TOPIC_SLICE", "SOURCE_REF", "ARTIFACT", "PROCEDURE", "RECEIPT", "VISUAL_WORKSPACE", "UNKNOWN"]:
        assert node_type in payload["node_types"]
    for relationship_type in ["CONTAINS", "LINKS_TO", "RELATED_TO", "SUMMARIZES", "DERIVED_FROM", "GENERATED", "SUPPORTS_PROOF", "BELONGS_TO_SCOPE", "SUGGESTED_REORG", "UNKNOWN"]:
        assert relationship_type in payload["relationship_types"]


def test_nodes_relationships_scope_and_provenance_are_present():
    payload = _build()

    assert payload["machine_proof"]["all_nodes_have_scope"] is True
    assert payload["machine_proof"]["all_relationships_have_scope"] is True
    assert payload["machine_proof"]["all_nodes_have_provenance"] is True
    assert payload["machine_proof"]["all_relationships_have_provenance"] is True
    assert payload["semantic_memory_nodes_by_ref"]["node_finance_capital_hilton_invoices"]["client_ref"] == "capital_hilton"
    assert payload["semantic_memory_relationships_by_ref"]["rel_capital_hilton_contains_invoices"]["client_ref"] == "capital_hilton"


def test_folder_tree_projection_is_mac_render_ready():
    payload = _build()
    folder_projection = payload["folder_tree_projection"]
    nodes = payload["folder_projection_nodes_by_ref"]

    assert payload["machine_proof"]["folder_projection_mac_render_ready"] is True
    assert folder_projection["projection_status"] == "UPDATED_READY_FOR_MAC"
    assert folder_projection["mac_render_ready"] is True
    assert "proj_music" in folder_projection["root_nodes"]
    assert "proj_finance" in folder_projection["root_nodes"]
    assert "proj_build" in folder_projection["root_nodes"]
    assert nodes["proj_finance_capital_hilton_invoices"]["folder_path"] == "finance/capital_hilton/invoices"


def test_scope_partition_policy_exists_and_blocks_cross_client_leaks():
    payload = _build()
    policies = payload["scope_partition_policies_by_id"]

    assert "scope_policy_capital_hilton_finance" in policies
    assert policies["scope_policy_capital_hilton_finance"]["client_ref"] == "capital_hilton"
    assert "must not leak" in policies["scope_policy_capital_hilton_finance"]["cross_client_leak_policy"]
    assert "raw legal body" in policies["scope_policy_struna_private_summary"]["blocked_cross_links"]


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["folder_projection_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    assert payload["machine_proof"]["blockers_present"] is True
    for expected in projection.BLOCKER_TYPES:
        assert expected in blocker_types
    assert payload["machine_proof"]["strict_tree_as_truth_blocker_exists"] is True
    assert payload["machine_proof"]["cross_client_leak_blocker_exists"] is True
    assert payload["machine_proof"]["provenance_missing_blocker_exists"] is True
    assert blockers["folder_projection_blocker_strict_tree_assumed_as_truth"]["fail_closed"] is True
    assert blockers["folder_projection_blocker_cross_client_leak"]["severity"] == "CRITICAL"


def test_music_live_x32_example_exists():
    payload = _build()
    example = payload["examples"]["music_live_x32"]

    assert payload["machine_proof"]["music_live_x32_example_exists"] is True
    assert example["projection"] == ("music", "live_music", "x32", "routing", "show_files")
    assert "X32 routing notes link to Behringer X32 source refs." in example["graph_bindings"]


def test_music_studio_album_song_example_exists():
    payload = _build()
    example = payload["examples"]["music_studio_album_song"]

    assert payload["machine_proof"]["music_studio_album_song_example_exists"] is True
    assert example["projection"] == ("music", "studio", "album", "song_name")
    assert "album spreadsheet source ref" in example["graph_bindings"]
    assert "song rich text doc source ref" in example["graph_bindings"]
    assert "Logic project metadata source ref" in example["graph_bindings"]


def test_finance_capital_hilton_example_exists():
    payload = _build()
    example = payload["examples"]["finance_capital_hilton"]

    assert payload["machine_proof"]["finance_capital_hilton_example_exists"] is True
    assert example["projection"] == ("finance", "capital_hilton", "invoices")
    for binding in ["invoice workflow procedure", "delivery fact receipts", "invoice artifact refs", "router readbacks", "payment tracking refs"]:
        assert binding in example["graph_bindings"]


def test_build_mission_control_example_exists():
    payload = _build()
    example = payload["examples"]["build_mission_control"]

    assert payload["machine_proof"]["build_mission_control_example_exists"] is True
    assert example["projection"] == ("build", "mission_control", "chat_surface")
    assert "readback cards" in example["graph_bindings"]
    assert "SwiftUI task history" in example["graph_bindings"]


def test_struna_example_exists_and_is_summary_only():
    payload = _build()
    example = payload["examples"]["struna_mac_version"]
    node = payload["semantic_memory_nodes_by_ref"]["node_struna_mac_version"]

    assert payload["machine_proof"]["struna_example_exists"] is True
    assert example["projection"] == ("build", "struna", "mac_version")
    assert "Draper ownership context summary" in example["graph_bindings"]
    assert "Winship 25 percent Mac-version agreement summary" in example["graph_bindings"]
    assert node["sensitivity_class"] == "private_summary_only"
    assert "legal/private bodies remain hidden" in node["summary"]


def test_multi_folder_chat_link_example_exists_without_destructive_move():
    payload = _build()
    example = payload["examples"]["multi_folder_chat"]

    assert payload["machine_proof"]["multi_folder_chat_link_example_exists"] is True
    assert example["start_projection"] == ("music", "live_music", "setlists")
    assert "X32 routing" in example["topic_candidates"]
    assert "new song arrangement" in example["topic_candidates"]
    assert "booking follow-up" in example["topic_candidates"]
    assert "No destructive move occurs." in example["expected_behavior"]
    assert payload["machine_proof"]["reorganization_or_folder_move_performed"] is False


def test_all_live_authority_false_and_no_mutation():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["live_memory_write_performed"] is False
    assert payload["machine_proof"]["live_db_migration_created"] is False
    assert payload["machine_proof"]["raw_transcript_ingested"] is False
    assert payload["machine_proof"]["raw_file_body_ingested"] is False
    assert payload["machine_proof"]["agent_retrieval_run"] is False
    assert payload["machine_proof"]["cross_scope_query_run"] is False
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

    assert summary["mac_render_ready"] is True
    assert summary["music_live_x32_example_exists"] is True
    assert summary["finance_capital_hilton_example_exists"] is True
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
    assert "raw file body:" not in combined.lower()


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "world_project_memory_graph_projection.py",
            "scripts/export_world_project_memory_graph_projection.py",
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
