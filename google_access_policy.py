"""
google_access_policy.py

Machine-readable capability policy for the Google Access Broker.

Defines which agent may invoke which Google capability, and what
approval class (A / B / C) each capability requires.

Class A — safe reads. Auto-proceed (L0). Always audit-logged.
Class B — reversible internal writes (e.g. draft creation). L1 terminal confirm.
Class C — externally consequential or irreversible. L2 phone approval.
           Not active in phase 1.

Unknown capabilities and unlisted agents are denied by default.

Usage:
    from google_access_policy import allowed, get_class
    if not allowed("cassandra", "google.calendar.read"):
        raise PermissionError("not authorized")
    cls = get_class("cassandra", "google.calendar.read")  # → "A"
"""

# ── Approval classes ──────────────────────────────────────────────────────────

CLASS_A = "A"   # Safe reads — auto-proceed, always logged
CLASS_B = "B"   # Reversible internal writes — L1 confirm
CLASS_C = "C"   # External / irreversible — L2 phone approval (not active phase 1)
DENIED  = None  # Access explicitly denied


# ── Policy table ─────────────────────────────────────────────────────────────
# Format: { capability: { agent: class_or_DENIED } }
#
# Phase 1 active:    google.calendar.read for Cassandra only.
# Phase 1 placeholder: contacts.read, gmail.read.metadata (defined, not yet wired).
# Phase 2 placeholder: gmail.read.body (needs audit log verified before activation).
# Phase 3 placeholder: gmail.draft.create (first write — L1 confirm, structured input).
# Chief denied for all until phase 2 deliberate decision.
#
# Do not change a DENIED entry to CLASS_A/B/C without reviewing the approval class.
# Do not add new capabilities here without adding a corresponding executor in the broker.

_POLICY: dict[str, dict[str, str | None]] = {

    # ── Phase 1 active ───────────────────────────────────────────────────────
    "google.calendar.read": {
        "cassandra": CLASS_A,
        "chief":     DENIED,
    },

    # ── Phase 1 placeholder — defined but broker executor not yet wired ──────
    "google.contacts.read": {
        "cassandra": CLASS_A,
        "chief":     DENIED,
    },
    "google.gmail.read.metadata": {
        "cassandra": CLASS_A,
        "chief":     DENIED,
    },

    # ── Phase 2 placeholder — requires audit log verified before activation ──
    "google.gmail.read.body": {
        "cassandra": CLASS_A,
        "chief":     DENIED,
    },

    # ── Phase 3 placeholder — first write; L1 confirm, structured input req. ─
    "google.gmail.draft.create": {
        "cassandra": CLASS_B,
        "chief":     DENIED,
    },

    # ── Phase 2 active: calendar event creation, L1 confirm ──────────────────
    "google.calendar.write": {
        "cassandra": CLASS_B,
        "chief":     DENIED,
    },

    # ── Future only — not active in any current phase ────────────────────────
    "google.gmail.send": {
        "cassandra": CLASS_C,
        "chief":     DENIED,
    },
}


# ── Public API ────────────────────────────────────────────────────────────────

def allowed(agent: str, capability: str) -> bool:
    """True if the agent is permitted to invoke this capability."""
    cap_entry = _POLICY.get(capability)
    if cap_entry is None:
        return False
    return cap_entry.get(agent.lower()) is not None


def get_class(agent: str, capability: str) -> str | None:
    """
    Return the approval class for this agent+capability, or None if denied/unknown.
    """
    cap_entry = _POLICY.get(capability)
    if cap_entry is None:
        return None
    return cap_entry.get(agent.lower())


def list_allowed(agent: str) -> list[tuple[str, str]]:
    """Return list of (capability, class) pairs permitted for this agent."""
    result = []
    for cap, agents in _POLICY.items():
        cls = agents.get(agent.lower())
        if cls is not None:
            result.append((cap, cls))
    return result


# ── CLI smoke test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cases = [
        ("cassandra", "google.calendar.read",       True,  CLASS_A),
        ("cassandra", "google.gmail.draft.create",  True,  CLASS_B),
        ("cassandra", "google.calendar.write",      True,  CLASS_B),
        ("cassandra", "google.gmail.send",           True,  CLASS_C),
        ("chief",     "google.calendar.read",       False, DENIED),
        ("unknown",   "google.calendar.read",       False, DENIED),
        ("cassandra", "google.nonexistent",          False, None),
    ]
    print(f"{'Agent':<12} {'Capability':<35} {'Allowed?':<10} {'Class':<8} {'Pass'}")
    print("-" * 78)
    all_pass = True
    for agent, cap, exp_allowed, exp_class in cases:
        got_allowed = allowed(agent, cap)
        got_class   = get_class(agent, cap)
        ok = (got_allowed == exp_allowed) and (got_class == exp_class)
        all_pass = all_pass and ok
        flag = "OK" if ok else "FAIL"
        print(f"{agent:<12} {cap:<35} {str(got_allowed):<10} {str(got_class):<8} {flag}")
    print()
    sys.exit(0 if all_pass else 1)
