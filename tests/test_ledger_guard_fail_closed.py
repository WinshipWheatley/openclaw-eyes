"""The runtime ledger guard must fail CLOSED, not open.

Review finding (2026-07-01): a guard exception (e.g. sqlite lock while a cron
fold writes the live ledger) was swallowed and the live answer was generated
from the original, unverified packet with only a buried receipt field. Doctrine
(Operator/ONE-KNOWLEDGE-LEDGER-DOCTRINE.md layer 2) requires failing HONEST.
Also: the all-or-nothing repair discarded topically relevant grounded facts
whenever one fact lacked provenance.
"""

import sqlite3
from pathlib import Path


def _make_empty_ledger(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.close()
    return path


def test_guard_exception_fails_closed_to_grounded_fallback(monkeypatch, tmp_path: Path) -> None:
    import context_source
    import protected_generate

    def exploding_guard(packet, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(context_source, "ensure_packet_ledger_grounded", exploding_guard)

    captured: dict[str, str] = {}

    def fake_generator(prompt, **_kwargs):
        captured["prompt"] = prompt
        return "A live model answer that must NOT be delivered."

    packet = {
        "schema_version": "maestro_context_packet_v0",
        "packet_id": "maestro_context_packet:locked",
        "facts": [
            {
                "fact_id": "unverified_fact",
                "label": "Unverified fact",
                "value": "Could not be checked against the ledger.",
                "source_ref": "somewhere#unverified",
            }
        ],
        "source_refs": ["somewhere#unverified"],
    }

    outcome = protected_generate.protected_generate_with_receipt(
        "what is the status?",
        context_packet=packet,
        generator_fn=fake_generator,
        front_door_profile=True,
        allow_live_model=False,
        agent="maestro",
    )

    receipt = outcome.receipt
    assert receipt["ledger_runtime_guard"]["status"] == "ledger_runtime_guard_error"
    assert receipt["model_output_delivered"] is False
    assert receipt["delivered_response_source"] == "grounded_fallback"
    assert receipt["model_fallback_reason"] == "ledger_guard_error"
    # Fail-closed short-circuit: the generator/model is never invoked on an
    # unverified packet — no answer is produced from ungrounded facts.
    assert captured == {}
    assert "must NOT be delivered" not in str(outcome.text or "")


def test_locked_ledger_returns_honest_unavailable_fact(monkeypatch, tmp_path: Path) -> None:
    import context_source

    db_path = _make_empty_ledger(tmp_path / "ledger.sqlite")

    def exploding_append(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(context_source, "_append_canonical_facts", exploding_append)

    facts = context_source.build_ledger_context_facts(
        question="status?", agent_id="maestro", db_path=db_path
    )

    assert len(facts) == 1
    assert facts[0]["label"] == "Ledger unavailable"


def test_partial_repair_keeps_grounded_facts(tmp_path: Path) -> None:
    from context_source import ensure_packet_ledger_grounded, make_ledger_fact

    db_path = _make_empty_ledger(tmp_path / "ledger.sqlite")
    grounded = make_ledger_fact(
        topic="agent_lane",
        label="Niles owns the music lane",
        value="Relevant grounded fact that must survive the repair.",
        source_table="agent_lanes",
        source_id="niles_lane",
        db_path=db_path,
    )
    ungrounded = {
        "fact_id": "sidecar_fact",
        "label": "Wrong-source fact",
        "value": "No ledger provenance.",
        "source_ref": "system_catalog.sqlite3#facts:sidecar_fact",
    }
    packet = {
        "schema_version": "maestro_context_packet_v0",
        "packet_id": "maestro_context_packet:mixed",
        "facts": [grounded, ungrounded],
        "source_refs": [grounded["source_ref"], ungrounded["source_ref"]],
    }

    repaired = ensure_packet_ledger_grounded(
        packet, builder_name="test.partial", question="who owns music?", db_path=db_path
    )

    labels = [fact["label"] for fact in repaired["facts"]]
    assert "Niles owns the music lane" in labels
    assert "Wrong-source fact" not in labels
    guard = repaired["runtime_ledger_guard"]
    assert guard["status"] == "ledger_runtime_partial_repair"
    assert "sidecar_fact" in guard.get("dropped_fact_ids", [])
