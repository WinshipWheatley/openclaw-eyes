from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import agent_task_proposals as atp
import dashboard_gen


def test_normalize_proposal_enforces_bounded_shape():
    proposal = atp.normalize_proposal(
        {
            "title": "Morning replay repair",
            "target_flow": "morning_brief",
            "reason": "Chief found a replay regression.",
            "urgency_lane": "now",
            "required_gate": "operator_review",
            "required_harness_mode": "recorded-replay",
            "success_evidence": ["replay manifest is stable"],
            "work_kind": "repair",
        },
        source_agent="guardian",
        now=datetime(2026, 4, 12, 1, 0, 0),
    )

    assert proposal["task_type"] == "agent_work_request"
    assert proposal["source_agent"] == "guardian"
    assert proposal["urgency_lane"] == "now"
    assert proposal["required_harness_mode"] == "recorded-replay"
    assert proposal["work_kind"] == "repair"
    assert proposal["advisory_only"] is True


def test_save_proposals_writes_store_and_visible_markdown(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "agent_task_proposals.json"
        visible = Path(tmp) / "advisory_task_proposals.md"
        monkeypatch.setattr(atp, "PROPOSALS_JSON", store, raising=False)
        monkeypatch.setattr(atp, "VISIBLE_MD", visible, raising=False)

        saved = atp.save_proposals(
            [
                {
                    "title": "Guardian bounded retest",
                    "target_flow": "guardian_schema",
                    "reason": "Schema reliability should be rechecked.",
                    "urgency_lane": "later",
                    "required_gate": "operator_review",
                    "required_harness_mode": "dry-run",
                    "success_evidence": ["json validation passes"],
                    "work_kind": "retest",
                }
            ],
            source_agent="guardian",
            now=datetime(2026, 4, 12, 1, 0, 0),
        )

        stored = json.loads(store.read_text(encoding="utf-8"))
        assert saved[0]["id"] == "ATP-GUARDIAN-20260412-001"
        assert stored["proposals"][0]["advisory_only"] is True
        assert "Guardian bounded retest" in visible.read_text(encoding="utf-8")


def test_dashboard_groups_advisory_proposals_by_lane(monkeypatch):
    monkeypatch.setattr(
        dashboard_gen,
        "_get_advisory_task_proposals",
        lambda: {
            "now": [{"id": "ATP-CHIEF-1", "source_agent": "chief", "work_kind": "repair", "title": "Fix morning replay", "target_flow": "morning_brief"}],
            "next": [{"id": "ATP-GUARDIAN-1", "source_agent": "guardian", "work_kind": "retest", "title": "Guardian schema retest", "target_flow": "guardian_schema"}],
            "later": [],
        },
    )
    monkeypatch.setattr(dashboard_gen, "load_json", lambda path: {"status": "idle"} if path == dashboard_gen.STATUS_FILE else {})
    monkeypatch.setattr(dashboard_gen, "_get_orchestrator_liveness", lambda: {"state_label": "Healthy", "governed": True, "note": ""})
    monkeypatch.setattr(dashboard_gen, "_get_last_attempted_task", lambda: None)
    monkeypatch.setattr(dashboard_gen, "_get_last_meaningful_successful_task", lambda: None)
    monkeypatch.setattr(dashboard_gen, "get_task_info", lambda: ("", ""))
    monkeypatch.setattr(dashboard_gen, "get_queued_tasks", lambda: [])
    monkeypatch.setattr(dashboard_gen, "get_runner_settings", lambda: {})
    monkeypatch.setattr(dashboard_gen, "_get_last_receipt", lambda: None)
    monkeypatch.setattr(dashboard_gen, "_get_last_verdict", lambda: None)
    monkeypatch.setattr(dashboard_gen, "_get_builder_scorecard", lambda: [])
    monkeypatch.setattr(dashboard_gen, "_get_headroom_summary", lambda: {})
    monkeypatch.setattr(dashboard_gen, "get_successful_loop_cycles", lambda: 0)
    monkeypatch.setattr(dashboard_gen, "get_completed_meaningful_tasks", lambda: 0)
    monkeypatch.setattr(dashboard_gen, "_human_state_reason", lambda *args, **kwargs: "")
    monkeypatch.setattr(dashboard_gen, "_likely_next_action", lambda *args, **kwargs: "Wait.")

    rendered = dashboard_gen.gen_right_now()

    assert "### Advisory Proposal Lanes (2 open)" in rendered
    assert "**Now:** 1" in rendered
    assert "ATP-CHIEF-1" in rendered
    assert "**Next:** 1" in rendered


def test_promote_proposal_creates_runnable_task_and_marks_promoted(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "agent_task_proposals.json"
        visible = Path(tmp) / "advisory_task_proposals.md"
        tasks = Path(tmp) / "tasks"
        monkeypatch.setattr(atp, "PROPOSALS_JSON", store, raising=False)
        monkeypatch.setattr(atp, "VISIBLE_MD", visible, raising=False)
        monkeypatch.setattr(atp, "TASKS_DIR", tasks, raising=False)

        atp.save_proposals(
            [
                {
                    "title": "Morning replay repair",
                    "target_flow": "morning_brief",
                    "reason": "Repair the replay regression from the advisory proposal.",
                    "urgency_lane": "next",
                    "required_gate": "operator_review",
                    "required_harness_mode": "recorded-replay",
                    "success_evidence": ["recorded replay passes"],
                    "work_kind": "repair",
                }
            ],
            source_agent="chief",
            now=datetime(2026, 4, 12, 1, 0, 0),
        )

        result = atp.promote_proposal("ATP-CHIEF-20260412-001", now=datetime(2026, 4, 12, 1, 5, 0))

        task_path = Path(result["task_path"])
        assert task_path.exists()
        content = task_path.read_text(encoding="utf-8")
        assert "title: atp-chief-20260412-001-morning-replay-repair" in content
        assert "proposal_id: ATP-CHIEF-20260412-001" in content
        assert "promotion_mode: manual" in content
        assert "generated_by: advisory_proposal_promotion" in content
        stored = json.loads(store.read_text(encoding="utf-8"))
        assert stored["proposals"][0]["status"] == "promoted"
        assert stored["proposals"][0]["promoted_task"] == result["task_name"]


def test_promote_proposal_prevents_double_promotion(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "agent_task_proposals.json"
        visible = Path(tmp) / "advisory_task_proposals.md"
        tasks = Path(tmp) / "tasks"
        monkeypatch.setattr(atp, "PROPOSALS_JSON", store, raising=False)
        monkeypatch.setattr(atp, "VISIBLE_MD", visible, raising=False)
        monkeypatch.setattr(atp, "TASKS_DIR", tasks, raising=False)

        atp.save_proposals(
            [
                {
                    "title": "Guardian bounded retest",
                    "target_flow": "guardian_schema",
                    "reason": "Retest the bounded schema path.",
                    "urgency_lane": "later",
                    "required_gate": "operator_review",
                    "required_harness_mode": "dry-run",
                    "success_evidence": ["json validation passes"],
                    "work_kind": "retest",
                }
            ],
            source_agent="guardian",
            now=datetime(2026, 4, 12, 1, 0, 0),
        )

        atp.promote_proposal("ATP-GUARDIAN-20260412-001", now=datetime(2026, 4, 12, 1, 5, 0))

        try:
            atp.promote_proposal("ATP-GUARDIAN-20260412-001", now=datetime(2026, 4, 12, 1, 6, 0))
            assert False, "expected double-promotion prevention"
        except ValueError as exc:
            assert "not promotable" in str(exc)


def test_auto_promote_safe_retest_promotes_only_one_qualified_proposal(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "agent_task_proposals.json"
        visible = Path(tmp) / "advisory_task_proposals.md"
        tasks = Path(tmp) / "tasks"
        monkeypatch.setattr(atp, "PROPOSALS_JSON", store, raising=False)
        monkeypatch.setattr(atp, "VISIBLE_MD", visible, raising=False)
        monkeypatch.setattr(atp, "TASKS_DIR", tasks, raising=False)

        saved = atp.save_proposals(
            [
                {
                    "title": "Safe retest one",
                    "target_flow": "chief_end_of_day_review",
                    "reason": "Retest one safe dry-run path.",
                    "urgency_lane": "next",
                    "required_gate": "none",
                    "required_harness_mode": "dry-run",
                    "success_evidence": ["dry-run completes"],
                    "work_kind": "retest",
                },
                {
                    "title": "Safe retest two",
                    "target_flow": "chief_end_of_day_review",
                    "reason": "Retest two safe dry-run path.",
                    "urgency_lane": "later",
                    "required_gate": "none",
                    "required_harness_mode": "dry-run",
                    "success_evidence": ["dry-run completes"],
                    "work_kind": "retest",
                },
            ],
            source_agent="chief",
            now=datetime(2026, 4, 12, 1, 0, 0),
        )

        result = atp.auto_promote_safe_retest([proposal["id"] for proposal in saved], now=datetime(2026, 4, 12, 1, 5, 0))

        assert result is not None
        task_path = Path(result["task_path"])
        assert task_path.exists()
        content = task_path.read_text(encoding="utf-8")
        assert "promotion_mode: auto-safe-retest" in content
        assert "generated_by: advisory_proposal_auto_promotion" in content
        assert "harness_mode: dry-run" in content
        assert "execution_mode: harness-backed-retest" in content
        assert "harness_expectation: gather evidence through a dry-run harness path before any live-touching follow-up" in content
        stored = json.loads(store.read_text(encoding="utf-8"))
        promoted = [p for p in stored["proposals"] if p["status"] == "promoted"]
        proposed = [p for p in stored["proposals"] if p["status"] == "proposed"]
        assert len(promoted) == 1
        assert len(proposed) == 1


def test_auto_promote_safe_retest_skips_non_safe_proposals(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "agent_task_proposals.json"
        visible = Path(tmp) / "advisory_task_proposals.md"
        tasks = Path(tmp) / "tasks"
        monkeypatch.setattr(atp, "PROPOSALS_JSON", store, raising=False)
        monkeypatch.setattr(atp, "VISIBLE_MD", visible, raising=False)
        monkeypatch.setattr(atp, "TASKS_DIR", tasks, raising=False)

        saved = atp.save_proposals(
            [
                {
                    "title": "Needs gate",
                    "target_flow": "chief_end_of_day_review",
                    "reason": "Not safe for automatic promotion.",
                    "urgency_lane": "next",
                    "required_gate": "operator_review",
                    "required_harness_mode": "dry-run",
                    "success_evidence": ["dry-run completes"],
                    "work_kind": "retest",
                }
            ],
            source_agent="chief",
            now=datetime(2026, 4, 12, 1, 0, 0),
        )

        result = atp.auto_promote_safe_retest([proposal["id"] for proposal in saved], now=datetime(2026, 4, 12, 1, 5, 0))

        assert result is None
        assert not list(tasks.glob("*.md"))


def test_auto_promote_safe_retest_carries_morning_brief_harness_entrypoint(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "agent_task_proposals.json"
        visible = Path(tmp) / "advisory_task_proposals.md"
        tasks = Path(tmp) / "tasks"
        monkeypatch.setattr(atp, "PROPOSALS_JSON", store, raising=False)
        monkeypatch.setattr(atp, "VISIBLE_MD", visible, raising=False)
        monkeypatch.setattr(atp, "TASKS_DIR", tasks, raising=False)

        saved = atp.save_proposals(
            [
                {
                    "title": "Morning brief harness retest",
                    "target_flow": "morning_brief",
                    "reason": "Retest the morning brief through the proven harness path.",
                    "urgency_lane": "next",
                    "required_gate": "none",
                    "required_harness_mode": "dry-run",
                    "success_evidence": ["harness run completes"],
                    "work_kind": "retest",
                }
            ],
            source_agent="chief",
            now=datetime(2026, 4, 12, 1, 0, 0),
        )

        result = atp.auto_promote_safe_retest([proposal["id"] for proposal in saved], now=datetime(2026, 4, 12, 1, 5, 0))

        content = Path(result["task_path"]).read_text(encoding="utf-8")
        assert "harness_flow: morning_brief" in content
        assert "harness_entrypoint: python3 /home/openclaw/morning_brief_harness.py --fixture /home/openclaw/staging/morning_brief_harness/fixtures/sample_morning.json" in content


def test_auto_promote_safe_retest_carries_chief_eod_harness_entrypoint(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "agent_task_proposals.json"
        visible = Path(tmp) / "advisory_task_proposals.md"
        tasks = Path(tmp) / "tasks"
        monkeypatch.setattr(atp, "PROPOSALS_JSON", store, raising=False)
        monkeypatch.setattr(atp, "VISIBLE_MD", visible, raising=False)
        monkeypatch.setattr(atp, "TASKS_DIR", tasks, raising=False)

        saved = atp.save_proposals(
            [
                {
                    "title": "Chief end-of-day review harness retest",
                    "target_flow": "chief_end_of_day_review",
                    "reason": "Retest the chief end-of-day review through the proven harness path.",
                    "urgency_lane": "next",
                    "required_gate": "none",
                    "required_harness_mode": "dry-run",
                    "success_evidence": ["harness run completes"],
                    "work_kind": "retest",
                }
            ],
            source_agent="chief",
            now=datetime(2026, 4, 12, 1, 0, 0),
        )

        result = atp.auto_promote_safe_retest([proposal["id"] for proposal in saved], now=datetime(2026, 4, 12, 1, 5, 0))

        content = Path(result["task_path"]).read_text(encoding="utf-8")
        assert "harness_flow: chief_end_of_day_review" in content
        assert "harness_entrypoint: python3 /home/openclaw/chief_eod_harness.py --fixture /home/openclaw/staging/chief_eod_harness/fixtures/sample_eod.json" in content


def test_auto_promote_safe_retest_carries_guardian_schema_harness_entrypoint(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "agent_task_proposals.json"
        visible = Path(tmp) / "advisory_task_proposals.md"
        tasks = Path(tmp) / "tasks"
        monkeypatch.setattr(atp, "PROPOSALS_JSON", store, raising=False)
        monkeypatch.setattr(atp, "VISIBLE_MD", visible, raising=False)
        monkeypatch.setattr(atp, "TASKS_DIR", tasks, raising=False)

        saved = atp.save_proposals(
            [
                {
                    "title": "Guardian approval schema retest",
                    "target_flow": "guardian_schema_retest",
                    "reason": "Retest Guardian approval input validation schema through the harness path.",
                    "urgency_lane": "next",
                    "required_gate": "none",
                    "required_harness_mode": "dry-run",
                    "success_evidence": ["all validation cases pass", "failed == 0 in manifest"],
                    "work_kind": "retest",
                }
            ],
            source_agent="chief",
            now=datetime(2026, 4, 12, 1, 0, 0),
        )

        result = atp.auto_promote_safe_retest([proposal["id"] for proposal in saved], now=datetime(2026, 4, 12, 1, 5, 0))

        content = Path(result["task_path"]).read_text(encoding="utf-8")
        assert "harness_flow: guardian_schema_retest" in content
        assert "harness_entrypoint: python3 /home/openclaw/guardian_schema_harness.py --fixture /home/openclaw/staging/guardian_schema_harness/fixtures/guardian_validation.json" in content
