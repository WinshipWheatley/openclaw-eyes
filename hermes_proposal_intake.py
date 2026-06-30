#!/usr/bin/env python3
"""Bridge: the CONVERSATIONAL Hermes (sidecar) -> the gated build pipe.

The sidecar Hermes you talk to is bounded-advisory and was a dead end — it could suggest but not
file. He now files a structured proposal by writing JSON to the watched inbox; this intake routes
each one through the SAME authorization gate the fleet loop uses (hermes_observer.route_to_chief):

    proposal JSON  ->  route_to_chief (requester ALWAYS "hermes")  ->
        normal build_goal       -> Chief's factory, PROPOSED + Guardian approval (BUILDOK/BUILDNO)
        privileged (send/money) -> escalated to Guardian (surfaced, never auto-built)
        not an allowed route    -> blocked (SURFACED to the operator, never silent)

Governance invariants (operator policy):
  * Hermes only PROPOSES. He cannot grant himself operator authority — a proposal file is always
    routed as requester "hermes" no matter what it claims; route_to_chief forces that.
  * Chief is not Hermes's executor: nothing builds without the operator's BUILDOK.
  * A block is never silent — every routed/escalated/blocked outcome is voiced to the operator
    (hermes_observer._default_notify_fn) so the operator always hears and can override.
  * The operator's own override stays first-class + separate (OPERATOR_REQUESTERS), from a trusted
    surface — not via a sidecar file.

  python3 hermes_proposal_intake.py            # dry run (list pending proposals)
  python3 hermes_proposal_intake.py --confirm   # route each pending proposal through the gate
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
DEFAULT_INBOX = ROOT / ".openclaw" / "hermes_proposals" / "inbox"
DEFAULT_DONE = ROOT / ".openclaw" / "hermes_proposals" / "done"
DEFAULT_ERRORS = ROOT / ".openclaw" / "hermes_proposals" / "errors"

_REQUIRED = ("id", "build_goal")


def _load_proposal(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if any(not str(data.get(k) or "").strip() for k in _REQUIRED):
        return None
    return data


def _to_suggestion(proposal: dict[str, Any]) -> dict[str, Any]:
    """Map a conversational proposal to the fleet-loop suggestion shape. source is fixed so the
    provenance ('hermes_conversation') is always honest; requester authority is set downstream."""
    return {
        "id": f"hermes_proposal_{str(proposal['id']).strip()}",
        "problem": str(proposal.get("title") or proposal.get("problem") or proposal["build_goal"]).strip(),
        "evidence": str(proposal.get("evidence") or "operator/Hermes conversation proposal").strip(),
        "build_goal": str(proposal["build_goal"]).strip(),
        "touched_scope_hint": proposal.get("touched_scope_hint"),
        "severity": str(proposal.get("severity") or "medium").strip(),
        "source": "hermes_conversation",
    }


def process_hermes_proposals(
    *,
    inbox: Path = DEFAULT_INBOX,
    done: Path = DEFAULT_DONE,
    errors: Path = DEFAULT_ERRORS,
    route_fn: Callable[[dict], dict] | None = None,
    notify_fn: Callable[[list[dict]], None] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    import hermes_observer

    route_fn = route_fn or hermes_observer.route_to_chief
    notify_fn = notify_fn if notify_fn is not None else hermes_observer._default_notify_fn

    inbox.mkdir(parents=True, exist_ok=True)
    pending = sorted(p for p in inbox.glob("*.json") if p.is_file())
    if not confirm:
        return {"dry_run": True, "pending": [p.name for p in pending],
                "operator_command": "python3 hermes_proposal_intake.py --confirm"}

    done.mkdir(parents=True, exist_ok=True)
    errors.mkdir(parents=True, exist_ok=True)
    receipts: list[dict] = []
    routed, escalated, blocked, bad = [], [], [], []
    for path in pending:
        proposal = _load_proposal(path)
        if proposal is None:
            path.rename(errors / path.name)
            bad.append(path.name)
            continue
        suggestion = _to_suggestion(proposal)
        receipt = route_fn(suggestion)
        receipt.setdefault("id", suggestion["id"])
        receipts.append(receipt)
        if not receipt.get("allowed"):
            blocked.append(suggestion["id"])
        elif receipt.get("route") == "guardian":
            escalated.append(suggestion["id"])
        else:
            routed.append(suggestion["id"])
        path.rename(done / path.name)
    if receipts:
        try:
            notify_fn(receipts)  # surfaces routed + escalated + BLOCKED to the operator
        except Exception:
            pass
    return {"confirmed": True, "routed_to_chief": routed, "escalated_to_guardian": escalated,
            "blocked": blocked, "invalid": bad}


def main() -> int:
    ap = argparse.ArgumentParser(description="Route conversational Hermes proposals through the gate.")
    ap.add_argument("--inbox", default=str(DEFAULT_INBOX))
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()
    print(json.dumps(process_hermes_proposals(inbox=Path(args.inbox), confirm=args.confirm), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
