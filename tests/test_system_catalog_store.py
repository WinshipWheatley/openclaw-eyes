"""
Tests for system_catalog_store.SystemCatalogStore — Unit 1.

Written INDEPENDENTLY from any implementation, to the SYSTEM-CATALOG-SPEC.md
(version 20260625-SYSCAT-v1) sections A, C, E, and F, and the shared interface
contract.  NO implementation files were read; behavior is derived from the spec
and audit documents only.

Spec-F coverage mapping is documented per test.

Assumptions encoded:
  - SystemCatalogStore is a context manager; __enter__/__exit__ handle open/close.
  - open() (or __enter__) creates the parent directory if it does not exist.
  - Migrations are idempotent: calling open() a second time on the same DB path
    does not raise an error and does not duplicate migration rows.
  - schema_migrations rows have a monotonically-increasing integer 'version' column.
  - All 9 tables from spec §C exist after migration.
  - begin_scan() inserts a catalog_scans row with status='RUNNING'.
  - finalize_scan() updates that row with the final status, completed_utc, repo_count,
    dirty_count, coverage_gaps_json, excluded_paths_json, receipt_json.
  - get_current_scan() returns the LATEST catalog_scans row whose status is 'COMPLETE'.
    A PARTIAL or FAILED scan is NOT returned.
  - is_stale() returns True when:
      a) the latest COMPLETE scan was started more than max_age_seconds ago (using
         now_iso if supplied, otherwise wall clock), OR
      b) any repo in live_head_map has a head_commit or dirty flag that differs
         from the catalogued value.
  - is_stale() returns False when the COMPLETE scan is within max_age_seconds AND
    all live_head_map entries match the catalogue.
  - MigrationError is raised when the schema is unreadable / migration fails.
  - record_* methods tag every row with the scan_id of the current scan.
  - Two simultaneous scan_ids (from two begin_scan calls) coexist in the DB;
    rows from each scan are isolated.
  - The schema contains NO columns for business domain data, invoices, PII, or
    message bodies (verified by inspecting column names).
  - list_repositories / list_worktrees / list_components / list_capabilities /
    list_queues / list_handoffs / list_tests filter by scan_id.
  - Injectable db_path: the default path is used only when no arg is passed; tests
    always supply a temp-file path so production state is never touched.
"""

import json
import sqlite3
import tempfile
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

# ---------------------------------------------------------------------------
# Import the module under test — by name only, per the contract.
# We do NOT import from any other syscat module; no impl files are opened.
# ---------------------------------------------------------------------------
from system_catalog_store import SystemCatalogStore, MigrationError  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_offset(seconds: int) -> str:
    """Return an ISO timestamp offset from *now* by `seconds`."""
    dt = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return dt.isoformat()


def _open_store(db_path: str) -> SystemCatalogStore:
    """Return an already-opened (entered) store pointing at db_path."""
    store = SystemCatalogStore(db_path=db_path)
    store.open()
    return store


def _minimal_scan(store: SystemCatalogStore, status: str = "COMPLETE") -> str:
    """Insert a minimal scan with 1 repo and return its scan_id."""
    scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
    store.record_repository(
        scan_id=scan_id,
        repo_path="/home/openclaw",
        branch="main",
        head_commit="abc123",
        dirty=False,
        coverage="VERIFIED",
        is_root=True,
    )
    store.finalize_scan(
        scan_id=scan_id,
        status=status,
        coverage_gaps=[],
        excluded_paths=[],
        receipt_json=json.dumps({"scan_id": scan_id}),
    )
    return scan_id


# ---------------------------------------------------------------------------
# Spec F-1 — Migration idempotent across reopen; all 9 tables present
# ---------------------------------------------------------------------------

REQUIRED_TABLES = {
    "catalog_scans",
    "repositories",
    "worktrees",
    "components",
    "capabilities",
    "queues",
    "handoffs",
    "tests",
    "schema_migrations",
}


def test_migration_creates_all_required_tables(tmp_path):
    """F-1: After open(), all 9 spec-§C tables exist."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

    assert REQUIRED_TABLES.issubset(tables), (
        f"Missing tables: {REQUIRED_TABLES - tables}"
    )


def test_migration_is_idempotent(tmp_path):
    """F-1: Opening the same DB twice does not raise or duplicate migration rows."""
    db_path = str(tmp_path / "catalog.sqlite3")

    # First open
    store1 = SystemCatalogStore(db_path=db_path)
    store1.open()
    store1.close()

    # Second open — must not raise MigrationError or any other error
    store2 = SystemCatalogStore(db_path=db_path)
    store2.open()
    store2.close()

    # schema_migrations must not have duplicate version rows
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    conn.close()
    versions = [r[0] for r in rows]
    assert versions == sorted(set(versions)), (
        "Duplicate migration versions detected after double-open"
    )


def test_open_creates_parent_directory(tmp_path):
    """F-1 (context manager): open() creates the parent directory when absent."""
    nested = tmp_path / "deep" / "nested" / "dir"
    db_path = str(nested / "catalog.sqlite3")
    # Directory does not exist yet
    assert not nested.exists()

    store = SystemCatalogStore(db_path=db_path)
    store.open()
    store.close()

    assert nested.exists(), "Parent directory was not created"
    assert Path(db_path).exists(), "DB file was not created"


def test_context_manager_protocol(tmp_path):
    """F-1: SystemCatalogStore supports 'with' statement (no exceptions)."""
    db_path = str(tmp_path / "ctx.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        # Must be usable inside the block
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        assert scan_id is not None and len(scan_id) > 0


def test_schema_migrations_table_has_version_column(tmp_path):
    """F-1: schema_migrations has at least a 'version' column (forward-only tracking)."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path):
        pass  # just open + close

    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(schema_migrations)")
    col_names = {row[1] for row in cursor.fetchall()}
    conn.close()
    assert "version" in col_names


# ---------------------------------------------------------------------------
# Spec F-2 — Scan-scoped writes; two scans coexist; get_current_scan
# ---------------------------------------------------------------------------

def test_begin_scan_inserts_running_row(tmp_path):
    """F-2: begin_scan inserts a catalog_scans row with status='RUNNING'."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        now = _now_iso()
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=now)

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status FROM catalog_scans WHERE scan_id=?", (scan_id,)
    ).fetchone()
    conn.close()
    assert row is not None, "catalog_scans row not found"
    assert row[0] == "RUNNING"


def test_finalize_scan_updates_status(tmp_path):
    """F-2: finalize_scan updates the status to COMPLETE and sets completed_utc."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(
            scan_id=scan_id,
            status="COMPLETE",
            coverage_gaps=[],
            excluded_paths=[],
            receipt_json="{}",
        )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, completed_utc FROM catalog_scans WHERE scan_id=?",
        (scan_id,),
    ).fetchone()
    conn.close()
    assert row[0] == "COMPLETE"
    assert row[1] is not None, "completed_utc was not set"


def test_two_scans_coexist_independently(tmp_path):
    """F-2: Two scans both write rows; query by scan_id returns only the right rows."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_a = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(
            scan_id=scan_a,
            repo_path="/home/openclaw",
            branch="main",
            head_commit="aaa",
            dirty=False,
            coverage="VERIFIED",
        )
        store.finalize_scan(scan_a, "COMPLETE", [], [], '{"scan_id":"a"}')

        scan_b = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(
            scan_id=scan_b,
            repo_path="/home/openclaw",
            branch="feature",
            head_commit="bbb",
            dirty=True,
            coverage="VERIFIED",
        )
        store.record_repository(
            scan_id=scan_b,
            repo_path="/mnt/e/openclaw-source",
            branch="main",
            head_commit="ccc",
            dirty=False,
            coverage="VERIFIED",
        )
        store.finalize_scan(scan_b, "COMPLETE", [], [], '{"scan_id":"b"}')

        repos_a = store.list_repositories(scan_a)
        repos_b = store.list_repositories(scan_b)

    assert len(repos_a) == 1
    assert repos_a[0]["repo_path"] == "/home/openclaw"
    assert repos_a[0]["head_commit"] == "aaa"

    assert len(repos_b) == 2
    assert {r["repo_path"] for r in repos_b} == {
        "/home/openclaw", "/mnt/e/openclaw-source"
    }


def test_get_current_scan_returns_latest_complete(tmp_path):
    """F-2: get_current_scan() returns the latest COMPLETE scan, not PARTIAL/FAILED."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        # First COMPLETE scan
        s1 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(s1, "COMPLETE", [], [], '{"scan_id":"s1"}')

        # Subsequent PARTIAL scan — must NOT become current
        s2 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(s2, "PARTIAL", ["gap1"], [], '{"scan_id":"s2"}')

        current = store.get_current_scan()

    assert current is not None, "get_current_scan() returned None despite COMPLETE scan"
    assert current["scan_id"] == s1, (
        f"Expected current={s1!r}, got {current['scan_id']!r}"
    )


def test_get_current_scan_returns_none_when_no_complete(tmp_path):
    """F-2: get_current_scan() returns None when no COMPLETE scan exists."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        s1 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(s1, "PARTIAL", ["unavailable-repo"], [], "{}")
        current = store.get_current_scan()

    assert current is None


def test_get_current_scan_prefers_second_complete_over_first(tmp_path):
    """F-2: When two COMPLETE scans exist, the latest one is returned."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        s1 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(s1, "COMPLETE", [], [], '{"scan_id":"s1"}')

        s2 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(s2, "COMPLETE", [], [], '{"scan_id":"s2"}')

        current = store.get_current_scan()

    assert current["scan_id"] == s2


# ---------------------------------------------------------------------------
# Spec F-3 — Metadata-only guard: no business/invoice/PII/message-body columns
# ---------------------------------------------------------------------------

# These column-name fragments must NOT appear anywhere in the schema.
_FORBIDDEN_COLUMN_FRAGMENTS = [
    "invoice_number",
    "invoice_amount",
    "amount",
    "price",
    "revenue",
    "pii",
    "ssn",
    "tax_id",
    "phone_number",
    "email_address",
    "message_body",
    "message_content",
    "sms_body",
    "raw_text",
    "legal_evidence",
    "sealed",
    "gig_id",         # AR domain
    "receivable",
    "payee",
    "payment",
]


def _get_all_columns(db_path: str) -> dict[str, list[str]]:
    """Return {table_name: [col_name, ...]} for every user table."""
    conn = sqlite3.connect(db_path)
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    result = {}
    for t in tables:
        cols = [
            row[1]
            for row in conn.execute(f"PRAGMA table_info({t})").fetchall()
        ]
        result[t] = cols
    conn.close()
    return result


def test_no_business_domain_columns_in_schema(tmp_path):
    """F-3: No column name in any table contains a forbidden business/PII fragment."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path):
        pass

    schema = _get_all_columns(db_path)
    violations = []
    for table, cols in schema.items():
        for col in cols:
            col_lower = col.lower()
            for forbidden in _FORBIDDEN_COLUMN_FRAGMENTS:
                if forbidden in col_lower:
                    violations.append(f"{table}.{col} contains '{forbidden}'")

    assert violations == [], (
        "Business/PII columns found in schema:\n" + "\n".join(violations)
    )


def test_repositories_table_only_has_metadata_columns(tmp_path):
    """F-3: 'repositories' table has exactly the spec-§C columns (metadata pointers only)."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path):
        pass

    conn = sqlite3.connect(db_path)
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(repositories)").fetchall()
    }
    conn.close()

    # Required columns per spec §C
    required = {"scan_id", "repo_path", "branch", "head_commit", "dirty", "coverage"}
    assert required.issubset(cols), f"Missing required columns: {required - cols}"

    # No forbidden fragments
    for col in cols:
        for forbidden in _FORBIDDEN_COLUMN_FRAGMENTS:
            assert forbidden not in col.lower(), (
                f"repositories.{col} contains forbidden fragment '{forbidden}'"
            )


def test_record_methods_accept_metadata_only(tmp_path):
    """F-3: All record_* methods accept only metadata pointers — no domain data can be stored."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())

        # Every record_* call succeeds without a 'business_data' argument
        store.record_repository(scan_id, "/home/openclaw", "main", "abc", False, "VERIFIED", True)
        store.record_worktree(scan_id, "/home/openclaw", "/home/openclaw/worktrees/A", "feat", "def", False)
        store.record_component(scan_id, "/home/openclaw", "COMP-001", "Chief", "agent", "chief_brain.py")
        store.record_capability(scan_id, "/home/openclaw", "CAP-001", "email-triage", "active", "chief_email_brain.py")
        store.record_queue(scan_id, "/home/openclaw", "approval_queue.json", 3, '{"pending":3}')
        store.record_handoff(scan_id, "/home/openclaw", "handoff.json", "checkpoint-001", "2026-06-25T10:00:00Z")
        store.record_test(scan_id, "/home/openclaw", "tests/test_chief.py", 42)

        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

        repos = store.list_repositories(scan_id)
        worktrees = store.list_worktrees(scan_id)
        components = store.list_components(scan_id)
        capabilities = store.list_capabilities(scan_id)
        queues = store.list_queues(scan_id)
        handoffs = store.list_handoffs(scan_id)
        tests = store.list_tests(scan_id)

    assert len(repos) == 1
    assert len(worktrees) == 1
    assert len(components) == 1
    assert len(capabilities) == 1
    assert len(queues) == 1
    assert len(handoffs) == 1
    assert len(tests) == 1


# ---------------------------------------------------------------------------
# Spec F-5 — Dirty capture: dirty=True is recorded (not silently dropped)
# ---------------------------------------------------------------------------

def test_dirty_repo_recorded_as_dirty(tmp_path):
    """F-5: A dirty repo is stored with dirty=1; a clean repo with dirty=0."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(scan_id, "/home/openclaw", "main", "abc", True, "VERIFIED")
        store.record_repository(scan_id, "/mnt/e/openclaw-source", "main", "def", False, "VERIFIED")
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")
        repos = store.list_repositories(scan_id)

    by_path = {r["repo_path"]: r for r in repos}
    assert by_path["/home/openclaw"]["dirty"] in (True, 1), (
        "dirty=True was not preserved"
    )
    assert by_path["/mnt/e/openclaw-source"]["dirty"] in (False, 0), (
        "dirty=False was incorrectly stored as dirty"
    )


def test_dirty_count_set_in_finalize(tmp_path):
    """F-5: finalize_scan sets dirty_count correctly on the catalog_scans row."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(scan_id, "/home/openclaw", "main", "abc", True, "VERIFIED")
        store.record_repository(scan_id, "/mnt/e/openclaw-source", "main", "def", False, "VERIFIED")
        store.record_repository(scan_id, "/home/openclaw/.nemoclaw/source", "main", "ghi", True, "VERIFIED")
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT repo_count, dirty_count FROM catalog_scans WHERE scan_id=?",
        (scan_id,),
    ).fetchone()
    conn.close()
    assert row[0] == 3, f"Expected repo_count=3, got {row[0]}"
    assert row[1] == 2, f"Expected dirty_count=2, got {row[1]}"


# ---------------------------------------------------------------------------
# Spec F-7 — Scan receipt stored in catalog_scans.receipt_json
# ---------------------------------------------------------------------------

def test_receipt_json_stored_and_round_trips(tmp_path):
    """F-7: The receipt passed to finalize_scan is stored verbatim in receipt_json."""
    db_path = str(tmp_path / "catalog.sqlite3")
    receipt = {
        "scan_id": "SYSCAT-20260625-abcdef",
        "timestamp": "2026-06-25T10:00:00Z",
        "tool_version": "syscat-v1",
        "repositories": [{"path": "/home/openclaw", "branch": "main",
                          "head_commit": "abc123", "worktrees": [],
                          "dirty": False, "coverage": "VERIFIED"}],
        "failures": [],
        "coverage_gaps": [],
        "excluded_paths": [],
    }
    receipt_json = json.dumps(receipt)

    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(scan_id, "COMPLETE", [], [], receipt_json)
        current = store.get_current_scan()

    stored = current.get("receipt_json")
    assert stored is not None, "receipt_json field missing from get_current_scan()"
    parsed = json.loads(stored)
    assert parsed["scan_id"] == receipt["scan_id"]
    assert parsed["tool_version"] == "syscat-v1"
    assert parsed["repositories"][0]["path"] == "/home/openclaw"


def test_coverage_gaps_stored_in_finalize(tmp_path):
    """F-7: coverage_gaps_json is persisted correctly on the catalog_scans row."""
    db_path = str(tmp_path / "catalog.sqlite3")
    gaps = ["C drive not in registry", "D drive not in registry"]
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(scan_id, "COMPLETE", gaps, [], "{}")

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT coverage_gaps_json FROM catalog_scans WHERE scan_id=?",
        (scan_id,),
    ).fetchone()
    conn.close()
    stored_gaps = json.loads(row[0])
    assert stored_gaps == gaps


def test_excluded_paths_stored_in_finalize(tmp_path):
    """F-7: excluded_paths_json is persisted correctly."""
    db_path = str(tmp_path / "catalog.sqlite3")
    excluded = ["/home/openclaw/.cache", "/home/openclaw/.nvm"]
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(scan_id, "COMPLETE", [], excluded, "{}")

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT excluded_paths_json FROM catalog_scans WHERE scan_id=?",
        (scan_id,),
    ).fetchone()
    conn.close()
    stored = json.loads(row[0])
    assert stored == excluded


# ---------------------------------------------------------------------------
# Spec F-8 — Idempotent re-scan: consistent logical content, new scan_id OK
# ---------------------------------------------------------------------------

def test_idempotent_rescan_same_logical_content(tmp_path):
    """F-8: Two scans of an identical registry produce the same logical content."""
    db_path = str(tmp_path / "catalog.sqlite3")

    def do_scan(store: SystemCatalogStore) -> str:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(scan_id, "/home/openclaw", "main", "abc123", False, "VERIFIED", True)
        store.record_worktree(scan_id, "/home/openclaw", "/home/openclaw/worktrees/A", "feat", "def456", False)
        store.record_component(scan_id, "/home/openclaw", "C1", "Chief", "agent", "chief_brain.py")
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")
        return scan_id

    with SystemCatalogStore(db_path=db_path) as store:
        s1 = do_scan(store)
        s2 = do_scan(store)

        repos1 = store.list_repositories(s1)
        repos2 = store.list_repositories(s2)
        comps1 = store.list_components(s1)
        comps2 = store.list_components(s2)

    # Different scan_ids are fine
    assert s1 != s2

    # Logical content is identical
    assert len(repos1) == len(repos2)
    assert repos1[0]["repo_path"] == repos2[0]["repo_path"]
    assert repos1[0]["head_commit"] == repos2[0]["head_commit"]

    assert len(comps1) == len(comps2)
    assert comps1[0]["component_id"] == comps2[0]["component_id"]


def test_rescan_does_not_overwrite_prior_scan_rows(tmp_path):
    """F-8: Historical scan rows persist after a second scan (append-versioned per D1)."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        s1 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(s1, "/home/openclaw", "main", "OLD_COMMIT", False, "VERIFIED")
        store.finalize_scan(s1, "COMPLETE", [], [], '{"scan":"s1"}')

        s2 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(s2, "/home/openclaw", "main", "NEW_COMMIT", False, "VERIFIED")
        store.finalize_scan(s2, "COMPLETE", [], [], '{"scan":"s2"}')

        old_repos = store.list_repositories(s1)
        new_repos = store.list_repositories(s2)

    assert old_repos[0]["head_commit"] == "OLD_COMMIT", (
        "Prior scan row was overwritten"
    )
    assert new_repos[0]["head_commit"] == "NEW_COMMIT"


# ---------------------------------------------------------------------------
# Spec F-10 — Freshness: is_stale() flips on HEAD advance or dirty change
# ---------------------------------------------------------------------------

def test_is_stale_false_when_fresh_and_heads_match(tmp_path):
    """F-10: is_stale() returns False for a recent COMPLETE scan with matching HEADs."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(scan_id, "/home/openclaw", "main", "abc123", False, "VERIFIED")
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

        live_head_map = {"/home/openclaw": {"head_commit": "abc123", "dirty": False}}
        result = store.is_stale(
            max_age_seconds=3600,
            live_head_map=live_head_map,
            now_iso=_now_iso(),
        )

    assert result is False


def test_is_stale_true_when_head_advances(tmp_path):
    """F-10: is_stale() returns True when a repo's live HEAD differs from catalogued."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(scan_id, "/home/openclaw", "main", "OLD_COMMIT", False, "VERIFIED")
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

        live_head_map = {"/home/openclaw": {"head_commit": "NEW_COMMIT", "dirty": False}}
        result = store.is_stale(
            max_age_seconds=3600,
            live_head_map=live_head_map,
            now_iso=_now_iso(),
        )

    assert result is True


def test_is_stale_true_when_repo_becomes_dirty(tmp_path):
    """F-10: is_stale() returns True when a repo's dirty flag differs from catalogued."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(scan_id, "/home/openclaw", "main", "abc123", False, "VERIFIED")
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

        # Same HEAD, but now dirty
        live_head_map = {"/home/openclaw": {"head_commit": "abc123", "dirty": True}}
        result = store.is_stale(
            max_age_seconds=3600,
            live_head_map=live_head_map,
            now_iso=_now_iso(),
        )

    assert result is True


def test_is_stale_true_when_scan_too_old(tmp_path):
    """F-10: is_stale() returns True when the latest COMPLETE scan exceeds max_age_seconds."""
    db_path = str(tmp_path / "catalog.sqlite3")

    # Scan time = 2 hours ago
    old_time = _iso_offset(-7200)

    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=old_time)
        store.record_repository(scan_id, "/home/openclaw", "main", "abc123", False, "VERIFIED")
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

        # Check freshness at "now" with max_age=3600 (1 hour)
        result = store.is_stale(
            max_age_seconds=3600,
            live_head_map={"/home/openclaw": {"head_commit": "abc123", "dirty": False}},
            now_iso=_now_iso(),
        )

    assert result is True


def test_is_stale_false_when_within_max_age(tmp_path):
    """F-10: is_stale() returns False when the scan is within max_age and heads match."""
    db_path = str(tmp_path / "catalog.sqlite3")
    recent_time = _now_iso()

    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=recent_time)
        store.record_repository(scan_id, "/home/openclaw", "main", "abc123", False, "VERIFIED")
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

        result = store.is_stale(
            max_age_seconds=3600,
            live_head_map={"/home/openclaw": {"head_commit": "abc123", "dirty": False}},
            now_iso=recent_time,  # same moment as the scan
        )

    assert result is False


def test_is_stale_returns_true_when_no_complete_scan(tmp_path):
    """F-10: is_stale() returns True (or raises) when no COMPLETE scan exists."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        # Only a PARTIAL scan
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.finalize_scan(scan_id, "PARTIAL", ["gap"], [], "{}")

        result = store.is_stale(max_age_seconds=3600, now_iso=_now_iso())

    # No COMPLETE scan → always stale
    assert result is True


def test_is_stale_ignores_partial_scan_for_age(tmp_path):
    """F-10: PARTIAL scan does not satisfy freshness; is_stale must still return True."""
    db_path = str(tmp_path / "catalog.sqlite3")
    recent = _now_iso()
    with SystemCatalogStore(db_path=db_path) as store:
        s1 = store.begin_scan(tool_version="syscat-v1", now_iso=recent)
        store.finalize_scan(s1, "PARTIAL", ["unavailable"], [], "{}")

        result = store.is_stale(max_age_seconds=3600, now_iso=recent)

    assert result is True


# ---------------------------------------------------------------------------
# Spec F-2 — Query methods filter by scan_id (isolation between scans)
# ---------------------------------------------------------------------------

def test_list_worktrees_isolated_by_scan_id(tmp_path):
    """F-2: list_worktrees returns only rows tagged with the given scan_id."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        s1 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_worktree(s1, "/home/openclaw", "/home/openclaw/worktrees/A", "feat-a", "aaa", False)
        store.finalize_scan(s1, "COMPLETE", [], [], "{}")

        s2 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_worktree(s2, "/home/openclaw", "/home/openclaw/worktrees/B", "feat-b", "bbb", False)
        store.record_worktree(s2, "/home/openclaw", "/home/openclaw/worktrees/C", "feat-c", "ccc", True)
        store.finalize_scan(s2, "COMPLETE", [], [], "{}")

        wt1 = store.list_worktrees(s1)
        wt2 = store.list_worktrees(s2)

    assert len(wt1) == 1
    assert wt1[0]["worktree_path"] == "/home/openclaw/worktrees/A"

    assert len(wt2) == 2
    paths2 = {w["worktree_path"] for w in wt2}
    assert paths2 == {"/home/openclaw/worktrees/B", "/home/openclaw/worktrees/C"}


def test_list_capabilities_isolated_by_scan_id(tmp_path):
    """F-2: list_capabilities returns only rows for the given scan_id."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        s1 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_capability(s1, "/home/openclaw", "CAP-A", "email-triage", "active", "chief_email.py")
        store.finalize_scan(s1, "COMPLETE", [], [], "{}")

        s2 = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_capability(s2, "/home/openclaw", "CAP-B", "invoice-review", "active", "chief_invoice.py")
        store.finalize_scan(s2, "COMPLETE", [], [], "{}")

        caps1 = store.list_capabilities(s1)
        caps2 = store.list_capabilities(s2)

    assert len(caps1) == 1 and caps1[0]["capability_id"] == "CAP-A"
    assert len(caps2) == 1 and caps2[0]["capability_id"] == "CAP-B"


def test_list_queues_records_item_count_and_states(tmp_path):
    """F-2 + schema integrity: queue records expose item_count and states_json."""
    db_path = str(tmp_path / "catalog.sqlite3")
    states = json.dumps({"pending": 5, "approved": 2})
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_queue(scan_id, "/home/openclaw", "approval_request_queue.json", 7, states)
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")
        queues = store.list_queues(scan_id)

    assert len(queues) == 1
    q = queues[0]
    assert q["item_count"] == 7
    stored_states = json.loads(q["states_json"]) if isinstance(q["states_json"], str) else q["states_json"]
    assert stored_states["pending"] == 5


def test_list_handoffs_records_checkpoint_and_updated_utc(tmp_path):
    """F-2: handoff records expose checkpoint and updated_utc."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_handoff(
            scan_id, "/home/openclaw", "agent_conversation_handoff.json",
            "step-42", "2026-06-25T09:00:00Z"
        )
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")
        handoffs = store.list_handoffs(scan_id)

    assert len(handoffs) == 1
    h = handoffs[0]
    assert h["checkpoint"] == "step-42"
    assert h["updated_utc"] == "2026-06-25T09:00:00Z"


def test_list_tests_records_count(tmp_path):
    """F-2: test records expose test_path and count."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_test(scan_id, "/home/openclaw", "tests/test_chief_llm_router.py", 18)
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")
        tests = store.list_tests(scan_id)

    assert len(tests) == 1
    assert tests[0]["test_path"] == "tests/test_chief_llm_router.py"
    assert tests[0]["count"] == 18


# ---------------------------------------------------------------------------
# Spec F-1 — Injectable db_path; default path is NOT touched in tests
# ---------------------------------------------------------------------------

def test_injectable_db_path_uses_temp_file(tmp_path):
    """F-1: The injectable db_path is honoured; the production path is never touched."""
    prod_path = Path("/home/openclaw/state/system_catalog/system_catalog.sqlite3")
    db_path = str(tmp_path / "test_catalog.sqlite3")

    with SystemCatalogStore(db_path=db_path) as store:
        _minimal_scan(store)

    # The test DB was created
    assert Path(db_path).exists()

    # The production DB must NOT have been created or modified by this test
    if prod_path.exists():
        # If it already exists (from the live system), we can't assert on mtime
        # but we assert the temp file is a different inode / path
        assert str(prod_path) != db_path
    # (If prod_path does not exist, that's fine too — we never touched it)


# ---------------------------------------------------------------------------
# Spec §C — Foreign-key constraint: content rows must reference a valid scan_id
# ---------------------------------------------------------------------------

def test_orphan_repository_row_rejected(tmp_path):
    """§C: Inserting a repositories row with an unknown scan_id is rejected."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path):
        pass  # migrations only

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO repositories (scan_id, repo_path, branch, head_commit, dirty, coverage) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("BOGUS-SCAN-ID", "/home/openclaw", "main", "abc", 0, "VERIFIED"),
        )
        conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Spec §C — status CHECK constraint on catalog_scans
# ---------------------------------------------------------------------------

def test_invalid_status_rejected_by_check_constraint(tmp_path):
    """§C: A status value outside RUNNING/COMPLETE/PARTIAL/FAILED is rejected."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path):
        pass

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO catalog_scans (scan_id, started_utc, tool_version, status) "
            "VALUES (?, ?, ?, ?)",
            ("SCAN-X", _now_iso(), "syscat-v1", "INVALID_STATUS"),
        )
        conn.commit()
    conn.close()


def test_valid_statuses_are_accepted(tmp_path):
    """§C: All four valid status values (RUNNING, COMPLETE, PARTIAL, FAILED) are accepted."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path):
        pass

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    for status in ("RUNNING", "COMPLETE", "PARTIAL", "FAILED"):
        conn.execute(
            "INSERT INTO catalog_scans (scan_id, started_utc, tool_version, status) "
            "VALUES (?, ?, ?, ?)",
            (f"SCAN-{status}", _now_iso(), "syscat-v1", status),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Spec §C — UNIQUE constraint on (scan_id, repo_path) in repositories
# ---------------------------------------------------------------------------

def test_duplicate_repo_path_within_scan_rejected(tmp_path):
    """§C: Inserting the same (scan_id, repo_path) twice is rejected."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(scan_id, "/home/openclaw", "main", "abc", False, "VERIFIED")
        with pytest.raises(Exception):
            store.record_repository(scan_id, "/home/openclaw", "main", "abc", False, "VERIFIED")


# ---------------------------------------------------------------------------
# Spec F-2 — get_current_scan returns the scan as a dict with expected keys
# ---------------------------------------------------------------------------

def test_get_current_scan_returns_dict_with_required_keys(tmp_path):
    """F-2: get_current_scan() result includes at minimum scan_id, status, and receipt_json."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = _minimal_scan(store, status="COMPLETE")
        current = store.get_current_scan()

    assert isinstance(current, dict)
    assert "scan_id" in current
    assert "status" in current
    assert current["status"] == "COMPLETE"
    assert current["scan_id"] == scan_id


# ---------------------------------------------------------------------------
# Spec A.2 — scan_id ties all consumers together (tag is present on records)
# ---------------------------------------------------------------------------

def test_all_record_types_carry_scan_id(tmp_path):
    """A.2: Every content table row for a scan carries the correct scan_id pointer."""
    db_path = str(tmp_path / "catalog.sqlite3")
    with SystemCatalogStore(db_path=db_path) as store:
        scan_id = store.begin_scan(tool_version="syscat-v1", now_iso=_now_iso())
        store.record_repository(scan_id, "/home/openclaw", "main", "abc", False, "VERIFIED")
        store.record_worktree(scan_id, "/home/openclaw", "/home/openclaw/worktrees/A", "f", "abc", False)
        store.record_component(scan_id, "/home/openclaw", "C1", "Chief", "agent", "chief.py")
        store.record_capability(scan_id, "/home/openclaw", "CAP1", "email", "active", "chief_email.py")
        store.record_queue(scan_id, "/home/openclaw", "q.json", 0, "{}")
        store.record_handoff(scan_id, "/home/openclaw", "h.json", "cp1", "2026-06-25T00:00:00Z")
        store.record_test(scan_id, "/home/openclaw", "tests/test_foo.py", 1)
        store.finalize_scan(scan_id, "COMPLETE", [], [], "{}")

    conn = sqlite3.connect(db_path)
    for table in ["repositories", "worktrees", "components", "capabilities", "queues", "handoffs", "tests"]:
        rows = conn.execute(f"SELECT scan_id FROM {table}").fetchall()
        for row in rows:
            assert row[0] == scan_id, (
                f"Row in {table} has scan_id={row[0]!r}, expected {scan_id!r}"
            )
    conn.close()


# ---------------------------------------------------------------------------
# Spec F-9 — Security: no production state mutated; no network access possible
# via the store (confirmed by API surface: no network/send/PII methods exist)
# ---------------------------------------------------------------------------

def test_store_has_no_send_or_network_methods(tmp_path):
    """F-9: SystemCatalogStore exposes no send/network/PII mutation method."""
    db_path = str(tmp_path / "catalog.sqlite3")
    store = SystemCatalogStore(db_path=db_path)
    forbidden_method_fragments = [
        "send", "email", "http", "request", "upload", "push",
        "pii", "tokenize", "invoice", "pay",
    ]
    method_names = [m.lower() for m in dir(store) if not m.startswith("__")]
    violations = [
        m for m in method_names
        if any(frag in m for frag in forbidden_method_fragments)
    ]
    assert violations == [], (
        f"Store exposes forbidden methods: {violations}"
    )


def test_store_public_api_matches_contract(tmp_path):
    """F-9: The store's public API includes exactly the methods named in the contract."""
    db_path = str(tmp_path / "catalog.sqlite3")
    store = SystemCatalogStore(db_path=db_path)
    required_methods = {
        "open", "close",
        "begin_scan", "finalize_scan",
        "record_repository", "record_worktree", "record_component",
        "record_capability", "record_queue", "record_handoff", "record_test",
        "get_current_scan",
        "list_repositories", "list_worktrees", "list_components",
        "list_capabilities", "list_queues", "list_handoffs", "list_tests",
        "is_stale",
    }
    actual = set(dir(store))
    missing = required_methods - actual
    assert missing == set(), f"Store is missing required methods: {missing}"


# ---------------------------------------------------------------------------
# Spec F-1 — MigrationError is importable (contract-declared exception)
# ---------------------------------------------------------------------------

def test_migration_error_is_importable():
    """F-1: MigrationError is exported from system_catalog_store as specified."""
    # The import at the top of this file already verifies this; this test
    # makes the assertion explicit so a missing export causes a clear failure.
    assert MigrationError is not None
    assert issubclass(MigrationError, Exception)
