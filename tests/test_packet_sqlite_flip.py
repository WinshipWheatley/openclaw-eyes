"""Tests for the DEFAULT-OFF SQLite canonical-facts source flip in build_maestro_context_packet.

Rules verified:
- Flag OFF (default): _sqlite_canonical_facts is NEVER called; packet is identical to today.
- Flag ON (packet_source="sqlite"): doctrine facts appear; non-maestro facts excluded;
  doctrine present even for an unrelated question; total SQLite facts <= limit.
- Ledger MISSING: flag ON gracefully returns no SQLite facts, no crash.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Shared fixtures (mirrors tests/test_maestro_brain_packet.py)
# ---------------------------------------------------------------------------

def _truth_store(monkeypatch, tmp_path: Path) -> Path:
    store_path = tmp_path / "operator_truth_store.json"
    seed_path = tmp_path / "OPERATOR-TRUTH-20260619-evening.md"
    seed_path.write_text(
        "\n".join([
            "# operator truth seed",
            "Capital Hilton: $2000 received; July 1 check; $400 gigs; next Friday.",
            "St Anne's all paid up.",
            "Live Arts MD owes for Draper follow-up work.",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(store_path))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(seed_path))
    return store_path


def _read_models(tmp_path: Path) -> Path:
    root = tmp_path / "read_models"
    root.mkdir()
    (root / "agent_presence.json").write_text(
        json.dumps({
            "generated_at": "2026-06-21T10:00:00+00:00",
            "agents": [
                {"agent_id": "cassandra", "display_name": "Cassandra", "actual_state": "online"},
                {"agent_id": "chief", "display_name": "Chief", "actual_state": "online"},
            ],
            "next_safe_move": "Review the Maestro packet before any runtime action.",
        }),
        encoding="utf-8",
    )
    (root / "openclaw_capability_index.json").write_text(
        json.dumps({
            "generic_capabilities": [
                {
                    "capability_id": "request_processing",
                    "capability_name": "Bounded request processor",
                    "capability_status": "LIVE_IMPLEMENTED",
                },
                {
                    "capability_id": "invoice_readback",
                    "capability_name": "Invoice status readback",
                    "capability_status": "READ_MODEL_ONLY",
                },
            ]
        }),
        encoding="utf-8",
    )
    (root / "chief_status_rail.json").write_text(
        json.dumps({"chief_current_status": "safe_status_read_model_only"}),
        encoding="utf-8",
    )
    (root / "openclaw_change_sentinel.json").write_text(
        json.dumps({
            "generated_at": "2026-06-21T10:01:00+00:00",
            "hermes_summary": {"what_changed": "No material change.", "what_to_do_next": "Continue."},
        }),
        encoding="utf-8",
    )
    (root / "finance_invoice_reconciliation.json").write_text(
        json.dumps({
            "counts": {"finance_candidate_count": 3, "high_risk_count": 1},
            "first_safe_workflow_proposal": {
                "operator_summary": "Draft invoice context packets are ready; sending remains blocked."
            },
        }),
        encoding="utf-8",
    )
    (root / "cassandra_email_calendar_delta_detangle.json").write_text(
        json.dumps({
            "calendar_operator_context": {
                "google_apple_calendar_merged_context_recorded": True,
                "live_calendar_access_enabled": False,
            },
            "classification_counts": {"DRAFT_PREVIEW_ONLY": 1, "EMAIL_SEND_BLOCKED": 1},
            "upcoming_calendar_events": [
                {
                    "title": "Call with Capital Hilton",
                    "start": "2026-06-21T11:00:00-04:00",
                    "end": "2026-06-21T11:30:00-04:00",
                    "location": "phone",
                },
            ],
        }),
        encoding="utf-8",
    )
    return root


def _seed_ledger(tmp_path: Path) -> Path:
    """Create a temp ledger seeded with doctrine + non-doctrine + non-maestro facts."""
    db_path = tmp_path / "test_ledger.sqlite"
    from canonical_fact_ingest import ingest_graded_fact

    # Fact 1: doctrine, allowed to maestro
    ingest_graded_fact({
        "fact_text": "OpenClaw canonical doctrine: all facts must be provenance-tagged.",
        "source_file": "OPENCLAW_RUNTIME.md",
        "section_heading": "Core Doctrine",
        "source_commit": "abc123",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["maestro", "all"],
        "doc_category": "doctrine",
        "temporal_or_doctrine": "doctrine",
    }, db_path=str(db_path))

    # Fact 2: doctrine, allowed to all
    ingest_graded_fact({
        "fact_text": "Send-hold is absolute: no outbound action without operator approval.",
        "source_file": "OPENCLAW_RUNTIME.md",
        "section_heading": "Send Hold Policy",
        "source_commit": "abc123",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["all"],
        "doc_category": "doctrine",
        "temporal_or_doctrine": "doctrine",
    }, db_path=str(db_path))

    # Fact 3: operational, allowed to maestro only
    ingest_graded_fact({
        "fact_text": "Capital Hilton invoice INV-2026-001 is overdue.",
        "source_file": "invoices/capital_hilton.md",
        "section_heading": "Capital Hilton",
        "source_commit": "abc123",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["maestro"],
        "doc_category": "finance",
        "temporal_or_doctrine": None,
    }, db_path=str(db_path))

    # Fact 4: allowed to chief only — must be EXCLUDED from maestro packet
    ingest_graded_fact({
        "fact_text": "This fact is for chief eyes only and must never appear in maestro packets.",
        "source_file": "internal/chief_only.md",
        "section_heading": "Chief Only",
        "source_commit": "abc123",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["chief"],
        "doc_category": "operations",
        "temporal_or_doctrine": None,
    }, db_path=str(db_path))

    return db_path


# ---------------------------------------------------------------------------
# Test: flag OFF — _sqlite_canonical_facts is never called
# ---------------------------------------------------------------------------

def test_flag_off_does_not_call_sqlite(monkeypatch, tmp_path: Path) -> None:
    """With default env (no OPENCLAW_PACKET_SOURCE), _sqlite_canonical_facts must not be called."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    monkeypatch.delenv("OPENCLAW_PACKET_SOURCE", raising=False)

    import maestro_context_packet as mcp

    call_log: list[Any] = []

    def spy(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        call_log.append((args, kwargs))
        return []

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=spy):
        packet = mcp.build_maestro_context_packet(
            question="What invoices are due?",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
        )

    assert call_log == [], "flag OFF: _sqlite_canonical_facts must not be called"
    # No canonical_facts sourced facts in the packet
    canonical_facts = [
        f for f in packet["facts"] if f.get("provenance") == "canonical_facts"
    ]
    assert canonical_facts == [], "flag OFF: no canonical_facts provenance in packet"
    assert packet["status"] == "READY"


def test_flag_off_via_env_flat(monkeypatch, tmp_path: Path) -> None:
    """Explicit OPENCLAW_PACKET_SOURCE=flat also disables SQLite."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    monkeypatch.setenv("OPENCLAW_PACKET_SOURCE", "flat")

    import maestro_context_packet as mcp

    call_log: list[Any] = []

    def spy(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        call_log.append((args, kwargs))
        return []

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=spy):
        mcp.build_maestro_context_packet(
            question="anything",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
        )

    assert call_log == [], "OPENCLAW_PACKET_SOURCE=flat must not call _sqlite_canonical_facts"


# ---------------------------------------------------------------------------
# Test: flag ON — doctrine included; non-maestro excluded; lean packet
# ---------------------------------------------------------------------------

def test_flag_on_includes_doctrine_excludes_non_maestro(monkeypatch, tmp_path: Path) -> None:
    """With packet_source='sqlite', doctrine facts appear and non-maestro facts are excluded."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    db_path = _seed_ledger(tmp_path)

    monkeypatch.delenv("OPENCLAW_PACKET_SOURCE", raising=False)

    # Patch _sqlite_canonical_facts to use the temp ledger
    import maestro_context_packet as mcp

    # Override ledger path so _sqlite_canonical_facts reads the temp db
    original_fn = mcp._sqlite_canonical_facts

    def patched_sqlite_facts(question: str, agent: str = "maestro", ledger_path: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        return original_fn(question=question, agent=agent, ledger_path=str(db_path), limit=limit)

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=patched_sqlite_facts):
        packet = mcp.build_maestro_context_packet(
            question="Capital Hilton invoice status",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
            packet_source="sqlite",
        )

    canonical_facts = [f for f in packet["facts"] if f.get("provenance") == "canonical_facts"]

    # Both doctrine facts should be present (doctrine always included)
    fact_values = [f["value"] for f in canonical_facts]
    assert any("provenance-tagged" in v for v in fact_values), "doctrine fact 1 must be in packet"
    assert any("Send-hold is absolute" in v for v in fact_values), "doctrine fact 2 must be in packet"

    # Capital Hilton operational fact (maestro-allowed) should appear via FTS match on "Capital"
    assert any("Capital Hilton" in v for v in fact_values), "maestro-allowed operational fact must be in packet"

    # Chief-only fact must be excluded (allowed_actors filter)
    assert not any("chief eyes only" in v for v in fact_values), "non-maestro fact must be excluded"

    # SQLite facts count must be within limit
    assert len(canonical_facts) <= 12, "SQLite facts must be within limit"

    # Provenance must be set correctly
    for f in canonical_facts:
        assert f["provenance"] == "canonical_facts"
        assert f["source_ref"].startswith("canonical_facts:")

    assert packet["status"] == "READY"


def test_doctrine_present_for_unrelated_question(monkeypatch, tmp_path: Path) -> None:
    """Doctrine facts appear even when the question has no matching FTS terms."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    db_path = _seed_ledger(tmp_path)

    monkeypatch.delenv("OPENCLAW_PACKET_SOURCE", raising=False)

    import maestro_context_packet as mcp

    original_fn = mcp._sqlite_canonical_facts

    def patched_sqlite_facts(question: str, agent: str = "maestro", ledger_path: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        return original_fn(question=question, agent=agent, ledger_path=str(db_path), limit=limit)

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=patched_sqlite_facts):
        packet = mcp.build_maestro_context_packet(
            question="xyzzy completely unrelated query with no matching terms",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
            packet_source="sqlite",
        )

    canonical_facts = [f for f in packet["facts"] if f.get("provenance") == "canonical_facts"]
    fact_values = [f["value"] for f in canonical_facts]

    # Doctrine always present regardless of query
    assert any("provenance-tagged" in v for v in fact_values), "doctrine must be present for unrelated question"
    assert any("Send-hold is absolute" in v for v in fact_values), "doctrine must be present for unrelated question"


def test_flag_on_via_env(monkeypatch, tmp_path: Path) -> None:
    """OPENCLAW_PACKET_SOURCE=sqlite env var enables SQLite source."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    db_path = _seed_ledger(tmp_path)

    monkeypatch.setenv("OPENCLAW_PACKET_SOURCE", "sqlite")

    import maestro_context_packet as mcp

    original_fn = mcp._sqlite_canonical_facts

    def patched_sqlite_facts(question: str, agent: str = "maestro", ledger_path: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        return original_fn(question=question, agent=agent, ledger_path=str(db_path), limit=limit)

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=patched_sqlite_facts):
        packet = mcp.build_maestro_context_packet(
            question="doctrine check",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
            # No packet_source param — should pick up from env
        )

    canonical_facts = [f for f in packet["facts"] if f.get("provenance") == "canonical_facts"]
    assert canonical_facts, "env-driven OPENCLAW_PACKET_SOURCE=sqlite must include canonical_facts"


def test_flag_on_hybrid_mode(monkeypatch, tmp_path: Path) -> None:
    """packet_source='hybrid' also enables SQLite."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    db_path = _seed_ledger(tmp_path)

    monkeypatch.delenv("OPENCLAW_PACKET_SOURCE", raising=False)

    import maestro_context_packet as mcp

    original_fn = mcp._sqlite_canonical_facts

    def patched_sqlite_facts(question: str, agent: str = "maestro", ledger_path: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        return original_fn(question=question, agent=agent, ledger_path=str(db_path), limit=limit)

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=patched_sqlite_facts):
        packet = mcp.build_maestro_context_packet(
            question="doctrine check",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
            packet_source="hybrid",
        )

    canonical_facts = [f for f in packet["facts"] if f.get("provenance") == "canonical_facts"]
    assert canonical_facts, "packet_source='hybrid' must include canonical_facts"


def test_param_overrides_env(monkeypatch, tmp_path: Path) -> None:
    """packet_source param takes precedence over OPENCLAW_PACKET_SOURCE env."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    # Even though env says sqlite, param='flat' should override it → no call
    monkeypatch.setenv("OPENCLAW_PACKET_SOURCE", "sqlite")

    import maestro_context_packet as mcp

    call_log: list[Any] = []

    def spy(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        call_log.append((args, kwargs))
        return []

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=spy):
        mcp.build_maestro_context_packet(
            question="anything",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
            packet_source="flat",
        )

    assert call_log == [], "packet_source='flat' must override env and not call _sqlite_canonical_facts"


# ---------------------------------------------------------------------------
# Test: ledger MISSING — graceful, no crash
# ---------------------------------------------------------------------------

def test_missing_ledger_graceful(monkeypatch, tmp_path: Path) -> None:
    """When the ledger file does not exist, flag ON returns no SQLite facts and does not crash."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    nonexistent_db = tmp_path / "does_not_exist.sqlite"

    monkeypatch.delenv("OPENCLAW_PACKET_SOURCE", raising=False)

    import maestro_context_packet as mcp

    original_fn = mcp._sqlite_canonical_facts

    def patched_sqlite_facts(question: str, agent: str = "maestro", ledger_path: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        return original_fn(question=question, agent=agent, ledger_path=str(nonexistent_db), limit=limit)

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=patched_sqlite_facts):
        packet = mcp.build_maestro_context_packet(
            question="something",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
            packet_source="sqlite",
        )

    # Must not crash; must have no canonical_facts facts
    canonical_facts = [f for f in packet["facts"] if f.get("provenance") == "canonical_facts"]
    assert canonical_facts == [], "missing ledger must produce no canonical_facts"
    assert packet["status"] == "READY", "packet must still be READY when ledger missing"


# ---------------------------------------------------------------------------
# Test: direct unit test of _sqlite_canonical_facts
# ---------------------------------------------------------------------------

def test_sqlite_canonical_facts_direct(tmp_path: Path) -> None:
    """Direct test of _sqlite_canonical_facts with a temp ledger."""
    db_path = _seed_ledger(tmp_path)

    from maestro_context_packet import _sqlite_canonical_facts

    # Maestro should see doctrine + maestro-allowed operational facts
    results = _sqlite_canonical_facts(
        question="What are the doctrine rules?",
        agent="maestro",
        ledger_path=str(db_path),
        limit=12,
    )

    provenances = {f["provenance"] for f in results}
    assert provenances == {"canonical_facts"}, "all results must have canonical_facts provenance"

    values = [f["value"] for f in results]
    assert any("provenance-tagged" in v for v in values), "doctrine fact 1 expected"
    assert any("Send-hold is absolute" in v for v in values), "doctrine fact 2 expected"

    # chief-only fact excluded
    assert not any("chief eyes only" in v for v in values), "chief-only fact must be excluded"

    # count within limit
    assert len(results) <= 12


def test_sqlite_canonical_facts_missing_db(tmp_path: Path) -> None:
    """_sqlite_canonical_facts returns [] gracefully for a missing db file."""
    from maestro_context_packet import _sqlite_canonical_facts

    results = _sqlite_canonical_facts(
        question="anything",
        agent="maestro",
        ledger_path=str(tmp_path / "no_such_file.sqlite"),
    )
    assert results == []


def test_sqlite_canonical_facts_empty_db(tmp_path: Path) -> None:
    """_sqlite_canonical_facts returns [] gracefully for an empty SQLite db (no tables)."""
    import sqlite3 as _sqlite3
    empty_db = tmp_path / "empty.sqlite"
    # Create a valid SQLite file with no tables
    conn = _sqlite3.connect(str(empty_db))
    conn.close()

    from maestro_context_packet import _sqlite_canonical_facts

    results = _sqlite_canonical_facts(
        question="anything",
        agent="maestro",
        ledger_path=str(empty_db),
    )
    assert results == []


def test_pii_tier_mapping_fails_closed(tmp_path: Path) -> None:
    """AGY-G flip-1 audit hole #2: the read-path sensitivity->PII-tier mapping must FAIL CLOSED.
    (Note: record_canonical_fact's write-validation also rejects non-allowlisted classes, so this
    is defense-in-depth — and forward-compatible for when graded finance/identity facts are added.)"""
    from maestro_context_packet import _SENSITIVITY_TO_PII_TIER, _PII_TIER_FAIL_CLOSED

    look = lambda s: _SENSITIVITY_TO_PII_TIER.get(s.strip().lower(), _PII_TIER_FAIL_CLOSED)
    assert _PII_TIER_FAIL_CLOSED == "MAX"
    # unknown / unmapped -> MAX (never silently PUBLIC)
    assert look("some_unmapped_class") == "MAX"
    assert look("") == "MAX"
    # explicit sensitive tiers map to themselves (no downgrade)
    assert look("HIGH") == "HIGH"
    assert look("max") == "MAX"
    assert look("med") == "MED"
    assert look("legal_discovery") == "MAX"
    # public doctrine classes still map to PUBLIC (no false upgrade)
    assert look("public_canonical") == "PUBLIC"
    assert look("operational_canonical") == "PUBLIC"


def test_sqlite_facts_precede_read_models_for_cap_survival(monkeypatch, tmp_path: Path) -> None:
    """AGY-G flip-1 audit hole #3: SQLite/canonical facts must be ordered BEFORE the bulky
    read-model facts so doctrine survives format_maestro_context_packet's facts[:30] cap."""
    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    db_path = _seed_ledger(tmp_path)
    monkeypatch.delenv("OPENCLAW_PACKET_SOURCE", raising=False)

    import maestro_context_packet as mcp
    original_fn = mcp._sqlite_canonical_facts

    def patched(question: str, agent: str = "maestro", ledger_path: str | None = None, limit: int = 12):
        return original_fn(question=question, agent=agent, ledger_path=str(db_path), limit=limit)

    with patch.object(mcp, "_sqlite_canonical_facts", side_effect=patched):
        packet = mcp.build_maestro_context_packet(
            question="doctrine Capital Hilton",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
            packet_source="sqlite",
        )

    facts = packet["facts"]
    canonical_idx = [i for i, f in enumerate(facts) if f.get("provenance") == "canonical_facts"]
    readmodel_idx = [i for i, f in enumerate(facts) if "read_models" in str(f.get("source_ref") or "")]
    assert canonical_idx, "expected canonical facts present with flag on"
    if readmodel_idx:
        assert max(canonical_idx) < min(readmodel_idx), \
            "canonical/SQLite facts must precede read-model facts so they survive the packet_text cap"
