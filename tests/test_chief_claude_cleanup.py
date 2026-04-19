from pathlib import Path
import re

import chief_analytics_brain
import chief_brand_brain
import chief_content_brain
import chief_cpa_brain
import chief_email_brain
import chief_goals_brain
import chief_momentum_brain
import chief_queue_brain
import chief_sms_brain
import chief_trinity_brain
import chief_website_coordinator


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
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "trinity summary"

    monkeypatch.setattr(chief_trinity_brain, "ollama_call", fake_ollama)
    result = chief_trinity_brain._build_narrative("audit body")
    assert result == "trinity summary"
    assert calls == [{
        "prompt": chief_trinity_brain._NARRATIVE_PROMPT.format(report="audit body"),
        "timeout": 30,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


def test_queue_clean_item_uses_chief_agentic_code(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "Fix calendar delete routing"

    monkeypatch.setattr(chief_queue_brain, "ollama_call", fake_ollama)
    result = chief_queue_brain._clean_item("queue request: fix calendar delete routing")
    assert result == "Fix calendar delete routing"
    assert calls == [{
        "prompt": chief_queue_brain._CLEAN_PROMPT.format(text="fix calendar delete routing"),
        "timeout": 15,
        "lane": None,
        "task_class": "chief_agentic_code",
    }]


def test_goals_checkin_uses_local_ollama(monkeypatch):
    calls = []
    goals = [{"id": 1, "title": "Release the album", "completion": 40, "target_date": "2026-12-31"}]

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "goals checkin"

    monkeypatch.setattr(chief_goals_brain, "ollama_call", fake_ollama)
    result = chief_goals_brain._get_checkin(goals)
    assert result == "goals checkin"
    assert calls == [{
        "prompt": chief_goals_brain._CHECKIN_PROMPT.format(
            goals_text=chief_goals_brain._build_goals_text(goals)
        ),
        "timeout": 30,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


def test_content_recommendation_uses_chief_structured_plan(monkeypatch):
    calls = []
    queue = [{"platform": "Instagram", "title": "studio clip", "size": "short"}]
    overdue = ["TikTok (0/3 this week)"]

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "Post the studio clip first."

    monkeypatch.setattr(chief_content_brain, "ollama_call", fake_ollama)
    result = chief_content_brain._get_recommendation(queue, overdue)
    assert result == "Post the studio clip first."
    assert calls == [{
        "prompt": chief_content_brain._RECOMMENDATION_PROMPT.format(
            queue_items="- [Instagram] studio clip (short)",
            overdue="- TikTok (0/3 this week)",
        ),
        "timeout": 20,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


def test_brand_check_uses_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "On-brand: warm and specific."

    monkeypatch.setattr(chief_brand_brain, "ollama_call", fake_ollama)
    result = chief_brand_brain._check_on_brand("A warm studio story.", chief_brand_brain.DPR_BRAND)
    assert result == "On-brand: warm and specific."
    assert calls == [{
        "prompt": chief_brand_brain._BRAND_CHECK_PROMPT.format(
            brand_name=chief_brand_brain.DPR_BRAND["name"],
            tone="; ".join(chief_brand_brain.DPR_BRAND["tone"][:3]),
            on_brand="; ".join(chief_brand_brain.DPR_BRAND["on_brand"][:4]),
            off_brand="; ".join(chief_brand_brain.DPR_BRAND["off_brand"][:4]),
            content="A warm studio story.",
        ),
        "timeout": 20,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


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


def test_cpa_tax_reply_uses_local_ollama(monkeypatch):
    calls = []
    estimate = {
        "ytd_income": 10000.0,
        "ytd_expenses": 3000.0,
        "net_income": 7000.0,
        "se_tax": 989.0,
        "income_tax": 1540.0,
        "total_annual": 2529.0,
        "per_quarter": 632.25,
        "next_deadline_label": "Q2 2026",
        "next_deadline_date": "2026-06-16",
    }

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout})
        return "Estimated quarterly tax is about $632.25. Confirm with a CPA."

    monkeypatch.setattr(chief_cpa_brain, "ollama_call", fake_ollama)
    result = chief_cpa_brain._format_tax_reply(estimate)
    assert result == "Estimated quarterly tax is about $632.25. Confirm with a CPA."
    assert calls == [{"prompt": chief_cpa_brain._TAX_PROMPT.format(**estimate), "timeout": 30}]


def test_website_update_parse_uses_local_ollama_json(monkeypatch):
    calls = []
    state = {
        "sections": {"homepage": {"status": "not_started", "updated": ""}},
        "updates": [],
    }

    def fake_ollama_json(prompt, timeout=0):
        calls.append({"prompt": prompt, "timeout": timeout})
        return {"section_id": "homepage", "status": "done", "note": "hero is live"}

    monkeypatch.setattr(chief_website_coordinator, "ollama_json", fake_ollama_json)
    monkeypatch.setattr(chief_website_coordinator, "_save_state", lambda data: None)
    monkeypatch.setattr(chief_website_coordinator, "_write_coordinator_md", lambda data: None)

    replies = chief_website_coordinator._handle_update("website update homepage done", state)

    assert state["sections"]["homepage"]["status"] == "done"
    assert state["updates"][-1]["section"] == "homepage"
    assert "Updated: Homepage Hero -> DONE" in replies[0].replace("→", "->")
    section_ids = ", ".join(s["id"] for s in chief_website_coordinator.SITE_SECTIONS)
    assert calls == [{
        "prompt": chief_website_coordinator._UPDATE_PARSE_PROMPT.format(
            section_ids=section_ids,
            text="website update homepage done",
        ),
        "timeout": 20,
    }]


def test_no_new_direct_chief_claude_calls_outside_allowlist():
    root = Path("/home/openclaw")
    allowed = {
        "chief_llm.py",
    }
    offenders = []
    pattern = re.compile(r"\bclaude_(?:call|json)\s*\(")
    for path in sorted(root.glob("chief_*.py")):
        text = path.read_text(encoding="utf-8")
        if pattern.search(text) and path.name not in allowed:
            offenders.append(path.name)
    assert offenders == []
