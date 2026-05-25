import json
import re
from pathlib import Path

import conversation_topic_slicer_contract as slicer
from scripts.export_conversation_topic_slicer_contract import main as export_main


FIXED_NOW = "2026-05-25T10:00:00+00:00"


def _build() -> dict:
    return slicer.build_conversation_topic_slicer_contract(generated_at=FIXED_NOW)


def test_required_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert slicer.stable_json(first) == slicer.stable_json(second)
    assert first["schema_version"] == slicer.SCHEMA_VERSION
    assert first["read_model_id"] == slicer.READ_MODEL_ID
    proof = first["machine_proof"]
    assert proof["conversation_topic_slicer_contract_model_present"] is True
    assert proof["source_chat_thread_ref_model_present"] is True
    assert proof["topic_slice_model_present"] is True
    assert proof["topic_slice_graph_link_model_present"] is True
    assert proof["topic_slice_reorganization_proposal_model_present"] is True
    assert proof["topic_slice_receipt_model_present"] is True
    assert proof["topic_slice_blocker_model_present"] is True
    assert proof["conversation_topic_slicer_elioperator_report_model_present"] is True


def test_required_field_lists_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["conversation_topic_slicer_contract"]["required_fields"] == list(slicer.REQUIRED_CONTRACT_FIELDS)
    assert schemas["source_chat_thread_ref"]["required_fields"] == list(slicer.REQUIRED_THREAD_FIELDS)
    assert schemas["topic_slice"]["required_fields"] == list(slicer.REQUIRED_TOPIC_SLICE_FIELDS)
    assert schemas["topic_slice_graph_link"]["required_fields"] == list(slicer.REQUIRED_GRAPH_LINK_FIELDS)
    assert schemas["topic_slice_reorganization_proposal"]["required_fields"] == list(slicer.REQUIRED_PROPOSAL_FIELDS)
    assert schemas["topic_slice_receipt"]["required_fields"] == list(slicer.REQUIRED_RECEIPT_FIELDS)
    assert schemas["topic_slice_blocker"]["required_fields"] == list(slicer.REQUIRED_BLOCKER_FIELDS)
    assert schemas["conversation_topic_slicer_elioperator_report"]["required_fields"] == list(slicer.REQUIRED_REPORT_FIELDS)


def test_contract_doctrine_and_message_pointer_policy_exist():
    payload = _build()
    contract = payload["conversation_topic_slicer_contract"]

    assert "Original chat thread remains intact." in contract["doctrine"]
    assert "Topic slices are pointer/index records, not copied raw transcript bodies." in contract["doctrine"]
    assert payload["machine_proof"]["message_pointer_policy_exists"] is True
    assert any("msg_0001" in item or "pointer" in item for item in contract["message_pointer_policy"])


def test_supported_actions_relationships_disruptions_and_receipts_exist():
    payload = _build()

    assert payload["machine_proof"]["suggested_actions_present"] is True
    assert payload["machine_proof"]["relationship_types_present"] is True
    assert payload["machine_proof"]["disruption_levels_present"] is True
    assert payload["machine_proof"]["receipt_actions_present"] is True
    for action in ["KEEP_IN_PLACE", "LINK_TO_FOLDER", "MOVE_SLICE_TO_FOLDER", "SPLIT_INTO_NEW_THREAD", "UNKNOWN_FAIL_CLOSED"]:
        assert action in payload["suggested_actions"]
    for level in ["NON_DISRUPTIVE_SUGGESTION", "REVIEW_REQUIRED_MOVE", "BLOCKED_DESTRUCTIVE"]:
        assert level in payload["disruption_levels"]


def test_source_threads_keep_raw_transcripts_out_of_read_model():
    payload = _build()
    threads = payload["source_chat_threads_by_ref"]

    assert payload["machine_proof"]["raw_transcript_disallowed_in_threads"] is True
    for thread in threads.values():
        assert thread["raw_transcript_allowed_in_read_model"] is False
        assert "raw messages remain outside normal read-model" in thread["message_count_policy"]
        assert thread["safe_summary"]


def test_topic_slices_use_pointer_ranges_and_no_truth_claims():
    payload = _build()
    slices = payload["topic_slices_by_ref"]

    assert payload["machine_proof"]["all_slices_have_message_pointers"] is True
    for topic in slices.values():
        assert topic["message_range_policy"] == "pointer_range_only_no_raw_body"
        assert topic["message_start_ref"].startswith("msg_")
        assert topic["message_end_ref"].startswith("msg_")
        assert "do not copy transcript body" in topic["next_safe_move"]


def test_graph_links_and_reorganization_proposals_preserve_provenance():
    payload = _build()

    assert payload["machine_proof"]["all_links_have_provenance"] is True
    assert payload["machine_proof"]["all_proposals_preserve_provenance"] is True
    assert payload["machine_proof"]["all_proposals_disallow_deletion"] is True
    for proposal in payload["topic_slice_reorganization_proposals_by_id"].values():
        assert proposal["provenance_preserved"] is True
        assert proposal["deletion_allowed"] is False


def test_topic_slice_receipts_do_not_move_or_copy_raw_bodies():
    payload = _build()

    assert payload["machine_proof"]["all_receipts_preserve_provenance"] is True
    assert payload["machine_proof"]["all_receipts_do_not_move_or_copy_raw_body"] is True
    for receipt in payload["topic_slice_receipts_by_id"].values():
        assert receipt["raw_body_moved"] is False
        assert receipt["raw_body_copied"] is False


def test_one_chat_three_topics_example_exists():
    payload = _build()
    example = payload["examples"]["one_chat_three_topics"]

    assert payload["machine_proof"]["one_chat_three_topics_example_exists"] is True
    assert example["initial_folder"] == "music/live_music"
    assert "music/live_music/setlists" in example["expected_target_folders"]
    assert "music/live_music/x32/routing" in example["expected_target_folders"]
    assert "music/studio/album/songwriting" in example["expected_target_folders"]
    assert "communications/bookings" in example["expected_target_folders"]
    assert "no destructive move" in example["expected_behavior"]


def test_misfiled_chat_example_exists():
    payload = _build()
    example = payload["examples"]["misfiled_chat"]
    architecture_slice = payload["topic_slices_by_ref"]["topic_slice_invoice_automation_architecture"]

    assert payload["machine_proof"]["misfiled_chat_example_exists"] is True
    assert example["initial_folder"] == "finance/capital_hilton"
    assert architecture_slice["folder_ref"] == "build/openclaw/invoice_workflows"
    assert architecture_slice["operator_review_required"] is True
    assert "Capital Hilton-specific slice remains linked to finance/capital_hilton/invoices" in example["expected_behavior"]


def test_x32_fader_replacement_example_exists():
    payload = _build()
    example = payload["examples"]["x32_fader_replacement"]
    topic = payload["topic_slices_by_ref"]["topic_slice_x32_fader_replacement"]

    assert payload["machine_proof"]["x32_fader_replacement_example_exists"] is True
    assert example["operator_resume_phrase"] == "Pick up the X32 fader replacement thread."
    assert topic["folder_ref"] == "music/live_music/x32/maintenance"
    assert "no live retrieval" in example["future_recommendation"]


def test_struna_drift_example_exists_and_is_summary_only():
    payload = _build()
    example = payload["examples"]["struna_drift"]
    thread = payload["source_chat_threads_by_ref"]["thread_ref_struna_creative_build_licensing"]
    licensing_slice = payload["topic_slices_by_ref"]["topic_slice_struna_licensing_summary"]

    assert payload["machine_proof"]["struna_drift_example_exists"] is True
    assert example["operator_review_required"] is True
    assert "raw legal/private details are not exposed" == example["privacy_note"]
    assert thread["privacy_class"] == "private_summary_only"
    assert licensing_slice["operator_review_required"] is True


def test_raw_transcript_copy_blocker_and_other_blockers_exist():
    payload = _build()
    blockers = payload["topic_slice_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    assert payload["machine_proof"]["blockers_present"] is True
    assert payload["machine_proof"]["raw_transcript_copy_blocker_exists"] is True
    assert payload["machine_proof"]["cross_client_leak_blocked"] is True
    assert payload["machine_proof"]["silent_destructive_reorganization_blocked"] is True
    for expected in slicer.BLOCKER_TYPES:
        assert expected in blocker_types
    assert blockers["topic_slice_blocker_raw_transcript_copied"]["fail_closed"] is True
    assert blockers["topic_slice_blocker_cross_client_leak"]["severity"] == "CRITICAL"


def test_all_live_authority_false_and_no_mutation_or_retrieval():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["live_topic_slicing_performed"] is False
    assert payload["machine_proof"]["raw_transcript_ingested"] is False
    assert payload["machine_proof"]["raw_transcript_copied"] is False
    assert payload["machine_proof"]["graph_link_write_performed"] is False
    assert payload["machine_proof"]["reorganization_move_split_delete_performed"] is False
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

    assert summary["one_chat_three_topics_example_exists"] is True
    assert summary["misfiled_chat_example_exists"] is True
    assert summary["x32_fader_replacement_example_exists"] is True
    assert summary["struna_drift_example_exists"] is True
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
            "conversation_topic_slicer_contract.py",
            "scripts/export_conversation_topic_slicer_contract.py",
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
