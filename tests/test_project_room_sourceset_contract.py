import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import context_compaction_preview_policy as compaction_policy
import context_freshness_decision_trace_gate as freshness_gate
import project_room_sourceset_contract as contract


FIXED_NOW = "2026-06-08T11:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    statuses = {
        freshness_gate.JSON_EXPORT_NAME: freshness_gate.READY_STATUS,
        "proof_bundle_freshness_trace_status.json": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",
        "retrospective_harness_learning_seed.json": "RETROSPECTIVE_HARNESS_LEARNING_SEED_READY",
        compaction_policy.JSON_EXPORT_NAME: compaction_policy.READY_STATUS,
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


def _source(read_model: dict, source_ref: str) -> dict:
    return next(row for row in read_model["source_inventory"] if row["source_ref"] == source_ref)


def _scenario(read_model: dict, scenario_ref: str) -> dict:
    return next(row for row in read_model["required_scenarios"] if row["scenario_ref"] == scenario_ref)


def test_source_inventory_required_before_synthesis_allowed_true(tmp_path):
    read_model = _read_model(tmp_path)
    gates = read_model["source_room_gate_examples"]

    assert read_model["status"] == contract.READY_STATUS
    assert gates["without_inventory"]["source_inventory_exists"] is False
    assert gates["without_inventory"]["synthesis_allowed"] is False
    assert gates["without_inventory"]["synthesis_allowed_without_inventory"] is False
    assert gates["with_inventory_and_clear_gates"]["synthesis_allowed"] is True
    assert read_model["project_room_template"]["synthesis_allowed"] is False
    assert "source_inventory_ref" in read_model["project_room_fields"]


def test_conflict_log_required_when_sources_disagree(tmp_path):
    read_model = _read_model(tmp_path)
    conflict = next(row for row in read_model["conflict_log"] if row["conflict_ref"] == "conflict:bd_capital_hilton_followup_status")
    scenario = _scenario(read_model, "business_development_capital_hilton_followup")

    assert conflict["operator_decision_required"] is True
    assert conflict["unresolved"] is True
    assert "source:bd:capital_hilton:older_followup_note" in conflict["conflicting_source_refs"]
    assert scenario["conflict_refs"] == ["conflict:bd_capital_hilton_followup_status"]
    assert scenario["synthesis_allowed"] is False
    assert scenario["send_authority"] is False


def test_missing_context_blocks_unsupported_claims(tmp_path):
    read_model = _read_model(tmp_path)
    missing = next(row for row in read_model["missing_context_list"] if row["missing_context_ref"] == "missing:finance_capital_hilton_payment_evidence")
    finance = _scenario(read_model, "finance_capital_hilton_payment_watch")
    stale = _scenario(read_model, "stale_source")

    assert missing["gap_summary"] == "Payment evidence is missing."
    assert "cannot mark paid" in missing["why_it_matters"]
    assert "ledger" in missing["safe_wording_if_unresolved"]
    assert finance["missing_context_refs"] == ["missing:finance_capital_hilton_payment_evidence"]
    assert stale["synthesis_allowed"] is False
    assert "say_needs_verification" in stale["allowed_next_steps"]


def test_duplicate_report_does_not_delete_files(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["duplicate_version_report"]
    assert all(report["deletion_allowed"] is False for report in read_model["duplicate_version_report"])
    assert read_model["authority_boundary"]["duplicate_deletion_allowed"] is False
    assert read_model["machine_proof"]["duplicates_not_deleted"] is True


def test_current_receipts_outrank_generated_summaries(tmp_path):
    read_model = _read_model(tmp_path)
    ranking = [row["authority_ref"] for row in read_model["authority_ranking"]]
    conflict = next(row for row in read_model["conflict_log"] if row["conflict_ref"] == "conflict:finance_generated_summary_vs_receipt")

    assert ranking.index("current_receipts_and_hashes") < ranking.index("generated_summaries")
    assert conflict["likely_resolution"].startswith("Current receipt wins")
    assert conflict["unresolved"] is False
    assert read_model["authority_boundary"]["generated_summary_override_allowed"] is False


def test_superseded_sources_cannot_be_current_truth(tmp_path):
    read_model = _read_model(tmp_path)
    generated = _source(read_model, "source:finance:capital_hilton:generated_payment_summary")
    version = next(row for row in read_model["duplicate_version_report"] if row["version_family_ref"] == "version_family:capital_hilton_payment_watch_summaries")

    assert generated["freshness_state"] == "historical"
    assert generated["confidence_class"] == "generated_summary"
    assert "current_truth" in generated["do_not_use_for"]
    assert version["likely_current_source_ref"] == "source:finance:capital_hilton:payment_watch_receipt"
    assert "source:finance:capital_hilton:generated_payment_summary" in version["older_or_superseded_refs"]


def test_build_resolved_packet_remains_historical(tmp_path):
    read_model = _read_model(tmp_path)
    source = _source(read_model, "source:build:review_packet_resolved")
    scenario = _scenario(read_model, "build_review_packet")

    assert source["freshness_state"] == "historical"
    assert "not_active_ready_for_review" in source["limitations"]
    assert scenario["lifecycle_state"] == "historical_resolved"
    assert scenario["active_work_allowed"] is False
    assert "treat_as_active_ready_for_review" in scenario["blocked_next_steps"]


def test_finance_payment_watch_blocks_paid_and_ledger(tmp_path):
    read_model = _read_model(tmp_path)
    source = _source(read_model, "source:finance:capital_hilton:payment_watch_receipt")
    scenario = _scenario(read_model, "finance_capital_hilton_payment_watch")

    assert "paid_false" in source["claims_supported"]
    assert "ledger_untouched" in source["claims_supported"]
    assert scenario["mark_paid_allowed"] is False
    assert scenario["ledger_action_allowed"] is False
    assert "mark_paid" in scenario["blocked_next_steps"]
    assert "ledger_mutation" in scenario["blocked_next_steps"]


def test_niles_creative_room_excludes_unrelated_finance_proof(tmp_path):
    scenario = _scenario(_read_model(tmp_path), "niles_music_controller_mapping")

    assert scenario["synthesis_scope"] == "creative_options_only_until_target_supplied"
    assert scenario["unrelated_finance_proof_included"] is False
    assert "missing:niles_controller_or_software_target" in scenario["missing_context_refs"]
    assert "include_finance_proof" in scenario["blocked_next_steps"]


def test_large_artifact_log_source_is_preview_reference_only(tmp_path):
    read_model = _read_model(tmp_path)
    source = _source(read_model, "source:system:large_error_log")
    scenario = _scenario(read_model, "large_artifact_log_source")

    assert source["preview_available"] is True
    assert source["full_source_reference_only"] is True
    assert "dump_full_log" in source["do_not_use_for"]
    assert scenario["full_source_dumped"] is False
    assert "dump_full_log" in scenario["blocked_next_steps"]
    assert read_model["authority_boundary"]["full_log_dump_allowed"] is False


def test_every_source_inventory_row_has_required_fields(tmp_path):
    read_model = _read_model(tmp_path)
    required = set(contract.SOURCE_INVENTORY_FIELDS)

    for source in read_model["source_inventory"]:
        assert required <= set(source)


def test_sqlite_row_check(tmp_path):
    sqlite_path = tmp_path / "project_room.sqlite"
    read_model = contract.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )
    expected = (
        len(read_model["source_inventory"])
        + len(read_model["conflict_log"])
        + len(read_model["missing_context_list"])
        + len(read_model["duplicate_version_report"])
        + len(read_model["required_scenarios"])
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
