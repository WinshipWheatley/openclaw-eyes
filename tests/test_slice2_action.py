"""
test_slice2_action.py — Slice-2 action runtime tests.

All tests are SYNTHETIC:
  - NO external sends, NO network, NO Telegram.
  - SEND_HOLD / TEST_MODE are honoured: tests that simulate SEND_HOLD create a
    temp file; tests never touch the real prod path.
  - email_send_executor is NEVER registered.
  - No side effect outside a tempdir SQLite ledger + tempdir capsule store.

Run:
    cd /home/openclaw/worktrees/slice2-action
    PYTHONPATH=/home/openclaw/worktrees/slice2-action \\
        /home/openclaw/.venv/bin/python -m pytest -q tests/test_slice2_action.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _enable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCLAW_ACTION_RUNTIME", "1")


def _disable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCLAW_ACTION_RUNTIME", "0")


def _hitl_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HITL_ENABLED", "1")


def _hitl_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HITL_ENABLED", "0")


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — authority_gate unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAuthorityGate:
    """authority_gate.decide() — pure/deterministic, flag-agnostic."""

    def test_allow_synthetic_noop(self, tmp_path: Path) -> None:
        """synthetic_noop is allow-listed → ALLOW."""
        from authority_gate import decide, Verdict

        db = str(tmp_path / "ledger.db")
        decision = decide("synthetic_noop", conversation_id="conv-1", surface="synthetic_noop", db_path=db)
        assert decision.verdict == Verdict.ALLOW
        assert "synthetic_noop" in decision.reason

    def test_deny_unknown_surface(self, tmp_path: Path) -> None:
        """Unknown surface → DENY (default-deny)."""
        from authority_gate import decide, Verdict

        db = str(tmp_path / "ledger.db")
        decision = decide("totally_unknown_surface_xyz", conversation_id="conv-2",
                          surface="totally_unknown_surface_xyz", db_path=db)
        assert decision.verdict == Verdict.DENY

    def test_deny_empty_surface(self, tmp_path: Path) -> None:
        """Empty surface string → DENY (default-deny, not crash)."""
        from authority_gate import decide, Verdict

        db = str(tmp_path / "ledger.db")
        decision = decide("", conversation_id="conv-3", surface="", db_path=db)
        assert decision.verdict == Verdict.DENY

    def test_send_hold_denies_send_surface(self, tmp_path: Path) -> None:
        """SEND_HOLD file present → DENY for any send surface."""
        from authority_gate import decide, Verdict

        send_hold = tmp_path / "SEND_HOLD.md"
        send_hold.write_text("hold active")
        db = str(tmp_path / "ledger.db")

        for surface in ("email_send", "invoice_send", "sms_send"):
            decision = decide(
                surface,
                conversation_id="conv-sh",
                surface=surface,
                send_hold_path=str(send_hold),
                db_path=db,
            )
            assert decision.verdict == Verdict.DENY, f"Expected DENY for {surface} when SEND_HOLD active"
            assert "SEND_HOLD" in decision.reason

    def test_send_hold_absent_send_surface_is_hitl(self, tmp_path: Path) -> None:
        """SEND_HOLD absent → send surface gets HITL_REQUIRED (not ALLOW)."""
        from authority_gate import decide, Verdict

        absent_path = tmp_path / "no_such_hold.md"  # does not exist
        db = str(tmp_path / "ledger.db")

        decision = decide(
            "email_send",
            conversation_id="conv-hitl",
            surface="email_send",
            send_hold_path=str(absent_path),
            db_path=db,
        )
        assert decision.verdict == Verdict.HITL_REQUIRED

    def test_every_decision_recorded_to_ledger(self, tmp_path: Path) -> None:
        """Every gate decision writes to the ledger (receipt ref is non-None)."""
        from authority_gate import decide

        db = str(tmp_path / "ledger.db")

        # ALLOW
        d1 = decide("synthetic_noop", conversation_id="c1", surface="synthetic_noop", db_path=db)
        assert d1.ledger_receipt_ref is not None, "ALLOW decision should have a ledger ref"

        # DENY
        d2 = decide("bad_surface", conversation_id="c2", surface="bad_surface", db_path=db)
        assert d2.ledger_receipt_ref is not None, "DENY decision should have a ledger ref"

    def test_decision_carries_conversation_id(self, tmp_path: Path) -> None:
        """AuthorityDecision echoes the conversation_id for correlation."""
        from authority_gate import decide

        db = str(tmp_path / "ledger.db")
        decision = decide("synthetic_noop", conversation_id="my-conv-id",
                          surface="synthetic_noop", db_path=db)
        assert decision.conversation_id == "my-conv-id"


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — no-regression (flag OFF)
# ─────────────────────────────────────────────────────────────────────────────


class TestNoRegressionFlagOff:
    """With OPENCLAW_ACTION_RUNTIME=0 the live path is byte-identical to base."""

    def test_synthetic_noop_not_in_executors_when_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With flag OFF, synthetic_noop must NOT be in chief_compose.EXECUTORS."""
        _disable_flag(monkeypatch)

        # Re-import to pick up env state.
        import importlib
        import chief_compose
        importlib.reload(chief_compose)

        # action_runtime.register_synthetic_executor() must be a no-op when off.
        import action_runtime
        importlib.reload(action_runtime)
        action_runtime.register_synthetic_executor()

        assert "synthetic_noop" not in chief_compose.EXECUTORS, (
            "synthetic_noop must NOT be registered when OPENCLAW_ACTION_RUNTIME=0"
        )

    def test_email_send_never_registered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """email_send must NEVER appear in EXECUTORS regardless of flag state."""
        import importlib
        import chief_compose
        importlib.reload(chief_compose)

        assert "email_send" not in chief_compose.EXECUTORS

    def test_dispatch_raises_when_flag_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dispatch_action() raises RuntimeError when flag is OFF."""
        _disable_flag(monkeypatch)

        from action_runtime import dispatch_action

        with pytest.raises(RuntimeError):
            dispatch_action(
                surface="synthetic_noop",
                packet_id="pkt-off",
                conversation_id="conv-off",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — e2e (flag ON): ALLOW → execute → correlated receipt → capsule
# ─────────────────────────────────────────────────────────────────────────────


class TestE2EFlagOn:
    """End-to-end synthetic action loop with OPENCLAW_ACTION_RUNTIME=1."""

    def test_synthetic_action_full_loop(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """
        synthetic_noop → authority_gate ALLOW → executor → receipt carries
        conversation_id+package_id → capsule.recent_receipt_refs populated.

        NO side effect, NO external call.
        """
        _enable_flag(monkeypatch)

        db = str(tmp_path / "ledger.db")
        capsule_store_dir = str(tmp_path / "capsules")
        os.makedirs(capsule_store_dir, exist_ok=True)

        conversation_id = "e2e-conv-001"
        package_id = "pkg-synthetic-001"
        packet_id = "pkt-e2e-001"

        from action_runtime import dispatch_action, _action_runtime_enabled

        assert _action_runtime_enabled(), "Flag must be ON for e2e test"

        result = dispatch_action(
            surface="synthetic_noop",
            packet_id=packet_id,
            conversation_id=conversation_id,
            package_id=package_id,
            db_path=db,
            capsule_store_dir=capsule_store_dir,
        )

        # Verdict
        assert result["verdict"] == "ALLOW", f"Expected ALLOW, got: {result}"
        assert result["receipt"] is not None

        # Receipt carries conversation_id + package_id in meta
        receipt_meta = result["receipt"]["meta"]
        assert receipt_meta.get("conversation_id") == conversation_id, (
            "receipt.meta must carry conversation_id"
        )
        assert receipt_meta.get("package_id") == package_id, (
            "receipt.meta must carry package_id"
        )

        # Receipt is from synthetic_noop (no real action)
        assert result["receipt"]["surface"] == "synthetic_noop"
        assert result["receipt"]["ok"] is True
        assert receipt_meta.get("synthetic") is True
        assert receipt_meta.get("no_side_effect") is True

        # Capsule recent_receipt_refs populated
        assert result["capsule_updated"] is True

        import conversation_capsule as cc
        store = cc.ConversationCapsuleStore(store_dir=capsule_store_dir)
        capsule = store.load("op1", "action_runtime", conversation_id, "synthetic")
        assert capsule is not None, "Capsule should have been written"
        assert any(
            conversation_id in ref and packet_id in ref
            for ref in capsule.recent_receipt_refs
        ), f"Expected receipt ref in capsule.recent_receipt_refs; got: {capsule.recent_receipt_refs}"

    def test_synthetic_noop_registered_when_flag_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With flag ON, register_synthetic_executor() adds synthetic_noop."""
        _enable_flag(monkeypatch)

        import importlib
        from action_runtime import register_synthetic_executor
        import chief_compose

        register_synthetic_executor()
        assert "synthetic_noop" in chief_compose.EXECUTORS

    def test_no_email_send_registered_when_flag_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even with flag ON, email_send must never appear in EXECUTORS."""
        _enable_flag(monkeypatch)

        from action_runtime import register_synthetic_executor
        import chief_compose

        register_synthetic_executor()
        assert "email_send" not in chief_compose.EXECUTORS

    def test_correlated_receipt_meta(self) -> None:
        """correlated_receipt() injects conversation_id+package_id into meta."""
        from compose_contract import ExecutionReceipt
        from action_runtime import correlated_receipt

        base = ExecutionReceipt(
            packet_id="pkt-meta",
            surface="synthetic_noop",
            ok=True,
            meta={"existing_key": "existing_value"},
        )
        wrapped = correlated_receipt(base, conversation_id="cv1", package_id="pkg1")
        assert wrapped.meta["conversation_id"] == "cv1"
        assert wrapped.meta["package_id"] == "pkg1"
        # Existing key preserved
        assert wrapped.meta["existing_key"] == "existing_value"
        # Original unchanged (frozen dataclass)
        assert "conversation_id" not in base.meta

    def test_deny_blocks_execution(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """DENY from authority_gate → executor is never called."""
        _enable_flag(monkeypatch)

        db = str(tmp_path / "ledger.db")

        from action_runtime import dispatch_action

        result = dispatch_action(
            surface="totally_unknown_surface_xyz",
            packet_id="pkt-deny",
            conversation_id="conv-deny",
            db_path=db,
        )

        assert result["verdict"] == "DENY"
        assert result["receipt"] is None
        assert result["capsule_updated"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — HITL path (flag ON): HITL_REQUIRED → WAITING, no execute
# ─────────────────────────────────────────────────────────────────────────────


class TestHITLPath:
    """HITL_REQUIRED surfaces create a pending action and do NOT execute."""

    def test_hitl_required_surface_no_execute(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """email_send (no SEND_HOLD) → HITL_REQUIRED → not executed."""
        _enable_flag(monkeypatch)
        _hitl_off(monkeypatch)  # HITL store disabled → action_id will be None

        absent_send_hold = tmp_path / "no_hold.md"  # does not exist
        db = str(tmp_path / "ledger.db")

        from action_runtime import dispatch_action

        result = dispatch_action(
            surface="email_send",
            packet_id="pkt-hitl",
            conversation_id="conv-hitl",
            send_hold_path=str(absent_send_hold),
            db_path=db,
        )

        assert result["verdict"] == "HITL_REQUIRED"
        # Executor was NOT called → no receipt
        assert result["receipt"] is None
        # Capsule was NOT updated
        assert result["capsule_updated"] is False

    def test_hitl_required_with_store_creates_waiting(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """With HITL_ENABLED=1, HITL_REQUIRED creates a WAITING_FOR_APPROVAL entry."""
        _enable_flag(monkeypatch)
        _hitl_on(monkeypatch)

        # Point HITL store to temp path to avoid touching real /mnt/c.
        hitl_store = tmp_path / "hitl_pending_actions.json"
        hitl_audit = tmp_path / "hitl_audit.jsonl"
        monkeypatch.setattr("hitl_pending_action._STORE_FILE", hitl_store)
        monkeypatch.setattr("hitl_pending_action._AUDIT_FILE", hitl_audit)

        absent_send_hold = tmp_path / "no_hold.md"
        db = str(tmp_path / "ledger.db")

        from action_runtime import dispatch_action
        from hitl_pending_action import list_pending_actions, WAITING_FOR_APPROVAL

        result = dispatch_action(
            surface="email_send",
            packet_id="pkt-hitl-store",
            conversation_id="conv-hitl-store",
            send_hold_path=str(absent_send_hold),
            db_path=db,
        )

        assert result["verdict"] == "HITL_REQUIRED"
        assert result["receipt"] is None

        # A pending action in WAITING state should exist.
        pending = list_pending_actions(status=WAITING_FOR_APPROVAL)
        assert len(pending) >= 1, "Expected at least one WAITING_FOR_APPROVAL pending action"
        action_ids = [p["action_id"] for p in pending]
        assert result["hitl_action_id"] in action_ids


# ─────────────────────────────────────────────────────────────────────────────
# Section 5 — SEND_HOLD blocks send surfaces (e2e, flag ON)
# ─────────────────────────────────────────────────────────────────────────────


class TestSendHoldE2E:
    """With SEND_HOLD present, any send surface is DENY even with flag ON."""

    def test_send_hold_active_denies_email_send(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _enable_flag(monkeypatch)

        send_hold = tmp_path / "SEND_HOLD.md"
        send_hold.write_text("hold active")
        db = str(tmp_path / "ledger.db")

        from action_runtime import dispatch_action

        result = dispatch_action(
            surface="email_send",
            packet_id="pkt-sh-email",
            conversation_id="conv-sh",
            send_hold_path=str(send_hold),
            db_path=db,
        )

        assert result["verdict"] == "DENY"
        assert result["receipt"] is None
        assert "SEND_HOLD" in result["reason"]
