from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

import cassandra_briefing_brain as briefing
import chief_morning_synthesis as morning_synthesis
import chief_ops_reporter as ops


STALE_LEAD = (
    "- [OPEN] St. Anne's / misc tech: reconcile payer, amount, and billing path "
    "for the unpaid Iranian band tech work and the unpaid Talent Machine tech job."
)
STALE_ACTION = (
    "- [OPEN] Live Arts Maryland / Annapolis Choral 2025: ask Dane which deposits "
    "covered speaker rental versus tech services (300 on 2025-03-11, 450 on "
    "2025-05-09, 750 on 2025-07-15); copy Draper by default."
)
STALE_ACTIONS = (STALE_LEAD, STALE_ACTION)


def _write_at(path: Path, text: str, when: datetime) -> None:
    path.write_text(text, encoding="utf-8")
    stamp = when.timestamp()
    os.utime(path, (stamp, stamp))


def _stale_source(path: Path, *, fresh_mtime: datetime) -> None:
    _write_at(
        path,
        "---\n"
        "type: ops-current\n"
        "updated: 2026-04-05\n"
        "---\n\n"
        "# Ops Actions\n\n"
        f"{STALE_LEAD}\n"
        f"{STALE_ACTION}\n",
        fresh_mtime,
    )


def _assert_no_stale_actions(text: str) -> None:
    for action in STALE_ACTIONS:
        assert action not in text


def test_frontmatter_timestamp_beats_fresh_mtime_and_empties_stale_lines(
    tmp_path,
    monkeypatch,
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = tmp_path / "Ops Actions.md"
    _stale_source(source, fresh_mtime=now)
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    action_slice = ops.read_ops_actions_slice(now=now)

    assert action_slice == {
        "status": "stale",
        "as_of": "2026-04-05T00:00:00+00:00",
        "timestamp_source": "frontmatter:updated",
        "lines": [],
    }


def test_frontmatter_timestamp_precedence_is_as_of_then_updated_then_generated_at(
    tmp_path,
    monkeypatch,
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = tmp_path / "Ops Actions.md"
    _write_at(
        source,
        "---\n"
        "as_of: 2025-07-15T09:00:00+00:00\n"
        "updated: 2026-07-10T11:30:00+00:00\n"
        "generated_at: 2026-07-10T11:45:00+00:00\n"
        "---\n"
        f"{STALE_ACTION}\n",
        now,
    )
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    action_slice = ops.read_ops_actions_slice(now=now)

    assert action_slice["status"] == "stale"
    assert action_slice["as_of"] == "2025-07-15T09:00:00+00:00"
    assert action_slice["timestamp_source"] == "frontmatter:as_of"
    assert action_slice["lines"] == []


def test_invalid_authoritative_frontmatter_does_not_fall_back_to_fresh_mtime(
    tmp_path,
    monkeypatch,
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = tmp_path / "Ops Actions.md"
    _write_at(
        source,
        "---\nas_of: definitely-not-a-time\n---\n- current-looking action\n",
        now,
    )
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    action_slice = ops.read_ops_actions_slice(now=now)

    assert action_slice == {
        "status": "invalid",
        "as_of": None,
        "timestamp_source": "frontmatter:as_of",
        "lines": [],
    }


def test_unclosed_frontmatter_fails_closed_instead_of_laundering_fresh_mtime(
    tmp_path,
    monkeypatch,
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = tmp_path / "Ops Actions.md"
    _write_at(
        source,
        f"---\nupdated: 2025-01-01\n{STALE_LEAD}\n{STALE_ACTION}\n",
        now,
    )
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    action_slice = ops.read_ops_actions_slice(now=now)

    assert action_slice == {
        "status": "invalid",
        "as_of": None,
        "timestamp_source": "frontmatter:invalid",
        "lines": [],
    }


def test_mtime_is_used_only_when_frontmatter_timestamp_is_absent(tmp_path, monkeypatch):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = tmp_path / "Ops Actions.md"
    _write_at(source, "# Ops Actions\n\n- [OPEN] current action\n", now - timedelta(hours=2))
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    action_slice = ops.read_ops_actions_slice(now=now)

    assert action_slice["status"] == "fresh"
    assert action_slice["timestamp_source"] == "mtime"
    assert action_slice["as_of"] == "2026-07-10T10:00:00+00:00"
    assert action_slice["lines"] == ["- [OPEN] current action"]


def test_missing_source_has_empty_structured_slice(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "_OPS_ACTIONS", tmp_path / "missing.md")

    action_slice = ops.read_ops_actions_slice(
        now=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    )

    assert action_slice == {
        "status": "missing",
        "as_of": None,
        "timestamp_source": None,
        "lines": [],
    }


def test_stale_report_artifact_is_honest_and_never_repeats_the_old_action(
    tmp_path,
    monkeypatch,
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = tmp_path / "Ops Actions.md"
    _stale_source(source, fresh_mtime=now)
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    artifact = ops.build_ops_actions_artifact_markdown(now=now)

    assert "slice_status: stale" in artifact
    assert "slice_as_of: 2026-04-05T00:00:00+00:00" in artifact
    assert "slice_timestamp_source: frontmatter:updated" in artifact
    assert "No current priority is claimed from this stale slice." in artifact
    assert "Pending (0)" in artifact
    assert "Completed (0)" in artifact
    _assert_no_stale_actions(artifact)


def test_fresh_report_artifact_admits_current_lines(tmp_path, monkeypatch):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = tmp_path / "Ops Actions.md"
    _write_at(
        source,
        "---\nas_of: 2026-07-10T11:00:00+00:00\n---\n- URGENT: current action\n",
        now,
    )
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    artifact = ops.build_ops_actions_artifact_markdown(now=now)

    assert "slice_status: fresh" in artifact
    assert "Pending (1)" in artifact
    assert "[PRIORITY] - URGENT: current action" in artifact


def test_artifact_write_uses_one_captured_slice_for_content_and_return_metadata(
    tmp_path,
    monkeypatch,
):
    artifact_path = tmp_path / "Ops Actions Context.md"
    calls: list[int] = []

    def changing_slice(n_actions=12, *, now=None):
        calls.append(n_actions)
        return {
            "status": "fresh" if len(calls) == 1 else "stale",
            "as_of": "2026-07-10T11:00:00+00:00",
            "timestamp_source": "frontmatter:as_of",
            "lines": ["- first captured line"] if len(calls) == 1 else [],
        }

    monkeypatch.setattr(ops, "read_ops_actions_slice", changing_slice)
    monkeypatch.setattr(ops, "_OPS_ACTIONS_CONTEXT", artifact_path)

    result = ops.write_ops_actions_artifact(
        now=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    )

    assert calls == [12]
    assert result["slice"]["status"] == "fresh"
    assert "slice_status: fresh" in result["markdown"]
    assert "first captured line" in result["markdown"]


def test_afternoon_prompt_removes_raw_stale_pending_actions_and_adds_age_note(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "Ops Actions.md"
    _stale_source(source, fresh_mtime=datetime.now().astimezone())
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)
    monkeypatch.setattr(
        briefing,
        "build_context_snapshot",
        lambda: (
            "Canonical current fact.\n"
            "Pending actions:\n"
            f"  {STALE_LEAD}\n"
            f"  {STALE_ACTION}\n"
            "Payment follow-ups:\n"
            "  safe current payment line"
        ),
    )
    monkeypatch.setattr(
        briefing,
        "resolve_local_model",
        lambda prompt, task_class=None: ("test-model", "test-lane"),
    )
    captured: dict[str, str] = {}

    def fake_model(prompt, **kwargs):
        captured["prompt"] = prompt
        return "Safe afternoon response."

    monkeypatch.setattr(briefing, "ollama_call", fake_model)

    output = briefing.generate_briefing("afternoon")

    assert output == "Safe afternoon response."
    _assert_no_stale_actions(captured["prompt"])
    assert "safe current payment line" in captured["prompt"]
    assert "Ops Actions slice: stale" in captured["prompt"]
    assert "No current priority is claimed" in captured["prompt"]


def test_stale_afternoon_and_evening_fallbacks_make_no_current_priority_claim(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "Ops Actions.md"
    _stale_source(source, fresh_mtime=datetime.now().astimezone())
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    for slot in ("afternoon", "evening"):
        text = briefing._bounded_ops_slot_fallback(slot)
        assert "Ops Actions slice is stale" in text
        assert "as of 2026-04-05" in text
        assert "No current priority is claimed" in text
        assert "Midday priority" not in text
        assert "Tonight's top open item" not in text
        _assert_no_stale_actions(text)


def test_fresh_evening_fallback_keeps_bounded_current_priority(tmp_path, monkeypatch):
    now = datetime.now().astimezone()
    source = tmp_path / "Ops Actions.md"
    _write_at(
        source,
        f"---\nas_of: {now.isoformat(timespec='seconds')}\n---\n- URGENT: finish current lane\n",
        now,
    )
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)

    text = briefing._bounded_ops_slot_fallback("evening")

    assert "Tonight's top open item: - URGENT: finish current lane" in text
    assert "No current priority is claimed" not in text


def test_fresh_fallback_classifies_the_same_slice_it_age_checked(monkeypatch):
    captured: list[dict] = []
    action_slice = {
        "status": "fresh",
        "as_of": "2026-07-10T11:00:00+00:00",
        "timestamp_source": "frontmatter:as_of",
        "lines": ["- one captured current action"],
    }
    monkeypatch.setattr(ops, "read_ops_actions_slice", lambda: action_slice)

    def summary(n_actions=12, *, action_slice=None):
        captured.append(action_slice)
        return "Pending (1):\n  - one captured current action\nCompleted (0):\n  (none)"

    monkeypatch.setattr(ops, "build_action_summary", summary)

    text = briefing._bounded_ops_slot_fallback("evening")

    assert captured == [action_slice]
    assert "one captured current action" in text


def test_stale_slice_cannot_reenter_through_indirect_morning_artifacts(
    tmp_path,
    monkeypatch,
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = tmp_path / "Ops Actions.md"
    context_artifact = tmp_path / "Ops Actions Context.md"
    synthesis_artifact = tmp_path / "Chief Morning Synthesis.md"
    _stale_source(source, fresh_mtime=now)
    monkeypatch.setattr(ops, "_OPS_ACTIONS", source)
    monkeypatch.setattr(ops, "_OPS_ACTIONS_CONTEXT", context_artifact)

    ops.write_ops_actions_artifact(now=now)
    synthesis = morning_synthesis.build_chief_morning_synthesis_markdown(
        now=now,
        upstream_artifacts=(
            morning_synthesis.UpstreamArtifact("Ops Actions Context", context_artifact),
        ),
    )
    synthesis_artifact.write_text(synthesis, encoding="utf-8")
    monkeypatch.setattr(briefing, "_CHIEF_MORNING_SYNTHESIS", synthesis_artifact)

    reference = briefing._build_morning_context_from_synthesis()

    _assert_no_stale_actions(context_artifact.read_text(encoding="utf-8"))
    _assert_no_stale_actions(synthesis)
    _assert_no_stale_actions(reference["prompt_context"])
    assert "Ops Actions Context: stale" in synthesis


def test_morning_synthesis_rejects_stale_ops_context_even_with_fresh_file_mtime(tmp_path):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    context_artifact = tmp_path / "Ops Actions Context.md"
    _write_at(
        context_artifact,
        "---\n"
        "type: ops-actions-context\n"
        "generated_at: 2026-07-10T11:59:00+00:00\n"
        "slice_status: stale\n"
        "slice_as_of: 2026-04-05T00:00:00+00:00\n"
        "slice_timestamp_source: frontmatter:updated\n"
        "---\n\n"
        "## Summary\n\n"
        f"{STALE_LEAD}\n"
        f"{STALE_ACTION}\n",
        now,
    )

    synthesis = morning_synthesis.build_chief_morning_synthesis_markdown(
        now=now,
        upstream_artifacts=(
            morning_synthesis.UpstreamArtifact("Ops Actions Context", context_artifact),
        ),
    )

    _assert_no_stale_actions(synthesis)
    assert "Ops Actions Context: stale: source as of 2026-04-05T00:00:00+00:00" in synthesis
