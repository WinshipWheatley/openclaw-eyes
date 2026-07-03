from __future__ import annotations

from pathlib import Path

import niles_x32_capability as cap
from showprofile import build_scene


EMAIL_PAYLOAD = {
    "from": "pm@example.invalid",
    "subject": "Stage plot for Saturday",
    "body": """
Stage plot attached in email:
Input 1 - Kick
Input 2 - Snare Top
3 Lead Vox
4 Guitar SR
5 Bass DI
IEM 1: Lead Vox, Guitar
99 Spare Input
Notes: confirm spare vocal mic at changeover.
""",
}


def test_email_stage_plot_normalizes_to_showprofile_channels() -> None:
    from niles_stage_plot_ingest import build_show_profile_from_email

    profile = build_show_profile_from_email(EMAIL_PAYLOAD)

    assert profile.schema_version == "niles_stage_plot_ingest_v1"
    assert profile.subject == "Stage plot for Saturday"
    assert profile.sender == "pm@example.invalid"
    assert [(channel["ch"], channel["name"]) for channel in profile.channels] == [
        (1, "Kick"),
        (2, "Snare Top"),
        (3, "Lead Vox"),
        (4, "Guitar SR"),
        (5, "Bass DI"),
    ]
    assert profile.channels[0]["category"] == "drums"
    assert profile.channels[2]["category"] == "vox"
    assert profile.scene_text == build_scene(list(profile.channels), scene_name=profile.scene_name)
    assert '/ch/01/config "Kick" 2 RD 1' in profile.scene_text
    assert '/ch/05/config "Bass DI" 17 BL 5' in profile.scene_text
    assert profile.monitor_notes == ("IEM 1: Lead Vox, Guitar",)
    assert profile.unparsed_lines == (
        "99 Spare Input",
        "Notes: confirm spare vocal mic at changeover.",
    )
    assert profile.authority_boundary == {
        "email_read_performed": False,
        "email_send_performed": False,
        "hardware_control_performed": False,
        "live_scene_loaded": False,
        "operator_approval_required_before_load": True,
    }


def test_niles_x32_lane_writes_email_stage_plot_artifact_tier1(tmp_path: Path) -> None:
    result = cap.handle_stage_plot_email(EMAIL_PAYLOAD, show_profile_dir=tmp_path)

    assert result["handled"] is True
    assert result["intent"] == "show_profile_email"
    assert result["hardware_gated"] is True
    assert "review" in result["reply"].lower()
    assert "monitor notes" in result["reply"].lower()
    assert result["artifacts"], "expected a reviewable .scn artifact"
    scene_path = Path(result["artifacts"][0])
    assert scene_path.exists()
    scene_text = scene_path.read_text(encoding="utf-8")
    assert '/ch/03/config "Lead Vox" 41 MG 3' in scene_text
    assert "IEM 1" not in scene_text
