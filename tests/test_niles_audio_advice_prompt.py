from __future__ import annotations

import json

import niles_rig_kb
from frontdoor_prompt import build_frontdoor_prompt


def _packet(facts: list[dict[str, object]]) -> dict[str, object]:
    return {"facts": facts}


def test_niles_x32_vocal_channel_howto_is_advice_not_hardware_refusal() -> None:
    packet = _packet(
        [
            {
                "fact_id": "niles_reynolds_gig",
                "topic": "niles_reynolds_gig",
                "label": "Reynolds Tavern gig",
                "value": "Reynolds Tavern is scheduled for 2026-06-27 at 19:00 for $250.",
                "source_ref": "generated/read_models/reynolds_gig_setup_status.json",
            },
            {
                "fact_id": "capital_hilton_receivable",
                "topic": "finance",
                "label": "Capital Hilton invoice",
                "value": "Capital Hilton has an open Coupa invoice awaiting payment.",
                "source_ref": "generated/read_models/finance_invoice_reconciliation.json",
            },
        ]
    )

    prompt, manifest = build_frontdoor_prompt(
        packet,
        "set me up a vocal channel on the x32 for a wedding",
        agent="niles",
        max_chars=3200,
    )

    prompt_lower = prompt.lower()
    assert "You are Niles" in prompt
    assert "You are Maestro" not in prompt
    assert "treat this as advice, not live device control" in prompt_lower
    assert "do not refuse" in prompt_lower
    assert "gain" in prompt_lower
    assert "hpf" in prompt_lower
    assert "compression" in prompt_lower
    assert "eq" in prompt_lower
    assert "Reynolds Tavern" not in prompt
    assert "Capital Hilton" not in prompt
    assert "maestro has zero authority" not in prompt_lower
    assert "niles_audio_advice:x32_vocal_channel" in manifest["kept_fact_ids"]
    assert "niles_reynolds_gig" in manifest["dropped_fact_ids"]
    assert "capital_hilton_receivable" in manifest["dropped_fact_ids"]


def test_niles_rig_kb_exports_vocal_channel_advice_without_execution_authority() -> None:
    payload = niles_rig_kb.build_payload()
    blob = json.dumps(payload, sort_keys=True).lower()

    assert "x32_vocal_channel_advice" in payload
    assert "hpf" in blob
    assert "compression" in blob
    assert "eq" in blob
    assert payload["authority_boundary"]["live_hardware_control_allowed"] is False
    assert payload["machine_proof"]["hardware_control_performed"] is False
