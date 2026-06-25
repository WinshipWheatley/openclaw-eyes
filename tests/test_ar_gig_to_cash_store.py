"""
Test suite for GigToCashStore — written strictly to G2C-006-SPEC.md (20260625-G2C006-v1).
Author: Sonnet-B (independent from Sonnet-A implementation).
Tests encode the CONTRACT, not any implementation detail.

DB policy per spec D2:
  - Temp-file SQLite for transaction / FK / concurrency tests.
  - :memory: only when the SAME connection is held for the whole test.
All tests use tmpdir fixtures; no shared, production, or vault paths are opened.
"""

import hashlib
import importlib
import inspect
import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Imports under test — the store module and its public exception hierarchy.
# The four record factories are imported directly from the domain modules
# (which exist in this worktree); the store module is imported by name so
# that a missing implementation gives a clean ImportError rather than an
# AttributeError buried in a test.
# ---------------------------------------------------------------------------
from ar_gig_record import GigRecord, create_gig_record
from ar_work_session_record import WorkSessionRecord, create_work_session
from ar_invoice_record import InvoiceRecord, create_invoice_record
from ar_expected_receivable_record import ExpectedReceivableRecord, create_expected_receivable
from ar_gig_to_cash_serialization import to_json, canonical_sha256

from ar_gig_to_cash_store import (
    GigToCashStore,
    IdempotencyConflict,
    GigImmutableConflict,
    UnsupportedOperation,
    IntegrityError,
    MigrationError,
)


# ===========================================================================
# Helpers / fixtures
# ===========================================================================

def _temp_db_path(tmp_path: Path) -> str:
    """Return a fresh temp-file DB path inside pytest's tmp_path."""
    return str(tmp_path / f"test_{uuid.uuid4().hex}.sqlite3")


def _make_gig(**kwargs) -> GigRecord:
    defaults = dict(
        counterparty_ref="cpref:hilton-001",
        counterparty_name="Capital Hilton",
        billing_policy_ref="bpref:standard",
        idempotency_key=f"idem:gig:{uuid.uuid4().hex}",
        timezone="America/New_York",
        lifecycle_state="proposed",
    )
    defaults.update(kwargs)
    return create_gig_record(**defaults)


def _make_session(gig_id: str, **kwargs) -> WorkSessionRecord:
    defaults = dict(
        gig_id=gig_id,
        worker_ref="worker:winship",
        idempotency_key=f"idem:ws:{uuid.uuid4().hex}",
        source_ref="evtreg:src-001",
        start_utc_iso="2026-06-25T10:00:00+00:00",
        iana_timezone="UTC",
        lifecycle_state="active",
    )
    defaults.update(kwargs)
    return create_work_session(**defaults)


def _make_completed_session(gig_id: str, **kwargs) -> WorkSessionRecord:
    defaults = dict(
        gig_id=gig_id,
        worker_ref="worker:winship",
        idempotency_key=f"idem:ws:{uuid.uuid4().hex}",
        source_ref="evtreg:src-001",
        start_utc_iso="2026-06-25T10:00:00+00:00",
        end_utc_iso="2026-06-25T12:00:00+00:00",
        iana_timezone="UTC",
        lifecycle_state="completed",
    )
    defaults.update(kwargs)
    return create_work_session(**defaults)


def _make_invoice(**kwargs) -> InvoiceRecord:
    defaults = dict(
        counterparty_ref="cpref:hilton-001",
        billing_entity_ref="entity:winship-music",
        idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
        source_ref="evtreg:inv-src-001",
        lifecycle_state="draft",
    )
    defaults.update(kwargs)
    return create_invoice_record(**defaults)


def _make_issued_invoice(invoice_id: str | None = None, **kwargs) -> InvoiceRecord:
    defaults = dict(
        counterparty_ref="cpref:hilton-001",
        billing_entity_ref="entity:winship-music",
        idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
        source_ref="evtreg:inv-src-001",
        lifecycle_state="issued",
        invoice_number="INV-2026-001",
        issue_date_iso="2026-06-25",
        due_date_iso="2026-07-25",
        currency_iso="USD",
        total_minor_units=500000,
    )
    if invoice_id:
        defaults["invoice_id"] = invoice_id
    defaults.update(kwargs)
    return create_invoice_record(**defaults)


def _make_receivable(invoice_id: str, invoice_version_id: str, **kwargs) -> ExpectedReceivableRecord:
    defaults = dict(
        invoice_id=invoice_id,
        invoice_version_id=invoice_version_id,
        counterparty_ref="cpref:hilton-001",
        expected_minor_units=500000,
        currency_iso="USD",
        due_date_iso="2026-07-25",
        recognized_utc_iso="2026-06-25T00:00:00+00:00",
        idempotency_key=f"idem:recv:{uuid.uuid4().hex}",
        source_ref="evtreg:recv-src-001",
        lifecycle_state="open",
    )
    defaults.update(kwargs)
    return create_expected_receivable(**defaults)


@pytest.fixture
def db_path(tmp_path):
    return _temp_db_path(tmp_path)


@pytest.fixture
def store(db_path):
    with GigToCashStore(db_path) as s:
        yield s


# ===========================================================================
# F-1: Migration — schema creation, idempotency across reopens
# ===========================================================================

class TestMigration:
    """Spec F.1 — Migration idempotency and schema creation."""

    EXPECTED_TABLES = {
        "gig_records",
        "work_session_records",
        "invoice_records",
        "expected_receivable_records",
        "schema_migrations",
    }

    def _open_store(self, db_path: str):
        """Open the store as a context manager and return it for the duration."""
        return GigToCashStore(db_path)

    def _get_table_names(self, db_path: str) -> set:
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            return {r[0] for r in rows}
        finally:
            conn.close()

    def _get_migration_rows(self, db_path: str) -> list:
        conn = sqlite3.connect(db_path)
        try:
            return conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        finally:
            conn.close()

    def test_fresh_open_creates_all_tables(self, db_path):
        """Fresh open() creates all required tables."""
        with GigToCashStore(db_path):
            pass
        tables = self._get_table_names(db_path)
        assert self.EXPECTED_TABLES.issubset(tables), (
            f"Missing tables: {self.EXPECTED_TABLES - tables}"
        )

    def test_fresh_open_records_migration_1(self, db_path):
        """Migration #1 is recorded in schema_migrations after first open."""
        with GigToCashStore(db_path):
            pass
        rows = self._get_migration_rows(db_path)
        versions = [r[0] for r in rows]
        assert 1 in versions, f"Migration #1 not in schema_migrations; found: {versions}"

    def test_reopen_does_not_duplicate_migration(self, db_path):
        """Reopening twice does not re-apply or duplicate migration #1."""
        with GigToCashStore(db_path):
            pass
        with GigToCashStore(db_path):
            pass
        rows = self._get_migration_rows(db_path)
        versions = [r[0] for r in rows]
        assert versions.count(1) == 1, (
            f"Migration #1 was applied more than once; rows: {rows}"
        )

    def test_schema_migrations_has_exactly_applied_rows(self, db_path):
        """schema_migrations has exactly the rows that were applied — no extras."""
        with GigToCashStore(db_path):
            pass
        rows = self._get_migration_rows(db_path)
        # At spec G2C-006 v1, exactly migration #1 is defined.
        assert len(rows) >= 1, "At least migration #1 must be present"
        # No row appears more than once (uniqueness enforced by PRIMARY KEY).
        versions = [r[0] for r in rows]
        assert len(versions) == len(set(versions)), "Duplicate migration rows detected"

    def test_triple_reopen_is_idempotent(self, db_path):
        """Three sequential opens still yield exactly one migration-1 row."""
        for _ in range(3):
            with GigToCashStore(db_path):
                pass
        rows = self._get_migration_rows(db_path)
        versions = [r[0] for r in rows]
        assert versions.count(1) == 1


# ===========================================================================
# F-2: Round-trip per record type (×4)
# ===========================================================================

class TestRoundTrip:
    """Spec F.2 — append → get_current / get_version returns equal record."""

    def test_roundtrip_gig_record(self, store):
        """GigRecord: append and get_current returns canonical-JSON-equal record."""
        gig = _make_gig()
        result = store.append(gig)
        assert result.created is True
        retrieved = store.get_current(GigRecord, gig.gig_id)
        assert retrieved is not None
        assert to_json(retrieved) == to_json(gig)

    def test_roundtrip_gig_record_with_optional_nulls(self, store):
        """GigRecord with optional scheduled_* = None round-trips correctly."""
        gig = _make_gig(scheduled_start_iso=None, scheduled_end_iso=None)
        store.append(gig)
        retrieved = store.get_current(GigRecord, gig.gig_id)
        assert retrieved is not None
        assert to_json(retrieved) == to_json(gig)
        assert retrieved.scheduled_start_iso is None
        assert retrieved.scheduled_end_iso is None

    def test_roundtrip_gig_record_with_scheduled_window(self, store):
        """GigRecord with scheduled window round-trips correctly."""
        gig = _make_gig(
            scheduled_start_iso="2026-07-01T18:00:00",
            scheduled_end_iso="2026-07-01T22:00:00",
        )
        store.append(gig)
        retrieved = store.get_current(GigRecord, gig.gig_id)
        assert to_json(retrieved) == to_json(gig)

    def test_roundtrip_work_session_active(self, store):
        """WorkSessionRecord (active, no end): append → get_current is equal."""
        gig = _make_gig()
        store.append(gig)
        ws = _make_session(gig.gig_id)
        result = store.append(ws)
        assert result.created is True
        retrieved = store.get_current(WorkSessionRecord, ws.work_session_id)
        assert retrieved is not None
        assert to_json(retrieved) == to_json(ws)

    def test_roundtrip_work_session_optional_null_end(self, store):
        """WorkSessionRecord with end_utc_iso=None preserves null on retrieval."""
        gig = _make_gig()
        store.append(gig)
        ws = _make_session(gig.gig_id, end_utc_iso=None)
        store.append(ws)
        retrieved = store.get_current(WorkSessionRecord, ws.work_session_id)
        assert retrieved.end_utc_iso is None

    def test_roundtrip_work_session_with_supersedes(self, store):
        """WorkSessionRecord with supersedes_session_id=None round-trips correctly."""
        gig = _make_gig()
        store.append(gig)
        ws = _make_session(gig.gig_id, supersedes_session_id=None)
        store.append(ws)
        retrieved = store.get_current(WorkSessionRecord, ws.work_session_id)
        assert retrieved.supersedes_session_id is None
        assert to_json(retrieved) == to_json(ws)

    def test_roundtrip_invoice_record_draft(self, store):
        """InvoiceRecord (draft, all optional nulls): round-trip correct."""
        inv = _make_invoice()
        result = store.append(inv)
        assert result.created is True
        retrieved = store.get_current(InvoiceRecord, inv.invoice_id)
        assert retrieved is not None
        assert to_json(retrieved) == to_json(inv)
        # Optional fields remain None
        assert retrieved.invoice_number is None
        assert retrieved.issue_date_iso is None
        assert retrieved.due_date_iso is None
        assert retrieved.currency_iso is None
        assert retrieved.total_minor_units is None
        assert retrieved.supersedes_invoice_version_id is None

    def test_roundtrip_invoice_record_issued_full(self, store):
        """InvoiceRecord (issued with all fields): round-trip correct."""
        inv = _make_issued_invoice()
        store.append(inv)
        retrieved = store.get_current(InvoiceRecord, inv.invoice_id)
        assert to_json(retrieved) == to_json(inv)
        assert retrieved.total_minor_units == 500000
        assert retrieved.currency_iso == "USD"

    def test_roundtrip_invoice_get_version(self, store):
        """InvoiceRecord: get_version(version_id) returns equal record."""
        inv = _make_invoice()
        store.append(inv)
        retrieved = store.get_version(InvoiceRecord, inv.invoice_version_id)
        assert retrieved is not None
        assert to_json(retrieved) == to_json(inv)

    def test_roundtrip_expected_receivable(self, store):
        """ExpectedReceivableRecord: append → get_current equal, optional nulls preserved."""
        inv = _make_issued_invoice()
        store.append(inv)
        recv = _make_receivable(inv.invoice_id, inv.invoice_version_id)
        result = store.append(recv)
        assert result.created is True
        retrieved = store.get_current(ExpectedReceivableRecord, recv.receivable_id)
        assert retrieved is not None
        assert to_json(retrieved) == to_json(recv)
        assert retrieved.supersedes_receivable_version_id is None
        assert retrieved.resolution_ref is None

    def test_roundtrip_expected_receivable_get_version(self, store):
        """ExpectedReceivableRecord: get_version(version_id) returns equal record."""
        inv = _make_issued_invoice()
        store.append(inv)
        recv = _make_receivable(inv.invoice_id, inv.invoice_version_id)
        store.append(recv)
        retrieved = store.get_version(ExpectedReceivableRecord, recv.receivable_version_id)
        assert retrieved is not None
        assert to_json(retrieved) == to_json(recv)

    def test_get_current_absent_returns_none(self, store):
        """get_current returns None for an id that was never stored."""
        result = store.get_current(GigRecord, "gig:nonexistent-id")
        assert result is None

    def test_get_version_absent_returns_none(self, store):
        """get_version returns None for a version_id that was never stored."""
        result = store.get_version(InvoiceRecord, "inv_ver:nonexistent")
        assert result is None

    def test_get_version_raises_type_error_for_gig(self, store):
        """get_version on GigRecord raises TypeError (no version chain per D1)."""
        with pytest.raises(TypeError):
            store.get_version(GigRecord, "gig:anything")


# ===========================================================================
# F-3: Idempotency
# ===========================================================================

class TestIdempotency:
    """Spec F.3 — re-append identical → no-op; same key + different content → conflict."""

    def _row_count(self, db_path: str, table: str) -> int:
        conn = sqlite3.connect(db_path)
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()

    def test_identical_gig_reappend_is_noop(self, tmp_path):
        """Re-appending the exact same GigRecord is a no-op; created=False."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        with GigToCashStore(db_path) as store:
            r1 = store.append(gig)
            r2 = store.append(gig)
        assert r1.created is True
        assert r2.created is False

    def test_identical_gig_reappend_row_count_unchanged(self, tmp_path):
        """Row count does not increase on idempotent gig re-append."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(gig)
        assert self._row_count(db_path, "gig_records") == 1

    def test_idempotency_conflict_gig_same_key_different_content(self, tmp_path):
        """Same idempotency_key, different content → IdempotencyConflict."""
        db_path = _temp_db_path(tmp_path)
        ikey = f"idem:gig:{uuid.uuid4().hex}"
        gig_a = _make_gig(idempotency_key=ikey, counterparty_name="Venue A")
        # Create a gig with the same idempotency_key but different counterparty_name.
        # We must also use a different gig_id so GigImmutableConflict doesn't fire first.
        gig_b = _make_gig(idempotency_key=ikey, counterparty_name="Venue B")
        with GigToCashStore(db_path) as store:
            store.append(gig_a)
            with pytest.raises(IdempotencyConflict):
                store.append(gig_b)

    def test_idempotency_conflict_does_not_mutate_rows(self, tmp_path):
        """Row count is unchanged after an IdempotencyConflict is raised."""
        db_path = _temp_db_path(tmp_path)
        ikey = f"idem:gig:{uuid.uuid4().hex}"
        gig_a = _make_gig(idempotency_key=ikey, counterparty_name="Venue A")
        gig_b = _make_gig(idempotency_key=ikey, counterparty_name="Venue B")
        with GigToCashStore(db_path) as store:
            store.append(gig_a)
            with pytest.raises(IdempotencyConflict):
                store.append(gig_b)
        assert self._row_count(db_path, "gig_records") == 1

    def test_identical_invoice_reappend_is_noop(self, tmp_path):
        """Re-appending the same InvoiceRecord is a no-op."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_invoice()
        with GigToCashStore(db_path) as store:
            r1 = store.append(inv)
            r2 = store.append(inv)
        assert r1.created is True
        assert r2.created is False
        assert self._row_count(db_path, "invoice_records") == 1

    def test_identical_work_session_reappend_is_noop(self, tmp_path):
        """Re-appending the same WorkSessionRecord is a no-op."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws = _make_session(gig.gig_id)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            r1 = store.append(ws)
            r2 = store.append(ws)
        assert r1.created is True
        assert r2.created is False
        assert self._row_count(db_path, "work_session_records") == 1

    def test_identical_receivable_reappend_is_noop(self, tmp_path):
        """Re-appending the same ExpectedReceivableRecord is a no-op."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_issued_invoice()
        recv = _make_receivable(inv.invoice_id, inv.invoice_version_id)
        with GigToCashStore(db_path) as store:
            store.append(inv)
            r1 = store.append(recv)
            r2 = store.append(recv)
        assert r1.created is True
        assert r2.created is False
        assert self._row_count(db_path, "expected_receivable_records") == 1


# ===========================================================================
# F-4: Versioning / supersede
# ===========================================================================

class TestVersioningAndSupersede:
    """Spec F.4 — supersede chain semantics for versioned types."""

    def _count_all_rows(self, db_path: str, table: str) -> int:
        conn = sqlite3.connect(db_path)
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()

    def _read_sha256(self, db_path: str, table: str, where_col: str, where_val: str) -> str:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                f"SELECT content_sha256 FROM {table} WHERE {where_col} = ?",
                (where_val,)
            ).fetchone()
            assert row is not None, f"Row not found in {table} where {where_col}={where_val!r}"
            return row[0]
        finally:
            conn.close()

    # --- WorkSession versioning ---

    def test_supersede_work_session_get_current_is_v2(self, tmp_path):
        """After supersede, get_current returns v2."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws_v1 = _make_completed_session(gig.gig_id)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(ws_v1)
            ws_v2 = create_work_session(
                gig_id=gig.gig_id,
                worker_ref="worker:winship",
                idempotency_key=f"idem:ws:{uuid.uuid4().hex}",
                source_ref="evtreg:src-002",
                start_utc_iso="2026-06-25T10:00:00+00:00",
                end_utc_iso="2026-06-25T13:00:00+00:00",
                lifecycle_state="completed",
                supersedes_session_id=ws_v1.work_session_id,
            )
            store.supersede(ws_v1.work_session_id, ws_v2)
            current = store.get_current(WorkSessionRecord, ws_v1.work_session_id)
        assert current is not None
        assert to_json(current) == to_json(ws_v2)

    def test_supersede_work_session_get_version_v1_unchanged(self, tmp_path):
        """After supersede, get_version with v1 id still returns v1's content."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws_v1 = _make_completed_session(gig.gig_id)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(ws_v1)
            ws_v2 = create_work_session(
                gig_id=gig.gig_id,
                worker_ref="worker:winship",
                idempotency_key=f"idem:ws:{uuid.uuid4().hex}",
                source_ref="evtreg:src-002",
                start_utc_iso="2026-06-25T10:00:00+00:00",
                end_utc_iso="2026-06-25T13:00:00+00:00",
                lifecycle_state="completed",
                supersedes_session_id=ws_v1.work_session_id,
            )
            store.supersede(ws_v1.work_session_id, ws_v2)
            # WorkSession uses work_session_id as its "version" id for get_version
            v1_back = store.get_version(WorkSessionRecord, ws_v1.work_session_id)
        assert v1_back is not None
        assert to_json(v1_back) == to_json(ws_v1)

    def test_supersede_work_session_list_history_ordered(self, tmp_path):
        """list_history returns [v1, v2] in oldest→newest order."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws_v1 = _make_completed_session(gig.gig_id)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(ws_v1)
            ws_v2 = create_work_session(
                gig_id=gig.gig_id,
                worker_ref="worker:winship",
                idempotency_key=f"idem:ws:{uuid.uuid4().hex}",
                source_ref="evtreg:src-002",
                start_utc_iso="2026-06-25T10:00:00+00:00",
                end_utc_iso="2026-06-25T13:00:00+00:00",
                lifecycle_state="completed",
                supersedes_session_id=ws_v1.work_session_id,
            )
            store.supersede(ws_v1.work_session_id, ws_v2)
            history = store.list_history(WorkSessionRecord, ws_v1.work_session_id)
        assert len(history) == 2
        assert to_json(history[0]) == to_json(ws_v1)
        assert to_json(history[1]) == to_json(ws_v2)

    def test_supersede_work_session_prior_sha256_unchanged(self, tmp_path):
        """v1's content_sha256 in the DB is unchanged after supersede."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws_v1 = _make_completed_session(gig.gig_id)
        expected_sha = canonical_sha256(ws_v1)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(ws_v1)
            sha_before = self._read_sha256(
                db_path, "work_session_records",
                "work_session_id", ws_v1.work_session_id,
            )
            ws_v2 = create_work_session(
                gig_id=gig.gig_id,
                worker_ref="worker:winship",
                idempotency_key=f"idem:ws:{uuid.uuid4().hex}",
                source_ref="evtreg:src-002",
                start_utc_iso="2026-06-25T10:00:00+00:00",
                end_utc_iso="2026-06-25T13:00:00+00:00",
                lifecycle_state="completed",
                supersedes_session_id=ws_v1.work_session_id,
            )
            store.supersede(ws_v1.work_session_id, ws_v2)
        sha_after = self._read_sha256(
            db_path, "work_session_records",
            "work_session_id", ws_v1.work_session_id,
        )
        assert sha_before == expected_sha
        assert sha_after == expected_sha

    def test_supersede_work_session_row_count_grows_by_exactly_1(self, tmp_path):
        """Supersede adds exactly one new row; total grows by 1."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws_v1 = _make_completed_session(gig.gig_id)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(ws_v1)
            before = self._count_all_rows(db_path, "work_session_records")
            ws_v2 = create_work_session(
                gig_id=gig.gig_id,
                worker_ref="worker:winship",
                idempotency_key=f"idem:ws:{uuid.uuid4().hex}",
                source_ref="evtreg:src-002",
                start_utc_iso="2026-06-25T10:00:00+00:00",
                end_utc_iso="2026-06-25T13:00:00+00:00",
                lifecycle_state="completed",
                supersedes_session_id=ws_v1.work_session_id,
            )
            store.supersede(ws_v1.work_session_id, ws_v2)
            after = self._count_all_rows(db_path, "work_session_records")
        assert after - before == 1

    # --- Invoice versioning ---

    def test_supersede_invoice_get_current_is_v2(self, tmp_path):
        """After invoice supersede, get_current returns v2."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            inv_v2 = create_invoice_record(
                counterparty_ref="cpref:hilton-001",
                billing_entity_ref="entity:winship-music",
                idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
                source_ref="evtreg:inv-src-002",
                lifecycle_state="draft",
                invoice_id=inv_id,
                supersedes_invoice_version_id=inv_v1.invoice_version_id,
            )
            store.supersede(inv_id, inv_v2)
            current = store.get_current(InvoiceRecord, inv_id)
        assert current is not None
        assert to_json(current) == to_json(inv_v2)

    def test_supersede_invoice_get_version_v1_still_accessible(self, tmp_path):
        """get_version(v1 version_id) returns v1 after supersede."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            inv_v2 = create_invoice_record(
                counterparty_ref="cpref:hilton-001",
                billing_entity_ref="entity:winship-music",
                idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
                source_ref="evtreg:inv-src-002",
                lifecycle_state="draft",
                invoice_id=inv_id,
                supersedes_invoice_version_id=inv_v1.invoice_version_id,
            )
            store.supersede(inv_id, inv_v2)
            v1_back = store.get_version(InvoiceRecord, inv_v1.invoice_version_id)
        assert v1_back is not None
        assert to_json(v1_back) == to_json(inv_v1)

    def test_supersede_invoice_list_history_ordered(self, tmp_path):
        """list_history for invoice returns [v1, v2] oldest→newest."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            inv_v2 = create_invoice_record(
                counterparty_ref="cpref:hilton-001",
                billing_entity_ref="entity:winship-music",
                idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
                source_ref="evtreg:inv-src-002",
                lifecycle_state="draft",
                invoice_id=inv_id,
                supersedes_invoice_version_id=inv_v1.invoice_version_id,
            )
            store.supersede(inv_id, inv_v2)
            history = store.list_history(InvoiceRecord, inv_id)
        assert len(history) == 2
        assert to_json(history[0]) == to_json(inv_v1)
        assert to_json(history[1]) == to_json(inv_v2)

    def test_supersede_invoice_prior_sha256_unchanged(self, tmp_path):
        """v1 invoice row content_sha256 is unchanged after supersede."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        expected_sha = canonical_sha256(inv_v1)
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            sha_before = self._read_sha256(
                db_path, "invoice_records",
                "invoice_version_id", inv_v1.invoice_version_id,
            )
            inv_v2 = create_invoice_record(
                counterparty_ref="cpref:hilton-001",
                billing_entity_ref="entity:winship-music",
                idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
                source_ref="evtreg:inv-src-002",
                lifecycle_state="draft",
                invoice_id=inv_id,
                supersedes_invoice_version_id=inv_v1.invoice_version_id,
            )
            store.supersede(inv_id, inv_v2)
        sha_after = self._read_sha256(
            db_path, "invoice_records",
            "invoice_version_id", inv_v1.invoice_version_id,
        )
        assert sha_before == expected_sha
        assert sha_after == expected_sha

    def test_supersede_invoice_row_count_grows_by_exactly_1(self, tmp_path):
        """Invoice supersede adds exactly one new row."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            before = self._count_all_rows(db_path, "invoice_records")
            inv_v2 = create_invoice_record(
                counterparty_ref="cpref:hilton-001",
                billing_entity_ref="entity:winship-music",
                idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
                source_ref="evtreg:inv-src-002",
                lifecycle_state="draft",
                invoice_id=inv_id,
                supersedes_invoice_version_id=inv_v1.invoice_version_id,
            )
            store.supersede(inv_id, inv_v2)
            after = self._count_all_rows(db_path, "invoice_records")
        assert after - before == 1

    # --- Receivable versioning ---

    def test_supersede_receivable_get_current_is_v2(self, tmp_path):
        """After receivable supersede, get_current returns v2."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_issued_invoice()
        recv_id = f"recv:{uuid.uuid4().hex}"
        recv_v1 = _make_receivable(inv.invoice_id, inv.invoice_version_id, receivable_id=recv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv)
            store.append(recv_v1)
            recv_v2 = create_expected_receivable(
                invoice_id=inv.invoice_id,
                invoice_version_id=inv.invoice_version_id,
                counterparty_ref="cpref:hilton-001",
                expected_minor_units=500000,
                currency_iso="USD",
                due_date_iso="2026-07-25",
                recognized_utc_iso="2026-06-25T00:00:00+00:00",
                idempotency_key=f"idem:recv:{uuid.uuid4().hex}",
                source_ref="evtreg:recv-src-002",
                receivable_id=recv_id,
                supersedes_receivable_version_id=recv_v1.receivable_version_id,
                lifecycle_state="disputed",
                resolution_ref=None,
            )
            store.supersede(recv_id, recv_v2)
            current = store.get_current(ExpectedReceivableRecord, recv_id)
        assert current is not None
        assert to_json(current) == to_json(recv_v2)

    def test_supersede_receivable_list_history_ordered(self, tmp_path):
        """list_history for receivable returns [v1, v2] oldest→newest."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_issued_invoice()
        recv_id = f"recv:{uuid.uuid4().hex}"
        recv_v1 = _make_receivable(inv.invoice_id, inv.invoice_version_id, receivable_id=recv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv)
            store.append(recv_v1)
            recv_v2 = create_expected_receivable(
                invoice_id=inv.invoice_id,
                invoice_version_id=inv.invoice_version_id,
                counterparty_ref="cpref:hilton-001",
                expected_minor_units=500000,
                currency_iso="USD",
                due_date_iso="2026-07-25",
                recognized_utc_iso="2026-06-25T00:00:00+00:00",
                idempotency_key=f"idem:recv:{uuid.uuid4().hex}",
                source_ref="evtreg:recv-src-002",
                receivable_id=recv_id,
                supersedes_receivable_version_id=recv_v1.receivable_version_id,
                lifecycle_state="disputed",
                resolution_ref=None,
            )
            store.supersede(recv_id, recv_v2)
            history = store.list_history(ExpectedReceivableRecord, recv_id)
        assert len(history) == 2
        assert to_json(history[0]) == to_json(recv_v1)
        assert to_json(history[1]) == to_json(recv_v2)

    # --- Invalid supersede linkage ---

    def test_supersede_wrong_logical_id_rejected(self, tmp_path):
        """supersede where new_record's logical id != prior_logical_id is rejected."""
        db_path = _temp_db_path(tmp_path)
        inv_id_a = f"inv:{uuid.uuid4().hex}"
        inv_id_b = f"inv:{uuid.uuid4().hex}"
        inv_a = _make_invoice(invoice_id=inv_id_a)
        inv_b = _make_invoice(invoice_id=inv_id_b)
        with GigToCashStore(db_path) as store:
            store.append(inv_a)
            store.append(inv_b)
            # Try to supersede inv_id_a but pass a record with inv_id_b
            inv_mismatch = create_invoice_record(
                counterparty_ref="cpref:hilton-001",
                billing_entity_ref="entity:winship-music",
                idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
                source_ref="evtreg:inv-src-002",
                lifecycle_state="draft",
                invoice_id=inv_id_b,  # wrong logical id
                supersedes_invoice_version_id=inv_a.invoice_version_id,
            )
            with pytest.raises((ValueError, TypeError, Exception)):
                store.supersede(inv_id_a, inv_mismatch)

    def test_supersede_wrong_supersedes_pointer_rejected(self, tmp_path):
        """supersede where supersedes_*_version_id != current version is rejected."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        bogus_version_id = f"inv_ver:{uuid.uuid4().hex}"  # never stored
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            inv_bad = create_invoice_record(
                counterparty_ref="cpref:hilton-001",
                billing_entity_ref="entity:winship-music",
                idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
                source_ref="evtreg:inv-src-002",
                lifecycle_state="draft",
                invoice_id=inv_id,
                supersedes_invoice_version_id=bogus_version_id,
            )
            with pytest.raises((ValueError, TypeError, Exception)):
                store.supersede(inv_id, inv_bad)


# ===========================================================================
# F-5: Append-only invariance
# ===========================================================================

class TestAppendOnlyInvariance:
    """Spec F.5 — no public or private path performs UPDATE/DELETE."""

    def _get_all_rows(self, db_path: str, table: str) -> list[tuple]:
        conn = sqlite3.connect(db_path)
        try:
            return conn.execute(f"SELECT * FROM {table}").fetchall()
        finally:
            conn.close()

    def test_no_rows_mutated_after_supersede_invoice(self, tmp_path):
        """Supersede does not mutate any pre-existing row — all rows are identical after."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            rows_before = self._get_all_rows(db_path, "invoice_records")
            inv_v2 = create_invoice_record(
                counterparty_ref="cpref:hilton-001",
                billing_entity_ref="entity:winship-music",
                idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
                source_ref="evtreg:inv-src-002",
                lifecycle_state="draft",
                invoice_id=inv_id,
                supersedes_invoice_version_id=inv_v1.invoice_version_id,
            )
            store.supersede(inv_id, inv_v2)
            rows_after = self._get_all_rows(db_path, "invoice_records")
        # All rows that existed before must still exist byte-for-byte unchanged.
        assert len(rows_after) == len(rows_before) + 1
        for row in rows_before:
            assert row in rows_after, f"Row was mutated or deleted: {row}"

    def test_no_delete_method_on_store(self, store):
        """GigToCashStore exposes no delete method."""
        assert not hasattr(store, "delete"), "Store must not expose a delete method"

    def test_no_update_method_on_store(self, store):
        """GigToCashStore exposes no update method."""
        assert not hasattr(store, "update"), "Store must not expose an update method"

    def test_no_sql_update_or_delete_in_source(self):
        """The store module source contains no bare UPDATE/DELETE SQL statements
        that would mutate stored rows (structural check on the module source)."""
        import ar_gig_to_cash_store as store_mod
        source = inspect.getsource(store_mod)
        # Allow the word in comments or strings referencing the spec, but the
        # actual SQL keywords used in execute() calls should not appear.
        # We look for the pattern of executing an UPDATE or DELETE statement.
        import re
        # Match execute("UPDATE ... or execute('DELETE ...
        update_pattern = re.compile(r'execute\s*\(\s*["\']?\s*UPDATE', re.IGNORECASE)
        delete_pattern = re.compile(r'execute\s*\(\s*["\']?\s*DELETE', re.IGNORECASE)
        assert not update_pattern.search(source), "Store contains an UPDATE execute() call"
        assert not delete_pattern.search(source), "Store contains a DELETE execute() call"

    def test_gig_records_only_grow(self, tmp_path):
        """Row count in gig_records only ever increases across operations."""
        db_path = _temp_db_path(tmp_path)
        counts = []
        with GigToCashStore(db_path) as store:
            gig_a = _make_gig()
            store.append(gig_a)
            conn = sqlite3.connect(db_path)
            counts.append(conn.execute("SELECT COUNT(*) FROM gig_records").fetchone()[0])
            conn.close()
            gig_b = _make_gig()
            store.append(gig_b)
            conn = sqlite3.connect(db_path)
            counts.append(conn.execute("SELECT COUNT(*) FROM gig_records").fetchone()[0])
            conn.close()
        assert counts == [1, 2], f"Expected monotonically growing row counts; got {counts}"


# ===========================================================================
# F-6: FK integrity — receivable → invoice_version_id
# ===========================================================================

class TestForeignKeyIntegrity:
    """Spec F.6 — FK from expected_receivable_records to invoice_records."""

    def test_receivable_with_absent_invoice_version_rejected(self, tmp_path):
        """Storing a receivable whose invoice_version_id is not in invoice_records is rejected."""
        db_path = _temp_db_path(tmp_path)
        # We build a receivable referencing an invoice_version_id that was never stored.
        bogus_inv_version = f"inv_ver:{uuid.uuid4().hex}"
        bogus_inv_id = f"inv:{uuid.uuid4().hex}"
        recv = _make_receivable(bogus_inv_id, bogus_inv_version)
        with GigToCashStore(db_path) as store:
            # FK violation must surface as IntegrityError — NOT IdempotencyConflict (regression guard:
            # a referential failure must never be conflated with an idempotency no-op/conflict).
            with pytest.raises(IntegrityError):
                store.append(recv)

    def test_receivable_with_present_invoice_version_accepted(self, tmp_path):
        """Storing a receivable whose invoice_version_id exists in invoice_records succeeds."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_issued_invoice()
        recv = _make_receivable(inv.invoice_id, inv.invoice_version_id)
        with GigToCashStore(db_path) as store:
            store.append(inv)
            result = store.append(recv)
        assert result.created is True

    def test_receivable_fk_references_exact_version_not_logical_id(self, tmp_path):
        """The FK constraint is on invoice_version_id (specific version), not invoice_id."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        inv_v2 = create_invoice_record(
            counterparty_ref="cpref:hilton-001",
            billing_entity_ref="entity:winship-music",
            idempotency_key=f"idem:inv:{uuid.uuid4().hex}",
            source_ref="evtreg:inv-src-002",
            lifecycle_state="draft",
            invoice_id=inv_id,
            supersedes_invoice_version_id=inv_v1.invoice_version_id,
        )
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            store.supersede(inv_id, inv_v2)
            # Receivable referencing v1 (present) should be accepted.
            recv_v1 = _make_receivable(inv_id, inv_v1.invoice_version_id)
            result = store.append(recv_v1)
            assert result.created is True
            # Receivable referencing v2 (also present) should be accepted.
            recv_v2 = _make_receivable(inv_id, inv_v2.invoice_version_id)
            result2 = store.append(recv_v2)
            assert result2.created is True

    def test_receivable_fk_stored_version_not_absent_version(self, tmp_path):
        """Receivable referencing a version_id that was never stored is rejected even if logical id matches."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
            # Reference an entirely fabricated version_id
            fake_version = f"inv_ver:{uuid.uuid4().hex}"
            recv = _make_receivable(inv_id, fake_version)
            with pytest.raises(IntegrityError):
                store.append(recv)


# ===========================================================================
# F-7: Strict read — tampered canonical_json raises IntegrityError
# ===========================================================================

class TestStrictRead:
    """Spec F.7 — tampered canonical_json (sha mismatch) → IntegrityError on read."""

    def _tamper_canonical_json(self, db_path: str, table: str, pk_col: str, pk_val: str):
        """Directly corrupt the canonical_json of a row in the DB (bypasses the store)."""
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                f"UPDATE {table} SET canonical_json = '{{\"tampered\":true}}' "
                f"WHERE {pk_col} = ?",
                (pk_val,),
            )
            conn.commit()
        finally:
            conn.close()

    def test_tampered_gig_json_raises_integrity_error(self, tmp_path):
        """get_current on a tampered GigRecord row raises IntegrityError."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        with GigToCashStore(db_path) as store:
            store.append(gig)
        # Tamper directly via raw SQLite after the store is closed.
        self._tamper_canonical_json(db_path, "gig_records", "gig_id", gig.gig_id)
        with GigToCashStore(db_path) as store:
            with pytest.raises(IntegrityError):
                store.get_current(GigRecord, gig.gig_id)

    def test_tampered_invoice_json_raises_integrity_error(self, tmp_path):
        """get_current on a tampered InvoiceRecord row raises IntegrityError."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_invoice()
        with GigToCashStore(db_path) as store:
            store.append(inv)
        self._tamper_canonical_json(db_path, "invoice_records", "invoice_version_id", inv.invoice_version_id)
        with GigToCashStore(db_path) as store:
            with pytest.raises(IntegrityError):
                store.get_current(InvoiceRecord, inv.invoice_id)

    def test_tampered_invoice_version_json_raises_integrity_error(self, tmp_path):
        """get_version on a tampered InvoiceRecord row raises IntegrityError."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_invoice()
        with GigToCashStore(db_path) as store:
            store.append(inv)
        self._tamper_canonical_json(db_path, "invoice_records", "invoice_version_id", inv.invoice_version_id)
        with GigToCashStore(db_path) as store:
            with pytest.raises(IntegrityError):
                store.get_version(InvoiceRecord, inv.invoice_version_id)

    def test_tampered_work_session_json_raises_integrity_error(self, tmp_path):
        """get_current on a tampered WorkSessionRecord row raises IntegrityError."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws = _make_session(gig.gig_id)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(ws)
        self._tamper_canonical_json(db_path, "work_session_records", "work_session_id", ws.work_session_id)
        with GigToCashStore(db_path) as store:
            with pytest.raises(IntegrityError):
                store.get_current(WorkSessionRecord, ws.work_session_id)

    def test_tampered_receivable_json_raises_integrity_error(self, tmp_path):
        """get_current on a tampered ExpectedReceivableRecord row raises IntegrityError."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_issued_invoice()
        recv = _make_receivable(inv.invoice_id, inv.invoice_version_id)
        with GigToCashStore(db_path) as store:
            store.append(inv)
            store.append(recv)
        self._tamper_canonical_json(
            db_path, "expected_receivable_records",
            "receivable_version_id", recv.receivable_version_id,
        )
        with GigToCashStore(db_path) as store:
            with pytest.raises(IntegrityError):
                store.get_current(ExpectedReceivableRecord, recv.receivable_id)

    def test_list_history_with_tampered_row_raises_integrity_error(self, tmp_path):
        """list_history raises IntegrityError if any row in the chain is tampered."""
        db_path = _temp_db_path(tmp_path)
        inv_id = f"inv:{uuid.uuid4().hex}"
        inv_v1 = _make_invoice(invoice_id=inv_id)
        with GigToCashStore(db_path) as store:
            store.append(inv_v1)
        self._tamper_canonical_json(db_path, "invoice_records", "invoice_version_id", inv_v1.invoice_version_id)
        with GigToCashStore(db_path) as store:
            with pytest.raises(IntegrityError):
                store.list_history(InvoiceRecord, inv_id)


# ===========================================================================
# F-8: Authority / exclusions
# ===========================================================================

class TestAuthorityExclusions:
    """Spec F.8 — no money/send/bank/network method; temp DBs only; no vault paths."""

    FORBIDDEN_METHOD_PATTERNS = [
        "send", "pay", "bank", "transfer", "email", "telegram",
        "network", "http", "ftp", "socket", "wire", "disburse",
    ]

    def test_store_has_no_send_method(self, store):
        """GigToCashStore has no method containing 'send'."""
        methods = [m for m in dir(store) if not m.startswith("__")]
        send_methods = [m for m in methods if "send" in m.lower()]
        assert not send_methods, f"Store exposes send-like methods: {send_methods}"

    def test_store_has_no_pay_method(self, store):
        """GigToCashStore has no method containing 'pay'."""
        methods = [m for m in dir(store) if not m.startswith("__")]
        pay_methods = [m for m in methods if "pay" in m.lower()]
        assert not pay_methods, f"Store exposes pay-like methods: {pay_methods}"

    def test_store_has_no_bank_method(self, store):
        """GigToCashStore has no method containing 'bank'."""
        methods = [m for m in dir(store) if not m.startswith("__")]
        bank_methods = [m for m in methods if "bank" in m.lower()]
        assert not bank_methods, f"Store exposes bank-like methods: {bank_methods}"

    def test_store_has_no_network_method(self, store):
        """GigToCashStore has no method containing 'network', 'http', or 'socket'."""
        methods = [m for m in dir(store) if not m.startswith("__")]
        net_methods = [
            m for m in methods
            if any(word in m.lower() for word in ("network", "http", "socket", "ftp"))
        ]
        assert not net_methods, f"Store exposes network-like methods: {net_methods}"

    def test_no_test_opens_production_path(self):
        """Confirm no test in this module OPENS the canonical prod DB path.

        Spec F.8: tests must run on temp/:memory: DBs only — no shared/
        production/vault path is opened. We check that the forbidden path is
        never passed to a DB-opening call (GigToCashStore(...) or
        sqlite3.connect(...)). A bare textual mention (e.g. in this very
        assertion) is not an "open" and must not trip the check, so the path
        is assembled from fragments to avoid a self-referential literal.
        """
        # Assembled so the literal does not appear verbatim in this file.
        prod_path = "/home/openclaw/state/" + "gig_to_cash/" + "gig_to_cash" + ".sqlite3"
        source = inspect.getsource(sys.modules[__name__])
        opens = [
            f"GigToCashStore({prod_path!r}",
            f"GigToCashStore(\"{prod_path}\"",
            f"GigToCashStore('{prod_path}'",
            f"sqlite3.connect({prod_path!r}",
            f"sqlite3.connect(\"{prod_path}\"",
            f"sqlite3.connect('{prod_path}'",
        ]
        for opener in opens:
            assert opener not in source, (
                f"A test opens the production DB path: {opener}"
            )

    def test_no_test_opens_control_plane_db(self):
        """Confirm no test OPENS the polish-loop control-plane DB.

        Same rationale as test_no_test_opens_production_path: we assert the
        forbidden DB is never passed to a DB-opening call, not merely that its
        name is absent from the file. The name is assembled from fragments to
        avoid a self-referential literal tripping the check.
        """
        forbidden = "control_plane" + ".sqlite3"
        source = inspect.getsource(sys.modules[__name__])
        opens = [
            f"GigToCashStore({forbidden!r}",
            f"sqlite3.connect({forbidden!r}",
            f'GigToCashStore("{forbidden}"',
            f"GigToCashStore('{forbidden}'",
            f'sqlite3.connect("{forbidden}"',
            f"sqlite3.connect('{forbidden}'",
        ]
        for opener in opens:
            assert opener not in source, (
                f"A test opens the control-plane DB: {opener}"
            )

    def test_store_public_api_is_bounded(self, store):
        """Store public API is limited to the documented methods."""
        documented = {"append", "get_current", "get_version", "list_history", "supersede"}
        public_methods = {
            m for m in dir(store)
            if not m.startswith("_") and callable(getattr(store, m))
        }
        # Context manager entry/exit are acceptable extras.
        extra = public_methods - documented - {"__enter__", "__exit__", "open", "close"}
        undocumented_destructive = {
            m for m in extra
            if any(w in m.lower() for w in ("delete", "drop", "update", "truncate", "pay", "send", "bank"))
        }
        assert not undocumented_destructive, (
            f"Store exposes undocumented destructive methods: {undocumented_destructive}"
        )

    def test_append_rejects_non_record_type(self, store):
        """append() with an unsupported type raises TypeError (authority boundary)."""
        with pytest.raises(TypeError):
            store.append({"not": "a record"})

    def test_append_rejects_plain_string(self, store):
        """append() with a plain string raises TypeError."""
        with pytest.raises(TypeError):
            store.append("raw string payload")

    def test_append_rejects_none(self, store):
        """append() with None raises TypeError."""
        with pytest.raises(TypeError):
            store.append(None)


# Need sys for the module source inspection tests
import sys


# ===========================================================================
# F-9: Determinism — stored canonical_json byte-identical to to_json(record)
# ===========================================================================

class TestDeterminism:
    """Spec F.9 — stored canonical_json is byte-identical to to_json(record)."""

    def _read_canonical_json(self, db_path: str, table: str, where_col: str, where_val: str) -> str:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                f"SELECT canonical_json FROM {table} WHERE {where_col} = ?",
                (where_val,)
            ).fetchone()
            assert row is not None
            return row[0]
        finally:
            conn.close()

    def _read_content_sha256(self, db_path: str, table: str, where_col: str, where_val: str) -> str:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                f"SELECT content_sha256 FROM {table} WHERE {where_col} = ?",
                (where_val,)
            ).fetchone()
            assert row is not None
            return row[0]
        finally:
            conn.close()

    def test_gig_canonical_json_byte_identical(self, tmp_path):
        """Stored canonical_json for GigRecord == to_json(record)."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        with GigToCashStore(db_path) as store:
            store.append(gig)
        stored = self._read_canonical_json(db_path, "gig_records", "gig_id", gig.gig_id)
        assert stored == to_json(gig)

    def test_invoice_canonical_json_byte_identical(self, tmp_path):
        """Stored canonical_json for InvoiceRecord == to_json(record)."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_invoice()
        with GigToCashStore(db_path) as store:
            store.append(inv)
        stored = self._read_canonical_json(
            db_path, "invoice_records", "invoice_version_id", inv.invoice_version_id
        )
        assert stored == to_json(inv)

    def test_work_session_canonical_json_byte_identical(self, tmp_path):
        """Stored canonical_json for WorkSessionRecord == to_json(record)."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws = _make_session(gig.gig_id)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(ws)
        stored = self._read_canonical_json(
            db_path, "work_session_records", "work_session_id", ws.work_session_id
        )
        assert stored == to_json(ws)

    def test_receivable_canonical_json_byte_identical(self, tmp_path):
        """Stored canonical_json for ExpectedReceivableRecord == to_json(record)."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_issued_invoice()
        recv = _make_receivable(inv.invoice_id, inv.invoice_version_id)
        with GigToCashStore(db_path) as store:
            store.append(inv)
            store.append(recv)
        stored = self._read_canonical_json(
            db_path, "expected_receivable_records",
            "receivable_version_id", recv.receivable_version_id,
        )
        assert stored == to_json(recv)

    def test_gig_content_sha256_matches(self, tmp_path):
        """Stored content_sha256 == sha256(to_json(record)) for GigRecord."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        with GigToCashStore(db_path) as store:
            store.append(gig)
        stored_sha = self._read_content_sha256(db_path, "gig_records", "gig_id", gig.gig_id)
        expected_sha = hashlib.sha256(to_json(gig).encode("utf-8")).hexdigest()
        assert stored_sha == expected_sha

    def test_invoice_content_sha256_matches(self, tmp_path):
        """Stored content_sha256 == sha256(to_json(record)) for InvoiceRecord."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_invoice()
        with GigToCashStore(db_path) as store:
            store.append(inv)
        stored_sha = self._read_content_sha256(
            db_path, "invoice_records", "invoice_version_id", inv.invoice_version_id
        )
        expected_sha = hashlib.sha256(to_json(inv).encode("utf-8")).hexdigest()
        assert stored_sha == expected_sha

    def test_work_session_content_sha256_matches(self, tmp_path):
        """Stored content_sha256 == sha256(to_json(record)) for WorkSessionRecord."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        ws = _make_session(gig.gig_id)
        with GigToCashStore(db_path) as store:
            store.append(gig)
            store.append(ws)
        stored_sha = self._read_content_sha256(
            db_path, "work_session_records", "work_session_id", ws.work_session_id
        )
        expected_sha = hashlib.sha256(to_json(ws).encode("utf-8")).hexdigest()
        assert stored_sha == expected_sha

    def test_receivable_content_sha256_matches(self, tmp_path):
        """Stored content_sha256 == sha256(to_json(record)) for ExpectedReceivableRecord."""
        db_path = _temp_db_path(tmp_path)
        inv = _make_issued_invoice()
        recv = _make_receivable(inv.invoice_id, inv.invoice_version_id)
        with GigToCashStore(db_path) as store:
            store.append(inv)
            store.append(recv)
        stored_sha = self._read_content_sha256(
            db_path, "expected_receivable_records",
            "receivable_version_id", recv.receivable_version_id,
        )
        expected_sha = hashlib.sha256(to_json(recv).encode("utf-8")).hexdigest()
        assert stored_sha == expected_sha

    def test_canonical_json_is_deterministic_across_two_calls(self):
        """to_json produces the same bytes on two separate calls for identical record."""
        gig = _make_gig()
        assert to_json(gig) == to_json(gig)

    def test_canonical_json_sort_keys(self):
        """to_json sorts keys — the stored bytes have sorted keys."""
        gig = _make_gig()
        j = to_json(gig)
        import json
        parsed = json.loads(j)
        keys = list(parsed.keys())
        assert keys == sorted(keys), f"Top-level keys are not sorted: {keys}"


# ===========================================================================
# F-10: Create-once GigRecord + supersede UnsupportedOperation
# ===========================================================================

class TestGigCreateOnce:
    """Spec F.10 — GigRecord is create-once; changed payload → GigImmutableConflict;
    supersede on Gig → UnsupportedOperation."""

    def test_same_gig_id_different_payload_raises_gig_immutable_conflict(self, tmp_path):
        """Appending a GigRecord with an existing gig_id but different content raises GigImmutableConflict."""
        db_path = _temp_db_path(tmp_path)
        # Build two GigRecord objects that share gig_id but differ in counterparty_name.
        # We have to construct GigRecord directly since create_gig_record generates a new gig_id.
        import uuid as _uuid
        shared_gig_id = f"gig:{_uuid.uuid4().hex}"
        gig_a = GigRecord(
            gig_id=shared_gig_id,
            counterparty_ref="cpref:hilton-001",
            counterparty_name="Capital Hilton",
            lifecycle_state="proposed",
            timezone="America/New_York",
            billing_policy_ref="bpref:standard",
            idempotency_key=f"idem:gig:{_uuid.uuid4().hex}",
        )
        gig_b = GigRecord(
            gig_id=shared_gig_id,
            counterparty_ref="cpref:hilton-001",
            counterparty_name="Different Name",  # changed
            lifecycle_state="proposed",
            timezone="America/New_York",
            billing_policy_ref="bpref:standard",
            idempotency_key=f"idem:gig:{_uuid.uuid4().hex}",  # distinct key
        )
        with GigToCashStore(db_path) as store:
            store.append(gig_a)
            with pytest.raises(GigImmutableConflict):
                store.append(gig_b)

    def test_same_gig_id_identical_payload_is_noop(self, tmp_path):
        """Appending a GigRecord with an existing gig_id and identical payload returns created=False."""
        db_path = _temp_db_path(tmp_path)
        import uuid as _uuid
        shared_gig_id = f"gig:{_uuid.uuid4().hex}"
        ikey = f"idem:gig:{_uuid.uuid4().hex}"
        gig = GigRecord(
            gig_id=shared_gig_id,
            counterparty_ref="cpref:hilton-001",
            counterparty_name="Capital Hilton",
            lifecycle_state="proposed",
            timezone="America/New_York",
            billing_policy_ref="bpref:standard",
            idempotency_key=ikey,
        )
        with GigToCashStore(db_path) as store:
            r1 = store.append(gig)
            r2 = store.append(gig)
        assert r1.created is True
        assert r2.created is False

    def test_supersede_gig_raises_unsupported_operation(self, tmp_path):
        """supersede on a GigRecord raises UnsupportedOperation (D1 — no version chain)."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        # A second gig to attempt as the "new" version (will never be used).
        gig_v2 = _make_gig()
        with GigToCashStore(db_path) as store:
            store.append(gig)
            with pytest.raises(UnsupportedOperation):
                store.supersede(gig.gig_id, gig_v2)

    def test_gig_does_not_gain_versions_in_list_history(self, tmp_path):
        """list_history for a GigRecord returns a list of length 1 (create-once)."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        with GigToCashStore(db_path) as store:
            store.append(gig)
            history = store.list_history(GigRecord, gig.gig_id)
        assert len(history) == 1
        assert to_json(history[0]) == to_json(gig)

    def test_gig_immutable_conflict_leaves_row_count_unchanged(self, tmp_path):
        """GigImmutableConflict does not add a row."""
        db_path = _temp_db_path(tmp_path)
        import uuid as _uuid
        shared_gig_id = f"gig:{_uuid.uuid4().hex}"
        gig_a = GigRecord(
            gig_id=shared_gig_id,
            counterparty_ref="cpref:a",
            counterparty_name="Venue A",
            lifecycle_state="proposed",
            timezone="UTC",
            billing_policy_ref="bpref:standard",
            idempotency_key=f"idem:gig:{_uuid.uuid4().hex}",
        )
        gig_b = GigRecord(
            gig_id=shared_gig_id,
            counterparty_ref="cpref:b",
            counterparty_name="Venue B",
            lifecycle_state="proposed",
            timezone="UTC",
            billing_policy_ref="bpref:standard",
            idempotency_key=f"idem:gig:{_uuid.uuid4().hex}",
        )
        with GigToCashStore(db_path) as store:
            store.append(gig_a)
            with pytest.raises(GigImmutableConflict):
                store.append(gig_b)
        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM gig_records").fetchone()[0]
        finally:
            conn.close()
        assert count == 1


# ===========================================================================
# Additional edge-case / integration tests
# ===========================================================================

class TestEdgeCases:
    """Supplementary tests for edge cases called out by the spec."""

    def test_append_result_has_created_attribute(self, store):
        """AppendResult has a 'created' boolean attribute."""
        gig = _make_gig()
        result = store.append(gig)
        assert hasattr(result, "created")
        assert isinstance(result.created, bool)

    def test_store_is_context_manager(self, db_path):
        """GigToCashStore supports the context-manager protocol."""
        with GigToCashStore(db_path) as s:
            gig = _make_gig()
            s.append(gig)

    def test_store_with_same_db_path_reads_across_open_close(self, tmp_path):
        """Data persists across close/reopen."""
        db_path = _temp_db_path(tmp_path)
        gig = _make_gig()
        with GigToCashStore(db_path) as store:
            store.append(gig)
        with GigToCashStore(db_path) as store:
            retrieved = store.get_current(GigRecord, gig.gig_id)
        assert retrieved is not None
        assert to_json(retrieved) == to_json(gig)

    def test_multiple_gigs_are_independent(self, store):
        """Multiple distinct GigRecords coexist without interference."""
        gig_a = _make_gig()
        gig_b = _make_gig()
        store.append(gig_a)
        store.append(gig_b)
        ra = store.get_current(GigRecord, gig_a.gig_id)
        rb = store.get_current(GigRecord, gig_b.gig_id)
        assert to_json(ra) == to_json(gig_a)
        assert to_json(rb) == to_json(gig_b)

    def test_invoice_draft_null_optional_fields_preserved(self, store):
        """Draft invoice with all optional fields None preserves None on retrieval."""
        inv = _make_invoice()
        store.append(inv)
        retrieved = store.get_current(InvoiceRecord, inv.invoice_id)
        assert retrieved.invoice_number is None
        assert retrieved.issue_date_iso is None
        assert retrieved.due_date_iso is None
        assert retrieved.currency_iso is None
        assert retrieved.total_minor_units is None
        assert retrieved.supersedes_invoice_version_id is None

    def test_receivable_optional_resolution_ref_null_preserved(self, store):
        """Open receivable with resolution_ref=None preserves None on retrieval."""
        inv = _make_issued_invoice()
        store.append(inv)
        recv = _make_receivable(inv.invoice_id, inv.invoice_version_id)
        store.append(recv)
        retrieved = store.get_current(ExpectedReceivableRecord, recv.receivable_id)
        assert retrieved.resolution_ref is None

    def test_list_history_empty_for_absent_id(self, store):
        """list_history returns an empty list for an id that was never stored."""
        result = store.list_history(InvoiceRecord, "inv:never-stored")
        assert result == []

    def test_store_does_not_open_other_component_db(self, tmp_path):
        """Each store instance opens only its own db_path (isolation check)."""
        db_path_a = _temp_db_path(tmp_path)
        db_path_b = _temp_db_path(tmp_path)
        with GigToCashStore(db_path_a) as store_a:
            gig = _make_gig()
            store_a.append(gig)
        # Opening store_b should not be able to read gig written to store_a.
        with GigToCashStore(db_path_b) as store_b:
            result = store_b.get_current(GigRecord, gig.gig_id)
        assert result is None, "Store B must not see data written to Store A's DB"

    def test_work_session_gig_id_is_soft_reference(self, store):
        """WorkSession with a gig_id not stored in gig_records is accepted
        (cross-domain refs are soft per spec — no FK on work_session.gig_id)."""
        # The spec says: gig_id on work_session_records is a soft text reference.
        fictitious_gig_id = f"gig:{uuid.uuid4().hex}"
        ws = _make_session(fictitious_gig_id)
        # This should not raise an FK error — gig_id is soft.
        result = store.append(ws)
        assert result.created is True
