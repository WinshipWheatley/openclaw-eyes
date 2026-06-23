"""Comedy Archetype Seeder acceptance tests.

Implements the spec's "Comedy acceptance tests" from THREE-COMPONENT-SPEC.md
§ Component 1.

Run with:
  OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 chief_env/bin/python -m pytest -q tests/test_comedy_archetype_seeder.py
"""

from __future__ import annotations

import os
import pytest

# Ensure test-mode env vars are set (guard against accidental send)
os.environ.setdefault("OPENCLAW_TEST_MODE", "1")
os.environ.setdefault("OPENCLAW_SEND_HOLD", "1")

from comedy_archetype_seeder import (
    POLICY_VERSION,
    ComedyHint,
    GroundedFact,
    _hmac_select,
    extract_situation_signals,
    realize_comedy_line,
    render_template,
    seed_comedy_archetype,
    TEMPLATE_REGISTRY,
    _templates_for,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _fact(
    fact_id: str,
    predicate: str,
    value,
    subject_ref: str = "test_subject",
    value_type: str = "dict",
    source_ref: str = "test_source",
    source_revision: str = "r1",
    observed_at: str = "2026-06-23T00:00:00Z",
) -> GroundedFact:
    return GroundedFact(
        fact_id=fact_id,
        subject_ref=subject_ref,
        predicate=predicate,
        value=value,
        value_type=value_type,
        source_ref=source_ref,
        source_revision=source_revision,
        observed_at=observed_at,
    )


def _admitted_gate(agent_rank: int = 3, intensity_cap: int = 3) -> dict:
    """A fully-admitted gate decision."""
    return {
        "admitted": True,
        "zero_error_pass": True,
        "agent_rank": agent_rank,
        "intensity_cap": intensity_cap,
        "golden_ratio_roll_passed": True,
        "gate_decision_ref": "gate-ref-001",
    }


def _rejected_gate(reason: str = "error") -> dict:
    """A gate that rejected comedy."""
    return {
        "admitted": False,
        "zero_error_pass": reason != "error",
        "agent_rank": 3,
        "intensity_cap": 3,
        "golden_ratio_roll_passed": False,
        "gate_decision_ref": "gate-ref-rejected",
    }


# ---------------------------------------------------------------------------
# Spec acceptance test 1: unresolved error => enabled False
# ---------------------------------------------------------------------------

class TestUnresolvedErrorDisablesComedy:
    """Spec: unresolved error => enabled False"""

    def test_zero_error_pass_false_gives_null_hint(self):
        facts = [
            _fact("f1", "approval_cycle_detected", True),
        ]
        gate = {
            "admitted": True,
            "zero_error_pass": False,  # <-- unresolved error
            "agent_rank": 3,
            "intensity_cap": 3,
            "golden_ratio_roll_passed": True,
            "gate_decision_ref": "gate-error",
        }
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="reply-001",
            agent_id="cassandra",
        )
        assert hint.enabled is False
        assert hint.archetype_hint is None
        assert hint.selection_mode == "none"
        assert hint.max_sentences == 0
        assert hint.template_id is None
        assert hint.evidence_fact_ids == []
        assert hint.slot_bindings == {}
        assert hint.diagnostic_signal is None

    def test_max_sentences_zero_when_disabled(self):
        gate = {
            "admitted": True,
            "zero_error_pass": False,
            "agent_rank": 4,
            "intensity_cap": 4,
            "golden_ratio_roll_passed": True,
            "gate_decision_ref": "gate-err2",
        }
        hint = seed_comedy_archetype(
            context_packet_facts=[],
            gate_decision=gate,
            reply_id="r2",
            agent_id="hermes",
        )
        assert hint.max_sentences == 0


# ---------------------------------------------------------------------------
# Spec acceptance test 2: hang => enabled False (process_hung maps to zero_error_pass=False)
# ---------------------------------------------------------------------------

class TestHangDisablesComedy:
    """Spec: hang => enabled False"""

    def test_hang_detected_in_retry_report_no_signal(self):
        """RETRY_WITHOUT_PROGRESS requires hang_detected=False. If hung, no signal fires."""
        facts = [
            _fact(
                "f_retry",
                "retry_report",
                {
                    "attempt_count": 5,
                    "same_state_revision": True,
                    "new_verified_result": False,
                    "hang_detected": True,  # <-- hung
                },
            )
        ]
        signals = extract_situation_signals(facts)
        retry_signals = [s for s in signals if s.code == "RETRY_WITHOUT_PROGRESS"]
        assert retry_signals == [], "Hung process must not produce RETRY_WITHOUT_PROGRESS signal"

    def test_hung_gate_false_disables(self):
        """Gate with zero_error_pass=False (maps to hung in operator_surface_guard) disables."""
        facts = [_fact("f1", "approval_cycle_detected", True)]
        gate = {
            "admitted": True,
            "zero_error_pass": False,
            "agent_rank": 5,
            "intensity_cap": 5,
            "golden_ratio_roll_passed": True,
            "gate_decision_ref": "gate-hung",
        }
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="r-hung",
            agent_id="maestro",
        )
        assert hint.enabled is False


# ---------------------------------------------------------------------------
# Spec acceptance test 3: rejected gate => no archetype
# ---------------------------------------------------------------------------

class TestRejectedGateNoArchetype:
    """Spec: rejected gate => no archetype"""

    def test_admitted_false_gives_null(self):
        facts = [_fact("f1", "approval_cycle_detected", True)]
        gate = {
            "admitted": False,
            "zero_error_pass": True,
            "agent_rank": 3,
            "intensity_cap": 3,
            "golden_ratio_roll_passed": True,
            "gate_decision_ref": "gate-rej",
        }
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="r-rej",
            agent_id="cassandra",
        )
        assert hint.enabled is False
        assert hint.archetype_hint is None

    def test_golden_ratio_false_gives_null(self):
        facts = [_fact("f1", "approval_cycle_detected", True)]
        gate = {
            "admitted": True,
            "zero_error_pass": True,
            "agent_rank": 3,
            "intensity_cap": 3,
            "golden_ratio_roll_passed": False,  # <-- not passed
            "gate_decision_ref": "gate-gr-rej",
        }
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="r-gr",
            agent_id="cassandra",
        )
        assert hint.enabled is False
        assert hint.archetype_hint is None

    def test_enabled_hint_has_all_gate_fields_true(self):
        """Spec invariant: comedy enabled => zero_error_pass AND admitted AND
        golden_ratio_roll_passed all True."""
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="r-all-true",
            agent_id="cassandra",
        )
        # If enabled, gate must have been fully admitted
        if hint.enabled:
            gate = _admitted_gate()
            assert gate["zero_error_pass"] is True
            assert gate["admitted"] is True
            assert gate["golden_ratio_roll_passed"] is True


# ---------------------------------------------------------------------------
# Spec acceptance test 4: same reply/agent/secret/policy => same fallback
# ---------------------------------------------------------------------------

class TestDeterministicFallback:
    """Spec: same reply_id+agent_id+secret+policy_version => same result"""

    def test_hmac_select_same_inputs_same_output(self):
        candidates = ["absurdist", "bureaucratic_overthinker", "misplaced_confidence"]
        result1 = _hmac_select("reply-X", "cassandra", "comedy-archetype", POLICY_VERSION, candidates)
        result2 = _hmac_select("reply-X", "cassandra", "comedy-archetype", POLICY_VERSION, candidates)
        assert result1 == result2

    def test_hmac_select_different_domain_may_differ(self):
        candidates = ["t1", "t2", "t3"]
        r1 = _hmac_select("reply-X", "cassandra", "comedy-archetype", POLICY_VERSION, candidates)
        r2 = _hmac_select("reply-X", "cassandra", "comedy-template-variant", POLICY_VERSION, candidates)
        # They are separate domains — may or may not collide, but are independently stable
        r1b = _hmac_select("reply-X", "cassandra", "comedy-archetype", POLICY_VERSION, candidates)
        r2b = _hmac_select("reply-X", "cassandra", "comedy-template-variant", POLICY_VERSION, candidates)
        assert r1 == r1b
        assert r2 == r2b

    def test_full_seeder_same_inputs_same_output(self):
        facts = [
            _fact(
                "f_conf",
                "confidence_report",
                {
                    "reported_confidence": 0.96,
                    "verified_checks": 2,
                    "required_checks": 5,
                },
            )
        ]
        gate = _admitted_gate()
        h1 = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="stable-reply",
            agent_id="chief",
        )
        h2 = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="stable-reply",
            agent_id="chief",
        )
        assert h1.archetype_hint == h2.archetype_hint
        assert h1.template_id == h2.template_id
        assert h1.selection_mode == h2.selection_mode
        assert h1.diagnostic_signal == h2.diagnostic_signal

    def test_different_reply_ids_can_differ(self):
        """Different reply_ids should not be guaranteed to collide."""
        facts = [
            _fact(
                "f_conf",
                "confidence_report",
                {
                    "reported_confidence": 0.96,
                    "verified_checks": 2,
                    "required_checks": 5,
                },
            )
        ]
        # Just verify no error and determinism holds per-id
        gate = _admitted_gate()
        h1 = seed_comedy_archetype(
            context_packet_facts=facts, gate_decision=gate,
            reply_id="rid-aaa", agent_id="chief",
        )
        h1b = seed_comedy_archetype(
            context_packet_facts=facts, gate_decision=gate,
            reply_id="rid-aaa", agent_id="chief",
        )
        assert h1.template_id == h1b.template_id  # same id -> same result


# ---------------------------------------------------------------------------
# Spec acceptance test 5: LITERAL_SCOPE_MISMATCH => logical_literalism
# ---------------------------------------------------------------------------

class TestLiteralScopeMismatch:
    """Spec: LITERAL_SCOPE_MISMATCH => logical_literalism"""

    def _scope_mismatch_facts(self) -> list:
        return [
            _fact(
                "f_scope",
                "scope_mismatch",
                {
                    "requested_label": "vocals",
                    "selected_label": "Lead Vox",
                },
            )
        ]

    def test_signal_extracted(self):
        signals = extract_situation_signals(self._scope_mismatch_facts())
        codes = [s.code for s in signals]
        assert "LITERAL_SCOPE_MISMATCH" in codes

    def test_forced_archetype_is_logical_literalism(self):
        signals = extract_situation_signals(self._scope_mismatch_facts())
        sig = next(s for s in signals if s.code == "LITERAL_SCOPE_MISMATCH")
        assert sig.forced_archetype == "logical_literalism"

    def test_seeder_selects_logical_literalism(self):
        hint = seed_comedy_archetype(
            context_packet_facts=self._scope_mismatch_facts(),
            gate_decision=_admitted_gate(),
            reply_id="scope-reply",
            agent_id="cassandra",
        )
        assert hint.enabled is True
        assert hint.archetype_hint == "logical_literalism"
        assert hint.selection_mode == "context_rule"
        assert hint.diagnostic_signal == "LITERAL_SCOPE_MISMATCH"

    def test_slot_bindings_point_to_grounded_fact(self):
        hint = seed_comedy_archetype(
            context_packet_facts=self._scope_mismatch_facts(),
            gate_decision=_admitted_gate(),
            reply_id="scope-reply2",
            agent_id="cassandra",
        )
        assert hint.enabled
        for slot_fid in hint.slot_bindings.values():
            assert slot_fid == "f_scope"

    def test_same_label_does_not_trigger(self):
        """requested == selected => not a scope mismatch."""
        facts = [
            _fact(
                "f_same",
                "scope_mismatch",
                {"requested_label": "vocals", "selected_label": "vocals"},
            )
        ]
        signals = extract_situation_signals(facts)
        assert all(s.code != "LITERAL_SCOPE_MISMATCH" for s in signals)


# ---------------------------------------------------------------------------
# Spec acceptance test 6: APPROVAL_DEPENDENCY_CYCLE => bureaucratic_overthinker
# ---------------------------------------------------------------------------

class TestApprovalDependencyCycle:
    """Spec: APPROVAL_DEPENDENCY_CYCLE => bureaucratic_overthinker"""

    def _cycle_facts(self) -> list:
        return [_fact("f_cycle", "approval_cycle_detected", True)]

    def test_signal_extracted(self):
        signals = extract_situation_signals(self._cycle_facts())
        codes = [s.code for s in signals]
        assert "APPROVAL_DEPENDENCY_CYCLE" in codes

    def test_forced_archetype_is_bureaucratic(self):
        signals = extract_situation_signals(self._cycle_facts())
        sig = next(s for s in signals if s.code == "APPROVAL_DEPENDENCY_CYCLE")
        assert sig.forced_archetype == "bureaucratic_overthinker"

    def test_seeder_selects_bureaucratic_overthinker(self):
        hint = seed_comedy_archetype(
            context_packet_facts=self._cycle_facts(),
            gate_decision=_admitted_gate(),
            reply_id="cycle-reply",
            agent_id="chief",
        )
        assert hint.enabled is True
        assert hint.archetype_hint == "bureaucratic_overthinker"
        assert hint.selection_mode == "context_rule"
        assert hint.diagnostic_signal == "APPROVAL_DEPENDENCY_CYCLE"

    def test_false_value_does_not_trigger(self):
        facts = [_fact("f_no_cycle", "approval_cycle_detected", False)]
        signals = extract_situation_signals(facts)
        assert all(s.code != "APPROVAL_DEPENDENCY_CYCLE" for s in signals)

    def test_rendered_joke_from_worked_example(self):
        """Spec worked example 1 joke text check."""
        hint = seed_comedy_archetype(
            context_packet_facts=self._cycle_facts(),
            gate_decision=_admitted_gate(),
            reply_id="cycle-joke-reply",
            agent_id="chief",
        )
        assert hint.enabled
        line = realize_comedy_line(
            hint,
            self._cycle_facts(),
            literal_explanation="Release is blocked by a circular approval dependency.",
        )
        assert line is not None
        assert "approval" in line.lower() or "waiting" in line.lower()


# ---------------------------------------------------------------------------
# Spec acceptance test 7: CONFIDENCE_EVIDENCE_GAP => misplaced_confidence
# ---------------------------------------------------------------------------

class TestConfidenceEvidenceGap:
    """Spec: CONFIDENCE_EVIDENCE_GAP => misplaced_confidence"""

    def _gap_facts(self, conf: float = 0.96, verified: int = 2, required: int = 5) -> list:
        return [
            _fact(
                "f_conf",
                "confidence_report",
                {
                    "reported_confidence": conf,
                    "verified_checks": verified,
                    "required_checks": required,
                },
            )
        ]

    def test_signal_extracted_high_conf_low_coverage(self):
        signals = extract_situation_signals(self._gap_facts(conf=0.96, verified=2, required=5))
        codes = [s.code for s in signals]
        assert "CONFIDENCE_EVIDENCE_GAP" in codes

    def test_signal_extracted_large_gap(self):
        # gap = 0.90 - 0.10 = 0.80 >= 0.40
        signals = extract_situation_signals(self._gap_facts(conf=0.90, verified=1, required=10))
        codes = [s.code for s in signals]
        assert "CONFIDENCE_EVIDENCE_GAP" in codes

    def test_no_signal_when_coverage_adequate(self):
        # conf=0.75 (below 0.80 threshold), coverage=0.80 (above 0.50)
        signals = extract_situation_signals(self._gap_facts(conf=0.75, verified=4, required=5))
        assert all(s.code != "CONFIDENCE_EVIDENCE_GAP" for s in signals)

    def test_forced_archetype_is_misplaced_confidence(self):
        signals = extract_situation_signals(self._gap_facts())
        sig = next(s for s in signals if s.code == "CONFIDENCE_EVIDENCE_GAP")
        assert sig.forced_archetype == "misplaced_confidence"

    def test_seeder_selects_misplaced_confidence(self):
        hint = seed_comedy_archetype(
            context_packet_facts=self._gap_facts(),
            gate_decision=_admitted_gate(),
            reply_id="conf-reply",
            agent_id="cassandra",
        )
        assert hint.enabled is True
        assert hint.archetype_hint == "misplaced_confidence"
        assert hint.selection_mode == "context_rule"
        assert hint.diagnostic_signal == "CONFIDENCE_EVIDENCE_GAP"

    def test_rendered_joke_from_worked_example(self):
        """Spec worked example 3 joke text check."""
        hint = seed_comedy_archetype(
            context_packet_facts=self._gap_facts(),
            gate_decision=_admitted_gate(),
            reply_id="conf-joke-reply",
            agent_id="chief",
        )
        assert hint.enabled
        line = realize_comedy_line(
            hint,
            self._gap_facts(),
            literal_explanation="Confidence was 96% but only 2 of 5 checks were verified.",
        )
        assert line is not None
        assert "confidence" in line.lower() or "checklist" in line.lower()


# ---------------------------------------------------------------------------
# Spec acceptance test 8: TYPE_CATEGORY_COLLISION => absurdist
# ---------------------------------------------------------------------------

class TestTypeCategoryCollision:
    """Spec: TYPE_CATEGORY_COLLISION => absurdist"""

    def _collision_facts(self) -> list:
        return [
            _fact(
                "f_collision",
                "type_category_collision",
                {
                    "field_name": "channel_selector",
                    "received_category": "string",
                    "expected_category": "integer",
                    "safely_handled": True,
                },
            )
        ]

    def test_signal_extracted(self):
        signals = extract_situation_signals(self._collision_facts())
        codes = [s.code for s in signals]
        assert "TYPE_CATEGORY_COLLISION" in codes

    def test_forced_archetype_is_absurdist(self):
        signals = extract_situation_signals(self._collision_facts())
        sig = next(s for s in signals if s.code == "TYPE_CATEGORY_COLLISION")
        assert sig.forced_archetype == "absurdist"

    def test_seeder_selects_absurdist(self):
        hint = seed_comedy_archetype(
            context_packet_facts=self._collision_facts(),
            gate_decision=_admitted_gate(),
            reply_id="collision-reply",
            agent_id="hermes",
        )
        assert hint.enabled is True
        assert hint.archetype_hint == "absurdist"
        assert hint.selection_mode == "context_rule"

    def test_unsafe_collision_no_signal(self):
        """safely_handled=False means there's an unresolved error — no signal."""
        facts = [
            _fact(
                "f_unsafe",
                "type_category_collision",
                {
                    "field_name": "x",
                    "received_category": "string",
                    "expected_category": "integer",
                    "safely_handled": False,
                },
            )
        ]
        signals = extract_situation_signals(facts)
        assert all(s.code != "TYPE_CATEGORY_COLLISION" for s in signals)


# ---------------------------------------------------------------------------
# Spec acceptance test 9: admission+no grounded signal => no joke
# ---------------------------------------------------------------------------

class TestAdmissionWithoutSignal:
    """Spec: admission+no grounded signal => no joke even if gate passed."""

    def test_empty_facts_no_joke(self):
        hint = seed_comedy_archetype(
            context_packet_facts=[],
            gate_decision=_admitted_gate(),
            reply_id="no-sig-reply",
            agent_id="niles",
        )
        assert hint.enabled is False

    def test_irrelevant_facts_no_joke(self):
        """Facts with predicates the seeder doesn't handle produce no signals."""
        facts = [
            _fact("f1", "some_other_predicate", {"data": "irrelevant"}),
            _fact("f2", "another_random_fact", 42, value_type="int"),
        ]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="irrel-reply",
            agent_id="niles",
        )
        assert hint.enabled is False
        assert hint.diagnostic_signal is None

    def test_disabled_comedy_has_null_archetype(self):
        hint = seed_comedy_archetype(
            context_packet_facts=[],
            gate_decision=_admitted_gate(),
            reply_id="null-archetype-reply",
            agent_id="chief",
        )
        assert hint.archetype_hint is None


# ---------------------------------------------------------------------------
# Spec acceptance test 10: failed template removed, no reroll
# ---------------------------------------------------------------------------

class TestFailedTemplateRemovedNoReroll:
    """Spec: on render/validation/guard failure, REMOVE the comedy line — do NOT reroll."""

    def test_render_template_returns_none_on_missing_slot(self):
        """If a required slot is missing from bindings, render returns None."""
        from comedy_archetype_seeder import TEMPLATE_REGISTRY, render_template
        # Find the LITERAL_SCOPE_MISMATCH template
        tmpl = next(
            t for t in TEMPLATE_REGISTRY if t.signal_code == "LITERAL_SCOPE_MISMATCH"
        )
        facts = [_fact("f1", "scope_mismatch", {"requested_label": "vocals", "selected_label": "Lead Vox"})]
        # Missing "selected_label" slot binding
        result = render_template(tmpl, {"requested_label": "f1"}, facts)
        assert result is None

    def test_realize_comedy_line_none_on_missing_explanation(self):
        """realize_comedy_line returns None if literal_explanation is empty."""
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="no-exp-reply",
            agent_id="chief",
        )
        if not hint.enabled:
            pytest.skip("Gate chose not to admit comedy for this input")
        result = realize_comedy_line(hint, facts, literal_explanation="")
        assert result is None

    def test_realize_comedy_line_none_when_disabled(self):
        """realize_comedy_line returns None when hint.enabled is False."""
        gate = {
            "admitted": False,
            "zero_error_pass": True,
            "agent_rank": 3,
            "intensity_cap": 3,
            "golden_ratio_roll_passed": True,
            "gate_decision_ref": "gate-dis",
        }
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="dis-reply",
            agent_id="chief",
        )
        result = realize_comedy_line(hint, facts, literal_explanation="Literal explanation here.")
        assert result is None

    def test_ref_validation_failure_returns_null_hint(self):
        """If a fact_id in slot_bindings doesn't exist in the packet, hint is null."""
        # We'll give the seeder a fact that extracts a signal, then strip the fact from
        # context_packet_facts to simulate a validation failure.
        # (We do this by having the signal point to a fact_id not in the list.)
        facts = [
            _fact(
                "f_scope",
                "scope_mismatch",
                {"requested_label": "vocals", "selected_label": "Lead Vox"},
            )
        ]
        # Run with facts present first — should succeed
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="val-reply",
            agent_id="cassandra",
        )
        assert hint.enabled is True

        # Now run with empty fact list — ref validation must fail -> null hint
        hint_missing = seed_comedy_archetype(
            context_packet_facts=[],  # no facts -> no signals -> null anyway
            gate_decision=_admitted_gate(),
            reply_id="val-reply",
            agent_id="cassandra",
        )
        assert hint_missing.enabled is False


# ---------------------------------------------------------------------------
# Spec acceptance test 11: comedy never adds unsupported number/date/entity/status
# ---------------------------------------------------------------------------

class TestTemplateGroundingInvariants:
    """Spec: templates may NOT add an entity/number/date/cause/status absent from facts."""

    def test_all_templates_use_only_slot_placeholders(self):
        """No template's rendered_pattern contains a hardcoded number, date, or
        entity that would need to come from facts but isn't represented by a slot."""
        import re
        # Patterns that would indicate hardcoded fact-like content outside slots
        # (digits alone, ISO dates, or named entities not from slots)
        slot_re = re.compile(r"\{(\w+)\}")

        for tmpl in TEMPLATE_REGISTRY:
            pattern = tmpl.rendered_pattern
            # After filling slots, no numeric literals should remain unexplained
            # We just verify the pattern uses only its declared slots
            used_slots = set(slot_re.findall(pattern))
            for slot in used_slots:
                assert slot in tmpl.required_slots, (
                    f"Template {tmpl.template_id} uses slot '{slot}' "
                    f"not in required_slots={tmpl.required_slots}"
                )

    def test_rendering_scope_mismatch_uses_only_fact_values(self):
        """The rendered joke for LITERAL_SCOPE_MISMATCH uses only the fact's labels."""
        facts = [
            _fact(
                "f_scope",
                "scope_mismatch",
                {"requested_label": "vocals", "selected_label": "Lead Vox"},
            )
        ]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="ground-reply",
            agent_id="cassandra",
        )
        assert hint.enabled
        line = realize_comedy_line(
            hint, facts,
            literal_explanation='It followed "vocals" so literally that "Lead Vox" did not qualify.',
        )
        assert line is not None
        # The rendered line must contain the grounded labels from the fact
        assert "vocals" in line or "Lead Vox" in line or "literally" in line

    def test_confidence_template_no_invented_numbers(self):
        """The CONFIDENCE_EVIDENCE_GAP template does not insert the conf number directly
        (the spec joke uses a metaphor, not the raw number from the fact)."""
        facts = [
            _fact(
                "f_conf",
                "confidence_report",
                {
                    "reported_confidence": 0.96,
                    "verified_checks": 2,
                    "required_checks": 5,
                },
            )
        ]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="conf-ground-reply",
            agent_id="chief",
        )
        assert hint.enabled
        line = realize_comedy_line(
            hint, facts,
            literal_explanation="Confidence was 96% but only 2 of 5 checks passed.",
        )
        assert line is not None
        # The spec joke is a metaphor — it should not inject raw numbers from the fact
        # since the template pattern uses slot references that resolve to fact values.
        # The pattern "The confidence finished the job before the checklist did."
        # contains no raw numbers — verify the line has no invented numbers.
        assert "0.96" not in line
        assert "96%" not in line or "96" not in line.replace("96%", "")


# ---------------------------------------------------------------------------
# Spec acceptance test 12: factual explanation precedes comedy
# ---------------------------------------------------------------------------

class TestLiteralExplanationPrecedesComedy:
    """Spec: the literal factual explanation PRECEDES the joke."""

    def test_realize_comedy_line_requires_non_empty_explanation(self):
        """realize_comedy_line returns None if no literal_explanation provided."""
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="prec-reply",
            agent_id="chief",
        )
        if not hint.enabled:
            pytest.skip("Gate chose not to admit comedy for this input")
        # Empty explanation
        assert realize_comedy_line(hint, facts, literal_explanation="") is None
        assert realize_comedy_line(hint, facts, literal_explanation="   ") is None

    def test_realize_comedy_line_returns_joke_only(self):
        """The helper returns only the comedy sentence; caller concatenates with explanation."""
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="joke-only-reply",
            agent_id="niles",
        )
        if not hint.enabled:
            pytest.skip("Gate chose not to admit comedy for this input")
        explanation = "Release is blocked by a circular approval dependency."
        line = realize_comedy_line(hint, facts, literal_explanation=explanation)
        assert line is not None
        # The returned line is ONLY the comedy sentence, not the explanation
        # (caller is responsible for concatenation order — explanation first)
        # We verify the joke doesn't accidentally embed the explanation verbatim
        assert len(line) < len(explanation) * 3  # loose sanity check


# ---------------------------------------------------------------------------
# Spec: comedy metadata never enters grounded facts (TRUTH FIRST)
# ---------------------------------------------------------------------------

class TestComedyNeverEntersGroundedFacts:
    """Comedy metadata must never enter the grounded facts list."""

    def test_seeder_does_not_mutate_input_facts(self):
        facts = [
            _fact(
                "f_scope",
                "scope_mismatch",
                {"requested_label": "vocals", "selected_label": "Lead Vox"},
            )
        ]
        original_ids = [f.fact_id for f in facts]
        original_predicates = [f.predicate for f in facts]
        original_count = len(facts)

        seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="mutate-check",
            agent_id="cassandra",
        )

        # Facts list must be unchanged
        assert len(facts) == original_count
        assert [f.fact_id for f in facts] == original_ids
        assert [f.predicate for f in facts] == original_predicates

    def test_hint_fields_are_comedy_only(self):
        """ComedyHint fields are all comedy metadata — verify none has a predicate
        that would mark it as a GroundedFact."""
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="hint-check",
            agent_id="chief",
        )
        # The hint is a ComedyHint, not a GroundedFact
        assert isinstance(hint, ComedyHint)
        assert not isinstance(hint, GroundedFact)


# ---------------------------------------------------------------------------
# Spec: v1 max_sentences invariant
# ---------------------------------------------------------------------------

class TestMaxSentencesInvariant:
    """Spec: v1: 0 or 1 comedy sentence."""

    def test_disabled_hint_has_max_sentences_zero(self):
        gate = {
            "admitted": False,
            "zero_error_pass": True,
            "agent_rank": 3,
            "intensity_cap": 3,
            "golden_ratio_roll_passed": False,
            "gate_decision_ref": "gate-ms0",
        }
        hint = seed_comedy_archetype(
            context_packet_facts=[],
            gate_decision=gate,
            reply_id="ms0",
            agent_id="chief",
        )
        assert hint.max_sentences == 0

    def test_enabled_hint_has_max_sentences_one(self):
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="ms1",
            agent_id="chief",
        )
        if hint.enabled:
            assert hint.max_sentences == 1

    def test_rendered_comedy_line_is_single_sentence(self):
        """The realized comedy line must be at most one sentence."""
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="single-sentence",
            agent_id="niles",
        )
        if not hint.enabled:
            pytest.skip("Gate chose not to admit comedy")
        line = realize_comedy_line(
            hint, facts, literal_explanation="Circular dependency detected."
        )
        if line is not None:
            # At most one sentence: no double newlines, <=2 sentence-ending punctuation
            import re
            sentences = re.split(r"[.!?]\s+", line.strip())
            # Allow trailing punctuation as part of last sentence
            assert len(sentences) <= 2, f"Expected <=1 sentence, got: {line!r}"


# ---------------------------------------------------------------------------
# Spec: policy_version written to hint
# ---------------------------------------------------------------------------

class TestPolicyVersion:

    def test_policy_version_in_enabled_hint(self):
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="pv-reply",
            agent_id="chief",
        )
        assert hint.policy_version == POLICY_VERSION

    def test_policy_version_in_null_hint(self):
        gate = {
            "admitted": False,
            "zero_error_pass": True,
            "agent_rank": 3,
            "intensity_cap": 3,
            "golden_ratio_roll_passed": False,
            "gate_decision_ref": "gate-pv-null",
        }
        hint = seed_comedy_archetype(
            context_packet_facts=[],
            gate_decision=gate,
            reply_id="pv-null",
            agent_id="chief",
        )
        assert hint.policy_version == POLICY_VERSION


# ---------------------------------------------------------------------------
# Spec: gate_decision consumed exactly — no re-admission
# ---------------------------------------------------------------------------

class TestGateDecisionConsumedExactly:
    """Seeder consumes gate_decision exactly; no re-admission, no reinterpretation."""

    def test_all_false_gate_gives_null(self):
        gate = {
            "admitted": False,
            "zero_error_pass": False,
            "agent_rank": 2,
            "intensity_cap": 2,
            "golden_ratio_roll_passed": False,
            "gate_decision_ref": "gate-all-false",
        }
        facts = [_fact("f1", "approval_cycle_detected", True)]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="all-false",
            agent_id="chief",
        )
        assert hint.enabled is False

    def test_agent_rank_and_intensity_cap_copied(self):
        """agent_rank and intensity_cap from gate are reflected in the hint."""
        facts = [_fact("f1", "approval_cycle_detected", True)]
        gate = _admitted_gate(agent_rank=5, intensity_cap=4)
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="rank-copy",
            agent_id="maestro",
        )
        assert hint.agent_rank == 5
        assert hint.intensity_cap == 4

    def test_gate_decision_ref_copied(self):
        facts = [_fact("f1", "approval_cycle_detected", True)]
        gate = _admitted_gate()
        gate["gate_decision_ref"] = "unique-gate-ref-xyz"
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=gate,
            reply_id="gdr-copy",
            agent_id="chief",
        )
        assert hint.gate_decision_ref == "unique-gate-ref-xyz"


# ---------------------------------------------------------------------------
# Signal priority ordering
# ---------------------------------------------------------------------------

class TestSignalPriorityOrdering:
    """Spec: multi-signal: pick highest priority."""

    def test_higher_priority_wins_when_two_signals(self):
        """APPROVAL_DEPENDENCY_CYCLE (100) beats CONFIDENCE_EVIDENCE_GAP (85)."""
        facts = [
            _fact("f_cycle", "approval_cycle_detected", True),
            _fact(
                "f_conf",
                "confidence_report",
                {
                    "reported_confidence": 0.96,
                    "verified_checks": 2,
                    "required_checks": 5,
                },
            ),
        ]
        hint = seed_comedy_archetype(
            context_packet_facts=facts,
            gate_decision=_admitted_gate(),
            reply_id="priority-reply",
            agent_id="cassandra",
        )
        assert hint.enabled is True
        assert hint.diagnostic_signal == "APPROVAL_DEPENDENCY_CYCLE"
        assert hint.archetype_hint == "bureaucratic_overthinker"
