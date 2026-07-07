from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _init_context_source_ledger(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE canonical_facts (
            fact_id TEXT PRIMARY KEY,
            source_file TEXT NOT NULL,
            section_heading TEXT NOT NULL,
            source_commit TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            fact_text TEXT NOT NULL,
            sensitivity_class TEXT NOT NULL,
            allowed_actors TEXT NOT NULL,
            doc_category TEXT,
            temporal_or_doctrine TEXT,
            source_description TEXT,
            ingested_at TEXT
        );
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
        CREATE TABLE corpus_paths (
            path_id TEXT PRIMARY KEY,
            root_id TEXT,
            absolute_path TEXT,
            relative_path TEXT,
            path_name TEXT,
            path_type TEXT,
            tracked_status TEXT,
            size_bytes INTEGER,
            mtime TEXT,
            freshness_label TEXT,
            sensitivity_label TEXT,
            raw_content_eligibility TEXT,
            canonicality TEXT
        );
        CREATE TABLE corpus_sensitivity_labels (
            label_id TEXT PRIMARY KEY,
            path_id TEXT,
            sensitivity_label TEXT,
            label_basis TEXT,
            created_at TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO canonical_facts (
            fact_id, source_file, section_heading, source_commit, content_hash,
            fact_text, sensitivity_class, allowed_actors, doc_category,
            temporal_or_doctrine, source_description, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "fact_openclaw",
            "docs/operations/OPENCLAW.md",
            "Runtime",
            "abc123",
            "hash-openclaw",
            "OpenClaw has one robust business ops ledger.",
            "operational_canonical",
            json.dumps(["maestro", "all"]),
            "operations",
            "doctrine",
            "test fact",
            "2026-06-29T00:00:00+00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO agent_lanes (
            agent_id, display_name, lane_id, lane_label, status, authority_level,
            role_summary, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "hermes",
            "Hermes",
            "advisory_systems",
            "Advisory Systems",
            "active_registry",
            "advisory_only",
            "Advisory systems engineer.",
            "2026-06-29T00:00:00+00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO corpus_paths (
            path_id, root_id, absolute_path, relative_path, path_name, path_type,
            tracked_status, size_bytes, mtime, freshness_label, sensitivity_label,
            raw_content_eligibility, canonicality
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "path_safe",
            "root",
            "/home/openclaw/maestro_context_packet.py",
            "maestro_context_packet.py",
            "maestro_context_packet.py",
            "file",
            "tracked",
            123,
            "2026-06-29T00:00:00+00:00",
            "current",
            "internal_project",
            "metadata_only",
            "canonical_current",
        ),
    )
    conn.execute(
        """
        INSERT INTO corpus_paths (
            path_id, root_id, absolute_path, relative_path, path_name, path_type,
            tracked_status, size_bytes, mtime, freshness_label, sensitivity_label,
            raw_content_eligibility, canonicality
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "path_secret",
            "root",
            "/home/openclaw/.chief.env",
            ".chief.env",
            ".chief.env",
            "file",
            "untracked",
            1,
            "2026-06-29T00:00:00+00:00",
            "current",
            "secret",
            "blocked_secret",
            "excluded",
        ),
    )
    conn.execute(
        """
        INSERT INTO corpus_sensitivity_labels (
            label_id, path_id, sensitivity_label, label_basis, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("label_secret", "path_secret", "secret", "test", "2026-06-29T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()


def test_context_source_reads_ledger_and_filters_sensitive_paths(tmp_path: Path) -> None:
    from context_source import build_ledger_context_facts, facts_have_ledger_provenance

    ledger = tmp_path / "ledger.sqlite"
    _init_context_source_ledger(ledger)

    facts = build_ledger_context_facts(
        question="what does OpenClaw know?",
        agent_id="maestro",
        db_path=ledger,
        limit=8,
    )

    assert facts
    assert facts_have_ledger_provenance(facts)
    joined = json.dumps(facts, sort_keys=True)
    assert "one robust business ops ledger" in joined
    assert "Hermes" in joined
    assert ".chief.env" not in joined


def test_context_source_adds_ledger_provenance_without_rewriting_source_ref(tmp_path: Path) -> None:
    from context_source import annotate_facts_with_ledger_provenance

    ledger = tmp_path / "ledger.sqlite"
    _init_context_source_ledger(ledger)
    facts = [
        {
            "fact_id": "presence:1",
            "topic": "agent_presence",
            "label": "Presence",
            "value": "Hermes online",
            "source_ref": "generated/read_models/agent_presence.json",
            "provenance": "generated_read_model",
        }
    ]

    enriched = annotate_facts_with_ledger_provenance(
        facts,
        builder_name="test_builder",
        db_path=ledger,
    )

    assert enriched[0]["source_ref"] == "generated/read_models/agent_presence.json"
    assert enriched[0]["ledger_source_ref"].startswith("ledger:")
    assert enriched[0]["ledger_provenance"]["source_of_truth"] == "business_ops_ledger"
    assert enriched[0]["ledger_provenance"]["projection_source_ref"] == (
        "generated/read_models/agent_presence.json"
    )


def test_polish_loop_builder_context_packet_prioritizes_build_doctrine(tmp_path: Path) -> None:
    from polish_loop.worker_runtime import build_polish_loop_build_context_packet

    ledger = tmp_path / "ledger.sqlite"
    _init_context_source_ledger(ledger)
    conn = sqlite3.connect(ledger)
    for index in range(12):
        conn.execute(
            """
            INSERT INTO canonical_facts (
                fact_id, source_file, section_heading, source_commit, content_hash,
                fact_text, sensitivity_class, allowed_actors, doc_category,
                temporal_or_doctrine, source_description, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"newer_fact_{index}",
                "docs/runtime.md",
                f"Newer fact {index}",
                "abc123",
                f"hash-newer-{index}",
                f"Newer operational fact {index}.",
                "operational_canonical",
                json.dumps(["all"]),
                "operations",
                "temporal_checkpoint",
                "crowding fixture",
                f"2026-07-07T12:{index:02d}:00+00:00",
            ),
        )
    conn.execute(
        """
        INSERT INTO canonical_facts (
            fact_id, source_file, section_heading, source_commit, content_hash,
            fact_text, sensitivity_class, allowed_actors, doc_category,
            temporal_or_doctrine, source_description, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "build_doctrine_class_level_fixes",
            "Operator/build-doctrine.md",
            "Class-Level Build Doctrine",
            "abc123",
            "hash-build-doctrine",
            "When builders or self-heal loops fix a failure, fix the failure class when sibling evidence exists.",
            "operational_canonical",
            json.dumps(["all", "polish_loop_builder"]),
            "build_doctrine",
            "doctrine_reference",
            "operator directive",
            "2026-07-07T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    packet = build_polish_loop_build_context_packet(
        goal="repair a repeated class-level build failure",
        db_path=ledger,
    )

    joined = json.dumps(packet, sort_keys=True)
    assert "build_doctrine" in joined
    assert "fix the failure class when sibling evidence exists" in joined
