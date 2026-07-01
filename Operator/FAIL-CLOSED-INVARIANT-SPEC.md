# Spec (for Codex): Fail-Closed Invariant — system-wide, enforced, indefinite

Status: **CODEX WORKLOAD** (big, ongoing). Opus fixed the immediate instance (the pytest-sandbox
dir_fd escape, `7f80eb55`); this is the detailed job to fix the CLASS across the whole system, for all
agents — including ones that don't exist yet — and to make it impossible to reintroduce.

Governing: this is a security sibling of the ledger doctrine's 3-layer enforcement
(`Operator/ONE-KNOWLEDGE-LEDGER-DOCTRINE.md`) and "never silently mask" — a fail-open control silently
allows the dangerous thing. Never weaken a control to pass a gate (that's how the sandbox bug got in).

## The invariant
**Every security/safety control fails CLOSED by default.** On error, unknown input, missing config, or
an un-handleable case, a control that protects something dangerous **denies / blocks / refuses /
raises** — it never allows, passes through, returns True, or skips the check. Fail-open is a defect.

## The discernment (do NOT make everything raise)
Fail-closed applies to controls where **failing open ALLOWS something dangerous**: sandbox/isolation
escape, auth/permission bypass, a gate being skipped, an external SEND / payment / money move, a PII
de-tokenization, a ledger/file mutation/delete, a SEND_HOLD bypass, a Guardian-gate skip. Non-critical
features may still degrade gracefully (fail-open is fine for a cosmetic/non-dangerous path). Test for
each finding: *if this control fails open, can something dangerous happen?* If yes → fail-closed.

## The pattern to hunt (seed: the bug just fixed)
The sandbox did `if kwargs.get("dir_fd") is not None: return self._original_os_remove(...)` — gave up
on the protection and passed through. Generalized fail-open smells:
- `except ...: return True` / `return ALLOW` in a guard/auth/gate.
- "skip the check / passthrough if <condition not met>" on a protective control.
- default-allow when config/env is missing (should default-deny).
- a control that, on an input it can't map/resolve, proceeds instead of refusing.

## The workload (4 parts)
1. **SWEEP** the system for fail-open in security/safety controls — sandbox(es), auth/permission,
   gates (Guardian/SEND_HOLD/green-gate), external-model/send/money/PII boundaries, redirect/isolation,
   file-mutation guards. Produce `Operator/CODEX-FAIL-OPEN-SWEEP-RESULT.md`: each finding with file:line,
   the dangerous-if-open assessment, and the fail-closed fix.
2. **CONVERT** each real finding to fail-closed (deny/block/refuse/raise on uncertainty), each with a
   regression test (model: `tests/test_pytest_sandbox_dir_fd_failclosed.py`). Anything ambiguous →
   flag for operator, do not blanket-raise.
3. **ENFORCE** going forward (the "for all agents whether new ones get made" part): a contract test /
   check that flags fail-open patterns in security/safety controls so NO new code from ANY agent can
   land one — structural, like the packet-ledger contract test. New agents inherit the invariant
   because the gate, not a human, holds the line.
4. **INDEFINITE** — fold the sweep into the perpetual self-knowledge / self-healing loop so it
   re-scans as the system grows; a newly-introduced fail-open becomes a flagged gap → fixed.

## Guardrails
TDD; Guardian-gated; never weaken a control to pass a gate; sweep is READ-first then fix the clear ones
and flag the ambiguous; report scope before any mass change.
