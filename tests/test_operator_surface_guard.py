"""Tests for operator_surface_guard — persona-voice / comedy doctrine, first piece.

Coverage:
  1. Machine-contract leak detection (extends master_voice.sh guard)
  2. Zero-Error Gate (comedy hard-locked when error_flags > 0 or process_hung)
  3. Comedy gate per-agent humor ranking (Guardian locked; Niles highest rank)
  4. Golden ratio reproducibility (same payload_hash → same comedy decision)
  5. Combined check_operator_surface entry point
  6. Contract read-model structure

All pure functions; no external I/O; safe in OPENCLAW_TEST_MODE=1.
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_surface_guard as guard


# ---------------------------------------------------------------------------
# 1. Machine-contract leak detection
# ---------------------------------------------------------------------------

class TestLeakDetection:
    """Exact parity with master_voice.sh inline guard + ELIWINSHIP extensions."""

    def test_plain_prose_is_safe(self):
        result = guard.check_machine_contract_leak(
            "Capital Hilton is not ready to move. The invoice basis is in place.",
        )
        assert result.is_leak is False
        assert result.reasons == ()

    def test_json_object_start_is_leaked(self):
        result = guard.check_machine_contract_leak('{"status": "ok", "ref": "abc123"}')
        assert result.is_leak is True
        assert "text_starts_with_json_structure" in result.reasons

    def test_json_array_start_is_leaked(self):
        result = guard.check_machine_contract_leak('[{"key": "val"}]')
        assert result.is_leak is True
        assert "text_starts_with_json_structure" in result.reasons

    def test_two_json_key_patterns_is_leaked(self):
        # Not starting with { but has 2+ "key": patterns — same as master_voice.sh guard
        text = 'Result: "status": "ok", "ref": "abc123"'
        result = guard.check_machine_contract_leak(text)
        assert result.is_leak is True
        assert any("json_key_pattern_count" in r for r in result.reasons)

    def test_one_json_key_pattern_is_safe(self):
        text = 'The "status": field shows blocked.'
        result = guard.check_machine_contract_leak(text)
        # Only 1 hit — below the threshold
        assert result.is_leak is False

    def test_stack_trace_is_leaked(self):
        text = "Traceback (most recent call last):\n  File foo.py, line 10"
        result = guard.check_machine_contract_leak(text)
        assert result.is_leak is True
        assert "stack_trace_present" in result.reasons

    def test_receipt_field_content_hash_is_leaked(self):
        text = "Receipt captured with content_hash=abc123"
        result = guard.check_machine_contract_leak(text)
        assert result.is_leak is True
        assert "receipt_field_pattern_present" in result.reasons

    def test_receipt_field_request_id_is_leaked(self):
        text = "Processed request_id=xyf7821 ok."
        result = guard.check_machine_contract_leak(text)
        assert result.is_leak is True
        assert "receipt_field_pattern_present" in result.reasons

    def test_class_name_is_leaked_in_eliwinship(self):
        text = "OpenClawResponseForMac is ready for dispatch."
        result = guard.check_machine_contract_leak(text, audience="ELIWINSHIP")
        assert result.is_leak is True
        assert "class_name_present_in_eliwinship" in result.reasons

    def test_class_name_is_safe_in_technical_audience(self):
        text = "OpenClawResponseForMac is ready for dispatch."
        result = guard.check_machine_contract_leak(text, audience="TECHNICAL")
        # Class names are OK in TECHNICAL view
        assert result.is_leak is False

    def test_absolute_path_is_leaked_in_eliwinship(self):
        text = "File saved to /home/openclaw/generated/read_models/foo.json"
        result = guard.check_machine_contract_leak(text, audience="ELIWINSHIP")
        assert result.is_leak is True
        assert "absolute_path_present_in_eliwinship" in result.reasons

    def test_absolute_path_safe_in_technical(self):
        text = "File saved to /home/openclaw/generated/read_models/foo.json"
        result = guard.check_machine_contract_leak(text, audience="TECHNICAL")
        assert result.is_leak is False

    def test_hash_string_leaked_in_eliwinship(self):
        # 32-char hex hash (typical sha256 prefix)
        text = "Content verified: a3f5d2e1b4c78901aabb23456789abcd"
        result = guard.check_machine_contract_leak(text, audience="ELIWINSHIP")
        assert result.is_leak is True
        assert "hash_string_present_in_eliwinship" in result.reasons

    def test_short_word_not_flagged_as_hash(self):
        # Short hex-ish but only 8 chars — below 16 threshold
        text = "Code: a3f5d2e1 passed check."
        result = guard.check_machine_contract_leak(text, audience="ELIWINSHIP")
        # 8 chars is below the 16-char hash threshold
        assert result.is_leak is False

    def test_multiple_reasons_accumulated(self):
        text = '{"content_hash": "abc"} Traceback (most recent call last): ...'
        result = guard.check_machine_contract_leak(text)
        assert result.is_leak is True
        assert len(result.reasons) >= 2

    def test_machine_proof_always_false_actions(self):
        result = guard.check_machine_contract_leak("anything")
        assert result.machine_proof["tts_live_connection_performed"] is False
        assert result.machine_proof["message_send_performed"] is False
        assert result.machine_proof["external_action_performed"] is False
        assert result.machine_proof["check_performed"] is True


# ---------------------------------------------------------------------------
# 2. Zero-Error Gate
# ---------------------------------------------------------------------------

class TestZeroErrorGate:
    """error_flags > 0 or process_hung → comedy hard-locked, no exceptions."""

    def test_error_flags_gt_zero_hard_locks_comedy(self):
        result = guard.check_comedy_gate(agent_role="NILES", error_flags=1)
        assert result.comedy_eligible is False
        assert result.comedy_hard_locked is True
        assert "error_flags=1" in result.kill_switch_reason

    def test_error_flags_zero_does_not_hard_lock(self):
        # With error_flags=0 and a payload_hash that passes golden ratio for Niles
        # We need to find a hash that passes — test the gate structure not a specific roll
        result = guard.check_comedy_gate(agent_role="NILES", error_flags=0, payload_hash="NILES")
        assert result.comedy_hard_locked is False  # gate is open; eligibility depends on ratio

    def test_process_hung_hard_locks_comedy(self):
        result = guard.check_comedy_gate(agent_role="NILES", process_hung=True)
        assert result.comedy_eligible is False
        assert result.comedy_hard_locked is True
        assert "process_hung=True" in result.kill_switch_reason

    def test_multiple_error_flags(self):
        result = guard.check_comedy_gate(agent_role="MAESTRO", error_flags=3)
        assert result.comedy_eligible is False
        assert result.comedy_hard_locked is True

    def test_zero_error_gate_machine_proof(self):
        result = guard.check_comedy_gate(agent_role="NILES", error_flags=2)
        assert result.machine_proof["zero_error_gate_enforced"] is True
        assert result.machine_proof["comedy_model_call_performed"] is False
        assert result.machine_proof["comedy_external_action_performed"] is False

    def test_high_risk_context_hard_locks_comedy(self):
        result = guard.check_comedy_gate(agent_role="NILES", high_risk_context=True)
        assert result.comedy_eligible is False
        assert result.comedy_hard_locked is True
        assert "high_risk_context=True" in result.kill_switch_reason


# ---------------------------------------------------------------------------
# 3. Agent humor ranking
# ---------------------------------------------------------------------------

class TestHumorRanking:

    def test_guardian_always_comedy_locked(self):
        result = guard.check_comedy_gate(agent_role="GUARDIAN", error_flags=0)
        assert result.comedy_eligible is False
        assert result.agent_humor_rank == 0
        assert "agent_humor_rank=0" in result.kill_switch_reason

    def test_openclaw_system_always_comedy_locked(self):
        result = guard.check_comedy_gate(agent_role="OPENCLAW_SYSTEM", error_flags=0)
        assert result.comedy_eligible is False
        assert result.agent_humor_rank == 0

    def test_unknown_agent_comedy_locked(self):
        result = guard.check_comedy_gate(agent_role="UNKNOWN", error_flags=0)
        assert result.comedy_eligible is False
        assert result.agent_humor_rank == 0

    def test_funny_ranking_constants_match_doctrine(self):
        # Doctrine order: Guardian(0) < Chief(1) < Cassandra(2) < Hermes(3) < Maestro(4) < Niles(5)
        r = guard.FUNNY_RANKING
        assert r["GUARDIAN"] == 0
        assert r["CHIEF"] == 1
        assert r["CASSANDRA"] == 2
        assert r["HERMES"] == 3
        assert r["MAESTRO"] == 4
        assert r["NILES"] == 5

    def test_niles_has_highest_rank(self):
        assert guard.FUNNY_RANKING["NILES"] == max(guard.FUNNY_RANKING.values())

    def test_chief_rank_above_floor(self):
        # Chief has rank 1 == COMEDY_RANK_FLOOR — eligible if golden ratio passes
        assert guard.FUNNY_RANKING["CHIEF"] >= guard.COMEDY_RANK_FLOOR

    def test_case_insensitive_agent_role(self):
        # "niles" should work as well as "NILES"
        result_upper = guard.check_comedy_gate(agent_role="NILES", payload_hash="same_hash")
        result_lower = guard.check_comedy_gate(agent_role="niles", payload_hash="same_hash")
        assert result_upper.agent_humor_rank == result_lower.agent_humor_rank
        assert result_upper.comedy_eligible == result_lower.comedy_eligible


# ---------------------------------------------------------------------------
# 4. Golden ratio reproducibility
# ---------------------------------------------------------------------------

class TestGoldenRatio:

    def test_same_payload_hash_gives_same_comedy_decision(self):
        kwargs = dict(agent_role="NILES", error_flags=0, payload_hash="stable_hash_abc")
        r1 = guard.check_comedy_gate(**kwargs)
        r2 = guard.check_comedy_gate(**kwargs)
        assert r1.comedy_eligible == r2.comedy_eligible
        assert r1.golden_ratio_passed == r2.golden_ratio_passed

    def test_different_payload_hashes_may_differ(self):
        # Not guaranteed to differ but statistically very likely with many samples.
        results = {
            guard.check_comedy_gate(agent_role="NILES", payload_hash=str(i)).comedy_eligible
            for i in range(50)
        }
        # With Niles rank=5, scaled chance = min(0.12*5, 0.60) = 0.60 — both True and False expected.
        assert True in results
        assert False in results

    def test_comedy_base_chance_in_doctrine_window(self):
        # Doctrine: 10–15% base chance
        assert 0.10 <= guard.COMEDY_BASE_CHANCE <= 0.15

    def test_guardian_golden_ratio_never_fires(self):
        # Even if we cycle many hashes, Guardian must never be eligible
        for i in range(200):
            r = guard.check_comedy_gate(agent_role="GUARDIAN", payload_hash=str(i))
            assert r.comedy_eligible is False, f"Guardian should never be comedy-eligible (seed={i})"


# ---------------------------------------------------------------------------
# 5. Combined operator surface check
# ---------------------------------------------------------------------------

class TestOperatorSurfaceCheck:

    def test_safe_prose_niles_no_errors(self):
        result = guard.check_operator_surface(
            "Easy. We can keep this loose and musical.",
            agent_role="NILES",
            audience="ELIWINSHIP",
            error_flags=0,
        )
        assert result.safe_for_operator is True
        assert result.schema_version == guard.SCHEMA_VERSION
        assert result.contract_status == guard.CONTRACT_STATUS

    def test_leaked_text_is_not_safe(self):
        result = guard.check_operator_surface(
            '{"content_hash": "abc123", "status": "ok"}',
            agent_role="NILES",
            error_flags=0,
        )
        assert result.safe_for_operator is False
        assert result.leak_check.is_leak is True

    def test_errors_lock_comedy_in_combined_check(self):
        result = guard.check_operator_surface(
            "Build passed locally.",
            agent_role="NILES",
            error_flags=2,
        )
        assert result.safe_for_operator is True  # text is safe
        assert result.comedy_gate.comedy_eligible is False  # but comedy locked
        assert result.comedy_gate.comedy_hard_locked is True

    def test_dict_result_is_json_serialisable(self):
        import json
        d = guard.check_operator_surface_dict(
            "Capital Hilton is not ready to move.",
            agent_role="CHIEF",
        )
        # Should not raise
        serialised = json.dumps(d)
        assert "safe_for_operator" in serialised
        assert "comedy_gate" in serialised
        assert "leak_check" in serialised

    def test_safe_for_operator_false_when_leaked(self):
        d = guard.check_operator_surface_dict(
            "Traceback (most recent call last): ...",
            agent_role="CHIEF",
        )
        assert d["safe_for_operator"] is False

    def test_guardian_comedy_always_locked_in_combined(self):
        result = guard.check_operator_surface(
            "Blocked. Proof and approval required before this can proceed.",
            agent_role="GUARDIAN",
            error_flags=0,
        )
        assert result.safe_for_operator is True
        assert result.comedy_gate.comedy_eligible is False


# ---------------------------------------------------------------------------
# 6. Operator decision/status wording
# ---------------------------------------------------------------------------

class TestOperatorDecisionWording:

    def test_machine_status_tokens_are_humanized(self):
        assert guard.operator_surface_value("open_not_paid") == "check expected, not yet paid"
        assert guard.operator_surface_value("needs_reconcile") == "needs your reconcile"
        assert guard.operator_surface_value("needs_operator_review") == "needs operator review"
        assert guard.operator_surface_value("2026-06") == "June"

    def test_money_status_line_is_operator_wording(self):
        assert (
            guard.render_operator_money_status_line(
                entity="Live Arts",
                amount="$1,095",
                status="needs_reconcile",
            )
            == "Live Arts still owes $1,095 — needs your reconcile"
        )

    def test_unknown_amount_money_status_uses_confirmation_template(self):
        assert (
            guard.render_operator_money_status_line(
                entity="Capital Hilton (June)",
                amount=None,
                status="open_amount_unknown",
            )
            == "Capital Hilton (June): check expected, amount not yet confirmed."
        )

    def test_operator_surface_text_humanizes_embedded_status_tokens(self):
        assert (
            guard.operator_surface_text(
                "Live Arts still owes $1,095 - needs_reconcile. Status open_not_paid for 2026-06."
            )
            == (
                "Live Arts still owes $1,095 — needs your reconcile. "
                "Status check expected, not yet paid for June."
            )
        )

    def test_refined_intent_display_never_uses_raw_dictation(self):
        refined = guard.refine_operator_intent_surface(
            raw_text="Niles, do something with that new Logic file.",
            actor="niles",
            intent_category="file_context_request",
            status="needs_operator_review",
            as_of="2026-07-07T00:00:00+00:00",
        )

        assert refined["refined_actor"] == "Niles"
        assert refined["refined_verb"] == "review"
        assert refined["refined_object"] == "new Logic file"
        assert refined["operator_display"] == "Niles request about new Logic file needs operator review."
        assert refined["provenance_raw"] == "Niles, do something with that new Logic file."
        assert refined["provenance_raw"] not in refined["operator_display"]


# ---------------------------------------------------------------------------
# 7. Contract read-model
# ---------------------------------------------------------------------------

class TestContractReadModel:

    def _model(self) -> dict:
        return guard.build_contract_read_model(generated_at="2026-06-22T00:00:00+00:00")

    def test_schema_version_and_status(self):
        m = self._model()
        assert m["schema_version"] == guard.SCHEMA_VERSION
        assert m["contract_status"] == guard.CONTRACT_STATUS

    def test_doctrine_sources_reference_real_files(self):
        m = self._model()
        sources = " ".join(m["doctrine_sources"])
        assert "master_voice.sh" in sources
        assert "agent_voice_response_layer.py" in sources
        assert "SYSTEM-READY-PERSONA-VOICE-COMEDY-PACKET-DOCTRINE.md" in sources

    def test_all_authority_false(self):
        m = self._model()
        for key, val in m["authority_boundary"].items():
            assert val is False, f"authority {key} should be False"

    def test_machine_proof_flags(self):
        m = self._model()
        proof = m["machine_proof"]
        assert proof["all_authority_false"] is True
        assert proof["no_llm_calls"] is True
        assert proof["no_external_io"] is True
        assert proof["deterministic_pure_functions"] is True
        assert proof["extends_master_voice_guard"] is True
        assert proof["zero_error_gate_enforced"] is True
        assert proof["golden_ratio_seeded_by_payload_hash"] is True

    def test_funny_ranking_in_read_model(self):
        m = self._model()
        ranking = m["funny_ranking"]
        assert ranking["GUARDIAN"] == 0
        assert ranking["NILES"] == 5

    def test_leak_detection_rules_present(self):
        m = self._model()
        rules = m["leak_detection_rules"]
        assert "json_structure_start" in rules
        assert "stack_trace" in rules
        assert "class_names_eliwinship" in rules
        assert "absolute_paths_eliwinship" in rules

    def test_comedy_gate_rules_present(self):
        m = self._model()
        rules = m["comedy_gate_rules"]
        assert "zero_error_gate" in rules
        assert "high_risk_suppression" in rules
        assert "golden_ratio" in rules
        assert "rank_floor" in rules
