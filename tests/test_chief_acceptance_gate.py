"""Tests for chief_acceptance_gate — verifies the 3 verdict paths and fail-safe behavior."""

from __future__ import annotations

import chief_acceptance_gate as gate


def _sample_evidence(**overrides) -> dict:
    base = {
        "task_name": "test-task-001",
        "pass_num": 1,
        "pc_output_summary": "PASS:1\nCHANGES: edited foo.py\nREASONING: fixed bug\nROLLBACK PLAN: revert\nCOST: $0\nTRUTH: verified\nHEADROOM: fine",
        "mac_review_verdict": "APPROVED",
        "harness_manifest": {
            "flow": "guardian_schema_retest",
            "passed": 13,
            "failed": 0,
            "total_cases": 13,
        },
    }
    base.update(overrides)
    return base


# --- _extract_verdict unit tests (no LLM) ---

def test_extract_verdict_approve():
    assert gate._extract_verdict("APPROVE") == "APPROVE"


def test_extract_verdict_rework():
    assert gate._extract_verdict("REWORK") == "REWORK"


def test_extract_verdict_insufficient():
    assert gate._extract_verdict("INSUFFICIENT_EVIDENCE") == "INSUFFICIENT_EVIDENCE"


def test_extract_verdict_with_trailing_text():
    assert gate._extract_verdict("APPROVE\nSome explanation that should be ignored") == "APPROVE"


def test_extract_verdict_with_markdown_formatting():
    assert gate._extract_verdict("**REWORK**") == "REWORK"
    assert gate._extract_verdict("  `APPROVE`  ") == "APPROVE"
    assert gate._extract_verdict("# REWORK") == "REWORK"


def test_extract_verdict_empty_falls_safe():
    assert gate._extract_verdict("") == "INSUFFICIENT_EVIDENCE"


def test_extract_verdict_garbage_falls_safe():
    assert gate._extract_verdict("I think the task looks good") == "INSUFFICIENT_EVIDENCE"


def test_extract_verdict_none_falls_safe():
    assert gate._extract_verdict(None) == "INSUFFICIENT_EVIDENCE"


def test_extract_verdict_close_but_wrong_falls_safe():
    assert gate._extract_verdict("APPROVED") == "INSUFFICIENT_EVIDENCE"
    assert gate._extract_verdict("approve") == "APPROVE"  # case normalization works
    assert gate._extract_verdict("DENY") == "INSUFFICIENT_EVIDENCE"


# --- evaluate_evidence with mocked LLM ---

def test_evaluate_evidence_approve(monkeypatch):
    monkeypatch.setattr(gate, "_call_local", lambda prompt: "APPROVE")
    assert gate.evaluate_evidence(_sample_evidence()) == "APPROVE"


def test_evaluate_evidence_rework(monkeypatch):
    monkeypatch.setattr(gate, "_call_local", lambda prompt: "REWORK")
    assert gate.evaluate_evidence(_sample_evidence()) == "REWORK"


def test_evaluate_evidence_insufficient(monkeypatch):
    monkeypatch.setattr(gate, "_call_local", lambda prompt: "INSUFFICIENT_EVIDENCE")
    assert gate.evaluate_evidence(_sample_evidence()) == "INSUFFICIENT_EVIDENCE"


def test_evaluate_evidence_llm_timeout_falls_safe(monkeypatch):
    monkeypatch.setattr(gate, "_call_local", lambda prompt: "")
    assert gate.evaluate_evidence(_sample_evidence()) == "INSUFFICIENT_EVIDENCE"


def test_evaluate_evidence_malformed_output_falls_safe(monkeypatch):
    monkeypatch.setattr(gate, "_call_local", lambda prompt: "The evidence looks solid, I approve.")
    assert gate.evaluate_evidence(_sample_evidence()) == "INSUFFICIENT_EVIDENCE"


def test_evaluate_evidence_no_harness(monkeypatch):
    monkeypatch.setattr(gate, "_call_local", lambda prompt: "APPROVE")
    evidence = _sample_evidence(harness_manifest=None)
    assert gate.evaluate_evidence(evidence) == "APPROVE"
    # Also verify the prompt includes "no harness run"
    calls = []
    monkeypatch.setattr(gate, "_call_local", lambda p: (calls.append(p), "APPROVE")[1])
    gate.evaluate_evidence(evidence)
    assert "no harness run" in calls[0]


def test_evaluate_evidence_harness_failures_visible_in_prompt(monkeypatch):
    calls = []
    monkeypatch.setattr(gate, "_call_local", lambda p: (calls.append(p), "REWORK")[1])
    evidence = _sample_evidence(harness_manifest={
        "flow": "guardian_schema_retest",
        "passed": 10,
        "failed": 3,
        "total_cases": 13,
    })
    result = gate.evaluate_evidence(evidence)
    assert result == "REWORK"
    assert "3 FAILED" in calls[0]


def test_evaluate_evidence_non_dict_falls_safe():
    assert gate.evaluate_evidence(None) == "INSUFFICIENT_EVIDENCE"
    assert gate.evaluate_evidence("garbage") == "INSUFFICIENT_EVIDENCE"
    assert gate.evaluate_evidence(42) == "INSUFFICIENT_EVIDENCE"
