from types import SimpleNamespace


def _configure_truth_store(monkeypatch, tmp_path, *, seed_text: str | None = None):
    store_path = tmp_path / "operator_truth_store.json"
    seed_path = tmp_path / "OPERATOR-TRUTH-20260619-evening.md"
    if seed_text is not None:
        seed_path.write_text(seed_text, encoding="utf-8")
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(store_path))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(seed_path))
    return store_path, seed_path


def test_maestro_correction_updates_shared_store_and_cassandra_context(monkeypatch, tmp_path):
    _configure_truth_store(monkeypatch, tmp_path)

    from maestro_cassandra_responder import answer_frontdoor_chat
    from operator_truth_store import load_operator_truth_store
    import cassandra_brain

    result = answer_frontdoor_chat(
        "Capital Hilton current truth: $2000 received through Coupa; check July 1, 2026.",
        source_surface="operator_maestro_chat",
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "operator_truth_correction"
    assert result.allowed_to_call_handle is False
    assert result.machine_proof["operator_truth_store_written"] is True

    store = load_operator_truth_store(ensure_seed=False)
    capital = store["entities"]["capital_hilton"]
    assert capital["provenance"] == "operator_corrected"
    assert capital["source_surface"] == "operator_maestro_chat"
    assert capital["pii_tier"] == "LIGHT"
    assert "$2000 received through Coupa" in capital["value"]

    context = cassandra_brain.build_context_snapshot(dict(cassandra_brain._DEFAULT_STATE))
    assert "[OPERATOR-CORRECTED TRUTH - shared across agents]" in context
    assert "Capital Hilton" in context
    assert "$2000 received through Coupa" in context
    assert "operator_maestro_chat" in context


def test_shared_operator_truth_beats_stale_finance_readback(monkeypatch, tmp_path):
    _configure_truth_store(monkeypatch, tmp_path)

    from operator_truth_store import upsert_operator_truth
    import cassandra_brain

    upsert_operator_truth(
        "capital_hilton",
        "$2000 received through Coupa; July 1 check is current.",
        source_surface="operator_maestro_chat",
        source_text="Capital Hilton current truth",
    )
    monkeypatch.setattr(cassandra_brain, "detect_finance_status_intent", lambda _text: True)
    monkeypatch.setattr(
        cassandra_brain,
        "get_finance_status_answer",
        lambda _text: "STALE: Will still needs to get Coupa working on Monday.",
    )

    reply = cassandra_brain._handle_finance_status_request("what is the Capital Hilton status?", {})

    assert "$2000 received through Coupa" in reply
    assert "STALE" not in reply
    assert "Will still needs" not in reply


def test_telegram_listener_intake_captures_operator_truth(monkeypatch, tmp_path):
    _configure_truth_store(monkeypatch, tmp_path)

    import telegram_agent_intake
    from operator_truth_store import load_operator_truth_store

    monkeypatch.setattr(
        telegram_agent_intake,
        "record_telegram_update",
        lambda **_kwargs: SimpleNamespace(update_record_id="update_test_1"),
    )

    update_id = telegram_agent_intake.record_telegram_listener_update_safe(
        text="St Anne's current truth: all paid up.",
        source_channel="chief_listener",
        agent_target="chief",
        source_message_id="msg-1",
    )

    assert update_id == "update_test_1"
    store = load_operator_truth_store(ensure_seed=False)
    st_annes = store["entities"]["st_annes"]
    assert st_annes["source_surface"] == "chief_listener"
    assert st_annes["source_ref"] == "msg-1"
    assert "all paid up" in st_annes["value"].lower()


def test_evening_seed_loads_current_truth_and_next_friday(monkeypatch, tmp_path):
    _configure_truth_store(
        monkeypatch,
        tmp_path,
        seed_text=(
            "# OPERATOR TRUTH - 2026-06-19 evening\n"
            "Capital Hilton: $2000 received, July 1 check, gigs at $400.\n"
            "St Anne's all paid. Live Arts MD owes. next Friday.\n"
        ),
    )

    from operator_truth_store import format_operator_truth_context, load_operator_truth_store

    context = format_operator_truth_context()
    store = load_operator_truth_store(ensure_seed=False)

    assert "Capital Hilton" in context
    assert "$2000 was received through Coupa" in context
    assert "2026-07-01" in context
    assert "2026-06-26" in context
    assert "St Anne's" in context
    assert "All paid up" in context
    assert "Live Arts MD owes" in context
    assert store["entities"]["capital_hilton"]["source_surface"] == "operator_truth_seed"


def test_test_mode_does_not_import_default_runtime_truth_without_explicit_seed(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", str(tmp_path / "isolated_test_truth.json"))
    monkeypatch.delenv("OPENCLAW_OPERATOR_TRUTH_STORE", raising=False)
    monkeypatch.delenv("OPENCLAW_OPERATOR_TRUTH_SEED", raising=False)

    from operator_truth_store import format_operator_truth_context, load_operator_truth_store

    assert format_operator_truth_context("Capital Hilton") == ""
    assert load_operator_truth_store(ensure_seed=False)["entities"] == {}
