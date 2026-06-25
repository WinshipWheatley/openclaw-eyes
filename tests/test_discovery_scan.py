"""
test_discovery_scan.py — Contract tests for Unit 2: discovery_scan.py
Authored INDEPENDENTLY of the implementation per the G2C pattern.
Written to the spec: /home/openclaw/Operator/SYSTEM-CATALOG-SPEC.md (binding, esp. §F)
and the audit at: /home/openclaw/workspaces/cross_repo_discovery_legal_readiness_audit/

These tests CATCH a wrong implementation by encoding the spec contract precisely.
All fixtures are synthetic (tmp_path / temp git repos). No real repo is mutated.
No implementation file is read, imported, or inspected from syscat-impl.

Coverage map (§F items encoded per-test are noted inline):
  §F-4  PARTIAL-block (unavailable repo not promoted)
  §F-5  Dirty capture
  §F-6  Consumer rebuild from catalog (traced to scan_id)
  §F-7  Scan receipt shape
  §F-8  Idempotent re-scan
  §F-9  Read-only security / excluded_paths / no-network / no-PII path / temp fixtures only
  §F-10 Freshness — is_stale flips on HEAD advance or dirty change

Unit-2 contract (discovery_scan.py) specifically covers:
  - load_registry: parse REPOSITORY_REGISTRY.md → list[dict]
  - capture_repo_state: read-only git, returns branch/head_commit/dirty/worktrees/coverage
  - parse_repo_metadata: metadata only, bounded, honor excluded_paths
  - generate_scan_id: deterministic format SYSCAT-<UTC-compact>-<short_hash>

The synchronizer (syscat_synchronizer.py / Unit 3) is exercised in tests that
wire capture → store → consumers → receipt → PARTIAL, because those cross-unit
integration guarantees (§F-4, §F-6, §F-7, §F-8) require the full pipeline.
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module-level import.  The modules must be importable from the worktree.
# We deliberately do NOT import from syscat-impl — the modules are expected
# on sys.path as installed/adjacent packages.
# ---------------------------------------------------------------------------

from discovery_scan import (
    capture_repo_state,
    generate_scan_id,
    load_registry,
    parse_repo_metadata,
)
from syscat_synchronizer import (
    build_scan_receipt,
    rebuild_graphify,
    rebuild_map_room,
    run_discovery_scan,
)
from system_catalog_store import MigrationError, SystemCatalogStore

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

NOW_ISO = "2026-06-25T10:00:00Z"
TOOL_VERSION = "syscat-v1"


def _make_git_repo(base: Path, *, dirty: bool = False, unreadable: bool = False) -> Path:
    """
    Create a minimal git repo under base/  suitable as a synthetic fixture.
    If dirty=True, adds an unstaged file after the initial commit.
    If unreadable=True, creates a directory that is NOT a git repo (simulates
    an unavailable/unreadable repo path for PARTIAL testing).
    Returns the repo path.
    """
    repo = base / ("dirty_repo" if dirty else ("unreadable_repo" if unreadable else "clean_repo"))
    repo.mkdir(parents=True, exist_ok=True)

    if unreadable:
        # Not a git repo at all — capture_repo_state must return coverage='UNAVAILABLE'
        (repo / "README.txt").write_text("not a git repo\n")
        return repo

    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, env=env)

    if dirty:
        (repo / "untracked.txt").write_text("dirty file\n")

    return repo


def _make_registry_md(entries: list[dict]) -> str:
    """
    Build a REPOSITORY_REGISTRY.md-style markdown table string from a list of
    dicts with keys: repo_path (required), is_root (optional bool).
    The real registry uses a pipe-table format; we match that format so
    load_registry can parse it.
    """
    lines = [
        "# Repository Registry",
        "",
        "| Repository Path | Purpose | Branch | HEAD Commit | Dirty | Worktrees | Coverage |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for e in entries:
        path = e["repo_path"]
        root_marker = " (root)" if e.get("is_root") else ""
        lines.append(f"| `{path}` | Test repo{root_marker} | main | abc123 | No | None | VERIFIED |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# §F-9 fixture scaffolding: all tests use temp dirs, no real-repo writes
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path: Path) -> str:
    """Return a fresh temp-file SQLite DB path for a SystemCatalogStore."""
    return str(tmp_path / "syscat.sqlite3")


@pytest.fixture()
def clean_repo(tmp_path: Path) -> Path:
    return _make_git_repo(tmp_path / "clean")


@pytest.fixture()
def dirty_repo(tmp_path: Path) -> Path:
    return _make_git_repo(tmp_path / "dirty", dirty=True)


@pytest.fixture()
def unreadable_repo(tmp_path: Path) -> Path:
    return _make_git_repo(tmp_path / "unreadable", unreadable=True)


# ===========================================================================
# GROUP A — load_registry
# ===========================================================================

class TestLoadRegistry:
    """
    §F-9: all fixtures synthetic; no real repo touched.
    Contract: load_registry(registry_path: str) -> list[dict]
      Each dict has at minimum: repo_path: str
      Optional: is_root: bool
    """

    def test_load_registry_returns_list_of_dicts(self, tmp_path: Path):
        """load_registry returns a non-empty list of dicts from a valid registry file."""
        reg_path = tmp_path / "REPOSITORY_REGISTRY.md"
        reg_path.write_text(_make_registry_md([{"repo_path": "/tmp/repo_a"}]))
        result = load_registry(str(reg_path))
        assert isinstance(result, list), "load_registry must return a list"
        assert len(result) >= 1, "must parse at least one entry"
        for entry in result:
            assert isinstance(entry, dict), "each entry must be a dict"

    def test_load_registry_includes_repo_path(self, tmp_path: Path):
        """Each loaded entry must include a 'repo_path' key."""
        reg_path = tmp_path / "REPOSITORY_REGISTRY.md"
        reg_path.write_text(_make_registry_md([
            {"repo_path": "/tmp/repo_alpha"},
            {"repo_path": "/tmp/repo_beta"},
        ]))
        entries = load_registry(str(reg_path))
        paths = [e["repo_path"] for e in entries]
        assert "/tmp/repo_alpha" in paths
        assert "/tmp/repo_beta" in paths

    def test_load_registry_preserves_distinct_paths(self, tmp_path: Path):
        """Two distinct entries must both appear in the output."""
        reg_path = tmp_path / "REPOSITORY_REGISTRY.md"
        reg_path.write_text(_make_registry_md([
            {"repo_path": "/a/one"},
            {"repo_path": "/a/two"},
            {"repo_path": "/a/three"},
        ]))
        entries = load_registry(str(reg_path))
        paths = [e["repo_path"] for e in entries]
        assert len(set(paths)) >= 3, "all three distinct paths must appear"

    def test_load_registry_missing_file_raises(self, tmp_path: Path):
        """load_registry must raise when the registry file does not exist."""
        bad_path = str(tmp_path / "nonexistent_REGISTRY.md")
        with pytest.raises(Exception):
            load_registry(bad_path)

    def test_load_registry_also_accepts_list(self):
        """
        §F-9 contract allows passing a pre-parsed list (for testability).
        load_registry(list[dict]) → same list (or equivalent).
        """
        entries_in = [{"repo_path": "/synthetic/repo"}]
        result = load_registry(entries_in)  # type: ignore[arg-type]
        assert isinstance(result, list)
        paths = [e["repo_path"] for e in result]
        assert "/synthetic/repo" in paths


# ===========================================================================
# GROUP B — capture_repo_state
# ===========================================================================

class TestCaptureRepoState:
    """
    §F-5  Dirty capture: dirty repo → dirty=True in returned dict
    §F-9  Read-only: capture must NOT write any files to the scanned repo
    Contract: capture_repo_state(repo_path: str) -> dict
      Keys: branch: str, head_commit: str, dirty: bool,
            worktrees: list, coverage: 'VERIFIED'|'UNAVAILABLE'
    """

    def test_capture_clean_repo_verified(self, clean_repo: Path):
        """A readable git repo returns coverage='VERIFIED'."""
        state = capture_repo_state(str(clean_repo))
        assert state["coverage"] == "VERIFIED", (
            "A readable git repo must return coverage='VERIFIED'"
        )

    def test_capture_returns_branch(self, clean_repo: Path):
        """Returned dict must include branch (non-empty string)."""
        state = capture_repo_state(str(clean_repo))
        assert "branch" in state, "capture must return 'branch'"
        assert isinstance(state["branch"], str) and state["branch"], "branch must be a non-empty string"

    def test_capture_returns_head_commit(self, clean_repo: Path):
        """Returned dict must include head_commit (non-empty string)."""
        state = capture_repo_state(str(clean_repo))
        assert "head_commit" in state, "capture must return 'head_commit'"
        assert isinstance(state["head_commit"], str) and state["head_commit"], (
            "head_commit must be a non-empty string"
        )

    def test_capture_clean_repo_not_dirty(self, clean_repo: Path):
        """A clean repo (no uncommitted changes) must return dirty=False. §F-5"""
        state = capture_repo_state(str(clean_repo))
        assert state["dirty"] is False, "clean repo must report dirty=False"

    def test_capture_dirty_repo_is_dirty(self, dirty_repo: Path):
        """
        §F-5 — Dirty capture: the current-systems gap is that dirty state was
        previously silently omitted. A repo with uncommitted/untracked files
        MUST return dirty=True.
        """
        state = capture_repo_state(str(dirty_repo))
        assert state["dirty"] is True, (
            "§F-5: a repo with uncommitted/untracked changes MUST return dirty=True"
        )

    def test_capture_dirty_repo_still_verified(self, dirty_repo: Path):
        """
        Dirty does NOT mean UNAVAILABLE. A dirty-but-readable git repo is still
        coverage='VERIFIED'. UNAVAILABLE is reserved for unreadable/inaccessible repos.
        """
        state = capture_repo_state(str(dirty_repo))
        assert state["coverage"] == "VERIFIED", (
            "A dirty but readable git repo must still be VERIFIED, not UNAVAILABLE"
        )

    def test_capture_unreadable_repo_unavailable(self, unreadable_repo: Path):
        """
        §F-4 dependency: an unreadable/non-git directory must return
        coverage='UNAVAILABLE' instead of raising an exception.
        """
        state = capture_repo_state(str(unreadable_repo))
        assert state["coverage"] == "UNAVAILABLE", (
            "An unreadable repo must return coverage='UNAVAILABLE', not raise"
        )

    def test_capture_unavailable_has_no_commit(self, unreadable_repo: Path):
        """UNAVAILABLE repos may have head_commit as None or empty string."""
        state = capture_repo_state(str(unreadable_repo))
        # head_commit should either be absent, None, or empty for an unavailable repo
        commit = state.get("head_commit")
        assert commit in (None, ""), (
            "UNAVAILABLE repo must not have a real head_commit value"
        )

    def test_capture_returns_worktrees_list(self, clean_repo: Path):
        """The returned dict must include a 'worktrees' key with a list value."""
        state = capture_repo_state(str(clean_repo))
        assert "worktrees" in state, "capture must return 'worktrees'"
        assert isinstance(state["worktrees"], list), "'worktrees' must be a list"

    def test_capture_does_not_write_to_repo(self, clean_repo: Path, tmp_path: Path):
        """
        §F-9 Read-only/security: the capture function MUST NOT create or modify
        any files in the scanned repository directory.
        """
        before = set(clean_repo.rglob("*"))
        capture_repo_state(str(clean_repo))
        after = set(clean_repo.rglob("*"))
        new_files = after - before
        # Filter out git internal state churn (index locks etc.) by only
        # checking for non-.git new files
        non_git_new = {f for f in new_files if ".git" not in str(f)}
        assert not non_git_new, (
            f"§F-9: capture_repo_state must NOT write any files to the scanned repo; "
            f"new non-.git files found: {non_git_new}"
        )

    def test_capture_nonexistent_path_unavailable(self, tmp_path: Path):
        """A completely nonexistent path must also return coverage='UNAVAILABLE'."""
        state = capture_repo_state(str(tmp_path / "does_not_exist_at_all"))
        assert state["coverage"] == "UNAVAILABLE"

    def test_capture_head_commit_looks_like_sha(self, clean_repo: Path):
        """head_commit on a VERIFIED repo should be a hex string of reasonable length."""
        state = capture_repo_state(str(clean_repo))
        commit = state["head_commit"]
        assert re.match(r"^[0-9a-f]{7,40}$", commit, re.IGNORECASE), (
            f"head_commit '{commit}' does not look like a git SHA"
        )


# ===========================================================================
# GROUP C — parse_repo_metadata
# ===========================================================================

class TestParseRepoMetadata:
    """
    §F-3 (metadata-only guard): parse must only return structural metadata,
         never raw domain/PII/invoice/message-body content.
    §F-9  Excluded_paths honored; bounded discovery.
    Contract: parse_repo_metadata(repo_path: str) -> dict
      Keys: components: list, capabilities: list, queues: list,
            handoffs: list, tests: list
    """

    def test_parse_returns_required_keys(self, clean_repo: Path):
        """parse_repo_metadata must return a dict with all five structural keys."""
        result = parse_repo_metadata(str(clean_repo))
        for key in ("components", "capabilities", "queues", "handoffs", "tests"):
            assert key in result, f"parse_repo_metadata must return '{key}' key"

    def test_parse_all_values_are_lists(self, clean_repo: Path):
        """All five structural keys must map to lists."""
        result = parse_repo_metadata(str(clean_repo))
        for key in ("components", "capabilities", "queues", "handoffs", "tests"):
            assert isinstance(result[key], list), f"'{key}' must be a list"

    def test_parse_empty_repo_returns_empty_lists(self, clean_repo: Path):
        """A minimal repo with no specs/queues/tests/etc. returns empty lists."""
        result = parse_repo_metadata(str(clean_repo))
        for key in ("components", "capabilities", "queues", "handoffs", "tests"):
            assert result[key] == [], (
                f"A repo with no metadata files should return empty list for '{key}'"
            )

    def test_parse_does_not_write_to_repo(self, clean_repo: Path):
        """§F-9: parse_repo_metadata must NOT write anything to the scanned repo."""
        before = set(clean_repo.rglob("*"))
        parse_repo_metadata(str(clean_repo))
        after = set(clean_repo.rglob("*"))
        new_files = after - before
        non_git_new = {f for f in new_files if ".git" not in str(f)}
        assert not non_git_new, (
            f"§F-9: parse_repo_metadata must NOT write files to the repo; "
            f"found: {non_git_new}"
        )

    def test_parse_honors_excluded_paths(self, clean_repo: Path, tmp_path: Path):
        """
        §F-9: excluded_paths must be honored — files under excluded directories
        must not appear in parse output.
        """
        secret_dir = clean_repo / "private_data"
        secret_dir.mkdir()
        (secret_dir / "invoice.json").write_text('{"amount": 9999}')

        # Parse with the secret_dir excluded
        result = parse_repo_metadata(str(clean_repo), excluded_paths=[str(secret_dir)])
        # Assert: no entry in any list references the excluded path
        all_entries = (
            result["components"] + result["capabilities"]
            + result["queues"] + result["handoffs"] + result["tests"]
        )
        for entry in all_entries:
            source = entry.get("source_ref", "") or entry.get("path", "") or ""
            assert str(secret_dir) not in source, (
                f"§F-9: excluded path '{secret_dir}' must not appear in parse output; "
                f"found in entry: {entry}"
            )

    def test_parse_metadata_no_domain_values(self, clean_repo: Path):
        """
        §F-3 metadata-only guard: parse_repo_metadata must return only structural
        pointers (paths, IDs, names) — never raw business data, invoice amounts,
        message bodies, or PII content in values.
        We assert that no returned entry has a key named 'amount', 'body',
        'message', 'pii', 'invoice_total', or 'raw_content'.
        """
        forbidden_keys = {
            "amount", "body", "message_body", "pii", "invoice_total",
            "raw_content", "email_body", "legal_text",
        }
        result = parse_repo_metadata(str(clean_repo))
        all_entries = (
            result["components"] + result["capabilities"]
            + result["queues"] + result["handoffs"] + result["tests"]
        )
        for entry in all_entries:
            if isinstance(entry, dict):
                overlap = forbidden_keys & set(entry.keys())
                assert not overlap, (
                    f"§F-3: metadata-only violation — parse_repo_metadata returned a "
                    f"domain/PII key: {overlap} in entry: {entry}"
                )

    def test_parse_components_have_source_ref(self, clean_repo: Path):
        """
        If components are found, each must include a 'source_ref' (metadata pointer),
        not raw content.
        """
        # Place a synthetic component spec file
        (clean_repo / "components.yaml").write_text(
            "- id: comp_1\n  name: TestComponent\n  kind: service\n"
        )
        result = parse_repo_metadata(str(clean_repo))
        for comp in result.get("components", []):
            assert "source_ref" in comp or "component_id" in comp, (
                "Component entries must carry a source_ref or component_id metadata pointer"
            )


# ===========================================================================
# GROUP D — generate_scan_id
# ===========================================================================

class TestGenerateScanId:
    """
    Contract: generate_scan_id(captured_summary, now_iso: str) -> str
      Format: SYSCAT-<UTC-compact>-<short-content-hash>
      Deterministic: same inputs → same scan_id
    """

    SAMPLE_SUMMARY = [
        {"repo_path": "/home/openclaw", "head_commit": "abc123", "dirty": False},
        {"repo_path": "/mnt/e/openclaw-source", "head_commit": "def456", "dirty": True},
    ]

    def test_scan_id_starts_with_syscat(self):
        """Scan ID must start with 'SYSCAT-'."""
        sid = generate_scan_id(self.SAMPLE_SUMMARY, NOW_ISO)
        assert sid.startswith("SYSCAT-"), f"scan_id must start with 'SYSCAT-'; got '{sid}'"

    def test_scan_id_contains_three_parts(self):
        """Scan ID format is SYSCAT-<compact_utc>-<short_hash> (3 dash-separated parts)."""
        sid = generate_scan_id(self.SAMPLE_SUMMARY, NOW_ISO)
        parts = sid.split("-")
        assert len(parts) >= 3, (
            f"scan_id must have at least 3 '-'-separated parts; got {parts}"
        )
        assert parts[0] == "SYSCAT"

    def test_scan_id_deterministic_same_inputs(self):
        """
        Same captured_summary + same now_iso → identical scan_id.
        This is critical for testability (the spec requires now to be injected).
        """
        sid_a = generate_scan_id(self.SAMPLE_SUMMARY, NOW_ISO)
        sid_b = generate_scan_id(self.SAMPLE_SUMMARY, NOW_ISO)
        assert sid_a == sid_b, (
            "generate_scan_id must be deterministic: same inputs must produce the same scan_id"
        )

    def test_scan_id_differs_with_different_content(self):
        """Different captured content → different scan_id (hash changes)."""
        summary_a = [{"repo_path": "/repo/a", "head_commit": "aaa111", "dirty": False}]
        summary_b = [{"repo_path": "/repo/a", "head_commit": "bbb222", "dirty": False}]
        sid_a = generate_scan_id(summary_a, NOW_ISO)
        sid_b = generate_scan_id(summary_b, NOW_ISO)
        assert sid_a != sid_b, (
            "Different captured content must yield different scan_ids"
        )

    def test_scan_id_differs_with_different_time(self):
        """Different now_iso → different scan_id (compact UTC portion changes)."""
        sid_a = generate_scan_id(self.SAMPLE_SUMMARY, "2026-06-25T10:00:00Z")
        sid_b = generate_scan_id(self.SAMPLE_SUMMARY, "2026-06-25T11:00:00Z")
        assert sid_a != sid_b, (
            "Different now_iso must produce different scan_ids"
        )

    def test_scan_id_is_string(self):
        sid = generate_scan_id(self.SAMPLE_SUMMARY, NOW_ISO)
        assert isinstance(sid, str), "generate_scan_id must return a str"

    def test_scan_id_compact_utc_portion_matches_time(self):
        """
        The compact UTC portion of the scan_id should encode the now_iso date/time.
        For now_iso='2026-06-25T10:00:00Z' the compact form should include
        digits representing '20260625' or '202606251000' etc.
        """
        sid = generate_scan_id(self.SAMPLE_SUMMARY, "2026-06-25T10:00:00Z")
        # Extract middle part (between first and last '-')
        parts = sid.split("-")
        compact_utc = parts[1]  # SYSCAT-<THIS>-<hash>
        # The compact UTC must contain digits referencing the date
        assert re.match(r"^\d+$", compact_utc), (
            f"Compact UTC part '{compact_utc}' must be all digits"
        )
        assert "2026" in compact_utc or compact_utc.startswith("202606"), (
            f"Compact UTC '{compact_utc}' should encode the year 2026"
        )


# ===========================================================================
# GROUP E — end-to-end via run_discovery_scan (Unit 3 wired to Unit 2)
# These tests validate §F-4, §F-5, §F-7, §F-8, §F-9, §F-10 at the pipeline level.
# ===========================================================================

class TestRunDiscoveryScanPartialBlock:
    """
    §F-4: PARTIAL-block — if ANY registered repo is UNAVAILABLE, the scan
    finalizes as PARTIAL and MUST NOT be promoted as the current catalog.
    get_current_scan() must still return the prior COMPLETE (or None if first scan).
    """

    def test_partial_scan_not_promoted_as_current(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path, unreadable_repo: Path
    ):
        """
        §F-4: A registry with one UNAVAILABLE repo → scan is PARTIAL.
        get_current_scan() returns None (no prior COMPLETE), NOT the partial scan.
        """
        reg_path = tmp_path / "REPOSITORY_REGISTRY.md"
        reg_path.write_text(_make_registry_md([
            {"repo_path": str(clean_repo)},
            {"repo_path": str(unreadable_repo)},
        ]))

        receipt = run_discovery_scan(
            str(reg_path),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )

        # The receipt must reflect PARTIAL
        assert receipt.get("status") in ("PARTIAL",) or any(
            r.get("coverage") == "UNAVAILABLE"
            for r in receipt.get("repositories", [])
        ), "§F-4: scan with an UNAVAILABLE repo must be PARTIAL"

        # The catalog MUST NOT promote a PARTIAL scan as current
        with SystemCatalogStore(tmp_db) as store:
            current = store.get_current_scan()
        assert current is None, (
            "§F-4: get_current_scan() must return None when the only scan is PARTIAL"
        )

    def test_partial_scan_gap_surfaced(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path, unreadable_repo: Path
    ):
        """
        §F-4: The PARTIAL scan must surface the gap — the unavailable repo
        must appear in coverage_gaps or the receipt's failures/coverage_gaps.
        """
        reg_path = tmp_path / "REPOSITORY_REGISTRY.md"
        reg_path.write_text(_make_registry_md([
            {"repo_path": str(clean_repo)},
            {"repo_path": str(unreadable_repo)},
        ]))

        receipt = run_discovery_scan(
            str(reg_path),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )

        # Coverage gap must be surfaced in the receipt
        gaps = receipt.get("coverage_gaps", []) or []
        failures = receipt.get("failures", []) or []
        repo_coverages = [
            r.get("coverage") for r in receipt.get("repositories", [])
        ]
        assert (
            len(gaps) > 0
            or len(failures) > 0
            or "UNAVAILABLE" in repo_coverages
        ), (
            "§F-4: PARTIAL scan must surface the unavailable repo as a gap, "
            "failure, or UNAVAILABLE coverage entry"
        )

    def test_prior_complete_scan_survives_partial(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path, unreadable_repo: Path
    ):
        """
        §F-4: If a prior COMPLETE scan exists and a new PARTIAL scan runs,
        get_current_scan() must still return the prior COMPLETE, not the PARTIAL.
        """
        # First: a fully VERIFIED scan (all repos readable)
        reg1 = tmp_path / "REGISTRY_complete.md"
        reg1.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        run_discovery_scan(
            str(reg1),
            catalog_db=tmp_db,
            now_iso="2026-06-25T09:00:00Z",
            tool_version=TOOL_VERSION,
        )

        with SystemCatalogStore(tmp_db) as store:
            first_current = store.get_current_scan()
        assert first_current is not None, "First all-VERIFIED scan must produce a COMPLETE"
        first_scan_id = first_current["scan_id"]

        # Second: a PARTIAL scan (one unavailable repo)
        reg2 = tmp_path / "REGISTRY_partial.md"
        reg2.write_text(_make_registry_md([
            {"repo_path": str(clean_repo)},
            {"repo_path": str(unreadable_repo)},
        ]))
        run_discovery_scan(
            str(reg2),
            catalog_db=tmp_db,
            now_iso="2026-06-25T10:00:00Z",
            tool_version=TOOL_VERSION,
        )

        with SystemCatalogStore(tmp_db) as store:
            current_after_partial = store.get_current_scan()

        assert current_after_partial is not None, (
            "§F-4: prior COMPLETE scan must still be accessible after a PARTIAL scan"
        )
        assert current_after_partial["scan_id"] == first_scan_id, (
            "§F-4: get_current_scan() must return the prior COMPLETE, "
            "not be overwritten by a PARTIAL scan"
        )


class TestDirtyCapturePipeline:
    """
    §F-5: Dirty capture — dirty repo → dirty=1 recorded in the catalog.
    This proves the current-systems gap (silently omitting dirty state) is closed.
    """

    def test_dirty_repo_recorded_in_catalog(
        self, tmp_path: Path, tmp_db: str, dirty_repo: Path
    ):
        """
        §F-5: A dirty repo fixture must produce a repositories row with dirty=1
        in the catalog after run_discovery_scan.
        """
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(dirty_repo)}]))
        run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )

        with SystemCatalogStore(tmp_db) as store:
            current = store.get_current_scan()
            assert current is not None, "Dirty repo scan must still complete as COMPLETE (dirty != unavailable)"
            repos = store.list_repositories(current["scan_id"])

        dirty_rows = [r for r in repos if r.get("dirty") in (1, True)]
        assert dirty_rows, (
            f"§F-5: dirty repo must be recorded with dirty=1 in the catalog; "
            f"found rows: {repos}"
        )

    def test_clean_repo_not_marked_dirty(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """A clean repo must be recorded with dirty=0 (not 1)."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )

        with SystemCatalogStore(tmp_db) as store:
            current = store.get_current_scan()
            repos = store.list_repositories(current["scan_id"])

        clean_rows = [r for r in repos if r.get("dirty") in (0, False)]
        assert clean_rows, (
            f"A clean repo must be recorded with dirty=0; found rows: {repos}"
        )


class TestScanReceiptShape:
    """
    §F-7: Scan receipt shape must match the audit contract:
      {scan_id, timestamp, tool_version, repositories:[{path, branch,
       head_commit, worktrees, dirty, coverage}], failures, coverage_gaps,
       excluded_paths}
    Receipt must also be stored in catalog_scans.receipt_json.
    """

    def test_receipt_has_required_top_level_keys(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-7: receipt must have all required top-level keys."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )

        required_keys = {
            "scan_id", "timestamp", "tool_version", "repositories",
            "failures", "coverage_gaps", "excluded_paths",
        }
        missing = required_keys - set(receipt.keys())
        assert not missing, f"§F-7: receipt missing required keys: {missing}"

    def test_receipt_repositories_have_required_fields(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-7: each repository entry must include path, branch, head_commit, worktrees, dirty, coverage."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )

        required_repo_keys = {"path", "branch", "head_commit", "worktrees", "dirty", "coverage"}
        for repo_entry in receipt["repositories"]:
            missing = required_repo_keys - set(repo_entry.keys())
            assert not missing, (
                f"§F-7: repository entry missing keys {missing}: {repo_entry}"
            )

    def test_receipt_scan_id_matches_tool_version(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """Receipt must carry the tool_version that was passed in."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version="syscat-v1",
        )
        assert receipt["tool_version"] == "syscat-v1", (
            "§F-7: receipt tool_version must match the tool_version passed to run_discovery_scan"
        )

    def test_receipt_stored_in_catalog(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-7: receipt must be stored in catalog_scans.receipt_json for the scan_id."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )
        scan_id = receipt["scan_id"]

        # Query the DB directly to verify receipt_json is stored
        conn = sqlite3.connect(tmp_db)
        try:
            row = conn.execute(
                "SELECT receipt_json FROM catalog_scans WHERE scan_id = ?", (scan_id,)
            ).fetchone()
        finally:
            conn.close()

        assert row is not None, "Scan must exist in catalog_scans"
        assert row[0] is not None, "§F-7: receipt_json must be stored in catalog_scans"
        stored = json.loads(row[0])
        assert stored.get("scan_id") == scan_id, (
            "Stored receipt_json must contain the correct scan_id"
        )

    def test_build_scan_receipt_shape(self):
        """
        §F-7: build_scan_receipt standalone — validates the shape of the receipt dict
        produced by the helper function directly.
        """
        repo_states = [
            {
                "repo_path": "/home/openclaw",
                "branch": "main",
                "head_commit": "abc123def456",
                "worktrees": [],
                "dirty": False,
                "coverage": "VERIFIED",
            }
        ]
        receipt = build_scan_receipt(
            scan_id="SYSCAT-20260625100000-abcd1234",
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
            repo_states=repo_states,
            coverage_gaps=[],
            excluded_paths=[],
        )

        required_keys = {
            "scan_id", "timestamp", "tool_version", "repositories",
            "failures", "coverage_gaps", "excluded_paths",
        }
        missing = required_keys - set(receipt.keys())
        assert not missing, f"§F-7: build_scan_receipt missing keys: {missing}"

        assert receipt["scan_id"] == "SYSCAT-20260625100000-abcd1234"
        assert receipt["tool_version"] == TOOL_VERSION

        repo_entry = receipt["repositories"][0]
        required_repo_keys = {"path", "branch", "head_commit", "worktrees", "dirty", "coverage"}
        missing_repo = required_repo_keys - set(repo_entry.keys())
        assert not missing_repo, f"§F-7: repo entry missing keys: {missing_repo}"


class TestConsumerRebuildFromCatalog:
    """
    §F-6: Consumer rebuild — Map Room + Graphify are rebuilt FROM the catalog
    (assert their nodes trace to catalog rows + the scan_id; not from a live
    filesystem walk).
    """

    def test_map_room_embeds_scan_id(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-6: The rebuilt Map Room JSON must embed the scan_id."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )
        scan_id = receipt["scan_id"]

        out_path = tmp_path / "map_room.json"
        with SystemCatalogStore(tmp_db) as store:
            terrain = rebuild_map_room(store, scan_id, out_path=str(out_path))

        assert "scan_id" in terrain, "§F-6: Map Room must embed 'scan_id'"
        assert terrain["scan_id"] == scan_id, (
            f"§F-6: Map Room scan_id '{terrain['scan_id']}' must equal the scan_id '{scan_id}'"
        )

    def test_map_room_written_to_file(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-6: rebuild_map_room must write the JSON file to the specified out_path."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )
        scan_id = receipt["scan_id"]

        out_path = tmp_path / "map_room_output.json"
        with SystemCatalogStore(tmp_db) as store:
            rebuild_map_room(store, scan_id, out_path=str(out_path))

        assert out_path.exists(), "§F-6: rebuild_map_room must write the JSON file"
        data = json.loads(out_path.read_text())
        assert data.get("scan_id") == scan_id

    def test_graphify_embeds_scan_id(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-6: The rebuilt Graphify JSON must embed the scan_id."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )
        scan_id = receipt["scan_id"]

        out_path = tmp_path / "graphify.json"
        with SystemCatalogStore(tmp_db) as store:
            graph = rebuild_graphify(store, scan_id, out_path=str(out_path))

        assert "scan_id" in graph, "§F-6: Graphify must embed 'scan_id'"
        assert graph["scan_id"] == scan_id, (
            f"§F-6: Graphify scan_id '{graph['scan_id']}' must equal '{scan_id}'"
        )

    def test_graphify_has_no_raw_domain_data(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-6 + §F-3: Graphify must not contain raw domain/PII data in its output."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )
        scan_id = receipt["scan_id"]

        out_path = tmp_path / "graphify_clean.json"
        with SystemCatalogStore(tmp_db) as store:
            graph = rebuild_graphify(store, scan_id, out_path=str(out_path))

        graph_str = json.dumps(graph)
        forbidden_patterns = ["invoice_total", "pii", "message_body", "email_body", "legal_text"]
        for pattern in forbidden_patterns:
            assert pattern not in graph_str.lower(), (
                f"§F-3/§F-6: Graphify must not contain raw domain/PII field '{pattern}'"
            )

    def test_map_room_nodes_trace_to_catalog_not_filesystem(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        §F-6: Map Room must be derived FROM catalog rows, not from a live filesystem walk.
        We verify this by checking that the Map Room reflects catalog data (scan_id-tagged)
        even though we have NOT walked clean_repo's filesystem directly in this test.
        The key invariant: if we delete the repo after the scan, Map Room should still
        rebuild from the catalog (the catalog IS the source, not the live FS).
        """
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )
        scan_id = receipt["scan_id"]

        # Simulate the repo being deleted/moved after the scan
        shutil.rmtree(clean_repo)

        # rebuild_map_room must still work from the catalog alone
        out_path = tmp_path / "map_room_post_delete.json"
        with SystemCatalogStore(tmp_db) as store:
            terrain = rebuild_map_room(store, scan_id, out_path=str(out_path))

        assert terrain["scan_id"] == scan_id, (
            "§F-6: Map Room must rebuild from catalog even when the scanned repo no longer exists"
        )
        assert out_path.exists()

    def test_graphify_nodes_trace_to_catalog(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        §F-6: Graphify nodes must trace to catalog rows (verifiable via scan_id tag).
        Deleting the source repo after the scan must not prevent Graphify rebuild.
        """
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )
        scan_id = receipt["scan_id"]

        shutil.rmtree(clean_repo)

        out_path = tmp_path / "graphify_post_delete.json"
        with SystemCatalogStore(tmp_db) as store:
            graph = rebuild_graphify(store, scan_id, out_path=str(out_path))

        assert graph["scan_id"] == scan_id, (
            "§F-6: Graphify must rebuild from catalog even when the source repo is gone"
        )


class TestIdempotentRescan:
    """
    §F-8: Idempotent re-scan — scanning an unchanged registry twice produces
    consistent content (same logical data; a new scan_id is acceptable).
    """

    def test_rescan_produces_consistent_repo_count(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-8: Two scans of the same registry produce the same repository count."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))

        receipt_1 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T09:00:00Z",
            tool_version=TOOL_VERSION,
        )
        receipt_2 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T10:00:00Z",
            tool_version=TOOL_VERSION,
        )

        assert len(receipt_1["repositories"]) == len(receipt_2["repositories"]), (
            "§F-8: Two scans of the same registry must have the same repository count"
        )

    def test_rescan_same_branch_and_commit(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-8: Re-scan of unchanged repo must report same branch and head_commit."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))

        r1 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T09:00:00Z",
            tool_version=TOOL_VERSION,
        )
        r2 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T10:00:00Z",
            tool_version=TOOL_VERSION,
        )

        repos_1 = {r["path"]: r for r in r1["repositories"]}
        repos_2 = {r["path"]: r for r in r2["repositories"]}

        for path in repos_1:
            assert repos_1[path]["branch"] == repos_2[path]["branch"], (
                f"§F-8: branch for '{path}' must be consistent across re-scans"
            )
            assert repos_1[path]["head_commit"] == repos_2[path]["head_commit"], (
                f"§F-8: head_commit for '{path}' must be consistent across re-scans"
            )

    def test_rescan_second_is_current(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """§F-8: After two COMPLETE scans, get_current_scan returns the LATEST."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))

        r1 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T09:00:00Z",
            tool_version=TOOL_VERSION,
        )
        r2 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T10:00:00Z",
            tool_version=TOOL_VERSION,
        )

        with SystemCatalogStore(tmp_db) as store:
            current = store.get_current_scan()

        assert current is not None
        # The current must be the later scan
        assert current["scan_id"] == r2["scan_id"], (
            "§F-8: get_current_scan must return the latest COMPLETE scan after re-scan"
        )

    def test_rescan_history_preserved(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        §F-8 + D1 (append-versioned): Both scan records must coexist in the DB
        (history is retained, not overwritten).
        """
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))

        r1 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T09:00:00Z",
            tool_version=TOOL_VERSION,
        )
        r2 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T10:00:00Z",
            tool_version=TOOL_VERSION,
        )

        conn = sqlite3.connect(tmp_db)
        try:
            rows = conn.execute("SELECT scan_id FROM catalog_scans").fetchall()
        finally:
            conn.close()

        scan_ids_in_db = {row[0] for row in rows}
        assert r1["scan_id"] in scan_ids_in_db, (
            "D1: First scan must be retained in DB history after re-scan"
        )
        assert r2["scan_id"] in scan_ids_in_db, (
            "D1: Second scan must also exist in DB"
        )


class TestFreshnessIsStale:
    """
    §F-10: Freshness — is_stale flips True when a repo HEAD advances or goes
    dirty vs the catalogued scan.
    Contract: is_stale(max_age_seconds, live_head_map, now_iso) -> bool
    """

    def test_is_stale_age_not_exceeded(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """A fresh scan should NOT be stale if max_age has not elapsed."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso=NOW_ISO, tool_version=TOOL_VERSION,
        )

        with SystemCatalogStore(tmp_db) as store:
            # very large max_age → should NOT be stale
            stale = store.is_stale(max_age_seconds=999_999, now_iso=NOW_ISO)

        assert stale is False, (
            "§F-10: A just-completed scan must not be stale when max_age is very large"
        )

    def test_is_stale_age_exceeded(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """is_stale must return True when max_age_seconds=0 (scan is always older)."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso=NOW_ISO, tool_version=TOOL_VERSION,
        )

        with SystemCatalogStore(tmp_db) as store:
            stale = store.is_stale(
                max_age_seconds=0,
                now_iso="2026-06-26T10:00:00Z",  # one day later
            )

        assert stale is True, (
            "§F-10: is_stale must return True when the scan's age exceeds max_age_seconds"
        )

    def test_is_stale_head_advanced(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        §F-10: is_stale must return True when a repo's live HEAD differs from
        what was catalogued (repo committed new work after the scan).
        """
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso=NOW_ISO, tool_version=TOOL_VERSION,
        )

        # Simulate a HEAD advancement — a new commit was made
        fake_advanced_head = "0000000000000000000000000000000000000001"
        live_head_map = {str(clean_repo): {"head_commit": fake_advanced_head, "dirty": False}}

        with SystemCatalogStore(tmp_db) as store:
            stale = store.is_stale(
                max_age_seconds=999_999,
                live_head_map=live_head_map,
                now_iso=NOW_ISO,
            )

        assert stale is True, (
            "§F-10: is_stale must return True when a repo's HEAD has advanced vs the catalogued value"
        )

    def test_is_stale_dirty_changed(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        §F-10: is_stale must return True when a repo's dirty state has changed
        since the catalog was written (e.g., it was clean, now it's dirty).
        """
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso=NOW_ISO, tool_version=TOOL_VERSION,
        )

        # The clean_repo was recorded as dirty=False; now signal that it's dirty
        with SystemCatalogStore(tmp_db) as store:
            current = store.get_current_scan()
            repos = store.list_repositories(current["scan_id"])

        # Get the actual head_commit from the catalog to not trigger HEAD-change staleness
        catalogued_commit = repos[0]["head_commit"] if repos else "abc"
        live_head_map = {
            str(clean_repo): {"head_commit": catalogued_commit, "dirty": True}
        }

        with SystemCatalogStore(tmp_db) as store:
            stale = store.is_stale(
                max_age_seconds=999_999,
                live_head_map=live_head_map,
                now_iso=NOW_ISO,
            )

        assert stale is True, (
            "§F-10: is_stale must return True when a repo's dirty state has changed vs the catalog"
        )

    def test_is_stale_returns_none_when_no_complete_scan(self, tmp_db: str):
        """
        When there is no COMPLETE scan at all, is_stale behaviour:
        the spec says get_current_scan returns None → is_stale should return True
        (there is no fresh catalog to rely on).
        """
        with SystemCatalogStore(tmp_db) as store:
            stale = store.is_stale(max_age_seconds=999_999, now_iso=NOW_ISO)

        assert stale is True, (
            "§F-10: is_stale must return True (treat as stale) when there is no COMPLETE scan"
        )


class TestReadOnlySecurityAndExcludedPaths:
    """
    §F-9: The synchronizer performs no writes to any scanned repo; excluded_paths
    honored; no network/send/PII path; all tests on temp DBs + synthetic repos.
    """

    def test_synchronizer_does_not_modify_scanned_repo(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        §F-9: run_discovery_scan must not create or modify any files in the
        scanned repository directory.
        """
        before = set(clean_repo.rglob("*"))
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso=NOW_ISO, tool_version=TOOL_VERSION,
        )
        after = set(clean_repo.rglob("*"))
        new_files = after - before
        non_git_new = {f for f in new_files if ".git" not in str(f)}
        assert not non_git_new, (
            f"§F-9: run_discovery_scan must NOT write files to the scanned repo; "
            f"new files found: {non_git_new}"
        )

    def test_catalog_db_is_not_inside_scanned_repo(
        self, tmp_path: Path, clean_repo: Path
    ):
        """
        §F-9: The catalog DB must be a separate file outside the scanned repo.
        (Enforcement: the DB path is injectable and defaults outside any scanned repo.)
        """
        db_path = tmp_path / "separate_catalog.sqlite3"
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        run_discovery_scan(
            str(reg),
            catalog_db=str(db_path),
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
        )
        # Verify: the DB is at the injected path, not inside clean_repo
        assert db_path.exists(), "Catalog DB must be written to the injected path"
        assert not (clean_repo / "separate_catalog.sqlite3").exists(), (
            "§F-9: Catalog DB must NOT be placed inside the scanned repo"
        )

    def test_excluded_paths_not_in_catalog(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        §F-9: Paths listed in excluded_paths must not appear as records in the catalog.
        We add a sub-directory to the clean_repo and pass it as excluded.
        """
        excluded_sub = clean_repo / "secret_subdir"
        excluded_sub.mkdir()
        (excluded_sub / "private.txt").write_text("secret content")

        reg = tmp_path / "REGISTRY.md"
        # Register the parent repo normally; excluded_paths is passed to parse step
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))

        run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
            excluded_paths=[str(excluded_sub)],
        )

        # No catalog entry (component, capability, queue, handoff, test) should
        # reference the excluded path
        conn = sqlite3.connect(tmp_db)
        try:
            for table in ("components", "capabilities", "queues", "handoffs", "tests"):
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                col_names = [d[0] for d in conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()]
                for row in rows:
                    row_dict = dict(zip(col_names, row))
                    for v in row_dict.values():
                        if isinstance(v, str) and str(excluded_sub) in v:
                            pytest.fail(
                                f"§F-9: excluded path '{excluded_sub}' found in "
                                f"catalog table '{table}': {row_dict}"
                            )
        finally:
            conn.close()

    def test_no_pii_or_domain_columns_in_catalog_schema(self, tmp_db: str):
        """
        §F-3 + §F-9: The catalog schema must not contain columns for business domain
        data, invoices, raw PII, or message bodies. We inspect the actual DDL.
        """
        # Open the store to trigger migrations
        with SystemCatalogStore(tmp_db):
            pass

        forbidden_column_names = {
            "invoice_total", "invoice_number", "amount", "message_body",
            "email_body", "pii_data", "raw_content", "legal_text",
            "phone_number", "ssn", "tax_id",
        }
        conn = sqlite3.connect(tmp_db)
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            for (table_name,) in tables:
                cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                col_names = {c[1].lower() for c in cols}
                overlap = forbidden_column_names & col_names
                assert not overlap, (
                    f"§F-3: Catalog table '{table_name}' contains forbidden domain/PII "
                    f"column(s): {overlap}"
                )
        finally:
            conn.close()

    def test_run_discovery_scan_accepts_excluded_paths_kwarg(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        §F-9: run_discovery_scan must accept an excluded_paths parameter without error.
        (Verifies the interface supports the security gate, even if no paths are excluded.)
        """
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        # Must not raise
        receipt = run_discovery_scan(
            str(reg),
            catalog_db=tmp_db,
            now_iso=NOW_ISO,
            tool_version=TOOL_VERSION,
            excluded_paths=[str(tmp_path / "nonexistent_exclude")],
        )
        assert receipt is not None


class TestScanScopeAndScanId:
    """
    §F-2 (scan-scoped writes, two scans coexist, get_current_scan returns latest COMPLETE)
    and scan_id integrity tests exercised via discovery integration.
    """

    def test_all_catalog_rows_carry_scan_id(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """
        Every row in every content table must carry the correct scan_id.
        This verifies the single-scan-id principle from spec §A-2 + §F-2.
        """
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso=NOW_ISO, tool_version=TOOL_VERSION,
        )
        expected_scan_id = receipt["scan_id"]

        conn = sqlite3.connect(tmp_db)
        try:
            for table in ("repositories", "worktrees", "components", "capabilities",
                          "queues", "handoffs", "tests"):
                rows = conn.execute(f"SELECT scan_id FROM {table}").fetchall()
                for (sid,) in rows:
                    assert sid == expected_scan_id, (
                        f"§F-2: row in '{table}' has scan_id '{sid}', "
                        f"expected '{expected_scan_id}'"
                    )
        finally:
            conn.close()

    def test_receipt_scan_id_starts_with_syscat(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """The scan_id in the receipt must follow the SYSCAT- format."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))
        receipt = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso=NOW_ISO, tool_version=TOOL_VERSION,
        )
        assert receipt["scan_id"].startswith("SYSCAT-"), (
            f"scan_id must start with 'SYSCAT-'; got '{receipt['scan_id']}'"
        )

    def test_two_scans_different_scan_ids(
        self, tmp_path: Path, tmp_db: str, clean_repo: Path
    ):
        """Two sequential scans at different times must produce different scan_ids."""
        reg = tmp_path / "REGISTRY.md"
        reg.write_text(_make_registry_md([{"repo_path": str(clean_repo)}]))

        r1 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T09:00:00Z",
            tool_version=TOOL_VERSION,
        )
        r2 = run_discovery_scan(
            str(reg), catalog_db=tmp_db, now_iso="2026-06-25T10:00:00Z",
            tool_version=TOOL_VERSION,
        )
        assert r1["scan_id"] != r2["scan_id"], (
            "Scans at different times must produce different scan_ids"
        )
