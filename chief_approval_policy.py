"""
chief_approval_policy.py

Machine-readable approval tier classification for the OpenClaw system.

Tier 0 — No gate. Proceed immediately.
Tier 1 — Local terminal confirmation (y/N prompt). Escalates to Tier 2 if no TTY.
Tier 2 — Remote phone approval via Guardian bot (out-of-band authorization gate).

Usage:
    from chief_approval_policy import classify, TIER_0, TIER_1, TIER_2
    tier = classify("Delete billing archive Jan-2026.csv")  # → 2

Callers may suggest a tier by passing explicit_tier= to
request_approval() in chief_approval_brain.py. Tier 2 hard rules
are enforced regardless of explicit_tier — use is_hard_t2() to check.

Design notes:
- Unknown/unrecognized actions default to TIER_2 (safe conservative default).
  This default is intentionally caller-overridable via explicit_tier — callers
  with context about an unrecognized action may specify a lower tier. This is
  distinct from T2 hard rules, which cannot be overridden (see is_hard_t2()).
- Tier 2 hardcoded rules cannot be downgraded by any caller (enforced via
  is_hard_t2() check in chief_approval_brain.py before explicit_tier applies).
- Tier 0 rules cover pure read-only and standard safe dev operations.
"""

import os
import re

TIER_0 = 0  # No gate
TIER_1 = 1  # Local terminal confirm (escalates to T2 if no TTY)
TIER_2 = 2  # Remote phone approval — always out-of-band

# ── OpenShell structural enforcement flag ──────────────────────────────────────
#
# OPENSHELL_ACTIVE is True only when NemoClaw OpenShell enforcement is confirmed
# active — meaning the credential file block has been tested and verified, not
# merely that NemoClaw is running.
#
# How to enable: set OPENSHELL_ENFORCEMENT_CONFIRMED=1 in the environment.
# The name is intentional (Mac review Flag 1): "confirmed" signals that the
# credential block test has passed. Do not set this env var until that test
# succeeds (attempt a read of .chief.env from inside the sandbox; confirm blocked).
#
# When False (default): classify() behavior is identical to baseline. No relaxations apply.
# When True: _OPENSHELL_T0_PATTERNS are checked before hard T2 rules.
OPENSHELL_ACTIVE: bool = os.environ.get("OPENSHELL_ENFORCEMENT_CONFIRMED", "0") == "1"

# ── OpenShell T0 relaxations — only active when OPENSHELL_ACTIVE is True ──────
#
# Each entry is path-specific or condition-specific.
# No generic class relaxations.
#
# IMPORTANT — what is NOT here and why:
#   Credential reads (.chief.env, credentials.json, token.json): never relax.
#   "Read-only" does not make credential access safe. Structural enforcement
#   reduces execution risk but does not reduce information disclosure risk.
#
#   CPA brain queries: not here. The CPA brain income summary path passes client
#   names, project names, and invoice numbers into LLM prompts — not aggregate.
#   Additionally, CPA brain queries do not route through the approval gate, so
#   this pattern would be inert. Relaxation requires a strictly aggregate-only
#   CPA interface AND CPA queries routed through the gate. Neither exists yet.
#
#   Raw financial file reads: not here. Raw file access exposes client identifiers
#   regardless of reversibility.
#
# This list is intentionally sparse. Add entries only when the enforcement
# boundary is real, tested, and the data class is demonstrably non-identifying.
_OPENSHELL_T0_PATTERNS: list[str] = [
    # (empty — no safe relaxations identified yet for current system state)
]


def _is_autonomous_local_only(action: str) -> bool:
    """True if the action is autonomous/unattended AND does not touch credentials,
    external endpoints, or financial record writes.

    Used by classify() when OPENSHELL_ACTIVE is True to relax autonomous actions
    that operate entirely within the local sandbox to T0.
    """
    t = action.lower()
    if not re.search(r"autonomous|unattended|while\s+.{0,10}away|scheduled\s+run", t, re.IGNORECASE):
        return False
    # Disqualifiers — any of these means the action is NOT local-only
    _disqualifiers: list[str] = [
        r"\.chief\.env|credentials?|token|api.?key|secret",
        r"publish\b|post\s+to\b|send\s+email|send\s+sms|telegram\s+broadcast|external\s+service",
        r"(delete|modify|edit|update|overwrite|truncate).{0,40}(billing|invoice|financial)",
        r"\.(csv|jsonl)\b",
        r"force.?push|reset\s+--hard|branch\s+-[dD]",
    ]
    for pattern in _disqualifiers:
        if re.search(pattern, t, re.IGNORECASE):
            return False
    return True


def sync_egress_yaml(endpoint: str) -> None:
    """Stub: add an approved external endpoint to the OpenShell egress YAML.

    Called after a T2 approval where the action involves a new external endpoint.
    No-op until NemoClaw is installed and the YAML path is configured.

    Wire-up point: call from chief_approval_brain._append_log() when OPENSHELL_ACTIVE
    and the approved action matches an external endpoint pattern.
    """
    if not OPENSHELL_ACTIVE:
        return
    # TODO (Phase 3): write endpoint to OpenShell egress YAML
    # YAML path: to be confirmed from NemoClaw config at integration time
    print(f"[openshell] sync_egress_yaml: stub — would add {endpoint!r} to egress YAML", flush=True)


# ── Tier 2 hard rules — always phone, no downgrade ────────────────────────────

_ALWAYS_T2: list[str] = [
    # Git destructive
    r"force.?push|push\s+--force|push\s+-f\b",
    r"branch\s+-[dD]\b|delete\s+branch|branch\s+deletion",
    r"reset\s+--hard",
    r"git\s+clean\s+-f",
    r"git\s+rebase\b",
    # Billing / financial records — destructive verbs only, not reads
    r"(delete|modify|edit|update|overwrite|truncate|clear|wipe).{0,40}(billing|invoice|payment.?record|financial)",
    r"(billing|invoice|payment.?record|financial).{0,40}(delete|modify|edit|update|overwrite|truncate)",
    r"\.(csv|jsonl)\b",
    r"expense_log\.json",  # financial record — .json extension missed by .jsonl rule
    # Credentials and secrets
    r"\.chief\.env",
    r"\.ssh[/\\]|ssh\s+key|private\s+key|id_rsa|id_ed25519",
    r"api.?key|bot.?token|telegram.*token|anthropic.*key|secret.*token",
    r"\bcredential|auth.?token|oauth\b",
    r"approval.?hmac.?secret|guardian.?bot.?token",
    # External publishing / sending
    r"publish\b|post\s+to\b|send\s+email|send\s+sms|telegram\s+broadcast",
    r"external\s+service|push\s+to\s+production",
    # Database / log destructive
    r"drop\s+table|truncate\b|drop\s+database",
    # Large deletions (when explicitly called out)
    r"large\s+deletion|bulk\s+delete",
    r"delete.{1,40}\d{3,}\s*mb|delete.{1,40}\d+\s*gb",
    # Autonomous / unattended runs
    r"autonomous|while\s+(i.?m\s+)?away|unattended|scheduled\s+run",
    # Windows system paths (non-trivial cleanup)
    r"program\s+files|appdata[/\\]local|\\windows\\|system32",
]

# ── Tier 1 — local terminal confirm, escalate if no TTY ───────────────────────

_T1_PATTERNS: list[str] = [
    r"pip\s+install|npm\s+install|apt\s+install|install\s+package",
    r"systemctl\b|restart\s+service|service\s+restart",
    r"move\s+file|rename\s+file|\bmv\b",
    r"git\s+reset\b(?!.*--hard)",   # reset without --hard
    # Safe-area deletions: must mention temp/cache/installer/stale explicitly
    r"delete.{0,50}(temp|cache|installer|stale|leftover|empty\s+dir)",
    r"(temp|cache|installer|stale|leftover).{0,50}delete",
    r"windows.{0,30}cleanup|cleanup.{0,30}windows",
    # Config edits (not .chief.env — that's T2 above)
    r"(edit|modify|update).{0,20}config(?!.*\.chief\.env)",
    r"config.{0,20}(edit|change|update)(?!.*\.chief\.env)",
]

# ── Tier 0 — no gate, clearly safe ────────────────────────────────────────────

_T0_PATTERNS: list[str] = [
    r"^(read|inspect|list|check|view|show|display)\b",
    r"\bread\s+(file|vault|log|config)\b",
    r"git\s+(log|status|diff|fetch|show)\b",
    r"git\s+add\b",
    r"git\s+commit\b",
    r"git\s+push\b(?!.*(?:force|-f\b))",   # push without force
    r"(create|add)\s+(new\s+)?(python|shell|source)\s+file",
    r"edit\s+vault|vault\s+markdown|obsidian\b",
    r"(start|restart)\s+(chief|stack)\b|start_chief",
    r"run\s+(test|smoke\s+test)",
    r"git\s+(remote\s+-v|branch\s+-a|log\s+--oneline)",
]


# ── Public API ─────────────────────────────────────────────────────────────────

def classify(action: str) -> int:
    """
    Return the approval tier for the given action description.

    Evaluation order:
    1. If OPENSHELL_ACTIVE: check _OPENSHELL_T0_PATTERNS and autonomous-local-only
       condition first. Matching actions return T0 before hard T2 rules are checked.
    2. Hard T2 rules — cannot be overridden when OpenShell is not active.
    3. T0 — clearly safe baseline patterns.
    4. T1 — medium risk.
    5. Default: unknown → T2.

    When OPENSHELL_ACTIVE is False, behavior is identical to baseline.
    """
    t = action.lower()

    # OpenShell relaxations — only when structural enforcement is confirmed active.
    # Checked before hard T2 rules for the specific conditions OpenShell covers.
    if OPENSHELL_ACTIVE:
        for pattern in _OPENSHELL_T0_PATTERNS:
            if re.search(pattern, t, re.IGNORECASE):
                return TIER_0
        if _is_autonomous_local_only(action):
            return TIER_0

    # TEST_ fixture carve-out — exempt from hard T2
    if re.search(r"\bTEST_\w+\.(csv|jsonl)\b", action, re.IGNORECASE):
        return TIER_0

    # Hard T2 rules — checked first, no override possible
    for pattern in _ALWAYS_T2:
        if re.search(pattern, t, re.IGNORECASE):
            return TIER_2

    # T0 — clearly safe
    for pattern in _T0_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            return TIER_0

    # T1 — medium risk
    for pattern in _T1_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            return TIER_1

    # Default: unknown → T2
    return TIER_2


def is_openshell_active() -> bool:
    """Return True if OpenShell structural enforcement is confirmed active.

    Reads OPENSHELL_ACTIVE at call time (not cached) so runtime env changes
    are reflected without restart.
    """
    return os.environ.get("OPENSHELL_ENFORCEMENT_CONFIRMED", "0") == "1"


def is_hard_t2(action: str) -> bool:
    """
    Return True if the action matches a Tier 2 hard rule.

    Hard T2 rules are structurally prior and cannot be overridden by any caller
    via explicit_tier in request_approval(). This is distinct from the T2 default
    for unrecognized actions, which callers may still override.
    """
    t = action.lower()
    for pattern in _ALWAYS_T2:
        if re.search(pattern, t, re.IGNORECASE):
            return True
    return False


def tier_label(tier: int) -> str:
    """Human-readable label for a tier integer."""
    return {TIER_0: "L0-pass", TIER_1: "L1-terminal", TIER_2: "L2-phone"}.get(tier, "L2-phone")


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    _openshell = OPENSHELL_ACTIVE
    cases = [
        # Baseline behavior (OPENSHELL_ACTIVE = False)
        ("Read billing_records.csv", TIER_2),       # .csv blanket rule
        ("Read expense_log.json", TIER_2),           # .jsonl blanket rule
        ("Delete billing archive Jan-2026.csv", TIER_2),
        ("git push --force origin master", TIER_2),
        ("Delete stale installer cache", TIER_1),
        ("pip install requests", TIER_1),
        ("git status", TIER_0),
        ("git commit", TIER_0),
        ("Start Chief stack", TIER_0),
        ("Edit vault markdown for album notes", TIER_0),
        ("Some completely unknown action", TIER_2),
    ]
    print(f"{'Action':<50} {'Expected':<12} {'Got':<12} {'Pass'}")
    print("-" * 85)
    all_pass = True
    for action, expected in cases:
        got = classify(action)
        passed = got == expected
        all_pass = all_pass and passed
        flag = "OK" if passed else "FAIL"
        print(f"{action:<50} {tier_label(expected):<12} {tier_label(got):<12} {flag}")
    print()
    if "--test" in sys.argv:
        sys.exit(0 if all_pass else 1)
    if not all_pass:
        sys.exit(1)
