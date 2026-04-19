import sys

import inbox_parser


def _write_handoff_fixture(tmp_path):
    inbox = """# Inbox

## Active Inbox

### Add calendar summaries
```
date: 2026-04-18 10:00
source: telegram
status: unrouted
id: [generated:auto]
tags: calendar
text: Add a new bot behavior for calendar conflict summaries.
bot_confidence:
router_note:
routed_to:
```

### Redesign brain routing
```
date: 2026-04-18 10:01
source: note
status: unrouted
id: [generated:auto]
tags: architecture
text: Redesign how Chief router connects to all brain modules.
bot_confidence:
router_note:
routed_to:
```

## Routed

| ID | Summary | Tags | Queue | Routed By | Date |
|---|---|---|---|---|---|
"""
    queues = """# Queues

## Feature Queue

| ID | Title | Type | Priority | Winship | Bot | Notes | Queued By |
|---|---|---|---|---|---|---|---|
| feat-004 | Existing feature | feature | low | — | 2 | existing | manual |
"""
    (tmp_path / "03_Inbox.md").write_text(inbox, encoding="utf-8")
    (tmp_path / "04_Queues.md").write_text(queues, encoding="utf-8")
    return inbox, queues


CLASSIFIER_CALLS = []


def _fake_classifier(prompt, timeout=30, task_class=None):
    CLASSIFIER_CALLS.append({"timeout": timeout, "task_class": task_class})
    if "calendar conflict summaries" in prompt:
        return {
            "classification": "feature",
            "bot_confidence": 4,
            "router_note": "New calendar summary behavior.",
            "suggested_title": "Add calendar summaries",
            "suggested_priority": "medium",
            "suggested_type": "feature",
        }
    if "Chief router connects" in prompt:
        return {
            "classification": "architecture",
            "bot_confidence": 3,
            "router_note": "Structural router change.",
            "suggested_title": "Redesign brain routing",
            "suggested_priority": "medium",
            "suggested_type": "architecture",
        }
    raise AssertionError("unexpected classifier prompt")


def test_dry_run_reserves_queue_ids_without_writing(tmp_path, monkeypatch, capsys):
    CLASSIFIER_CALLS.clear()
    inbox_before, queues_before = _write_handoff_fixture(tmp_path)
    monkeypatch.setattr(inbox_parser, "ollama_json", _fake_classifier)
    monkeypatch.setattr(
        sys,
        "argv",
        ["inbox_parser.py", "--dir", str(tmp_path), "--dry-run"],
    )

    try:
        inbox_parser.main()
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "classification: feature | queue_id: feat-005 | status: routed" in out
    assert "classification: architecture | queue_id: feat-006 | status: routed" in out
    assert CLASSIFIER_CALLS == [
        {"timeout": 30, "task_class": "chief_structured_plan"},
        {"timeout": 30, "task_class": "chief_structured_plan"},
    ]
    assert (tmp_path / "03_Inbox.md").read_text(encoding="utf-8") == inbox_before
    assert (tmp_path / "04_Queues.md").read_text(encoding="utf-8") == queues_before


def test_live_run_uses_same_reserved_queue_ids(tmp_path, monkeypatch, capsys):
    CLASSIFIER_CALLS.clear()
    _write_handoff_fixture(tmp_path)
    monkeypatch.setattr(inbox_parser, "ollama_json", _fake_classifier)
    monkeypatch.setattr(sys, "argv", ["inbox_parser.py", "--dir", str(tmp_path)])

    inbox_parser.main()

    out = capsys.readouterr().out
    queues_after = (tmp_path / "04_Queues.md").read_text(encoding="utf-8")
    assert "classification: feature | queue_id: feat-005 | status: routed" in out
    assert "classification: architecture | queue_id: feat-006 | status: routed" in out
    assert CLASSIFIER_CALLS == [
        {"timeout": 30, "task_class": "chief_structured_plan"},
        {"timeout": 30, "task_class": "chief_structured_plan"},
    ]
    assert "| feat-005 | Add calendar summaries | feature | medium" in queues_after
    assert "| feat-006 | Redesign brain routing | architecture | medium" in queues_after
