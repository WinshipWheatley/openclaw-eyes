import json
import sqlite3
from pathlib import Path

from corpus_atlas import run_corpus_atlas
from evidence_kettle import (
    build_evidence_report,
    evidence_table_names,
    plan_evidence_ingestion,
    query_evidence_report_section,
    run_evidence_kettle,
)
from scripts.query_evidence_kettle import main as query_main


WORLD_IDS = (
    "music_art",
    "finance",
    "operations",
    "security",
    "build",
    "research",
    "communications",
    "business_development",
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sample_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    for name in (
        "AGENTS.md",
        "CORE_ARCHITECTURE_PRINCIPLES.md",
        "OPENCLAW_RUNTIME.md",
        "USER.md",
    ):
        (root / name).write_text(f"# {name}\n", encoding="utf-8")

    (root / ".ssh").mkdir()
    (root / ".ssh" / "id_rsa").write_text("secret fixture should not be read\n", encoding="utf-8")
    (root / "loose.unknown").write_text("unknown fixture should not ingest\n", encoding="utf-8")
    (root / "execution_receipts").mkdir()
    (root / "execution_receipts" / "receipt.json").write_text(
        '{"full_body":"receipt body should not be stored"}\n',
        encoding="utf-8",
    )
    (root / "compliance_verdicts").mkdir()
    (root / "compliance_verdicts" / "verdict.json").write_text(
        '{"verdict_body":"verification body should not be stored"}\n',
        encoding="utf-8",
    )
    (root / "generated" / "read_models").mkdir(parents=True)
    _write_json(
        root / "generated" / "read_models" / "helm_state.json",
        {
            "read_model_version": "helm_state_v0",
            "helm_state": {"state": "inspect_only"},
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution": False,
            "strategic_gravity": {"supported": False},
            "agent_presence_model": {
                "supported": False,
                "live_agents_claimed": False,
            },
            "activation_gate": {
                "gate_state": "blocked_v0_contract",
                "missing_prerequisites": ["explicit_operator_approval"],
            },
            "next_safe_move": "keep inspect-only",
        },
    )
    _write_json(
        root / "generated" / "read_models" / "world_domain_registry.json",
        {
            "read_model_version": "world_domain_registry_v0",
            "world_count": len(WORLD_IDS),
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution": False,
            "dynamic_world_state": False,
            "strategic_gravity_supported": False,
            "agent_presence_supported": False,
            "worlds": [{"world_id": world_id} for world_id in WORLD_IDS],
        },
    )
    _write_json(
        root / "generated" / "read_models" / "world_status.json",
        {
            "read_model_version": "world_status_v0",
            "world_count": len(WORLD_IDS),
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution": False,
            "dynamic_world_state": False,
            "strategic_gravity_supported": False,
            "agent_presence_supported": False,
            "worlds": [{"world_id": world_id, "status": "inspect_only"} for world_id in WORLD_IDS],
        },
    )
    _write_json(
        root / "generated" / "read_models" / "runtime_activation_gate.json",
        {
            "artifact_version": "runtime_module_activation_gate_v0",
            "gate_state": "blocked_v0_contract",
            "runtime_authority": False,
            "activation_allowed": False,
            "module_activation_authority": False,
            "missing_prerequisites": ["explicit_operator_approval", "rollback_plan"],
            "next_safe_move": "keep packets as reasoning context",
        },
    )
    _write_json(
        root / "generated" / "read_models" / "artifact_registry.json",
        {
            "read_model_version": "artifact_registry_v0",
            "artifact_count": 34,
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution_authorized": False,
            "body_ingested": False,
            "metadata_only": True,
            "artifacts": [
                {
                    "artifact_id": "helm_state_json_export",
                    "path_or_command": "generated/read_models/helm_state.json",
                }
            ],
        },
    )
    _write_json(
        root / "generated" / "read_models" / "source_inventory.json",
        {
            "inventory_version": "bounded_source_inventory_v0",
            "summary": {
                "records_total": 21,
                "allowlisted_records": 13,
                "blocked_no_go_examples": 8,
                "blocked_records": 8,
                "body_ingested": False,
                "metadata_only_records": 13,
            },
            "scope": {
                "runtime_activation": False,
                "agent_activation": False,
                "broker_connection": False,
                "customer_deployment": False,
                "hard_drive_scan": False,
                "sqlite_touched": False,
                "whole_repo_scan": False,
            },
            "records": [],
        },
    )
    _write_json(
        root / "generated" / "read_models" / "evidence_freshness.json",
        {
            "read_model_version": "evidence_freshness_v0",
            "artifact_count": 9,
            "freshness_counts": {
                "current": 9,
                "stale": 0,
                "missing": 0,
                "unknown": 0,
            },
            "generated_status_current": True,
            "read_model_exports_current": True,
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution_authorized": False,
            "body_ingested": False,
            "artifacts": [
                {
                    "artifact_id": "helm_state",
                    "path": "generated/read_models/helm_state.json",
                    "freshness_state": "current",
                    "basis": "fixture",
                }
            ],
        },
    )
    (root / "generated" / "read_models" / "generated_current_state.md").write_text(
        "# Generated current state\n",
        encoding="utf-8",
    )
    (root / "generated" / "read_models" / "generated_next_actions.md").write_text(
        "# Generated next actions\n",
        encoding="utf-8",
    )
    return root


def _run_atlas(tmp_path: Path):
    root = _sample_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    atlas_hashed = []

    def hash_reader(path: Path) -> str:
        rel = path.relative_to(root).as_posix()
        atlas_hashed.append(rel)
        assert not rel.startswith(".ssh")
        return "hash-" + rel.replace("/", "_")

    result = run_corpus_atlas(
        db_path=db_path,
        root=root,
        run_id="atlas_fixture",
        hash_reader=hash_reader,
    )
    return root, db_path, result


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def test_evidence_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "evidence_ingestion_runs",
        "evidence_sources",
        "evidence_items",
        "evidence_item_labels",
        "evidence_world_bindings",
        "evidence_source_links",
        "read_model_snapshots",
    } <= set(evidence_table_names(db_path))


def test_plan_uses_only_explicitly_eligible_sources(tmp_path):
    _, db_path, result = _run_atlas(tmp_path)

    plan = plan_evidence_ingestion(db_path=db_path, atlas_run_id=result.run_id)

    assert plan["source_count"] == 15
    assert plan["counts"]["included_ingestion_eligibility"] == {
        "generated_snapshot_only": 9,
        "ingest_allowed": 4,
        "receipt_summary_only": 2,
    }
    assert "needs_review" in plan["counts"]["excluded_ingestion_eligibility"]
    assert not any(source["relative_path"] == "loose.unknown" for source in plan["sample_sources"])


def test_ingestion_records_snapshots_without_reading_no_go_or_receipts(tmp_path):
    root, db_path, result = _run_atlas(tmp_path)
    read_paths = []

    def file_reader(path: Path) -> bytes:
        rel = path.relative_to(root).as_posix()
        read_paths.append(rel)
        assert rel.startswith("generated/read_models/")
        assert not rel.startswith(".ssh")
        assert not rel.startswith("execution_receipts/")
        return path.read_bytes()

    ingestion = run_evidence_kettle(
        db_path=db_path,
        root=root,
        atlas_run_id=result.run_id,
        ingestion_run_id="ek_fixture",
        file_reader=file_reader,
    )

    assert ingestion.source_count == 15
    assert ingestion.snapshot_count == 9
    assert ingestion.receipt_summary_count == 2
    assert len(read_paths) == 9
    assert _row(
        db_path,
        "SELECT COUNT(*) FROM evidence_sources WHERE ingestion_run_id = ? AND ingestion_eligibility IN ('needs_review','no_go','metadata_only','not_for_ingestion')",
        (ingestion.ingestion_run_id,),
    )[0] == 0
    assert _row(
        db_path,
        "SELECT body_ingested, raw_sensitive_data_stored, runtime_authority, activation_allowed FROM evidence_ingestion_runs WHERE ingestion_run_id = ?",
        (ingestion.ingestion_run_id,),
    ) == (0, 0, 0, 0)


def test_generated_read_model_facts_are_extracted_without_truth_promotion(tmp_path):
    root, db_path, result = _run_atlas(tmp_path)
    ingestion = run_evidence_kettle(
        db_path=db_path,
        root=root,
        atlas_run_id=result.run_id,
        ingestion_run_id="ek_fixture",
    )

    item_map = {
        (row[0], row[1]): json.loads(row[2])
        for row in _rows(
            db_path,
            """
SELECT evidence_category, evidence_key, evidence_value_json
FROM evidence_items
WHERE ingestion_run_id = ?
""",
            (ingestion.ingestion_run_id,),
        )
    }
    worlds = {
        row[0]
        for row in _rows(
            db_path,
            """
SELECT DISTINCT world_id
FROM evidence_world_bindings wb
JOIN evidence_items ei ON ei.evidence_id = wb.evidence_id
WHERE ei.ingestion_run_id = ?
""",
            (ingestion.ingestion_run_id,),
        )
    }

    assert item_map[("helm_state", "helm_state")] == "inspect_only"
    assert item_map[("runtime_gate", "runtime_authority")] is False
    assert item_map[("runtime_gate", "activation_allowed")] is False
    assert item_map[("artifact_registry", "artifact_count")] == 34
    assert item_map[("source_inventory", "source_inventory:records_total")] == 21
    assert item_map[("evidence_freshness", "freshness_count:current")] == 9
    assert set(WORLD_IDS) <= worlds
    assert _row(db_path, "SELECT COUNT(*) FROM canonical_facts")[0] == 0
    assert _row(
        db_path,
        "SELECT COUNT(*) FROM evidence_items WHERE truth_claimed != 0 OR runtime_authority != 0",
    )[0] == 0


def test_receipt_summaries_are_metadata_only(tmp_path):
    root, db_path, result = _run_atlas(tmp_path)
    ingestion = run_evidence_kettle(
        db_path=db_path,
        root=root,
        atlas_run_id=result.run_id,
        ingestion_run_id="ek_fixture",
    )

    rows = _rows(
        db_path,
        """
SELECT evidence_label, evidence_value_json, summary
FROM evidence_items
WHERE ingestion_run_id = ?
  AND evidence_label IN ('receipt_summary','verification_evidence')
ORDER BY evidence_label
""",
        (ingestion.ingestion_run_id,),
    )
    combined = "\n".join(row[1] + row[2] for row in rows)

    assert {row[0] for row in rows} == {"receipt_summary", "verification_evidence"}
    assert "receipt body should not be stored" not in combined
    assert "verification body should not be stored" not in combined
    assert all(json.loads(row[1])["body_ingested"] is False for row in rows)


def test_reports_cover_required_views(tmp_path, capsys):
    root, db_path, result = _run_atlas(tmp_path)
    ingestion = run_evidence_kettle(
        db_path=db_path,
        root=root,
        atlas_run_id=result.run_id,
        ingestion_run_id="ek_fixture",
    )

    report = build_evidence_report(db_path=db_path, ingestion_run_id=ingestion.ingestion_run_id)
    world = query_evidence_report_section(
        db_path=db_path,
        ingestion_run_id=ingestion.ingestion_run_id,
        section="world",
        world="build",
    )
    read_models = query_evidence_report_section(
        db_path=db_path,
        ingestion_run_id=ingestion.ingestion_run_id,
        section="read-models",
    )
    future_gated = query_evidence_report_section(
        db_path=db_path,
        ingestion_run_id=ingestion.ingestion_run_id,
        section="future-gated",
    )
    runtime_gate = query_evidence_report_section(
        db_path=db_path,
        ingestion_run_id=ingestion.ingestion_run_id,
        section="runtime-gate",
    )
    receipts = query_evidence_report_section(
        db_path=db_path,
        ingestion_run_id=ingestion.ingestion_run_id,
        section="receipts",
    )

    assert report["counts"]["evidence_label"]["generated_read_model_fact"] >= 1
    assert len(read_models["items"]) == 9
    assert any(item["world_id"] == "build" for item in world["items"])
    assert any("explicit_operator_approval" in item["evidence_key"] for item in future_gated["items"])
    assert any(item["evidence_key"] == "activation_allowed" for item in runtime_gate["items"])
    assert len(receipts["items"]) == 2

    exit_code = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            ingestion.ingestion_run_id,
            "--report",
            "runtime-gate",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["section"] == "runtime-gate"

    summary_exit_code = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            ingestion.ingestion_run_id,
            "--report",
            "summary",
            "--format",
            "operator",
        ]
    )
    summary_output = capsys.readouterr().out
    assert summary_exit_code == 0
    assert "Evidence Kettle v0.1" in summary_output
