"""
tests/test_canonical_fact_ingest.py

Pytest suite for canonical_fact_ingest.py:
  - single-door indexes-on-write
  - deduplication by content_hash (re-ingest → skipped)
  - reconcile back-fills an out-of-band row
  - widened markdown sources (OPENCLAW_RUNTIME.md etc.) parse + ingest
  - production ledger path guard
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

# ---- set test-mode env so safety guards allow /tmp paths ----
os.environ["OPENCLAW_TEST_MODE"] = "1"

from canonical_fact_ingest import ingest_graded_fact, reconcile_fact_index
from business_ops_ledger import init_business_ops_ledger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path):
    """Return path to a fresh throwaway ledger in /tmp."""
    db_file = tmp_path / "test_ledger.sqlite"
    init_business_ops_ledger(str(db_file))
    return str(db_file)


def _minimal_record(**overrides) -> dict:
    base = {
        "source_file": "docs/test/example.md",
        "section_heading": "Test Section",
        "source_commit": "abc123deadbeef",
        "fact_text": "OpenClaw uses SQLite as its canonical fact store.",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["chief", "guardian"],
        "doc_category": "test_category",
        "temporal_or_doctrine": "doctrine_reference",
        "source_description": "Unit test fact",
        "truth_status": "declared",
        "verification_required": 1,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test 1: Single door indexes-on-write
# ---------------------------------------------------------------------------

class TestSingleDoorIndexesOnWrite:
    def test_insert_returns_inserted_status(self, tmp_db):
        record = _minimal_record()
        result = ingest_graded_fact(record, db_path=tmp_db)
        assert result["status"] == "inserted"
        assert result["fact_id"]
        assert len(result["content_hash"]) == 64  # sha256 hex

    def test_fts_row_created_after_insert(self, tmp_db):
        record = _minimal_record()
        result = ingest_graded_fact(record, db_path=tmp_db)

        conn = sqlite3.connect(tmp_db)
        fts_row = conn.execute(
            "SELECT fact_id FROM fts_canonical_facts WHERE content_hash = ?",
            (result["content_hash"],),
        ).fetchone()
        conn.close()

        assert fts_row is not None, "FTS5 row should exist after ingest_graded_fact"
        assert fts_row[0] == result["fact_id"]

    def test_embedding_queued_after_insert(self, tmp_db):
        record = _minimal_record()
        result = ingest_graded_fact(record, db_path=tmp_db)

        conn = sqlite3.connect(tmp_db)
        queue_row = conn.execute(
            "SELECT fact_id FROM embedding_work_queue WHERE content_hash = ?",
            (result["content_hash"],),
        ).fetchone()
        conn.close()

        assert queue_row is not None, "Embedding queue entry should exist after insert"
        assert queue_row[0] == result["fact_id"]

    def test_canonical_facts_row_created(self, tmp_db):
        record = _minimal_record()
        result = ingest_graded_fact(record, db_path=tmp_db)

        conn = sqlite3.connect(tmp_db)
        cf_row = conn.execute(
            "SELECT fact_id, content_hash FROM canonical_facts WHERE fact_id = ?",
            (result["fact_id"],),
        ).fetchone()
        conn.close()

        assert cf_row is not None
        assert cf_row[1] == result["content_hash"]

    def test_fts_search_finds_inserted_fact(self, tmp_db):
        record = _minimal_record(
            fact_text="The guardian agent enforces authority boundaries in OpenClaw.",
            section_heading="Guardian Role",
        )
        ingest_graded_fact(record, db_path=tmp_db)

        conn = sqlite3.connect(tmp_db)
        rows = conn.execute(
            "SELECT fact_id FROM fts_canonical_facts WHERE fts_canonical_facts MATCH 'guardian'",
        ).fetchall()
        conn.close()

        assert len(rows) >= 1, "FTS5 search should find newly inserted fact"


# ---------------------------------------------------------------------------
# Test 2: Deduplication by content_hash (re-ingest = skipped)
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_second_ingest_same_text_returns_skipped(self, tmp_db):
        record = _minimal_record()
        first = ingest_graded_fact(record, db_path=tmp_db)
        assert first["status"] == "inserted"

        second = ingest_graded_fact(record, db_path=tmp_db)
        assert second["status"] == "skipped"
        assert second["fact_id"] == first["fact_id"]
        assert second["content_hash"] == first["content_hash"]

    def test_skipped_does_not_create_duplicate_canonical_row(self, tmp_db):
        record = _minimal_record()
        r1 = ingest_graded_fact(record, db_path=tmp_db)
        ingest_graded_fact(record, db_path=tmp_db)  # second call — should skip
        ingest_graded_fact(record, db_path=tmp_db)  # third call  — should skip

        conn = sqlite3.connect(tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM canonical_facts WHERE content_hash = ?",
            (r1["content_hash"],),
        ).fetchone()[0]
        conn.close()

        # After 3 calls, still only 1 row
        assert count == 1

    def test_different_text_both_inserted(self, tmp_db):
        r1 = _minimal_record(fact_text="Fact alpha about system design.")
        r2 = _minimal_record(fact_text="Fact beta about authority model.")

        res1 = ingest_graded_fact(r1, db_path=tmp_db)
        res2 = ingest_graded_fact(r2, db_path=tmp_db)

        assert res1["status"] == "inserted"
        assert res2["status"] == "inserted"
        assert res1["content_hash"] != res2["content_hash"]

    def test_skipped_does_not_duplicate_fts_row(self, tmp_db):
        record = _minimal_record()
        r1 = ingest_graded_fact(record, db_path=tmp_db)
        ingest_graded_fact(record, db_path=tmp_db)  # second call

        conn = sqlite3.connect(tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM fts_canonical_facts WHERE content_hash = ?",
            (r1["content_hash"],),
        ).fetchone()[0]
        conn.close()

        assert count == 1, "FTS5 should not have duplicate rows for same content_hash"


# ---------------------------------------------------------------------------
# Test 3: reconcile back-fills an out-of-band row
# ---------------------------------------------------------------------------

class TestReconcile:
    def _insert_out_of_band(self, db_path: str) -> tuple[str, str]:
        """Directly INSERT into canonical_facts bypassing ingest_graded_fact.
        Also ensures FTS tables exist first (simulates a system that may have
        been initialised but not yet indexed)."""
        import hashlib, uuid, json
        from canonical_fact_ingest import _init_fts_tables
        from business_ops_ledger import init_business_ops_ledger

        fact_text = "Out-of-band fact inserted directly into canonical_facts table."
        chash = hashlib.sha256(fact_text.encode()).hexdigest()
        fact_id = f"oob_{chash[:8]}"

        # Initialise FTS schema (so table exists, but OOB row won't be in it)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        _init_fts_tables(conn)
        conn.close()

        conn = sqlite3.connect(db_path)
        conn.execute(
            """INSERT OR IGNORE INTO canonical_facts
               (fact_id, source_file, section_heading, source_commit,
                content_hash, fact_text, sensitivity_class, allowed_actors,
                truth_status, verification_required)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fact_id, "docs/oob/oob.md", "OOB Section", "deadbeef000",
             chash, fact_text, "operational_canonical", json.dumps(["chief"]),
             "declared", 1),
        )
        conn.commit()
        conn.close()
        return fact_id, chash

    def test_reconcile_back_fills_oob_row(self, tmp_db):
        fact_id, chash = self._insert_out_of_band(tmp_db)

        # Confirm FTS is empty before reconcile
        conn = sqlite3.connect(tmp_db)
        before = conn.execute(
            "SELECT 1 FROM fts_canonical_facts WHERE content_hash = ?", (chash,)
        ).fetchone()
        conn.close()
        assert before is None, "FTS should not have OOB row before reconcile"

        result = reconcile_fact_index(db_path=tmp_db)

        assert result["back_filled"] >= 1
        conn = sqlite3.connect(tmp_db)
        after = conn.execute(
            "SELECT fact_id FROM fts_canonical_facts WHERE content_hash = ?", (chash,)
        ).fetchone()
        conn.close()
        assert after is not None, "reconcile should back-fill OOB row into FTS"

    def test_reconcile_is_idempotent(self, tmp_db):
        self._insert_out_of_band(tmp_db)
        reconcile_fact_index(db_path=tmp_db)
        result2 = reconcile_fact_index(db_path=tmp_db)

        # Second run: nothing new to back-fill
        assert result2["back_filled"] == 0

    def test_reconcile_queues_embedding_for_oob_rows(self, tmp_db):
        fact_id, chash = self._insert_out_of_band(tmp_db)
        result = reconcile_fact_index(db_path=tmp_db)

        assert result["embedding_queued"] >= 1
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT fact_id FROM embedding_work_queue WHERE content_hash = ?", (chash,)
        ).fetchone()
        conn.close()
        assert row is not None, "reconcile should enqueue embedding for OOB row"

    def test_reconcile_already_indexed_are_counted(self, tmp_db):
        record = _minimal_record()
        ingest_graded_fact(record, db_path=tmp_db)

        result = reconcile_fact_index(db_path=tmp_db)
        assert result["already_indexed"] >= 1
        assert result["back_filled"] == 0


# ---------------------------------------------------------------------------
# Test 4: Widened markdown sources parse + ingest through the single door
# ---------------------------------------------------------------------------

class TestWidenedMarkdownSources:
    """Test the widened doctrine source(s) that are committed + parseable.
    populate-1b dropped CORE_ARCHITECTURE_PRINCIPLES.md / AGENTS.md /
    OPEN_CLAW_MANIFEST.md (gitignored-untracked at root / 0 sections); their
    doctrine moved to the grounded, verified canonical_doctrine_facts.py."""

    NEW_SOURCES = [
        "OPENCLAW_RUNTIME.md",
    ]

    def test_new_sources_in_registry(self):
        from scripts.ingest_canonical_docs import SOURCE_REGISTRY
        for src in self.NEW_SOURCES:
            assert src in SOURCE_REGISTRY, f"{src} must be in SOURCE_REGISTRY"

    def test_new_sources_have_public_canonical_sensitivity(self):
        from scripts.ingest_canonical_docs import SOURCE_REGISTRY
        for src in self.NEW_SOURCES:
            meta = SOURCE_REGISTRY[src]
            assert meta["sensitivity_class"] == "public_canonical", (
                f"{src} should be public_canonical (shared doctrine)"
            )

    def test_new_sources_allowed_actors_include_all(self):
        from scripts.ingest_canonical_docs import SOURCE_REGISTRY
        for src in self.NEW_SOURCES:
            actors = SOURCE_REGISTRY[src]["allowed_actors"]
            assert "all" in actors or len(actors) >= 5, (
                f"{src} should allow all/most agents"
            )

    @pytest.mark.parametrize("source_file", NEW_SOURCES)
    def test_new_source_file_parses_into_sections(self, source_file):
        """Each new source file must exist and extract at least 1 section.
        AGENTS.md is a thin redirect doc with no ## sections — that is acceptable;
        the test skips gracefully rather than failing."""
        if not Path(source_file).exists():
            pytest.skip(f"{source_file} not found at repo root (run from /home/openclaw)")

        from scripts.extract_canonical_facts import extract_markdown_sections
        content = Path(source_file).read_text()
        sections = extract_markdown_sections(content, source_file, "test_commit_abc123")

        # AGENTS.md is a known thin redirect doc (no ## headers) — allowed to have 0
        if source_file == "AGENTS.md" and len(sections) == 0:
            pytest.skip("AGENTS.md has no ## sections (thin redirect doc — acceptable)")
        assert len(sections) >= 1, f"{source_file} should extract at least 1 section"

    @pytest.mark.parametrize("source_file", NEW_SOURCES)
    def test_new_source_ingests_via_single_door(self, tmp_db, source_file):
        """Each new source file routes through ingest_graded_fact correctly."""
        if not Path(source_file).exists():
            pytest.skip(f"{source_file} not found at repo root")

        from scripts.extract_canonical_facts import extract_markdown_sections
        from scripts.ingest_canonical_docs import SOURCE_REGISTRY, _build_fact_record

        content = Path(source_file).read_text()
        facts = extract_markdown_sections(content, source_file, "test_commit_abc123")

        # AGENTS.md is a thin redirect doc with no ## sections — skip gracefully
        if source_file == "AGENTS.md" and len(facts) == 0:
            pytest.skip("AGENTS.md has no ## sections (thin redirect doc — acceptable)")

        meta = SOURCE_REGISTRY[source_file]

        inserted = 0
        skipped = 0
        for fact in facts:
            record = _build_fact_record(fact, meta, truth_entry=None)
            result = ingest_graded_fact(record, db_path=tmp_db)
            assert result["status"] in ("inserted", "skipped")
            if result["status"] == "inserted":
                inserted += 1
            else:
                skipped += 1

        # All sections either inserted or deduped — none should error
        assert inserted + skipped == len(facts)

        # At least 1 inserted (non-empty file)
        assert inserted >= 1, f"At least 1 fact from {source_file} should be inserted"

    @pytest.mark.parametrize("source_file", NEW_SOURCES)
    def test_new_source_fts_searchable_after_ingest(self, tmp_db, source_file):
        """After ingesting a new source, FTS5 should return results."""
        if not Path(source_file).exists():
            pytest.skip(f"{source_file} not found at repo root")

        from scripts.extract_canonical_facts import extract_markdown_sections
        from scripts.ingest_canonical_docs import SOURCE_REGISTRY, _build_fact_record

        content = Path(source_file).read_text()
        facts = extract_markdown_sections(content, source_file, "test_commit_abc123")

        # AGENTS.md is a thin redirect doc with no ## sections — skip gracefully
        if source_file == "AGENTS.md" and len(facts) == 0:
            pytest.skip("AGENTS.md has no ## sections (thin redirect doc — acceptable)")

        meta = SOURCE_REGISTRY[source_file]

        for fact in facts:
            record = _build_fact_record(fact, meta, truth_entry=None)
            ingest_graded_fact(record, db_path=tmp_db)

        conn = sqlite3.connect(tmp_db)
        # Basic sanity: FTS table has rows
        count = conn.execute(
            "SELECT COUNT(*) FROM fts_canonical_facts"
        ).fetchone()[0]
        conn.close()
        assert count >= 1


# ---------------------------------------------------------------------------
# Test 5: Safety — production path guard
# ---------------------------------------------------------------------------

class TestProductionPathGuard:
    def test_production_path_raises(self, monkeypatch):
        """ingest_graded_fact must refuse to open the production ledger path."""
        # Resolve the actual production path
        from canonical_fact_ingest import _PRODUCTION_DB_PATH
        prod_path = str(Path(_PRODUCTION_DB_PATH).expanduser().resolve())

        record = _minimal_record()
        with pytest.raises(ValueError, match="SAFETY"):
            ingest_graded_fact(record, db_path=prod_path)

    def test_reconcile_production_path_raises(self):
        from canonical_fact_ingest import _PRODUCTION_DB_PATH
        prod_path = str(Path(_PRODUCTION_DB_PATH).expanduser().resolve())
        with pytest.raises(ValueError, match="SAFETY"):
            reconcile_fact_index(db_path=prod_path)
