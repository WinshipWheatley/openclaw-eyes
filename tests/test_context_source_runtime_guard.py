from __future__ import annotations

import json
from pathlib import Path


def test_runtime_guard_repairs_unprovenanced_packet_and_logs_drift(tmp_path: Path) -> None:
    from context_source import ensure_packet_ledger_grounded, facts_have_ledger_provenance

    drift_log = tmp_path / "ledger_drift.jsonl"
    packet = {
        "packet_id": "bad_packet",
        "agent_id": "cassandra",
        "question": "where does this live?",
        "facts": [
            {
                "fact_id": "sidecar_fact",
                "label": "Wrong-source fact",
                "value": "This came from system_catalog.sqlite3, not the ledger.",
                "source_ref": "system_catalog.sqlite3#facts:sidecar_fact",
            }
        ],
        "source_refs": ["system_catalog.sqlite3#facts:sidecar_fact"],
        "machine_proof": {"original": True},
    }

    repaired = ensure_packet_ledger_grounded(
        packet,
        builder_name="test_bad_builder",
        question="where does this live?",
        agent_id="cassandra",
        db_path=tmp_path / "missing-ledger.sqlite",
        drift_log_path=drift_log,
    )

    assert repaired["facts"]
    assert facts_have_ledger_provenance(repaired["facts"])
    assert repaired["facts"][0]["ledger_provenance"]["source_table"] == "ledger_status"
    assert repaired["facts"][0]["fact_id"] != "sidecar_fact"
    assert repaired["source_refs"] != packet["source_refs"]
    assert repaired["runtime_ledger_guard"]["status"] == "ledger_runtime_repair_applied"
    assert repaired["runtime_ledger_guard"]["original_fact_count"] == 1
    assert repaired["runtime_ledger_guard"]["repair_fact_count"] == len(repaired["facts"])
    assert repaired["machine_proof"]["ledger_runtime_guard_fired"] is True
    assert repaired["machine_proof"]["original_facts_have_ledger_provenance"] is False

    [line] = drift_log.read_text(encoding="utf-8").splitlines()
    receipt = json.loads(line)
    assert receipt["builder_name"] == "test_bad_builder"
    assert receipt["status"] == "ledger_runtime_repair_applied"
    assert receipt["source_of_truth"] == "business_ops_ledger"
    assert receipt["original_fact_count"] == 1
    assert receipt["repair_fact_count"] == len(repaired["facts"])
    assert receipt["original_source_refs"] == ["system_catalog.sqlite3#facts:sidecar_fact"]


def test_runtime_guard_noops_for_already_grounded_packet(tmp_path: Path) -> None:
    from context_source import ensure_packet_ledger_grounded, make_ledger_fact

    drift_log = tmp_path / "ledger_drift.jsonl"
    fact = make_ledger_fact(
        topic="test",
        label="Already grounded",
        value="This fact already came from the ledger.",
        source_table="canonical_facts",
        source_id="fact_ok",
        db_path=tmp_path / "ledger.sqlite",
    )
    packet = {"packet_id": "ok_packet", "facts": [fact], "source_refs": [fact["source_ref"]]}

    guarded = ensure_packet_ledger_grounded(
        packet,
        builder_name="test_good_builder",
        question="what is grounded?",
        agent_id="maestro",
        db_path=tmp_path / "ledger.sqlite",
        drift_log_path=drift_log,
    )

    assert guarded == packet
    assert not drift_log.exists()


def test_frontdoor_protected_generate_invokes_runtime_ledger_guard(monkeypatch, tmp_path: Path) -> None:
    import context_source
    import protected_generate

    called: dict[str, object] = {}

    def fake_guard(packet, *, builder_name, question, agent_id, **_kwargs):
        called["builder_name"] = builder_name
        called["question"] = question
        called["agent_id"] = agent_id
        fact = context_source.make_ledger_fact(
            topic="runtime_guard",
            label="Guarded front door fact",
            value="The front door packet was repaired from the ledger.",
            source_table="canonical_facts",
            source_id="guarded",
            db_path=tmp_path / "ledger.sqlite",
        )
        repaired = dict(packet)
        repaired["facts"] = [fact]
        repaired["source_refs"] = [fact["source_ref"]]
        repaired["runtime_ledger_guard"] = {"status": "ledger_runtime_repair_applied"}
        return repaired

    captured: dict[str, str] = {}

    def fake_generator(prompt, *, context_packet=None, **_kwargs):
        captured["prompt"] = prompt
        captured["context_packet"] = str(context_packet or "")
        return "The packet was repaired."

    monkeypatch.setattr(context_source, "ensure_packet_ledger_grounded", fake_guard)

    packet = {
        "schema_version": "maestro_context_packet_v0",
        "packet_id": "maestro_context_packet:bad",
        "facts": [
            {
                "fact_id": "sidecar_fact",
                "label": "Wrong-source fact",
                "value": "This should not reach the front-door prompt as trusted context.",
                "source_ref": "system_catalog.sqlite3#facts:sidecar_fact",
            }
        ],
        "source_refs": ["system_catalog.sqlite3#facts:sidecar_fact"],
    }

    outcome = protected_generate.protected_generate_with_receipt(
        "what is the grounded answer?",
        context_packet=packet,
        generator_fn=fake_generator,
        front_door_profile=True,
        allow_live_model=False,
        agent="cassandra",
    )

    assert outcome.status == "ANSWER_READY"
    assert called == {
        "builder_name": "protected_generate.frontdoor",
        "question": "what is the grounded answer?",
        "agent_id": "cassandra",
    }
    assert "The front door packet was repaired from the ledger." in captured["prompt"]
    assert "This should not reach" not in captured["prompt"]
    assert outcome.receipt["ledger_runtime_guard"]["status"] == "ledger_runtime_repair_applied"


def test_runtime_guard_does_not_write_default_drift_log_without_explicit_path(
    monkeypatch, tmp_path: Path
) -> None:
    import context_source

    default_log = tmp_path / "default-drift.jsonl"
    monkeypatch.setattr(context_source, "DEFAULT_LEDGER_DRIFT_RECEIPT_PATH", default_log)

    repaired = context_source.ensure_packet_ledger_grounded(
        {
            "packet_id": "bad_packet",
            "facts": [{"fact_id": "bad", "value": "wrong", "source_ref": "wrong.sqlite"}],
            "source_refs": ["wrong.sqlite"],
        },
        builder_name="test_default_log",
        db_path=tmp_path / "ledger.sqlite",
    )

    assert repaired["runtime_ledger_guard"]["receipt"]["drift_log_written"] is False
    assert not default_log.exists()
