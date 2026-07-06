from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import self_knowledge_orient as orient  # noqa: E402


def _ctx(**overrides: Any) -> orient.OrientationContext:
    data = {
        "principal": "openclaw",
        "machine_id": "pc",
        "network_context": "local_process",
        "local_process": True,
    }
    data.update(overrides)
    return orient.OrientationContext(**data)


def _seed_graph_ledger(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE knowledge_system_nodes ("
            "node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner_scope TEXT NOT NULL, "
            "health_status TEXT, activation_state TEXT, last_seen_at TEXT, last_verified_at TEXT, "
            "payload_json TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE knowledge_system_edges ("
            "source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, relation TEXT NOT NULL, "
            "owner_scope TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)"
        )
        nodes = {
            "machine:pc": {
                "id": "machine:pc",
                "kind": "machine",
                "owner_scope": "pc",
                "health_status": "ok",
            },
            "repo:/home/openclaw": {
                "id": "repo:/home/openclaw",
                "kind": "repo",
                "owner_scope": "pc",
                "path": "/home/openclaw",
                "branch": "main",
                "health_status": "ok",
            },
        }
        for node_id, payload in nodes.items():
            conn.execute(
                "INSERT INTO knowledge_system_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    node_id,
                    payload["kind"],
                    payload["owner_scope"],
                    payload.get("health_status"),
                    payload.get("activation_state"),
                    "2026-07-06T12:00:00+00:00",
                    "2026-07-06T12:00:00+00:00",
                    json.dumps(payload, sort_keys=True),
                    "self_knowledge_inventory_graph:pc",
                    "2026-07-06T12:00:00+00:00",
                ),
            )
        conn.execute(
            "INSERT INTO knowledge_system_edges VALUES (?, ?, ?, ?, ?, ?)",
            (
                "machine:pc",
                "repo:/home/openclaw",
                "contains",
                "pc",
                "self_knowledge_inventory_graph:pc",
                "2026-07-06T12:00:00+00:00",
            ),
        )


def _truth_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    store_path = tmp_path / "operator_truth_store.json"
    seed_path = tmp_path / "OPERATOR-TRUTH-domain-module.md"
    seed_path.write_text(
        "OpenClaw domain modules are contract-only until explicitly activated.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(store_path))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(seed_path))
    return store_path


def _read_models(tmp_path: Path) -> Path:
    root = tmp_path / "read_models"
    root.mkdir()
    (root / "agent_presence.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-06T12:00:00+00:00",
                "agents": [{"agent_id": "maestro", "display_name": "Maestro", "actual_state": "online"}],
                "next_safe_move": "Review domain-module registration without runtime action.",
            }
        ),
        encoding="utf-8",
    )
    (root / "openclaw_capability_index.json").write_text(
        json.dumps(
            {
                "generic_capabilities": [
                    {
                        "capability_id": "domain_module_registry",
                        "capability_name": "Domain module registry",
                        "capability_status": "READ_MODEL_ONLY",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


def test_record_label_worked_example_registers_all_snap_in_points() -> None:
    import domain_module_registry as registry

    payload = registry.build_domain_module_registry([registry.record_label_worked_example()])
    domain = payload["domains"]["record_label"]

    assert domain["status"] == "STUB_REGISTERED_CONTRACT_ONLY"
    assert set(domain["registration_points"]) == set(registry.REQUIRED_REGISTRATION_POINT_IDS)
    assert payload["machine_proof"]["record_label_registered"] is True
    assert payload["machine_proof"]["all_required_registration_points_declared"] is True
    assert payload["machine_proof"]["zero_invoice_or_st_annes_code_edits_required"] is True
    assert payload["authority_boundary"]["send_or_payment_allowed"] is False
    assert payload["authority_boundary"]["ledger_mutation_allowed"] is False


def test_register_domain_rejects_missing_required_point() -> None:
    import domain_module_registry as registry

    domain = registry.record_label_worked_example()
    points = dict(domain["registration_points"])
    points.pop("interpreter_intents")
    incomplete = {**domain, "registration_points": points}

    with pytest.raises(ValueError, match="interpreter_intents"):
        registry.build_domain_module_registry([incomplete])


def test_record_label_surfaces_in_orient_without_runtime_authority(tmp_path: Path) -> None:
    import domain_module_registry as registry

    ledger = tmp_path / "ledger.sqlite"
    _seed_graph_ledger(ledger)

    payload = orient.orient(level="high", ledger_path=ledger, context=_ctx())
    domain_modules = payload["map"]["domain_modules"]

    assert domain_modules["schema_version"] == "domain_module_registry_v0"
    assert domain_modules["authority_boundary"]["read_only"] is True
    assert domain_modules["authority_boundary"]["runtime_mutation_allowed"] is False
    assert domain_modules["domains"][0]["domain_id"] == "record_label"
    assert domain_modules["domains"][0]["registration_points_ready"] == len(
        registry.REQUIRED_REGISTRATION_POINT_IDS  # type: ignore[name-defined]
    )


def test_record_label_fact_grounds_through_existing_packet_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import domain_module_registry as registry
    from canonical_fact_ingest import ingest_graded_fact
    import maestro_context_packet as packet_builder

    store_path = _truth_store(monkeypatch, tmp_path)
    read_model_root = _read_models(tmp_path)
    db_path = tmp_path / "canonical_facts.sqlite"
    ingest_graded_fact(registry.record_label_canonical_fact(), db_path=str(db_path))

    original_sqlite_facts = packet_builder._sqlite_canonical_facts

    def patched_sqlite_facts(
        question: str,
        agent: str = "maestro",
        ledger_path: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        return original_sqlite_facts(question=question, agent=agent, ledger_path=str(db_path), limit=limit)

    with patch.object(packet_builder, "_sqlite_canonical_facts", side_effect=patched_sqlite_facts):
        packet = packet_builder.build_maestro_context_packet(
            question="What is the record label domain status?",
            read_model_root=read_model_root,
            operator_truth_store_path=store_path,
            require_real_truth=True,
            packet_source="sqlite",
        )

    canonical_values = [
        fact["value"]
        for fact in packet["facts"]
        if fact.get("provenance") == "canonical_facts"
    ]
    assert any("record label domain module" in value.lower() for value in canonical_values)
    assert any(fact.get("topic") == "record_label" for fact in packet["facts"])
    assert packet["status"] == "READY"


def test_domain_onboarding_doc_names_required_snap_in_points() -> None:
    doc = Path("DOMAIN-ONBOARDING.md").read_text(encoding="utf-8")

    for phrase in (
        "FACTS -> the one knowledge ledger",
        "ENTITIES -> registries",
        "WORKFLOWS -> declarative workflow engine",
        "RECURRENCE/TEMPORAL -> client-recurrence registry",
        "INTENTS -> shared interpreter",
        "AGENTS/PERSONAS -> agent roster",
        "SELF-KNOWLEDGE -> crawler roots",
        "record_label",
    ):
        assert phrase in doc
