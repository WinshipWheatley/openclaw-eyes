"""Hermes fleet loop — the fleet-level self-healing loop.

Hermes is the systems-architect sidecar. It WATCHES the whole fleet (brain quality, fleet
health, …), turns what it sees into concrete build suggestions, and routes each one to a
builder THROUGH an authorization gate so the pass-along is always allowed:

  • a normal buildable improvement      -> Chief's factory  (PROPOSED + Guardian "Build it?")
  • anything touching a privileged       -> Guardian          (escalated, NOT auto-built — the
    domain (sends / money / external)        operator decides; Hermes won't quietly wire it up)
  • a target that isn't an allowed route -> blocked           (surfaced, never routed)

Each suggestion is routed once (shared gap lifecycle: file-once, retry a build that didn't
land, re-open on recurrence, auto-close when the fleet signal clears) so Hermes never spams
Chief. This is the fleet-scale sibling of the per-agent ``autonomous_self_check`` — same
lifecycle, plus the gateway authorization that decides Chief-vs-Guardian.

CLI:  python3 hermes_observer.py        # run one fleet-observation pass
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

ROOT = Path("/home/openclaw")
_ROUTE_LOG = ROOT / ".openclaw" / "hermes_fleet_routes.jsonl"


# --------------------------------------------------------------------------- #
# Authorization gate — reuse the real Hermes gateway policy definitions.
# --------------------------------------------------------------------------- #
def _allowed_route_targets() -> frozenset[str]:
    try:
        from openclaw_hermes_gateway_policy import _agent_route_targets

        return _agent_route_targets()
    except Exception:
        return frozenset({"chief", "guardian"})


def _touches_privileged_domain(text: str) -> bool:
    """A build_goal that would send/notify externally or move money is privileged — Hermes is
    not allowed to pass that to Chief as a routine build; it must go to Guardian."""
    try:
        from openclaw_hermes_gateway_policy import _is_send_or_money_action

        return _is_send_or_money_action(text or "")
    except Exception:
        return False


def authorize_route(suggestion: dict, *, target: str = "chief",
                    allowed_targets: Optional[frozenset[str]] = None) -> dict:
    """Decide whether and how Hermes may pass ``suggestion`` along.
    Returns {"allowed": bool, "route": "chief"|"guardian"|None, "reason": str}."""
    targets = allowed_targets if allowed_targets is not None else _allowed_route_targets()
    goal = (suggestion or {}).get("build_goal", "") if isinstance(suggestion, dict) else ""

    if _touches_privileged_domain(goal):
        if "guardian" in targets:
            return {"allowed": True, "route": "guardian",
                    "reason": "touches a privileged domain (send/money/external) — Guardian decides"}
        return {"allowed": False, "route": None,
                "reason": "privileged domain and Guardian is not a reachable route target"}

    if target in targets:
        return {"allowed": True, "route": target, "reason": "buildable fleet improvement"}
    return {"allowed": False, "route": None, "reason": f"{target} is not an allowed route target"}


# --------------------------------------------------------------------------- #
# Observation — what Hermes watches. Each observer is () -> list[suggestion].
# A suggestion is {id, problem, evidence, build_goal, severity, source}.
# --------------------------------------------------------------------------- #
def _brain_quality_observer() -> list[dict]:
    """The fleet's shared front-door brain quality, via the proven self-monitor."""
    try:
        from self_monitor import self_check

        return [{"id": f["id"], "problem": f["problem"], "evidence": f.get("evidence", ""),
                 "build_goal": f["fix_goal"], "severity": f.get("severity", "medium"),
                 "source": "brain_quality"}
                for f in self_check()]
    except Exception:
        return []


def _fleet_health_observer() -> list[dict]:
    """Fleet sync health — if the read-model reports a degraded/failed lane, suggest a fix.
    Grounded + defensive: reads the generated read-model, fires only on a real failure signal."""
    try:
        path = ROOT / "generated" / "read_models" / "sync_health.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    status = str(
        (data.get("status") or data.get("overall_status") or data.get("health") or "")
    ).strip().lower()
    if status and status not in ("ok", "healthy", "green", "pass", "passing", "nominal"):
        return [{
            "id": "fleet_sync_degraded",
            "problem": "fleet sync health is degraded",
            "evidence": f"sync_health status={status}",
            "build_goal": "Investigate and repair the degraded sync lane so fleet read-models "
                          "stay fresh (identify the stalled source and restore its refresh).",
            "severity": "medium",
            "source": "fleet_health",
        }]
    return []


def _no_response_observer() -> list[dict]:
    try:
        from no_response_watchdog import no_response_observer

        return no_response_observer()
    except Exception:
        return []


DEFAULT_OBSERVERS = (
    _brain_quality_observer,
    _fleet_health_observer,
    _no_response_observer,
)


def observe_fleet(observers: Optional[Sequence[Callable[[], list[dict]]]] = None) -> list[dict]:
    """Run every observer and return de-duplicated suggestions (first id wins). A failing
    observer is isolated — it never sinks the others."""
    obs = observers if observers is not None else DEFAULT_OBSERVERS
    out: list[dict] = []
    seen: set[str] = set()
    for fn in obs:
        try:
            for s in (fn() or []):
                sid = s.get("id")
                if sid and sid not in seen:
                    seen.add(sid)
                    out.append(s)
        except Exception:
            continue
    return out


# --------------------------------------------------------------------------- #
# Routing — pass one authorized suggestion to its builder.
# --------------------------------------------------------------------------- #
def _default_file_to_factory(suggestion: dict) -> Any:
    """File the suggestion as a Hermes-originated build request: PROPOSED + Guardian approval."""
    from self_improvement_request import _default_file_fn as file_to_factory

    return file_to_factory(suggestion, "hermes")


def _default_handoff(suggestion: dict, receipt: dict) -> None:
    """Append an append-only routing receipt to the Hermes→builder audit trail. Fail-quiet,
    and never clobbers the sidecar's generated read-model."""
    try:
        _ROUTE_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {"suggestion_id": suggestion.get("id"), "source": suggestion.get("source"),
               "route": receipt.get("route"), "build_goal": suggestion.get("build_goal"),
               "reason": receipt.get("reason")}
        with _ROUTE_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def route_to_chief(suggestion: dict, *, file_fn: Optional[Callable[[dict], Any]] = None,
                   handoff_fn: Optional[Callable[[dict, dict], None]] = None,
                   allowed_targets: Optional[frozenset[str]] = None) -> dict:
    """Authorize, then route a single suggestion. A normal build is filed to Chief's factory;
    a privileged one is escalated to Guardian (surfaced, never auto-filed). Returns a receipt."""
    auth = authorize_route(suggestion, target="chief", allowed_targets=allowed_targets)
    receipt = {"suggestion_id": suggestion.get("id"), "route": auth["route"],
               "allowed": auth["allowed"], "reason": auth["reason"], "filed": False}
    handoff = handoff_fn or _default_handoff

    if not auth["allowed"]:
        return receipt

    if auth["route"] == "guardian":
        receipt["escalated"] = True
        try:
            handoff(suggestion, receipt)
        except Exception:
            pass
        return receipt

    # route == "chief": file the build (Guardian-gated PROPOSED downstream).
    fn = file_fn or _default_file_to_factory
    try:
        receipt["file_result"] = fn(suggestion)
        receipt["filed"] = True
    except Exception as exc:  # factory down — leave unmarked so the loop retries next cycle.
        receipt["error"] = str(exc)
        return receipt
    try:
        handoff(suggestion, receipt)
    except Exception:
        pass
    return receipt


# --------------------------------------------------------------------------- #
# The loop — observe → authorize+route each (file-once lifecycle) → notify.
# --------------------------------------------------------------------------- #
def _default_notify_fn(routed: list[dict]) -> None:
    """Tell the operator, in prose, what Hermes routed this pass. Fail-open."""
    if not routed:
        return
    built = [r for r in routed if r.get("route") == "chief"]
    flagged = [r for r in routed if r.get("route") == "guardian"]
    bits = []
    if built:
        bits.append(f"sent {len(built)} build{'s' if len(built) != 1 else ''} to Chief")
    if flagged:
        bits.append(f"flagged {len(flagged)} for your call (Guardian)")
    if not bits:
        return
    msg = ("Hermes here — watching the fleet, I " + " and ".join(bits) +
           ". You'll get a Guardian approval for each build.")
    try:
        import subprocess

        subprocess.run(["bash", str(ROOT / "master_voice.sh")], input=msg,
                       text=True, timeout=120, capture_output=True)
    except Exception:
        pass


def run_hermes_fleet_loop(
    *,
    observers: Optional[Sequence[Callable[[], list[dict]]]] = None,
    file_fn: Optional[Callable[[dict], Any]] = None,
    notify_fn: Optional[Callable[[list[dict]], None]] = None,
    handoff_fn: Optional[Callable[[dict, dict], None]] = None,
    requested_failed_fn: Optional[Callable[[dict], bool]] = None,
    allowed_targets: Optional[frozenset[str]] = None,
    state_store: Optional[Path] = None,
    now: Optional[float] = None,
    build_grace_s: float = 86400.0,
    resolve_grace_s: float = 43200.0,
) -> dict:
    """One fleet-observation pass with the file-once lifecycle (so Hermes never spams Chief):
      • new suggestion                      -> authorize + route (Chief build or Guardian escalate)
      • routed before, build hasn't landed  -> wait (skipped) until build_grace, then retry
      • detected again after 'done'         -> recurrence: re-route
      • no longer detected after grace      -> the fix worked: auto-close ('done')
    Returns {checked, routed_to_chief, escalated_to_guardian, blocked, failed, refiled,
    resolved, skipped}."""
    import time

    from self_knowledge import _gap_state, mark_gap, _GAP_STATE_STORE, _state_of, _ts_of

    store = state_store or _GAP_STATE_STORE
    now = now if now is not None else time.time()
    notify_fn = notify_fn or _default_notify_fn
    if requested_failed_fn is None:
        try:
            from self_improvement_request import requested_self_improvement_terminal

            requested_failed_fn = requested_self_improvement_terminal
        except Exception:
            requested_failed_fn = lambda _suggestion: False

    suggestions = {s["id"]: s for s in observe_fleet(observers) if s.get("id")}
    st = _gap_state(store=store)
    routed_to_chief: list[str] = []
    escalated_to_guardian: list[str] = []
    blocked: list[str] = []
    failed: list[str] = []
    refiled: list[str] = []
    resolved: list[str] = []
    skipped: list[str] = []
    routed_receipts: list[dict] = []

    def _route(sug: dict, *, is_refile: bool) -> None:
        receipt = route_to_chief(sug, file_fn=file_fn, handoff_fn=handoff_fn,
                                 allowed_targets=allowed_targets)
        sid = sug["id"]
        if not receipt.get("allowed"):
            blocked.append(sid)
            return
        if receipt.get("route") == "chief" and not receipt.get("filed"):
            failed.append(sid)          # factory down: not marked -> retried next cycle
            return
        mark_gap(sid, "requested", store=store, ts=now)   # routed once
        routed_receipts.append(receipt)
        if receipt.get("route") == "guardian":
            escalated_to_guardian.append(sid)
        elif is_refile:
            refiled.append(sid)
        else:
            routed_to_chief.append(sid)

    # 1. Currently-observed suggestions.
    for sid, sug in suggestions.items():
        rec = st.get(sid)
        state, ts = _state_of(rec), _ts_of(rec)
        if state is None:
            _route(sug, is_refile=False)               # brand-new
        elif state == "done":
            _route(sug, is_refile=True)                # recurrence -> re-route
        elif state == "requested":
            try:
                requested_failed = bool(requested_failed_fn(sug))
            except Exception:
                requested_failed = False
            if requested_failed or now - ts > build_grace_s:
                _route(sug, is_refile=True)            # build didn't land -> retry
            else:
                skipped.append(sid)                    # still waiting on the build

    # 2. Auto-close anything routed but no longer observed (the fix worked).
    for sid, rec in list(st.items()):
        if _state_of(rec) == "requested" and sid not in suggestions and (now - _ts_of(rec)) > resolve_grace_s:
            mark_gap(sid, "done", store=store, ts=now)
            resolved.append(sid)

    if routed_receipts:
        try:
            notify_fn(routed_receipts)
        except Exception:
            pass

    return {"checked": True, "routed_to_chief": routed_to_chief,
            "escalated_to_guardian": escalated_to_guardian, "blocked": blocked,
            "failed": failed, "refiled": refiled, "resolved": resolved, "skipped": skipped}


def main() -> None:
    res = run_hermes_fleet_loop()
    print(f"hermes fleet loop: to_chief={res['routed_to_chief']} "
          f"guardian={res['escalated_to_guardian']} skipped={res['skipped']}")


if __name__ == "__main__":
    main()
