"""
SQLite append-only versioned data-access layer for Gig-to-Cash domain records.
Spec: 20260625-G2C006-v1

AUTHORITY BOUNDARY: Pure local persistence of facts only.
NO money movement, payment execution, bank, send, email, Telegram, or network behavior.
"""

from __future__ import annotations

import dataclasses
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, NamedTuple

from ar_expected_receivable_record import ExpectedReceivableRecord
from ar_gig_record import GigRecord
from ar_gig_to_cash_serialization import canonical_sha256, from_json, to_json
from ar_invoice_record import InvoiceRecord
from ar_work_session_record import WorkSessionRecord

# ---------------------------------------------------------------------------
# Canonical default DB path (operator decision D2)
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH = "/home/openclaw/state/gig_to_cash/gig_to_cash.sqlite3"

# ---------------------------------------------------------------------------
# Supported record types
# ---------------------------------------------------------------------------
_SUPPORTED_TYPES = (GigRecord, InvoiceRecord, WorkSessionRecord, ExpectedReceivableRecord)

# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------


class IdempotencyConflict(Exception):
    """Same idempotency_key submitted with a different payload."""


class GigImmutableConflict(Exception):
    """A different payload was submitted for an existing gig_id (create-once D1)."""


class UnsupportedOperation(Exception):
    """Operation not supported for this record type (e.g. supersede on GigRecord)."""


class IntegrityError(Exception):
    """Stored SHA-256 does not match recomputed hash of the stored canonical JSON."""


class MigrationError(Exception):
    """DB schema is at a version newer than this code supports, or migration failed."""


# ---------------------------------------------------------------------------
# AppendResult
# ---------------------------------------------------------------------------


class AppendResult(NamedTuple):
    """Result returned by append() and supersede()."""

    ingestion_seq: int
    idempotency_key: str
    content_sha256: str
    created: bool  # False = idempotent no-op; True = newly written


# ---------------------------------------------------------------------------
# Migration DDL
# ---------------------------------------------------------------------------

_MIGRATION_1_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS gig_records (
        ingestion_seq   INTEGER PRIMARY KEY AUTOINCREMENT,
        ingested_utc    TEXT    NOT NULL,
        canonical_json  TEXT    NOT NULL,
        content_sha256  TEXT    NOT NULL,
        idempotency_key TEXT    NOT NULL UNIQUE,
        lifecycle_state TEXT    NOT NULL,
        gig_id          TEXT    NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS work_session_records (
        ingestion_seq          INTEGER PRIMARY KEY AUTOINCREMENT,
        ingested_utc           TEXT    NOT NULL,
        canonical_json         TEXT    NOT NULL,
        content_sha256         TEXT    NOT NULL,
        idempotency_key        TEXT    NOT NULL UNIQUE,
        lifecycle_state        TEXT    NOT NULL,
        work_session_id        TEXT    NOT NULL,
        gig_id                 TEXT    NOT NULL,
        supersedes_session_id  TEXT    NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ws_work_session_id ON work_session_records (work_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_ws_gig_id ON work_session_records (gig_id)",
    "CREATE INDEX IF NOT EXISTS idx_ws_supersedes_session_id ON work_session_records (supersedes_session_id)",
    """
    CREATE TABLE IF NOT EXISTS invoice_records (
        ingestion_seq                  INTEGER PRIMARY KEY AUTOINCREMENT,
        ingested_utc                   TEXT    NOT NULL,
        canonical_json                 TEXT    NOT NULL,
        content_sha256                 TEXT    NOT NULL,
        idempotency_key                TEXT    NOT NULL UNIQUE,
        lifecycle_state                TEXT    NOT NULL,
        invoice_id                     TEXT    NOT NULL,
        invoice_version_id             TEXT    NOT NULL UNIQUE,
        supersedes_invoice_version_id  TEXT    NULL,
        source_ref                     TEXT    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_inv_invoice_id ON invoice_records (invoice_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_inv_invoice_version_id ON invoice_records (invoice_version_id)",
    """
    CREATE TABLE IF NOT EXISTS expected_receivable_records (
        ingestion_seq                      INTEGER PRIMARY KEY AUTOINCREMENT,
        ingested_utc                       TEXT    NOT NULL,
        canonical_json                     TEXT    NOT NULL,
        content_sha256                     TEXT    NOT NULL,
        idempotency_key                    TEXT    NOT NULL UNIQUE,
        lifecycle_state                    TEXT    NOT NULL,
        receivable_id                      TEXT    NOT NULL,
        receivable_version_id              TEXT    NOT NULL UNIQUE,
        invoice_id                         TEXT    NOT NULL,
        invoice_version_id                 TEXT    NOT NULL,
        supersedes_receivable_version_id   TEXT    NULL,
        source_ref                         TEXT    NOT NULL,
        FOREIGN KEY (invoice_version_id)
            REFERENCES invoice_records (invoice_version_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_recv_receivable_id ON expected_receivable_records (receivable_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_recv_receivable_version_id ON expected_receivable_records (receivable_version_id)",
]

_MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (
        1,
        "Initial schema: gig_records, work_session_records, invoice_records, expected_receivable_records",
        _MIGRATION_1_STATEMENTS,
    ),
]

# The highest migration version this code supports.
_MAX_SUPPORTED_VERSION = max(m[0] for m in _MIGRATIONS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verify_sha256(row_json: str, row_sha: str) -> None:
    """Recompute SHA-256 of stored canonical_json and compare; raise IntegrityError on mismatch."""
    import hashlib
    recomputed = hashlib.sha256(row_json.encode("utf-8")).hexdigest()
    if recomputed != row_sha:
        raise IntegrityError(
            f"SHA-256 mismatch: stored={row_sha!r}, recomputed={recomputed!r}"
        )


def _reconstruct(row: sqlite3.Row) -> Any:
    """Verify integrity then deserialize a DB row to a domain record."""
    _verify_sha256(row["canonical_json"], row["content_sha256"])
    return from_json(row["canonical_json"])


# ---------------------------------------------------------------------------
# GigToCashStore
# ---------------------------------------------------------------------------


class GigToCashStore:
    """
    Append-only, versioned SQLite store for Gig-to-Cash domain records.

    Usage (context manager):
        with GigToCashStore(db_path) as store:
            result = store.append(record)

    Or manual open/close:
        store = GigToCashStore(db_path)
        store.open()
        ...
        store.close()
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> "GigToCashStore":
        """Open the DB, create parent dir if needed, apply pending migrations."""
        parent = os.path.dirname(self._db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self._conn = sqlite3.connect(self._db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._apply_migrations()
        return self

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "GigToCashStore":
        return self.open()

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Migrations
    # ------------------------------------------------------------------

    def _apply_migrations(self) -> None:
        """
        Apply any pending schema migrations idempotently.

        IMPORTANT: We use isolation_level=None (autocommit) on the connection,
        so we manage transactions explicitly with BEGIN/COMMIT/ROLLBACK via execute().
        We deliberately avoid executescript() because it issues an implicit COMMIT,
        breaking our transaction control.
        """
        conn = self._conn
        assert conn is not None

        # Bootstrap: ensure schema_migrations exists.  Done in its own transaction.
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version     INTEGER PRIMARY KEY,
                    applied_utc TEXT    NOT NULL,
                    description TEXT    NOT NULL
                )
                """
            )
            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise MigrationError(f"Failed to bootstrap schema_migrations: {exc}") from exc

        # Read applied versions (outside a transaction — read-only).
        applied = {
            row[0]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }

        # Detect DB schema ahead of code.
        if applied:
            max_applied = max(applied)
            if max_applied > _MAX_SUPPORTED_VERSION:
                raise MigrationError(
                    f"DB schema version {max_applied} exceeds the maximum "
                    f"version this code supports ({_MAX_SUPPORTED_VERSION}). "
                    "Upgrade the code before opening this DB."
                )

        # Apply each pending migration in its own transaction.
        for version, description, statements in _MIGRATIONS:
            if version in applied:
                continue  # idempotent skip

            conn.execute("BEGIN IMMEDIATE")
            try:
                for stmt in statements:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_utc, description) VALUES (?, ?, ?)",
                    (version, _utc_now_iso(), description),
                )
                conn.execute("COMMIT")
            except Exception as exc:
                conn.execute("ROLLBACK")
                raise MigrationError(f"Migration {version} failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, record: Any) -> AppendResult:
        """
        Append a domain record to the store.

        Returns AppendResult(created=True) on fresh insert.
        Returns AppendResult(created=False) on idempotent no-op (identical payload).
        Raises:
          TypeError          — unsupported record type
          IdempotencyConflict — same idempotency_key, different content
          GigImmutableConflict — different payload for existing gig_id (D1)
          IntegrityError     — referential (FK) violation OR version_id/gig_id uniqueness clash
        """
        if not isinstance(record, _SUPPORTED_TYPES):
            raise TypeError(f"Unsupported record type: {type(record).__name__!r}")

        conn = self._conn
        assert conn is not None

        canonical = to_json(record)
        sha = canonical_sha256(record)
        ikey = record.idempotency_key
        now = _utc_now_iso()

        conn.execute("BEGIN IMMEDIATE;")
        try:
            result = self._insert_record(conn, record, canonical, sha, ikey, now)
            conn.execute("COMMIT;")
            return result
        except (IdempotencyConflict, GigImmutableConflict, TypeError):
            conn.execute("ROLLBACK;")
            raise
        except sqlite3.IntegrityError as exc:
            conn.execute("ROLLBACK;")
            msg = str(exc)
            # Do NOT conflate referential / uniqueness failures with idempotency. Only an
            # idempotency_key collision (a race past the explicit pre-check) is an idempotency
            # conflict; FK violations and version_id/gig_id uniqueness clashes are integrity errors.
            if "FOREIGN KEY" in msg:
                raise IntegrityError(
                    f"Referential integrity violated (referenced version does not exist): {exc}"
                ) from exc
            if "UNIQUE" in msg and "idempotency_key" in msg:
                raise IdempotencyConflict(
                    f"idempotency_key already exists (concurrent insert past pre-check): {exc}"
                ) from exc
            raise IntegrityError(
                f"Integrity constraint violated (duplicate version_id / uniqueness): {exc}"
            ) from exc
        except Exception:
            conn.execute("ROLLBACK;")
            raise

    def _insert_record(
        self,
        conn: sqlite3.Connection,
        record: Any,
        canonical: str,
        sha: str,
        ikey: str,
        now: str,
    ) -> AppendResult:
        """Route to per-type insert logic (called inside an open transaction)."""
        if isinstance(record, GigRecord):
            return self._insert_gig(conn, record, canonical, sha, ikey, now)
        elif isinstance(record, WorkSessionRecord):
            return self._insert_work_session(conn, record, canonical, sha, ikey, now)
        elif isinstance(record, InvoiceRecord):
            return self._insert_invoice(conn, record, canonical, sha, ikey, now)
        elif isinstance(record, ExpectedReceivableRecord):
            return self._insert_receivable(conn, record, canonical, sha, ikey, now)
        else:
            raise TypeError(f"No insert handler for {type(record).__name__!r}")

    # --- per-type inserts ---

    def _insert_gig(
        self,
        conn: sqlite3.Connection,
        record: GigRecord,
        canonical: str,
        sha: str,
        ikey: str,
        now: str,
    ) -> AppendResult:
        # Check idempotency_key first.
        existing_by_key = conn.execute(
            "SELECT ingestion_seq, content_sha256, gig_id FROM gig_records WHERE idempotency_key = ?;",
            (ikey,),
        ).fetchone()
        if existing_by_key is not None:
            if existing_by_key["content_sha256"] == sha:
                return AppendResult(
                    ingestion_seq=existing_by_key["ingestion_seq"],
                    idempotency_key=ikey,
                    content_sha256=sha,
                    created=False,
                )
            raise IdempotencyConflict(
                f"idempotency_key={ikey!r} already exists with a different payload."
            )

        # D1: check gig_id uniqueness separately (different payload for same gig_id).
        existing_by_gig_id = conn.execute(
            "SELECT ingestion_seq, content_sha256 FROM gig_records WHERE gig_id = ?;",
            (record.gig_id,),
        ).fetchone()
        if existing_by_gig_id is not None:
            # Different idempotency_key but same gig_id — always a conflict.
            raise GigImmutableConflict(
                f"gig_id={record.gig_id!r} already exists. GigRecord is create-once (D1). "
                "Lifecycle changes require a future gig-version contract."
            )

        conn.execute(
            """
            INSERT INTO gig_records
                (ingested_utc, canonical_json, content_sha256, idempotency_key, lifecycle_state, gig_id)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (now, canonical, sha, ikey, record.lifecycle_state, record.gig_id),
        )
        seq = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
        return AppendResult(ingestion_seq=seq, idempotency_key=ikey, content_sha256=sha, created=True)

    def _insert_work_session(
        self,
        conn: sqlite3.Connection,
        record: WorkSessionRecord,
        canonical: str,
        sha: str,
        ikey: str,
        now: str,
    ) -> AppendResult:
        existing = conn.execute(
            "SELECT ingestion_seq, content_sha256 FROM work_session_records WHERE idempotency_key = ?;",
            (ikey,),
        ).fetchone()
        if existing is not None:
            if existing["content_sha256"] == sha:
                return AppendResult(
                    ingestion_seq=existing["ingestion_seq"],
                    idempotency_key=ikey,
                    content_sha256=sha,
                    created=False,
                )
            raise IdempotencyConflict(
                f"idempotency_key={ikey!r} already exists with a different payload."
            )

        conn.execute(
            """
            INSERT INTO work_session_records
                (ingested_utc, canonical_json, content_sha256, idempotency_key, lifecycle_state,
                 work_session_id, gig_id, supersedes_session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                now, canonical, sha, ikey, record.lifecycle_state,
                record.work_session_id, record.gig_id, record.supersedes_session_id,
            ),
        )
        seq = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
        return AppendResult(ingestion_seq=seq, idempotency_key=ikey, content_sha256=sha, created=True)

    def _insert_invoice(
        self,
        conn: sqlite3.Connection,
        record: InvoiceRecord,
        canonical: str,
        sha: str,
        ikey: str,
        now: str,
    ) -> AppendResult:
        existing = conn.execute(
            "SELECT ingestion_seq, content_sha256 FROM invoice_records WHERE idempotency_key = ?;",
            (ikey,),
        ).fetchone()
        if existing is not None:
            if existing["content_sha256"] == sha:
                return AppendResult(
                    ingestion_seq=existing["ingestion_seq"],
                    idempotency_key=ikey,
                    content_sha256=sha,
                    created=False,
                )
            raise IdempotencyConflict(
                f"idempotency_key={ikey!r} already exists with a different payload."
            )

        conn.execute(
            """
            INSERT INTO invoice_records
                (ingested_utc, canonical_json, content_sha256, idempotency_key, lifecycle_state,
                 invoice_id, invoice_version_id, supersedes_invoice_version_id, source_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                now, canonical, sha, ikey, record.lifecycle_state,
                record.invoice_id, record.invoice_version_id,
                record.supersedes_invoice_version_id, record.source_ref,
            ),
        )
        seq = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
        return AppendResult(ingestion_seq=seq, idempotency_key=ikey, content_sha256=sha, created=True)

    def _insert_receivable(
        self,
        conn: sqlite3.Connection,
        record: ExpectedReceivableRecord,
        canonical: str,
        sha: str,
        ikey: str,
        now: str,
    ) -> AppendResult:
        existing = conn.execute(
            "SELECT ingestion_seq, content_sha256 FROM expected_receivable_records WHERE idempotency_key = ?;",
            (ikey,),
        ).fetchone()
        if existing is not None:
            if existing["content_sha256"] == sha:
                return AppendResult(
                    ingestion_seq=existing["ingestion_seq"],
                    idempotency_key=ikey,
                    content_sha256=sha,
                    created=False,
                )
            raise IdempotencyConflict(
                f"idempotency_key={ikey!r} already exists with a different payload."
            )

        conn.execute(
            """
            INSERT INTO expected_receivable_records
                (ingested_utc, canonical_json, content_sha256, idempotency_key, lifecycle_state,
                 receivable_id, receivable_version_id, invoice_id, invoice_version_id,
                 supersedes_receivable_version_id, source_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                now, canonical, sha, ikey, record.lifecycle_state,
                record.receivable_id, record.receivable_version_id,
                record.invoice_id, record.invoice_version_id,
                record.supersedes_receivable_version_id, record.source_ref,
            ),
        )
        seq = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
        return AppendResult(ingestion_seq=seq, idempotency_key=ikey, content_sha256=sha, created=True)

    # ------------------------------------------------------------------

    def get_current(self, record_type: type, logical_id: str) -> Any | None:
        """
        Return the current (non-superseded) snapshot for the given type and logical ID.
        Returns None if no record exists.

        logical_id:
          GigRecord           → gig_id
          WorkSessionRecord   → work_session_id
          InvoiceRecord       → invoice_id
          ExpectedReceivable  → receivable_id
        """
        conn = self._conn
        assert conn is not None

        if record_type is GigRecord:
            row = conn.execute(
                "SELECT canonical_json, content_sha256 FROM gig_records WHERE gig_id = ?;",
                (logical_id,),
            ).fetchone()
            return _reconstruct(row) if row else None

        elif record_type is WorkSessionRecord:
            # Correction-pointer model (spec §C.2): the chain is linked by
            # supersedes_session_id, and each correction has a NEW work_session_id.
            # The logical_id is any session id in the chain (typically the root);
            # "current" is the tip reached by walking supersedes pointers forward.
            row = self._work_session_chain_tip(conn, logical_id)
            return _reconstruct(row) if row else None

        elif record_type is InvoiceRecord:
            # Current = invoice_version_id that is NOT referenced by any supersedes_invoice_version_id
            row = conn.execute(
                """
                SELECT canonical_json, content_sha256
                FROM invoice_records
                WHERE invoice_id = ?
                  AND invoice_version_id NOT IN (
                      SELECT supersedes_invoice_version_id
                      FROM invoice_records
                      WHERE supersedes_invoice_version_id IS NOT NULL
                  )
                ORDER BY ingestion_seq DESC
                LIMIT 1;
                """,
                (logical_id,),
            ).fetchone()
            return _reconstruct(row) if row else None

        elif record_type is ExpectedReceivableRecord:
            # Current = receivable_version_id not referenced by any supersedes_receivable_version_id
            row = conn.execute(
                """
                SELECT canonical_json, content_sha256
                FROM expected_receivable_records
                WHERE receivable_id = ?
                  AND receivable_version_id NOT IN (
                      SELECT supersedes_receivable_version_id
                      FROM expected_receivable_records
                      WHERE supersedes_receivable_version_id IS NOT NULL
                  )
                ORDER BY ingestion_seq DESC
                LIMIT 1;
                """,
                (logical_id,),
            ).fetchone()
            return _reconstruct(row) if row else None

        else:
            raise TypeError(f"Unsupported record type for get_current: {record_type!r}")

    def get_version(self, record_type: type, version_id: str) -> Any | None:
        """
        Return a specific version by version_id for versioned types.
        Raises TypeError for GigRecord (no version semantics).
        Returns None if the version_id is not found.
        """
        conn = self._conn
        assert conn is not None

        if record_type is GigRecord:
            raise TypeError(
                "GigRecord has no version chain (create-once D1). Use get_current(GigRecord, gig_id) instead."
            )
        elif record_type is InvoiceRecord:
            row = conn.execute(
                "SELECT canonical_json, content_sha256 FROM invoice_records WHERE invoice_version_id = ?;",
                (version_id,),
            ).fetchone()
            return _reconstruct(row) if row else None
        elif record_type is ExpectedReceivableRecord:
            row = conn.execute(
                "SELECT canonical_json, content_sha256 FROM expected_receivable_records WHERE receivable_version_id = ?;",
                (version_id,),
            ).fetchone()
            return _reconstruct(row) if row else None
        elif record_type is WorkSessionRecord:
            # WorkSession uses correction-pointer model; version_id = work_session_id
            row = conn.execute(
                "SELECT canonical_json, content_sha256 FROM work_session_records WHERE work_session_id = ? ORDER BY ingestion_seq ASC LIMIT 1;",
                (version_id,),
            ).fetchone()
            return _reconstruct(row) if row else None
        else:
            raise TypeError(f"Unsupported record type for get_version: {record_type!r}")

    def list_history(self, record_type: type, logical_id: str) -> list[Any]:
        """
        Return the full append-only chain for the given type and logical ID,
        ordered oldest → newest (by ingestion_seq).
        """
        conn = self._conn
        assert conn is not None

        if record_type is GigRecord:
            rows = conn.execute(
                "SELECT canonical_json, content_sha256 FROM gig_records WHERE gig_id = ? ORDER BY ingestion_seq ASC;",
                (logical_id,),
            ).fetchall()
        elif record_type is WorkSessionRecord:
            # Correction-pointer chain (spec §C.2/§D.4): walk supersedes pointers
            # forward from the given (root) session id, oldest→newest.
            rows = self._work_session_chain_rows(conn, logical_id)
        elif record_type is InvoiceRecord:
            rows = conn.execute(
                "SELECT canonical_json, content_sha256 FROM invoice_records WHERE invoice_id = ? ORDER BY ingestion_seq ASC;",
                (logical_id,),
            ).fetchall()
        elif record_type is ExpectedReceivableRecord:
            rows = conn.execute(
                "SELECT canonical_json, content_sha256 FROM expected_receivable_records WHERE receivable_id = ? ORDER BY ingestion_seq ASC;",
                (logical_id,),
            ).fetchall()
        else:
            raise TypeError(f"Unsupported record type for list_history: {record_type!r}")

        return [_reconstruct(row) for row in rows]

    def supersede(self, prior_logical_id: str, new_record: Any) -> AppendResult:
        """
        Append a superseding version of an existing record.

        Raises:
          UnsupportedOperation — for GigRecord (lifecycle changes deferred to future contract)
          TypeError            — unsupported record type
          ValueError           — invalid supersede linkage (wrong logical_id or wrong pointer)
        """
        if isinstance(new_record, GigRecord):
            raise UnsupportedOperation(
                "supersede() is not supported for GigRecord. "
                "Gig lifecycle changes await a future contract with gig_version_id (D1)."
            )
        if not isinstance(new_record, _SUPPORTED_TYPES):
            raise TypeError(f"Unsupported record type: {type(new_record).__name__!r}")

        conn = self._conn
        assert conn is not None

        conn.execute("BEGIN IMMEDIATE;")
        try:
            result = self._supersede_inner(conn, prior_logical_id, new_record)
            conn.execute("COMMIT;")
            return result
        except (UnsupportedOperation, TypeError, ValueError, IdempotencyConflict):
            conn.execute("ROLLBACK;")
            raise
        except sqlite3.IntegrityError as exc:
            conn.execute("ROLLBACK;")
            raise IdempotencyConflict(
                f"Integrity constraint violated during supersede: {exc}"
            ) from exc
        except Exception:
            conn.execute("ROLLBACK;")
            raise

    def _supersede_inner(
        self, conn: sqlite3.Connection, prior_logical_id: str, new_record: Any
    ) -> AppendResult:
        """Validate supersede linkage then delegate to append inside an open transaction."""
        if isinstance(new_record, WorkSessionRecord):
            # Correction-pointer model (spec §C.2/§D.5): a correction is a NEW
            # work_session_id whose supersedes_session_id points at the CURRENT
            # tip of the chain identified by prior_logical_id. The new record's
            # own work_session_id is necessarily different, so the only linkage
            # check the spec requires is supersedes_session_id == current id.
            current = self._get_current_work_session_in_tx(conn, prior_logical_id)
            if current is None:
                raise ValueError(
                    f"No current WorkSession found for work_session_id={prior_logical_id!r}"
                )
            if new_record.supersedes_session_id != current.work_session_id:
                raise ValueError(
                    f"new_record.supersedes_session_id={new_record.supersedes_session_id!r} "
                    f"must equal current.work_session_id={current.work_session_id!r}"
                )

        elif isinstance(new_record, InvoiceRecord):
            if new_record.invoice_id != prior_logical_id:
                raise ValueError(
                    f"new_record.invoice_id={new_record.invoice_id!r} "
                    f"does not match prior_logical_id={prior_logical_id!r}"
                )
            current = self._get_current_invoice_in_tx(conn, prior_logical_id)
            if current is None:
                raise ValueError(
                    f"No current Invoice found for invoice_id={prior_logical_id!r}"
                )
            if new_record.supersedes_invoice_version_id != current.invoice_version_id:
                raise ValueError(
                    f"new_record.supersedes_invoice_version_id={new_record.supersedes_invoice_version_id!r} "
                    f"must equal current.invoice_version_id={current.invoice_version_id!r}"
                )

        elif isinstance(new_record, ExpectedReceivableRecord):
            if new_record.receivable_id != prior_logical_id:
                raise ValueError(
                    f"new_record.receivable_id={new_record.receivable_id!r} "
                    f"does not match prior_logical_id={prior_logical_id!r}"
                )
            current = self._get_current_receivable_in_tx(conn, prior_logical_id)
            if current is None:
                raise ValueError(
                    f"No current ExpectedReceivable found for receivable_id={prior_logical_id!r}"
                )
            if new_record.supersedes_receivable_version_id != current.receivable_version_id:
                raise ValueError(
                    f"new_record.supersedes_receivable_version_id={new_record.supersedes_receivable_version_id!r} "
                    f"must equal current.receivable_version_id={current.receivable_version_id!r}"
                )

        # Delegate actual insert (still inside the BEGIN IMMEDIATE transaction).
        canonical = to_json(new_record)
        sha = canonical_sha256(new_record)
        ikey = new_record.idempotency_key
        now = _utc_now_iso()
        return self._insert_record(conn, new_record, canonical, sha, ikey, now)

    # --- in-transaction helpers (do not open new transactions) ---

    def _get_current_work_session_in_tx(
        self, conn: sqlite3.Connection, work_session_id: str
    ) -> WorkSessionRecord | None:
        row = self._work_session_chain_tip(conn, work_session_id)
        return _reconstruct(row) if row else None

    # --- WorkSession correction-pointer chain walkers (spec §C.2) ---

    def _work_session_chain_rows(
        self, conn: sqlite3.Connection, root_session_id: str
    ) -> list[sqlite3.Row]:
        """
        Walk the correction-pointer chain forward from root_session_id.

        Returns the ordered rows (oldest→newest) for that logical session: the
        root row plus every row that (transitively) supersedes it. Returns an
        empty list if root_session_id is not present.
        """
        root = conn.execute(
            """
            SELECT ingestion_seq, canonical_json, content_sha256,
                   work_session_id, supersedes_session_id
            FROM work_session_records
            WHERE work_session_id = ?
            ORDER BY ingestion_seq ASC
            LIMIT 1;
            """,
            (root_session_id,),
        ).fetchone()
        if root is None:
            return []

        chain: list[sqlite3.Row] = [root]
        seen: set[str] = {root["work_session_id"]}
        current_id = root["work_session_id"]
        while True:
            nxt = conn.execute(
                """
                SELECT ingestion_seq, canonical_json, content_sha256,
                       work_session_id, supersedes_session_id
                FROM work_session_records
                WHERE supersedes_session_id = ?
                ORDER BY ingestion_seq ASC
                LIMIT 1;
                """,
                (current_id,),
            ).fetchone()
            if nxt is None:
                break
            nxt_id = nxt["work_session_id"]
            if nxt_id in seen:  # cycle guard (defensive; should not occur)
                break
            chain.append(nxt)
            seen.add(nxt_id)
            current_id = nxt_id
        return chain

    def _work_session_chain_tip(
        self, conn: sqlite3.Connection, root_session_id: str
    ) -> sqlite3.Row | None:
        """Return the tip (current) row of the correction-pointer chain, or None."""
        chain = self._work_session_chain_rows(conn, root_session_id)
        return chain[-1] if chain else None

    def _get_current_invoice_in_tx(
        self, conn: sqlite3.Connection, invoice_id: str
    ) -> InvoiceRecord | None:
        row = conn.execute(
            """
            SELECT canonical_json, content_sha256
            FROM invoice_records
            WHERE invoice_id = ?
              AND invoice_version_id NOT IN (
                  SELECT supersedes_invoice_version_id
                  FROM invoice_records
                  WHERE supersedes_invoice_version_id IS NOT NULL
              )
            ORDER BY ingestion_seq DESC
            LIMIT 1;
            """,
            (invoice_id,),
        ).fetchone()
        return _reconstruct(row) if row else None

    def _get_current_receivable_in_tx(
        self, conn: sqlite3.Connection, receivable_id: str
    ) -> ExpectedReceivableRecord | None:
        row = conn.execute(
            """
            SELECT canonical_json, content_sha256
            FROM expected_receivable_records
            WHERE receivable_id = ?
              AND receivable_version_id NOT IN (
                  SELECT supersedes_receivable_version_id
                  FROM expected_receivable_records
                  WHERE supersedes_receivable_version_id IS NOT NULL
              )
            ORDER BY ingestion_seq DESC
            LIMIT 1;
            """,
            (receivable_id,),
        ).fetchone()
        return _reconstruct(row) if row else None
