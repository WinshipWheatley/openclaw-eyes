"""Tests for comedy_signal_facts.py.

Acceptance criteria:
  a) Emits the right signal-fact for a planted real-shaped condition
     (in a tmp read-model/state fixture).
  b) Emits NOTHING on clean/absent state.
  c) Every emitted fact has a real source_ref + matches the seeder's extractor format.
  d) Never fabricates (assertions about what predicates and value structures look like).

Run:
    OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 \
        chief_env/bin/python -m pytest -q tests/test_comedy_signal_facts.py
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

# Module under test
from comedy_signal_facts import (
    GroundedFact,
    SystemState,
    produce_signal_facts,
)

# ---------------------------------------------------------------------------
# The extractors from the seeder (imported ONLY for format-matching assertions;
# we do NOT import seed_comedy_archetype or any I/O paths from it).
# ---------------------------------------------------------------------------
# We replicate the extractor logic inline here so we can confirm our facts
# would be recognised, without importing the seeder module (as instructed).

SEEDER_PREDICATES = frozenset({
    "approval_cycle_detected",
    "scope_mismatch",
    "confidence_report",
    "task_completion_report",
    "type_category_collision",
    "boundary_check",
    "retry_report",
    "constraint_solver_result",
    "gate_chain_report",
    "magnitude_report",
    "alias_resolution_failure",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_minimal_cp_db(path: str, *, attempts: int, fp: str = "fp-abc", status: str = "RETRY") -> None:
    """Create a minimal control_plane.sqlite3 fixture."""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE tasks (
            id TEXT, type TEXT, status TEXT, source TEXT, owner TEXT,
            lease_nonce TEXT, lease_expiry TEXT, version INTEGER,
            attempts INTEGER, max_attempts INTEGER,
            budget_spent REAL, budget_cap REAL,
            acceptance_ref TEXT, candidate_evidence TEXT, terminal_reason TEXT,
            payload TEXT, proposed_expires_at TEXT, dispatchable INTEGER,
            failure_fingerprint TEXT, created_at TEXT, updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE attempts (
            id INTEGER PRIMARY KEY, task_id TEXT, attempt_no INTEGER,
            owner TEXT, lease_nonce TEXT, started_at TEXT, finished_at TEXT,
            status TEXT, failure_fingerprint TEXT, budget_spent REAL, evidence TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY, task_id TEXT, event_type TEXT,
            from_status TEXT, to_status TEXT, actor TEXT, detail TEXT, created_at TEXT
        )
    """)
    conn.execute(
        "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "task-test-001", "packet_enrich", status, "test", "codex",
            None, None, 1,
            attempts, 5,
            0.0, 1.0,
            None, None, "validation_failed",
            "{}", None, 1,
            fp, "2026-06-23T01:00:00+00:00", "2026-06-23T02:00:00+00:00",
        )
    )
    for i in range(min(attempts, 4)):
        conn.execute(
            "INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                i, "task-test-001", i + 1,
                "codex", None,
                "2026-06-23T01:00:00+00:00", "2026-06-23T01:30:00+00:00",
                "FAILED", fp, 0.25, None,
            )
        )
    conn.commit()
    conn.close()


def _fact_ids(facts: list[GroundedFact]) -> list[str]:
    return [f.fact_id for f in facts]


def _by_predicate(facts: list[GroundedFact], predicate: str) -> list[GroundedFact]:
    return [f for f in facts if f.predicate == predicate]


# ---------------------------------------------------------------------------
# (a) Emits the right signal-fact for planted conditions
# ---------------------------------------------------------------------------

class TestPlantedConditions:
    """Verify that the producer fires for explicitly-planted real-shaped conditions."""

    def test_approval_cycle_from_posture_injected(self):
        """APPROVAL_DEPENDENCY_CYCLE fires when injected cycle is present."""
        state = SystemState(
            injected_read_models={
                "__approval_cycles__": [
                    {
                        "cycle_detected": True,
                        "agent_id": "cassandra",
                        "source_ref": "test:guardian_approval_posture",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        cycles = _by_predicate(facts, "approval_cycle_detected")
        assert len(cycles) == 1
        assert cycles[0].value is True
        assert "cassandra" in cycles[0].subject_ref
        assert cycles[0].source_ref == "test:guardian_approval_posture"

    def test_confidence_evidence_gap_from_injected(self):
        """CONFIDENCE_EVIDENCE_GAP fires for conf=0.9, verified=0, required=5."""
        state = SystemState(
            injected_read_models={
                "__confidence_reports__": [
                    {
                        "reported_confidence": 0.90,
                        "verified_checks": 0,
                        "required_checks": 5,
                        "source_ref": "test:evidence_confidence_scoring",
                        "subject_ref": "fact:capital_hilton_payment_watch_inferred",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        gaps = _by_predicate(facts, "confidence_report")
        assert len(gaps) == 1
        val = gaps[0].value
        assert val["reported_confidence"] == 0.90
        assert val["verified_checks"] == 0
        assert val["required_checks"] == 5

    def test_order_of_magnitude_anomaly_from_injected(self):
        """ORDER_OF_MAGNITUDE_ANOMALY fires for ratio >= 10."""
        state = SystemState(
            injected_read_models={
                "__magnitude_reports__": [
                    {
                        "ratio": 15.0,
                        "compatible_units": True,
                        "actual": 15,
                        "reference": 1,
                        "unit": "restart_count",
                        "source_ref": "test:sentinel",
                        "subject_ref": "service:openclaw-request-response",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        mags = _by_predicate(facts, "magnitude_report")
        assert len(mags) == 1
        assert mags[0].value["ratio"] == 15.0
        assert mags[0].value["compatible_units"] is True

    def test_retry_without_progress_from_sqlite(self):
        """RETRY_WITHOUT_PROGRESS fires for task with >=3 attempts and same fingerprint."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        try:
            _build_minimal_cp_db(db_path, attempts=3, fp="fp-abc123", status="RETRY")
            state = SystemState(control_plane_db=db_path)
            facts = produce_signal_facts(state)
            retries = _by_predicate(facts, "retry_report")
            assert len(retries) >= 1
            val = retries[0].value
            assert val["attempt_count"] >= 3
            assert val["same_state_revision"] is True
            assert val["new_verified_result"] is False
            assert val["hang_detected"] is False
        finally:
            os.unlink(db_path)

    def test_premature_success_from_sqlite(self):
        """PREMATURE_SUCCESS fires when DONE task has a failure terminal_reason."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        try:
            _build_minimal_cp_db(db_path, attempts=1, fp=None, status="DONE")
            state = SystemState(control_plane_db=db_path)
            facts = produce_signal_facts(state)
            premature = _by_predicate(facts, "task_completion_report")
            assert len(premature) >= 1
            val = premature[0].value
            assert val["declared_complete"] is True
            assert val["grounded_verifications_failed"] > 0
        finally:
            os.unlink(db_path)

    def test_redundant_gate_chain_from_injected(self):
        """REDUNDANT_GATE_CHAIN fires when >=3 gates check same condition."""
        state = SystemState(
            injected_read_models={
                "__gate_chains__": [
                    {
                        "sequential_gates_same_condition": 4,
                        "condition_ref": "email_send",
                        "source_ref": "test:gate_decision_ledger",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        chains = _by_predicate(facts, "gate_chain_report")
        assert len(chains) == 1
        assert chains[0].value["sequential_gates_same_condition"] == 4

    def test_scope_mismatch_from_injected(self):
        """LITERAL_SCOPE_MISMATCH fires for mismatched label pair."""
        state = SystemState(
            injected_read_models={
                "__scope_mismatches__": [
                    {
                        "requested_label": "Lead Vox",
                        "selected_label": "vocals",
                        "subject_ref": "intent:gmail_filter",
                        "source_ref": "test:intent_router",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        mismatches = _by_predicate(facts, "scope_mismatch")
        assert len(mismatches) == 1
        val = mismatches[0].value
        assert val["requested_label"] == "Lead Vox"
        assert val["selected_label"] == "vocals"

    def test_wording_intent_mismatch_from_injected(self):
        """WORDING_INTENT_MISMATCH fires when alias map exists and wording failed."""
        state = SystemState(
            injected_read_models={
                "__alias_failures__": [
                    {
                        "alias_map_exists": True,
                        "raw_wording": "morning checkin",
                        "known_alias": "morning_briefing",
                        "source_ref": "test:intent_alias_map",
                        "subject_ref": "intent:morning_routine",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        mismatches = _by_predicate(facts, "alias_resolution_failure")
        assert len(mismatches) == 1
        val = mismatches[0].value
        assert val["alias_map_exists"] is True
        assert val["raw_wording"] == "morning checkin"
        assert val["known_alias"] == "morning_briefing"

    def test_type_category_collision_from_injected(self):
        """TYPE_CATEGORY_COLLISION fires for safely-handled category error."""
        state = SystemState(
            injected_read_models={
                "__type_collisions__": [
                    {
                        "field_name": "invoice_amount",
                        "received_category": "string",
                        "expected_category": "money",
                        "safely_handled": True,
                        "source_ref": "test:invoice_parser",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        collisions = _by_predicate(facts, "type_category_collision")
        assert len(collisions) == 1
        val = collisions[0].value
        assert val["field_name"] == "invoice_amount"
        assert val["received_category"] == "string"
        assert val["expected_category"] == "money"
        assert val["safely_handled"] is True

    def test_boundary_literalism_from_injected(self):
        """BOUNDARY_LITERALISM fires when observed == threshold for strictly_less_than."""
        state = SystemState(
            injected_read_models={
                "__boundary_checks__": [
                    {
                        "operator": "strictly_less_than",
                        "threshold": 100,
                        "observed": 100,
                        "subject_ref": "task:budget_gate",
                        "source_ref": "test:budget_checker",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        boundaries = _by_predicate(facts, "boundary_check")
        assert len(boundaries) == 1
        val = boundaries[0].value
        assert val["operator"] == "strictly_less_than"
        assert val["threshold"] == 100
        assert val["observed"] == 100

    def test_mutually_exclusive_constraints_from_injected(self):
        """MUTUALLY_EXCLUSIVE_CONSTRAINTS fires for unsat core with >=2 operator constraints."""
        state = SystemState(
            injected_read_models={
                "__constraint_results__": [
                    {
                        "satisfiable": False,
                        "unsat_core_operator_count": 3,
                        "subject_ref": "approval:request_002",
                        "source_ref": "test:constraint_solver",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        constraints = _by_predicate(facts, "constraint_solver_result")
        assert len(constraints) == 1
        val = constraints[0].value
        assert val["satisfiable"] is False
        assert val["unsat_core_operator_count"] == 3


# ---------------------------------------------------------------------------
# (b) Emits NOTHING on clean/absent state
# ---------------------------------------------------------------------------

class TestCleanState:
    """Verify that no facts are emitted when conditions are absent."""

    def test_no_facts_on_empty_state(self):
        """Empty SystemState produces no facts."""
        facts = produce_signal_facts(SystemState())
        assert facts == []

    def test_no_facts_on_missing_read_models_dir(self):
        """Non-existent read_models_dir produces no facts."""
        state = SystemState(read_models_dir="/nonexistent/path/to/read_models")
        facts = produce_signal_facts(state)
        assert facts == []

    def test_no_facts_on_missing_control_plane_db(self):
        """Non-existent control_plane_db produces no facts."""
        state = SystemState(control_plane_db="/nonexistent/control_plane.sqlite3")
        facts = produce_signal_facts(state)
        assert facts == []

    def test_no_approval_cycle_when_no_cycle(self):
        """No approval cycle fact when injected cycle_detected=False."""
        state = SystemState(
            injected_read_models={
                "__approval_cycles__": [{"cycle_detected": False, "agent_id": "chief"}]
            }
        )
        facts = produce_signal_facts(state)
        cycles = _by_predicate(facts, "approval_cycle_detected")
        assert len(cycles) == 0

    def test_no_confidence_gap_when_coverage_high(self):
        """No confidence gap when confidence is high AND coverage is high."""
        state = SystemState(
            injected_read_models={
                "__confidence_reports__": [
                    {
                        "reported_confidence": 0.90,
                        "verified_checks": 9,
                        "required_checks": 10,
                        "source_ref": "test:ok",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        gaps = _by_predicate(facts, "confidence_report")
        assert len(gaps) == 0

    def test_no_magnitude_anomaly_when_ratio_below_threshold(self):
        """No ORDER_OF_MAGNITUDE_ANOMALY when ratio is between 0.1 and 10."""
        state = SystemState(
            injected_read_models={
                "__magnitude_reports__": [
                    {
                        "ratio": 5.0,
                        "compatible_units": True,
                        "source_ref": "test:ok",
                        "subject_ref": "service:x",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        mags = _by_predicate(facts, "magnitude_report")
        assert len(mags) == 0

    def test_no_magnitude_anomaly_when_incompatible_units(self):
        """No ORDER_OF_MAGNITUDE_ANOMALY when compatible_units=False."""
        state = SystemState(
            injected_read_models={
                "__magnitude_reports__": [
                    {
                        "ratio": 100.0,
                        "compatible_units": False,
                        "source_ref": "test:ok",
                        "subject_ref": "service:x",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        mags = _by_predicate(facts, "magnitude_report")
        assert len(mags) == 0

    def test_no_retry_when_below_threshold(self):
        """No RETRY_WITHOUT_PROGRESS when task has only 2 attempts."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        try:
            _build_minimal_cp_db(db_path, attempts=2, fp="fp-x", status="RETRY")
            state = SystemState(control_plane_db=db_path)
            facts = produce_signal_facts(state)
            retries = _by_predicate(facts, "retry_report")
            assert len(retries) == 0
        finally:
            os.unlink(db_path)

    def test_no_scope_mismatch_when_labels_identical(self):
        """No LITERAL_SCOPE_MISMATCH when requested_label == selected_label."""
        state = SystemState(
            injected_read_models={
                "__scope_mismatches__": [
                    {
                        "requested_label": "vocals",
                        "selected_label": "vocals",
                        "source_ref": "test:ok",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        mismatches = _by_predicate(facts, "scope_mismatch")
        assert len(mismatches) == 0

    def test_no_gate_chain_when_below_3(self):
        """No REDUNDANT_GATE_CHAIN when only 2 gates check the same condition."""
        state = SystemState(
            injected_read_models={
                "__gate_chains__": [
                    {
                        "sequential_gates_same_condition": 2,
                        "condition_ref": "email_send",
                        "source_ref": "test:ok",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        chains = _by_predicate(facts, "gate_chain_report")
        assert len(chains) == 0

    def test_no_boundary_when_observed_less_than_threshold(self):
        """No BOUNDARY_LITERALISM when observed < threshold (valid case)."""
        state = SystemState(
            injected_read_models={
                "__boundary_checks__": [
                    {
                        "operator": "strictly_less_than",
                        "threshold": 100,
                        "observed": 99,
                        "source_ref": "test:ok",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        boundaries = _by_predicate(facts, "boundary_check")
        assert len(boundaries) == 0

    def test_no_type_collision_when_not_safely_handled(self):
        """No TYPE_CATEGORY_COLLISION when safely_handled=False (unresolved error)."""
        state = SystemState(
            injected_read_models={
                "__type_collisions__": [
                    {
                        "field_name": "invoice_amount",
                        "received_category": "string",
                        "expected_category": "money",
                        "safely_handled": False,
                        "source_ref": "test:ok",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        collisions = _by_predicate(facts, "type_category_collision")
        assert len(collisions) == 0

    def test_no_constraint_when_satisfiable(self):
        """No MUTUALLY_EXCLUSIVE_CONSTRAINTS when satisfiable=True."""
        state = SystemState(
            injected_read_models={
                "__constraint_results__": [
                    {
                        "satisfiable": True,
                        "unsat_core_operator_count": 3,
                        "source_ref": "test:ok",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        constraints = _by_predicate(facts, "constraint_solver_result")
        assert len(constraints) == 0

    def test_no_wording_mismatch_when_no_alias_map(self):
        """No WORDING_INTENT_MISMATCH when alias_map_exists=False."""
        state = SystemState(
            injected_read_models={
                "__alias_failures__": [
                    {
                        "alias_map_exists": False,
                        "raw_wording": "morning checkin",
                        "known_alias": "morning_briefing",
                        "source_ref": "test:ok",
                    }
                ]
            }
        )
        facts = produce_signal_facts(state)
        mismatches = _by_predicate(facts, "alias_resolution_failure")
        assert len(mismatches) == 0


# ---------------------------------------------------------------------------
# (c) Every emitted fact has a real source_ref + matches seeder extractor format
# ---------------------------------------------------------------------------

class TestFactFormat:
    """Verify structural contract: every fact the producer emits is seeder-compatible."""

    def _get_all_kinds_of_facts(self) -> list[GroundedFact]:
        """Produce facts for all injectable signal types in one call."""
        state = SystemState(
            injected_read_models={
                "__approval_cycles__": [
                    {
                        "cycle_detected": True,
                        "agent_id": "chief",
                        "source_ref": "test:posture",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
                "__confidence_reports__": [
                    {
                        "reported_confidence": 0.95,
                        "verified_checks": 1,
                        "required_checks": 10,
                        "source_ref": "test:confidence",
                        "subject_ref": "fact:some_fact",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
                "__magnitude_reports__": [
                    {
                        "ratio": 20.0,
                        "compatible_units": True,
                        "actual": 20,
                        "reference": 1,
                        "unit": "count",
                        "source_ref": "test:magnitude",
                        "subject_ref": "service:foo",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
                "__gate_chains__": [
                    {
                        "sequential_gates_same_condition": 5,
                        "condition_ref": "email_send",
                        "source_ref": "test:gate_ledger",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
                "__scope_mismatches__": [
                    {
                        "requested_label": "A",
                        "selected_label": "B",
                        "subject_ref": "intent:x",
                        "source_ref": "test:intent",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
                "__alias_failures__": [
                    {
                        "alias_map_exists": True,
                        "raw_wording": "foo",
                        "known_alias": "bar",
                        "source_ref": "test:alias",
                        "subject_ref": "intent:y",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
                "__type_collisions__": [
                    {
                        "field_name": "f",
                        "received_category": "string",
                        "expected_category": "money",
                        "safely_handled": True,
                        "source_ref": "test:type",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
                "__boundary_checks__": [
                    {
                        "operator": "strictly_less_than",
                        "threshold": 5,
                        "observed": 5,
                        "source_ref": "test:boundary",
                        "subject_ref": "gate:budget",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
                "__constraint_results__": [
                    {
                        "satisfiable": False,
                        "unsat_core_operator_count": 2,
                        "source_ref": "test:constraint",
                        "subject_ref": "approval:req",
                        "observed_at": "2026-06-23T00:00:00+00:00",
                    }
                ],
            }
        )
        return produce_signal_facts(state)

    def test_every_fact_has_fact_id(self):
        facts = self._get_all_kinds_of_facts()
        assert len(facts) > 0
        for f in facts:
            assert isinstance(f.fact_id, str) and len(f.fact_id) > 0, \
                f"fact_id missing on {f}"

    def test_every_fact_has_non_empty_source_ref(self):
        """Core anti-confabulation check: every fact must trace to a source."""
        facts = self._get_all_kinds_of_facts()
        for f in facts:
            assert isinstance(f.source_ref, str) and len(f.source_ref) > 0, \
                f"source_ref missing or empty on fact {f.fact_id}"
            # source_ref must NOT be a bare 'unknown' or empty placeholder
            assert f.source_ref not in ("", "unknown", None), \
                f"source_ref is placeholder on fact {f.fact_id}"

    def test_every_predicate_is_seeder_recognised(self):
        """Every predicate produced must be one the seeder extractors recognise."""
        facts = self._get_all_kinds_of_facts()
        for f in facts:
            assert f.predicate in SEEDER_PREDICATES, \
                f"Predicate '{f.predicate}' not recognised by seeder (fact_id={f.fact_id})"

    def test_every_fact_has_subject_ref(self):
        facts = self._get_all_kinds_of_facts()
        for f in facts:
            assert isinstance(f.subject_ref, str) and len(f.subject_ref) > 0

    def test_every_fact_has_observed_at(self):
        facts = self._get_all_kinds_of_facts()
        for f in facts:
            assert isinstance(f.observed_at, str) and len(f.observed_at) > 0

    def test_every_fact_has_source_revision(self):
        facts = self._get_all_kinds_of_facts()
        for f in facts:
            assert isinstance(f.source_revision, str) and len(f.source_revision) > 0

    def test_approval_cycle_value_is_truthy_bool(self):
        """Seeder extractor checks: if f.value: → value must be truthy."""
        state = SystemState(
            injected_read_models={
                "__approval_cycles__": [{
                    "cycle_detected": True,
                    "agent_id": "chief",
                    "source_ref": "test:posture",
                }]
            }
        )
        facts = produce_signal_facts(state)
        cycles = _by_predicate(facts, "approval_cycle_detected")
        assert all(f.value for f in cycles)

    def test_confidence_report_value_has_required_keys(self):
        """Seeder extractor: val.get('reported_confidence'), verified_checks, required_checks."""
        state = SystemState(
            injected_read_models={
                "__confidence_reports__": [{
                    "reported_confidence": 0.85,
                    "verified_checks": 0,
                    "required_checks": 5,
                    "source_ref": "test:conf",
                    "subject_ref": "fact:x",
                }]
            }
        )
        facts = produce_signal_facts(state)
        gaps = _by_predicate(facts, "confidence_report")
        for f in gaps:
            val = f.value
            assert "reported_confidence" in val
            assert "verified_checks" in val
            assert "required_checks" in val
            assert isinstance(val["reported_confidence"], (int, float))
            assert isinstance(val["verified_checks"], int)
            assert isinstance(val["required_checks"], int)

    def test_scope_mismatch_value_has_required_keys(self):
        """Seeder extractor: val['requested_label'], val['selected_label']."""
        state = SystemState(
            injected_read_models={
                "__scope_mismatches__": [{
                    "requested_label": "X",
                    "selected_label": "Y",
                    "source_ref": "test:sm",
                    "subject_ref": "intent:z",
                }]
            }
        )
        facts = produce_signal_facts(state)
        mismatches = _by_predicate(facts, "scope_mismatch")
        for f in mismatches:
            val = f.value
            assert "requested_label" in val
            assert "selected_label" in val
            assert isinstance(val["requested_label"], str)
            assert isinstance(val["selected_label"], str)
            assert val["requested_label"] != val["selected_label"]

    def test_magnitude_report_value_has_required_keys(self):
        """Seeder extractor: val['ratio'], val['compatible_units']."""
        state = SystemState(
            injected_read_models={
                "__magnitude_reports__": [{
                    "ratio": 50.0,
                    "compatible_units": True,
                    "source_ref": "test:mag",
                    "subject_ref": "service:s",
                }]
            }
        )
        facts = produce_signal_facts(state)
        mags = _by_predicate(facts, "magnitude_report")
        for f in mags:
            val = f.value
            assert "ratio" in val
            assert "compatible_units" in val
            assert isinstance(val["compatible_units"], bool)
            assert isinstance(val["ratio"], (int, float))

    def test_retry_report_value_has_required_keys(self):
        """Seeder extractor: attempt_count, same_state_revision, new_verified_result, hang_detected."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        try:
            _build_minimal_cp_db(db_path, attempts=3, fp="fpXYZ", status="RETRY")
            state = SystemState(control_plane_db=db_path)
            facts = produce_signal_facts(state)
            retries = _by_predicate(facts, "retry_report")
            for f in retries:
                val = f.value
                assert "attempt_count" in val
                assert "same_state_revision" in val
                assert "new_verified_result" in val
                assert "hang_detected" in val
                assert isinstance(val["same_state_revision"], bool)
                assert isinstance(val["new_verified_result"], bool)
                assert isinstance(val["hang_detected"], bool)
        finally:
            os.unlink(db_path)

    def test_gate_chain_report_value_has_required_keys(self):
        """Seeder extractor: val['sequential_gates_same_condition'] >= 3."""
        state = SystemState(
            injected_read_models={
                "__gate_chains__": [{
                    "sequential_gates_same_condition": 4,
                    "condition_ref": "email_send",
                    "source_ref": "test:gate",
                }]
            }
        )
        facts = produce_signal_facts(state)
        chains = _by_predicate(facts, "gate_chain_report")
        for f in chains:
            val = f.value
            assert "sequential_gates_same_condition" in val
            assert val["sequential_gates_same_condition"] >= 3

    def test_type_category_collision_value_has_required_keys(self):
        """Seeder extractor: field_name, received_category, expected_category, safely_handled."""
        state = SystemState(
            injected_read_models={
                "__type_collisions__": [{
                    "field_name": "amount",
                    "received_category": "str",
                    "expected_category": "int",
                    "safely_handled": True,
                    "source_ref": "test:type",
                }]
            }
        )
        facts = produce_signal_facts(state)
        colls = _by_predicate(facts, "type_category_collision")
        for f in colls:
            val = f.value
            assert "field_name" in val
            assert "received_category" in val
            assert "expected_category" in val
            assert val.get("safely_handled") is True

    def test_boundary_check_value_has_required_keys(self):
        """Seeder extractor: operator='strictly_less_than', threshold, observed; observed==threshold."""
        state = SystemState(
            injected_read_models={
                "__boundary_checks__": [{
                    "operator": "strictly_less_than",
                    "threshold": 10,
                    "observed": 10,
                    "source_ref": "test:bc",
                    "subject_ref": "gate:x",
                }]
            }
        )
        facts = produce_signal_facts(state)
        boundaries = _by_predicate(facts, "boundary_check")
        for f in boundaries:
            val = f.value
            assert val["operator"] == "strictly_less_than"
            assert "threshold" in val
            assert "observed" in val
            assert val["observed"] == val["threshold"]

    def test_alias_resolution_failure_has_required_keys(self):
        """Seeder extractor: alias_map_exists=True, raw_wording, known_alias."""
        state = SystemState(
            injected_read_models={
                "__alias_failures__": [{
                    "alias_map_exists": True,
                    "raw_wording": "raw",
                    "known_alias": "canonical",
                    "source_ref": "test:alias",
                    "subject_ref": "intent:a",
                }]
            }
        )
        facts = produce_signal_facts(state)
        mismatches = _by_predicate(facts, "alias_resolution_failure")
        for f in mismatches:
            val = f.value
            assert val.get("alias_map_exists") is True
            assert "raw_wording" in val
            assert "known_alias" in val


# ---------------------------------------------------------------------------
# (d) Never fabricates
# ---------------------------------------------------------------------------

class TestNoFabrication:
    """Prove the producer cannot invent conditions that are not in the input."""

    def test_empty_injected_lists_produce_nothing(self):
        """All injection slots empty -> zero facts."""
        state = SystemState(
            injected_read_models={
                "__approval_cycles__": [],
                "__confidence_reports__": [],
                "__magnitude_reports__": [],
                "__gate_chains__": [],
                "__scope_mismatches__": [],
                "__alias_failures__": [],
                "__type_collisions__": [],
                "__boundary_checks__": [],
                "__constraint_results__": [],
            }
        )
        facts = produce_signal_facts(state)
        assert facts == []

    def test_boundary_observed_above_threshold_not_emitted(self):
        """observed > threshold should NOT fire (only observed == threshold fires)."""
        state = SystemState(
            injected_read_models={
                "__boundary_checks__": [{
                    "operator": "strictly_less_than",
                    "threshold": 10,
                    "observed": 11,
                    "source_ref": "test:bc",
                    "subject_ref": "gate:x",
                }]
            }
        )
        facts = produce_signal_facts(state)
        assert _by_predicate(facts, "boundary_check") == []

    def test_scope_mismatch_not_emitted_when_labels_empty(self):
        """Empty string labels should NOT produce a scope_mismatch fact."""
        state = SystemState(
            injected_read_models={
                "__scope_mismatches__": [{
                    "requested_label": "",
                    "selected_label": "vocals",
                    "source_ref": "test:sm",
                    "subject_ref": "intent:z",
                }]
            }
        )
        facts = produce_signal_facts(state)
        assert _by_predicate(facts, "scope_mismatch") == []

    def test_confidence_gap_not_emitted_when_required_zero(self):
        """required_checks=0 should NOT produce a confidence_report (division guard)."""
        state = SystemState(
            injected_read_models={
                "__confidence_reports__": [{
                    "reported_confidence": 0.99,
                    "verified_checks": 0,
                    "required_checks": 0,
                    "source_ref": "test:conf",
                    "subject_ref": "fact:x",
                }]
            }
        )
        facts = produce_signal_facts(state)
        assert _by_predicate(facts, "confidence_report") == []

    def test_magnitude_ratio_below_10_not_emitted(self):
        """ratio=9 (just below threshold) should NOT fire."""
        state = SystemState(
            injected_read_models={
                "__magnitude_reports__": [{
                    "ratio": 9.9,
                    "compatible_units": True,
                    "source_ref": "test:mag",
                    "subject_ref": "svc:x",
                }]
            }
        )
        facts = produce_signal_facts(state)
        assert _by_predicate(facts, "magnitude_report") == []

    def test_type_collision_missing_fields_not_emitted(self):
        """Incomplete type_collision (missing expected_category) is NOT emitted."""
        state = SystemState(
            injected_read_models={
                "__type_collisions__": [{
                    "field_name": "amount",
                    "received_category": "string",
                    # missing expected_category
                    "safely_handled": True,
                    "source_ref": "test:type",
                }]
            }
        )
        facts = produce_signal_facts(state)
        assert _by_predicate(facts, "type_category_collision") == []

    def test_constraint_with_only_one_operator_not_emitted(self):
        """unsat_core_operator_count=1 should NOT fire (requires >=2)."""
        state = SystemState(
            injected_read_models={
                "__constraint_results__": [{
                    "satisfiable": False,
                    "unsat_core_operator_count": 1,
                    "source_ref": "test:c",
                    "subject_ref": "gate:x",
                }]
            }
        )
        facts = produce_signal_facts(state)
        assert _by_predicate(facts, "constraint_solver_result") == []

    def test_alias_failure_without_alias_map_not_emitted(self):
        """alias_map_exists=False must prevent emission."""
        state = SystemState(
            injected_read_models={
                "__alias_failures__": [{
                    "alias_map_exists": False,
                    "raw_wording": "something",
                    "known_alias": "canonical",
                    "source_ref": "test:alias",
                    "subject_ref": "intent:a",
                }]
            }
        )
        facts = produce_signal_facts(state)
        assert _by_predicate(facts, "alias_resolution_failure") == []

    def test_done_task_without_failure_keyword_not_emitted(self):
        """PREMATURE_SUCCESS: DONE task with benign terminal_reason should NOT fire."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE tasks (
                    id TEXT, type TEXT, status TEXT, source TEXT, owner TEXT,
                    lease_nonce TEXT, lease_expiry TEXT, version INTEGER,
                    attempts INTEGER, max_attempts INTEGER,
                    budget_spent REAL, budget_cap REAL,
                    acceptance_ref TEXT, candidate_evidence TEXT, terminal_reason TEXT,
                    payload TEXT, proposed_expires_at TEXT, dispatchable INTEGER,
                    failure_fingerprint TEXT, created_at TEXT, updated_at TEXT
                )
            """)
            conn.execute(
                "CREATE TABLE attempts (id INTEGER PRIMARY KEY, task_id TEXT, attempt_no INTEGER, owner TEXT, lease_nonce TEXT, started_at TEXT, finished_at TEXT, status TEXT, failure_fingerprint TEXT, budget_spent REAL, evidence TEXT)"
            )
            conn.execute(
                "CREATE TABLE events (id INTEGER PRIMARY KEY, task_id TEXT, event_type TEXT, from_status TEXT, to_status TEXT, actor TEXT, detail TEXT, created_at TEXT)"
            )
            conn.execute(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("task-ok", "packet_enrich", "DONE", "test", "codex",
                 None, None, 1, 0, 2, 0.0, 1.0, None, None, "completed normally",
                 "{}", None, 1, None,
                 "2026-06-23T01:00:00+00:00", "2026-06-23T02:00:00+00:00")
            )
            conn.commit()
            conn.close()

            state = SystemState(control_plane_db=db_path)
            facts = produce_signal_facts(state)
            premature = _by_predicate(facts, "task_completion_report")
            assert len(premature) == 0
        finally:
            os.unlink(db_path)

    def test_no_duplicate_fact_ids(self):
        """Fact IDs must be unique across all emitted facts."""
        state = SystemState(
            injected_read_models={
                "__approval_cycles__": [
                    {"cycle_detected": True, "agent_id": "chief", "source_ref": "test:a"},
                    {"cycle_detected": True, "agent_id": "cassandra", "source_ref": "test:b"},
                ],
                "__confidence_reports__": [
                    {"reported_confidence": 0.9, "verified_checks": 0, "required_checks": 5,
                     "source_ref": "test:c1", "subject_ref": "f1"},
                    {"reported_confidence": 0.85, "verified_checks": 0, "required_checks": 5,
                     "source_ref": "test:c2", "subject_ref": "f2"},
                ],
            }
        )
        facts = produce_signal_facts(state)
        ids = [f.fact_id for f in facts]
        assert len(ids) == len(set(ids)), f"Duplicate fact IDs: {ids}"
