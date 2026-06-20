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
import chief_ops_reporter as ops
import morning_brief_harness


def test_classify_separates_pending_and_completed():
    lines = [
        "- Follow up with distributor about payment",
        "- [DONE] Update release date in calendar",
        "- Urgent: review mixing notes from yesterday",
        "- ✓ Send invoice to label",
        "- Check in with photographer next week",
    ]
    pending, completed = ops.classify_ops_actions(lines)
    assert len(pending) == 3
    assert len(completed) == 2


def test_counts_match_source_records():
    lines = [
        "- Task A",
        "- [done] Task B",
        "- Task C [x]",
        "- Task D",
    ]
    pending, completed = ops.classify_ops_actions(lines)
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
    pending, completed = ops.classify_ops_actions(lines)
    assert len(completed) == 7
    assert len(pending) == 0


def test_priority_items_appear_first_in_pending():
    lines = [
        "- Regular follow-up item",
        "- Another routine task",
        "- URGENT: call back manager",
        "- ASAP review contract",
    ]
    pending, completed = ops.classify_ops_actions(lines)
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
    pending, _ = ops.classify_ops_actions(priority_lines)
    assert len(pending) == 6
    # All should sort to the front (no non-priority items to displace them)
    for item in pending:
        assert ops._PRIORITY_RE.search(item)


def test_build_action_summary_contains_distinct_sections(tmp_path, monkeypatch):
    ops_path = tmp_path / "Ops Actions.md"
    ops_path.write_text(
        "# Ops Actions\n\n"
        "- Follow up with distributor\n"
        "- [DONE] Update calendar\n"
        "- URGENT: review mixing notes\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ops, "_OPS_ACTIONS", ops_path)

    summary = ops.build_action_summary()

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
    monkeypatch.setattr(ops, "_OPS_ACTIONS", ops_path)

    summary = ops.build_action_summary()

    assert "Pending (2)" in summary
    assert "Completed (2)" in summary


def test_build_action_summary_marks_priority_items(tmp_path, monkeypatch):
    ops_path = tmp_path / "Ops Actions.md"
    ops_path.write_text(
        "- routine task\n"
        "- URGENT: call manager\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ops, "_OPS_ACTIONS", ops_path)

    summary = ops.build_action_summary()

    assert "[PRIORITY]" in summary


def test_build_action_summary_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "_OPS_ACTIONS", tmp_path / "nonexistent.md")

    summary = ops.build_action_summary()

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
    monkeypatch.setattr(ops, "_OPS_ACTIONS", ops_path)
    monkeypatch.setattr(ops, "_OPS_ACTIONS_CONTEXT", artifact_path)

    artifact = ops.write_ops_actions_artifact(n_actions=2)
    content = artifact_path.read_text(encoding="utf-8")

    assert artifact["path"] == str(artifact_path)
    assert "type: ops-actions-context" in content
    assert "source_module: chief_ops_reporter.py" in content
    assert f"source_path: {ops_path}" in content
    assert "freshness:" in content
    assert "bounded_to_last_actions: 2" in content
    assert "Bound: last 2 non-heading action lines" in content
    assert "Pending (1)" in content
    assert "Completed (1)" in content
    assert "routine task" not in content


def test_ops_actions_artifact_missing_source_records_staleness_note(tmp_path, monkeypatch):
    artifact_path = tmp_path / "Ops Actions Context.md"
    monkeypatch.setattr(ops, "_OPS_ACTIONS", tmp_path / "missing.md")
    monkeypatch.setattr(ops, "_OPS_ACTIONS_CONTEXT", artifact_path)

    ops.write_ops_actions_artifact()
    content = artifact_path.read_text(encoding="utf-8")

    assert "missing: source file not found" in content
    assert "Pending (0)" in content
    assert "Completed (0)" in content


def test_morning_synthesis_missing_artifact_returns_safe_fallback(tmp_path, monkeypatch):
    import chief_morning_orchestrator

    synthesis = tmp_path / "Chief Morning Synthesis.md"
    cache = tmp_path / "morning_reference_cache.json"
    monkeypatch.setattr(bb, "_CHIEF_MORNING_SYNTHESIS", synthesis)
    monkeypatch.setattr(bb, "_MORNING_REFERENCE_CACHE", cache)
    monkeypatch.setattr(chief_morning_orchestrator, "refresh_morning_artifacts", lambda: False)
    monkeypatch.setattr(
        bb,
        "ollama_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("missing synthesis should not call LLM")),
    )

    text = bb.generate_briefing("morning")

    assert "Chief Morning Synthesis is missing or stale" in text
    assert cache.exists()


def test_split_briefing_messages_chunks_dense_morning_text():
    entry = {
        "slot": "morning",
        "date": "2026-04-19",
        "text": "Para one " * 80 + "\n\n" + "Para two " * 80,
    }

    messages = bb.split_briefing_messages(entry, max_chars=320)

    assert len(messages) > 1
    assert messages[0].startswith("[Morning")
    assert "Part 1/" in messages[0]
    assert all(len(message) <= 420 for message in messages)


def test_morning_voice_text_uses_compressed_cache_summary(tmp_path, monkeypatch):
    cache = tmp_path / "morning_reference_cache.json"
    monkeypatch.setattr(bb, "_MORNING_REFERENCE_CACHE", cache)
    bb.save_json(
        cache,
        {
            "spoken_summary": "Short spoken version.",
            "delivery_text": "Long text that should not be spoken.",
        },
    )

    voice = bb.briefing_voice_text({"slot": "morning", "text": "Full raw delivery " * 100})

    assert voice == "Short spoken version."


def test_briefing_prompt_pins_cassandra_self_and_operator_perspective():
    prompt = bb._build_briefing_prompt(
        "morning",
        "Cassandra notes that Winship needs the short status.",
        "Generate a morning briefing.",
        "cassandra_morning_brief",
    )

    assert "You are Cassandra" in prompt
    assert "refer only to Cassandra" in prompt
    assert "The human operator is Winship" in prompt
    assert 'do not use "I", "me", or "my" for the operator' in prompt


def test_morning_reference_cache_preserves_sections(tmp_path, monkeypatch):
    synthesis = tmp_path / "Chief Morning Synthesis.md"
    cache = tmp_path / "morning_reference_cache.json"
    synthesis.write_text(
        "# Chief Morning Synthesis\n\n"
        "## Top Priorities\n\n"
        "- First priority\n\n"
        "## Blockers / Watchlist\n\n"
        "- One blocker\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bb, "_CHIEF_MORNING_SYNTHESIS", synthesis)
    monkeypatch.setattr(bb, "_MORNING_REFERENCE_CACHE", cache)
    monkeypatch.setattr(bb, "_morning_task_config", lambda: ("cassandra_morning_brief", "llm"))
    monkeypatch.setattr(bb, "ollama_json", lambda *args, **kwargs: [{"header": "TEST", "body": "Brief morning delivery."}])

    bb.generate_briefing("morning")
    saved = bb.load_morning_reference_cache()

    assert saved["available"] is True
    assert saved["source_artifact"] == str(synthesis)
    assert "Top Priorities" in saved["sections"]
    assert "Brief morning delivery." in saved["spoken_summary"]


def test_non_morning_brief_uses_qwen_fallback_before_deterministic(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(bb, "build_context_snapshot", lambda: "Bounded current context.")
    monkeypatch.setattr(
        bb,
        "resolve_local_model",
        lambda prompt, task_class=None: ("gemma4:e4b", "strong"),
    )

    def fake_ollama_call(prompt, timeout=0, model=None, task_class=None, attempts=None, **kwargs):
        calls.append({
            "model": model,
            "timeout": timeout,
            "task_class": task_class,
        })
        if model == bb._NON_MORNING_BRIEF_FALLBACK_MODEL:
            return "Safe qwen fallback briefing."
        return ""

    monkeypatch.setattr(bb, "ollama_call", fake_ollama_call)

    text = bb.generate_briefing("afternoon")

    assert text == "Safe qwen fallback briefing."
    assert calls[0] == {
        "model": "gemma4:e4b",
        "timeout": 180,
        "task_class": "cassandra_user_reply",
    }
    assert calls[1]["model"] == "qwen3:8b-q4_K_M"
    assert 1 <= calls[1]["timeout"] <= 300
    assert calls[1]["task_class"] == "cassandra_user_reply"


def test_non_morning_brief_uses_deterministic_fallback_after_llm_failures(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(bb, "build_context_snapshot", lambda: "Bounded current context.")
    monkeypatch.setattr(
        bb,
        "resolve_local_model",
        lambda prompt, task_class=None: ("gemma4:e4b", "strong"),
    )
    monkeypatch.setattr(
        bb,
        "build_action_summary",
        lambda: "Pending (1):\n  [PRIORITY] finish the active lane\nCompleted (0):\n  (none)",
    )

    def fake_ollama_call(prompt, timeout=0, model=None, task_class=None, **kwargs):
        calls.append(model)
        return ""

    monkeypatch.setattr(bb, "ollama_call", fake_ollama_call)

    text = bb.generate_briefing("evening")

    assert calls == ["gemma4:e4b", "qwen3:8b-q4_K_M"]
    assert "evening fallback" in text
    assert "finish the active lane" in text
    assert "LLM did not respond" not in text


def test_generate_morning_brief_uses_generous_delivery_timeout(monkeypatch, tmp_path):
    synthesis = tmp_path / "Chief Morning Synthesis.md"
    cache = tmp_path / "morning_reference_cache.json"
    synthesis.write_text(
        "# Chief Morning Synthesis\n\n"
        "## Top Priorities\n\n"
        "- Keep the morning lane alive.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bb, "_CHIEF_MORNING_SYNTHESIS", synthesis)
    monkeypatch.setattr(bb, "_MORNING_REFERENCE_CACHE", cache)
    monkeypatch.setattr(bb, "_MORNING_DELIVERY_TIMEOUT_SECONDS", 420)
    monkeypatch.setattr(bb, "_morning_task_config", lambda: ("cassandra_morning_brief", "llm"))

    calls: list[dict] = []

    def fake_ollama_json(prompt, timeout=0, task_class=None):
        calls.append({"timeout": timeout, "task_class": task_class})
        return [{"header": "Priorities", "body": "Morning delivery."}]

    monkeypatch.setattr(bb, "ollama_json", fake_ollama_json)

    text = bb.generate_briefing("morning")

    assert "Morning delivery." in text
    assert calls == [{"timeout": 420, "task_class": "cassandra_morning_brief"}]


def test_scheduler_delivery_uses_chunks_and_compressed_voice(monkeypatch):
    import cassandra_briefing_scheduler as scheduler

    sent: list[str] = []
    spoken: list[str] = []
    marked: list[tuple[str, str]] = []

    monkeypatch.setattr(scheduler, "split_briefing_messages", lambda entry: ["chunk one", "chunk two"])
    monkeypatch.setattr(scheduler, "briefing_voice_text", lambda entry: "compressed spoken summary")
    monkeypatch.setattr(scheduler, "briefing_delivery_blocked", lambda: False)
    monkeypatch.setattr(scheduler, "send_operator_brief", lambda text: sent.append(text))
    monkeypatch.setattr(scheduler, "speak_and_send_operator_brief_voice", lambda text: spoken.append(text))
    monkeypatch.setattr(scheduler, "mark_delivered", lambda date, slot: marked.append((date, slot)))

    scheduler._deliver({"slot": "afternoon", "date": "2026-04-19", "text": "full text"})

    assert sent == ["chunk one", "chunk two"]
    assert spoken == ["compressed spoken summary"]
    assert marked == [("2026-04-19", "afternoon")]


def test_fallback_morning_delivery_is_clean_not_artifact_shaped():
    reference = {
        "freshness": "fresh: source last changed 2026-04-19T10:38:51",
        "sections": {
            "Top Priorities": [
                "- Nightly Polish Log: The Gate: no actions currently waiting for approval click.",
                "- Nightly Polish Log: Queue: 1 tasks ready for execution.",
                "- Ops Actions Context: - Source: `/mnt/c/OpenClawShared/openclaw-vault/System/Ops Actions.md`",
                "- Ops Actions Context: - [OPEN] St. Anne's / misc tech: reconcile payer and billing path.",
            ],
            "Blockers / Watchlist": [
                "- System Health Report: Errors detected - check listener.out",
                "- Website QA Log: STATUS: OFFLINE",
            ],
            "Confidence / What May Be Stale": [
                "- Ops Calendar Notes: stale: source last changed 2026-04-05T13:40:39",
            ],
        },
    }

    text = bb._fallback_morning_delivery(reference)

    assert "The approval gate is clear" in text
    assert "Top open item:" in text
    assert "listener errors are logged" in text
    assert "Ops Actions Context:" not in text
    assert "Source:" not in text
    assert "/mnt/c/" not in text


def test_compact_morning_test_context_uses_parsed_sections_only():
    reference = {
        "freshness": "fresh: source last changed 2026-04-19T10:38:51",
        "sections": {
            "Top Priorities": [
                "- Nightly Polish Log: The Gate: no actions currently waiting for approval click.",
                "- Nightly Polish Log: Queue: 1 tasks ready for execution.",
                "- Ops Actions Context: - Source: `/mnt/c/OpenClawShared/openclaw-vault/System/Ops Actions.md`",
                "- Ops Actions Context: - [OPEN] St. Anne's / misc tech: reconcile payer and billing path.",
            ],
            "Blockers / Watchlist": [
                "- System Health Report: Errors detected - check listener.out",
                "- Website QA Log: STATUS: OFFLINE",
            ],
            "System / Ops State": [
                "- System Health Report: Workers",
                "- System Health Report: 0 messages queued today",
            ],
            "Confidence / What May Be Stale": [
                "- Ops Calendar Notes: stale: source last changed 2026-04-05T13:40:39",
            ],
        },
    }

    context = bb._compact_morning_test_context(reference)

    assert "COMPACT TEST CONTEXT" in context
    assert "The approval gate is clear" in context
    assert "listener errors are logged" in context
    assert "calendar notes may be stale" in context
    assert "/mnt/c/" not in context
    assert len(context.split()) < 120


def test_morning_harness_recorded_replay_writes_machine_readable_manifest(tmp_path, monkeypatch):
    roots = morning_brief_harness.HarnessRoots(
        root=tmp_path / "morning_brief_harness",
        fixtures=tmp_path / "morning_brief_harness" / "fixtures",
        runs=tmp_path / "morning_brief_harness" / "runs",
    )
    roots.fixtures.mkdir(parents=True)
    fixture = roots.fixtures / "sample_morning.json"
    fixture.write_text(
        bb.json.dumps(
            {
                "fixture_name": "sample_morning",
                "reference_time": "2026-04-30T05:00:00",
                "inputs": {
                    "context": "canonical context",
                    "morning_context": "morning context",
                    "action_summary": "Pending (0):\n  (none)",
                },
            }
        ),
        encoding="utf-8",
    )
    recorded_dir = tmp_path / "recorded_morning"
    recorded_dir.mkdir()
    recorded_stages = [
        {"name": "guardian", "lane": "fast", "text": "Guardian gate clear.", "duration_ms": 1},
        {"name": "chief", "lane": "deep", "text": "Chief synthesis ready.", "duration_ms": 1},
        {"name": "cassandra", "lane": "fast", "text": "Cassandra brief ready.", "duration_ms": 1},
    ]
    (recorded_dir / "recorded_stage_outputs.json").write_text(bb.json.dumps(recorded_stages), encoding="utf-8")
    (recorded_dir / "manifest.json").write_text(bb.json.dumps({"stages": recorded_stages}), encoding="utf-8")
    monkeypatch.setattr(
        morning_brief_harness.briefing,
        "ollama_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("recorded replay must not call a model")),
    )

    run_dir = morning_brief_harness.run_replay(fixture, roots, recorded_from=recorded_dir)

    manifest = bb.json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["harness_name"] == "morning_brief_harness"
    assert manifest["task_name"] == "morning_brief"
    assert manifest["flow"] == "morning_brief"
    assert manifest["inference_mode"] == "recorded"
    assert manifest["generated_at"]
    assert manifest["passed"] == manifest["total_cases"]
    assert manifest["failed"] == 0
    assert {check["name"] for check in manifest["checks"]} >= {
        "fixture_has_inputs",
        "brief_text_present",
        "generation_path_present",
        "stages_present",
        "stage_names_present",
        "staging_only",
    }
