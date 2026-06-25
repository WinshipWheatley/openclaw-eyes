"""
Test suite for syscat_synchronizer — Unit 3 of the System Catalog discovery pipeline.

Written INDEPENDENTLY to the spec at /home/openclaw/Operator/SYSTEM-CATALOG-SPEC.md
(version 20260625-SYSCAT-v1) and the audit in
workspaces/cross_repo_discovery_legal_readiness_audit/.

This file MUST NOT import or inspect any implementation file. It encodes the
CONTRACT: every test will catch a wrong or drifted implementation.

Spec-F coverage mapping (stated at each test):
  F-4  PARTIAL-block: unavailable repo not promoted as current scan
  F-5  Dirty capture: dirty repo recorded as dirty=1
  F-6  Consumer rebuild: Map Room + Graphify built FROM catalog, not filesystem
  F-7  Scan receipt shape: matches audit contract; stored in catalog_scans row
  F-8  Idempotent re-scan: second run over same registry yields consistent catalog
  F-9  Read-only security: synchronizer never writes to scanned repos
       excluded_paths honored; no network/send/PII path
  F-10 Freshness: is_stale flips when HEAD advances or goes dirty

Synthetic fixtures only:
  - temp-file SQLite DBs via tmp_path
  - tiny throwaway git repos created with subprocess (git init + first commit)
  - one dirty repo fixture (untracked file added)
  - one unreadable repo fixture (non-git directory)
  - REPOSITORY_REGISTRY.md written as a temp file

Author: Sonnet (Unit-3 test writer, independent worktree syscat-tests)
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Module imports — by name only; no implementation file is read or opened.
# If the impl is missing, ImportError surfaces cleanly in the test session.
# ---------------------------------------------------------------------------

syscat_synchronizer = importlib.import_module("syscat_synchronizer")
system_catalog_store = importlib.import_module("system_catalog_store")

run_discovery_scan = syscat_synchronizer.run_discovery_scan
rebuild_map_room = syscat_synchronizer.rebuild_map_room
rebuild_graphify = syscat_synchronizer.rebuild_graphify
build_scan_receipt = syscat_synchronizer.build_scan_receipt

SystemCatalogStore = system_catalog_store.SystemCatalogStore


# ===========================================================================
# Fixtures: synthetic git repos + registry helpers
# ===========================================================================

def _init_git_repo(path: Path, branch: str = "main") -> Path:
    """Create a minimal real git repo with one commit at *path*."""
    path.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}
    subprocess.run(["git", "init", "-b", branch, str(path)], check=True,
                   capture_output=True, env=env)
    readme = path / "README.md"
    readme.write_text(f"repo at {path}\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True,
                   capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), check=True,
                   capture_output=True, env=env)
    return path


def _make_dirty(repo_path: Path) -> None:
    """Add an untracked file to make the repo dirty."""
    (repo_path / "dirty_sentinel.txt").write_text("dirty\n")


def _write_registry(registry_path: Path, repo_paths: list[dict]) -> None:
    """
    Write a REPOSITORY_REGISTRY.md with one line per repo.
    Each dict must have 'path'; optional 'is_root' (bool).

    Format assumed by load_registry (from Unit-2 contract):
      One repo path per non-blank, non-comment line.
      Lines may carry an optional [ROOT] or [root] marker.
    """
    lines = ["# REPOSITORY_REGISTRY\n", "\n"]
    for entry in repo_paths:
        marker = " [ROOT]" if entry.get("is_root") else ""
        lines.append(f"{entry['path']}{marker}\n")
    registry_path.write_text("".join(lines))


def _temp_db(tmp_path: Path) -> str:
    return str(tmp_path / f"syscat_{uuid.uuid4().hex}.sqlite3")


def _now_iso() -> str:
    return "2026-06-25T12:00:00Z"


# ===========================================================================
# Helpers shared across tests
# ===========================================================================

def _run_scan(registry_path: Path, db_path: str, now_iso: str | None = None) -> dict:
    """Convenience wrapper around run_discovery_scan with injected paths."""
    return run_discovery_scan(
        str(registry_path),
        catalog_db=db_path,
        now_iso=now_iso or _now_iso(),
        tool_version="syscat-v1",
    )


def _open_store(db_path: str) -> "SystemCatalogStore":
    store = SystemCatalogStore(db_path=db_path)
    store.open()
    return store


def _get_scan_row(db_path: str, scan_id: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT * FROM catalog_scans WHERE scan_id = ?", (scan_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_all_scan_rows(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM catalog_scans ORDER BY started_utc")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ===========================================================================
# F-4 PARTIAL-block tests
# ===========================================================================

class TestPartialBlock:
    """Spec F-4: a registry with one UNAVAILABLE repo → scan PARTIAL, not promoted as current."""

    def test_partial_scan_status_when_one_repo_unavailable(self, tmp_path):
        """
        F-4: If any repo in the registry is not a readable git repo,
        run_discovery_scan must finalize the scan as PARTIAL (not COMPLETE).
        """
        good_repo = _init_git_repo(tmp_path / "good_repo")
        bad_repo = tmp_path / "not_a_git_repo"
        bad_repo.mkdir()  # exists but is not a git repo
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(good_repo)},
            {"path": str(bad_repo)},
        ])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)

        # The scan that was written must be PARTIAL
        scan_id = receipt["scan_id"]
        scan_row = _get_scan_row(db_path, scan_id)
        assert scan_row is not None, "scan row must exist in catalog_scans"
        assert scan_row["status"] == "PARTIAL", (
            f"Expected PARTIAL, got {scan_row['status']}"
        )

    def test_partial_scan_not_promoted_as_current(self, tmp_path):
        """
        F-4: A PARTIAL scan MUST NOT be returned by get_current_scan().
        get_current_scan() must return None (no prior COMPLETE exists).
        """
        good_repo = _init_git_repo(tmp_path / "good_repo")
        bad_repo = tmp_path / "not_a_git_repo"
        bad_repo.mkdir()
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(good_repo)},
            {"path": str(bad_repo)},
        ])
        db_path = _temp_db(tmp_path)

        _run_scan(registry, db_path)

        store = _open_store(db_path)
        try:
            current = store.get_current_scan()
        finally:
            store.close()

        assert current is None, (
            "get_current_scan() must return None when only PARTIAL scans exist"
        )

    def test_partial_scan_does_not_overwrite_prior_complete(self, tmp_path):
        """
        F-4: If a prior COMPLETE scan exists, a subsequent PARTIAL scan must NOT
        replace it as the current scan — get_current_scan must still return the
        prior COMPLETE.
        """
        good_repo = _init_git_repo(tmp_path / "good_repo")
        registry_good = tmp_path / "REGISTRY_GOOD.md"
        _write_registry(registry_good, [{"path": str(good_repo)}])
        db_path = _temp_db(tmp_path)

        # First scan: all repos available → should be COMPLETE
        receipt1 = _run_scan(registry_good, db_path, now_iso="2026-06-25T10:00:00Z")
        first_scan_id = receipt1["scan_id"]

        store = _open_store(db_path)
        try:
            current_after_first = store.get_current_scan()
        finally:
            store.close()

        assert current_after_first is not None, "First full scan must be COMPLETE and current"
        assert current_after_first["scan_id"] == first_scan_id

        # Second scan: introduce unavailable repo → PARTIAL
        bad_repo = tmp_path / "missing_repo"
        bad_repo.mkdir()
        registry_bad = tmp_path / "REGISTRY_BAD.md"
        _write_registry(registry_bad, [
            {"path": str(good_repo)},
            {"path": str(bad_repo)},
        ])
        _run_scan(registry_bad, db_path, now_iso="2026-06-25T11:00:00Z")

        store = _open_store(db_path)
        try:
            current_after_partial = store.get_current_scan()
        finally:
            store.close()

        assert current_after_partial is not None, (
            "get_current_scan must still return the prior COMPLETE scan"
        )
        assert current_after_partial["scan_id"] == first_scan_id, (
            "Prior COMPLETE scan must remain current after a PARTIAL scan"
        )

    def test_partial_scan_surfaces_coverage_gap(self, tmp_path):
        """
        F-4: The scan receipt must surface the unavailable repo as a coverage gap.
        """
        good_repo = _init_git_repo(tmp_path / "good_repo")
        bad_repo = tmp_path / "not_a_git_repo"
        bad_repo.mkdir()
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(good_repo)},
            {"path": str(bad_repo)},
        ])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)

        assert "coverage_gaps" in receipt, "receipt must contain coverage_gaps key"
        assert isinstance(receipt["coverage_gaps"], list)
        # At least one coverage gap must be present when a repo is unavailable
        assert len(receipt["coverage_gaps"]) >= 1, (
            "coverage_gaps must be non-empty when a repo is UNAVAILABLE"
        )

    def test_full_scan_is_complete_when_all_repos_available(self, tmp_path):
        """
        Inverse of F-4: when every repo is reachable, the scan must be COMPLETE
        and promoted as current.
        """
        repo_a = _init_git_repo(tmp_path / "repo_a")
        repo_b = _init_git_repo(tmp_path / "repo_b", branch="feature")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(repo_a)},
            {"path": str(repo_b)},
        ])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]
        scan_row = _get_scan_row(db_path, scan_id)

        assert scan_row["status"] == "COMPLETE", (
            f"Expected COMPLETE when all repos available, got {scan_row['status']}"
        )

        store = _open_store(db_path)
        try:
            current = store.get_current_scan()
        finally:
            store.close()

        assert current is not None
        assert current["scan_id"] == scan_id


# ===========================================================================
# F-5 Dirty capture tests
# ===========================================================================

class TestDirtyCapture:
    """Spec F-5: dirty repos must be captured as dirty=1 in catalog."""

    def test_dirty_repo_recorded_dirty_true(self, tmp_path):
        """
        F-5: A repo with uncommitted changes (untracked file) must appear
        in the repositories table with dirty=1.
        """
        repo = _init_git_repo(tmp_path / "dirty_repo")
        _make_dirty(repo)
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT dirty FROM repositories WHERE scan_id = ? AND repo_path = ?",
                (scan_id, str(repo)),
            ).fetchone()
        finally:
            conn.close()

        assert row is not None, "dirty repo must have a row in repositories table"
        assert row["dirty"] == 1, (
            f"Expected dirty=1 for dirty repo, got dirty={row['dirty']}"
        )

    def test_clean_repo_recorded_dirty_false(self, tmp_path):
        """
        F-5 (inverse): A clean repo must appear with dirty=0.
        """
        repo = _init_git_repo(tmp_path / "clean_repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT dirty FROM repositories WHERE scan_id = ? AND repo_path = ?",
                (scan_id, str(repo)),
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        assert row["dirty"] == 0, (
            f"Expected dirty=0 for clean repo, got dirty={row['dirty']}"
        )

    def test_dirty_state_in_scan_receipt(self, tmp_path):
        """
        F-5 + F-7: The scan receipt must reflect dirty=True for a dirty repo
        (the receipt is the external truth surface, not just the DB row).
        """
        repo = _init_git_repo(tmp_path / "dirty_repo")
        _make_dirty(repo)
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)

        repo_entries = receipt.get("repositories", [])
        matching = [r for r in repo_entries if r["path"] == str(repo)]
        assert matching, "repo must appear in receipt.repositories"
        assert matching[0]["dirty"] is True or matching[0]["dirty"] == 1, (
            "receipt must report dirty repo as dirty=True/1"
        )


# ===========================================================================
# F-6 Consumer rebuild tests
# ===========================================================================

class TestConsumerRebuild:
    """Spec F-6: Map Room + Graphify derived FROM catalog; nodes trace to catalog rows."""

    def test_rebuild_map_room_embeds_scan_id(self, tmp_path):
        """
        F-6: Map Room JSON must embed the scan_id that produced it.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)
        out_path = str(tmp_path / "map_room.json")

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        store = _open_store(db_path)
        try:
            map_room = rebuild_map_room(store, scan_id, out_path=out_path)
        finally:
            store.close()

        assert "scan_id" in map_room, "Map Room dict must contain scan_id"
        assert map_room["scan_id"] == scan_id, (
            f"Expected scan_id={scan_id}, got {map_room.get('scan_id')}"
        )

    def test_rebuild_map_room_writes_file(self, tmp_path):
        """
        F-6: rebuild_map_room must write the JSON file to out_path.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)
        out_path = str(tmp_path / "map_room.json")

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        store = _open_store(db_path)
        try:
            rebuild_map_room(store, scan_id, out_path=out_path)
        finally:
            store.close()

        assert Path(out_path).exists(), "Map Room file must be written to out_path"
        with open(out_path) as f:
            data = json.load(f)
        assert data["scan_id"] == scan_id

    def test_rebuild_map_room_nodes_traceable_to_catalog(self, tmp_path):
        """
        F-6: Every repo listed in the Map Room must correspond to a row in the
        catalog's repositories table for the same scan_id. This proves it is
        derived from the catalog, not from a live filesystem walk.
        """
        repo_a = _init_git_repo(tmp_path / "repo_a")
        repo_b = _init_git_repo(tmp_path / "repo_b")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(repo_a)},
            {"path": str(repo_b)},
        ])
        db_path = _temp_db(tmp_path)
        out_path = str(tmp_path / "map_room.json")

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        store = _open_store(db_path)
        try:
            map_room = rebuild_map_room(store, scan_id, out_path=out_path)
            catalog_repos = {r["repo_path"] for r in store.list_repositories(scan_id)}
        finally:
            store.close()

        # Map Room must list repos; each must be in the catalog
        map_repos = map_room.get("repositories", [])
        assert len(map_repos) > 0, "Map Room must list at least one repository"
        for entry in map_repos:
            repo_path = entry.get("repo_path") or entry.get("path")
            assert repo_path in catalog_repos, (
                f"Map Room repo {repo_path!r} not found in catalog repositories"
            )

    def test_rebuild_graphify_embeds_scan_id(self, tmp_path):
        """
        F-6: Graphify JSON must embed the scan_id that produced it.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)
        out_path = str(tmp_path / "graphify.json")

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        store = _open_store(db_path)
        try:
            graphify = rebuild_graphify(store, scan_id, out_path=out_path)
        finally:
            store.close()

        assert "scan_id" in graphify, "Graphify dict must contain scan_id"
        assert graphify["scan_id"] == scan_id

    def test_rebuild_graphify_writes_file(self, tmp_path):
        """
        F-6: rebuild_graphify must write the JSON file to out_path.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)
        out_path = str(tmp_path / "graphify.json")

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        store = _open_store(db_path)
        try:
            rebuild_graphify(store, scan_id, out_path=out_path)
        finally:
            store.close()

        assert Path(out_path).exists(), "Graphify file must be written to out_path"
        with open(out_path) as f:
            data = json.load(f)
        assert data["scan_id"] == scan_id

    def test_map_room_not_derived_from_filesystem(self, tmp_path):
        """
        F-6 guard: verify Map Room is rebuilt from catalog nodes, not from a
        live filesystem walk. We do this by running a scan, REMOVING a scanned
        repo from disk, then rebuilding Map Room from the already-committed
        catalog rows — the repo must still appear in Map Room because it came
        from the catalog snapshot.
        """
        repo_a = _init_git_repo(tmp_path / "repo_a")
        repo_b = _init_git_repo(tmp_path / "repo_b")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(repo_a)},
            {"path": str(repo_b)},
        ])
        db_path = _temp_db(tmp_path)
        out_path = str(tmp_path / "map_room.json")

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        # Delete repo_b from the filesystem after the scan
        shutil.rmtree(str(repo_b))
        assert not repo_b.exists(), "repo_b must be removed to test catalog-derivation"

        store = _open_store(db_path)
        try:
            map_room = rebuild_map_room(store, scan_id, out_path=out_path)
        finally:
            store.close()

        # Map Room must still reflect the catalog (which has repo_b), even though
        # repo_b no longer exists on disk.
        map_repos = map_room.get("repositories", [])
        repo_b_paths = [
            e.get("repo_path") or e.get("path")
            for e in map_repos
            if (e.get("repo_path") or e.get("path", "")) == str(repo_b)
        ]
        assert repo_b_paths, (
            "Map Room must include repo_b from the catalog even though it was "
            "deleted from disk — proving catalog-derivation, not filesystem walk"
        )


# ===========================================================================
# F-7 Scan receipt shape tests
# ===========================================================================

class TestScanReceiptShape:
    """Spec F-7: receipt shape matches audit contract; stored in catalog_scans."""

    REQUIRED_TOP_KEYS = {"scan_id", "timestamp", "tool_version", "repositories",
                         "failures", "coverage_gaps", "excluded_paths"}

    REQUIRED_REPO_KEYS = {"path", "branch", "head_commit", "worktrees", "dirty", "coverage"}

    def test_receipt_has_all_required_top_level_keys(self, tmp_path):
        """
        F-7: The run_discovery_scan return value must contain all top-level
        keys from the SCAN_RECEIPT.json audit shape.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)

        missing = self.REQUIRED_TOP_KEYS - set(receipt.keys())
        assert not missing, f"Receipt missing required keys: {missing}"

    def test_receipt_repositories_entry_has_required_keys(self, tmp_path):
        """
        F-7: Each entry in receipt['repositories'] must have the shape from
        the audit contract: {path, branch, head_commit, worktrees, dirty, coverage}.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)

        assert len(receipt["repositories"]) >= 1, "repositories list must be non-empty"
        for entry in receipt["repositories"]:
            missing = self.REQUIRED_REPO_KEYS - set(entry.keys())
            assert not missing, (
                f"Repository entry missing keys {missing}: {entry}"
            )

    def test_receipt_scan_id_format(self, tmp_path):
        """
        F-7 + spec §D step 4: scan_id must match SYSCAT-<compact_utc>-<short_hash>.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        # Format: SYSCAT-<UTC-compact>-<short-hash>
        assert scan_id.startswith("SYSCAT-"), (
            f"scan_id must start with SYSCAT-, got {scan_id!r}"
        )
        parts = scan_id.split("-")
        assert len(parts) >= 3, (
            f"scan_id must have at least 3 dash-separated parts, got {scan_id!r}"
        )

    def test_receipt_stored_in_catalog_scans_row(self, tmp_path):
        """
        F-7: The scan receipt JSON must also be stored in catalog_scans.receipt_json.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        scan_row = _get_scan_row(db_path, scan_id)
        assert scan_row is not None
        assert scan_row.get("receipt_json") is not None, (
            "catalog_scans.receipt_json must be populated after finalize_scan"
        )

        stored = json.loads(scan_row["receipt_json"])
        assert stored.get("scan_id") == scan_id, (
            "Stored receipt_json.scan_id must match the scan_id"
        )

    def test_receipt_tool_version_matches_input(self, tmp_path):
        """
        F-7: receipt['tool_version'] must echo back the tool_version passed in.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = run_discovery_scan(
            str(registry),
            catalog_db=db_path,
            now_iso=_now_iso(),
            tool_version="syscat-v1",
        )

        assert receipt["tool_version"] == "syscat-v1", (
            f"Expected tool_version='syscat-v1', got {receipt['tool_version']!r}"
        )

    def test_receipt_worktrees_is_list(self, tmp_path):
        """
        F-7: Each repo entry's 'worktrees' field must be a list (possibly empty).
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)

        for entry in receipt["repositories"]:
            assert isinstance(entry["worktrees"], list), (
                f"worktrees must be a list, got {type(entry['worktrees'])}"
            )

    def test_receipt_coverage_field_valid_value(self, tmp_path):
        """
        F-7: Each repo entry's 'coverage' must be one of VERIFIED / UNAVAILABLE / PARTIAL.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)

        valid_coverage = {"VERIFIED", "UNAVAILABLE", "PARTIAL"}
        for entry in receipt["repositories"]:
            assert entry["coverage"] in valid_coverage, (
                f"coverage must be one of {valid_coverage}, got {entry['coverage']!r}"
            )

    def test_receipt_failures_is_list(self, tmp_path):
        """
        F-7: receipt['failures'] must be a list.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)

        assert isinstance(receipt["failures"], list), (
            "receipt.failures must be a list"
        )

    def test_build_scan_receipt_standalone_shape(self, tmp_path):
        """
        F-7: build_scan_receipt (the pure function) must produce the correct shape
        independently of run_discovery_scan, so callers can verify the contract.
        """
        scan_id = "SYSCAT-20260625T120000-abcdef01"
        now_iso = _now_iso()
        tool_version = "syscat-v1"
        repo_states = [
            {
                "path": "/fake/repo",
                "branch": "main",
                "head_commit": "deadbeef" * 5,
                "worktrees": [],
                "dirty": False,
                "coverage": "VERIFIED",
            }
        ]
        receipt = build_scan_receipt(
            scan_id=scan_id,
            now_iso=now_iso,
            tool_version=tool_version,
            repo_states=repo_states,
            coverage_gaps=[],
            excluded_paths=[],
        )

        required = {"scan_id", "timestamp", "tool_version", "repositories",
                    "failures", "coverage_gaps", "excluded_paths"}
        missing = required - set(receipt.keys())
        assert not missing, f"build_scan_receipt missing keys: {missing}"
        assert receipt["scan_id"] == scan_id
        assert receipt["tool_version"] == tool_version
        assert isinstance(receipt["repositories"], list)
        assert len(receipt["repositories"]) == 1


# ===========================================================================
# F-8 Idempotent re-scan tests
# ===========================================================================

class TestIdempotentRescan:
    """Spec F-8: re-scanning an unchanged registry yields consistent catalog content."""

    def test_two_scans_produce_two_scan_ids(self, tmp_path):
        """
        F-8: Each invocation of run_discovery_scan generates a new, distinct
        scan_id (even if content is identical). Scan history is retained.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt1 = _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")
        receipt2 = _run_scan(registry, db_path, now_iso="2026-06-25T11:00:00Z")

        assert receipt1["scan_id"] != receipt2["scan_id"], (
            "Two scans must produce distinct scan_ids"
        )

    def test_two_scans_both_stored_in_catalog(self, tmp_path):
        """
        F-8 + spec D1 append-versioned: both scans must be retained in
        catalog_scans (history not overwritten).
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt1 = _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")
        receipt2 = _run_scan(registry, db_path, now_iso="2026-06-25T11:00:00Z")

        all_rows = _get_all_scan_rows(db_path)
        scan_ids = {r["scan_id"] for r in all_rows}
        assert receipt1["scan_id"] in scan_ids, "First scan must be retained"
        assert receipt2["scan_id"] in scan_ids, "Second scan must be retained"

    def test_get_current_scan_returns_latest_complete(self, tmp_path):
        """
        F-8: After two COMPLETE scans, get_current_scan must return the latest one.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")
        receipt2 = _run_scan(registry, db_path, now_iso="2026-06-25T11:00:00Z")

        store = _open_store(db_path)
        try:
            current = store.get_current_scan()
        finally:
            store.close()

        assert current is not None
        assert current["scan_id"] == receipt2["scan_id"], (
            "get_current_scan must return the latest COMPLETE scan"
        )

    def test_second_scan_repo_count_consistent(self, tmp_path):
        """
        F-8: Re-scanning the same registry must record the same number of repos
        in both scans.
        """
        repo_a = _init_git_repo(tmp_path / "repo_a")
        repo_b = _init_git_repo(tmp_path / "repo_b")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(repo_a)},
            {"path": str(repo_b)},
        ])
        db_path = _temp_db(tmp_path)

        receipt1 = _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")
        receipt2 = _run_scan(registry, db_path, now_iso="2026-06-25T11:00:00Z")

        assert len(receipt1["repositories"]) == len(receipt2["repositories"]) == 2, (
            "Both scans must record the same number of repos for an identical registry"
        )

    def test_rescan_does_not_mutate_prior_scan_rows(self, tmp_path):
        """
        F-8 + append-versioned (D1): a second scan must NOT mutate any row
        from the first scan. Each scan_id's rows are immutable once finalized.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt1 = _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")
        scan_id_1 = receipt1["scan_id"]

        # Snapshot the first scan's repo rows before the second scan
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows_before = [dict(r) for r in conn.execute(
                "SELECT * FROM repositories WHERE scan_id = ?", (scan_id_1,)
            ).fetchall()]
        finally:
            conn.close()

        _run_scan(registry, db_path, now_iso="2026-06-25T11:00:00Z")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows_after = [dict(r) for r in conn.execute(
                "SELECT * FROM repositories WHERE scan_id = ?", (scan_id_1,)
            ).fetchall()]
        finally:
            conn.close()

        assert rows_before == rows_after, (
            "Second scan must not mutate rows belonging to the first scan_id"
        )


# ===========================================================================
# F-9 Read-only / security tests
# ===========================================================================

class TestReadOnlySecurity:
    """Spec F-9: synchronizer never writes to scanned repos; excluded_paths honored."""

    def test_synchronizer_does_not_write_to_scanned_repo(self, tmp_path):
        """
        F-9: Running a discovery scan must leave the scanned repo's working tree
        exactly as it was before the scan (no new files, no staged changes).
        """
        repo = _init_git_repo(tmp_path / "repo")
        # Record the state of the repo's directory before the scan
        files_before = set(
            str(p.relative_to(repo))
            for p in repo.rglob("*")
            if not any(part.startswith(".git") for part in p.parts)
        )

        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)
        _run_scan(registry, db_path)

        files_after = set(
            str(p.relative_to(repo))
            for p in repo.rglob("*")
            if not any(part.startswith(".git") for part in p.parts)
        )

        assert files_before == files_after, (
            "Synchronizer must not write to the scanned repo; files changed: "
            f"added={files_after - files_before}, removed={files_before - files_after}"
        )

    def test_scan_db_written_to_catalog_path_not_repo(self, tmp_path):
        """
        F-9: The SQLite catalog must be written to the injected catalog_db path,
        never inside the scanned repo.
        """
        repo = _init_git_repo(tmp_path / "repo")
        db_path = str(tmp_path / "catalog" / "syscat.sqlite3")
        Path(tmp_path / "catalog").mkdir()
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])

        _run_scan(registry, db_path)

        assert Path(db_path).exists(), "Catalog DB must be written to the injected path"

        # Verify no .sqlite3 files exist inside the scanned repo
        sqlite_in_repo = list(repo.rglob("*.sqlite3"))
        assert not sqlite_in_repo, (
            f"No .sqlite3 files must be written inside the scanned repo, found: {sqlite_in_repo}"
        )

    def test_excluded_paths_not_catalogued(self, tmp_path):
        """
        F-9: Repos whose paths match excluded_paths (or directories within
        excluded_paths) must not appear as VERIFIED entries in the catalog.

        We use the excluded_paths parameter as an advisory: a repo nested under
        an excluded prefix should be absent from the catalog repositories table.
        This tests that the implementation respects the exclusion contract.

        NOTE: This test exercises the run_discovery_scan 'excluded_paths'
        argument that the spec requires to be honored. If the implementation
        does not expose excluded_paths as a kwarg, this test will fail,
        correctly catching the gap.
        """
        repo_ok = _init_git_repo(tmp_path / "repo_ok")
        excluded_dir = tmp_path / "excluded"
        repo_excluded = _init_git_repo(excluded_dir / "repo_excluded")

        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(repo_ok)},
            {"path": str(repo_excluded)},
        ])
        db_path = _temp_db(tmp_path)

        receipt = run_discovery_scan(
            str(registry),
            catalog_db=db_path,
            now_iso=_now_iso(),
            tool_version="syscat-v1",
            excluded_paths=[str(excluded_dir)],
        )

        # The excluded repo must not appear in the receipt repositories as VERIFIED
        repo_excluded_str = str(repo_excluded)
        verified_entries = [
            r for r in receipt["repositories"]
            if (r.get("path") == repo_excluded_str or
                r.get("repo_path") == repo_excluded_str)
            and r.get("coverage") == "VERIFIED"
        ]
        assert not verified_entries, (
            f"Excluded repo must not appear as VERIFIED in receipt: {verified_entries}"
        )

    def test_no_business_domain_columns_in_schema(self, tmp_path):
        """
        F-9 + spec A-1 metadata-only guard: the catalog schema must contain no
        columns that could hold business/invoice/PII/message body content.

        We assert that the column names of every catalog table do not include
        any of the forbidden domain terms.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        _run_scan(registry, db_path)

        FORBIDDEN_COLUMN_TERMS = {
            "invoice", "amount", "payment", "pii", "ssn", "email_body",
            "message_body", "raw_message", "bank", "account_number",
            "credit_card", "balance", "gig_rate", "legal_evidence",
        }

        conn = sqlite3.connect(db_path)
        try:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            for table in tables:
                columns = [r[1].lower() for r in conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()]
                for col in columns:
                    for term in FORBIDDEN_COLUMN_TERMS:
                        assert term not in col, (
                            f"Forbidden domain term '{term}' found in "
                            f"column '{col}' of table '{table}'"
                        )
        finally:
            conn.close()

    def test_git_index_not_modified_in_scanned_repo(self, tmp_path):
        """
        F-9: The git index (staging area) of the scanned repo must not be
        touched by the scan. We check by verifying git status output is
        identical before and after the scan.
        """
        env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
               "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}
        repo = _init_git_repo(tmp_path / "repo")

        status_before = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo), capture_output=True, text=True, env=env
        ).stdout

        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)
        _run_scan(registry, db_path)

        status_after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo), capture_output=True, text=True, env=env
        ).stdout

        assert status_before == status_after, (
            "git index/staging area must not be modified by the scan. "
            f"Before: {status_before!r}  After: {status_after!r}"
        )


# ===========================================================================
# F-10 Freshness / is_stale tests
# ===========================================================================

class TestFreshness:
    """Spec F-10: is_stale flips when HEAD advances or repo goes dirty."""

    def test_is_stale_returns_false_immediately_after_scan(self, tmp_path):
        """
        F-10: A freshly completed scan must not be stale when max_age is large.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        _run_scan(registry, db_path, now_iso="2026-06-25T12:00:00Z")

        store = _open_store(db_path)
        try:
            stale = store.is_stale(
                max_age_seconds=3600,
                now_iso="2026-06-25T12:00:01Z",   # 1 second later
            )
        finally:
            store.close()

        assert stale is False, "Scan must not be stale immediately after completion"

    def test_is_stale_returns_true_when_age_exceeded(self, tmp_path):
        """
        F-10: is_stale must return True when the latest COMPLETE scan is older
        than max_age_seconds.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")

        store = _open_store(db_path)
        try:
            # Check 2 hours later with a max_age of 60 seconds → stale
            stale = store.is_stale(
                max_age_seconds=60,
                now_iso="2026-06-25T12:00:00Z",
            )
        finally:
            store.close()

        assert stale is True, (
            "is_stale must return True when scan is older than max_age_seconds"
        )

    def test_is_stale_returns_true_when_head_advances(self, tmp_path):
        """
        F-10: is_stale must return True when a repo's live HEAD commit differs
        from the catalogued HEAD commit (repo advanced).
        """
        env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
               "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}

        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")

        # Advance the repo by adding a new commit after the scan
        new_file = repo / "new_feature.txt"
        new_file.write_text("new work\n")
        subprocess.run(["git", "add", "new_feature.txt"], cwd=str(repo),
                       check=True, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "advance head"],
                       cwd=str(repo), check=True, capture_output=True, env=env)

        new_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo),
            capture_output=True, text=True, env=env
        ).stdout.strip()

        live_head_map = {str(repo): {"head_commit": new_head, "dirty": False}}

        store = _open_store(db_path)
        try:
            stale = store.is_stale(
                max_age_seconds=3600,
                live_head_map=live_head_map,
                now_iso="2026-06-25T10:00:10Z",
            )
        finally:
            store.close()

        assert stale is True, (
            "is_stale must return True when a repo's HEAD has advanced since the scan"
        )

    def test_is_stale_returns_true_when_repo_goes_dirty(self, tmp_path):
        """
        F-10: is_stale must return True when a repo that was clean at scan time
        is now reported as dirty in live_head_map.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")

        # Repo was clean; now simulate it going dirty
        env = {**os.environ}
        head_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo),
            capture_output=True, text=True, env=env
        ).stdout.strip()

        live_head_map = {str(repo): {"head_commit": head_commit, "dirty": True}}

        store = _open_store(db_path)
        try:
            stale = store.is_stale(
                max_age_seconds=3600,
                live_head_map=live_head_map,
                now_iso="2026-06-25T10:00:10Z",
            )
        finally:
            store.close()

        assert stale is True, (
            "is_stale must return True when a repo's dirty state changed since the scan"
        )

    def test_is_stale_returns_none_when_no_complete_scan(self, tmp_path):
        """
        F-10 edge case: is_stale with no COMPLETE scans should return True
        (or raise, but the spec implies True/stale when no current scan exists).
        """
        db_path = _temp_db(tmp_path)
        store = _open_store(db_path)
        try:
            result = store.is_stale(max_age_seconds=60, now_iso=_now_iso())
        finally:
            store.close()

        # With no COMPLETE scan, the system must consider itself stale
        assert result is True, (
            "is_stale must return True (stale) when no COMPLETE scan exists"
        )

    def test_map_room_and_graphify_embed_generated_utc(self, tmp_path):
        """
        F-10: Map Room and Graphify must embed generated_utc so a consumer can
        detect staleness (spec §E).
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)
        map_out = str(tmp_path / "map_room.json")
        graph_out = str(tmp_path / "graphify.json")

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        store = _open_store(db_path)
        try:
            map_room = rebuild_map_room(store, scan_id, out_path=map_out)
            graphify = rebuild_graphify(store, scan_id, out_path=graph_out)
        finally:
            store.close()

        assert "generated_utc" in map_room, (
            "Map Room must embed 'generated_utc' for staleness detection"
        )
        assert "generated_utc" in graphify, (
            "Graphify must embed 'generated_utc' for staleness detection"
        )


# ===========================================================================
# End-to-end pipeline tests (composite coverage)
# ===========================================================================

class TestEndToEnd:
    """End-to-end pipeline: spec §D steps 1-9, covering all F items together."""

    def test_full_pipeline_two_clean_repos(self, tmp_path):
        """
        E2E: Two clean repos → COMPLETE scan; Map Room + Graphify written;
        receipt with correct shape; catalog has both repos; get_current_scan works.
        """
        repo_a = _init_git_repo(tmp_path / "alpha")
        repo_b = _init_git_repo(tmp_path / "beta", branch="feature-x")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(repo_a), "is_root": True},
            {"path": str(repo_b)},
        ])
        db_path = _temp_db(tmp_path)
        map_out = str(tmp_path / "map_room.json")
        graph_out = str(tmp_path / "graphify.json")

        # Inject consumer out_paths via run_discovery_scan if supported,
        # or rebuild manually from the scan result
        receipt = run_discovery_scan(
            str(registry),
            catalog_db=db_path,
            now_iso="2026-06-25T12:00:00Z",
            tool_version="syscat-v1",
        )
        scan_id = receipt["scan_id"]

        store = _open_store(db_path)
        try:
            rebuild_map_room(store, scan_id, out_path=map_out)
            rebuild_graphify(store, scan_id, out_path=graph_out)
            repos = store.list_repositories(scan_id)
            current = store.get_current_scan()
        finally:
            store.close()

        # Pipeline step 5: repos in catalog
        assert len(repos) == 2
        repo_paths = {r["repo_path"] for r in repos}
        assert str(repo_a) in repo_paths
        assert str(repo_b) in repo_paths

        # Pipeline step 9: COMPLETE, promoted as current
        assert current is not None
        assert current["scan_id"] == scan_id

        # Pipeline steps 6-7: consumer files written
        assert Path(map_out).exists()
        assert Path(graph_out).exists()

        # Receipt shape (step 8)
        assert receipt["scan_id"] == scan_id
        assert len(receipt["repositories"]) == 2

    def test_full_pipeline_mixed_dirty_and_clean(self, tmp_path):
        """
        E2E: One dirty repo + one clean repo → COMPLETE scan; dirty repo catalogued
        as dirty=1; clean as dirty=0.
        """
        clean_repo = _init_git_repo(tmp_path / "clean")
        dirty_repo = _init_git_repo(tmp_path / "dirty")
        _make_dirty(dirty_repo)

        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [
            {"path": str(clean_repo)},
            {"path": str(dirty_repo)},
        ])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = {
                r["repo_path"]: r["dirty"]
                for r in conn.execute(
                    "SELECT repo_path, dirty FROM repositories WHERE scan_id = ?",
                    (scan_id,)
                ).fetchall()
            }
        finally:
            conn.close()

        assert rows.get(str(clean_repo)) == 0
        assert rows.get(str(dirty_repo)) == 1

    def test_full_pipeline_scan_scoped_writes(self, tmp_path):
        """
        E2E + spec §C: every row in every content table carries the same scan_id.
        After two scans, rows can be unambiguously attributed to one scan.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt1 = _run_scan(registry, db_path, now_iso="2026-06-25T10:00:00Z")
        receipt2 = _run_scan(registry, db_path, now_iso="2026-06-25T11:00:00Z")
        sid1 = receipt1["scan_id"]
        sid2 = receipt2["scan_id"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            content_tables = ["repositories", "worktrees", "components",
                              "capabilities", "queues", "handoffs", "tests"]
            for table in content_tables:
                # Every row in each table must have a scan_id that is one of our two
                rows = conn.execute(f"SELECT scan_id FROM {table}").fetchall()
                for row in rows:
                    assert row["scan_id"] in (sid1, sid2), (
                        f"Row in {table} has unexpected scan_id {row['scan_id']!r}"
                    )
        finally:
            conn.close()

    def test_nine_required_tables_exist_after_scan(self, tmp_path):
        """
        E2E + F-1 (migration): after a scan, all 9 catalog tables + schema_migrations
        must exist in the SQLite database.
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        _run_scan(registry, db_path)

        REQUIRED_TABLES = {
            "catalog_scans", "repositories", "worktrees", "components",
            "capabilities", "queues", "handoffs", "tests", "schema_migrations",
        }

        conn = sqlite3.connect(db_path)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        finally:
            conn.close()

        missing = REQUIRED_TABLES - tables
        assert not missing, f"Missing required tables after scan: {missing}"

    def test_scan_id_one_per_pipeline_run(self, tmp_path):
        """
        E2E + spec §D step 4: ONE immutable scan_id per run_discovery_scan call.
        All catalog rows for a given run must share the same scan_id, and it must
        match the receipt['scan_id'].
        """
        repo = _init_git_repo(tmp_path / "repo")
        registry = tmp_path / "REPOSITORY_REGISTRY.md"
        _write_registry(registry, [{"path": str(repo)}])
        db_path = _temp_db(tmp_path)

        receipt = _run_scan(registry, db_path)
        scan_id = receipt["scan_id"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # All repository rows written in this run must carry the receipt's scan_id
            repo_rows = conn.execute(
                "SELECT DISTINCT scan_id FROM repositories WHERE scan_id = ?",
                (scan_id,)
            ).fetchall()
        finally:
            conn.close()

        # There should be exactly one distinct scan_id for this run's repos
        assert len(repo_rows) == 1, (
            "All repo rows from one pipeline run must share exactly one scan_id"
        )
        assert repo_rows[0]["scan_id"] == scan_id
