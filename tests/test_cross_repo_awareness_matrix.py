import ast
import json
from pathlib import Path

import cross_repo_awareness_matrix as matrix
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_cross_repo_awareness_matrix import main as export_main


FIXED_NOW = "2026-05-19T04:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# metadata fixture only\n", encoding="utf-8")


def _fixture_repo(root: Path, repo_b: Path) -> None:
    read_models = root / "generated" / "read_models"
    _write_json(
        read_models / "repo_a_known_rail_completion_map.json",
        {
            "schema_version": "repo_a_known_rail_completion_map_v0",
            "known_rail_count": 14,
            "rails": [
                {"rail_id": "capital_hilton_cassandra_clara_finance", "maturity": "APPROVAL_REQUEST_CONTRACT_READY"},
                {"rail_id": "cassandra_draft_review_email_calendar", "maturity": "REVIEW_PACKET_READY"},
                {"rail_id": "chief_orchestration_work_packets", "maturity": "READ_MODEL_VISIBLE"},
            ],
            "repo_b_inspected": False,
        },
    )
    _write_json(
        read_models / "repo_b_remaining_capability_delta_map.json",
        {
            "schema_version": "repo_b_remaining_capability_delta_map_v0",
            "repo_b_reference_only": True,
            "repo_b_code_executed": False,
            "capability_delta_list": [
                {
                    "capability_id": "cassandra_core_listener_review",
                    "classification": "ALREADY_REPRESENTED_IN_REPO_A",
                    "repo_b_paths": ["cassandra_listener.py"],
                    "repo_a_equivalent": [{"path": "generated/read_models/cassandra_draft_review_packet.json"}],
                    "should_bring_forward": False,
                    "suggested_future_lane": "None",
                },
                {
                    "capability_id": "cassandra_calendar_email_draft",
                    "classification": "PARTIALLY_REPRESENTED_IN_REPO_A",
                    "repo_b_paths": ["google_access_broker.py"],
                    "repo_a_equivalent": [{"path": "generated/read_models/cassandra_email_calendar_delta_detangle.json"}],
                    "should_bring_forward": True,
                    "suggested_future_lane": "Cassandra Email Calendar Delta Detangle v0",
                },
                {
                    "capability_id": "planner_builder_automation_loops",
                    "classification": "UNSAFE_OR_BLOCKED",
                    "repo_b_paths": ["polish_loop/orchestrator.py"],
                    "repo_a_equivalent": [],
                    "should_bring_forward": False,
                    "suggested_future_lane": "Planner Builder Delta Safety Review v0",
                },
            ],
            "operator_memory_review_items": [
                {"remembered_area": "Hermes status", "needs_operator_memory_review": True}
            ],
        },
    )
    for name, schema in {
        "capability_skill_registry_metadata_delta.json": "capability_skill_registry_metadata_delta_v0",
        "chief_role_capability_segmentation_map.json": "chief_role_capability_segmentation_map_v0",
        "chief_status_rail.json": "chief_status_rail_v0",
        "build_now_vs_hold_queue_posture.json": "build_now_vs_hold_queue_posture_v0",
        "cassandra_email_calendar_delta_detangle.json": "cassandra_email_calendar_delta_detangle_v0",
        "protected_access_broker_concept.json": "protected_access_broker_concept_v0",
        "protected_evidence_reference_receipt.json": "protected_evidence_reference_receipt_v0",
        "guardian_protected_access_gate_spec.json": "guardian_protected_access_gate_spec_v0",
    }.items():
        _write_json(read_models / name, {"schema_version": schema})

    _touch(repo_b / "cassandra_listener.py")
    _touch(repo_b / "google_access_broker.py")
    _touch(repo_b / "polish_loop/orchestrator.py")
    _touch(repo_b / ".claude/commands/cassandra.md")
    _touch(repo_b / "UNKNOWN_NEW_SURFACE.md")


def _build(tmp_path: Path) -> dict:
    root = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    _fixture_repo(root, repo_b)
    return matrix.build_cross_repo_awareness_matrix(
        repo_root=root,
        repo_b_root=repo_b,
        generated_at=FIXED_NOW,
    )


def _item(payload: dict, item_id: str) -> dict:
    return next(item for item in payload["matrix_items"] if item["matrix_item_id"] == item_id)


def test_matrix_is_deterministic_and_read_model_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert matrix.stable_json(first) == matrix.stable_json(second)
    assert first["schema_version"] == matrix.SCHEMA_VERSION
    assert first["matrix_status"] == "cross_repo_awareness_read_model_only"
    assert first["repo_b_code_executed"] is False
    assert first["repo_b_modules_imported"] is False
    assert first["runtime_authority_added"] is False
    assert first["send_or_submit_authority_added"] is False
    assert first["repo_b_reference_path_metadata_inspected"] is True
    assert first["repo_b_content_body_read"] is False


def test_repo_a_tracked_items_are_represented(tmp_path):
    payload = _build(tmp_path)
    tracked = payload["awareness_answers"]["repo_a_tagged_or_tracked"]

    assert "capital_hilton_finance" in tracked
    assert "cassandra_email_calendar" in tracked
    assert "chief_work_packet_queue" in tracked
    assert _item(payload, "capital_hilton_finance")["classification"] == "REPO_A_TRACKED"
    assert _item(payload, "cassandra_email_calendar")["classification"] == "REPO_A_TRACKED"


def test_repo_b_represented_items_are_separated_from_untagged_items(tmp_path):
    payload = _build(tmp_path)

    represented = _item(payload, "repo_b_cassandra_listener_review")
    partial = _item(payload, "repo_b_cassandra_email_calendar")
    untagged = _item(payload, "repo_b_untagged_safe_path_inventory")

    assert represented["classification"] == "REPO_B_ALREADY_REPRESENTED"
    assert partial["classification"] == "REPO_B_PARTIALLY_REPRESENTED"
    assert untagged["classification"] == "REPO_B_UNTAGGED"
    assert ".claude/commands/cassandra.md" in untagged["path_or_read_model_refs"]
    assert "UNKNOWN_NEW_SURFACE.md" in untagged["path_or_read_model_refs"]
    assert "repo_b_untagged_safe_path_inventory" in payload["awareness_answers"]["repo_b_untagged_or_unclear"]


def test_unsafe_blocked_items_remain_blocked(tmp_path):
    payload = _build(tmp_path)

    for item_id in ["repo_b_planner_builder_automation", "repo_b_oauth_browser_credential_bridges"]:
        item = _item(payload, item_id)
        assert item["classification"] == "REPO_B_UNSAFE_OR_BLOCKED"
        assert item["safe_to_use_now"] is False
        assert item["metadata_only"] is True
        assert item["authority_boundary"] == "known_but_not_allowed_to_run"


def test_operator_memory_only_is_not_treated_as_proven(tmp_path):
    payload = _build(tmp_path)
    memory = _item(payload, "operator_memory_calendar_merge_context")

    assert memory["classification"] == "OPERATOR_MEMORY_ONLY"
    assert memory["needs_winship_memory_review"] is True
    assert memory["safe_to_use_now"] is False
    assert memory["what_openclaw_currently_knows"].startswith("Operator memory/context only")


def test_unknowns_fail_closed_and_support_aware_x_not_y_answer(tmp_path):
    payload = _build(tmp_path)
    unknown = _item(payload, "unknown_unclassified_capability")
    examples = payload["aware_of_x_not_y_examples"]

    assert unknown["classification"] == "UNKNOWN_NEEDS_REVIEW"
    assert unknown["safe_to_use_now"] is False
    assert unknown["should_be_brought_forward"] is False
    assert examples["aware_of_examples"]
    assert examples["not_yet_aware_or_not_classified_examples"]


def test_eli5_summary_exists_and_is_operator_readable(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "definitely aware" in eli5["what_openclaw_is_definitely_aware_of"].lower()
    assert "Repo A has tagged" in eli5["what_repo_a_has_tagged"]
    assert "Repo B had" in eli5["what_repo_b_had_already_represented"]
    assert "Repo B still has" in eli5["what_repo_b_still_has_that_may_not_be_tagged"]
    assert "known but blocked" in eli5["what_is_known_but_blocked"].lower()
    assert len(eli5["next_1_to_3_sensible_lanes"]) == 3


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    root = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    _fixture_repo(root, repo_b)

    result = matrix.export_cross_repo_awareness_matrix(
        repo_root=root,
        repo_b_root=repo_b,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == matrix.SCHEMA_VERSION
    assert result.runtime_authority_added is False
    assert "cross_repo_awareness_matrix.json" in canonical_generated_read_model_expected_files(
        source_root=root / "generated/read_models",
        repo_root=root,
    )

    assert export_main(["--repo-root", root.as_posix(), "--repo-b-root", repo_b.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == matrix.SCHEMA_VERSION

    assert export_main(["--repo-root", root.as_posix(), "--repo-b-root", repo_b.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Cross-Repo Awareness Matrix v0" in output
    assert "No Repo B code was executed" in output


def test_source_does_not_import_live_execution_or_repo_b_runtime_mechanisms():
    source = Path("cross_repo_awareness_matrix.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "subprocess" not in imports
    assert "requests" not in imports
    assert "httpx" not in imports
    assert "google_access_broker" not in imports
    assert "smtplib" not in imports
    assert "imaplib" not in imports
    assert "webbrowser" not in imports
    assert "selenium" not in imports
    assert "playwright" not in imports


def test_write_calls_are_limited_to_generated_read_model_exports():
    tree = ast.parse(Path("cross_repo_awareness_matrix.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
