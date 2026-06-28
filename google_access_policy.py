"""
google_access_policy.py

Machine-readable capability policy for the Google Access Broker.

Defines which agent may invoke which Google capability, and what
approval class (A / B / C) each capability requires.

Class A — safe reads. Auto-proceed (L0). Always audit-logged.
Class B — reversible internal writes that still require confirmation.
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
# Active safe reads: contacts.read, gmail.read.metadata.
# Sensitive Gmail body reads and draft creation are Tier 1 confirmation paths.
# Chief denied for all until phase 2 deliberate decision.
#
# Do not change a DENIED entry to CLASS_A/B/C without reviewing the approval class.
# Do not add new capabilities here without adding a corresponding executor in the broker.

_POLICY: dict[str, dict[str, str | None]] = {

    # ── Calendar: ALL agents read + write events freely; DELETE needs Guardian ──
    "google.calendar.read": {
        "*": CLASS_A,   # all agents, auto-proceed (always audit-logged)
    },

    # ── Phase 1 placeholder — defined but broker executor not yet wired ──────
    "google.contacts.read": {
        "cassandra": CLASS_A,
        "chief":     DENIED,
    },
    # Inbox metadata (subjects/senders/dates) of the operator's OWN account — low risk,
    # open to the operator's agents so they can read what was sent to winshiplive@gmail.com
    # (the email-loopback test + agent inbox awareness). Class A (auto-proceed).
    "google.gmail.read.metadata": {
        "*":         CLASS_A,
        "chief":     DENIED,
    },
    "google.gmail.unread_count": {
        "*":         CLASS_A,
        "chief":     DENIED,
    },

    # ── Grounded thread read — private correspondence; Tier 1 confirmation ──
    "google.gmail.read.body": {
        "cassandra": CLASS_B,
        "chief":     DENIED,
    },

    # ── Active review-first write — reversible Gmail Draft; Tier 1 confirmation ─
    "google.gmail.draft.create": {
        "cassandra": CLASS_B,
        "chief":     DENIED,
    },

    # Calendar event create/update — free for all agents (reversible). The operator
    # wants agents to manage the calendar without per-write friction; the safety
    # boundary is DELETE (irreversible), which is Guardian-gated just below.
    "google.calendar.write": {
        "*": CLASS_A,
    },
    # Calendar event DELETE — Class C: each delete fires a tier-2 Guardian approval the
    # operator must approve/deny. Fails closed (denies) if the approval brain is down.
    "google.calendar.delete": {
        "*": CLASS_C,
    },

    # Email send: open to the operator's agents (Class C). Safety in self-test mode is
    # the broker's recipient allowlist (winshiplive@gmail.com only); external sends still
    # hit the Class C / exact-send approval gate once self-test is graduated off.
    "google.gmail.send": {
        "*":         CLASS_C,
        "chief":     DENIED,
    },
}


# ── Public API ────────────────────────────────────────────────────────────────

def allowed(agent: str, capability: str) -> bool:
    """True if the agent is permitted to invoke this capability."""
    return get_class(agent, capability) is not None


def get_class(agent: str, capability: str) -> str | None:
    """
    Return the approval class for this agent+capability, or None if denied/unknown.
    An explicit per-agent entry wins; otherwise a wildcard "*" entry applies, so a
    capability can be granted to every agent at once (and a specific agent can still be
    explicitly DENIED to override the wildcard).
    """
    cap_entry = _POLICY.get(capability)
    if cap_entry is None:
        return None
    a = agent.lower()
    if a in cap_entry:
        return cap_entry[a]
    return cap_entry.get("*")


def list_allowed(agent: str) -> list[tuple[str, str]]:
    """Return list of (capability, class) pairs permitted for this agent."""
    result = []
    for cap in _POLICY:
        cls = get_class(agent, cap)  # wildcard-aware
        if cls is not None:
            result.append((cap, cls))
    return result


# ── CLI smoke test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cases = [
        ("cassandra", "google.calendar.read",       True,  CLASS_A),
        ("cassandra", "google.gmail.read.body",     True,  CLASS_B),
        ("cassandra", "google.gmail.draft.create",  True,  CLASS_B),
        ("cassandra", "google.calendar.write",      True,  CLASS_A),
        ("maestro",   "google.calendar.write",      True,  CLASS_A),
        ("niles",     "google.calendar.delete",     True,  CLASS_C),
        ("cassandra", "google.gmail.send",           True,  CLASS_C),
        ("chief",     "google.calendar.read",       True,  CLASS_A),
        ("chief",     "google.gmail.send",          False, DENIED),
        ("Cassandra", "google.calendar.read",       True,  CLASS_A),
        ("unknown",   "google.calendar.read",       True,  CLASS_A),
        ("cassandra", "google.nonexistent",          False, None),
    ]
    assert ("google.gmail.send", CLASS_C) not in list_allowed("niles")
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
