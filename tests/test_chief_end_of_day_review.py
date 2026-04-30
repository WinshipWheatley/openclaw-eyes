from __future__ import annotations

import json
import sys
import types
from datetime import datetime
from pathlib import Path

import chief_end_of_day_review as eod


def _redirect_live_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(eod, "CONTINUITY_PATH", tmp_path / "Chief Continuity.md", raising=False)


def test_active_user_gate_is_conservative(tmp_path, monkeypatch):
    _redirect_live_writes(tmp_path, monkeypatch)
    route_log = tmp_path / "route_log.csv"
    route_log.write_text(
        "timestamp,message_hash,intent,route_method,llm_fallback_used\n"
        "2026-04-11 00:40:00,abcd1234,cassandra,cassandra_direct,False\n",
        encoding="utf-8",
    )
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({"status": "pc_turn"}), encoding="utf-8")
    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps({"status": "active", "active_workflow": "focus_block"}), encoding="utf-8")
    approval_file = tmp_path / "approval.json"
    approval_file.write_text(
        json.dumps({"status": "pending", "requested_at": "2026-04-11T00:50:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(eod, "ROUTE_LOG", route_log, raising=False)
    monkeypatch.setattr(eod, "STATUS_FILE", status_file, raising=False)
    monkeypatch.setattr(eod, "SESSION_FILE", session_file, raising=False)
    monkeypatch.setattr(eod, "APPROVAL_PENDING", approval_file, raising=False)

    reasons = eod.active_user_reasons(datetime(2026, 4, 11, 1, 0, 0))

    assert "chief_session active (focus_block)" in reasons
    assert "ops loop status is pc_turn" in reasons
    assert "fresh approval pending" in reasons
    assert any(reason.startswith("recent operator message") for reason in reasons)


def test_run_review_writes_artifact_and_saves_advisory_proposals(tmp_path, monkeypatch):
    _redirect_live_writes(tmp_path, monkeypatch)
    review_dir = tmp_path / "chief_end_of_day"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    (archive_dir / "task_example_20260410.md").write_text("done", encoding="utf-8")
    (tmp_path / "pc_output.md").write_text("builder output", encoding="utf-8")
    (tmp_path / "mac_review.md").write_text("planner notes", encoding="utf-8")
    (tmp_path / "orchestrator.log").write_text("orchestrator tail", encoding="utf-8")
    (tmp_path / "builder.out").write_text("builder tail", encoding="utf-8")

    monkeypatch.setattr(eod, "REVIEW_DIR", review_dir, raising=False)
    monkeypatch.setattr(eod, "ARCHIVE_DIR", archive_dir, raising=False)
    monkeypatch.setattr(eod, "PC_OUTPUT", tmp_path / "pc_output.md", raising=False)
    monkeypatch.setattr(eod, "MAC_REVIEW", tmp_path / "mac_review.md", raising=False)
    monkeypatch.setattr(eod, "ORCH_LOG", tmp_path / "orchestrator.log", raising=False)
    monkeypatch.setattr(eod, "BUILDER_LOG", tmp_path / "builder.out", raising=False)
    monkeypatch.setattr(eod, "build_review_context", lambda compact=False: "compact context", raising=False)
    saved_calls = []
    monkeypatch.setattr(
        eod,
        "save_proposals",
        lambda proposals, source_agent, now=None: saved_calls.extend(proposals) or [
            {"id": "ATP-CHIEF-20260411-001", **proposals[0]}
        ],
    )
    monkeypatch.setattr(eod, "auto_promote_safe_retest", lambda proposal_ids, now=None: None, raising=False)
    monkeypatch.setattr(
        eod,
        "_run_review_model",
        lambda context: json.loads(json.dumps(
            {
                "summary": "Chief found one hardening issue and one polish gap.",
                "findings": ["Tighten morning fallback coverage", "Queue one scheduler hardening pass"],
                "proposals": [
                    {
                        "title": "Scheduler hardening follow-up",
                        "target_flow": "polish_loop",
                        "reason": "Harden the scheduler edge case surfaced in end-of-day review.",
                        "urgency_lane": "next",
                        "required_gate": "operator_review",
                        "required_harness_mode": "dry-run",
                        "success_evidence": ["Regression covered and tests pass"],
                        "work_kind": "repair",
                    }
                ],
                "_review_meta": {
                    "structured_output_lane": "fast",
                    "fast_attempt_structured": True,
                    "strong_attempt_structured": False,
                    "empty_output_cause": None,
                },
            }
        )),
    )

    artifact = eod.run_review(datetime(2026, 4, 11, 1, 0, 0))

    assert artifact["proposal_count"] == 1
    assert artifact["proposal_ids"] == ["ATP-CHIEF-20260411-001"]
    assert artifact["auto_promoted_task"] is None
    assert artifact["structured_output_lane"] == "fast"
    assert artifact["fast_attempt_structured"] is True
    assert artifact["strong_attempt_structured"] is False
    assert artifact["empty_output_cause"] is None
    assert saved_calls[0]["work_kind"] == "repair"

    saved_json = json.loads((review_dir / "2026-04-11.json").read_text(encoding="utf-8"))
    assert saved_json["summary"] == "Chief found one hardening issue and one polish gap."
    assert saved_json["proposal_ids"] == artifact["proposal_ids"]
    assert saved_json["structured_output_lane"] == "fast"
    assert (review_dir / "2026-04-11.md").exists()


def test_run_review_falls_back_without_stalling_when_local_models_return_empty(tmp_path, monkeypatch):
    _redirect_live_writes(tmp_path, monkeypatch)
    review_dir = tmp_path / "chief_end_of_day"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    monkeypatch.setattr(eod, "REVIEW_DIR", review_dir, raising=False)
    monkeypatch.setattr(eod, "ARCHIVE_DIR", archive_dir, raising=False)
    monkeypatch.setattr(eod, "build_review_context", lambda compact=False: "compact context", raising=False)
    saved_calls = []
    monkeypatch.setattr(
        eod,
        "save_proposals",
        lambda proposals, source_agent, now=None: saved_calls.extend(proposals) or [
            {"id": "ATP-CHIEF-20260411-001", **proposals[0]}
        ],
        raising=False,
    )
    monkeypatch.setattr(
        eod,
        "auto_promote_safe_retest",
        lambda proposal_ids, now=None: {"proposal_id": proposal_ids[0], "task_name": "atp-chief-20260411-001-end-of-day-review-harness-retest"},
        raising=False,
    )
    monkeypatch.setattr(eod, "_single_shot_local", lambda prompt, lane, timeout: "", raising=False)

    artifact = eod.run_review(datetime(2026, 4, 11, 1, 0, 0))

    assert artifact["proposal_count"] == 1
    assert artifact["proposal_ids"] == ["ATP-CHIEF-20260411-001"]
    assert artifact["auto_promoted_proposal_id"] == "ATP-CHIEF-20260411-001"
    assert artifact["auto_promoted_task"] == "atp-chief-20260411-001-end-of-day-review-harness-retest"
    assert artifact["summary"].startswith("Chief review fallback:")
    assert artifact["structured_output_lane"] == "fallback"
    assert artifact["fast_attempt_structured"] is False
    assert artifact["strong_attempt_structured"] is False
    assert artifact["empty_output_cause"] == "empty_or_unparseable_fast_and_strong"
    assert saved_calls[0]["work_kind"] == "retest"
    assert saved_calls[0]["required_gate"] == "none"
    assert saved_calls[0]["required_harness_mode"] == "dry-run"
    assert saved_calls[0]["target_flow"] == "morning_brief"
    saved_json = json.loads((review_dir / "2026-04-11.json").read_text(encoding="utf-8"))
    assert saved_json["proposal_ids"] == ["ATP-CHIEF-20260411-001"]
    assert saved_json["empty_output_cause"] == "empty_or_unparseable_fast_and_strong"


def test_run_review_uses_strong_lane_when_fast_lane_returns_no_structured_output(tmp_path, monkeypatch):
    _redirect_live_writes(tmp_path, monkeypatch)
    review_dir = tmp_path / "chief_end_of_day"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    monkeypatch.setattr(eod, "REVIEW_DIR", review_dir, raising=False)
    monkeypatch.setattr(eod, "ARCHIVE_DIR", archive_dir, raising=False)
    monkeypatch.setattr(eod, "build_review_context", lambda compact=False: "compact context", raising=False)
    monkeypatch.setattr(
        eod,
        "save_proposals",
        lambda proposals, source_agent, now=None: [{"id": "ATP-CHIEF-20260411-002", **proposals[0]}],
        raising=False,
    )
    monkeypatch.setattr(eod, "auto_promote_safe_retest", lambda proposal_ids, now=None: None, raising=False)
    responses = iter(
        [
            "",
            json.dumps(
                {
                    "summary": "Strong lane recovered the review output.",
                    "findings": ["Fast lane returned no structured output in budget."],
                    "proposals": [
                        {
                            "title": "Keep strong-lane fallback in review harness",
                            "target_flow": "chief_end_of_day_review",
                            "reason": "Strong lane still emits structured advisory output when fast lane does not.",
                            "urgency_lane": "next",
                            "required_gate": "operator_review",
                            "required_harness_mode": "dry-run",
                            "success_evidence": ["Strong lane path remains covered"],
                            "work_kind": "retest",
                        }
                    ],
                }
            ),
        ]
    )
    monkeypatch.setattr(eod, "_single_shot_local", lambda prompt, lane, timeout: next(responses), raising=False)

    artifact = eod.run_review(datetime(2026, 4, 11, 1, 0, 0))

    assert artifact["structured_output_lane"] == "strong"
    assert artifact["fast_attempt_structured"] is False
    assert artifact["strong_attempt_structured"] is True
    assert artifact["empty_output_cause"] is None
    saved_json = json.loads((review_dir / "2026-04-11.json").read_text(encoding="utf-8"))
    assert saved_json["structured_output_lane"] == "strong"


def test_run_review_model_uses_generous_fast_then_deep_timeouts(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(eod, "FAST_REVIEW_TIMEOUT_SECONDS", 120)
    monkeypatch.setattr(eod, "STRONG_REVIEW_TIMEOUT_SECONDS", 420)

    responses = iter([
        "",
        json.dumps({"summary": "Deep lane recovered.", "findings": [], "proposals": []}),
    ])

    def fake_single_shot(prompt, lane, timeout):
        calls.append({"lane": lane, "timeout": timeout})
        return next(responses)

    monkeypatch.setattr(eod, "_single_shot_local", fake_single_shot)

    parsed = eod._run_review_model("compact context")

    assert parsed["summary"] == "Deep lane recovered."
    assert parsed["_review_meta"]["structured_output_lane"] == "strong"
    assert parsed["_review_meta"]["strong_model_lane"] == "deep"
    assert calls == [
        {"lane": "fast", "timeout": 120},
        {"lane": "deep", "timeout": 420},
    ]
