import json
import sqlite3
from pathlib import Path

import agentic_chain_inspector as inspector


FIXED_NOW = "2026-06-02T09:00:00+00:00"


def _sqlite(path: Path, statements: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()


def _fixture_sqlite_roots(tmp_path: Path) -> tuple[Path, Path]:
    generated = tmp_path / "generated" / "system_knowledge"
    openclaw = tmp_path / ".openclaw"
    _sqlite(
        generated / "workflow_package_queue.sqlite",
        [
            "CREATE TABLE packages (package_id TEXT)",
            "INSERT INTO packages VALUES ('pkg_1')",
            "CREATE TABLE package_inputs (package_id TEXT)",
            "CREATE TABLE privacy_gate_results (package_id TEXT)",
            "CREATE TABLE intent_classification_results (package_id TEXT)",
            "CREATE TABLE capability_gate_results (package_id TEXT)",
            "CREATE TABLE worker_assignments (package_id TEXT)",
            "CREATE TABLE worker_results (package_id TEXT)",
            "CREATE TABLE operator_review_receipts (package_id TEXT)",
            "CREATE TABLE business_action_gate_results (package_id TEXT)",
        ],
    )
    _sqlite(
        openclaw / "business_ops" / "ledger.sqlite",
        [
            "CREATE TABLE ledger_entries (entry_id TEXT)",
            "INSERT INTO ledger_entries VALUES ('ledger_1')",
        ],
    )
    _sqlite(
        openclaw / "test_harness" / "gate_chain_harness.sqlite",
        [
            "CREATE TABLE package_gate_decisions (decision_id TEXT)",
            "CREATE TABLE child_package_requests (request_id TEXT)",
            "INSERT INTO package_gate_decisions VALUES ('decision_1')",
        ],
    )
    return generated, openclaw


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_sqlite_inventory_records_paths_tables_counts_and_ledger_exclusion(tmp_path):
    generated, openclaw = _fixture_sqlite_roots(tmp_path)

    inventory = inspector.inspect_sqlite_databases((generated, openclaw))

    by_name = {Path(item["path"]).name: item for item in inventory}
    assert set(by_name) == {
        "workflow_package_queue.sqlite",
        "ledger.sqlite",
        "gate_chain_harness.sqlite",
    }
    assert by_name["workflow_package_queue.sqlite"]["row_counts"]["packages"] == 1
    assert by_name["workflow_package_queue.sqlite"]["canonical_noncanonical_guess"] == "canonical_candidate_for_package_queue"
    assert by_name["ledger.sqlite"]["consolidation_risk"] == "never_mix_business_ledger"
    assert by_name["ledger.sqlite"]["canonical_noncanonical_guess"] == "business_ledger_canonical_never_mix"
    assert by_name["gate_chain_harness.sqlite"]["purpose"] == "test harness or pytest fixture database"


def test_gate_chain_maps_required_gates_and_sqlite_tracking(tmp_path):
    generated, openclaw = _fixture_sqlite_roots(tmp_path)
    read_model = inspector.build_read_model(
        sqlite_roots=(generated, openclaw),
        generated_at=FIXED_NOW,
    )

    gates = {gate["gate_id"]: gate for gate in read_model["gate_chain"]}
    assert {
        "human_message",
        "privacy_pii_gate",
        "intent_lm_gate",
        "sqlite_package_gate",
        "workflow_package_compiler",
        "capability_provider_gate",
        "lm2_child_cage",
        "worker",
        "result_receipt",
        "operator_review_gate",
        "business_action_gate",
        "final_read_model_ui_response",
    } == set(gates)
    assert gates["privacy_pii_gate"]["sqlite_tracked"] is True
    assert gates["business_action_gate"]["sqlite_tracked"] is True
    assert gates["lm2_child_cage"]["posture"] == "contract-only"
    assert all(value is False for value in gates["business_action_gate"]["authority_boundary"].values())


def test_fragmentation_risks_and_recommendations_include_required_boundaries(tmp_path):
    generated, openclaw = _fixture_sqlite_roots(tmp_path)
    read_model = inspector.build_read_model(
        sqlite_roots=(generated, openclaw),
        generated_at=FIXED_NOW,
    )

    risks = {risk["risk_id"]: risk for risk in read_model["fragmentation_risks"]}
    assert risks["duplicate_package_concepts"]["severity"] == "high"
    assert risks["business_ledger_exclusion"]["severity"] == "critical"
    assert risks["test_harness_dbs"]["affected_path_count"] >= 1
    recommendations = {item["recommendation_id"]: item for item in read_model["recommendations"]}
    assert "consolidate_package_event_index_first" in recommendations
    assert recommendations["never_mix_ledger_with_agent_memory"]["category"] == "never_mix"


def test_export_writes_local_bridge_and_inspector_sqlite_rows(tmp_path):
    generated, openclaw = _fixture_sqlite_roots(tmp_path)
    result = inspector.export_agentic_chain_inspector(
        sqlite_roots=(generated, openclaw),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Agentic Chain Inspector.md",
        inspector_sqlite_path=tmp_path / "system_knowledge" / "agentic_chain_inspector.sqlite",
        generated_at=FIXED_NOW,
    )

    local = _load(result["read_model_path"])
    bridge = _load(result["bridge_read_model_path"])
    assert local == bridge
    assert local["status"] == inspector.CONTRACT_STATUS
    assert local["sqlite_inventory_count"] == 3
    assert Path(result["wiki_path"]).exists()

    conn = sqlite3.connect(result["inspector_sqlite_path"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM gate_chain").fetchone()[0] == 12
        assert conn.execute("SELECT COUNT(*) FROM database_inventory").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM fragmentation_risks").fetchone()[0] == 6
        assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] >= 4
    finally:
        conn.close()


def test_no_unsafe_true_grants(tmp_path):
    generated, openclaw = _fixture_sqlite_roots(tmp_path)
    read_model = inspector.build_read_model(
        sqlite_roots=(generated, openclaw),
        generated_at=FIXED_NOW,
    )
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "paid_marking_allowed",
        "sent",
        "paid",
    }
    assert not [
        key
        for key, value in _walk_values(read_model)
        if key in unsafe_keys and value is True
    ]
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
