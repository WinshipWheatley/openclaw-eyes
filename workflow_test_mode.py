"""Workflow Test Mode — Phase 1: the send-edge gear-shift.

One decision at the outward edge, so the SAME executors serve both production and test:
  - PRODUCTION + SEND_HOLD active  -> BLOCK_SEND_HOLD (the master kill-switch, enforced at the
    broker/executor, the last gate before the provider call).
  - TEST_LIVE / TEST_DRY_RUN       -> TEST_REDIRECT_FLAG: redirect the send to the operator's own
    inbox and stamp the test flag. Nothing can reach anyone else, so SEND_HOLD need not hard-block.
  - PRODUCTION + no SEND_HOLD       -> PROCEED to the normal approval gates (unchanged).

This is deliberately a pure decision function + a pure param transform, so it is fully testable and
carries no side effects. The broker/executor consult it; they do not re-implement the policy.

Design refs: Operator/FABLE-WORKFLOW-TEST-MODE-SPEC-20260703.md.
"""

from __future__ import annotations

from typing import Any, Mapping

from global_run_mode_context import PRODUCTION, TEST_DRY_RUN, TEST_LIVE, TEST_MARKER

# Dispositions
PROCEED = "proceed"                       # normal path / normal gates
BLOCK_SEND_HOLD = "block_send_hold"       # production + SEND_HOLD -> absolute block
TEST_REDIRECT_FLAG = "test_redirect_flag" # test mode -> redirect to operator + flag

_TEST_MODES = frozenset({TEST_LIVE, TEST_DRY_RUN})

# Send-class = capabilities that emit something OUTWARD (a real external effect). SEND_HOLD and the
# test-mode redirect apply to these. Reads / internal ops are not send-class.
_SEND_CLASS_CAPABILITIES = frozenset({"google.gmail.send"})

_TEST_SUBJECT_TAG = "[OPENCLAW TEST]"


def is_send_class_capability(capability: str) -> bool:
    return str(capability or "") in _SEND_CLASS_CAPABILITIES


def resolve_send_disposition(*, run_mode: str, send_hold_active: bool, is_send_class: bool) -> str:
    """Decide what happens to a send, given the run mode and the SEND_HOLD state."""
    if not is_send_class:
        return PROCEED
    if run_mode in _TEST_MODES:
        # Test mode is the gear-shift: the send is made safe (redirected + flagged), not blocked.
        return TEST_REDIRECT_FLAG
    if send_hold_active:
        return BLOCK_SEND_HOLD
    return PROCEED


def apply_test_mode_send(
    params: Mapping[str, Any],
    *,
    operator_inbox: str,
    test_run_id: str,
) -> dict[str, Any]:
    """Return a COPY of ``params`` made safe for a test-mode send: recipient hard-locked to the
    operator's own inbox (no cc/bcc can reach anyone else) and the payload flagged as test-only."""
    out = dict(params)
    out["to"] = operator_inbox
    out.pop("cc", None)
    out.pop("bcc", None)

    subject = str(out.get("subject") or "")
    if _TEST_SUBJECT_TAG not in subject:
        subject = f"{_TEST_SUBJECT_TAG} {subject}".strip()
    out["subject"] = subject

    body = str(out.get("body") or "")
    if TEST_MARKER not in body:
        body = f"{TEST_MARKER}\nTest run: {test_run_id}\n\n{body}"
    elif test_run_id and test_run_id not in body:
        body = f"{body}"  # marker already present; leave the existing header intact
    out["body"] = body
    return out


__all__ = [
    "PROCEED", "BLOCK_SEND_HOLD", "TEST_REDIRECT_FLAG",
    "is_send_class_capability", "resolve_send_disposition", "apply_test_mode_send",
]
