import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import project_room_sourceset_contract as contract


FIXED_NOW = "2026-06-08T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    statuses = {
        "context_freshness_decision_trace_gate.json": "CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",
        "proof_bundle_freshness_trace_status.json": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",
        "retrospective_harness_learning_seed.json": "RETROSPECTIVE_HARNESS_LEARNING_SEED_READY",
        "proof_bundle_redaction_policy.json": "PROOF_BUNDLE_REDACTION_HARDENING_READY",
        "universal_receipt_envelope_status.json": "UNIVERSAL_RECEIPT_ENVELOPE_READY",
        "operator_session_timeline.json": "OPERATOR_SESSION_TIMELINE_READY",
        "goldilocks_gate_calibration.json": "GOLDILOCKS_GATE_CALIBRATION_READY",
    }
    for filename, status in statuses.items():
        _write_json(root / filename, {"status": status})
    return root


def _read_model(tmp_path: Path) -> dict:
    return contract.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "project_room.sqlite",
        generated_at=FIXED_NOW,
    )


def _room(read_model: dict, room_id: str) -> dict:
    return next(room for room in read_model["project_rooms"] if room["project_room_id"] == room_id)


def _sources(read_model: dict, room_id: str) -> list[dict]:
    return [source for source in read_model["source_inventory"] if source["project_room_id"] == room_id]


def test_all_required_project_room_artifact_fields_exist(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == contract.READY_STATUS
    assert {room["project_room_id"] for room in read_model["project_rooms"]} == set(contract.REQUIRED_SCENARIOS)
    assert read_model["machine_proof"]["all_required_scenarios_present"] is True
    assert read_model["machine_proof"]["project_room_fields_complete"] is True
    assert read_model["machine_proof"]["source_inventory_fields_complete"] is True
    assert read_model["machine_proof"]["conflict_log_fields_complete"] is True
    assert read_model["machine_proof"]["missing_context_fields_complete"] is True
    assert read_model["machine_proof"]["duplicate_report_fields_complete"] is True
    assert read_model["machine_proof"]["decision_trace_fields_complete"] is True


def test_source_inventory_required_before_synthesis_allowed_true(tmp_path):
    read_model = _read_model(tmp_path)
    inventory_refs = {source["source_inventory_ref"] for source in read_model["source_inventory"]}

    assert contract.source_inventory_required_before_synthesis(read_model) is True
    assert read_model["machine_proof"]["source_inventory_required_before_synthesis"] is True
    for room in read_model["project_rooms"]:
        if room["synthesis_allowed"] is True:
            assert room["source_inventory_ref"] in inventory_refs
            assert not room["inventory_gate"].startswith("blocked")


def test_conflict_log_required_when_sources_disagree(tmp_path):
    read_model = _read_model(tmp_path)
    bd_room = _room(read_model, "business_development_capital_hilton_follow_up")
    stale_room = _room(read_model, "stale_source")

    assert bd_room["source_disagreement_detected"] is True
    assert stale_room["source_disagreement_detected"] is True
    assert contract.conflict_log_required_when_sources_disagree(read_model) is True
    assert read_model["machine_proof"]["conflict_log_required_when_sources_disagree"] is True
    assert any(conflict["conflict_ref"] == "conflict:bd_proposal_follow_up_status" for conflict in read_model["conflict_log"])
    assert any(conflict["conflict_ref"] == "conflict:stale_summary_vs_current_truth" for conflict in read_model["conflict_log"])


def test_missing_context_blocks_unsupported_claims(tmp_path):
    read_model = _read_model(tmp_path)
    gaps = {gap["missing_context_ref"]: gap for gap in read_model["missing_context_list"]}

    assert contract.missing_context_blocks_unsupported_claims(read_model) is True
    assert read_model["machine_proof"]["missing_context_blocks_unsupported_claims"] is True
    assert "payment evidence is missing" in gaps["missing_context:finance_payment_evidence"]["safe_wording_if_unresolved"].lower()
    assert "cannot mark paid" in gaps["missing_context:finance_payment_evidence"]["safe_wording_if_unresolved"].lower()
    assert "cannot make factual controller claims" in gaps["missing_context:niles_controller_target"][
        "safe_wording_if_unresolved"
    ].lower()


def test_duplicate_report_does_not_delete_files(tmp_path):
    read_model = _read_model(tmp_path)

    assert contract.duplicate_report_does_not_delete_files(read_model) is True
    assert read_model["machine_proof"]["duplicate_report_does_not_delete_files"] is True
    assert all(report["operator_review_required"] is True for report in read_model["duplicate_version_report"])
    assert all(report["deletion_allowed"] is False for report in read_model["duplicate_version_report"])


def test_current_receipts_outrank_generated_summaries(tmp_path):
    read_model = _read_model(tmp_path)
    ranking = read_model["authority_rankings"][0]["ranked_authority"]
    summaries = [source for source in read_model["source_inventory"] if source["apparent_authority"] == "generated_summaries"]

    assert ranking.index("current_receipts_and_proof") < ranking.index("generated_summaries")
    assert contract.current_receipts_outrank_generated_summaries(read_model) is True
    assert summaries
    assert all("current truth" in {item.lower() for item in source["do_not_use_for"]} for source in summaries)


def test_superseded_sources_cannot_be_current_truth(tmp_path):
    read_model = _read_model(tmp_path)
    stale_room = _room(read_model, "stale_source")
    stale_sources = _sources(read_model, "stale_source")

    assert contract.superseded_sources_cannot_be_current_truth(read_model) is True
    assert read_model["machine_proof"]["superseded_sources_cannot_be_current_truth"] is True
    assert stale_room["synthesis_allowed"] is False
    assert "Needs verification" in stale_room["allowed_next_steps"][0]
    assert all("current truth" in {item.lower() for item in source["do_not_use_for"]} for source in stale_sources)


def test_build_resolved_packet_remains_historical(tmp_path):
    read_model = _read_model(tmp_path)
    build_room = _room(read_model, "build_review_packet")
    build_sources = _sources(read_model, "build_review_packet")
    trace = next(trace for trace in read_model["decision_traces"] if trace["project_room_id"] == "build_review_packet")

    assert contract.build_resolved_packet_remains_historical(read_model) is True
    assert build_room["synthesis_scope"] == "historical_summary_only"
    assert "treat resolved packet as active work" in build_room["blocked_next_steps"]
    assert build_sources[0]["freshness_state"] == "historical_resolved"
    assert "Resolved packet remains historical" in " ".join(trace["operator_decisions"])


def test_finance_payment_watch_blocks_paid_and_ledger(tmp_path):
    read_model = _read_model(tmp_path)
    finance_room = _room(read_model, "finance_capital_hilton_payment_watch")
    finance_sources = _sources(read_model, "finance_capital_hilton_payment_watch")

    assert contract.finance_payment_watch_blocks_paid_ledger(read_model) is True
    assert finance_room["synthesis_scope"] == "explanation_and_next_step_only"
    assert "mark paid" in finance_room["blocked_next_steps"]
    assert "mutate ledger" in finance_room["blocked_next_steps"]
    assert finance_room["protected_authority"]["paid_action_allowed"] is False
    assert finance_room["protected_authority"]["ledger_action_allowed"] is False
    assert "paid=false" in " ".join(finance_sources[0]["claims_supported"])
    assert "ledger untouched" in " ".join(finance_sources[0]["claims_supported"])


def test_niles_creative_room_excludes_unrelated_finance_proof(tmp_path):
    read_model = _read_model(tmp_path)
    niles_room = _room(read_model, "niles_music_controller_mapping")
    niles_sources = _sources(read_model, "niles_music_controller_mapping")

    assert contract.niles_creative_room_excludes_unrelated_finance_proof(read_model) is True
    assert niles_room["synthesis_scope"] == "creative_options_only"
    assert "make factual controller claims" in niles_room["blocked_next_steps"]
    assert len(niles_sources) == 1
    source_refs = json.dumps(
        [
            niles_sources[0]["source_ref"],
            niles_sources[0]["path_or_artifact_ref"],
            niles_sources[0]["receipt_refs"],
        ]
    ).lower()
    assert "finance" not in source_refs
    assert "coupa" not in source_refs


def test_self_heal_repair_package_requires_validation_plan(tmp_path):
    read_model = _read_model(tmp_path)
    room = _room(read_model, "self_heal_repair")
    sources = _sources(read_model, "self_heal_repair")

    assert room["synthesis_scope"] == "repair_package_proposal_only"
    assert "propose repair package with validation plan" in room["allowed_next_steps"]
    assert "execute repair" in room["blocked_next_steps"]
    assert "validation plan" in room["repair_package_requirements"]
    assert any("Validation plan is required" in " ".join(source["claims_supported"]) for source in sources)


def test_sqlite_row_count_matches_json(tmp_path):
    sqlite_path = tmp_path / "project_room.sqlite"
    read_model = contract.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )
    expected = (
        len(read_model["project_rooms"])
        + len(read_model["source_inventory"])
        + len(read_model["conflict_log"])
        + len(read_model["missing_context_list"])
        + len(read_model["duplicate_version_report"])
        + len(read_model["decision_traces"])
    )

    with sqlite3.connect(sqlite_path) as conn:
        actual = conn.execute("SELECT COUNT(*) FROM project_room_sourceset_records").fetchone()[0]

    assert actual == expected
    assert read_model["sqlite_summary"]["sqlite_row_count"] == expected
    assert read_model["machine_proof"]["sqlite_row_count_matches_json"] is True


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert contract.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_wiki_and_sqlite(tmp_path):
    result = contract.export_project_room_sourceset_contract(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Project Room Sourceset Contract.md",
        sqlite_path=tmp_path / "project_room.sqlite",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == contract.READY_STATUS
    assert local == bridge
    assert contract.unsafe_true_grants(local) == []
    assert wiki.startswith("# Project Room Sourceset Contract")
    assert int(result["sqlite_row_count"]) == local["sqlite_summary"]["sqlite_row_count"]
