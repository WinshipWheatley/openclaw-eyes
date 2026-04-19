from pathlib import Path
import re

import chief_analytics_brain
import chief_album_mixer
import chief_brand_brain
import chief_content_brain
import chief_cpa_brain
import chief_email_brain
import chief_fundo_identity
import chief_goals_brain
import chief_marketing_brain
import chief_momentum_brain
import chief_queue_brain
import chief_reporter_brain
import chief_scout_brain
import chief_sms_brain
import chief_trinity_brain
import chief_website_coordinator
import chief_website_creative
import chief_website_qa


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


def test_reporter_format_uses_chief_evidence_synthesis(monkeypatch):
    calls = []
    stats = {
        "date": "2026-04-18",
        "messages_today": 3,
        "queued_today": 1,
        "queued_total": 4,
        "logged_today": 2,
        "state_updates": 5,
        "listener_errors": False,
        "billing_completions": 0,
        "watcher_alert_count": 1,
        "watcher_alert_samples": ["calendar wait"],
    }

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "Daily report."

    monkeypatch.setattr(chief_reporter_brain, "ollama_call", fake_ollama)
    result = chief_reporter_brain.format_report(stats)
    assert result == "Daily report."
    assert calls == [{
        "prompt": chief_reporter_brain._FORMAT_PROMPT.format(
            date="2026-04-18",
            messages_today=3,
            queued_today=1,
            queued_total=4,
            logged_today=2,
            state_updates=5,
            listener_errors="None",
            billing_completions=0,
            watcher_alert_count=1,
            watcher_alert_samples="calendar wait",
        ),
        "timeout": 30,
        "lane": None,
        "task_class": "chief_evidence_synthesis",
    }]


def test_scout_synthesis_uses_chief_structured_plan_json(monkeypatch):
    calls = []
    findings = [{
        "name": "Local Music Tool",
        "category": "ai-music",
        "summary": "A local music workflow helper.",
        "why_it_matters": "It could help the studio workflow.",
        "status": "ready_now",
        "url": "",
    }]

    def fake_ollama_json(prompt, timeout=0, task_class=None):
        calls.append({"prompt": prompt, "timeout": timeout, "task_class": task_class})
        return findings

    monkeypatch.setattr(chief_scout_brain, "ollama_json", fake_ollama_json)
    result = chief_scout_brain._synthesize([], live_search=False)
    assert result == findings
    assert calls == [{
        "prompt": chief_scout_brain._SYNTHESIS_PROMPT.format(
            stack=chief_scout_brain._STACK_FLAT,
            results="(no live results — use training knowledge)",
            rejected=chief_scout_brain._REJECTED_CONTEXT,
        ),
        "timeout": 60,
        "task_class": "chief_structured_plan",
    }]


def test_website_qa_brand_analysis_uses_chief_evidence_synthesis(monkeypatch):
    calls = []
    page = chief_website_qa.PageResult("https://deeppocketrecords.com")
    page.add("HTTP status", True, "HTTP 200")
    page.add("Meta description", False, "MISSING")

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "BRAND CHECK: good.\nNEXT ACTIONS: fix metadata."

    monkeypatch.setattr(chief_website_qa, "ollama_call", fake_ollama)
    result = chief_website_qa._brand_analysis([page])
    assert "BRAND CHECK" in result
    assert calls == [{
        "prompt": chief_website_qa._BRAND_PROMPT.format(
            page_summaries=(
                "URL: https://deeppocketrecords.com — 1 passed / 1 failed\n"
                "  ✓ HTTP status: HTTP 200\n"
                "  ✗ Meta description: MISSING"
            ),
        ),
        "timeout": 30,
        "lane": None,
        "task_class": "chief_evidence_synthesis",
    }]


def test_album_mixer_brief_uses_chief_structured_plan(monkeypatch):
    calls = []
    row = {
        "completion_pct": "80",
        "status": "in-progress",
        "vocals_pass": "done",
        "drums_pass": "needs polish",
        "completion_blocker": "drums are crowded",
        "vocal_archetype_primary": "warm lead",
        "vocal_archetype_influences": "classic soul",
        "batch_days": "Saturday",
    }

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "Start with the drums."

    monkeypatch.setattr(chief_album_mixer, "ollama_call", fake_ollama)
    result = chief_album_mixer._build_brief("Blue Weather", row)
    assert result == "Start with the drums."
    assert calls == [{
        "prompt": chief_album_mixer._MIX_PROMPT.format(
            title="Blue Weather",
            pct="80",
            status="in-progress",
            passes="Vocals",
            gaps="Drums",
            blocker="drums are crowded",
            vocal="Vocal archetype: warm lead | Influences: classic soul",
            batch_days="Saturday",
        ),
        "timeout": 30,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


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


def test_fundo_identity_default_brief_uses_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "Fundo is a hidden signal in rhythm."

    monkeypatch.setattr(chief_fundo_identity, "_write_identity_md", lambda: None)
    monkeypatch.setattr(chief_fundo_identity, "ollama_call", fake_ollama)

    replies = chief_fundo_identity.handle("fundo brief")

    assert "Fundo is a hidden signal in rhythm." in replies[0]
    assert calls == [{
        "prompt": chief_fundo_identity._BRIEF_PROMPT.format(
            brief=chief_fundo_identity.FUNDO_FULL_BRIEF,
        ),
        "timeout": 30,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


def test_fundo_identity_arc_brief_uses_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "Track 7 is the peak: all rhythmic systems converge."

    monkeypatch.setattr(chief_fundo_identity, "_write_identity_md", lambda: None)
    monkeypatch.setattr(chief_fundo_identity, "ollama_call", fake_ollama)

    replies = chief_fundo_identity.handle("fundo song 7")

    assert replies == ["Track #7 Arc Brief:\n\nTrack 7 is the peak: all rhythmic systems converge."]
    assert calls == [{
        "prompt": chief_fundo_identity._ARC_PROMPT.format(
            brief=chief_fundo_identity.FUNDO_FULL_BRIEF,
            number=7,
        ),
        "timeout": 30,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


def test_fundo_identity_who_is_fundo_uses_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "fundo does not clarify itself."

    monkeypatch.setattr(chief_fundo_identity, "_write_identity_md", lambda: None)
    monkeypatch.setattr(chief_fundo_identity, "ollama_call", fake_ollama)

    replies = chief_fundo_identity.handle("who is fundo")

    assert replies == ["fundo does not clarify itself."]
    assert calls == [{
        "prompt": chief_fundo_identity._WHO_PROMPT.format(
            brief=chief_fundo_identity.FUNDO_FULL_BRIEF,
        ),
        "timeout": 25,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


def test_fundo_identity_visual_direction_uses_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "lane": lane, "task_class": task_class})
        return "CONCEPT: a dark record label half-submerged in water."

    monkeypatch.setattr(chief_fundo_identity, "_write_identity_md", lambda: None)
    monkeypatch.setattr(chief_fundo_identity, "ollama_call", fake_ollama)

    replies = chief_fundo_identity.handle("fundo visual first release teaser")

    assert replies == ["CONCEPT: a dark record label half-submerged in water."]
    assert calls == [{
        "prompt": chief_fundo_identity._VISUAL_PROMPT.format(
            brief=chief_fundo_identity.FUNDO_FULL_BRIEF,
            context="first release teaser",
        ),
        "timeout": 30,
        "lane": None,
        "task_class": "chief_structured_plan",
    }]


def test_marketing_ideas_use_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama_json(prompt, timeout=0, task_class=None):
        calls.append({"prompt": prompt, "timeout": timeout, "task_class": task_class})
        return [{
            "title": "Studio Light",
            "platform": "Instagram",
            "size": "quick_win",
            "song": None,
            "hook": "A quick behind-the-scenes angle.",
            "what_to_make": "Film the studio desk.",
            "tool_note": "Footage needed: studio desk",
        }]

    monkeypatch.setattr(chief_marketing_brain, "_ideas_context", lambda: "context")
    monkeypatch.setattr(chief_marketing_brain, "_add_to_log", lambda entry: None)
    monkeypatch.setattr(chief_marketing_brain, "ollama_json", fake_ollama_json)

    replies = chief_marketing_brain._generate_ideas("marketing ideas")

    assert "Studio Light" in replies[0]
    assert calls == [{
        "prompt": chief_marketing_brain._IDEAS_PROMPT.format(
            context="context",
            request="marketing ideas",
            constraint="",
        ),
        "timeout": 60,
        "task_class": "chief_structured_plan",
    }]


def test_marketing_draft_uses_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "task_class": task_class})
        return "caption draft"

    monkeypatch.setattr(chief_marketing_brain, "ollama_call", fake_ollama)

    replies = chief_marketing_brain._draft_content("draft an Instagram caption")

    assert replies == ["caption draft"]
    assert calls == [{
        "prompt": chief_marketing_brain._DRAFT_PROMPT.format(
            name=chief_marketing_brain.ARTIST_PROFILE["name"],
            artist=chief_marketing_brain.ARTIST_PROFILE["artist"],
            label=chief_marketing_brain.ARTIST_PROFILE["label"],
            genre=chief_marketing_brain.ARTIST_PROFILE["genre"],
            request="draft an Instagram caption",
        ),
        "timeout": 60,
        "task_class": "chief_structured_plan",
    }]


def test_marketing_log_update_parse_uses_chief_structured_plan(monkeypatch):
    calls = []
    saved = {}

    def fake_ollama_json(prompt, timeout=0, task_class=None):
        calls.append({"prompt": prompt, "timeout": timeout, "task_class": task_class})
        return {"action": "status_update", "title": "Studio Light", "status": "posted"}

    monkeypatch.setattr(chief_marketing_brain, "ollama_json", fake_ollama_json)
    monkeypatch.setattr(chief_marketing_brain, "_load_content_log", lambda: {
        "entries": [{"title": "Studio Light", "status": "suggested"}],
    })
    monkeypatch.setattr(chief_marketing_brain, "_save_content_log", lambda data: saved.setdefault("data", data))
    monkeypatch.setattr(chief_marketing_brain, "_write_content_log_md", lambda data: None)

    replies = chief_marketing_brain._update_log("mark Studio Light as posted")

    assert "Updated" in replies[0]
    assert saved["data"]["entries"][0]["status"] == "posted"
    assert calls == [{
        "prompt": chief_marketing_brain._LOG_UPDATE_PROMPT.format(text="mark Studio Light as posted"),
        "timeout": 15,
        "task_class": "chief_structured_plan",
    }]


def test_fundo_marketing_paths_use_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama_json(prompt, timeout=0, task_class=None):
        calls.append({"kind": "json", "timeout": timeout, "task_class": task_class})
        return [{
            "title": "black label",
            "platform": "TikTok",
            "size": "quick_win",
            "hook": "something moves in the grooves",
            "what_to_make": "macro shot of vinyl texture",
            "tool_note": "phone macro",
        }]

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"kind": "text", "timeout": timeout, "task_class": task_class})
        return "fundo caption"

    monkeypatch.setattr(chief_marketing_brain, "_get_fundo_ctx", lambda: "fundo context")
    monkeypatch.setattr(chief_marketing_brain, "_load_fundo_content_log", lambda: {"entries": []})
    monkeypatch.setattr(chief_marketing_brain, "_save_fundo_content_log", lambda data: None)
    monkeypatch.setattr(chief_marketing_brain, "ollama_json", fake_ollama_json)
    monkeypatch.setattr(chief_marketing_brain, "ollama_call", fake_ollama)

    ideas = chief_marketing_brain._fundo_ideas("fundo content idea")
    draft = chief_marketing_brain._fundo_draft("fundo caption for TikTok")

    assert "black label" in ideas[0]
    assert draft == ["fundo caption"]
    assert calls == [
        {"kind": "json", "timeout": 45, "task_class": "chief_structured_plan"},
        {"kind": "text", "timeout": 40, "task_class": "chief_structured_plan"},
    ]


def test_website_creative_paths_use_chief_structured_plan(monkeypatch):
    calls = []

    def fake_ollama(prompt, timeout=0, lane=None, task_class=None, model=None):
        calls.append({"timeout": timeout, "task_class": task_class})
        return "creative output"

    monkeypatch.setattr(chief_website_creative, "_log_entry", lambda *args, **kwargs: None)
    monkeypatch.setattr(chief_website_creative, "ollama_call", fake_ollama)

    assert chief_website_creative._generate_headlines("headline hero")[0].endswith("creative output")
    assert chief_website_creative._generate_bio("bio short fundo")[0].endswith("creative output")
    assert chief_website_creative._generate_song_description("song description Blue Weather")[0].endswith("creative output")
    assert chief_website_creative._generate_fundo_mystery("fundo mystery text")[0].endswith("creative output")
    assert chief_website_creative._generate_svg_logo("logo minimal")[0].startswith("Logo concept")
    assert chief_website_creative._generate_canva_brief("canva brief hero")[0].endswith("creative output")
    assert chief_website_creative._generate_general_copy("website copy about")[0].endswith("creative output")
    assert calls == [
        {"timeout": 30, "task_class": "chief_structured_plan"},
        {"timeout": 40, "task_class": "chief_structured_plan"},
        {"timeout": 30, "task_class": "chief_structured_plan"},
        {"timeout": 30, "task_class": "chief_structured_plan"},
        {"timeout": 40, "task_class": "chief_structured_plan"},
        {"timeout": 30, "task_class": "chief_structured_plan"},
        {"timeout": 40, "task_class": "chief_structured_plan"},
    ]


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
