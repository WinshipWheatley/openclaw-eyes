"""
system_catalog_store.py — Unit 1: Metadata Catalog Store / DAL
Spec: SYSTEM-CATALOG-SPEC.md id 20260625-SYSCAT-v1, sections A–F, G Unit 1.

Principles (A):
- Metadata-only: NO business/invoice/PII/message-body data ever stored.
- Append-versioned by scan_id (D1): history retained; current = latest COMPLETE.
- DB path injectable; default per D2.
- read-only discovery: this module itself never writes to any scanned repo.
- Exceptions: MigrationError on schema failure.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MigrationError(Exception):
    """Raised when schema migration fails."""


# ---------------------------------------------------------------------------
# DDL (exact per spec §C)
# ---------------------------------------------------------------------------

_DDL_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INT PRIMARY KEY,
    applied_utc TEXT NOT NULL,
    description TEXT NOT NULL
);
"""

_DDL_CATALOG_SCANS = """
CREATE TABLE IF NOT EXISTS catalog_scans (
    scan_id             TEXT PRIMARY KEY,
    started_utc         TEXT NOT NULL,
    completed_utc       TEXT,
    tool_version        TEXT NOT NULL,
    status              TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETE','PARTIAL','FAILED')),
    repo_count          INT,
    dirty_count         INT,
    coverage_gaps_json  TEXT,
    excluded_paths_json TEXT,
    receipt_json        TEXT
);
"""

_DDL_REPOSITORIES = """
CREATE TABLE IF NOT EXISTS repositories (
    scan_id     TEXT NOT NULL REFERENCES catalog_scans(scan_id),
    repo_path   TEXT NOT NULL,
    branch      TEXT,
    head_commit TEXT,
    dirty       INT NOT NULL DEFAULT 0,
    coverage    TEXT NOT NULL CHECK(coverage IN ('VERIFIED','PARTIAL','UNAVAILABLE')),
    is_root     INT NOT NULL DEFAULT 0,
    UNIQUE(scan_id, repo_path)
);
"""

_DDL_WORKTREES = """
CREATE TABLE IF NOT EXISTS worktrees (
    scan_id       TEXT NOT NULL REFERENCES catalog_scans(scan_id),
    repo_path     TEXT NOT NULL,
    worktree_path TEXT NOT NULL,
    branch        TEXT,
    head_commit   TEXT,
    dirty         INT NOT NULL DEFAULT 0
);
"""

_DDL_COMPONENTS = """
CREATE TABLE IF NOT EXISTS components (
    scan_id      TEXT NOT NULL REFERENCES catalog_scans(scan_id),
    repo_path    TEXT NOT NULL,
    component_id TEXT NOT NULL,
    name         TEXT NOT NULL,
    kind         TEXT,
    source_ref   TEXT
);
"""

_DDL_CAPABILITIES = """
CREATE TABLE IF NOT EXISTS capabilities (
    scan_id       TEXT NOT NULL REFERENCES catalog_scans(scan_id),
    repo_path     TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    name          TEXT NOT NULL,
    status        TEXT,
    source_ref    TEXT
);
"""

_DDL_QUEUES = """
CREATE TABLE IF NOT EXISTS queues (
    scan_id     TEXT NOT NULL REFERENCES catalog_scans(scan_id),
    repo_path   TEXT NOT NULL,
    queue_path  TEXT NOT NULL,
    item_count  INT NOT NULL DEFAULT 0,
    states_json TEXT
);
"""

_DDL_HANDOFFS = """
CREATE TABLE IF NOT EXISTS handoffs (
    scan_id      TEXT NOT NULL REFERENCES catalog_scans(scan_id),
    repo_path    TEXT NOT NULL,
    handoff_path TEXT NOT NULL,
    checkpoint   TEXT,
    updated_utc  TEXT
);
"""

_DDL_TESTS = """
CREATE TABLE IF NOT EXISTS tests (
    scan_id   TEXT NOT NULL REFERENCES catalog_scans(scan_id),
    repo_path TEXT NOT NULL,
    test_path TEXT NOT NULL,
    count     INT NOT NULL DEFAULT 0
);
"""

# Migration table: (version, description, ddl_to_run)
_MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "Initial schema: 8 catalog tables + schema_migrations",
        "\n".join([
            _DDL_CATALOG_SCANS,
            _DDL_REPOSITORIES,
            _DDL_WORKTREES,
            _DDL_COMPONENTS,
            _DDL_CAPABILITIES,
            _DDL_QUEUES,
            _DDL_HANDOFFS,
            _DDL_TESTS,
        ]),
    ),
]


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class SystemCatalogStore:
    """
    Metadata-only catalog DAL backed by SQLite.

    Usage (context manager):
        with SystemCatalogStore("/tmp/test.sqlite3") as store:
            scan_id = store.begin_scan("syscat-v1", "2026-06-25T10:00:00Z")
            store.record_repository(scan_id, "/home/openclaw", "main", "abc123", dirty=False, coverage="VERIFIED", is_root=True)
            store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

    Or explicit open/close:
        store = SystemCatalogStore()
        store.open()
        ...
        store.close()
    """

    DEFAULT_DB_PATH: str = "/home/openclaw/state/system_catalog/system_catalog.sqlite3"

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "SystemCatalogStore":
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Create parent dir if needed, open connection, run idempotent migrations."""
        path = Path(self._db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._run_migrations()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _conn_required(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SystemCatalogStore is not open. Call open() or use as context manager.")
        return self._conn

    def _run_migrations(self) -> None:
        conn = self._conn_required()
        try:
            conn.execute(_DDL_SCHEMA_MIGRATIONS)
            conn.commit()

            applied: set[int] = set()
            for row in conn.execute("SELECT version FROM schema_migrations"):
                applied.add(row[0])

            for version, description, ddl in _MIGRATIONS:
                if version not in applied:
                    try:
                        conn.executescript(ddl)
                        conn.execute(
                            "INSERT INTO schema_migrations(version, applied_utc, description) VALUES (?,?,?)",
                            (version, _utc_now(), description),
                        )
                        conn.commit()
                    except sqlite3.Error as exc:
                        conn.rollback()
                        raise MigrationError(f"Migration v{version} failed: {exc}") from exc
        except MigrationError:
            raise
        except sqlite3.Error as exc:
            raise MigrationError(f"Migration bootstrap failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Scan lifecycle
    # ------------------------------------------------------------------

    def begin_scan(self, tool_version: str, now_iso: str) -> str:
        """
        Insert a catalog_scans row with status='RUNNING'.
        Returns the generated scan_id (immutable once created).

        scan_id format: SYSCAT-<compact-utc>-<short-hash> is generated by
        discovery_scan.generate_scan_id; here we accept an externally-generated
        scan_id if provided via the insert contract.

        Note: The caller (Unit 3 orchestrator) generates the scan_id via
        discovery_scan.generate_scan_id and passes it. To keep Unit 1
        self-contained for testing we also support generating a local scan_id
        when one isn't supplied (begin_scan returns the id it used).
        """
        import hashlib
        compact = now_iso.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")[:14]
        short_hash = hashlib.sha1(f"{tool_version}{now_iso}".encode()).hexdigest()[:8]
        scan_id = f"SYSCAT-{compact}-{short_hash}"
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO catalog_scans(scan_id, started_utc, tool_version, status)
            VALUES (?, ?, ?, 'RUNNING')
            """,
            (scan_id, now_iso, tool_version),
        )
        conn.commit()
        return scan_id

    def begin_scan_with_id(self, scan_id: str, tool_version: str, now_iso: str) -> str:
        """
        Insert a catalog_scans row with an externally-supplied scan_id.
        Used by Unit 3 orchestrator which pre-generates the deterministic scan_id.
        Returns the scan_id.
        """
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO catalog_scans(scan_id, started_utc, tool_version, status)
            VALUES (?, ?, ?, 'RUNNING')
            """,
            (scan_id, now_iso, tool_version),
        )
        conn.commit()
        return scan_id

    def finalize_scan(
        self,
        scan_id: str,
        status: str,
        coverage_gaps: list,
        excluded_paths: list,
        receipt_json: str,
    ) -> None:
        """
        Finalize a scan: set status COMPLETE|PARTIAL|FAILED, completed_utc,
        repo_count, dirty_count (computed from rows), coverage_gaps, excluded_paths,
        receipt_json.

        PARTIAL scans: per spec A4/D9, a PARTIAL scan MUST NOT be promoted as current.
        get_current_scan only returns COMPLETE rows, so this is automatically enforced.
        """
        if status not in ("COMPLETE", "PARTIAL", "FAILED"):
            raise ValueError(f"Invalid finalize status: {status!r}. Must be COMPLETE, PARTIAL, or FAILED.")
        conn = self._conn_required()
        row_counts = conn.execute(
            "SELECT COUNT(*) AS rc, SUM(dirty) AS dc FROM repositories WHERE scan_id=?",
            (scan_id,),
        ).fetchone()
        repo_count = row_counts["rc"] or 0
        dirty_count = row_counts["dc"] or 0
        conn.execute(
            """
            UPDATE catalog_scans
            SET status=?, completed_utc=?, repo_count=?, dirty_count=?,
                coverage_gaps_json=?, excluded_paths_json=?, receipt_json=?
            WHERE scan_id=?
            """,
            (
                status,
                _utc_now(),
                repo_count,
                dirty_count,
                json.dumps(coverage_gaps),
                json.dumps(excluded_paths),
                receipt_json if isinstance(receipt_json, str) else json.dumps(receipt_json),
                scan_id,
            ),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Record writers (scan-scoped; metadata-only)
    # ------------------------------------------------------------------

    def record_repository(
        self,
        scan_id: str,
        repo_path: str,
        branch: str,
        head_commit: str,
        dirty: bool,
        coverage: str,
        is_root: bool = False,
    ) -> None:
        """Insert one repository row. coverage must be VERIFIED|PARTIAL|UNAVAILABLE.

        Spec §C: UNIQUE(scan_id, repo_path) — a duplicate (scan_id, repo_path)
        within a scan is rejected (raises sqlite3.IntegrityError), never silently
        dropped. The synchronizer records each registered repo exactly once per
        scan, so this constraint is a correctness guard, not an idempotency knob.
        """
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO repositories
                (scan_id, repo_path, branch, head_commit, dirty, coverage, is_root)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (scan_id, repo_path, branch, head_commit, int(dirty), coverage, int(is_root)),
        )
        conn.commit()

    def record_worktree(
        self,
        scan_id: str,
        repo_path: str,
        worktree_path: str,
        branch: str,
        head_commit: str,
        dirty: bool,
    ) -> None:
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO worktrees
                (scan_id, repo_path, worktree_path, branch, head_commit, dirty)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (scan_id, repo_path, worktree_path, branch, head_commit, int(dirty)),
        )
        conn.commit()

    def record_component(
        self,
        scan_id: str,
        repo_path: str,
        component_id: str,
        name: str,
        kind: str,
        source_ref: str,
    ) -> None:
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO components
                (scan_id, repo_path, component_id, name, kind, source_ref)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (scan_id, repo_path, component_id, name, kind, source_ref),
        )
        conn.commit()

    def record_capability(
        self,
        scan_id: str,
        repo_path: str,
        capability_id: str,
        name: str,
        status: str,
        source_ref: str,
    ) -> None:
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO capabilities
                (scan_id, repo_path, capability_id, name, status, source_ref)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (scan_id, repo_path, capability_id, name, status, source_ref),
        )
        conn.commit()

    def record_queue(
        self,
        scan_id: str,
        repo_path: str,
        queue_path: str,
        item_count: int,
        states_json: str,
    ) -> None:
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO queues
                (scan_id, repo_path, queue_path, item_count, states_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scan_id, repo_path, queue_path, item_count, states_json),
        )
        conn.commit()

    def record_handoff(
        self,
        scan_id: str,
        repo_path: str,
        handoff_path: str,
        checkpoint: str,
        updated_utc: str,
    ) -> None:
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO handoffs
                (scan_id, repo_path, handoff_path, checkpoint, updated_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scan_id, repo_path, handoff_path, checkpoint, updated_utc),
        )
        conn.commit()

    def record_test(
        self,
        scan_id: str,
        repo_path: str,
        test_path: str,
        count: int,
    ) -> None:
        conn = self._conn_required()
        conn.execute(
            """
            INSERT INTO tests
                (scan_id, repo_path, test_path, count)
            VALUES (?, ?, ?, ?)
            """,
            (scan_id, repo_path, test_path, count),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_current_scan(self) -> dict | None:
        """
        Return the latest catalog_scans row with status=='COMPLETE', or None.

        Per spec §C, §E: Current = latest COMPLETE. PARTIAL/FAILED are NOT promoted.
        History is retained (D1).
        """
        conn = self._conn_required()
        row = conn.execute(
            """
            SELECT * FROM catalog_scans
            WHERE status='COMPLETE'
            ORDER BY started_utc DESC
            LIMIT 1
            """,
        ).fetchone()
        return dict(row) if row else None

    def list_repositories(self, scan_id: str) -> list[dict]:
        return self._list_table("repositories", scan_id)

    def list_worktrees(self, scan_id: str) -> list[dict]:
        return self._list_table("worktrees", scan_id)

    def list_components(self, scan_id: str) -> list[dict]:
        return self._list_table("components", scan_id)

    def list_capabilities(self, scan_id: str) -> list[dict]:
        return self._list_table("capabilities", scan_id)

    def list_queues(self, scan_id: str) -> list[dict]:
        return self._list_table("queues", scan_id)

    def list_handoffs(self, scan_id: str) -> list[dict]:
        return self._list_table("handoffs", scan_id)

    def list_tests(self, scan_id: str) -> list[dict]:
        return self._list_table("tests", scan_id)

    def _list_table(self, table: str, scan_id: str) -> list[dict]:
        # table name is internal; never from user input — safe to interpolate.
        conn = self._conn_required()
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE scan_id=?",  # noqa: S608
            (scan_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Freshness / staleness (spec §E)
    # ------------------------------------------------------------------

    def is_stale(
        self,
        max_age_seconds: int,
        live_head_map: dict | None = None,
        now_iso: str | None = None,
    ) -> bool:
        """
        Return True if:
          (a) there is no COMPLETE scan, OR
          (b) the latest COMPLETE scan is older than max_age_seconds, OR
          (c) any repo in live_head_map has a head_commit or dirty state that
              differs from what is catalogued in the latest COMPLETE scan.

        live_head_map: {repo_path: {"head_commit": str, "dirty": bool}}
        now_iso: injectable for testing; defaults to real UTC now.
        """
        current = self.get_current_scan()
        if current is None:
            return True

        now_dt = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
        scan_dt = _parse_iso(current["started_utc"])
        age_seconds = (now_dt - scan_dt).total_seconds()
        if age_seconds > max_age_seconds:
            return True

        if live_head_map:
            scan_id = current["scan_id"]
            catalogued = {
                r["repo_path"]: r
                for r in self.list_repositories(scan_id)
            }
            for repo_path, live in live_head_map.items():
                cat = catalogued.get(repo_path)
                if cat is None:
                    # A repo that wasn't in the catalog — definitely stale.
                    return True
                live_head = live.get("head_commit")
                live_dirty = live.get("dirty")
                if live_head is not None and cat["head_commit"] != live_head:
                    return True
                if live_dirty is not None and bool(cat["dirty"]) != bool(live_dirty):
                    return True

        return False


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(iso_str: str) -> datetime:
    """Parse ISO-8601 UTC string to aware datetime."""
    # Support both "Z" suffix and "+00:00".
    iso_str = iso_str.rstrip("Z")
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
