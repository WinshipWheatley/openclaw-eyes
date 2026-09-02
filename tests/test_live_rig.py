from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import live_rig

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "live_rig.v1.json"


def _payload(**kwargs):
    return live_rig.build_live_rig_read_model(live_rig.load_config(CONFIG), today=date(2026, 9, 2), generated_at="2026-09-02T07:50:00+00:00", **kwargs)


def test_budget_matches_the_doc() -> None:
    budget = _payload()["budget"]
    assert budget["gear_total_minor_units_low"] == 169900
    assert budget["gear_total_minor_units_high"] == 184900
    assert budget["fee_covered_gear_minor_units_low"] == 144900
    assert budget["fee_covered_gear_minor_units_high"] == 159900
    assert budget["self_funded_items"] == ["MOTU M4"]
    assert budget["self_funded_minor_units"] == 25000


def test_open_loops_are_mine_first_with_days_open_and_blockers() -> None:
    payload = _payload()
    loops = payload["open_loops"]
    assert loops[0]["owner"] == "me"
    assert loops[0]["id"] == "call_will"
    assert loops[0]["days_open"] == 9
    by_id = {row["id"]: row for row in loops}
    assert by_id["order_gear"]["blocked_on"] == "call_will"
    assert by_id["routing_scene"]["proposal"] == "proposed_x32"
    assert payload["open_loops_by_owner"]["sarah"] == ["sarah_reply"]
    assert payload["open_loops_by_owner"]["synth_dev"] == ["synth_mac_port"]


def test_proposed_channels_categorize_cleanly_and_answer_both_questions() -> None:
    payload = _payload()
    proposed = payload["proposed_x32"]
    assert proposed["confirmation_status"] == "proposed_not_confirmed"
    assert proposed["uncategorized_channels"] == []
    by_ch = {row["ch"]: row for row in proposed["channels"]}
    assert by_ch[1]["category"] == "vox" and by_ch[1]["color"] == "MG"
    assert by_ch[3]["category"] == "keys" and by_ch[3]["color"] == "YEi"
    assert by_ch[5]["category"] == "looper" and by_ch[5]["color"] == "CYi"
    assert by_ch[7]["to_main"] is False and by_ch[8]["to_main"] is False
    assert not by_ch[5]["to_looper_send"] and not by_ch[6]["to_looper_send"]
    assert set(proposed["answers"]) == {"rc505_x32_io", "x32_scene"}
    question_ids = {row["id"] for row in payload["routing_questions"]}
    assert question_ids == set(proposed["answers"])


def test_scene_artifact_is_a_loadable_scn_with_named_channels() -> None:
    scene = live_rig.render_scene(live_rig.load_config(CONFIG))
    lines = scene.splitlines()
    assert lines[0].startswith('#4.0# "Winship Loop v0"')
    assert '/ch/01/config "Lead Vox" 41 MG 1' in lines
    assert '/ch/05/config "Looper L" 60 CYi 5' in lines
    assert '/ch/07/config "Click L" 60 WH 7' in lines
    assert len(lines) == 8


def test_export_writes_read_model_operator_and_scene(tmp_path: Path) -> None:
    summary = live_rig.export_live_rig(config_path=CONFIG, export_root=tmp_path / "rm", artifact_root=tmp_path / "art", today=date(2026, 9, 2), generated_at="2026-09-02T07:50:00+00:00")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    assert payload["read_model_id"] == "live_rig"
    assert all(value is False for value in payload["authority_boundary"].values())
    assert payload["proposed_x32"]["scene_artifact_path"] == str(tmp_path / "art" / "live_rig_proposed.scn")
    assert Path(summary["scene_path"]).exists()
    operator = Path(summary["operator_path"]).read_text(encoding="utf-8")
    assert "Deals side by side:" in operator
    assert "$1,125/night full rig" in operator
    assert "[me] Call Will, then send three recap texts" in operator
    assert "ch 07 Click L" in operator and "not on LR" in operator
    assert "the operator loads the scene" in operator
    again = live_rig.export_live_rig(config_path=CONFIG, export_root=tmp_path / "rm", artifact_root=tmp_path / "art", today=date(2026, 9, 2), generated_at="2026-09-02T07:50:00+00:00")
    assert Path(again["json_path"]).read_bytes() == Path(summary["json_path"]).read_bytes()
