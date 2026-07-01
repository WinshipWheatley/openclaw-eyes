from __future__ import annotations

import json
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _audit_row(*, builder: str, packet_id: str, route: str = "local_ollama_frontdoor") -> dict:
    return {
        "schema_version": "protected_generate_receipt_v0",
        "route": route,
        "ledger_runtime_guard": {
            "status": "ledger_runtime_repair_applied",
            "builder_name": builder,
            "original_fact_count": 1,
            "repair_fact_count": 3,
            "receipt": {
                "schema_version": "ledger_runtime_drift_receipt_v0",
                "builder_name": builder,
                "packet_id": packet_id,
                "agent_id": "cassandra",
                "status": "ledger_runtime_repair_applied",
                "source_of_truth": "business_ops_ledger",
                "original_fact_count": 1,
                "repair_fact_count": 3,
                "original_source_refs": ["system_catalog.sqlite3#facts:stale"],
                "repair_source_refs": [
                    "ledger:/home/openclaw/.openclaw/business_ops/ledger.sqlite#canonical_facts:SD-1"
                ],
            },
        },
    }


def test_detects_recurring_real_ledger_drift_and_ignores_synthetic(tmp_path: Path) -> None:
    from ledger_drift_monitor import detect_ledger_source_drift_gaps

    audit = tmp_path / "protected_generate_audit.jsonl"
    _write_jsonl(
        audit,
        [
            _audit_row(builder="protected_generate.frontdoor", packet_id="maestro_context_packet:real1"),
            _audit_row(builder="protected_generate.frontdoor", packet_id="maestro_context_packet:real2"),
            _audit_row(
                builder="protected_generate.frontdoor",
                packet_id="maestro_context_packet:manual_guard_probe",
                route="injected_generator",
            ),
            {
                **_audit_row(builder="protected_generate.frontdoor", packet_id="maestro_context_packet:test"),
                "ledger_runtime_guard": {
                    "status": "ledger_runtime_repair_applied",
                    "builder_name": "protected_generate.frontdoor",
                    "receipt": {
                        "builder_name": "protected_generate.frontdoor",
                        "packet_id": "maestro_context_packet:test",
                        "status": "ledger_runtime_repair_applied",
                        "original_source_refs": ["generated/read_models/operator_truth.json"],
                        "repair_source_refs": ["ledger:/home/openclaw/.pytest_openclaw/business_ops/ledger.sqlite"],
                    },
                },
            },
        ],
    )

    gaps = detect_ledger_source_drift_gaps(audit_log_path=audit, min_occurrences=2)

    assert len(gaps) == 1
    gap = gaps[0]
    assert gap["id"].startswith("ledger_source_drift:")
    assert "protected_generate.frontdoor" in gap["build_goal"]
    assert "system_catalog.sqlite3#facts:stale" in gap["evidence"]
    assert "2 runtime ledger repair" in gap["evidence"]


def test_ledger_source_drift_package_is_bounded_for_guardian_factory(tmp_path: Path) -> None:
    from ledger_drift_monitor import detect_ledger_source_drift_gaps
    from self_improvement_request import compile_self_improvement_package

    audit = tmp_path / "protected_generate_audit.jsonl"
    _write_jsonl(
        audit,
        [
            _audit_row(builder="protected_generate.frontdoor", packet_id="maestro_context_packet:real1"),
            _audit_row(builder="protected_generate.frontdoor", packet_id="maestro_context_packet:real2"),
        ],
    )

    [gap] = detect_ledger_source_drift_gaps(audit_log_path=audit, min_occurrences=2)
    package = compile_self_improvement_package(gap, agent="maestro")

    assert package["package_profile"] == "ledger_source_drift"
    assert package["source"] == "agent_self_improvement"
    assert "context_source.py" in package["allowed_files"]
    assert "protected_generate.py" in package["allowed_files"]
    assert "tests/test_ledger_drift_monitor.py" in package["allowed_files"]
    assert any("No production restarts" in item for item in package["production_prohibitions"])


def test_self_knowledge_merges_ledger_drift_gaps(monkeypatch) -> None:
    import self_knowledge

    monkeypatch.setattr(self_knowledge, "_detected_self_monitor_gaps", lambda: [])
    monkeypatch.setattr(
        self_knowledge,
        "_detected_ledger_drift_gaps",
        lambda: [{"id": "ledger_source_drift:abc", "say": "ledger drift", "build_goal": "fix it"}],
    )

    assert self_knowledge.detected_problems_as_gaps() == [
        {"id": "ledger_source_drift:abc", "say": "ledger drift", "build_goal": "fix it"}
    ]
