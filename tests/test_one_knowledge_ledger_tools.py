from __future__ import annotations

import sqlite3
from pathlib import Path


def test_system_catalog_ingest_dedupes_worktrees_and_requires_confirm(tmp_path: Path) -> None:
    from scripts.ingest_system_catalog_to_ledger import ingest_system_catalog_to_ledger

    catalog = tmp_path / "system_catalog.sqlite3"
    ledger = tmp_path / "ledger.sqlite"
    conn = sqlite3.connect(catalog)
    conn.executescript(
        """
        CREATE TABLE repos (
            repo_path TEXT,
            repo_name TEXT,
            remote_url TEXT,
            branch TEXT,
            head_commit TEXT,
            is_worktree INTEGER
        );
        INSERT INTO repos VALUES
          ('/home/openclaw', 'openclaw', 'git@example/openclaw.git', 'main', 'abc', 0),
          ('/home/openclaw/worktrees/a', 'openclaw', 'git@example/openclaw.git', 'topic', 'def', 1),
          ('/home/other', 'other', 'git@example/other.git', 'main', '123', 0);
        """
    )
    conn.commit()
    conn.close()

    dry = ingest_system_catalog_to_ledger(catalog, ledger, confirm=False)
    assert dry["status"] == "operator_confirmation_required"
    assert not ledger.exists()

    written = ingest_system_catalog_to_ledger(catalog, ledger, confirm=True)
    assert written["status"] == "written"
    assert written["deduped_repo_count"] == 2
    conn = sqlite3.connect(ledger)
    try:
        count = conn.execute("SELECT count(*) FROM knowledge_repo_roots").fetchone()[0]
    finally:
        conn.close()
    assert count == 2


def test_reconcile_satellites_reports_table_overlap_without_writing(tmp_path: Path) -> None:
    from scripts.reconcile_knowledge_satellites import reconcile_satellite

    ledger = tmp_path / "ledger.sqlite"
    satellite = tmp_path / "satellite.sqlite"
    sqlite3.connect(ledger).executescript(
        "CREATE TABLE corpus_paths (path_id TEXT); CREATE TABLE agent_lanes (agent_id TEXT);"
    )
    sqlite3.connect(satellite).executescript(
        "CREATE TABLE corpus_paths (path_id TEXT); CREATE TABLE unique_semantic_layer (id TEXT);"
    )

    report = reconcile_satellite(ledger_path=ledger, satellite_path=satellite)

    assert report["status"] == "read_only_diff"
    assert report["table_count"] == 2
    assert report["tables"]["corpus_paths"]["classification"] == "already_present"
    assert report["tables"]["unique_semantic_layer"]["classification"] == "unique_fold_in"


def test_hermes_inventory_exporter_uses_ledger_not_system_catalog(tmp_path: Path) -> None:
    from scripts.export_hermes_inventory_from_ledger import build_hermes_inventory_markdown

    ledger = tmp_path / "ledger.sqlite"
    conn = sqlite3.connect(ledger)
    conn.executescript(
        """
        CREATE TABLE agent_lanes (
            agent_id TEXT PRIMARY KEY,
            display_name TEXT,
            lane_id TEXT,
            lane_label TEXT,
            status TEXT,
            authority_level TEXT,
            role_summary TEXT,
            updated_at TEXT
        );
        CREATE TABLE corpus_roots (
            root_id TEXT PRIMARY KEY,
            host_kind TEXT,
            absolute_root TEXT,
            root_label TEXT,
            status TEXT,
            updated_at TEXT,
            repo_name TEXT,
            canonical_status TEXT
        );
        CREATE TABLE module_registry_modules (
            module_id TEXT PRIMARY KEY,
            display_name TEXT,
            name TEXT,
            status TEXT,
            authority_level TEXT,
            description TEXT,
            updated_at TEXT
        );
        INSERT INTO agent_lanes VALUES
          ('hermes', 'Hermes', 'advisory_systems', 'Advisory Systems', 'active', 'advisory_only', 'Advises only.', '2026-06-29');
        INSERT INTO corpus_roots VALUES
          ('root_openclaw', 'wsl', '/home/openclaw', 'OpenClaw', 'active', '2026-06-29', 'openclaw', 'canonical_current');
        INSERT INTO module_registry_modules VALUES
          ('corpus_atlas', 'Corpus Atlas', 'Corpus Atlas', 'available', 'metadata_only', 'Metadata atlas.', '2026-06-29');
        """
    )
    conn.commit()
    conn.close()

    text = build_hermes_inventory_markdown(ledger_path=ledger)

    assert "ledger.sqlite" in text
    assert "system_catalog.sqlite3" not in text
    assert "Hermes" in text
    assert "Corpus Atlas" in text


def test_governance_policy_record_is_gated(tmp_path: Path) -> None:
    from sqlite_governance_registry import record_one_knowledge_ledger_policy

    registry = tmp_path / "sqlite_governance_registry.sqlite"
    ledger = tmp_path / "ledger.sqlite"

    pending = record_one_knowledge_ledger_policy(
        registry_sqlite_path=registry,
        ledger_path=ledger,
        confirm=False,
    )
    assert pending["status"] == "operator_confirmation_required"
    assert not registry.exists()

    written = record_one_knowledge_ledger_policy(
        registry_sqlite_path=registry,
        ledger_path=ledger,
        confirm=True,
    )
    assert written["status"] == "written"

    conn = sqlite3.connect(registry)
    try:
        row = conn.execute(
            "SELECT policy_status, ledger_path FROM knowledge_sqlite_policies WHERE policy_id=?",
            ("one_knowledge_ledger",),
        ).fetchone()
    finally:
        conn.close()

    assert row == ("active", str(ledger))
