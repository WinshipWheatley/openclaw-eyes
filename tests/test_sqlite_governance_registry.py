import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sqlite_governance_registry as registry


FIXED_NOW = "2026-06-03T12:00:00+00:00"


def _sqlite(path: Path, statements: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_roots(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    generated = tmp_path / "generated" / "system_knowledge"
    openclaw = tmp_path / ".openclaw"
    read_models = tmp_path / "generated" / "read_models"
    agentic_json = read_models / "agentic_chain_inspector.json"
    package_index_json = read_models / "package_event_index.json"

    _sqlite(
        generated / "workflow_package_queue.sqlite",
        [
            "CREATE TABLE packages (package_id TEXT)",
            "INSERT INTO packages VALUES ('pkg_1')",
            "CREATE TABLE package_inputs (package_id TEXT)",
            "CREATE TABLE business_action_gate_results (package_id TEXT)",
        ],
    )
    _sqlite(
        generated / "openclaw_change_sentinel.sqlite",
        [
            "CREATE TABLE observed_change (change_id TEXT)",
            "INSERT INTO observed_change VALUES ('change_1')",
        ],
    )
    _sqlite(
        generated / "st_annes_invoice_status.sqlite",
        [
            "CREATE TABLE st_annes_invoice_status_receipt (receipt_id TEXT)",
            "INSERT INTO st_annes_invoice_status_receipt VALUES ('receipt_1')",
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
        openclaw / "business_ops" / "backups" / "ledger_before.sqlite",
        [
            "CREATE TABLE ledger_entries (entry_id TEXT)",
            "INSERT INTO ledger_entries VALUES ('ledger_backup_1')",
        ],
    )
    _sqlite(
        openclaw / "test_harness" / "gate_chain_harness.sqlite",
        [
            "CREATE TABLE package_gate_decisions (decision_id TEXT)",
            "INSERT INTO package_gate_decisions VALUES ('decision_1')",
        ],
    )
    _sqlite(
        openclaw / "flows" / "registry.sqlite",
        [
            "CREATE TABLE flow_runs (run_id TEXT)",
        ],
    )
    _sqlite(
        openclaw / "privacy" / "token_vault.sqlite",
        [
            "CREATE TABLE token_vault_metadata (metadata_id TEXT)",
            "INSERT INTO token_vault_metadata VALUES ('metadata_1')",
        ],
    )

    agentic_inventory = []
    for path, purpose, guess, risk in [
        (
            generated / "workflow_package_queue.sqlite",
            "workflow package queue and gate registry",
            "canonical_candidate_for_package_queue",
            "high_duplicate_package_or_gate_concept",
        ),
        (
            generated / "openclaw_change_sentinel.sqlite",
            "system health, sentinel, or service status",
            "read_model_evidence_or_contract_state",
            "medium_duplicate_event_or_status_store",
        ),
        (
            openclaw / "business_ops" / "ledger.sqlite",
            "business ledger or test ledger",
            "business_ledger_canonical_never_mix",
            "never_mix_business_ledger",
        ),
        (
            openclaw / "privacy" / "token_vault.sqlite",
            "privacy token vault",
            "privacy_vault_canonical_isolated",
            "never_mix_privacy_vault",
        ),
    ]:
        agentic_inventory.append(
            {
                "path": path.resolve().as_posix(),
                "purpose": purpose,
                "tables": [],
                "row_counts": {},
                "last_modified": FIXED_NOW,
                "canonical_noncanonical_guess": guess,
                "consolidation_risk": risk,
                "open_status": "ok",
                "error": "",
            }
        )
    _write_json(
        agentic_json,
        {
            "status": registry.REQUIRED_PRECONDITIONS["agentic_chain_inspector"],
            "sqlite_inventory": agentic_inventory,
        },
    )
    _write_json(
        package_index_json,
        {"status": registry.REQUIRED_PRECONDITIONS["package_event_index"], "events": []},
    )
    return generated, openclaw, read_models, agentic_json, package_index_json


def _by_name(read_model: dict) -> dict[str, dict]:
    return {Path(item["path"]).name: item for item in read_model["databases"]}


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_classifies_canonical_generated_test_ledger_and_unknown_databases(tmp_path):
    generated, openclaw, _read_models, agentic_json, package_index_json = _fixture_roots(tmp_path)
    read_model = registry.build_read_model(
        sqlite_roots=(generated, openclaw),
        agentic_chain_read_model_path=agentic_json,
        agentic_chain_sqlite_path=tmp_path / "missing_agentic_chain.sqlite",
        package_event_index_read_model_path=package_index_json,
        generated_at=FIXED_NOW,
    )

    by_name = _by_name(read_model)
    queue = by_name["workflow_package_queue.sqlite"]
    assert queue["classification"] == "canonical_workflow_state"
    assert queue["canonical_truth_allowed"] is True
    assert queue["writable_by_automation"] is False
    assert queue["safe_to_delete"] is False
    assert queue["row_counts"]["packages"] == 1

    ledger = by_name["ledger.sqlite"]
    assert ledger["classification"] == "protected_business_ledger"
    assert ledger["owner_lane"] == "business_ops"
    assert ledger["consolidation_risk"] == "forbidden"
    assert ledger["canonical_truth_allowed"] is True
    assert ledger["writable_by_automation"] is False

    backup = by_name["ledger_before.sqlite"]
    assert backup["classification"] == "protected_business_ledger"
    assert backup["canonical_truth_allowed"] is False
    assert backup["consolidation_risk"] == "forbidden"

    harness = by_name["gate_chain_harness.sqlite"]
    assert harness["classification"] == "test_harness"
    assert harness["canonical_truth_allowed"] is False
    assert harness["writable_by_automation"] is False

    status = by_name["openclaw_change_sentinel.sqlite"]
    assert status["classification"] == "generated_status"
    assert status["canonical_truth_allowed"] is False

    invoice = by_name["st_annes_invoice_status.sqlite"]
    assert invoice["classification"] == "generated_evidence"
    assert invoice["canonical_truth_allowed"] is False

    unknown = by_name["registry.sqlite"]
    assert unknown["classification"] == "unknown_needs_review"
    assert unknown["writable_by_automation"] is False

    vault = by_name["token_vault.sqlite"]
    assert vault["classification"] == "canonical_workflow_state"
    assert vault["canonical_truth_allowed"] is True
    assert vault["consolidation_risk"] == "forbidden"


def test_agentic_chain_sqlite_inventory_is_merged(tmp_path):
    generated, openclaw, _read_models, agentic_json, package_index_json = _fixture_roots(tmp_path)
    inspector_sqlite = tmp_path / "generated" / "system_knowledge" / "agentic_chain_inspector.sqlite"
    external = tmp_path / ".openclaw" / "external_inventory_only.sqlite"
    _sqlite(
        inspector_sqlite,
        [
            "CREATE TABLE database_inventory (path TEXT PRIMARY KEY, root_group TEXT, purpose TEXT, tables_json TEXT, row_counts_json TEXT, last_modified TEXT, canonical_noncanonical_guess TEXT, consolidation_risk TEXT, open_status TEXT, error TEXT)",
            (
                "INSERT INTO database_inventory VALUES "
                f"('{external.as_posix()}', 'openclaw_state', 'local OpenClaw SQLite state', '[\"external_table\"]', '{{\"external_table\": 3}}', '{FIXED_NOW}', 'noncanonical_or_unknown', 'medium_unknown_until_owner_named', 'ok', '')"
            ),
        ],
    )

    read_model = registry.build_read_model(
        sqlite_roots=(generated, openclaw),
        agentic_chain_read_model_path=agentic_json,
        agentic_chain_sqlite_path=inspector_sqlite,
        package_event_index_read_model_path=package_index_json,
        generated_at=FIXED_NOW,
    )

    match = [item for item in read_model["databases"] if item["path"] == external.resolve().as_posix()]
    assert len(match) == 1
    assert match[0]["classification"] == "unknown_needs_review"
    assert match[0]["row_counts"] == {"external_table": 3}


def test_export_writes_local_bridge_wiki_and_registry_sqlite(tmp_path):
    generated, openclaw, _read_models, agentic_json, package_index_json = _fixture_roots(tmp_path)
    result = registry.export_sqlite_governance_registry(
        sqlite_roots=(generated, openclaw),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "SQLite Governance Registry.md",
        registry_sqlite_path=tmp_path / "system_knowledge" / "sqlite_governance_registry.sqlite",
        agentic_chain_read_model_path=agentic_json,
        agentic_chain_sqlite_path=tmp_path / "missing_agentic_chain.sqlite",
        package_event_index_read_model_path=package_index_json,
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == registry.REGISTRY_STATUS
    assert local["machine_proof"]["preconditions_ready"] is True
    assert Path(result["wiki_path"]).exists()
    assert Path(result["sqlite_path"]).exists()
    assert "sqlite_governance_registry.sqlite" in _by_name(local)

    conn = sqlite3.connect(result["sqlite_path"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM database_governance").fetchone()[0] == local["database_count"]
        assert conn.execute("SELECT value FROM registry_metadata WHERE key='status'").fetchone()[0] == registry.REGISTRY_STATUS
        protected = conn.execute(
            "SELECT COUNT(*) FROM database_governance WHERE classification='protected_business_ledger' AND consolidation_risk='forbidden'"
        ).fetchone()[0]
        assert protected >= 2
    finally:
        conn.close()


def test_precondition_failure_marks_not_ready(tmp_path):
    generated, openclaw, _read_models, agentic_json, package_index_json = _fixture_roots(tmp_path)
    _write_json(package_index_json, {"status": "NOT_READY"})

    read_model = registry.build_read_model(
        sqlite_roots=(generated, openclaw),
        agentic_chain_read_model_path=agentic_json,
        agentic_chain_sqlite_path=tmp_path / "missing_agentic_chain.sqlite",
        package_event_index_read_model_path=package_index_json,
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == registry.REGISTRY_NOT_READY_STATUS
    assert read_model["machine_proof"]["preconditions_ready"] is False


def test_no_deletes_migrations_or_unsafe_true_grants(tmp_path):
    generated, openclaw, _read_models, agentic_json, package_index_json = _fixture_roots(tmp_path)
    read_model = registry.build_read_model(
        sqlite_roots=(generated, openclaw),
        agentic_chain_read_model_path=agentic_json,
        agentic_chain_sqlite_path=tmp_path / "missing_agentic_chain.sqlite",
        package_event_index_read_model_path=package_index_json,
        generated_at=FIXED_NOW,
    )

    unsafe_keys = {
        "email_send_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "ledger_posting_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "paid_marking_allowed",
        "database_delete_allowed",
        "database_move_allowed",
        "sqlite_consolidation_allowed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    assert all(item["safe_to_delete"] is False for item in read_model["databases"])
    assert all(item["writable_by_automation"] is False for item in read_model["databases"])
    assert read_model["machine_proof"]["database_delete_performed"] is False
    assert read_model["machine_proof"]["database_migration_performed"] is False
    assert read_model["machine_proof"]["ledger_mutation_performed"] is False
