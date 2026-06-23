"""Tests for the worker packet dankness scorer.

Covers:
  - score_worker_packet: completeness, missing fields, gap specs, is_dank
  - worker_block_is_thin_packet: genuine-failure vs thin-packet classification
  - emit_worker_packet_enrich_tasks: ON-by-default queuing with grounded-only contract

LOAD-BEARING RULE verified here: scoring rewards structural presence, gaps are
grounded task-specs (field name + why it matters), and queuing is DEFAULT ON
but disableable.  No fabrication path exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the worktree root is on sys.path for importing worker_packet_dankness.
# ControlPlaneLedger is loaded lazily inside worker_packet_dankness; the test
# simply imports the ledger class directly using the same helper the module uses.
import os as _os
_WORKTREE = str(Path(__file__).resolve().parents[1])
_POLISH_LOOP = "/home/openclaw/polish_loop"
for _p in (_WORKTREE, _POLISH_LOOP):
    if _os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import worker_packet_dankness as wpd


def _get_ledger_class():
    """Load ControlPlaneLedger via the same lazy path as the module."""
    return wpd._import_ledger()


def _make_ledger(tmp_path):
    """Create an isolated in-test ledger using a tmp directory."""
    ControlPlaneLedger = _get_ledger_class()
    return ControlPlaneLedger(tmp_path / "cp.sqlite3", status_view_path=tmp_path / "s.json")


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

def _dank_payload() -> dict:
    """A fully-populated heal payload that should score 1.0 / is_dank=True."""
    return {
        "source_surface": "maestro",
        "bad_exchange": {
            "request": "what gigs do I have next week?",
            "answer": "I don't know",
            "claim_type": "gig_schedule",
            "claimed_value": None,
        },
        "expected_behavior": "list confirmed gigs from the read-model",
        "truth_inputs": ["generated/read_models/gig_schedule.json"],
        "bounds": {"OPENCLAW_TEST_MODE": "1", "OPENCLAW_SEND_HOLD": "1"},
        "allowed_tools_class": "read_only_readmodels",
        "pii_rules": "no vault, no Legal, no Finance",
        "repro_prompts": ["what gigs do I have next week?"],
        "acceptance_tests": ["tests/test_pc4_self_healing.py"],
        "rollback_no_send": True,
        "agent_id": "maestro",
    }


def _thin_payload(omit: tuple[str, ...] = ()) -> dict:
    """Return a dank payload with some required fields removed or emptied."""
    p = _dank_payload()
    for field in omit:
        p.pop(field, None)
    return p


# ──────────────────────────────────────────────────────────────────
# score_worker_packet tests
# ──────────────────────────────────────────────────────────────────

def test_dank_payload_scores_full_completeness():
    score = wpd.score_worker_packet(_dank_payload())
    assert score.completeness == 1.0
    assert score.is_dank is True
    assert score.missing == ()
    assert score.gaps == ()


def test_empty_payload_scores_zero_and_flags_all_required_fields():
    score = wpd.score_worker_packet({})
    assert score.completeness == 0.0
    assert score.is_dank is False
    assert set(score.missing) == set(wpd.WORKER_REQUIRED_FIELDS)
    assert len(score.gaps) == len(wpd.WORKER_REQUIRED_FIELDS)


def test_partial_payload_scores_proportionally():
    # Omit 2 of N required fields
    omit = ("repro_prompts", "acceptance_tests")
    score = wpd.score_worker_packet(_thin_payload(omit=omit))
    n = len(wpd.WORKER_REQUIRED_FIELDS)
    expected = round((n - len(omit)) / n, 4)
    assert score.completeness == expected
    assert set(score.missing) == set(omit)
    assert not score.is_dank


def test_missing_field_gap_has_correct_kind_and_field():
    score = wpd.score_worker_packet(_thin_payload(omit=("truth_inputs",)))
    gaps = [g for g in score.gaps if g["field"] == "truth_inputs"]
    assert len(gaps) == 1
    assert gaps[0]["kind"] == "missing_worker_context"
    assert "truth_inputs" in gaps[0]["detail"]
    # The gap must never contain instructions to fabricate content
    assert "fabricate" not in gaps[0]["detail"].lower() or "never fabricate" in gaps[0]["detail"].lower()


def test_empty_string_value_counts_as_missing():
    p = _dank_payload()
    p["source_surface"] = ""
    score = wpd.score_worker_packet(p)
    assert "source_surface" in score.missing


def test_empty_list_value_counts_as_missing():
    p = _dank_payload()
    p["repro_prompts"] = []
    score = wpd.score_worker_packet(p)
    assert "repro_prompts" in score.missing


def test_empty_dict_value_counts_as_missing():
    p = _dank_payload()
    p["bounds"] = {}
    score = wpd.score_worker_packet(p)
    assert "bounds" in score.missing


def test_boolean_true_is_never_empty():
    # rollback_no_send=True is not a required field, but booleans in general
    # must not be treated as empty — test via a payload where bounds is True
    # (unusual but guards the isinstance check).
    p = _dank_payload()
    p["bounds"] = True  # unusual but must not be flagged as empty
    score = wpd.score_worker_packet(p)
    assert "bounds" not in score.missing


def test_none_value_counts_as_missing():
    p = _dank_payload()
    p["expected_behavior"] = None
    score = wpd.score_worker_packet(p)
    assert "expected_behavior" in score.missing


def test_required_fields_constant_is_stable():
    # Ensures the required-field set contains the minimum fields the worker needs.
    required = set(wpd.WORKER_REQUIRED_FIELDS)
    assert "source_surface" in required
    assert "bad_exchange" in required
    assert "expected_behavior" in required
    assert "truth_inputs" in required
    assert "bounds" in required
    assert "repro_prompts" in required
    assert "acceptance_tests" in required


# ──────────────────────────────────────────────────────────────────
# worker_block_is_thin_packet tests
# ──────────────────────────────────────────────────────────────────

def test_genuine_failure_reason_returns_false_for_dank_payload():
    for reason in ("max_attempts_exhausted", "repeated_failure_fingerprint",
                   "budget_cap_exhausted", "green_gate_failed"):
        result = wpd.worker_block_is_thin_packet(reason, _dank_payload())
        # Dank payload + genuine reason -> False (not a thin-packet problem)
        assert result is False, f"expected False for reason={reason!r}"


def test_max_attempts_exhausted_with_thin_payload_is_thin_signal():
    # Even a "genuine" failure reason like max_attempts_exhausted should be
    # flagged as thin-packet when the payload itself is thin.
    result = wpd.worker_block_is_thin_packet(
        "max_attempts_exhausted", _thin_payload(omit=("truth_inputs", "repro_prompts"))
    )
    assert isinstance(result, dict)
    assert result["signal"] == "thin_packet_exhausted_attempts"
    assert "truth_inputs" in result["missing_fields"]
    assert "repro_prompts" in result["missing_fields"]


def test_thin_packet_keyword_in_reason_returns_gap_dict():
    thin_reasons = [
        "missing_context_for_worker",
        "failed_to_start",
        "no_repro_available",
        "runner_failed_to_start",
        "missing_bounds",
    ]
    for reason in thin_reasons:
        result = wpd.worker_block_is_thin_packet(reason, _dank_payload())
        assert isinstance(result, dict), f"expected dict for reason={reason!r}"
        assert result["signal"] == "thin_packet_keyword"
        assert "matched_keyword" in result


def test_unknown_reason_with_thin_payload_is_thin_signal():
    result = wpd.worker_block_is_thin_packet(
        "some_custom_infra_error", _thin_payload(omit=("source_surface",))
    )
    assert isinstance(result, dict)
    assert result["signal"] == "thin_packet_unknown_reason"
    assert "source_surface" in result["missing_fields"]


def test_unknown_reason_with_dank_payload_returns_false():
    result = wpd.worker_block_is_thin_packet("some_custom_infra_error", _dank_payload())
    assert result is False


def test_none_reason_with_thin_payload_is_thin_signal():
    result = wpd.worker_block_is_thin_packet(None, _thin_payload(omit=("bad_exchange",)))
    assert isinstance(result, dict)
    assert "bad_exchange" in result["missing_fields"]


def test_none_reason_with_dank_payload_returns_false():
    result = wpd.worker_block_is_thin_packet(None, _dank_payload())
    assert result is False


def test_gap_dicts_in_result_carry_grounded_only_specs():
    result = wpd.worker_block_is_thin_packet(
        "thin_packet_no_repro", _thin_payload(omit=("repro_prompts",))
    )
    assert isinstance(result, dict)
    for gap in result["gaps"]:
        assert gap["kind"] == "missing_worker_context"
        assert "field" in gap
        # Gap must never instruct fabrication
        detail = gap.get("detail", "")
        assert "never fabricate" in detail.lower() or "fabricate" not in detail.lower()


# ──────────────────────────────────────────────────────────────────
# emit_worker_packet_enrich_tasks tests
# ──────────────────────────────────────────────────────────────────

def test_emit_on_by_default_queues_one_task_per_gap(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCLAW_WORKER_PACKET_DANKIFY_EMIT", raising=False)
    ledger = _make_ledger(tmp_path)
    score = wpd.score_worker_packet(_thin_payload(omit=("truth_inputs", "repro_prompts")))
    assert not score.is_dank
    admitted = wpd.emit_worker_packet_enrich_tasks(
        ledger, score, task_id="heal-abc123", source_surface="maestro"
    )
    assert len(admitted) == len(score.gaps) == 2
    assert ledger.counts()["tasks"] == 2


def test_emit_can_be_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_WORKER_PACKET_DANKIFY_EMIT", "off")
    ledger = _make_ledger(tmp_path)
    score = wpd.score_worker_packet(_thin_payload(omit=("truth_inputs",)))
    admitted = wpd.emit_worker_packet_enrich_tasks(
        ledger, score, task_id="heal-abc123", source_surface="maestro"
    )
    assert admitted == []
    assert ledger.counts()["tasks"] == 0


def test_emit_disabled_explicitly_overrides_env(tmp_path):
    ledger = _make_ledger(tmp_path)
    score = wpd.score_worker_packet(_thin_payload(omit=("truth_inputs",)))
    admitted = wpd.emit_worker_packet_enrich_tasks(
        ledger, score, task_id="heal-abc123", source_surface="maestro", enabled=False
    )
    assert admitted == []


def test_emitted_task_carries_grounded_only_contract(tmp_path):
    ledger = _make_ledger(tmp_path)
    score = wpd.score_worker_packet(_thin_payload(omit=("truth_inputs",)))
    admitted = wpd.emit_worker_packet_enrich_tasks(
        ledger, score, task_id="heal-abc123", source_surface="maestro", enabled=True
    )
    assert len(admitted) == 1
    task = ledger.get_task(admitted[0])
    assert task["type"] == "worker_packet_enrich"
    assert task["source"] == "detector"
    assert task["status"] == "READY"
    assert task["payload"]["grounded_only"] is True
    assert task["payload"]["rollback_no_send"] is True
    assert task["payload"]["original_task_id"] == "heal-abc123"
    assert task["payload"]["source_surface"] == "maestro"


def test_emit_no_gaps_emits_nothing(tmp_path):
    ledger = _make_ledger(tmp_path)
    score = wpd.score_worker_packet(_dank_payload())
    assert score.is_dank
    admitted = wpd.emit_worker_packet_enrich_tasks(
        ledger, score, task_id="heal-abc123", source_surface="maestro", enabled=True
    )
    assert admitted == []
    assert ledger.counts()["tasks"] == 0


def test_emit_env_off_alternatives(tmp_path, monkeypatch):
    """All OPENCLAW_WORKER_PACKET_DANKIFY_EMIT falsy values disable emission."""
    for val in ("0", "false", "no", "off", "OFF", "False"):
        monkeypatch.setenv("OPENCLAW_WORKER_PACKET_DANKIFY_EMIT", val)
        ledger = _make_ledger(tmp_path)
        score = wpd.score_worker_packet(_thin_payload(omit=("truth_inputs",)))
        admitted = wpd.emit_worker_packet_enrich_tasks(
            ledger, score, task_id="heal-x", source_surface="maestro"
        )
        assert admitted == [], f"expected disabled for OPENCLAW_WORKER_PACKET_DANKIFY_EMIT={val!r}"
