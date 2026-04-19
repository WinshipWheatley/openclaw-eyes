"""
tests/test_cassandra_briefing_context.py

Unit tests for cassandra_briefing_brain action classification and summary.

Verifies:
- classify_ops_actions separates pending vs completed correctly
- Counts match source records
- Priority items appear first in the Pending list
- build_action_summary produces distinct Pending/Completed sections with counts
"""

import cassandra_briefing_brain as bb


def test_classify_separates_pending_and_completed():
    lines = [
        "- Follow up with distributor about payment",
        "- [DONE] Update release date in calendar",
        "- Urgent: review mixing notes from yesterday",
        "- ✓ Send invoice to label",
        "- Check in with photographer next week",
    ]
    pending, completed = bb.classify_ops_actions(lines)
    assert len(pending) == 3
    assert len(completed) == 2


def test_counts_match_source_records():
    lines = [
        "- Task A",
        "- [done] Task B",
        "- Task C [x]",
        "- Task D",
    ]
    pending, completed = bb.classify_ops_actions(lines)
    assert len(pending) + len(completed) == 4
    assert len(pending) == 2
    assert len(completed) == 2


def test_done_variants_all_classified_as_completed():
    lines = [
        "- [done] item one",
        "- [DONE] item two",
        "- ✓ item three",
        "- [x] item four",
        "- [completed] item five",
        "- ~~item six~~",
        "- (done) item seven",
    ]
    pending, completed = bb.classify_ops_actions(lines)
    assert len(completed) == 7
    assert len(pending) == 0


def test_priority_items_appear_first_in_pending():
    lines = [
        "- Regular follow-up item",
        "- Another routine task",
        "- URGENT: call back manager",
        "- ASAP review contract",
    ]
    pending, completed = bb.classify_ops_actions(lines)
    assert len(pending) == 4
    assert len(completed) == 0
    # First two items should be the priority ones
    low = pending[0].lower()
    assert "urgent" in low or "asap" in low
    low = pending[1].lower()
    assert "urgent" in low or "asap" in low


def test_priority_keywords_all_detected():
    priority_lines = [
        "- urgent: do this now",
        "- asap: contact venue",
        "- critical issue with the release",
        "- high priority: update bio",
        "- finish this today",
        "- overdue invoice needs sending",
    ]
    pending, _ = bb.classify_ops_actions(priority_lines)
    assert len(pending) == 6
    # All should sort to the front (no non-priority items to displace them)
    for item in pending:
        assert bb._PRIORITY_RE.search(item)


def test_build_action_summary_contains_distinct_sections(tmp_path, monkeypatch):
    ops_path = tmp_path / "Ops Actions.md"
    ops_path.write_text(
        "# Ops Actions\n\n"
        "- Follow up with distributor\n"
        "- [DONE] Update calendar\n"
        "- URGENT: review mixing notes\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bb, "_OPS_ACTIONS", ops_path)

    summary = bb.build_action_summary()

    assert "Pending (" in summary
    assert "Completed (" in summary


def test_build_action_summary_counts_are_accurate(tmp_path, monkeypatch):
    ops_path = tmp_path / "Ops Actions.md"
    ops_path.write_text(
        "- item one\n"
        "- [done] item two\n"
        "- item three\n"
        "- ✓ item four\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bb, "_OPS_ACTIONS", ops_path)

    summary = bb.build_action_summary()

    assert "Pending (2)" in summary
    assert "Completed (2)" in summary


def test_build_action_summary_marks_priority_items(tmp_path, monkeypatch):
    ops_path = tmp_path / "Ops Actions.md"
    ops_path.write_text(
        "- routine task\n"
        "- URGENT: call manager\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bb, "_OPS_ACTIONS", ops_path)

    summary = bb.build_action_summary()

    assert "[PRIORITY]" in summary


def test_build_action_summary_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(bb, "_OPS_ACTIONS", tmp_path / "nonexistent.md")

    summary = bb.build_action_summary()

    assert "Pending (0)" in summary
    assert "Completed (0)" in summary


def test_ops_actions_artifact_contains_metadata_and_bounded_summary(tmp_path, monkeypatch):
    ops_path = tmp_path / "Ops Actions.md"
    artifact_path = tmp_path / "Ops Actions Context.md"
    ops_path.write_text(
        "# Ops Actions\n\n"
        "- routine task\n"
        "- URGENT: call manager today\n"
        "- [done] completed task\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bb, "_OPS_ACTIONS", ops_path)
    monkeypatch.setattr(bb, "_OPS_ACTIONS_CONTEXT", artifact_path)

    artifact = bb.write_ops_actions_artifact(n_actions=2)
    content = artifact_path.read_text(encoding="utf-8")

    assert artifact["path"] == str(artifact_path)
    assert "type: ops-actions-context" in content
    assert "source_module: cassandra_briefing_brain.py" in content
    assert f"source_path: {ops_path}" in content
    assert "freshness:" in content
    assert "bounded_to_last_actions: 2" in content
    assert "Bound: last 2 non-heading action lines" in content
    assert "Pending (1)" in content
    assert "Completed (1)" in content
    assert "routine task" not in content


def test_ops_actions_artifact_missing_source_records_staleness_note(tmp_path, monkeypatch):
    artifact_path = tmp_path / "Ops Actions Context.md"
    monkeypatch.setattr(bb, "_OPS_ACTIONS", tmp_path / "missing.md")
    monkeypatch.setattr(bb, "_OPS_ACTIONS_CONTEXT", artifact_path)

    bb.write_ops_actions_artifact()
    content = artifact_path.read_text(encoding="utf-8")

    assert "missing: source file not found" in content
    assert "Pending (0)" in content
    assert "Completed (0)" in content
