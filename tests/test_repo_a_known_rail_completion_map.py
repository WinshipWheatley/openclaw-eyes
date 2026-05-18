import ast
import json
from pathlib import Path

import repo_a_known_rail_completion_map as completion
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_repo_a_known_rail_completion_map import main as export_main


FIXED_NOW = "2026-05-18T18:00:00+00:00"


def test_every_known_major_rail_gets_classified():
    payload = completion.build_repo_a_known_rail_completion_map(generated_at=FIXED_NOW)
    rail_ids = {rail["rail_id"] for rail in payload["rails"]}

    expected = {
        "capital_hilton_cassandra_clara_finance",
        "cassandra_draft_review_email_calendar",
        "guardian_hitl_security_sovereignty",
        "chief_orchestration_work_packets",
        "hermes_advisory_synthesis",
        "niles_music_album_struna_capsule",
        "report_bridge_package_intake",
        "deterministic_planner_builder_automation",
        "brain_dump_cue_intent_inbox",
        "mission_control_read_model_surfaces",
        "sync_mirror_read_model_trust",
        "project_client_capsule_custom_build",
        "operator_action_intent_gates",
        "approval_request_receipt_execution_boundaries",
    }
    assert expected.issubset(rail_ids)
    assert payload["known_rail_count"] >= len(expected)
    for rail in payload["rails"]:
        assert rail["maturity"] in completion.MATURITY_SCALE
        assert set(rail["ready_for"]) == set(completion.READINESS_KEYS)
        assert rail["old_files_treated_as_evidence_not_truth"] is True


def test_live_execution_remains_blocked_for_every_rail():
    payload = completion.build_repo_a_known_rail_completion_map(generated_at=FIXED_NOW)

    assert payload["readiness_counts"]["live_workflow"] == 0
    assert payload["must_not_activate_yet"]
    for rail in payload["rails"]:
        assert rail["ready_for_live_workflow"] is False
        assert rail["ready_for"]["live_workflow"] is False
        assert rail["live_authority_blocked"] is True
    for key, expected in completion.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected


def test_repo_b_is_not_inspected_and_delta_questions_are_future_only():
    payload = completion.build_repo_a_known_rail_completion_map(generated_at=FIXED_NOW)

    assert payload["repo_scope"] == "Repo A only"
    assert payload["repo_b_inspected"] is False
    assert payload["repo_b_delta_pass_prepared_not_run"] is True
    assert payload["repo_b_delta_questions_for_later"]
    text = json.dumps(payload).lower()
    assert "/home/openclaw_external" not in text
    assert "openclaw-runtime" not in text


def test_security_pass_is_future_threshold_not_current():
    payload = completion.build_repo_a_known_rail_completion_map(generated_at=FIXED_NOW)

    assert payload["security_pass_current"] is False
    assert payload["security_pass_posture"] == "future_when_rails_approach_live_execution_threshold"
    for rail in payload["rails"]:
        assert rail["security_threshold_audit_now"] is False
        assert rail["security_threshold_audit_posture"] == "future_threshold_not_current_lane"


def test_output_includes_next_lane_recommendations_that_pass_batch_gate():
    payload = completion.build_repo_a_known_rail_completion_map(generated_at=FIXED_NOW)
    recommendations = payload["recommended_next_lanes_before_repo_b"]

    assert len(recommendations) == 3
    assert payload["recommended_next_lanes_all_gate_pass"] is True
    assert [item["lane_name"] for item in recommendations] == [
        "Capital Hilton Proof Metadata Capture v0",
        "Guardian Final-Send Approval Receipt Contract v0",
        "Niles Governed Metadata Review Packet Completion v0",
    ]
    for item in recommendations:
        gate = item["post_preflight_batch_gate_evaluation"]
        assert gate["gate_status"] == "pass"
        assert gate["named_operator_workflow"]
        assert gate["runtime_authority_added"] is False
        assert gate["send_or_submit_authority_added"] is False
        assert gate["customer_deployment_authority_added"] is False


def test_output_includes_concise_operator_eli5_summary():
    payload = completion.build_repo_a_known_rail_completion_map(generated_at=FIXED_NOW)
    eli5 = payload["operator_eli5_summary"]

    assert "Repo A already tracks" in eli5["summary_text"]
    assert "Capital Hilton finance/Cassandra-Clara" in eli5["tracked"]
    assert "Chief planning/work packets" in eli5["partially_tracked"]
    assert "what Repo B still contains that Repo A has not already absorbed" in eli5["not_yet_proven"]
    assert len(eli5["next_1_to_3_sensible_lanes"]) == 3


def test_unknown_rails_fail_closed_not_ready():
    unknown = completion.unknown_rail_record("operator remembered rail")

    assert unknown["maturity"] == "NOT_FOUND"
    assert unknown["authority_boundary"] == "fail_closed_until_repo_a_evidence_exists"
    assert unknown["operator_confirmation_needed"] is True
    assert all(value is False for value in unknown["ready_for"].values())


def test_read_model_distinguishes_visibility_review_proof_approval_and_execution():
    payload = completion.build_repo_a_known_rail_completion_map(generated_at=FIXED_NOW)
    capital = next(rail for rail in payload["rails"] if rail["rail_id"] == "capital_hilton_cassandra_clara_finance")
    operator_action = next(rail for rail in payload["rails"] if rail["rail_id"] == "operator_action_intent_gates")
    hermes = next(rail for rail in payload["rails"] if rail["rail_id"] == "hermes_advisory_synthesis")

    assert payload["read_model_distinguishes_visibility_review_proof_approval_execution"] is True
    assert capital["ready_for"]["review_packet"] is True
    assert capital["ready_for"]["proof_packet"] is True
    assert capital["ready_for"]["approval_request_contract"] is True
    assert capital["ready_for"]["live_workflow"] is False
    assert operator_action["ready_for"]["approval_receipt"] is True
    assert hermes["ready_for"]["visibility_only"] is True
    assert hermes["ready_for"]["approval_request_contract"] is False


def test_export_writes_valid_json_and_operator_packet(tmp_path, capsys):
    export_root = tmp_path / "generated/read_models"

    exit_code = export_main(["--repo-root", str(tmp_path), "--export-root", "generated/read_models", "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((export_root / completion.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert (export_root / completion.OPERATOR_EXPORT_NAME).is_file()
    assert "Repo A Known Rail Completion Map" in operator_text
    assert "ELI5 Summary" in operator_text
    assert payload["repo_b_inspected"] is False
    assert payload["security_pass_current"] is False


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated/read_models"
    completion.export_repo_a_known_rail_completion_map(
        repo_root=tmp_path,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert completion.JSON_EXPORT_NAME in expected
    assert completion.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_execute_shell_network_or_repo_b():
    source_files = [
        Path("repo_a_known_rail_completion_map.py"),
        Path("scripts/export_repo_a_known_rail_completion_map.py"),
    ]
    forbidden_text = [
        "/home/openclaw_external",
        "openclaw-runtime",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "send_message",
        "smtplib",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
        "git clone",
        "docker run",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden_text:
            assert token not in text

    tree = ast.parse(Path("repo_a_known_rail_completion_map.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
