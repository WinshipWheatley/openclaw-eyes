import ast
import json
from pathlib import Path

import capability_skill_registry_metadata_delta as registry
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_capability_skill_registry_metadata_delta import main as export_main


FIXED_NOW = "2026-05-19T04:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    _write_json(
        read_models / "repo_a_known_rail_completion_map.json",
        {
            "schema_version": "repo_a_known_rail_completion_map_v0",
            "known_rail_count": 14,
            "maturity_counts": {
                "READ_MODEL_VISIBLE": 14,
                "REVIEW_PACKET_READY": 3,
                "PROOF_RAIL_READY": 1,
                "APPROVAL_REQUEST_CONTRACT_READY": 4,
            },
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
                    "capability_id": "planner_builder_automation",
                    "classification": "UNSAFE_OR_BLOCKED",
                    "should_bring_forward": False,
                }
            ],
        },
    )
    for name, schema in {
        "chief_status_rail.json": "chief_status_rail_v0",
        "build_now_vs_hold_queue_posture.json": "build_now_vs_hold_queue_posture_v0",
        "protected_access_broker_concept.json": "protected_access_broker_concept_v0",
        "protected_evidence_reference_receipt.json": "protected_evidence_reference_receipt_v0",
        "guardian_protected_access_gate_spec.json": "guardian_protected_access_gate_spec_v0",
        "tool_inventory.json": "local_tool_inventory_read_model_v0",
        "tool_intake.json": "tool_intake_read_model_v0",
    }.items():
        _write_json(read_models / name, {"schema_version": schema, "read_model_version": schema})


def _build(tmp_path: Path) -> dict:
    root = tmp_path / "repo_a"
    _fixture_repo(root)
    return registry.build_capability_skill_registry_metadata_delta(repo_root=root, generated_at=FIXED_NOW)


def _record(payload: dict, capability_id: str) -> dict:
    return next(item for item in payload["capability_records"] if item["capability_id"] == capability_id)


def test_registry_is_metadata_only_and_does_not_activate_tools_or_agents(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == registry.SCHEMA_VERSION
    assert payload["registry_delta_status"] == "metadata_only_capability_skill_registry_delta"
    assert payload["metadata_only"] is True
    assert payload["tools_enabled"] is False
    assert payload["agents_activated"] is False
    assert payload["execution_authority_added"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["repo_b_code_executed"] is False
    assert payload["repo_b_filesystem_inspected"] is False


def test_classifies_current_capabilities_with_required_states(tmp_path):
    payload = _build(tmp_path)
    records = {item["capability_id"]: item for item in payload["capability_records"]}

    assert "cassandra_draft_review_email_calendar" in records
    assert "guardian_approval_hitl_protected_access" in records
    assert "chief_status_work_packets_build_now_hold" in records
    assert "capital_hilton_finance_proof_request" in records
    assert "tool_inventory_intake" in records

    cassandra = records["cassandra_draft_review_email_calendar"]
    assert cassandra["primary_state"] == "REVIEW_PACKET_CAPABLE"
    assert "APPROVAL_REQUEST_CAPABLE" in cassandra["state_labels"]
    assert cassandra["execution_allowed_now"] is False

    chief = records["chief_status_work_packets_build_now_hold"]
    assert "WORK_PACKET_CAPABLE" in chief["state_labels"]
    assert chief["tool_activation_allowed_now"] is False


def test_protected_access_capabilities_require_guardian_and_security_gates(tmp_path):
    payload = _build(tmp_path)

    for capability_id in [
        "capital_hilton_finance_proof_request",
        "browser_oauth_credential_bridges",
        "guardian_approval_hitl_protected_access",
    ]:
        item = _record(payload, capability_id)
        assert item["requires_guardian_gate"] is True

    protected = _record(payload, "browser_oauth_credential_bridges")
    assert protected["requires_protected_access_gate"] is True
    assert protected["requires_security_threshold_before_live_use"] is True
    assert "SECURITY_THRESHOLD_REQUIRED" in protected["state_labels"]
    assert protected["activation_allowed_now"] is False


def test_repo_b_derived_items_remain_reference_only_until_promoted(tmp_path):
    payload = _build(tmp_path)

    legacy = _record(payload, "legacy_capability_registry_cross_agent_lookup")
    planner = _record(payload, "planner_builder_automation_loops")

    assert legacy["primary_state"] == "REFERENCE_ONLY"
    assert legacy["repo_b_delta_posture"] == "legacy_reference_or_repo_b_delta_evidence_only"
    assert legacy["activation_allowed_now"] is False
    assert planner["primary_state"] == "UNSAFE_OR_BLOCKED"
    assert "REFERENCE_ONLY" in planner["state_labels"]
    assert payload["repo_b_delta_handling"]["repo_b_filesystem_inspected"] is False


def test_blocked_automation_repair_browser_oauth_remain_blocked(tmp_path):
    payload = _build(tmp_path)

    for capability_id in [
        "planner_builder_automation_loops",
        "automatic_repair_loops",
        "browser_oauth_credential_bridges",
    ]:
        item = _record(payload, capability_id)
        assert item["primary_state"] in {"UNSAFE_OR_BLOCKED", "PROTECTED_ACCESS_GATED"}
        assert item["execution_allowed_now"] is False
        assert item["agent_activation_allowed_now"] is False
        assert item["blocked_authorities"]


def test_unknown_capability_fails_closed(tmp_path):
    payload = _build(tmp_path)
    unknown = _record(payload, "unknown_capability")

    assert unknown["primary_state"] == "UNKNOWN_FAIL_CLOSED"
    assert unknown["unknown_fails_closed"] is True
    assert unknown["safe_to_route_as_work_packet_or_read_model_lane"] is False
    assert unknown["execution_allowed_now"] is False


def test_safe_work_packet_routes_are_visibility_not_execution(tmp_path):
    payload = _build(tmp_path)
    safe_routes = payload["routing_summary"]["safe_work_packet_or_read_model_lane_capabilities"]

    assert "chief_status_work_packets_build_now_hold" in safe_routes
    assert "capital_hilton_finance_proof_request" in safe_routes
    for capability_id in safe_routes:
        item = _record(payload, capability_id)
        assert item["execution_allowed_now"] is False
        assert item["safe_to_route_as_work_packet_or_read_model_lane"] is True


def test_eli5_summary_exists_and_recommends_bounded_lanes(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "Here is what OpenClaw knows how to talk about" in eli5["what_openclaw_knows_how_to_talk_about"]
    assert "blocked until security/live-authority work" in eli5["what_is_blocked_until_security_live_authority_work"]
    assert len(eli5["next_1_to_3_sensible_lanes"]) == 3
    assert "live execution" not in " ".join(eli5["next_1_to_3_sensible_lanes"]).lower()


def test_generated_read_model_is_deterministic_exportable_and_safe_mirror_candidate(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = registry.export_capability_skill_registry_metadata_delta(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )
    first = (repo / "generated/read_models/capability_skill_registry_metadata_delta.json").read_text(encoding="utf-8")
    registry.export_capability_skill_registry_metadata_delta(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )
    second = (repo / "generated/read_models/capability_skill_registry_metadata_delta.json").read_text(encoding="utf-8")

    assert first == second
    assert result.schema_version == registry.SCHEMA_VERSION
    assert "capability_skill_registry_metadata_delta.json" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )
    assert "capability_skill_registry_metadata_delta_OPERATOR.md" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )


def test_cli_exports_json_and_operator_outputs(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    exit_code = export_main(["--repo-root", repo.as_posix(), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == registry.SCHEMA_VERSION
    assert (repo / "generated/read_models/capability_skill_registry_metadata_delta_OPERATOR.md").is_file()

    exit_code = export_main(["--repo-root", repo.as_posix(), "--format", "operator"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Capability Skill Registry Metadata Delta v0" in output
    assert "ELI5 Summary" in output
    assert "No tools, agents, browser/OAuth/credentials, sends, approvals, Repo B execution, planner/builder, repair, or runtime authority were activated." in output


def test_source_does_not_import_live_execution_or_repo_b_mechanisms():
    source = Path("capability_skill_registry_metadata_delta.py").read_text(encoding="utf-8")
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
    assert "selenium" not in imports
    assert "playwright" not in imports
    assert "capability_registry" not in imports
    assert "/home/openclaw_external/openclaw-runtime" not in source
