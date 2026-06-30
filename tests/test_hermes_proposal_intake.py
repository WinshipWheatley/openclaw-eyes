from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hermes_proposal_intake as intake  # noqa: E402


def _write(inbox: Path, name: str, payload: dict) -> None:
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / name).write_text(json.dumps(payload), encoding="utf-8")


def _fake_route(suggestion):
    # Mimic authorize_route's verdicts by build_goal content.
    goal = suggestion["build_goal"].lower()
    if "wire the payment" in goal or "email the client" in goal:
        return {"allowed": True, "route": "guardian", "escalated": True}
    if "forbidden" in goal:
        return {"allowed": False, "reason": "not an allowed route"}
    return {"allowed": True, "route": "chief", "filed": True}


def test_valid_proposal_routes_and_moves_to_done(tmp_path):
    inbox, done, errors = tmp_path / "in", tmp_path / "done", tmp_path / "err"
    _write(inbox, "p1.json", {"id": "abc", "build_goal": "add a field to the invoice flow", "evidence": "e"})
    captured = {}
    res = intake.process_hermes_proposals(
        inbox=inbox, done=done, errors=errors,
        route_fn=_fake_route, notify_fn=lambda r: captured.__setitem__("r", r), confirm=True,
    )
    assert res["routed_to_chief"] == ["hermes_proposal_abc"]
    assert (done / "p1.json").exists() and not (inbox / "p1.json").exists()
    # provenance is always honest: source can't be spoofed to escape the hermes lane
    assert captured["r"] and captured["r"][0]["id"] == "hermes_proposal_abc"


def test_privileged_proposal_escalates_and_block_surfaces(tmp_path):
    inbox = tmp_path / "in"
    _write(inbox, "pay.json", {"id": "pay", "build_goal": "wire the payment to the vendor"})
    _write(inbox, "no.json", {"id": "no", "build_goal": "do a forbidden thing"})
    captured = {}
    res = intake.process_hermes_proposals(
        inbox=inbox, done=tmp_path / "d", errors=tmp_path / "e",
        route_fn=_fake_route, notify_fn=lambda r: captured.__setitem__("r", r), confirm=True,
    )
    assert res["escalated_to_guardian"] == ["hermes_proposal_pay"]
    assert res["blocked"] == ["hermes_proposal_no"]
    # the BLOCKED one is surfaced to the operator notify (never silent)
    surfaced = [x for x in captured["r"] if not x.get("allowed")]
    assert [x["id"] for x in surfaced] == ["hermes_proposal_no"]


def test_invalid_proposal_goes_to_errors_not_routed(tmp_path):
    inbox, errors = tmp_path / "in", tmp_path / "err"
    _write(inbox, "bad.json", {"id": "x"})  # missing build_goal
    (inbox / "junk.json").write_text("not json", encoding="utf-8")
    calls = []
    res = intake.process_hermes_proposals(
        inbox=inbox, done=tmp_path / "d", errors=errors,
        route_fn=lambda s: calls.append(s) or {"allowed": True, "route": "chief"},
        notify_fn=lambda r: None, confirm=True,
    )
    assert calls == []  # nothing invalid was routed
    assert sorted(res["invalid"]) == ["bad.json", "junk.json"]
    assert (errors / "bad.json").exists()


def test_dry_run_lists_pending_without_routing(tmp_path):
    inbox = tmp_path / "in"
    _write(inbox, "p1.json", {"id": "a", "build_goal": "x"})
    res = intake.process_hermes_proposals(inbox=inbox, route_fn=lambda s: 1 / 0, confirm=False)
    assert res["dry_run"] is True and res["pending"] == ["p1.json"]
