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
