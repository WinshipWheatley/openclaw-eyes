"""Regression tests for evidence-registry pilot schema constraints.

T001 — permanent regression suite.
Uses temporary SQLite databases only. Never touches production data.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ar_counterparty_contact_operations as ar_ops


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_conn(tmp_path: Path) -> sqlite3.Connection:
    """Return a connection to a fresh temporary database with full schema."""
    db = tmp_path / "pilot_test.sqlite"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ar_ops.ensure_schema(conn)
    return conn


def _seed_account(conn: sqlite3.Connection, account_id: str = "acct:test:001") -> str:
    """Insert a minimal ar_counterparty_accounts row and return its account_id."""
    import json
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO ar_counterparty_accounts
          (account_id, account_label, status, created_at, updated_at, account_json)
        VALUES (?, ?, 'active', ?, ?, ?)
        """,
        (account_id, "Test Account", now, now, json.dumps({"account_id": account_id})),
    )
    conn.commit()
    return account_id


def _seed_evidence(
    conn: sqlite3.Connection,
    account_id: str,
    evidence_id: str = "ev:001",
    source_system: str = "synthetic",
    source_event: str = "evt:001",
    source_locator: str = "loc:001",
    evidence_hash: str = "deadbeef00000001",
) -> str:
    """Insert a minimal ar_evidence_registry row and return its evidence_id."""
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO ar_evidence_registry (
          evidence_id, account_id, source_system, source_event, source_locator,
          evidence_hash, governed_artifact_path, world, governance_status,
          processing_status, availability, first_seen_timestamp, ingestion_timestamp,
          extractor_version, schema_version, source_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 'pending', 'available', ?, ?, '0.1', '1', ?)
        """,
        (
            evidence_id, account_id, source_system, source_event, source_locator,
            evidence_hash,
            f"/governed/artifacts/{evidence_id}.bin",
            "test-world", now, now,
            f"ref:{evidence_id}",
        ),
    )
    conn.commit()
    return evidence_id


def _seed_run(
    conn: sqlite3.Connection,
    run_id: str = "run:001",
    status: str = "published",
) -> str:
    """Insert a minimal ar_materialization_runs row and return its run_id."""
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO ar_materialization_runs (
          run_id, generator_id, generator_version, schema_version,
          run_start_timestamp, freshness_cutoff, status
        ) VALUES (?, 'gen:test', '0.1', '1', ?, ?, ?)
        """,
        (run_id, now, now, status),
    )
    conn.commit()
    return run_id


# ---------------------------------------------------------------------------
# 1. Schema creation — all four pilot tables and triggers exist
# ---------------------------------------------------------------------------

def test_pilot_tables_created_by_ensure_schema(tmp_path):
    """ensure_schema() must create all four pilot tables."""
    conn = _tmp_conn(tmp_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {
        "ar_evidence_registry",
        "ar_materialization_runs",
        "ar_materialization_run_evidence",
        "ar_published_read_models",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_pilot_triggers_created_by_ensure_schema(tmp_path):
    """ensure_schema() must create both publication-guard triggers."""
    conn = _tmp_conn(tmp_path)
    triggers = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    assert "enforce_published_read_model" in triggers
    assert "enforce_published_read_model_update" in triggers


# ---------------------------------------------------------------------------
# 2. Foreign-key enforcement is ON
# ---------------------------------------------------------------------------

def test_foreign_keys_pragma_is_on(tmp_path):
    """PRAGMA foreign_keys must be ON after _connect() path is used."""
    conn = _tmp_conn(tmp_path)
    result = conn.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1, "foreign_keys pragma must be 1 (ON)"


def test_evidence_registry_rejects_unknown_account_fk(tmp_path):
    """ar_evidence_registry must reject evidence for a non-existent account."""
    conn = _tmp_conn(tmp_path)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_evidence_registry (
              evidence_id, account_id, source_system, source_event, source_locator,
              evidence_hash, governed_artifact_path, world, governance_status,
              processing_status, availability, first_seen_timestamp, ingestion_timestamp,
              extractor_version, schema_version, source_reference
            ) VALUES (
              'ev:fk-fail', 'acct:nonexistent', 'sys', 'evt', 'loc',
              'hash001', '/gov/art/fk-fail.bin', 'world',
              'active', 'pending', 'available', ?, ?, '0.1', '1', 'ref:fk-fail'
            )
            """,
            (now, now),
        )


def test_run_evidence_rejects_unknown_run_fk(tmp_path):
    """ar_materialization_run_evidence must reject a non-existent run_id FK."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    ev = _seed_evidence(conn, acct)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_materialization_run_evidence
              (run_id, evidence_id, inclusion_status)
            VALUES ('run:nonexistent', ?, 'used')
            """,
            (ev,),
        )


def test_run_evidence_rejects_unknown_evidence_fk(tmp_path):
    """ar_materialization_run_evidence must reject a non-existent evidence_id FK."""
    conn = _tmp_conn(tmp_path)
    run = _seed_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_materialization_run_evidence
              (run_id, evidence_id, inclusion_status)
            VALUES (?, 'ev:nonexistent', 'used')
            """,
            (run,),
        )


def test_published_read_model_rejects_unknown_run_fk(tmp_path):
    """ar_published_read_models must reject a non-existent run FK."""
    conn = _tmp_conn(tmp_path)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO ar_published_read_models VALUES ('domain:test', 'run:nonexistent', ?)",
            (now,),
        )


# ---------------------------------------------------------------------------
# 3. CHECK constraints
# ---------------------------------------------------------------------------

def test_evidence_governance_status_check(tmp_path):
    """ar_evidence_registry must reject invalid governance_status values."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_evidence_registry (
              evidence_id, account_id, source_system, source_event, source_locator,
              evidence_hash, governed_artifact_path, world, governance_status,
              processing_status, availability, first_seen_timestamp, ingestion_timestamp,
              extractor_version, schema_version, source_reference
            ) VALUES (
              'ev:bad-gov', ?, 'sys', 'evt', 'loc', 'hash001', '/gov/art.bin',
              'world', 'deleted', 'pending', 'available', ?, ?, '0.1', '1', 'ref'
            )
            """,
            (acct, now, now),
        )


def test_evidence_processing_status_check(tmp_path):
    """ar_evidence_registry must reject invalid processing_status values."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_evidence_registry (
              evidence_id, account_id, source_system, source_event, source_locator,
              evidence_hash, governed_artifact_path, world, governance_status,
              processing_status, availability, first_seen_timestamp, ingestion_timestamp,
              extractor_version, schema_version, source_reference
            ) VALUES (
              'ev:bad-proc', ?, 'sys', 'evt', 'loc', 'hash002', '/gov/art.bin',
              'world', 'active', 'processing', 'available', ?, ?, '0.1', '1', 'ref'
            )
            """,
            (acct, now, now),
        )


def test_evidence_availability_check(tmp_path):
    """ar_evidence_registry must reject invalid availability values."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_evidence_registry (
              evidence_id, account_id, source_system, source_event, source_locator,
              evidence_hash, governed_artifact_path, world, governance_status,
              processing_status, availability, first_seen_timestamp, ingestion_timestamp,
              extractor_version, schema_version, source_reference
            ) VALUES (
              'ev:bad-avail', ?, 'sys', 'evt', 'loc', 'hash003', '/gov/art.bin',
              'world', 'active', 'pending', 'unknown', ?, ?, '0.1', '1', 'ref'
            )
            """,
            (acct, now, now),
        )


def test_materialization_run_status_check(tmp_path):
    """ar_materialization_runs must reject invalid status values."""
    conn = _tmp_conn(tmp_path)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_materialization_runs (
              run_id, generator_id, generator_version, schema_version,
              run_start_timestamp, freshness_cutoff, status
            ) VALUES ('run:bad-status', 'gen:test', '0.1', '1', ?, ?, 'running')
            """,
            (now, now),
        )


def test_run_evidence_inclusion_status_check(tmp_path):
    """ar_materialization_run_evidence must reject invalid inclusion_status values."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    ev = _seed_evidence(conn, acct)
    run = _seed_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_materialization_run_evidence
              (run_id, evidence_id, inclusion_status)
            VALUES (?, ?, 'ignored')
            """,
            (run, ev),
        )


# ---------------------------------------------------------------------------
# 4. UNIQUE constraint on ar_evidence_registry
# ---------------------------------------------------------------------------

def test_evidence_unique_composite_key(tmp_path):
    """ar_evidence_registry must reject duplicate (source_system, source_event, source_locator, evidence_hash)."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(
        conn, acct,
        evidence_id="ev:orig",
        source_system="sys", source_event="evt", source_locator="loc",
        evidence_hash="hash:unique:001",
    )
    with pytest.raises(sqlite3.IntegrityError):
        _seed_evidence(
            conn, acct,
            evidence_id="ev:dup",  # different PK
            source_system="sys", source_event="evt", source_locator="loc",
            evidence_hash="hash:unique:001",  # same composite → must fail
        )


def test_evidence_different_hash_is_allowed(tmp_path):
    """ar_evidence_registry must allow same (sys, evt, loc) with different hash."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(
        conn, acct,
        evidence_id="ev:v1",
        evidence_hash="hash:v1",
    )
    # Different hash → no UNIQUE violation
    _seed_evidence(
        conn, acct,
        evidence_id="ev:v2",
        evidence_hash="hash:v2",
    )
    count = conn.execute(
        "SELECT COUNT(*) FROM ar_evidence_registry WHERE account_id = ?", (acct,)
    ).fetchone()[0]
    assert count == 2


# ---------------------------------------------------------------------------
# 5. Supersession self-reference
# ---------------------------------------------------------------------------

def test_evidence_supersession_self_reference(tmp_path):
    """supersedes_evidence_id must accept a valid FK back into the same table."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:base", evidence_hash="hash:base")
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO ar_evidence_registry (
          evidence_id, account_id, source_system, source_event, source_locator,
          evidence_hash, governed_artifact_path, world, governance_status,
          processing_status, availability, first_seen_timestamp, ingestion_timestamp,
          extractor_version, schema_version, source_reference, supersedes_evidence_id
        ) VALUES (
          'ev:superseding', ?, 'synthetic', 'evt:001', 'loc:001',
          'hash:superseding', '/gov/art/superseding.bin',
          'test-world', 'active', 'pending', 'available', ?, ?, '0.1', '1',
          'ref:superseding', 'ev:base'
        )
        """,
        (acct, now, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT supersedes_evidence_id FROM ar_evidence_registry WHERE evidence_id = 'ev:superseding'"
    ).fetchone()
    assert row["supersedes_evidence_id"] == "ev:base"


def test_evidence_supersession_rejects_nonexistent_parent(tmp_path):
    """supersedes_evidence_id must reject a reference to a non-existent evidence_id."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO ar_evidence_registry (
              evidence_id, account_id, source_system, source_event, source_locator,
              evidence_hash, governed_artifact_path, world, governance_status,
              processing_status, availability, first_seen_timestamp, ingestion_timestamp,
              extractor_version, schema_version, source_reference, supersedes_evidence_id
            ) VALUES (
              'ev:orphan', ?, 'synthetic', 'evt:001', 'loc:001',
              'hash:orphan', '/gov/art/orphan.bin',
              'test-world', 'active', 'pending', 'available', ?, ?, '0.1', '1',
              'ref:orphan', 'ev:ghost'
            )
            """,
            (acct, now, now),
        )


# ---------------------------------------------------------------------------
# 6. Publication trigger — INSERT guard
# ---------------------------------------------------------------------------

def test_publication_trigger_blocks_non_published_run_on_insert(tmp_path):
    """Trigger must reject INSERT into ar_published_read_models for a 'preparing' run."""
    conn = _tmp_conn(tmp_path)
    run = _seed_run(conn, run_id="run:prep", status="preparing")
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO ar_published_read_models VALUES ('domain:ar', ?, ?)",
            (run, now),
        )


def test_publication_trigger_allows_published_run_on_insert(tmp_path):
    """Trigger must allow INSERT into ar_published_read_models for a 'published' run."""
    conn = _tmp_conn(tmp_path)
    run = _seed_run(conn, run_id="run:pub", status="published")
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        "INSERT INTO ar_published_read_models VALUES ('domain:ar', ?, ?)",
        (run, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT current_run_id FROM ar_published_read_models WHERE read_model_domain = 'domain:ar'"
    ).fetchone()
    assert row["current_run_id"] == run


def test_publication_trigger_blocks_failed_run_on_insert(tmp_path):
    """Trigger must reject INSERT into ar_published_read_models for a 'failed' run."""
    conn = _tmp_conn(tmp_path)
    run = _seed_run(conn, run_id="run:fail", status="failed")
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO ar_published_read_models VALUES ('domain:ar', ?, ?)",
            (run, now),
        )


def test_publication_trigger_blocks_aborted_run_on_insert(tmp_path):
    """Trigger must reject INSERT into ar_published_read_models for an 'aborted' run."""
    conn = _tmp_conn(tmp_path)
    run = _seed_run(conn, run_id="run:abort", status="aborted")
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO ar_published_read_models VALUES ('domain:ar', ?, ?)",
            (run, now),
        )


# ---------------------------------------------------------------------------
# 7. Publication trigger — UPDATE guard
# ---------------------------------------------------------------------------

def test_publication_trigger_blocks_update_to_non_published_run(tmp_path):
    """UPDATE trigger must reject pointing ar_published_read_models at a 'preparing' run."""
    conn = _tmp_conn(tmp_path)
    run_pub = _seed_run(conn, run_id="run:pub-u", status="published")
    run_prep = _seed_run(conn, run_id="run:prep-u", status="preparing")
    now = "2026-01-01T00:00:00+00:00"
    # Legitimate INSERT
    conn.execute(
        "INSERT INTO ar_published_read_models VALUES ('domain:ar', ?, ?)",
        (run_pub, now),
    )
    conn.commit()
    # Attempt to point at a non-published run via UPDATE
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE ar_published_read_models SET current_run_id = ? WHERE read_model_domain = 'domain:ar'",
            (run_prep,),
        )


def test_publication_trigger_allows_update_to_published_run(tmp_path):
    """UPDATE trigger must allow pointing ar_published_read_models at a second 'published' run."""
    conn = _tmp_conn(tmp_path)
    run1 = _seed_run(conn, run_id="run:pub-1", status="published")
    run2 = _seed_run(conn, run_id="run:pub-2", status="published")
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        "INSERT INTO ar_published_read_models VALUES ('domain:ar', ?, ?)",
        (run1, now),
    )
    conn.commit()
    conn.execute(
        "UPDATE ar_published_read_models SET current_run_id = ? WHERE read_model_domain = 'domain:ar'",
        (run2,),
    )
    conn.commit()
    row = conn.execute(
        "SELECT current_run_id FROM ar_published_read_models WHERE read_model_domain = 'domain:ar'"
    ).fetchone()
    assert row["current_run_id"] == run2


# ---------------------------------------------------------------------------
# 8. ar_materialization_run_evidence join constraints
# ---------------------------------------------------------------------------

def test_run_evidence_primary_key_uniqueness(tmp_path):
    """ar_materialization_run_evidence PK must reject duplicate (run_id, evidence_id)."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    ev = _seed_evidence(conn, acct)
    run = _seed_run(conn)
    conn.execute(
        "INSERT INTO ar_materialization_run_evidence VALUES (?, ?, 'used')",
        (run, ev),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO ar_materialization_run_evidence VALUES (?, ?, 'excluded')",
            (run, ev),
        )


def test_run_evidence_valid_insertion(tmp_path):
    """ar_materialization_run_evidence must accept valid 'used' and 'excluded' rows."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    ev1 = _seed_evidence(conn, acct, evidence_id="ev:re-001", evidence_hash="h:re:001")
    ev2 = _seed_evidence(conn, acct, evidence_id="ev:re-002", evidence_hash="h:re:002")
    run = _seed_run(conn)
    conn.execute(
        "INSERT INTO ar_materialization_run_evidence VALUES (?, ?, 'used')", (run, ev1)
    )
    conn.execute(
        "INSERT INTO ar_materialization_run_evidence VALUES (?, ?, 'excluded')", (run, ev2)
    )
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) FROM ar_materialization_run_evidence WHERE run_id = ?", (run,)
    ).fetchone()[0]
    assert count == 2


# ---------------------------------------------------------------------------
# 9. Existing regression suite must still pass (smoke check)
# ---------------------------------------------------------------------------

def test_existing_schema_tables_still_present(tmp_path):
    """Pilot schema additions must not destroy existing core tables."""
    conn = _tmp_conn(tmp_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    pre_existing = {
        "ar_counterparty_accounts",
        "ar_contact_profiles",
        "ar_communication_policies",
        "ar_email_watch_policies",
        "ar_invoice_send_policies",
        "ar_contact_events",
    }
    assert pre_existing.issubset(tables), f"Missing legacy tables: {pre_existing - tables}"


# ---------------------------------------------------------------------------
# T002 — Publication completeness invariant tests
# (enforce_run_publication_completeness trigger)
# A run must not transition to 'published' unless all four fields are non-null:
#   run_completion_timestamp, stable_payload_hash,
#   published_artifact_path, published_artifact_hash
# ---------------------------------------------------------------------------

def _seed_preparing_run(conn: sqlite3.Connection, run_id: str = "run:t002") -> str:
    """Insert a minimal ar_materialization_runs row in 'preparing' state."""
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO ar_materialization_runs (
          run_id, generator_id, generator_version, schema_version,
          run_start_timestamp, freshness_cutoff, status
        ) VALUES (?, 'gen:test', '0.1', '1', ?, ?, 'preparing')
        """,
        (run_id, now, now),
    )
    conn.commit()
    return run_id


def test_t002_publication_completeness_trigger_exists(tmp_path):
    """enforce_run_publication_completeness trigger must be registered by ensure_schema."""
    conn = _tmp_conn(tmp_path)
    triggers = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    assert "enforce_run_publication_completeness" in triggers


def test_t002_blocks_publish_with_no_completeness_fields(tmp_path):
    """Transition to published with all completeness fields NULL must be rejected."""
    conn = _tmp_conn(tmp_path)
    run = _seed_preparing_run(conn)
    with pytest.raises(sqlite3.IntegrityError, match="run_completion_timestamp is required"):
        conn.execute(
            "UPDATE ar_materialization_runs SET status='published' WHERE run_id=?",
            (run,),
        )


def test_t002_blocks_publish_missing_stable_payload_hash(tmp_path):
    """Transition to published with stable_payload_hash NULL must be rejected."""
    conn = _tmp_conn(tmp_path)
    run = _seed_preparing_run(conn)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError, match="stable_payload_hash is required"):
        conn.execute(
            """
            UPDATE ar_materialization_runs
            SET status='published', run_completion_timestamp=?
            WHERE run_id=?
            """,
            (now, run),
        )


def test_t002_blocks_publish_missing_published_artifact_path(tmp_path):
    """Transition to published with published_artifact_path NULL must be rejected."""
    conn = _tmp_conn(tmp_path)
    run = _seed_preparing_run(conn)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError, match="published_artifact_path is required"):
        conn.execute(
            """
            UPDATE ar_materialization_runs
            SET status='published',
                run_completion_timestamp=?,
                stable_payload_hash='abc123'
            WHERE run_id=?
            """,
            (now, run),
        )


def test_t002_blocks_publish_missing_published_artifact_hash(tmp_path):
    """Transition to published with published_artifact_hash NULL must be rejected."""
    conn = _tmp_conn(tmp_path)
    run = _seed_preparing_run(conn)
    now = "2026-01-01T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError, match="published_artifact_hash is required"):
        conn.execute(
            """
            UPDATE ar_materialization_runs
            SET status='published',
                run_completion_timestamp=?,
                stable_payload_hash='abc123',
                published_artifact_path='/gov/art/run.json'
            WHERE run_id=?
            """,
            (now, run),
        )


def test_t002_allows_publish_with_all_completeness_fields(tmp_path):
    """Transition to published with all four fields populated must succeed."""
    conn = _tmp_conn(tmp_path)
    run = _seed_preparing_run(conn)
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        """
        UPDATE ar_materialization_runs
        SET status='published',
            run_completion_timestamp=?,
            stable_payload_hash='abc123',
            published_artifact_path='/gov/art/run.json',
            published_artifact_hash='def456'
        WHERE run_id=?
        """,
        (now, run),
    )
    conn.commit()
    row = conn.execute(
        "SELECT status FROM ar_materialization_runs WHERE run_id=?", (run,)
    ).fetchone()
    assert row["status"] == "published"


def test_t002_trigger_does_not_block_non_published_transitions(tmp_path):
    """Transition to 'failed' or 'aborted' with NULL completeness fields must be allowed."""
    conn = _tmp_conn(tmp_path)
    run1 = _seed_preparing_run(conn, run_id="run:t002-fail")
    run2 = _seed_preparing_run(conn, run_id="run:t002-abort")
    conn.execute(
        "UPDATE ar_materialization_runs SET status='failed' WHERE run_id=?", (run1,)
    )
    conn.execute(
        "UPDATE ar_materialization_runs SET status='aborted' WHERE run_id=?", (run2,)
    )
    conn.commit()
    statuses = {
        row["run_id"]: row["status"]
        for row in conn.execute(
            "SELECT run_id, status FROM ar_materialization_runs WHERE run_id IN (?, ?)",
            (run1, run2),
        ).fetchall()
    }
    assert statuses[run1] == "failed"
    assert statuses[run2] == "aborted"


def test_t002_ar_seed_helper_uses_direct_insert_bypassing_trigger(tmp_path):
    """_seed_run helper uses INSERT (not UPDATE) so it bypasses the UPDATE trigger correctly.
    
    Runs seeded directly with status='published' and no completeness fields are used
    in helper tests; this confirms the trigger only guards UPDATE paths, not INSERT.
    Direct INSERT of a 'published' run without completeness fields IS currently
    allowed by schema (INSERT trigger not yet implemented). This test documents
    that known behavior and confirms the UPDATE path is guarded.
    """
    conn = _tmp_conn(tmp_path)
    # Direct INSERT with status='published' and no completeness fields (legacy helper behavior)
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        """
        INSERT INTO ar_materialization_runs (
          run_id, generator_id, generator_version, schema_version,
          run_start_timestamp, freshness_cutoff, status
        ) VALUES ('run:direct-pub', 'gen:test', '0.1', '1', ?, ?, 'published')
        """,
        (now, now),
    )
    conn.commit()
    # Confirm row exists with NULL completeness fields (INSERT path — not guarded by trigger)
    row = conn.execute(
        "SELECT status, run_completion_timestamp FROM ar_materialization_runs WHERE run_id='run:direct-pub'"
    ).fetchone()
    assert row["status"] == "published"
    assert row["run_completion_timestamp"] is None  # Documents INSERT gap for future T002b


def test_t002_full_combined_suite_count(tmp_path):
    """Smoke test: ensure all tables, triggers are present after T002 trigger addition."""
    conn = _tmp_conn(tmp_path)
    triggers = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    expected_triggers = {
        "enforce_published_read_model",
        "enforce_published_read_model_update",
        "enforce_run_publication_completeness",
    }
    assert expected_triggers.issubset(triggers), f"Missing triggers: {expected_triggers - triggers}"


# ---------------------------------------------------------------------------
# T003 — Governed-artifact path policy tests
# governed_artifact_path(relative_path, governed_root) must enforce:
# 1. No absolute path injection
# 2. No parent-traversal components (..)
# 3. Resolved path contained within governed root
# 4. Symlink escape rejected (via resolve())
# ---------------------------------------------------------------------------

def test_t003_valid_simple_path(tmp_path):
    """A simple relative path inside the governed root must be accepted."""
    result = ar_ops.governed_artifact_path("evidence/abc123.pdf", tmp_path)
    assert result == (tmp_path / "evidence" / "abc123.pdf").resolve()
    assert str(result).startswith(str(tmp_path.resolve()))


def test_t003_valid_nested_path(tmp_path):
    """A valid multi-level relative path inside the governed root must be accepted."""
    result = ar_ops.governed_artifact_path("year/2026/month/06/artifact.json", tmp_path)
    assert result.is_absolute()
    assert str(result).startswith(str(tmp_path.resolve()))


def test_t003_rejects_absolute_path_injection(tmp_path):
    """An absolute path must be rejected regardless of content."""
    with pytest.raises(ValueError, match="absolute path injection"):
        ar_ops.governed_artifact_path("/etc/passwd", tmp_path)


def test_t003_rejects_absolute_path_under_root(tmp_path):
    """Even an absolute path pointing inside the root must be rejected (must be relative)."""
    abs_inside = str(tmp_path / "evidence" / "file.pdf")
    with pytest.raises(ValueError, match="absolute path injection"):
        ar_ops.governed_artifact_path(abs_inside, tmp_path)


def test_t003_rejects_simple_parent_traversal(tmp_path):
    """A path with .. must be rejected before joining."""
    with pytest.raises(ValueError, match="parent-traversal"):
        ar_ops.governed_artifact_path("../outside.pdf", tmp_path)


def test_t003_rejects_embedded_parent_traversal(tmp_path):
    """A path with embedded .. must be rejected."""
    with pytest.raises(ValueError, match="parent-traversal"):
        ar_ops.governed_artifact_path("evidence/../../../etc/passwd", tmp_path)


def test_t003_rejects_dotdot_only(tmp_path):
    """A path consisting only of .. must be rejected."""
    with pytest.raises(ValueError, match="parent-traversal"):
        ar_ops.governed_artifact_path("..", tmp_path)


def test_t003_rejects_empty_path(tmp_path):
    """An empty string must be rejected."""
    with pytest.raises(ValueError):
        ar_ops.governed_artifact_path("", tmp_path)


def test_t003_rejects_whitespace_only_path(tmp_path):
    """A whitespace-only string must be rejected."""
    with pytest.raises(ValueError):
        ar_ops.governed_artifact_path("   ", tmp_path)


def test_t003_rejects_symlink_escape(tmp_path):
    """A symlink that points outside the governed root must be rejected."""
    # Create a symlink inside the root that points outside
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "escape_link"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="path escapes governed root"):
        ar_ops.governed_artifact_path("escape_link/secret.pdf", tmp_path)


def test_t003_valid_symlink_inside_root(tmp_path):
    """A symlink pointing to another location inside the root must be accepted."""
    inner = tmp_path / "inner"
    inner.mkdir()
    target = tmp_path / "real_file.pdf"
    target.write_text("data")
    link = inner / "link_to_real.pdf"
    link.symlink_to(target)
    result = ar_ops.governed_artifact_path("inner/link_to_real.pdf", tmp_path)
    assert str(result).startswith(str(tmp_path.resolve()))


def test_t003_path_does_not_need_to_exist(tmp_path):
    """governed_artifact_path must succeed even for a non-existent path (validate only)."""
    result = ar_ops.governed_artifact_path("not/yet/written/artifact.pdf", tmp_path)
    assert not result.exists()
    assert str(result).startswith(str(tmp_path.resolve()))


def test_t003_return_type_is_path(tmp_path):
    """governed_artifact_path must return a pathlib.Path object."""
    result = ar_ops.governed_artifact_path("ev/test.bin", tmp_path)
    assert isinstance(result, Path)


def test_t003_root_as_string(tmp_path):
    """governed_artifact_path must accept governed_root as a string."""
    result = ar_ops.governed_artifact_path("ev/test.bin", str(tmp_path))
    assert isinstance(result, Path)
    assert str(result).startswith(str(tmp_path.resolve()))


# ---------------------------------------------------------------------------
# T004 — Hashing and object-path util tests
# sha256_hex(data: bytes) -> str
# object_path(digest_hex: str) -> str
# ---------------------------------------------------------------------------

# Known SHA-256 test vector: sha256("") == e3b0c44298fc1c14...
_SHA256_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
# Known vector: sha256("hello") == 2cf24dba5fb0a30e...
_SHA256_HELLO = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_t004_sha256_hex_empty_bytes():
    """sha256_hex(b'') must return the standard SHA-256 digest of empty bytes."""
    assert ar_ops.sha256_hex(b"") == _SHA256_EMPTY


def test_t004_sha256_hex_known_vector():
    """sha256_hex(b'hello') must match the known test vector."""
    assert ar_ops.sha256_hex(b"hello") == _SHA256_HELLO


def test_t004_sha256_hex_returns_64_chars():
    """sha256_hex must always return a 64-character string."""
    result = ar_ops.sha256_hex(b"arbitrary content for length check")
    assert len(result) == 64


def test_t004_sha256_hex_returns_lowercase_hex():
    """sha256_hex must return only lowercase hexadecimal characters."""
    result = ar_ops.sha256_hex(b"case check data")
    assert all(c in "0123456789abcdef" for c in result)


def test_t004_sha256_hex_is_deterministic():
    """sha256_hex must return the same value for the same input."""
    data = b"determinism check"
    assert ar_ops.sha256_hex(data) == ar_ops.sha256_hex(data)


def test_t004_sha256_hex_different_inputs_differ():
    """sha256_hex must return different values for different inputs."""
    assert ar_ops.sha256_hex(b"abc") != ar_ops.sha256_hex(b"abd")


def test_t004_sha256_hex_rejects_non_bytes():
    """sha256_hex must raise TypeError for non-bytes input."""
    with pytest.raises(TypeError, match="expected bytes"):
        ar_ops.sha256_hex("not bytes")  # type: ignore[arg-type]


def test_t004_sha256_hex_rejects_int():
    """sha256_hex must raise TypeError for integer input."""
    with pytest.raises(TypeError):
        ar_ops.sha256_hex(42)  # type: ignore[arg-type]


def test_t004_object_path_format():
    """object_path must return '<2-char-prefix>/<remaining-62-chars>'."""
    result = ar_ops.object_path(_SHA256_HELLO)
    assert result == f"{_SHA256_HELLO[:2]}/{_SHA256_HELLO[2:]}"
    assert result == "2c/f24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_t004_object_path_length():
    """object_path result must have exactly 65 chars (2 + '/' + 62)."""
    result = ar_ops.object_path(_SHA256_HELLO)
    assert len(result) == 65
    parts = result.split("/")
    assert len(parts) == 2
    assert len(parts[0]) == 2
    assert len(parts[1]) == 62


def test_t004_object_path_accepts_uppercase_hex():
    """object_path must accept uppercase hex and normalize to lowercase."""
    upper = _SHA256_HELLO.upper()
    result = ar_ops.object_path(upper)
    assert result == f"{_SHA256_HELLO[:2]}/{_SHA256_HELLO[2:]}"


def test_t004_object_path_rejects_short_digest():
    """object_path must reject digests shorter than 64 characters."""
    with pytest.raises(ValueError, match="64-char"):
        ar_ops.object_path("abc123")


def test_t004_object_path_rejects_long_digest():
    """object_path must reject digests longer than 64 characters."""
    with pytest.raises(ValueError, match="64-char"):
        ar_ops.object_path(_SHA256_HELLO + "00")


def test_t004_object_path_rejects_non_hex():
    """object_path must reject strings containing non-hex characters."""
    bad = "g" + _SHA256_HELLO[1:]  # 'g' is not a hex char
    with pytest.raises(ValueError, match="64-char"):
        ar_ops.object_path(bad)


def test_t004_object_path_rejects_non_str():
    """object_path must raise TypeError for non-string input."""
    with pytest.raises(TypeError, match="expected str"):
        ar_ops.object_path(b"bytes not str")  # type: ignore[arg-type]


def test_t004_sha256_then_object_path_roundtrip(tmp_path):
    """sha256_hex + object_path + governed_artifact_path must produce a valid path."""
    data = b"synthetic evidence payload for round-trip test"
    digest = ar_ops.sha256_hex(data)
    rel = ar_ops.object_path(digest)
    full = ar_ops.governed_artifact_path(rel, tmp_path)
    assert full.is_absolute()
    assert str(full).startswith(str(tmp_path.resolve()))
    # The last two parts of the path must be the 2-char prefix and 62-char suffix
    parts = full.parts
    assert parts[-2] == digest[:2]
    assert parts[-1] == digest[2:]


# ---------------------------------------------------------------------------
# T005 — Registry data-access operation tests
# registry_lookup, registry_register, registry_supersede,
# registry_set_governance, registry_set_processing, registry_set_availability
# ---------------------------------------------------------------------------

def _reg_kwargs(account_id: str, evidence_id: str = "ev:t005:001") -> dict:
    """Return a minimal valid set of registry_register keyword arguments."""
    now = "2026-01-01T00:00:00+00:00"
    return dict(
        evidence_id=evidence_id,
        account_id=account_id,
        source_system="synthetic",
        source_event="evt:t005",
        source_locator="loc:t005",
        evidence_hash=f"hash:{evidence_id}",
        governed_artifact_path_str=f"/governed/artifacts/{evidence_id}.bin",
        world="test-world",
        first_seen_timestamp=now,
        ingestion_timestamp=now,
        extractor_version="0.1",
        schema_version="1",
        source_reference=f"ref:{evidence_id}",
    )


# --- registry_lookup ---

def test_t005_lookup_returns_none_for_absent(tmp_path):
    """registry_lookup must return None for a non-existent evidence_id."""
    conn = _tmp_conn(tmp_path)
    assert ar_ops.registry_lookup(conn, "ev:nonexistent") is None


def test_t005_lookup_returns_dict_for_existing(tmp_path):
    """registry_lookup must return a dict for a found evidence_id."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:t005:lookup")
    result = ar_ops.registry_lookup(conn, "ev:t005:lookup")
    assert isinstance(result, dict)
    assert result["evidence_id"] == "ev:t005:lookup"
    assert result["account_id"] == acct


# --- registry_register ---

def test_t005_register_inserts_new_row(tmp_path):
    """registry_register must insert a new row and return it."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    kwargs = _reg_kwargs(acct)
    result = ar_ops.registry_register(conn, **kwargs)
    assert isinstance(result, dict)
    assert result["evidence_id"] == "ev:t005:001"
    assert result["governance_status"] == "active"
    assert result["processing_status"] == "pending"
    assert result["availability"] == "available"


def test_t005_register_is_idempotent(tmp_path):
    """registry_register called twice with same source composite must return same row."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    kwargs = _reg_kwargs(acct)
    r1 = ar_ops.registry_register(conn, **kwargs)
    # Second call with different evidence_id but same source composite — should be ignored
    kwargs2 = dict(kwargs, evidence_id="ev:t005:dup")
    r2 = ar_ops.registry_register(conn, **kwargs2)
    # Both should return the *first* row (INSERT OR IGNORE, then SELECT by composite)
    assert r1["evidence_id"] == r2["evidence_id"]
    # Only one row should exist for this composite
    count = conn.execute(
        "SELECT COUNT(*) FROM ar_evidence_registry WHERE source_system=? AND source_event=? "
        "AND source_locator=? AND evidence_hash=?",
        ("synthetic", "evt:t005", "loc:t005", "hash:ev:t005:001"),
    ).fetchone()[0]
    assert count == 1


def test_t005_register_rejects_invalid_governance_status(tmp_path):
    """registry_register must reject invalid governance_status."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    kwargs = dict(_reg_kwargs(acct), governance_status="deleted")
    with pytest.raises(ValueError, match="governance_status"):
        ar_ops.registry_register(conn, **kwargs)


def test_t005_register_rejects_invalid_processing_status(tmp_path):
    """registry_register must reject invalid processing_status."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    kwargs = dict(_reg_kwargs(acct), processing_status="processing")
    with pytest.raises(ValueError, match="processing_status"):
        ar_ops.registry_register(conn, **kwargs)


def test_t005_register_rejects_invalid_availability(tmp_path):
    """registry_register must reject invalid availability."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    kwargs = dict(_reg_kwargs(acct), availability="unknown")
    with pytest.raises(ValueError, match="availability"):
        ar_ops.registry_register(conn, **kwargs)


# --- registry_supersede ---

def test_t005_supersede_sets_supersedes_field(tmp_path):
    """registry_supersede must set new_evidence.supersedes_evidence_id."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:base", evidence_hash="hash:base")
    _seed_evidence(conn, acct, evidence_id="ev:new", evidence_hash="hash:new")
    ar_ops.registry_supersede(conn, "ev:base", "ev:new")
    row = ar_ops.registry_lookup(conn, "ev:new")
    assert row["supersedes_evidence_id"] == "ev:base"


def test_t005_supersede_rejects_missing_new(tmp_path):
    """registry_supersede must raise ValueError if new_evidence_id not found."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:base2", evidence_hash="hash:base2")
    with pytest.raises(ValueError, match="new_evidence_id"):
        ar_ops.registry_supersede(conn, "ev:base2", "ev:nonexistent")


def test_t005_supersede_rejects_missing_superseded(tmp_path):
    """registry_supersede must raise ValueError if superseded_evidence_id not found."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:new2", evidence_hash="hash:new2")
    with pytest.raises(ValueError, match="superseded_evidence_id"):
        ar_ops.registry_supersede(conn, "ev:nonexistent", "ev:new2")


# --- registry_set_governance ---

def test_t005_set_governance_updates_status(tmp_path):
    """registry_set_governance must update governance_status."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:gov")
    ar_ops.registry_set_governance(conn, "ev:gov", "quarantined")
    row = ar_ops.registry_lookup(conn, "ev:gov")
    assert row["governance_status"] == "quarantined"


def test_t005_set_governance_to_revoked(tmp_path):
    """registry_set_governance must allow revocation."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:revoke")
    ar_ops.registry_set_governance(conn, "ev:revoke", "revoked")
    row = ar_ops.registry_lookup(conn, "ev:revoke")
    assert row["governance_status"] == "revoked"


def test_t005_set_governance_rejects_invalid(tmp_path):
    """registry_set_governance must reject invalid status values."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:govbad")
    with pytest.raises(ValueError, match="invalid status"):
        ar_ops.registry_set_governance(conn, "ev:govbad", "deleted")


def test_t005_set_governance_rejects_missing_id(tmp_path):
    """registry_set_governance must raise ValueError for missing evidence_id."""
    conn = _tmp_conn(tmp_path)
    with pytest.raises(ValueError, match="evidence_id"):
        ar_ops.registry_set_governance(conn, "ev:nonexistent", "active")


# --- registry_set_processing ---

def test_t005_set_processing_updates_status(tmp_path):
    """registry_set_processing must update processing_status."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:proc")
    ar_ops.registry_set_processing(conn, "ev:proc", "extracted")
    row = ar_ops.registry_lookup(conn, "ev:proc")
    assert row["processing_status"] == "extracted"


def test_t005_set_processing_rejects_invalid(tmp_path):
    """registry_set_processing must reject invalid status values."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:procbad")
    with pytest.raises(ValueError, match="invalid status"):
        ar_ops.registry_set_processing(conn, "ev:procbad", "processing")


def test_t005_set_processing_rejects_missing_id(tmp_path):
    """registry_set_processing must raise ValueError for missing evidence_id."""
    conn = _tmp_conn(tmp_path)
    with pytest.raises(ValueError, match="evidence_id"):
        ar_ops.registry_set_processing(conn, "ev:nonexistent", "extracted")


# --- registry_set_availability ---

def test_t005_set_availability_updates_to_missing(tmp_path):
    """registry_set_availability must update availability to 'missing'."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:avail")
    ar_ops.registry_set_availability(conn, "ev:avail", "missing")
    row = ar_ops.registry_lookup(conn, "ev:avail")
    assert row["availability"] == "missing"


def test_t005_set_availability_rejects_invalid(tmp_path):
    """registry_set_availability must reject invalid availability values."""
    conn = _tmp_conn(tmp_path)
    acct = _seed_account(conn)
    _seed_evidence(conn, acct, evidence_id="ev:availbad")
    with pytest.raises(ValueError, match="availability"):
        ar_ops.registry_set_availability(conn, "ev:availbad", "unknown")


def test_t005_set_availability_rejects_missing_id(tmp_path):
    """registry_set_availability must raise ValueError for missing evidence_id."""
    conn = _tmp_conn(tmp_path)
    with pytest.raises(ValueError, match="evidence_id"):
        ar_ops.registry_set_availability(conn, "ev:nonexistent", "available")
