import json
import sqlite3
from pathlib import Path

from corpus_atlas import (
    DEFAULT_ROOT_ID,
    WORLD_BINDINGS,
    build_atlas_report,
    corpus_table_names,
    query_report_section,
    run_corpus_atlas,
)
from scripts.query_corpus_atlas import main as query_main


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
    (root / "docs" / "operations").mkdir(parents=True)
    (root / "docs" / "operations" / "OPENCLAW_CURRENT_EVIDENCE_COVERAGE_AUDIT.md").write_text(
        "# Old audit\n",
        encoding="utf-8",
    )
    (root / "docs" / "operations" / "OPENCLAW_GENERIC_RECEIPT_SPINE_V0.md").write_text(
        "# Receipt spine\n",
        encoding="utf-8",
    )
    (root / "CURRENT_STATE.md").write_text("# Legacy state\n", encoding="utf-8")
    (root / "NEXT_ACTIONS.md").write_text("# Legacy next actions\n", encoding="utf-8")
    (root / "OPENCLAW_RUNTIME.md").write_text("# Runtime law\n", encoding="utf-8")
    (root / "business_ops_ledger.py").write_text("DEFAULT_DB_PATH = 'x'\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / "build_source_inventory.py").write_text("print('metadata')\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_source_inventory.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (root / ".ssh").mkdir()
    (root / ".ssh" / "id_rsa").write_text("secret fixture should not be read\n", encoding="utf-8")
    (root / ".chief.env").write_text("TOKEN=secret fixture should not be read\n", encoding="utf-8")
    (root / "finance").mkdir()
    (root / "finance" / "ledger.txt").write_text("finance fixture should not be read\n", encoding="utf-8")
    (root / "OpenClaw").mkdir()
    (root / "OpenClaw" / "old.md").write_text("# old\n", encoding="utf-8")
    (root / "077").mkdir()
    (root / "077" / "scratch.txt").write_text("scratch\n", encoding="utf-8")

    _write_json(
        root / "generated" / "read_models" / "world_domain_registry.json",
        {
            "read_model_version": "world_domain_registry_v0",
            "worlds": [{"world_id": world_id} for world_id in WORLD_IDS],
        },
    )
    _write_json(
        root / "generated" / "read_models" / "evidence_freshness.json",
        {
            "artifacts": [
                {
                    "artifact_id": "world_domain_registry",
                    "path": "generated/read_models/world_domain_registry.json",
                    "freshness_state": "current",
                    "basis": "export_check",
                    "body_ingested": False,
                },
                {
                    "artifact_id": "source_inventory",
                    "path": "generated/read_models/source_inventory.json",
                    "freshness_state": "current",
                    "basis": "export_check",
                    "body_ingested": False,
                },
            ]
        },
    )
    _write_json(
        root / "generated" / "read_models" / "artifact_registry.json",
        {
            "artifacts": [
                {
                    "artifact_id": "world_domain_registry_json_export",
                    "artifact_type": "standardized_export_path",
                    "path_or_command": "generated/read_models/world_domain_registry.json",
                }
            ]
        },
    )
    _write_json(
        root / "generated" / "read_models" / "source_inventory.json",
        {
            "records": [
                {
                    "path": "docs/operations/OPENCLAW_GENERIC_RECEIPT_SPINE_V0.md",
                    "source_class": "receipt_spine_doctrine",
                    "body_ingested": False,
                }
            ]
        },
    )
    for name in (
        "helm_state.json",
        "world_status.json",
        "runtime_activation_gate.json",
    ):
        _write_json(root / "generated" / "read_models" / name, {})
    return root


def _run(tmp_path, *, run_id="test_run"):
    root = _sample_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    hashed = []

    def hash_reader(path: Path) -> str:
        rel = path.relative_to(root).as_posix()
        hashed.append(rel)
        assert not rel.startswith(".ssh")
        assert not rel.startswith("finance")
        assert rel != ".chief.env"
        return "hash-" + rel.replace("/", "_")

    result = run_corpus_atlas(
        db_path=db_path,
        root=root,
        run_id=run_id,
        hash_reader=hash_reader,
    )
    return root, db_path, result, hashed


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_schema_initializes_corpus_namespace(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    tables = set(corpus_table_names(db_path))

    assert {
        "corpus_roots",
        "corpus_paths",
        "corpus_path_labels",
        "corpus_world_bindings",
        "corpus_artifact_links",
        "corpus_freshness_signals",
        "corpus_sensitivity_labels",
        "corpus_reorg_candidates",
        "corpus_mirror_candidates",
        "corpus_atlas_runs",
    } <= tables


def test_atlas_run_records_provenance_and_no_runtime_authority(tmp_path):
    _, db_path, result, _ = _run(tmp_path)

    row = _row(
        db_path,
        """
SELECT root_id, atlas_version, path_count, runtime_authority, activation_allowed,
       backend_execution_authorized, body_ingested, raw_sensitive_data_stored
FROM corpus_atlas_runs
WHERE run_id = ?
""",
        (result.run_id,),
    )

    assert row[0] == DEFAULT_ROOT_ID
    assert row[1] == "corpus_atlas_v0_5"
    assert row[2] == result.path_count
    assert row[3:] == (0, 0, 0, 0, 0)


def test_no_go_paths_are_registered_without_hashing_or_descent(tmp_path):
    _, db_path, _, hashed = _run(tmp_path)

    rows = _rows(
        db_path,
        """
SELECT relative_path, raw_content_eligibility, sensitivity_label, content_hash
FROM corpus_paths
WHERE relative_path IN ('.ssh', '.chief.env', 'finance')
ORDER BY relative_path
""",
    )
    by_path = {row[0]: row for row in rows}

    assert by_path[".ssh"][1:] == ("no_go", "credential_boundary", None)
    assert by_path[".chief.env"][1:] == ("no_go", "credential_boundary", None)
    assert by_path["finance"][1:] == ("no_go", "finance_boundary", None)
    assert ".ssh/id_rsa" not in {row[0] for row in _rows(db_path, "SELECT relative_path FROM corpus_paths")}
    assert all(not path.startswith((".ssh", "finance")) for path in hashed)


def test_generated_read_models_are_classified_and_linked(tmp_path):
    _, db_path, _, _ = _run(tmp_path)

    row = _row(
        db_path,
        """
SELECT source_role, freshness_label, raw_content_eligibility, content_hash
FROM corpus_paths
WHERE relative_path = 'generated/read_models/world_domain_registry.json'
""",
    )
    link_count = _row(db_path, "SELECT COUNT(*) FROM corpus_artifact_links")[0]
    freshness_count = _row(db_path, "SELECT COUNT(*) FROM corpus_freshness_signals")[0]

    assert row == ("generated_read_model", "generated_current", "eligible", "hash-generated_read_models_world_domain_registry.json")
    assert link_count >= 1
    assert freshness_count >= 1


def test_known_stale_and_historical_candidates_are_labeled(tmp_path):
    _, db_path, _, _ = _run(tmp_path)

    labels = dict(
        _rows(
            db_path,
            """
SELECT relative_path, freshness_label
FROM corpus_paths
WHERE relative_path IN (
  'CURRENT_STATE.md',
  'NEXT_ACTIONS.md',
  'docs/operations/OPENCLAW_CURRENT_EVIDENCE_COVERAGE_AUDIT.md',
  'OpenClaw'
)
""",
        )
    )

    assert labels["CURRENT_STATE.md"] == "stale_possible"
    assert labels["NEXT_ACTIONS.md"] == "stale_possible"
    assert labels["docs/operations/OPENCLAW_CURRENT_EVIDENCE_COVERAGE_AUDIT.md"] == "stale_possible"
    assert labels["OpenClaw"] == "historical"


def test_duplicate_run_dedupes_paths_by_root_path_run(tmp_path):
    root = _sample_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"

    first = run_corpus_atlas(db_path=db_path, root=root, run_id="same_run")
    second = run_corpus_atlas(db_path=db_path, root=root, run_id="same_run")
    count = _row(db_path, "SELECT COUNT(*) FROM corpus_paths WHERE run_id = 'same_run'")[0]

    assert first.path_count == second.path_count
    assert count == first.path_count


def test_safe_eligible_files_receive_hashes_and_no_go_files_do_not(tmp_path):
    _, db_path, _, _ = _run(tmp_path)

    safe_hash = _row(
        db_path,
        "SELECT content_hash FROM corpus_paths WHERE relative_path = 'docs/operations/OPENCLAW_GENERIC_RECEIPT_SPINE_V0.md'",
    )[0]
    no_go_hash = _row(db_path, "SELECT content_hash FROM corpus_paths WHERE relative_path = '.chief.env'")[0]

    assert safe_hash == "hash-docs_operations_OPENCLAW_GENERIC_RECEIPT_SPINE_V0.md"
    assert no_go_hash is None


def test_all_eight_worlds_can_be_represented_as_bindings(tmp_path):
    _, db_path, _, _ = _run(tmp_path)

    world_ids = {
        row[0]
        for row in _rows(
            db_path,
            """
SELECT DISTINCT world_id
FROM corpus_world_bindings
WHERE world_id NOT IN ('unknown', 'no_world', 'cross_world')
""",
        )
    }

    assert set(WORLD_IDS) <= world_ids
    assert world_ids <= WORLD_BINDINGS


def test_reorg_candidates_are_advisory_and_do_not_move_files(tmp_path):
    root, db_path, _, _ = _run(tmp_path)

    row = _row(
        db_path,
        """
SELECT suggested_bucket, candidate_action, advisory_only, moved, c.requires_operator_review
FROM corpus_reorg_candidates c
JOIN corpus_paths p ON p.path_id = c.path_id
WHERE p.relative_path = 'OpenClaw'
""",
    )

    assert row == ("scratch_archive", "classify_only_no_filesystem_change", 1, 0, 1)
    assert (root / "OpenClaw").is_dir()
    assert (root / ".ssh" / "id_rsa").is_file()


def test_report_includes_required_count_groups_and_query_sections(tmp_path, capsys):
    _, db_path, result, _ = _run(tmp_path)

    report = build_atlas_report(db_path=db_path, run_id=result.run_id)
    for key in (
        "source_role",
        "freshness_label",
        "sensitivity_label",
        "raw_content_eligibility",
        "world_binding",
        "reorg_bucket",
    ):
        assert key in report["counts"]
        assert report["counts"][key]

    no_go = query_report_section(db_path=db_path, run_id=result.run_id, section="no-go")
    generated = query_report_section(db_path=db_path, run_id=result.run_id, section="generated-read-models")
    stale = query_report_section(db_path=db_path, run_id=result.run_id, section="stale")
    reorg = query_report_section(db_path=db_path, run_id=result.run_id, section="reorg")

    assert any(item["relative_path"] == ".chief.env" for item in no_go["items"])
    assert any(item["relative_path"].startswith("generated/read_models/") for item in generated["items"])
    assert any(item["relative_path"] == "CURRENT_STATE.md" for item in stale["items"])
    assert any(item["relative_path"] == "OpenClaw" for item in reorg["items"])

    exit_code = query_main(
        ["--db", str(db_path), "--run-id", result.run_id, "--report", "no-go", "--format", "json"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["section"] == "no-go"
