from __future__ import annotations

from pathlib import Path

import maestro_cassandra_responder as maestro

from test_capability_ledger_reconciler import (
    OBSERVED_AT,
    _ledger,
    _mac_inventory,
    _pc_inventory,
    _register,
)
import capability_ledger_reconciler as reconciler


def _confirmed_ledger(tmp_path: Path) -> Path:
    ledger = _ledger(tmp_path / "ledger.sqlite")
    reconciler.reconcile_capabilities(
        register_path=_register(tmp_path / "register.json"),
        ledger_path=ledger,
        pc_inventory=_pc_inventory(),
        mac_inventory=_mac_inventory(),
        observed_at=OBSERVED_AT,
        confirm=True,
        receipt_path=tmp_path / "receipt.json",
        attention_path=tmp_path / "attention.json",
    )
    return ledger


def test_maestro_built_vs_on_answer_reads_capability_ledger_only(tmp_path: Path) -> None:
    ledger = _confirmed_ledger(tmp_path)

    answer = maestro.build_ledger_capability_answer(ledger_path=ledger)

    assert answer["one_line_answer"].startswith("Ledger-only capability readback:")
    assert "4 runtime rows are confirmed on" in answer["plain_summary"]
    assert "3 running rows are unregistered" in answer["plain_summary"]
    proof = answer["machine_proof"]
    assert proof["capability_ledger_only"] is True
    assert proof["capability_activations_used"] is True
    assert proof["read_model_used"] is False
    assert proof["external_llm_invoked"] is False
    assert proof["runtime_collection_performed"] is False


def test_maestro_frontdoor_routes_exact_built_vs_on_question_to_ledger(tmp_path: Path, monkeypatch) -> None:
    ledger = _confirmed_ledger(tmp_path)
    monkeypatch.setattr(maestro, "DEFAULT_CAPABILITY_LEDGER_PATH", ledger)

    result = maestro.answer_frontdoor_chat("what's built and what's actually on?")

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "status_capability_readback"
    assert result.allowed_to_call_handle is False
    assert "Ledger-only capability readback:" in result.plain_summary
    assert result.machine_proof["capability_ledger_only"] is True
    assert result.machine_proof["protected_generate_called"] is False
    assert result.machine_proof["external_llm_invoked"] is False


def test_typed_contract_status_owner_uses_ledger_answer_not_bare_status(tmp_path: Path, monkeypatch) -> None:
    ledger = _confirmed_ledger(tmp_path)
    monkeypatch.setattr(maestro, "DEFAULT_CAPABILITY_LEDGER_PATH", ledger)

    answer = maestro._build_typed_contract_status_answer(
        "what's built and what's actually on?",
        agent="maestro",
        session=None,
    )

    assert answer["machine_proof"]["status_capability_readback_performed"] is True
    assert answer["machine_proof"]["capability_ledger_only"] is True
    assert "Ledger-only capability readback:" in answer["plain_summary"]
