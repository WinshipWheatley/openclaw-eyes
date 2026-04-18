from pathlib import Path
import re

import chief_analytics_brain
import chief_email_brain
import chief_goals_brain
import chief_momentum_brain
import chief_sms_brain
import chief_trinity_brain


def test_analytics_narrative_uses_local_ollama(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane})
        return "analytics summary"

    monkeypatch.setattr(chief_analytics_brain, "ollama_call", fake_ollama)
    result = chief_analytics_brain._build_narrative("report body")
    assert result == "analytics summary"
    assert calls == [{"prompt": chief_analytics_brain._NARRATIVE_PROMPT.format(report="report body"), "timeout": 30, "lane": "strong"}]


def test_trinity_narrative_uses_local_ollama(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane})
        return "trinity summary"

    monkeypatch.setattr(chief_trinity_brain, "ollama_call", fake_ollama)
    result = chief_trinity_brain._build_narrative("audit body")
    assert result == "trinity summary"
    assert calls == [{"prompt": chief_trinity_brain._NARRATIVE_PROMPT.format(report="audit body"), "timeout": 30, "lane": "strong"}]


def test_goals_checkin_uses_local_ollama(monkeypatch):
    calls = []
    goals = [{"id": 1, "title": "Release the album", "completion": 40, "target_date": "2026-12-31"}]

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane})
        return "goals checkin"

    monkeypatch.setattr(chief_goals_brain, "ollama_call", fake_ollama)
    result = chief_goals_brain._get_checkin(goals)
    assert result == "goals checkin"
    assert calls == [{"prompt": chief_goals_brain._CHECKIN_PROMPT.format(goals_text=chief_goals_brain._build_goals_text(goals)), "timeout": 30, "lane": "strong"}]


def test_momentum_narrative_uses_local_ollama(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane})
        return "momentum summary"

    monkeypatch.setattr(chief_momentum_brain, "ollama_call", fake_ollama)
    result = chief_momentum_brain._build_narrative("momentum body")
    assert result == "momentum summary"
    assert calls == [{"prompt": chief_momentum_brain._NARRATIVE_PROMPT.format(report="momentum body"), "timeout": 30, "lane": "strong"}]


def test_email_parse_uses_local_ollama_json(monkeypatch):
    calls = []

    def fake_ollama_json(prompt, timeout=0):
        calls.append({"prompt": prompt, "timeout": timeout})
        return {
            "to_name": "Ada",
            "to_email": "ada@example.com",
            "topic": "contract update",
            "context": "INV-123",
            "email_type": "contract",
        }

    monkeypatch.setattr(chief_email_brain, "ollama_json", fake_ollama_json)
    parsed = chief_email_brain._parse_email_request("email Ada about the contract update")
    assert parsed == {
        "to_name": "Ada",
        "to_email": "ada@example.com",
        "topic": "contract update",
        "context": "INV-123",
        "email_type": "contract",
    }
    assert calls == [{"prompt": chief_email_brain._PARSE_PROMPT.format(text="email Ada about the contract update"), "timeout": 20}]


def test_email_draft_uses_local_strong_ollama(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane})
        return "Subject: Contract update\n\nHi Ada,\n\nQuick update.\n\nBest,\nWinship\nDeep Pocket Records"

    monkeypatch.setattr(chief_email_brain, "ollama_call", fake_ollama)
    subject, body = chief_email_brain._draft_email("Ada", "contract update", "INV-123", "contract")
    assert subject == "Contract update"
    assert "Hi Ada" in body
    assert calls == [{
        "prompt": chief_email_brain._DRAFT_PROMPT.format(
            to_name="Ada",
            topic="contract update",
            context="INV-123",
            email_type="contract",
        ),
        "timeout": 30,
        "lane": "strong",
    }]


def test_sms_parse_uses_local_ollama_json(monkeypatch):
    calls = []

    def fake_ollama_json(prompt, timeout=0):
        calls.append({"prompt": prompt, "timeout": timeout})
        return {
            "to_name": "Ada",
            "to_number": "+12025551234",
            "topic": "invoice follow-up",
            "context": "INV-123",
        }

    monkeypatch.setattr(chief_sms_brain, "ollama_json", fake_ollama_json)
    parsed = chief_sms_brain._parse_sms_request("text Ada about invoice follow-up")
    assert parsed == {
        "to_name": "Ada",
        "to_number": "+12025551234",
        "topic": "invoice follow-up",
        "context": "INV-123",
    }
    assert calls == [{"prompt": chief_sms_brain._PARSE_PROMPT.format(text="text Ada about invoice follow-up"), "timeout": 20}]


def test_sms_draft_uses_local_strong_ollama(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane})
        return "Hi Ada, following up on INV-123. Can you confirm receipt today?"

    monkeypatch.setattr(chief_sms_brain, "ollama_call", fake_ollama)
    body = chief_sms_brain._draft_sms("Ada", "invoice follow-up", "INV-123")
    assert body == "Hi Ada, following up on INV-123. Can you confirm receipt today?"
    assert calls == [{
        "prompt": chief_sms_brain._DRAFT_PROMPT.format(
            to_name="Ada",
            topic="invoice follow-up",
            context="INV-123",
        ),
        "timeout": 20,
        "lane": "strong",
    }]


def test_no_new_direct_chief_claude_calls_outside_allowlist():
    root = Path("/home/openclaw")
    allowed = {
        "chief_llm.py",
        "chief_cpa_brain.py",
        "chief_website_coordinator.py",
    }
    offenders = []
    pattern = re.compile(r"\bclaude_(?:call|json)\s*\(")
    for path in sorted(root.glob("chief_*.py")):
        text = path.read_text(encoding="utf-8")
        if pattern.search(text) and path.name not in allowed:
            offenders.append(path.name)
    assert offenders == []
