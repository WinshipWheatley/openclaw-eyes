"""
Jargon-Teaching Store Acceptance Tests.
Covers all acceptance criteria from THREE-COMPONENT-SPEC.md §Component 2.

Run with:
    OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 chief_env/bin/python -m pytest -q tests/test_jargon_teaching_store.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from jargon_teaching_store import (
    # Schemas
    VerifiedTermCatalogEntry,
    OperatorTermKnowledge,
    TermRequirement,
    TermTeachingHint,
    # Event types
    TERM_TAUGHT_FULL,
    TERM_TAUGHT_BRIEF,
    TERM_USED_PLAIN,
    TERM_ACKNOWLEDGED,
    TERM_CORRECT_USE_CONFIRMED,
    TERM_DEFINITION_REQUESTED,
    TERM_MISUSE_CONFIRMED,
    TERM_LEARNING_EXPIRED,
    TERM_CONCEPT_VERSION_CHANGED,
    # Status / mode constants
    STATUS_UNKNOWN, STATUS_LEARNING, STATUS_KNOWN,
    MODE_FULL, MODE_BRIEF, MODE_PLAIN, MODE_SUBSTITUTE, MODE_BLOCKED,
    VSTATUS_VERIFIED, VSTATUS_DRAFT, VSTATUS_STALE, VSTATUS_REJECTED,
    # Core API
    append_term_event,
    append_unique_term_event,
    load_verified_term_catalog,
    load_operator_term_knowledge,
    save_operator_term_knowledge,
    project_term_events,
    calc_effective_status,
    plan_term_teaching,
    build_definition_grounded_fact,
    detect_explicit_ack,
    record_teaching_events_after_delivery,
    record_acknowledgement_event,
    record_correct_use_confirmed_event,
    record_concept_version_changed_event,
    record_learning_expired_event,
    is_surface_term_allowed,
    LEARNING_EXPIRY_DAYS,
    REASON_FIRST_TAUGHT,
    REASON_REINFORCEMENT,
    REASON_EXPLICIT_ACK,
    REASON_CORRECT_USE_THRESHOLD,
    REASON_LEARNING_EXPIRED,
    REASON_CONCEPT_VERSION_CHANGED,
    INSERT_AFTER_FIRST_USE,
    INSERT_REPLACE_WITH_PLAIN,
)


# ────────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────────

def make_verified_entry(
    term_id: str = "idempotency",
    canonical_surface: str = "idempotency",
    aliases: list[str] | None = None,
    domain: str = "engineering",
    concept_version: int = 1,
    wording_version: int = 1,
    verification_status: str = VSTATUS_VERIFIED,
    plain_replacement: str | None = "safe-to-repeat operation",
) -> VerifiedTermCatalogEntry:
    return VerifiedTermCatalogEntry(
        term_id=term_id,
        canonical_surface=canonical_surface,
        aliases=aliases or ["idempotent"],
        domain=domain,
        concept_version=concept_version,
        wording_version=wording_version,
        precise_definition=f"An operation is {canonical_surface} if performing it multiple times has the same effect as performing it once.",
        eli5_full=f"'{canonical_surface}' means you can safely repeat an operation and get the same result — like pressing a button that only registers once no matter how many times you press it.",
        eli5_brief=f"(Quick reminder: '{canonical_surface}' = safe to repeat, same result every time.)",
        plain_replacement=plain_replacement,
        definition_dependencies=[],
        usage_validator_id=None,
        source_refs=["https://en.wikipedia.org/wiki/Idempotence"],
        verification_status=verification_status,
        verified_by="operator",
        verified_at="2026-06-01T00:00:00+00:00",
    )


def make_catalog(entries: list[VerifiedTermCatalogEntry] | None = None) -> dict[str, VerifiedTermCatalogEntry]:
    if entries is None:
        entries = [make_verified_entry()]
    return {e.term_id: e for e in entries}


def make_requirement(
    term_id: str = "idempotency",
    necessity: str = "required",
    plain_replacement: str | None = "safe-to-repeat operation",
    definition_requested: bool = False,
) -> TermRequirement:
    return TermRequirement(
        term_id=term_id,
        preferred_surface=term_id,
        necessity=necessity,
        supporting_fact_ids=["fact_001"],
        plain_replacement=plain_replacement,
        definition_requested=definition_requested,
    )


def _past(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _future(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


# ────────────────────────────────────────────────────────────────────────────────
# Section 1: Acceptance test — unknown required => full
# ────────────────────────────────────────────────────────────────────────────────

class TestUnknownRequiredFull:
    """unknown required => FULL (spec acceptance test 1)"""

    def test_unknown_required_produces_full_mode(self):
        catalog = make_catalog()
        req = make_requirement(necessity="required")
        hints = plan_term_teaching(
            operator_id="op1",
            requirements=[req],
            catalog=catalog,
            knowledge_rows={},
        )
        assert len(hints) == 1
        assert hints[0].mode == MODE_FULL
        assert hints[0].term_id == "idempotency"

    def test_unknown_required_has_definition_fact_id(self):
        catalog = make_catalog()
        req = make_requirement(necessity="required")
        hints = plan_term_teaching(
            operator_id="op1",
            requirements=[req],
            catalog=catalog,
            knowledge_rows={},
        )
        assert hints[0].definition_fact_id is not None
        assert "full" in hints[0].definition_fact_id

    def test_unknown_required_insertion_policy_after_first_use(self):
        catalog = make_catalog()
        req = make_requirement(necessity="required")
        hints = plan_term_teaching("op1", [req], catalog, {})
        assert hints[0].insertion_policy == INSERT_AFTER_FIRST_USE

    def test_absent_row_is_unknown(self):
        """Absent row = unknown (spec: "Absent row = unknown")"""
        entry = make_verified_entry()
        status = calc_effective_status(None, entry)
        assert status == STATUS_UNKNOWN


# ────────────────────────────────────────────────────────────────────────────────
# Section 2: Acceptance test — second exposure within interval => brief
# ────────────────────────────────────────────────────────────────────────────────

class TestSecondExposureBrief:
    """second exposure within 90d interval => BRIEF (spec acceptance test 2)"""

    def make_learning_row(self, last_taught_days_ago: int = 5) -> OperatorTermKnowledge:
        return OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,
            status=STATUS_LEARNING,
            status_reason=REASON_FIRST_TAUGHT,
            exposure_count=1,
            full_teach_count=1,
            last_taught_at=_past(last_taught_days_ago),
            last_taught_mode=MODE_FULL,
            learning_expires_at=_future(175),
        )

    def test_required_learning_within_90d_produces_brief(self):
        catalog = make_catalog()
        row = self.make_learning_row(last_taught_days_ago=5)
        req = make_requirement(necessity="required")
        hints = plan_term_teaching("op1", [req], catalog, {"idempotency": row})
        assert hints[0].mode == MODE_BRIEF

    def test_required_learning_over_90d_produces_full_refresher(self):
        """required learning & taught>=90d => FULL refresher"""
        catalog = make_catalog()
        row = self.make_learning_row(last_taught_days_ago=95)
        req = make_requirement(necessity="required")
        hints = plan_term_teaching("op1", [req], catalog, {"idempotency": row})
        assert hints[0].mode == MODE_FULL

    def test_brief_mode_has_definition_fact_id(self):
        catalog = make_catalog()
        row = self.make_learning_row()
        req = make_requirement(necessity="required")
        hints = plan_term_teaching("op1", [req], catalog, {"idempotency": row})
        assert hints[0].definition_fact_id is not None
        assert "brief" in hints[0].definition_fact_id


# ────────────────────────────────────────────────────────────────────────────────
# Section 3: Acceptance test — exposure alone never marks known
# ────────────────────────────────────────────────────────────────────────────────

class TestExposureNeverMarksKnown:
    """exposure alone never marks known (spec acceptance test 3)"""

    def test_many_plain_uses_do_not_create_known(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        # Simulate many USED_PLAIN events
        for i in range(10):
            append_term_event({
                "event_type": TERM_USED_PLAIN,
                "operator_id": operator_id,
                "term_id": term_id,
                "reply_id": f"reply_{i}",
            }, ledger)

        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows.get(term_id)
        # USED_PLAIN should increment exposure_count but NOT change status
        # (no teaching events were issued, so status row may not even exist with known)
        if row is not None:
            assert row.status != STATUS_KNOWN
            assert row.exposure_count == 10

    def test_taught_full_then_many_brief_do_not_mark_known(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        # Teach full once
        append_term_event({
            "event_type": TERM_TAUGHT_FULL,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_0",
        }, ledger)

        # Many brief exposures
        for i in range(1, 20):
            append_term_event({
                "event_type": TERM_TAUGHT_BRIEF,
                "operator_id": operator_id,
                "term_id": term_id,
                "reply_id": f"reply_{i}",
            }, ledger)

        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows.get(term_id)
        assert row is not None
        assert row.status == STATUS_LEARNING  # not known
        assert row.brief_teach_count == 19
        assert row.full_teach_count == 1


# ────────────────────────────────────────────────────────────────────────────────
# Section 4: Acceptance test — named ack marks known
# ────────────────────────────────────────────────────────────────────────────────

class TestNamedAckMarksKnown:
    """named ack marks known; bare 'Got it' does not (spec acceptance test 4)"""

    def test_explicit_ack_event_marks_known(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        # First teach it
        append_term_event({
            "event_type": TERM_TAUGHT_FULL,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_0",
        }, ledger)
        # Then ack
        append_term_event({
            "event_type": TERM_ACKNOWLEDGED,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_1",
        }, ledger)

        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows.get(term_id)
        assert row is not None
        assert row.status == STATUS_KNOWN
        assert row.status_reason == REASON_EXPLICIT_ACK
        assert row.explicit_ack_at is not None
        assert row.known_at is not None
        assert row.learning_expires_at is None

    def test_bare_got_it_not_detected_as_ack(self):
        catalog = make_catalog()
        result = detect_explicit_ack("Got it", catalog)
        assert result == []

    def test_bare_okay_not_detected_as_ack(self):
        catalog = make_catalog()
        result = detect_explicit_ack("Okay, makes sense", catalog)
        assert result == []

    def test_named_ack_stop_explaining_detected(self):
        catalog = make_catalog()
        result = detect_explicit_ack("Stop explaining idempotency please", catalog)
        assert "idempotency" in result

    def test_named_ack_i_know_what_means_detected(self):
        catalog = make_catalog()
        result = detect_explicit_ack("I know what idempotency means", catalog)
        assert "idempotency" in result

    def test_named_ack_via_alias_detected(self):
        catalog = make_catalog()
        result = detect_explicit_ack("Stop explaining idempotent please", catalog)
        assert "idempotency" in result

    def test_named_ack_mark_known_detected(self):
        catalog = make_catalog()
        result = detect_explicit_ack("Mark idempotency known", catalog)
        assert "idempotency" in result

    def test_named_ack_stop_defining_detected(self):
        catalog = make_catalog()
        result = detect_explicit_ack("Stop defining idempotency", catalog)
        assert "idempotency" in result


# ────────────────────────────────────────────────────────────────────────────────
# Section 5: Acceptance test — 2 validated correct uses (>=1 unprompted) marks known
# ────────────────────────────────────────────────────────────────────────────────

class TestCorrectUseMarksKnown:
    """2 validated correct uses (>=1 unprompted) marks known (spec acceptance test 5)"""

    def test_two_correct_uses_with_one_unprompted_marks_known(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        # First use: prompted
        append_term_event({
            "event_type": TERM_CORRECT_USE_CONFIRMED,
            "operator_id": operator_id,
            "term_id": term_id,
            "operator_turn_id": "turn_001",
            "unprompted": False,
        }, ledger)

        rows = project_term_events(operator_id, ledger, knowledge)
        assert rows[term_id].status != STATUS_KNOWN  # 1 use not enough

        # Second use: unprompted
        append_term_event({
            "event_type": TERM_CORRECT_USE_CONFIRMED,
            "operator_id": operator_id,
            "term_id": term_id,
            "operator_turn_id": "turn_002",
            "unprompted": True,
        }, ledger)

        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows[term_id]
        assert row.status == STATUS_KNOWN
        assert row.status_reason == REASON_CORRECT_USE_THRESHOLD
        assert row.correct_use_count == 2
        assert row.unprompted_correct_use_count == 1
        assert row.known_at is not None
        assert row.learning_expires_at is None

    def test_two_prompted_uses_does_not_mark_known(self, tmp_path: Path):
        """2 correct uses but both prompted => still learning"""
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        for turn_id in ["turn_001", "turn_002"]:
            append_term_event({
                "event_type": TERM_CORRECT_USE_CONFIRMED,
                "operator_id": operator_id,
                "term_id": term_id,
                "operator_turn_id": turn_id,
                "unprompted": False,
            }, ledger)

        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows.get(term_id)
        assert row is not None
        assert row.status != STATUS_KNOWN


# ────────────────────────────────────────────────────────────────────────────────
# Section 6: Acceptance test — known doesn't decay with time
# ────────────────────────────────────────────────────────────────────────────────

class TestKnownDoesNotDecay:
    """known doesn't decay with time (spec acceptance test 6)"""

    def test_known_status_persists_far_past_expiry_window(self):
        entry = make_verified_entry()
        row = OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,
            status=STATUS_KNOWN,
            status_reason=REASON_EXPLICIT_ACK,
            known_at=_past(200),
            learning_expires_at=None,  # no expiry for known
        )
        # Far future now (simulate 5 years later)
        far_future = datetime.now(timezone.utc) + timedelta(days=365 * 5)
        effective = calc_effective_status(row, entry, now=far_future)
        assert effective == STATUS_KNOWN

    def test_known_not_downgraded_to_learning_by_time(self):
        entry = make_verified_entry()
        row = OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,
            status=STATUS_KNOWN,
            status_reason=REASON_EXPLICIT_ACK,
            known_at=_past(500),
            # Even if learning_expires_at was set for some reason, known status doesn't use it
            learning_expires_at=_past(300),
        )
        # calc_effective_status should NOT downgrade known via expiry
        effective = calc_effective_status(row, entry)
        assert effective == STATUS_KNOWN


# ────────────────────────────────────────────────────────────────────────────────
# Section 7: Acceptance test — concept-version change returns known->learning
# ────────────────────────────────────────────────────────────────────────────────

class TestConceptVersionChangeResetsToLearning:
    """concept-version change returns known->learning (spec acceptance test 7)"""

    def test_known_row_with_old_concept_version_becomes_learning(self):
        """Effective status: row cv1, catalog cv2 => learning"""
        catalog_v2 = make_verified_entry(concept_version=2)
        row = OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,      # old version
            status=STATUS_KNOWN,
            status_reason=REASON_EXPLICIT_ACK,
            known_at=_past(10),
        )
        effective = calc_effective_status(row, catalog_v2)
        assert effective == STATUS_LEARNING

    def test_concept_version_changed_event_clears_ack_and_correct_use(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        # Teach + ack first
        append_term_event({
            "event_type": TERM_TAUGHT_FULL,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_0",
            "concept_version": 1,
        }, ledger)
        append_term_event({
            "event_type": TERM_ACKNOWLEDGED,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_1",
        }, ledger)

        rows = project_term_events(operator_id, ledger, knowledge)
        assert rows[term_id].status == STATUS_KNOWN

        # Now concept version changed
        append_term_event({
            "event_type": TERM_CONCEPT_VERSION_CHANGED,
            "operator_id": operator_id,
            "term_id": term_id,
            "new_concept_version": 2,
            "reply_id": "system_event",
        }, ledger)

        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows[term_id]
        assert row.status == STATUS_LEARNING
        assert row.status_reason == REASON_CONCEPT_VERSION_CHANGED
        assert row.explicit_ack_at is None
        assert row.known_at is None
        assert row.correct_use_count == 0
        assert row.unprompted_correct_use_count == 0
        assert row.concept_version == 2

    def test_wording_version_change_does_not_alter_status(self):
        """wording-version change doesn't alter status (spec acceptance test 8)"""
        # Wording-only edit: same concept_version, different wording_version
        # The row's concept_version matches => status unchanged
        catalog_wv2 = make_verified_entry(concept_version=1, wording_version=2)
        row = OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,      # matches catalog concept_version
            status=STATUS_KNOWN,
            status_reason=REASON_EXPLICIT_ACK,
            known_at=_past(10),
        )
        effective = calc_effective_status(row, catalog_wv2)
        assert effective == STATUS_KNOWN  # wording change alone does not reset


# ────────────────────────────────────────────────────────────────────────────────
# Section 8: Acceptance test — unverified/stale/missing/rejected term can't pass guard
# ────────────────────────────────────────────────────────────────────────────────

class TestUnverifiedTermBlocked:
    """unverified/stale/missing/rejected term can't pass guard (spec acceptance test 9)"""

    @pytest.mark.parametrize("vstatus", [VSTATUS_DRAFT, VSTATUS_STALE, VSTATUS_REJECTED])
    def test_non_verified_entry_produces_substitute_or_blocked(self, vstatus: str):
        entry = make_verified_entry(verification_status=vstatus)
        catalog = {entry.term_id: entry}
        req = make_requirement(necessity="required", plain_replacement="safe-to-repeat")
        hints = plan_term_teaching("op1", [req], catalog, {})
        # TRUTH FIRST: non-verified must substitute or block, never teach
        assert hints[0].mode in (MODE_SUBSTITUTE, MODE_BLOCKED)
        assert hints[0].mode != MODE_FULL
        assert hints[0].mode != MODE_BRIEF

    def test_missing_catalog_entry_produces_substitute_or_blocked(self):
        # No catalog entry at all
        req = make_requirement(necessity="required", plain_replacement="safe-to-repeat")
        hints = plan_term_teaching("op1", [req], {}, {})
        assert hints[0].mode in (MODE_SUBSTITUTE, MODE_BLOCKED)

    def test_missing_catalog_no_plain_replacement_produces_blocked(self):
        req = make_requirement(necessity="required", plain_replacement=None)
        hints = plan_term_teaching("op1", [req], {}, {})
        assert hints[0].mode == MODE_BLOCKED

    def test_surface_guard_blocked_term_not_allowed(self):
        hint = TermTeachingHint(
            term_id="idempotency",
            surface_form="",
            mode=MODE_BLOCKED,
            supporting_fact_ids=[],
            definition_fact_id=None,
            allowed_surface_forms=[],
            insertion_policy="none",
        )
        assert is_surface_term_allowed("idempotency", hint) is False

    def test_surface_guard_substitute_only_allows_plain_form(self):
        hint = TermTeachingHint(
            term_id="idempotency",
            surface_form="safe-to-repeat operation",
            mode=MODE_SUBSTITUTE,
            supporting_fact_ids=[],
            definition_fact_id=None,
            allowed_surface_forms=["safe-to-repeat operation"],
            insertion_policy=INSERT_REPLACE_WITH_PLAIN,
        )
        assert is_surface_term_allowed("safe-to-repeat operation", hint) is True
        assert is_surface_term_allowed("idempotency", hint) is False


# ────────────────────────────────────────────────────────────────────────────────
# Section 9: Acceptance test — optional unknown replaced with plain
# ────────────────────────────────────────────────────────────────────────────────

class TestOptionalUnknownSubstituted:
    """optional & unknown replaced with plain (spec acceptance test 10)"""

    def test_optional_unknown_with_plain_replacement_produces_substitute(self):
        catalog = make_catalog()
        req = make_requirement(necessity="optional", plain_replacement="safe-to-repeat operation")
        hints = plan_term_teaching("op1", [req], catalog, {})
        assert hints[0].mode == MODE_SUBSTITUTE
        assert hints[0].surface_form == "safe-to-repeat operation"
        assert hints[0].insertion_policy == INSERT_REPLACE_WITH_PLAIN

    def test_optional_unknown_no_plain_replacement_produces_blocked(self):
        entry = make_verified_entry(plain_replacement=None)
        catalog = {entry.term_id: entry}
        req = make_requirement(necessity="optional", plain_replacement=None)
        hints = plan_term_teaching("op1", [req], catalog, {})
        assert hints[0].mode == MODE_BLOCKED


# ────────────────────────────────────────────────────────────────────────────────
# Section 10: Acceptance test — failed/rejected/retried/undelivered reply doesn't update counts
# ────────────────────────────────────────────────────────────────────────────────

class TestUndeliveredReplyDoesNotUpdateCounts:
    """failed/rejected/retried/undelivered reply doesn't update counts (spec acceptance test 11)"""

    def test_no_events_appended_without_delivery(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        # Simulate planning (no delivery occurs)
        catalog = make_catalog()
        req = make_requirement(necessity="required")
        hints = plan_term_teaching(operator_id, [req], catalog, {})
        # We have hints planned, but we do NOT call record_teaching_events_after_delivery
        # (simulating a failed/rejected/undelivered reply)

        rows = project_term_events(operator_id, ledger, knowledge)
        # No events in ledger => no knowledge rows
        assert term_id not in rows

    def test_delivery_creates_event_in_ledger(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        catalog = make_catalog()
        req = make_requirement(necessity="required")
        hints = plan_term_teaching(operator_id, [req], catalog, {})

        # Now simulate confirmed delivery
        record_teaching_events_after_delivery(
            operator_id=operator_id,
            reply_id="reply_001",
            delivered_hints=hints,
            ledger_path=ledger,
            knowledge_path=knowledge,
        )

        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows.get(term_id)
        assert row is not None
        assert row.status == STATUS_LEARNING
        assert row.full_teach_count == 1
        assert row.exposure_count == 1


# ────────────────────────────────────────────────────────────────────────────────
# Section 11: Acceptance test — term x5 in one reply = 1 exposure
# ────────────────────────────────────────────────────────────────────────────────

class TestOneExposurePerTermPerReply:
    """term x5 in one reply = 1 exposure (spec acceptance test 12)"""

    def test_same_term_multiple_hints_deduped_to_one_exposure(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        # Simulate 5 hints for the same term (as if it appeared 5 times in the reply)
        hint = TermTeachingHint(
            term_id=term_id,
            surface_form="idempotency",
            mode=MODE_FULL,
            supporting_fact_ids=[],
            definition_fact_id="def_fact_id",
            allowed_surface_forms=["idempotency"],
            insertion_policy=INSERT_AFTER_FIRST_USE,
        )
        # Even if we pass 5 identical hints, uniqueness check prevents duplicate events
        five_hints = [hint] * 5
        record_teaching_events_after_delivery(
            operator_id=operator_id,
            reply_id="reply_001",
            delivered_hints=five_hints,
            ledger_path=ledger,
            knowledge_path=knowledge,
        )

        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows.get(term_id)
        assert row is not None
        assert row.exposure_count == 1  # Only 1, not 5
        assert row.full_teach_count == 1

    def test_uniqueness_prevents_duplicate_teaching_events(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        operator_id = "op1"
        term_id = "idempotency"

        base_event = {
            "event_type": TERM_TAUGHT_FULL,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_001",
        }
        # First append should succeed
        result1 = append_unique_term_event(base_event, ledger)
        assert result1 is not None

        # Second append with same (reply_id, term_id, event_type) should be suppressed
        result2 = append_unique_term_event(base_event, ledger)
        assert result2 is None


# ────────────────────────────────────────────────────────────────────────────────
# Section 12: Projector idempotency
# ────────────────────────────────────────────────────────────────────────────────

class TestProjectorIdempotency:
    """Projector must be idempotent (skip events <= last_applied_event_seq)"""

    def test_projecting_twice_gives_same_result(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        append_term_event({
            "event_type": TERM_TAUGHT_FULL,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_0",
        }, ledger)

        rows1 = project_term_events(operator_id, ledger, knowledge)
        save_operator_term_knowledge(operator_id, rows1, knowledge)

        # Project again — should not double-apply
        rows2 = project_term_events(operator_id, ledger, knowledge)

        assert rows2[term_id].exposure_count == rows1[term_id].exposure_count
        assert rows2[term_id].full_teach_count == 1  # not 2

    def test_projector_skips_seq_le_last_applied(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        # Append 3 events
        for i in range(3):
            append_term_event({
                "event_type": TERM_TAUGHT_BRIEF,
                "operator_id": operator_id,
                "term_id": term_id,
                "reply_id": f"reply_{i}",
            }, ledger)

        # Project and persist
        rows = project_term_events(operator_id, ledger, knowledge)
        save_operator_term_knowledge(operator_id, rows, knowledge)
        assert rows[term_id].brief_teach_count == 3
        assert rows[term_id].last_applied_event_seq == 3

        # Add 1 more event
        append_term_event({
            "event_type": TERM_TAUGHT_BRIEF,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_3",
        }, ledger)

        # Re-project: only event 4 should be applied
        rows2 = project_term_events(operator_id, ledger, knowledge)
        assert rows2[term_id].brief_teach_count == 4
        assert rows2[term_id].last_applied_event_seq == 4


# ────────────────────────────────────────────────────────────────────────────────
# Section 13: Learning expiry
# ────────────────────────────────────────────────────────────────────────────────

class TestLearningExpiry:
    """Learning expires after 180d with no exposure/correct-use/ack/def-request"""

    def test_expired_learning_returns_unknown_in_effective_status(self):
        entry = make_verified_entry()
        row = OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,
            status=STATUS_LEARNING,
            status_reason=REASON_FIRST_TAUGHT,
            learning_expires_at=_past(1),  # expired yesterday
        )
        effective = calc_effective_status(row, entry)
        assert effective == STATUS_UNKNOWN

    def test_not_yet_expired_learning_returns_learning(self):
        entry = make_verified_entry()
        row = OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,
            status=STATUS_LEARNING,
            status_reason=REASON_FIRST_TAUGHT,
            learning_expires_at=_future(90),  # expires in 90 days
        )
        effective = calc_effective_status(row, entry)
        assert effective == STATUS_LEARNING

    def test_learning_expired_event_resets_status_to_unknown(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        operator_id = "op1"
        term_id = "idempotency"

        append_term_event({
            "event_type": TERM_TAUGHT_FULL,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "reply_0",
        }, ledger)
        rows = project_term_events(operator_id, ledger, knowledge)
        assert rows[term_id].status == STATUS_LEARNING

        append_term_event({
            "event_type": TERM_LEARNING_EXPIRED,
            "operator_id": operator_id,
            "term_id": term_id,
            "reply_id": "expiry_event",
        }, ledger)
        rows = project_term_events(operator_id, ledger, knowledge)
        row = rows[term_id]
        assert row.status == STATUS_UNKNOWN
        assert row.status_reason == REASON_LEARNING_EXPIRED
        assert row.learning_expires_at is None


# ────────────────────────────────────────────────────────────────────────────────
# Section 14: Definition grounding (TRUTH FIRST)
# ────────────────────────────────────────────────────────────────────────────────

class TestDefinitionGrounding:
    """Runtime NEVER authors/paraphrases a definition (TRUTH FIRST)"""

    def test_full_definition_fact_uses_exact_eli5_full_wording(self):
        entry = make_verified_entry()
        fact = build_definition_grounded_fact("idempotency", entry, MODE_FULL)
        assert fact["value"] == entry.eli5_full
        assert fact["predicate"] == "definition"
        assert fact["subject_ref"] == "idempotency"
        assert fact["teaching_metadata"] is True
        assert fact["definition_only"] is True

    def test_brief_definition_fact_uses_exact_eli5_brief_wording(self):
        entry = make_verified_entry()
        fact = build_definition_grounded_fact("idempotency", entry, MODE_BRIEF)
        assert fact["value"] == entry.eli5_brief
        assert "cv" in fact["source_revision"]
        assert "wv" in fact["source_revision"]

    def test_definition_fact_cites_catalog_source_refs(self):
        entry = make_verified_entry()
        fact = build_definition_grounded_fact("idempotency", entry, MODE_FULL)
        assert fact["source_refs"] == entry.source_refs
        assert len(fact["source_refs"]) > 0

    def test_definition_fact_id_stable_for_same_version(self):
        entry = make_verified_entry()
        id1 = build_definition_grounded_fact("idempotency", entry, MODE_FULL)["fact_id"]
        id2 = build_definition_grounded_fact("idempotency", entry, MODE_FULL)["fact_id"]
        assert id1 == id2

    def test_full_and_brief_have_different_fact_ids(self):
        entry = make_verified_entry()
        id_full = build_definition_grounded_fact("idempotency", entry, MODE_FULL)["fact_id"]
        id_brief = build_definition_grounded_fact("idempotency", entry, MODE_BRIEF)["fact_id"]
        assert id_full != id_brief


# ────────────────────────────────────────────────────────────────────────────────
# Section 15: Planner deduplication
# ────────────────────────────────────────────────────────────────────────────────

class TestPlannerDeduplication:
    """Planner dedupes by term_id; required wins over optional; def request propagates"""

    def test_same_term_multiple_requirements_produces_one_hint(self):
        catalog = make_catalog()
        reqs = [
            make_requirement(necessity="optional"),
            make_requirement(necessity="required"),
        ]
        hints = plan_term_teaching("op1", reqs, catalog, {})
        assert len(hints) == 1
        # required wins => full
        assert hints[0].mode == MODE_FULL

    def test_def_request_propagates_through_dedup(self):
        catalog = make_catalog()
        reqs = [
            make_requirement(necessity="optional", definition_requested=False),
            make_requirement(necessity="optional", definition_requested=True),
        ]
        hints = plan_term_teaching("op1", reqs, catalog, {})
        assert len(hints) == 1
        assert hints[0].mode == MODE_FULL  # def requested => full

    def test_definition_requested_full_regardless_of_status(self):
        """operator asks for def => FULL regardless of known status"""
        catalog = make_catalog()
        entry = catalog["idempotency"]
        # Row is KNOWN
        row = OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,
            status=STATUS_KNOWN,
            status_reason=REASON_EXPLICIT_ACK,
            known_at=_past(10),
        )
        req = make_requirement(necessity="required", definition_requested=True)
        hints = plan_term_teaching("op1", [req], catalog, {"idempotency": row})
        assert hints[0].mode == MODE_FULL


# ────────────────────────────────────────────────────────────────────────────────
# Section 16: Catalog I/O round-trip
# ────────────────────────────────────────────────────────────────────────────────

class TestCatalogIO:
    """Catalog JSON I/O loads correctly in both shapes"""

    def test_load_catalog_list_shape(self, tmp_path: Path):
        catalog_path = tmp_path / "catalog.json"
        entry = make_verified_entry()
        catalog_path.write_text(json.dumps({
            "terms": [
                {
                    "term_id": entry.term_id,
                    "canonical_surface": entry.canonical_surface,
                    "aliases": entry.aliases,
                    "domain": entry.domain,
                    "concept_version": entry.concept_version,
                    "wording_version": entry.wording_version,
                    "precise_definition": entry.precise_definition,
                    "eli5_full": entry.eli5_full,
                    "eli5_brief": entry.eli5_brief,
                    "plain_replacement": entry.plain_replacement,
                    "definition_dependencies": entry.definition_dependencies,
                    "usage_validator_id": entry.usage_validator_id,
                    "source_refs": entry.source_refs,
                    "verification_status": entry.verification_status,
                    "verified_by": entry.verified_by,
                    "verified_at": entry.verified_at,
                }
            ]
        }), encoding="utf-8")

        loaded = load_verified_term_catalog(catalog_path)
        assert "idempotency" in loaded
        assert loaded["idempotency"].is_safe_to_teach() is True
        assert loaded["idempotency"].eli5_full == entry.eli5_full

    def test_missing_catalog_returns_empty(self, tmp_path: Path):
        catalog_path = tmp_path / "nonexistent.json"
        loaded = load_verified_term_catalog(catalog_path)
        assert loaded == {}


# ────────────────────────────────────────────────────────────────────────────────
# Section 17: Knowledge I/O round-trip
# ────────────────────────────────────────────────────────────────────────────────

class TestKnowledgeIO:
    """Knowledge JSON I/O round-trip"""

    def test_save_and_load_knowledge_rows(self, tmp_path: Path):
        knowledge_path = tmp_path / "knowledge.json"
        row = OperatorTermKnowledge(
            operator_id="op1",
            term_id="idempotency",
            concept_version=1,
            status=STATUS_LEARNING,
            status_reason=REASON_FIRST_TAUGHT,
            exposure_count=3,
            full_teach_count=1,
            brief_teach_count=2,
        )
        save_operator_term_knowledge("op1", {"idempotency": row}, knowledge_path)
        loaded = load_operator_term_knowledge("op1", knowledge_path)
        assert "idempotency" in loaded
        r = loaded["idempotency"]
        assert r.exposure_count == 3
        assert r.full_teach_count == 1
        assert r.brief_teach_count == 2
        assert r.status == STATUS_LEARNING

    def test_missing_knowledge_returns_empty(self, tmp_path: Path):
        knowledge_path = tmp_path / "nonexistent.json"
        loaded = load_operator_term_knowledge("op1", knowledge_path)
        assert loaded == {}


# ────────────────────────────────────────────────────────────────────────────────
# Section 18: Surface guard integration
# ────────────────────────────────────────────────────────────────────────────────

class TestSurfaceGuardIntegration:
    """Surface guard checks for each mode"""

    def test_known_mode_allows_canonical_and_aliases(self):
        hint = TermTeachingHint(
            term_id="idempotency",
            surface_form="idempotency",
            mode=MODE_PLAIN,
            supporting_fact_ids=[],
            definition_fact_id=None,
            allowed_surface_forms=["idempotency", "idempotent"],
            insertion_policy="none",
        )
        assert is_surface_term_allowed("idempotency", hint) is True
        assert is_surface_term_allowed("idempotent", hint) is True

    def test_full_mode_allows_canonical_and_aliases(self):
        hint = TermTeachingHint(
            term_id="idempotency",
            surface_form="idempotency",
            mode=MODE_FULL,
            supporting_fact_ids=[],
            definition_fact_id="def_id",
            allowed_surface_forms=["idempotency", "idempotent"],
            insertion_policy=INSERT_AFTER_FIRST_USE,
        )
        assert is_surface_term_allowed("idempotency", hint) is True

    def test_blocked_mode_allows_nothing(self):
        hint = TermTeachingHint(
            term_id="idempotency",
            surface_form="",
            mode=MODE_BLOCKED,
            supporting_fact_ids=[],
            definition_fact_id=None,
            allowed_surface_forms=[],
            insertion_policy="none",
        )
        assert is_surface_term_allowed("idempotency", hint) is False
        assert is_surface_term_allowed("idempotent", hint) is False

    def test_substitute_mode_blocks_technical_surface(self):
        hint = TermTeachingHint(
            term_id="idempotency",
            surface_form="safe-to-repeat operation",
            mode=MODE_SUBSTITUTE,
            supporting_fact_ids=[],
            definition_fact_id=None,
            allowed_surface_forms=["safe-to-repeat operation"],
            insertion_policy=INSERT_REPLACE_WITH_PLAIN,
        )
        assert is_surface_term_allowed("safe-to-repeat operation", hint) is True
        assert is_surface_term_allowed("idempotency", hint) is False


# ────────────────────────────────────────────────────────────────────────────────
# Section 19: Correct-use uniqueness (operator_turn_id based)
# ────────────────────────────────────────────────────────────────────────────────

class TestCorrectUseUniqueness:
    """TERM_CORRECT_USE_CONFIRMED uniqueness: (operator_turn_id, term_id, event_type)"""

    def test_duplicate_correct_use_same_turn_suppressed(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"

        event = {
            "event_type": TERM_CORRECT_USE_CONFIRMED,
            "operator_id": "op1",
            "term_id": "idempotency",
            "operator_turn_id": "turn_001",
            "unprompted": True,
        }
        r1 = append_unique_term_event(event, ledger)
        r2 = append_unique_term_event(event, ledger)
        assert r1 is not None
        assert r2 is None  # duplicate suppressed

    def test_different_turn_ids_both_accepted(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"

        r1 = append_unique_term_event({
            "event_type": TERM_CORRECT_USE_CONFIRMED,
            "operator_id": "op1",
            "term_id": "idempotency",
            "operator_turn_id": "turn_001",
            "unprompted": True,
        }, ledger)
        r2 = append_unique_term_event({
            "event_type": TERM_CORRECT_USE_CONFIRMED,
            "operator_id": "op1",
            "term_id": "idempotency",
            "operator_turn_id": "turn_002",
            "unprompted": False,
        }, ledger)
        assert r1 is not None
        assert r2 is not None


# ────────────────────────────────────────────────────────────────────────────────
# Section 20: Multi-operator isolation
# ────────────────────────────────────────────────────────────────────────────────

class TestMultiOperatorIsolation:
    """Knowledge rows are isolated per operator_id"""

    def test_operators_do_not_share_knowledge_rows(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        knowledge = tmp_path / "knowledge.json"
        term_id = "idempotency"

        # op1 gets taught
        append_term_event({
            "event_type": TERM_TAUGHT_FULL,
            "operator_id": "op1",
            "term_id": term_id,
            "reply_id": "reply_0",
        }, ledger)

        rows_op1 = project_term_events("op1", ledger, knowledge)
        rows_op2 = project_term_events("op2", ledger, knowledge)

        assert term_id in rows_op1
        assert term_id not in rows_op2
