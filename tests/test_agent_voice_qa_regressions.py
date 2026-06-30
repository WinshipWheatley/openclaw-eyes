from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest


def test_stale_relative_date_operator_truth_fact_is_not_packeted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_store = types.ModuleType("operator_truth_store")

    def load_operator_truth_store(*, path, ensure_seed):
        return {
            "entities": {
                "stale_next_friday": {
                    "entity_key": "stale_next_friday",
                    "label": "Relative date correction",
                    "value": "In the 2026-06-19 evening correction, 'next Friday' means 2026-06-26.",
                    "source_ref": "operator_truth_store",
                    "precedence": 100,
                    "at": "2026-06-19T22:00:00Z",
                },
                "evergreen_payment_rule": {
                    "entity_key": "evergreen_payment_rule",
                    "label": "Payment safety rule",
                    "value": "Confirm brand-new vendor payment details out-of-band before acting.",
                    "source_ref": "operator_truth_store",
                    "precedence": 90,
                    "at": "2026-06-19T22:00:00Z",
                },
            }
        }

    fake_store.load_operator_truth_store = load_operator_truth_store
    monkeypatch.setitem(sys.modules, "operator_truth_store", fake_store)

    import maestro_context_packet as packet_mod

    facts, used, _ref = packet_mod._operator_truth_facts(
        path=None,
        question="what should I know about next Friday?",
    )

    blob = json.dumps(facts, sort_keys=True)
    assert used is True
    assert "Payment safety rule" in blob
    assert "2026-06-26" not in blob
    assert "next Friday" not in blob


def test_cassandra_prompt_requires_confirming_new_gig_amount_vs_existing_receivable() -> None:
    from frontdoor_prompt import build_frontdoor_prompt

    packet = {
        "facts": [
            {
                "fact_id": "niles_gig_context",
                "topic": "niles_gig_context",
                "label": "Niles gig setup context",
                "value": "Reynolds Tavern; 2026-06-27; fee $250.",
            },
            {
                "fact_id": "capital_hilton_receivable",
                "topic": "finance",
                "label": "Existing receivable",
                "value": "Capital Hilton/Coupa has an existing $2000 receivable due 2026-07-01.",
            }
        ]
    }
    prompt, _manifest = build_frontdoor_prompt(
        packet,
        "I just landed a $2000 gig next month. What should I be tracking?",
        agent="cassandra",
        max_chars=2600,
    )

    assert "same receivable" in prompt.lower()
    assert "new gig" in prompt.lower()
    assert "ask" in prompt.lower() or "confirm" in prompt.lower()
    assert "Capital Hilton/Coupa" in prompt


def test_niles_packet_includes_existing_music_read_models(tmp_path: Path) -> None:
    from maestro_context_packet import build_maestro_context_packet
    from frontdoor_prompt import build_frontdoor_prompt

    read_models = tmp_path / "read_models"
    read_models.mkdir()
    (read_models / "niles_track_registry.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-29T12:00:00+00:00",
                "real_track_roster_available": True,
                "track_count": 2,
                "tracks": [
                    {"title": "Nineteen Floors", "status": "rough mix"},
                    {"title": "Glass Orchard", "status": "live transition candidate"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (read_models / "reynolds_gig_setup_status.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-29T12:00:00+00:00",
                "venue_display_name": "Reynolds Tavern",
                "known_core_facts": {
                    "venue_name": "Reynolds Tavern",
                    "date": "2026-06-27",
                    "fee_amount": 250,
                    "start_time": "18:00",
                },
                "lanes": {"music": {"status": "needs set feel"}},
            }
        ),
        encoding="utf-8",
    )

    packet = build_maestro_context_packet(
        question="Quick vibe check -- how do I make my live set feel more alive?",
        read_model_root=read_models,
        require_real_truth=False,
    )
    blob = json.dumps(packet, sort_keys=True)

    assert "Nineteen Floors" in blob
    assert "Glass Orchard" in blob
    assert "Reynolds Tavern" in blob

    prompt, manifest = build_frontdoor_prompt(
        packet,
        "Quick vibe check -- how do I make my live set feel more alive?",
        agent="niles",
        max_chars=1800,
    )
    assert "Nineteen Floors" in prompt
    assert "Glass Orchard" in prompt
    assert "Reynolds Tavern" in prompt
    assert "first sentence must name one of those facts" in prompt
    assert any(fact_id.startswith("niles_music_context:") for fact_id in manifest["kept_fact_ids"])


def test_shared_agent_voice_sender_uses_mapped_voice_and_injected_delivery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import agent_voice_sender

    synth_calls: list[tuple[str, str, Path, float]] = []

    def fake_synth(text: str, voice: str, wav_path: Path, *, speed: float) -> bool:
        synth_calls.append((text, voice, wav_path, speed))
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        wav_path.write_bytes(b"RIFF")
        return True

    monkeypatch.setattr(agent_voice_sender, "synth_kokoro_wav", fake_synth)
    deliveries: list[tuple[str, str | None]] = []

    receipt = agent_voice_sender.send_agent_voice_note(
        "niles",
        "Make the second transition breathe.",
        wav_path=tmp_path / "niles.wav",
        chat_id="operator-chat",
        send_voice_note_fn=lambda path, chat_id=None: deliveries.append((path, chat_id)),
    )

    assert receipt.agent == "niles"
    assert receipt.voice == "am_puck"
    assert receipt.sent is True
    assert synth_calls == [("Make the second transition breathe.", "am_puck", tmp_path / "niles.wav", 1.0)]
    assert deliveries == [(str(tmp_path / "niles.wav"), "operator-chat")]


def test_master_voice_shell_resolves_agent_voice_without_maestro_fallback() -> None:
    source = Path("master_voice.sh").read_text(encoding="utf-8")

    assert "voice_for_agent" in source
    assert "KOKORO_AGENT" in source
    assert ":-am_michael" not in source
