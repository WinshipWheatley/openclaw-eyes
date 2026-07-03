"""Phase 1 of Workflow Test Mode: the send-edge GEAR-SHIFT.

- Production + SEND_HOLD active  -> send is BLOCKED absolutely (kill-switch at the last gate).
- Test mode (TEST_LIVE/TEST_DRY_RUN) -> send is REDIRECTED to the operator's own inbox AND FLAGGED
  (the safe channel; SEND_HOLD does not need to hard-block because nothing reaches anyone else).
- Production, no SEND_HOLD -> PROCEED to the normal approval gates (unchanged behavior).

Same executors, one decision at the outward edge — so "works in test mode" == "works in prod".
"""

import workflow_test_mode as wtm
from global_run_mode_context import PRODUCTION, TEST_DRY_RUN, TEST_LIVE, TEST_MARKER


def test_production_send_hold_blocks_absolutely():
    d = wtm.resolve_send_disposition(run_mode=PRODUCTION, send_hold_active=True, is_send_class=True)
    assert d == wtm.BLOCK_SEND_HOLD


def test_production_no_send_hold_proceeds():
    d = wtm.resolve_send_disposition(run_mode=PRODUCTION, send_hold_active=False, is_send_class=True)
    assert d == wtm.PROCEED


def test_test_live_redirects_and_flags_even_with_send_hold():
    d = wtm.resolve_send_disposition(run_mode=TEST_LIVE, send_hold_active=True, is_send_class=True)
    assert d == wtm.TEST_REDIRECT_FLAG


def test_test_dry_run_redirects_and_flags():
    d = wtm.resolve_send_disposition(run_mode=TEST_DRY_RUN, send_hold_active=False, is_send_class=True)
    assert d == wtm.TEST_REDIRECT_FLAG


def test_non_send_class_always_proceeds():
    for mode in (PRODUCTION, TEST_LIVE, TEST_DRY_RUN):
        for hold in (True, False):
            assert wtm.resolve_send_disposition(run_mode=mode, send_hold_active=hold, is_send_class=False) == wtm.PROCEED


def test_is_send_class_capability():
    assert wtm.is_send_class_capability("google.gmail.send") is True
    assert wtm.is_send_class_capability("google.gmail.read.metadata") is False
    assert wtm.is_send_class_capability("google.calendar.read") is False


def test_apply_test_mode_send_redirects_and_flags():
    params = {"to": "attorney@example.com", "cc": "someoneelse@example.com",
              "subject": "Invoice", "body": "Please pay."}
    out = wtm.apply_test_mode_send(params, operator_inbox="winshiplive@gmail.com", test_run_id="run-123")
    # recipient hard-locked to the operator; no one else can be reached
    assert out["to"] == "winshiplive@gmail.com"
    assert not out.get("cc") and not out.get("bcc")
    # flagged so a human can never mistake it for real
    assert "[OPENCLAW TEST]" in out["subject"]
    assert TEST_MARKER in out["body"]
    assert "run-123" in out["body"]
    # original is not mutated
    assert params["to"] == "attorney@example.com"


def test_apply_test_mode_send_idempotent_flag():
    params = {"to": "x@y.com", "subject": "[OPENCLAW TEST] Invoice", "body": f"{TEST_MARKER}\nhi"}
    out = wtm.apply_test_mode_send(params, operator_inbox="winshiplive@gmail.com", test_run_id="r")
    assert out["subject"].count("[OPENCLAW TEST]") == 1
    assert out["body"].count(TEST_MARKER) == 1
