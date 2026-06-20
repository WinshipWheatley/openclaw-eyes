from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import niles_responder as niles
import niles_rig_kb as rig_kb


def test_identity_answer_speaks_as_niles_and_names_winship():
    result = niles.answer_niles_frontdoor("who are you?")

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "identity"
    assert "I'm Niles" in result.one_line_answer
    assert "Winship" in result.plain_summary
    assert result.machine_proof["text_response_only"] is True
    assert result.machine_proof["hardware_control_performed"] is False
    assert result.machine_proof["external_send_performed"] is False


@pytest.mark.parametrize(
    "prompt",
    [
        "what can you help me with?",
        "give me your status",
        "what are your capabilities?",
    ],
)
def test_capability_and_status_prompts_return_safe_readback(prompt: str):
    result = niles.answer_niles_frontdoor(prompt)

    assert result.status == "ANSWER_READY"
    assert result.intent_class in {"capability", "status"}
    assert "music" in result.plain_summary.lower()
    assert "rig" in result.plain_summary.lower()
    assert "no hardware action" in result.plain_summary.lower()
    assert result.machine_proof["model_call_performed"] is False
    assert result.machine_proof["send_hold_boundary_visible"] is True


def test_gear_readback_lists_rig_and_truthful_holds():
    result = niles.answer_niles_frontdoor("what gear do you control?")

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "rig_inventory"
    answer = result.plain_summary.lower()
    for expected in [
        "x32 rack",
        "broken",
        "dbx driverack pa2",
        "dl32",
        "push 2",
        "fcb1010",
        "x32 edit",
    ]:
        assert expected in answer
    assert "explicit operator confirmation" in answer
    assert result.machine_proof["rig_kb_used"] is True
    assert result.machine_proof["hardware_control_performed"] is False


@pytest.mark.parametrize(
    "prompt",
    [
        "set X32 channel 1 fader to -5",
        "mute the vocal channel on the X32",
        "open Logic and arm the guitar track",
        "send that rig note to the band",
    ],
)
def test_action_prompts_stage_or_deny_without_control(prompt: str):
    result = niles.answer_niles_frontdoor(prompt)

    assert result.status == "ROUTE_TO_STAGING"
    assert result.allowed_to_reply_directly is False
    assert "no_hardware_or_external_action" in result.route_to_staging_reason
    assert result.machine_proof["hardware_control_performed"] is False
    assert result.machine_proof["osc_message_sent"] is False
    assert result.machine_proof["external_send_performed"] is False


def test_rig_kb_builds_sqlite_with_x32_osc_starting_point(tmp_path: Path):
    db_path = tmp_path / "niles_gear_kb.sqlite"
    rig_kb.build_sqlite_kb(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        devices = {
            row["device_id"]: dict(row)
            for row in conn.execute("select * from devices order by device_id")
        }
        controls = {
            row["control_id"]: dict(row)
            for row in conn.execute("select * from control_paths order by control_id")
        }

    assert devices["x32_rack_broken"]["repair_status"] == "needs_repair"
    assert devices["x32_rack_monitor"]["gig_role"] == "monitor_iem"
    assert devices["kat_percussion_pad"]["model_verification_status"] == "verify_model"
    assert controls["x32_osc_channel_fader"]["protocol"] == "OSC"
    assert controls["x32_osc_channel_fader"]["address_pattern"] == "/ch/{channel:02d}/mix/fader"
    assert controls["x32_osc_channel_fader"]["safe_to_execute"] == 0
    assert "X32 Edit" in controls["x32_osc_channel_fader"]["stress_test_target"]


def test_rig_kb_json_readback_has_no_secret_or_private_material(tmp_path: Path):
    db_path = tmp_path / "niles_gear_kb.sqlite"
    payload = rig_kb.build_payload(sqlite_path=db_path)
    text = json.dumps(payload, sort_keys=True)

    assert db_path.exists()
    assert payload["machine_proof"]["all_control_authority_false"] is True
    assert payload["machine_proof"]["manuals_fabricated"] is False
    assert "NILES_BOT_TOKEN" not in text
    assert ".chief.env" not in text
    assert "MusicLawPrivate" not in text

