import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm2_live_worker_pilot_boundary_packet as boundary


FIXED_NOW = "2026-06-08T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    for spec in boundary.ROOM_BACKED_PRECONDITIONS.values():
        _write_json(root / spec["filename"], {"status": spec["accepted_statuses"][0]})
    return root


def _read_model(tmp_path: Path) -> dict:
    return boundary.build_room_backed_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "lm2_room_backed.sqlite",
        generated_at=FIXED_NOW,
    )


def test_boundary_requires_room_backed_package(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == boundary.ROOM_BACKED_READY_STATUS
    assert read_model["room_backed_package_required"] is True
    assert read_model["project_room_ready_required"] is True
    assert read_model["room_backed_package"]["room_backed_package_required"] is True
    assert read_model["machine_proof"]["room_backed_package_required"] is True


def test_lm2_package_includes_project_source_room_refs(tmp_path):
    package = _read_model(tmp_path)["room_backed_package"]

    for ref in (
        "project_room_id",
        "source_inventory_ref",
        "conflict_log_ref",
        "missing_context_ref",
        "duplicate_report_ref",
        "decision_trace_ref",
        "redacted_proof_bundle_ref",
        "authority_boundary_ref",
        "receipt_requirement_ref",
    ):
        assert package[ref]
    assert package["project_room_id"] == "finance_capital_hilton_payment_watch"
    assert package["missing_context_ref"] == "missing_context:finance_payment_evidence"


def test_lm2_package_includes_freshness_and_compaction_refs(tmp_path):
    package = _read_model(tmp_path)["room_backed_package"]

    assert package["freshness_gate_ref"] == "freshness_gate:receipt_current_or_needs_verification"
    assert package["compaction_policy_ref"] == "generated/read_models/context_compaction_preview_policy.json"
    assert package["compiled_by_ref"] == "generated/read_models/project_room_package_compiler_integration.json"


def test_lm2_package_excludes_raw_messy_folder_dumps(tmp_path):
    worker_input = _read_model(tmp_path)["worker_package_input"]

    assert "raw_messy_folder_dump" in worker_input["forbidden"]
    assert "full_logs_or_artifacts_by_default" in worker_input["forbidden"]
    assert "raw_messy_folder_dump" not in worker_input["allowed"]
    assert worker_input["raw_context_allowed"] is False


def test_lm2_package_excludes_stale_context_as_current_truth(tmp_path):
    worker_input = _read_model(tmp_path)["worker_package_input"]

    assert "stale_source_as_current_truth" in worker_input["forbidden"]
    assert "duplicate_versions_as_equal_evidence" in worker_input["forbidden"]
    assert "missing_context_as_permission_to_invent" in worker_input["forbidden"]
    assert _read_model(tmp_path)["machine_proof"]["forbidden_inputs_match_contract"] is True


def test_invocation_worker_spawn_and_proof_bundle_disallowed(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["invocation_allowed"] is False
    assert read_model["worker_spawn_allowed"] is False
    assert read_model["proof_bundle_allowed"] is False
    assert read_model["authority_boundary"]["invocation_allowed"] is False
    assert read_model["authority_boundary"]["worker_spawn_allowed"] is False
    assert read_model["authority_boundary"]["proof_bundle_allowed"] is False


def test_tool_and_business_authority_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["authority_boundary"]["tool_authority"] is False
    assert read_model["authority_boundary"]["tool_authority_allowed"] is False
    assert read_model["authority_boundary"]["business_action_authority"] is False
    assert read_model["authority_boundary"]["business_action_allowed"] is False
    assert read_model["machine_proof"]["tool_authority_false"] is True
    assert read_model["machine_proof"]["business_action_authority_false"] is True


def test_stop_conditions_include_required_blocks(tmp_path):
    stop_conditions = set(_read_model(tmp_path)["stop_conditions"])

    assert "project_room_not_ready" in stop_conditions
    assert "source_inventory_missing" in stop_conditions
    assert "freshness_stale_superseded_or_unknown" in stop_conditions
    assert "model_returns_non_json" in stop_conditions
    assert "model_claims_paid_sent_submitted_or_executed" in stop_conditions
    assert "model_promises_protected_action" in stop_conditions
    assert "model_attempts_tool_use" in stop_conditions
    assert "model_exceeds_one_attempt" in stop_conditions


def test_worker_receives_only_room_backed_allowed_input(tmp_path):
    worker_input = _read_model(tmp_path)["worker_package_input"]

    assert set(worker_input["allowed"]) == set(boundary.ROOM_BACKED_ALLOWED_WORKER_INPUTS)
    assert set(worker_input["forbidden"]) == set(boundary.ROOM_BACKED_FORBIDDEN_WORKER_INPUTS)
    assert set(worker_input["allowed"]).isdisjoint(set(worker_input["forbidden"]))
    assert worker_input["loose_proof_bundle_allowed"] is False


def test_expected_response_target_matches_payment_watch_contract(tmp_path):
    expected = _read_model(tmp_path)["expected_response_target"]

    assert expected == boundary.ROOM_BACKED_EXPECTED_RESPONSE
    assert expected["headline"] == "Payment evidence needed"
    assert "paid_false" in expected["claimed_facts"]
    assert expected["requested_controls"] == ["attach_proof"]


def test_required_receipts_before_and_after_future_invocation(tmp_path):
    read_model = _read_model(tmp_path)

    before = set(read_model["required_receipts"]["before_future_invocation"])
    after = set(read_model["required_receipts"]["after_future_invocation"])
    assert "operator_approval_receipt" in before
    assert "room_backed_package_receipt" in before
    assert "project_room_readiness_receipt" in before
    assert "redacted_proof_bundle_receipt" in before
    assert "no_tool_authority_receipt" in before
    assert "worker_started_receipt" in after
    assert "model_invocation_attempt_receipt" in after
    assert "verifier_pass_fail_receipt" in after
    assert "no_business_action_receipt" in after


def test_sqlite_row_check(tmp_path):
    sqlite_path = tmp_path / "lm2_room_backed.sqlite"
    read_model = boundary.build_room_backed_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )

    with sqlite3.connect(sqlite_path) as conn:
        actual = conn.execute("SELECT COUNT(*) FROM lm2_room_backed_worker_pilot_boundary_records").fetchone()[0]

    assert actual == read_model["sqlite_row_count"]
    assert actual == read_model["sqlite_expected_row_count"]
    assert read_model["machine_proof"]["sqlite_row_count_matches_records"] is True


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert boundary.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_wiki_and_sqlite(tmp_path):
    result = boundary.export_lm2_room_backed_worker_pilot_boundary(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "LM2 Room Backed Worker Pilot Boundary.md",
        sqlite_path=tmp_path / "lm2_room_backed.sqlite",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == boundary.ROOM_BACKED_READY_STATUS
    assert local == bridge
    assert boundary.unsafe_true_grants(local) == []
    assert wiki.startswith("# LM2 Room Backed Worker Pilot Boundary")
    assert int(result["sqlite_row_count"]) == local["sqlite_row_count"]
