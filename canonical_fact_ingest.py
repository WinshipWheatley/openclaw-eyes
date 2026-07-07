"""
canonical_fact_ingest.py — Single-door canonical fact ingestion with FTS5 index.

NB-2 compliance: indexing is PART of the write, never a separate watcher.
Every call to ingest_graded_fact maintains the retrieval index inline.

HARD RULES:
- NEVER opens .openclaw/business_ops/ledger.sqlite directly.
- db_path must be supplied explicitly or via OPENCLAW_LEDGER_PATH env var.
- In production, the caller is responsible for passing a non-production path
  when running tests.
"""

import hashlib
import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import (
    init_business_ops_ledger,
    record_canonical_fact,
    resolve_business_ops_ledger_path,
)
from fact_refinement import (
    ensure_fact_refinement_columns,
    refine_fact_record_for_ingest,
    store_fact_refinement_metadata,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PRODUCTION_DB_PATH = ".openclaw/business_ops/ledger.sqlite"


def _guard_production_path(path: str, allow_production: bool = False) -> None:
    """Raise if path resolves to the live production ledger, UNLESS the caller is
    explicitly, deliberately authorized (allow_production=True).

    Default refuses — no build/test path can write the real ledger by accident.
    The ONLY sanctioned writer is scripts/populate_real_ledger.py, run under a
    one-use operator approval; it passes allow_production=True after its own
    explicit --confirm gate. Everything else stays hard-blocked."""
    resolved = str(Path(path).expanduser().resolve())
    production_resolved = str(Path(_PRODUCTION_DB_PATH).expanduser().resolve())
    if resolved == production_resolved and not allow_production:
        raise ValueError(
            "SAFETY: refuses to write the production ledger. Supply a test/temp db_path, "
            "or use the sanctioned, operator-approved populate_real_ledger.py."
        )


def _connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _init_fts_tables(conn: sqlite3.Connection) -> None:
    """
    Create the FTS5 virtual table and the embedding-work queue if absent.

    fts_canonical_facts  — standalone FTS5 index over fact_text, section_heading,
                           doc_category. Standalone (no content=) so MATCH queries
                           work without joining back to canonical_facts rows.
    embedding_work_queue — Pending-embedding marker rows (content_hash + fact_id).
    """
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_canonical_facts
        USING fts5(
            fact_id UNINDEXED,
            content_hash UNINDEXED,
            fact_text,
            section_heading,
            doc_category
        );

        CREATE TABLE IF NOT EXISTS embedding_work_queue (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT NOT NULL,
            fact_id      TEXT NOT NULL,
            queued_at    TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(content_hash)
        );
    """)
    conn.commit()


def _content_hash(fact_text: str) -> str:
    return hashlib.sha256(fact_text.encode("utf-8")).hexdigest()


def _validate_record(record: dict[str, Any], fact_text: str) -> None:
    if not all([record.get("source_file"), record.get("section_heading"), record.get("source_commit")]):
        raise ValueError("Missing mandatory provenance fields.")
    allowed_sensitivity = {"public_canonical", "operational_canonical", "non_sensitive"}
    sensitivity = record.get("sensitivity_class", "operational_canonical")
    if sensitivity not in allowed_sensitivity:
        raise ValueError(f"Invalid sensitivity_class: {sensitivity}")
    pii_patterns = [
        r"\d{3}-\d{2}-\d{4}",
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        r"\d{3}-\d{3}-\d{4}",
    ]
    for pattern in pii_patterns:
        if re.search(pattern, fact_text):
            raise ValueError("PII detected in fact_text.")


def _fact_exists_by_hash(conn: sqlite3.Connection, chash: str) -> tuple[bool, str | None]:
    """Return (exists, fact_id_or_None)."""
    row = conn.execute(
        "SELECT fact_id FROM canonical_facts WHERE content_hash = ? LIMIT 1",
        (chash,),
    ).fetchone()
    if row:
        return True, row["fact_id"]
    return False, None


def _fact_by_id(conn: sqlite3.Connection, fact_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT fact_id, content_hash FROM canonical_facts WHERE fact_id = ? LIMIT 1",
        (fact_id,),
    ).fetchone()


def _index_fact(conn: sqlite3.Connection, fact_id: str, chash: str,
                fact_text: str, section_heading: str, doc_category: str | None) -> None:
    """Insert into standalone FTS5 table (idempotent — checked by caller)."""
    # Guard: skip if content_hash already in FTS (idempotent)
    existing = conn.execute(
        "SELECT 1 FROM fts_canonical_facts WHERE content_hash = ? LIMIT 1",
        (chash,),
    ).fetchone()
    if existing:
        return
    conn.execute(
        """INSERT INTO fts_canonical_facts (fact_id, content_hash, fact_text, section_heading, doc_category)
           VALUES (?, ?, ?, ?, ?)""",
        (fact_id, chash, fact_text, section_heading or "", doc_category or ""),
    )


def _enqueue_embedding(conn: sqlite3.Connection, chash: str, fact_id: str) -> None:
    """Enqueue a needs_embedding marker (ignore if already present)."""
    conn.execute(
        """INSERT OR IGNORE INTO embedding_work_queue (content_hash, fact_id, queued_at)
           VALUES (?, ?, ?)""",
        (chash, fact_id, datetime.now(timezone.utc).isoformat()),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_graded_fact(record: dict[str, Any], db_path: str | None = None, allow_production: bool = False) -> dict[str, Any]:
    """
    THE SINGLE DOOR for writing a canonical fact.

    Steps (all inline, atomically committed):
      1. Resolve and guard the db path.
      2. Ensure ledger schema + FTS tables exist.
      3. Compute content_hash; skip if already present (deduplication).
      4. Call record_canonical_fact (validates PII, inserts into canonical_facts).
      5. Maintain FTS5 index inline.
      6. Enqueue needs_embedding marker.

    Args:
        record: dict with keys matching record_canonical_fact signature, plus optional
                'fact_id' (auto-generated uuid if absent).
        db_path: explicit path to SQLite ledger. REQUIRED for safety — never defaults
                 to the production ledger.

    Returns:
        {'status': 'inserted'|'skipped', 'fact_id': str, 'content_hash': str}
    """
    requested_path = str(db_path or os.environ.get("OPENCLAW_LEDGER_PATH") or _PRODUCTION_DB_PATH)
    _guard_production_path(requested_path, allow_production=allow_production)
    path = resolve_business_ops_ledger_path(db_path)
    _guard_production_path(path, allow_production=allow_production)

    refinement = refine_fact_record_for_ingest(record)
    record = refinement.record
    fact_text = record.get("fact_text", "")
    if not fact_text or not fact_text.strip():
        raise ValueError("record['fact_text'] cannot be empty.")
    _validate_record(record, fact_text)

    chash = _content_hash(fact_text)

    # Ensure schema (idempotent)
    init_business_ops_ledger(path)
    conn = _connect(path)
    _init_fts_tables(conn)
    ensure_fact_refinement_columns(conn)

    try:
        # Deduplication check
        exists, existing_id = _fact_exists_by_hash(conn, chash)
        if exists:
            if existing_id:
                store_fact_refinement_metadata(
                    conn,
                    fact_id=existing_id,
                    metadata=refinement.metadata,
                    db_path=path,
                )
                conn.commit()
            conn.close()
            return {"status": "skipped", "fact_id": existing_id, "content_hash": chash}

        fact_id = record.get("fact_id") or f"fact_{chash[:12]}"
        existing_by_id = _fact_by_id(conn, fact_id)

        if existing_by_id and existing_by_id["content_hash"] != chash:
            old_hash = existing_by_id["content_hash"]
            conn.execute(
                """UPDATE canonical_facts
                   SET source_file = ?,
                       section_heading = ?,
                       source_commit = ?,
                       content_hash = ?,
                       fact_text = ?,
                       sensitivity_class = ?,
                       allowed_actors = ?,
                       doc_category = ?,
                       temporal_or_doctrine = ?,
                       source_description = ?,
                       truth_source_id = ?,
                       truth_status = ?,
                       verification_required = ?,
                       verification_evidence_id = ?
                   WHERE fact_id = ?""",
                (
                    record["source_file"],
                    record["section_heading"],
                    record["source_commit"],
                    chash,
                    fact_text,
                    record.get("sensitivity_class", "operational_canonical"),
                    json.dumps(record.get("allowed_actors", [])),
                    record.get("doc_category"),
                    record.get("temporal_or_doctrine"),
                    record.get("source_description"),
                    record.get("truth_source_id"),
                    record.get("truth_status", "declared"),
                    record.get("verification_required", 1),
                    record.get("verification_evidence_id"),
                    fact_id,
                ),
            )
            conn.execute("DELETE FROM fts_canonical_facts WHERE content_hash = ?", (old_hash,))
            conn.execute("DELETE FROM embedding_work_queue WHERE content_hash = ?", (old_hash,))
            _index_fact(
                conn,
                fact_id,
                chash,
                fact_text,
                record.get("section_heading", ""),
                record.get("doc_category"),
            )
            _enqueue_embedding(conn, chash, fact_id)
            store_fact_refinement_metadata(
                conn,
                fact_id=fact_id,
                metadata=refinement.metadata,
                db_path=path,
            )
            conn.commit()
            return {
                "status": "replaced",
                "fact_id": fact_id,
                "content_hash": chash,
                "old_content_hash": old_hash,
            }

        # Delegate write + PII validation to the existing low-level function
        record_canonical_fact(
            fact_id=fact_id,
            source_file=record["source_file"],
            section_heading=record["section_heading"],
            source_commit=record["source_commit"],
            fact_text=fact_text,
            sensitivity_class=record.get("sensitivity_class", "operational_canonical"),
            allowed_actors=record.get("allowed_actors", []),
            doc_category=record.get("doc_category"),
            temporal_or_doctrine=record.get("temporal_or_doctrine"),
            source_description=record.get("source_description"),
            truth_source_id=record.get("truth_source_id"),
            truth_status=record.get("truth_status", "declared"),
            verification_required=record.get("verification_required", 1),
            verification_evidence_id=record.get("verification_evidence_id"),
            db_path=path,
        )

        # Inline FTS index maintenance (NB-2 compliance)
        _index_fact(
            conn,
            fact_id,
            chash,
            fact_text,
            record.get("section_heading", ""),
            record.get("doc_category"),
        )

        # Enqueue embedding work
        _enqueue_embedding(conn, chash, fact_id)
        store_fact_refinement_metadata(
            conn,
            fact_id=fact_id,
            metadata=refinement.metadata,
            db_path=path,
        )

        conn.commit()
        return {"status": "inserted", "fact_id": fact_id, "content_hash": chash}

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reconcile_fact_index(db_path: str | None = None, allow_production: bool = False) -> dict[str, Any]:
    """
    Deterministic, idempotent sweep to back-fill the FTS5 index for any
    canonical_facts row missing from fts_canonical_facts (keyed by content_hash).

    Safety net for out-of-band inserts that bypass ingest_graded_fact.

    Returns:
        {'back_filled': int, 'already_indexed': int, 'embedding_queued': int}
    """
    requested_path = str(db_path or os.environ.get("OPENCLAW_LEDGER_PATH") or _PRODUCTION_DB_PATH)
    _guard_production_path(requested_path, allow_production=allow_production)
    path = resolve_business_ops_ledger_path(db_path)
    _guard_production_path(path, allow_production=allow_production)

    init_business_ops_ledger(path)
    conn = _connect(path)
    _init_fts_tables(conn)

    try:
        rows = conn.execute(
            "SELECT fact_id, content_hash, fact_text, section_heading, doc_category "
            "FROM canonical_facts"
        ).fetchall()

        back_filled = 0
        already_indexed = 0
        embedding_queued = 0

        for row in rows:
            fact_id = row["fact_id"]
            chash = row["content_hash"]
            in_fts = conn.execute(
                "SELECT 1 FROM fts_canonical_facts WHERE content_hash = ? LIMIT 1",
                (chash,),
            ).fetchone()

            if in_fts:
                already_indexed += 1
            else:
                _index_fact(
                    conn,
                    fact_id,
                    chash,
                    row["fact_text"],
                    row["section_heading"],
                    row["doc_category"],
                )
                back_filled += 1

            # Also ensure embedding queue entry exists
            in_queue = conn.execute(
                "SELECT 1 FROM embedding_work_queue WHERE content_hash = ? LIMIT 1",
                (chash,),
            ).fetchone()
            if not in_queue:
                _enqueue_embedding(conn, chash, fact_id)
                embedding_queued += 1

        conn.commit()
        return {
            "back_filled": back_filled,
            "already_indexed": already_indexed,
            "embedding_queued": embedding_queued,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
