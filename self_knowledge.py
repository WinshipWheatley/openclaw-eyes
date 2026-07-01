"""Maestro's self-knowledge for conversation.

So Maestro can say, genuinely: "yeah, that did help me — keep 'em coming. And honestly, X
would help too" — then (next increment) actually file a request for X via the agent-request
factory. GROUNDED, never invented: recent improvements come from real recent commits;
gaps come from a curated list the system actually knows about.

Used lightly by the conversational lane — offered as "you MAY mention if it fits," not recited.
"""
from __future__ import annotations

import json
import subprocess
import time

_REPO = "/home/openclaw"

# Conventional-commit prefixes that represent operator-visible improvements.
_IMPROVEMENT_PREFIXES = ("feat", "fix", "tune", "perf")


import re

# Markers that mean a commit is internal/dev-detail, not an operator-facing improvement.
_TECHNICAL_MARKERS = (
    "nameerror", "typeerror", "regression", "byte-identical", "default off", "default-off",
    "gitignore", "syntax", "import", "traceback", "stub", "scaffold", "lint",
)
_SNAKE_CASE = re.compile(r"\b[a-z]+_[a-z_]+\b")  # likely a function/module name


def _clean_commit_subject(subject: str) -> str:
    """Turn 'feat(brain): casual chat is real…' into 'casual chat is real…' (operator-facing)."""
    s = subject.strip()
    if ":" in s:
        s = s.split(":", 1)[1].strip()
    return s


def _is_operator_facing(desc: str) -> bool:
    low = desc.lower()
    if any(m in low for m in _TECHNICAL_MARKERS):
        return False
    if _SNAKE_CASE.search(low):  # mentions a code identifier -> too technical to say out loud
        return False
    return True


def recent_improvements(limit: int = 4, *, repo: str = _REPO) -> list[str]:
    """Operator-facing list of the most recent real improvements (newest first)."""
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", "-40", "--format=%s"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return []
    items: list[str] = []
    seen: set[str] = set()
    for line in out.splitlines():
        low = line.strip().lower()
        if not any(low.startswith(p) for p in _IMPROVEMENT_PREFIXES):
            continue
        desc = _clean_commit_subject(line)
        key = desc.lower()[:40]
        if desc and key not in seen and _is_operator_facing(desc):
            items.append(desc)
            seen.add(key)
        if len(items) >= limit:
            break
    return items


# Curated, grounded improvements that would REALLY make the agent better — each is a REAL,
# buildable gap (NOT model-invented). `say` is what the agent mentions in conversation;
# `build_goal` is the concrete thing that gets filed as a build request if the operator
# agrees. Maintained by hand as real gaps open/close, so a recommendation always maps to
# something the factory can actually build.
_IMPROVEMENT_GAPS = [
    {
        "id": "agent_voices_cross_board",
        "say": "getting Cassandra, Niles, and Chief talking in their own voice too — right now only I do",
        "build_goal": "Wire each agent's reply surface (Cassandra email/intake, Niles studio, Chief status) to pass its agent_id into the conversational brain (build_frontdoor_prompt/protected_generate already accept agent=) so every agent talks in its own voice, not just Maestro.",
    },
    {
        "id": "predictive_on_it",
        "say": "forecasting when something's actually going to take a while and telling you 'on it' up front, instead of making you wait",
        "build_goal": "Make the fast-ack predictive: only fire when a response is forecast to take >10s, and forecast it from the request shape (substantive/complex vs casual) so the 'on it' is sent proactively, not after a fixed delay.",
    },
    {
        "id": "email_after_proof",
        "say": "handling your email myself once you've watched me get it right a few times",
        "build_goal": "Graduate the Gmail self-send test mode: after N verified self-test loops, allow Guardian-gated external sends so the agents can actually handle real email, not just self-tests.",
    },
]


from pathlib import Path as _Path

# Gap lifecycle state so a recommendation is only ever for a REAL, still-open gap — never one
# already requested or built. {gap_id: "requested" | "done"}. Absent = open.
_GAP_STATE_STORE = _Path("/home/openclaw/.openclaw/improvement_gap_state.json")


def _gap_state(store: _Path = _GAP_STATE_STORE) -> dict:
    try:
        return json.loads(_Path(store).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _state_of(rec) -> str | None:
    """Extract the state from a record — handles both the {'state','ts'} form and the legacy
    bare-string form."""
    if isinstance(rec, str):
        return rec
    if isinstance(rec, dict):
        return rec.get("state")
    return None


def _ts_of(rec) -> float:
    return float(rec.get("ts", 0)) if isinstance(rec, dict) else 0.0


def gap_record(gap_id: str, *, store: _Path = _GAP_STATE_STORE) -> dict | None:
    """Full lifecycle record {'state','ts'} for a gap, or None if never marked."""
    rec = _gap_state(store).get(gap_id)
    if rec is None:
        return None
    return {"state": _state_of(rec), "ts": _ts_of(rec)}


def mark_gap(gap_id: str, state: str, *, store: _Path = _GAP_STATE_STORE, ts: float | None = None) -> None:
    """state in {'requested','done'} (or 'open' to reset). Marks a gap with a timestamp so the
    lifecycle (auto-close when fixed, re-open on recurrence, retry a fix that didn't land) works."""
    d = _gap_state(store)
    if state == "open":
        d.pop(gap_id, None)
    else:
        d[gap_id] = {"state": state, "ts": float(ts) if ts is not None else time.time()}
    p = _Path(store)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        pass


def open_gaps(*, store: _Path = _GAP_STATE_STORE) -> list[dict]:
    """Gaps that are still OPEN — not yet requested or done. 'there actually is one'."""
    st = _gap_state(store)
    return [dict(g) for g in _IMPROVEMENT_GAPS if _state_of(st.get(g["id"])) not in ("requested", "done")]


def known_gaps() -> list[str]:
    return [g["say"] for g in open_gaps()]


def improvement_gaps() -> list[dict]:
    return [dict(g) for g in _IMPROVEMENT_GAPS]


def _detected_self_monitor_gaps() -> list[dict]:
    try:
        from self_monitor import self_check

        return [
            {"id": f["id"], "say": f["problem"], "build_goal": f["fix_goal"],
             "evidence": f.get("evidence", "")}
            for f in self_check()
        ]
    except Exception:
        return []


def _detected_ledger_drift_gaps() -> list[dict]:
    try:
        from ledger_drift_monitor import detect_ledger_source_drift_gaps

        return detect_ledger_source_drift_gaps()
    except Exception:
        return []


def detected_problems_as_gaps() -> list[dict]:
    """Live self-monitor findings turned into fileable gaps.

    REAL problems only: self-monitor findings plus runtime one-ledger guard drift. These
    take priority over the curated list and flow through the normal Guardian-gated factory.
    """
    return [*_detected_self_monitor_gaps(), *_detected_ledger_drift_gaps()]


def next_improvement() -> dict | None:
    """The single concrete OPEN improvement to recommend. Prefers a REAL problem the agent
    just DETECTED about itself over a curated gap; falls back to curated open gaps; None when
    nothing's open."""
    st = _gap_state()
    detected = [g for g in detected_problems_as_gaps()
                if _state_of(st.get(g["id"])) not in ("requested", "done")]
    if detected:
        return detected[0]
    o = open_gaps()
    return o[0] if o else None


def gap_by_id(gap_id: str) -> dict | None:
    for g in detected_problems_as_gaps():  # a detected problem the operator agreed to fix
        if g["id"] == gap_id:
            return dict(g)
    for g in _IMPROVEMENT_GAPS:
        if g["id"] == gap_id:
            return dict(g)
    return None


def self_knowledge_hint(*, repo: str = _REPO) -> str:
    """A short hint block the conversational lane can include for self-aware chat.
    Returns '' if nothing is available (fail-quiet)."""
    imp = recent_improvements(repo=repo)
    nxt = next_improvement()
    if not imp and not nxt:
        return ""
    parts = []
    if imp:
        parts.append("Recently you actually got better at: " + "; ".join(imp[:3]) + ".")
    if nxt:
        parts.append(
            f"The ONE next thing that would genuinely help you: {nxt['say']}. If the operator "
            "seems open to it, you can suggest it — if they say go for it, it gets built."
        )
    return " ".join(parts)
