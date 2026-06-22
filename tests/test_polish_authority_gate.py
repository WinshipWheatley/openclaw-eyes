"""tests/test_polish_authority_gate.py — Tests for the polish loop authority gate.

Tests cover:
1. Authorised agent within its lane → allowed.
2. Unauthorised agent (no matching agent_id) → rejected (fail closed).
3. Missing / malformed agent_id → rejected (fail closed).
4. Consequence hard floor: R3/R4 from a low-authority agent → rejected.
5. R4 is NEVER autonomous regardless of authority level.
6. Blocked output_kind → rejected.
7. Orchestrator wiring: rejected task is NOT promoted; allowed task IS promoted.
8. record_rejection: stdout emission without ledger.
9. Inferred consequence from action/output_kind keywords.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Path setup — resolve the worktree root so both authority_gate and orchestrator
# imports work without installing the package.
# ---------------------------------------------------------------------------

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
LOOP_DIR = WORKTREE_ROOT / "polish_loop"

for _p in (str(WORKTREE_ROOT), str(LOOP_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from authority_gate import check_task_authority, record_rejection  # type: ignore[import]

# ---------------------------------------------------------------------------
# Mock registry — does NOT touch any SQLite database
# ---------------------------------------------------------------------------

MOCK_REGISTRY = [
    {
        "agent_id": "chief",
        "authority_level": "request_only",
        "blocked_output_kinds": [
            "direct_execution",
            "approval_decision",
            "truth_promotion",
            "file_move",
            "file_delete",
            "client_deployment",
        ],
        "status": "active_registry",
    },
    {
        "agent_id": "cassandra",
        "authority_level": "advisory_only",
        "blocked_output_kinds": [
            "external_send",
            "approval_decision",
            "direct_execution",
            "truth_promotion",
            "invoice_paid_mark",
            "external_ledger_mutation",
        ],
        "status": "active_registry",
    },
    {
        "agent_id": "guardian",
        "authority_level": "advisory_only",
        "blocked_output_kinds": [
            "direct_execution",
            "secret_disclosure",
            "policy_mutation_without_approval",
        ],
        "status": "active_registry",
    },
    {
        "agent_id": "future_agent",
        "authority_level": "future_gated",
        "blocked_output_kinds": [],
        "status": "future_gated",
    },
    {
        "agent_id": "deprecated_agent",
        "authority_level": "advisory_only",
        "blocked_output_kinds": [],
        "status": "deprecated",
    },
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def gate(task: dict[str, Any]) -> dict[str, Any]:
    """Call check_task_authority with the mock registry."""
    return check_task_authority(task, registry=MOCK_REGISTRY)


# ---------------------------------------------------------------------------
# 1. Authorised agent within its lane
# ---------------------------------------------------------------------------


class TestAuthorisedAgent:
    def test_chief_allowed_for_r0(self):
        result = gate({"agent_id": "chief", "consequence": "R0"})
        assert result["allowed"] is True
        assert "chief" in result["reason"]

    def test_chief_allowed_for_r1(self):
        result = gate({"agent_id": "chief", "consequence": "R1"})
        assert result["allowed"] is True

    def test_chief_allowed_for_r2(self):
        result = gate({"agent_id": "chief", "consequence": "R2"})
        assert result["allowed"] is True

    def test_cassandra_allowed_for_r0(self):
        result = gate({"agent_id": "cassandra", "consequence": "R0"})
        assert result["allowed"] is True

    def test_cassandra_allowed_for_r1(self):
        result = gate({"agent_id": "cassandra", "consequence": "R1"})
        assert result["allowed"] is True

    def test_allowed_result_has_required_fields(self):
        result = gate({"agent_id": "chief", "consequence": "R1"})
        assert "allowed" in result
        assert "reason" in result
        assert "required_tier" in result
        assert isinstance(result["reason"], str)
        assert len(result["reason"]) > 0

    def test_case_insensitive_agent_id(self):
        result = gate({"agent_id": "CHIEF", "consequence": "R0"})
        assert result["allowed"] is True

    def test_case_insensitive_consequence(self):
        result = gate({"agent_id": "chief", "consequence": "r0"})
        # "r0" is not a known tier (expects "R0") — gate should fail closed
        # on unrecognised consequence if we normalise, or we test the real behaviour.
        # The gate normalises: consequence = raw.strip().upper() → "R0"
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# 2. Unauthorised agent (unknown agent_id)
# ---------------------------------------------------------------------------


class TestUnauthorisedAgent:
    def test_unknown_agent_rejected(self):
        result = gate({"agent_id": "rogue_agent_xyz", "consequence": "R0"})
        assert result["allowed"] is False
        assert "not found in registry" in result["reason"]

    def test_unknown_agent_rejected_r1(self):
        result = gate({"agent_id": "phantom", "consequence": "R1"})
        assert result["allowed"] is False

    def test_rejected_result_has_all_fields(self):
        result = gate({"agent_id": "no_such_agent"})
        assert result["allowed"] is False
        assert isinstance(result["reason"], str)
        assert result["required_tier"] is None or isinstance(result["required_tier"], str)


# ---------------------------------------------------------------------------
# 3. Fail-closed: missing / malformed agent_id
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_missing_agent_id_rejected(self):
        result = gate({"consequence": "R0"})
        assert result["allowed"] is False
        assert "agent_id" in result["reason"]

    def test_none_agent_id_rejected(self):
        result = gate({"agent_id": None, "consequence": "R0"})
        assert result["allowed"] is False

    def test_empty_string_agent_id_rejected(self):
        result = gate({"agent_id": "", "consequence": "R0"})
        assert result["allowed"] is False

    def test_whitespace_agent_id_rejected(self):
        result = gate({"agent_id": "   ", "consequence": "R0"})
        assert result["allowed"] is False

    def test_not_a_dict_rejected(self):
        result = check_task_authority("not_a_dict", registry=MOCK_REGISTRY)  # type: ignore[arg-type]
        assert result["allowed"] is False
        assert "not a dict" in result["reason"]

    def test_empty_dict_rejected(self):
        result = gate({})
        assert result["allowed"] is False

    def test_future_gated_status_rejected(self):
        """Agents with status=future_gated cannot run tasks."""
        result = gate({"agent_id": "future_agent", "consequence": "R0"})
        assert result["allowed"] is False
        assert "future_gated" in result["reason"]

    def test_deprecated_status_rejected(self):
        """Agents with status=deprecated cannot run tasks."""
        result = gate({"agent_id": "deprecated_agent", "consequence": "R0"})
        assert result["allowed"] is False
        assert "deprecated" in result["reason"]

    def test_unrecognised_consequence_tier_rejected(self):
        result = gate({"agent_id": "chief", "consequence": "R99"})
        assert result["allowed"] is False
        assert "unrecognised consequence tier" in result["reason"]

    def test_registry_exception_rejected(self):
        """Registry lookup that raises an exception → fail closed."""
        def broken_registry_lookup(agent_id, registry):
            raise RuntimeError("database exploded")

        import authority_gate as _ag
        with patch.object(_ag, "_lookup_agent", side_effect=RuntimeError("database exploded")):
            result = gate({"agent_id": "chief", "consequence": "R0"})
        assert result["allowed"] is False
        assert "gate_error" in result["reason"]


# ---------------------------------------------------------------------------
# 4. Consequence hard floor: R3 from low-authority agent
# ---------------------------------------------------------------------------


class TestConsequenceFloor:
    def test_advisory_only_blocked_for_r3(self):
        """Cassandra is advisory_only — cannot run R3 tasks."""
        result = gate({"agent_id": "cassandra", "consequence": "R3"})
        assert result["allowed"] is False
        assert "R3" in result["reason"] or "insufficient" in result["reason"]

    def test_advisory_only_blocked_for_r2(self):
        """advisory_only agents (cassandra) are blocked from R2 tasks."""
        result = gate({"agent_id": "cassandra", "consequence": "R2"})
        assert result["allowed"] is False
        assert "insufficient" in result["reason"] or "R2" in result["reason"]

    def test_request_only_blocked_for_r3(self):
        """chief is request_only — cannot run R3 tasks autonomously."""
        result = gate({"agent_id": "chief", "consequence": "R3"})
        assert result["allowed"] is False
        assert "R3" in result["reason"] or "insufficient" in result["reason"]

    def test_required_tier_present_on_rejection(self):
        result = gate({"agent_id": "cassandra", "consequence": "R3"})
        assert result["allowed"] is False
        assert result["required_tier"] is not None

    def test_consequence_floor_is_not_discounted_by_output_kind(self):
        """
        Even if the task has an 'allowed' output_kind, a high-consequence task
        from a low-authority agent must still be rejected.
        """
        result = gate({
            "agent_id": "cassandra",
            "consequence": "R3",
            "output_kind": "summary",  # allowed output for cassandra
        })
        assert result["allowed"] is False


# ---------------------------------------------------------------------------
# 5. R4 hard floor — NEVER autonomous regardless of authority
# ---------------------------------------------------------------------------


class TestR4HardFloor:
    def test_r4_rejected_for_advisory_only(self):
        result = gate({"agent_id": "cassandra", "consequence": "R4"})
        assert result["allowed"] is False
        assert "R4" in result["reason"]

    def test_r4_rejected_for_request_only(self):
        result = gate({"agent_id": "chief", "consequence": "R4"})
        assert result["allowed"] is False
        assert "R4" in result["reason"]

    def test_r4_hard_floor_reason_mentions_operator(self):
        result = gate({"agent_id": "chief", "consequence": "R4"})
        assert result["allowed"] is False
        reason = result["reason"].lower()
        assert "operator" in reason or "approval" in reason or "hard floor" in reason

    def test_r4_rejected_even_with_approval_required_registry(self):
        """Add a hypothetical high-authority agent — R4 still blocked."""
        high_auth_registry = [
            {
                "agent_id": "super_agent",
                "authority_level": "approval_required",
                "blocked_output_kinds": [],
                "status": "active_registry",
            }
        ]
        result = check_task_authority(
            {"agent_id": "super_agent", "consequence": "R4"},
            registry=high_auth_registry,
        )
        assert result["allowed"] is False
        assert "R4" in result["reason"]


# ---------------------------------------------------------------------------
# 6. Blocked output_kind
# ---------------------------------------------------------------------------


class TestBlockedOutputKind:
    def test_cassandra_external_send_blocked(self):
        result = gate({
            "agent_id": "cassandra",
            "consequence": "R1",
            "output_kind": "external_send",
        })
        assert result["allowed"] is False
        assert "blocked" in result["reason"].lower() or "external_send" in result["reason"]

    def test_chief_direct_execution_blocked(self):
        result = gate({
            "agent_id": "chief",
            "consequence": "R1",
            "output_kind": "direct_execution",
        })
        assert result["allowed"] is False

    def test_cassandra_summary_allowed(self):
        """'summary' is in cassandra's allowed_output_kinds — not blocked."""
        result = gate({
            "agent_id": "cassandra",
            "consequence": "R1",
            "output_kind": "summary",
        })
        assert result["allowed"] is True

    def test_unknown_output_kind_allowed(self):
        """An output_kind not explicitly blocked passes the gate."""
        result = gate({
            "agent_id": "cassandra",
            "consequence": "R0",
            "output_kind": "some_benign_output",
        })
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# 7. Consequence inference from keywords
# ---------------------------------------------------------------------------


class TestConsequenceInference:
    def test_money_keyword_infers_r4(self):
        result = gate({
            "agent_id": "chief",
            "action": "process money transfer",
        })
        assert result["allowed"] is False
        # R4 hard floor should be the reason
        assert "R4" in result["reason"]

    def test_external_send_keyword_infers_r3(self):
        """external_send keyword → R3 → chief (request_only) blocked."""
        result = gate({
            "agent_id": "chief",
            "action": "trigger external_send to partner",
        })
        assert result["allowed"] is False

    def test_send_keyword_infers_r3(self):
        result = gate({
            "agent_id": "cassandra",
            "action": "send a summary email",
        })
        assert result["allowed"] is False

    def test_no_keywords_infers_r2(self):
        """No matching keywords → inferred R2; advisory_only agent blocked."""
        result = gate({
            "agent_id": "cassandra",
            # No consequence, no keywords → inferred R2
        })
        assert result["allowed"] is False  # advisory_only cannot do R2

    def test_explicit_r0_overrides_inference(self):
        """Explicit consequence=R0 is trusted even if action has no risky keywords."""
        result = gate({
            "agent_id": "cassandra",
            "consequence": "R0",
            "action": "generate a summary of receipts",
        })
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# 8. Orchestrator wiring — rejected task NOT promoted; builder not called
# ---------------------------------------------------------------------------


class TestOrchestratorWiring:
    """
    Test that orchestrator.handle_idle() calls the authority gate before
    promoting a task and does NOT promote rejected tasks.

    We import orchestrator in this class only, patching all file-system
    side-effects to keep tests hermetic.
    """

    def _make_task_content(self, agent_id: str | None = "chief", consequence: str | None = "R1") -> str:
        lines = ["title: test-task-001", "goal: test the gate"]
        if agent_id is not None:
            lines.append(f"agent_id: {agent_id}")
        if consequence is not None:
            lines.append(f"consequence: {consequence}")
        return "\n".join(lines) + "\n"

    def test_rejected_task_not_promoted(self, tmp_path):
        """A task from an unknown agent is rejected; task.md is NOT written."""
        import orchestrator as orch

        queue_dir = tmp_path / "tasks"
        queue_dir.mkdir()
        task_file = queue_dir / "bad-task.md"
        # rogue agent not in any registry
        task_file.write_text(
            "title: bad-task\ngoal: evil\nagent_id: rogue_agent_xyz\nconsequence: R1\n"
        )

        task_md = tmp_path / "task.md"
        status_file = tmp_path / "status.json"
        status_file.write_text('{"status": "idle", "task_name": "?"}')

        original_loop_dir = orch.LOOP_DIR
        original_task_md = orch.TASK_MD
        original_suppress = orch._TEST_SUPPRESS_FILE_LOGS
        original_disable_idle = orch._TEST_DISABLE_IDLE_AUTOLAUNCH
        original_disable_gate = orch._TEST_DISABLE_AUTHORITY_GATE

        try:
            orch.LOOP_DIR = tmp_path
            orch.TASK_MD = task_md
            orch._TEST_SUPPRESS_FILE_LOGS = True
            orch._TEST_DISABLE_IDLE_AUTOLAUNCH = False
            orch._TEST_DISABLE_AUTHORITY_GATE = False

            # Ensure gate is available
            assert orch._AUTHORITY_GATE_AVAILABLE, "authority_gate must be importable for this test"

            status = {"status": "idle", "task_name": "?"}
            orch.handle_idle(status, dry_run=False)

            # task.md must NOT have been written — gate blocked promotion
            assert not task_md.exists(), (
                "task.md should not exist — authority gate should have rejected the task"
            )
        finally:
            orch.LOOP_DIR = original_loop_dir
            orch.TASK_MD = original_task_md
            orch._TEST_SUPPRESS_FILE_LOGS = original_suppress
            orch._TEST_DISABLE_IDLE_AUTOLAUNCH = original_disable_idle
            orch._TEST_DISABLE_AUTHORITY_GATE = original_disable_gate

    def test_allowed_task_is_promoted(self, tmp_path):
        """A task from an authorised agent is promoted to task.md."""
        import orchestrator as orch

        queue_dir = tmp_path / "tasks"
        queue_dir.mkdir()
        task_file = queue_dir / "good-task.md"
        task_file.write_text(
            "title: good-task\ngoal: valid work\nagent_id: chief\nconsequence: R1\n"
        )

        task_md = tmp_path / "task.md"
        status_file = tmp_path / "status.json"
        status_file.write_text('{"status": "idle", "task_name": "?"}')

        # Patch write_status to avoid writing a real status.json
        original_loop_dir = orch.LOOP_DIR
        original_task_md = orch.TASK_MD
        original_status_file = orch.STATUS_FILE
        original_suppress = orch._TEST_SUPPRESS_FILE_LOGS
        original_disable_idle = orch._TEST_DISABLE_IDLE_AUTOLAUNCH
        original_disable_gate = orch._TEST_DISABLE_AUTHORITY_GATE
        original_log_file = orch.LOG_FILE
        original_current_dir = orch.CURRENT_DIR
        original_pc_output = orch.PC_OUTPUT
        original_mac_review = orch.MAC_REVIEW
        original_closeout = orch.CLOSEOUT

        try:
            orch.LOOP_DIR = tmp_path
            orch.TASK_MD = task_md
            orch.STATUS_FILE = status_file
            orch.LOG_FILE = tmp_path / "orchestrator.log"
            orch.CURRENT_DIR = tmp_path / "current"
            orch.PC_OUTPUT = orch.CURRENT_DIR / "pc_output.md"
            orch.MAC_REVIEW = orch.CURRENT_DIR / "mac_review.md"
            orch.CLOSEOUT = orch.CURRENT_DIR / "closeout.ok"
            orch._TEST_SUPPRESS_FILE_LOGS = True
            orch._TEST_DISABLE_IDLE_AUTOLAUNCH = False
            orch._TEST_DISABLE_AUTHORITY_GATE = False

            status = {"status": "idle", "task_name": "?"}
            orch.handle_idle(status, dry_run=False)

            # task.md must have been written
            assert task_md.exists(), "task.md should exist — chief@R1 is authorised"
            content = task_md.read_text()
            assert "good-task" in content
        finally:
            orch.LOOP_DIR = original_loop_dir
            orch.TASK_MD = original_task_md
            orch.STATUS_FILE = original_status_file
            orch._TEST_SUPPRESS_FILE_LOGS = original_suppress
            orch._TEST_DISABLE_IDLE_AUTOLAUNCH = original_disable_idle
            orch._TEST_DISABLE_AUTHORITY_GATE = original_disable_gate
            orch.LOG_FILE = original_log_file
            orch.CURRENT_DIR = original_current_dir
            orch.PC_OUTPUT = original_pc_output
            orch.MAC_REVIEW = original_mac_review
            orch.CLOSEOUT = original_closeout

    def test_gate_disabled_in_test_mode_skips_check(self, tmp_path):
        """When _TEST_DISABLE_AUTHORITY_GATE=True the gate does not block."""
        import orchestrator as orch

        queue_dir = tmp_path / "tasks"
        queue_dir.mkdir()
        task_file = queue_dir / "bypass-task.md"
        # rogue agent — but gate is disabled
        task_file.write_text(
            "title: bypass-task\ngoal: bypass test\nagent_id: rogue_agent_xyz\nconsequence: R1\n"
        )

        task_md = tmp_path / "task.md"
        status_file = tmp_path / "status.json"
        status_file.write_text('{"status": "idle", "task_name": "?"}')

        original_loop_dir = orch.LOOP_DIR
        original_task_md = orch.TASK_MD
        original_status_file = orch.STATUS_FILE
        original_suppress = orch._TEST_SUPPRESS_FILE_LOGS
        original_disable_idle = orch._TEST_DISABLE_IDLE_AUTOLAUNCH
        original_disable_gate = orch._TEST_DISABLE_AUTHORITY_GATE
        original_log_file = orch.LOG_FILE
        original_current_dir = orch.CURRENT_DIR
        original_pc_output = orch.PC_OUTPUT
        original_mac_review = orch.MAC_REVIEW
        original_closeout = orch.CLOSEOUT

        try:
            orch.LOOP_DIR = tmp_path
            orch.TASK_MD = task_md
            orch.STATUS_FILE = status_file
            orch.LOG_FILE = tmp_path / "orchestrator.log"
            orch.CURRENT_DIR = tmp_path / "current"
            orch.PC_OUTPUT = orch.CURRENT_DIR / "pc_output.md"
            orch.MAC_REVIEW = orch.CURRENT_DIR / "mac_review.md"
            orch.CLOSEOUT = orch.CURRENT_DIR / "closeout.ok"
            orch._TEST_SUPPRESS_FILE_LOGS = True
            orch._TEST_DISABLE_IDLE_AUTOLAUNCH = False
            orch._TEST_DISABLE_AUTHORITY_GATE = True  # gate off for this test

            status = {"status": "idle", "task_name": "?"}
            orch.handle_idle(status, dry_run=False)

            # With gate disabled, task.md should be promoted despite rogue agent
            assert task_md.exists(), "task.md should exist when gate is disabled"
        finally:
            orch.LOOP_DIR = original_loop_dir
            orch.TASK_MD = original_task_md
            orch.STATUS_FILE = original_status_file
            orch._TEST_SUPPRESS_FILE_LOGS = original_suppress
            orch._TEST_DISABLE_IDLE_AUTOLAUNCH = original_disable_idle
            orch._TEST_DISABLE_AUTHORITY_GATE = original_disable_gate
            orch.LOG_FILE = original_log_file
            orch.CURRENT_DIR = original_current_dir
            orch.PC_OUTPUT = original_pc_output
            orch.MAC_REVIEW = original_mac_review
            orch.CLOSEOUT = original_closeout


# ---------------------------------------------------------------------------
# 9. record_rejection — stdout emission
# ---------------------------------------------------------------------------


class TestRecordRejection:
    def test_record_rejection_no_ledger_prints_stdout(self, capsys):
        task = {
            "agent_id": "rogue_agent",
            "task_id": "bad-task-001",
            "consequence": "R3",
        }
        gate_result = {
            "allowed": False,
            "reason": "consequence R3 blocked",
            "required_tier": "approval_required",
        }
        record_rejection(task, gate_result)
        captured = capsys.readouterr()
        assert "REJECTED" in captured.out
        assert "rogue_agent" in captured.out

    def test_record_rejection_with_ledger_that_lacks_method(self, capsys):
        """Ledger without record_authority_rejection still emits stdout."""
        task = {"agent_id": "chief", "task_id": "task-42", "consequence": "R4"}
        gate_result = {"allowed": False, "reason": "R4 hard floor", "required_tier": "approval_required"}
        ledger_stub = object()  # no record_authority_rejection method
        record_rejection(task, gate_result, ledger=ledger_stub)
        captured = capsys.readouterr()
        assert "REJECTED" in captured.out

    def test_record_rejection_with_working_ledger(self, capsys):
        """Ledger implementing record_authority_rejection is called."""
        task = {"agent_id": "cassandra", "task_id": "task-99", "consequence": "R3"}
        gate_result = {"allowed": False, "reason": "advisory blocked for R3", "required_tier": "approval_required"}
        ledger_mock = MagicMock()
        record_rejection(task, gate_result, ledger=ledger_mock)
        ledger_mock.record_authority_rejection.assert_called_once()
        captured = capsys.readouterr()
        # Should still print to stdout
        assert "REJECTED" in captured.out

    def test_record_rejection_missing_agent_id_does_not_raise(self, capsys):
        """record_rejection is best-effort and must not raise on malformed task."""
        record_rejection({}, {"allowed": False, "reason": "no agent", "required_tier": None})
        captured = capsys.readouterr()
        assert "REJECTED" in captured.out


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_task_without_agent_id_in_frontmatter_is_parsed_gracefully(self):
        """_parse_authority_gate_fields returns empty dict for no agent_id field."""
        import orchestrator as orch
        from pathlib import Path
        import tempfile

        content = "title: old-style-task\ngoal: no agent_id field here\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            tmp = Path(f.name)

        try:
            fields = orch._parse_authority_gate_fields(tmp)
            assert "agent_id" not in fields
        finally:
            tmp.unlink(missing_ok=True)

    def test_gate_fields_extracted_from_frontmatter(self):
        """_parse_authority_gate_fields extracts all gate fields correctly."""
        import orchestrator as orch
        from pathlib import Path
        import tempfile

        content = (
            "title: gate-test-task\n"
            "goal: test gate parsing\n"
            "agent_id: chief\n"
            "consequence: R1\n"
            "output_kind: plan_proposal\n"
            "action: prepare bounded implementation packet\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            tmp = Path(f.name)

        try:
            fields = orch._parse_authority_gate_fields(tmp)
            assert fields["agent_id"] == "chief"
            assert fields["consequence"] == "R1"
            assert fields["output_kind"] == "plan_proposal"
            assert fields["action"] == "prepare bounded implementation packet"
            assert fields["task_id"] == "gate-test-task"
        finally:
            tmp.unlink(missing_ok=True)

    def test_guardian_advisory_only_allowed_for_r0(self):
        result = gate({"agent_id": "guardian", "consequence": "R0"})
        assert result["allowed"] is True

    def test_guardian_blocked_for_r3(self):
        result = gate({"agent_id": "guardian", "consequence": "R3"})
        assert result["allowed"] is False


# ---------------------------------------------------------------------------
# 11. Fail-closed gate: no agent_id → REJECTED (D1 mandatory gate)
# ---------------------------------------------------------------------------


class TestFailClosedNoAgentId:
    """
    Tests that prove the gate is MANDATORY (fail-closed) when agent_id is absent.
    These tests verify the D1(b) flip: tasks without agent_id are now rejected,
    not silently promoted as legacy/trusted.
    """

    def _setup_orch(self, tmp_path):
        """Helper: patch orchestrator globals for an isolated handle_idle() call."""
        import orchestrator as orch
        queue_dir = tmp_path / "tasks"
        queue_dir.mkdir()
        task_md = tmp_path / "task.md"
        status_file = tmp_path / "status.json"
        status_file.write_text('{"status": "idle", "task_name": "?"}')

        saved = {}
        for attr in (
            "LOOP_DIR", "TASK_MD", "STATUS_FILE", "LOG_FILE",
            "CURRENT_DIR", "PC_OUTPUT", "MAC_REVIEW", "CLOSEOUT",
            "_TEST_SUPPRESS_FILE_LOGS", "_TEST_DISABLE_IDLE_AUTOLAUNCH",
            "_TEST_DISABLE_AUTHORITY_GATE",
        ):
            saved[attr] = getattr(orch, attr)

        orch.LOOP_DIR = tmp_path
        orch.TASK_MD = task_md
        orch.STATUS_FILE = status_file
        orch.LOG_FILE = tmp_path / "orchestrator.log"
        orch.CURRENT_DIR = tmp_path / "current"
        orch.PC_OUTPUT = orch.CURRENT_DIR / "pc_output.md"
        orch.MAC_REVIEW = orch.CURRENT_DIR / "mac_review.md"
        orch.CLOSEOUT = orch.CURRENT_DIR / "closeout.ok"
        orch._TEST_SUPPRESS_FILE_LOGS = True
        orch._TEST_DISABLE_IDLE_AUTOLAUNCH = False
        orch._TEST_DISABLE_AUTHORITY_GATE = False

        return orch, queue_dir, task_md, saved

    def _restore_orch(self, orch, saved):
        for attr, val in saved.items():
            setattr(orch, attr, val)

    def test_task_without_agent_id_is_rejected_fail_closed(self, tmp_path):
        """
        A task with valid title + goal but NO agent_id must be REJECTED by the gate
        and must NOT be promoted to task.md (fail-closed).
        """
        orch, queue_dir, task_md, saved = self._setup_orch(tmp_path)
        try:
            task_file = queue_dir / "no-agent-task.md"
            task_file.write_text(
                "title: no-agent-task\ngoal: do something\nscope:\n- stuff\n"
            )
            assert orch._AUTHORITY_GATE_AVAILABLE, "authority_gate must be importable"

            orch.handle_idle({"status": "idle", "task_name": "?"}, dry_run=False)

            assert not task_md.exists(), (
                "task.md must NOT be written — gate must reject tasks without agent_id"
            )
        finally:
            self._restore_orch(orch, saved)

    def test_task_with_agent_id_is_promoted(self, tmp_path):
        """
        A task with agent_id + R1 consequence → promoted (gate ALLOWS it).
        """
        orch, queue_dir, task_md, saved = self._setup_orch(tmp_path)
        try:
            task_file = queue_dir / "good-agent-task.md"
            task_file.write_text(
                "title: good-agent-task\ngoal: do real work\nagent_id: chief\nconsequence: R1\n"
            )
            assert orch._AUTHORITY_GATE_AVAILABLE

            orch.handle_idle({"status": "idle", "task_name": "?"}, dry_run=False)

            assert task_md.exists(), (
                "task.md must be written — chief@R1 is authorised"
            )
            assert "good-agent-task" in task_md.read_text()
        finally:
            self._restore_orch(orch, saved)

    def test_task_with_agent_id_r4_consequence_is_rejected(self, tmp_path):
        """
        A task with agent_id but R4 consequence hits the hard floor — REJECTED.
        """
        orch, queue_dir, task_md, saved = self._setup_orch(tmp_path)
        try:
            task_file = queue_dir / "r4-task.md"
            task_file.write_text(
                "title: r4-task\ngoal: dangerous money work\nagent_id: chief\nconsequence: R4\n"
            )
            assert orch._AUTHORITY_GATE_AVAILABLE

            orch.handle_idle({"status": "idle", "task_name": "?"}, dry_run=False)

            assert not task_md.exists(), (
                "task.md must NOT be written — R4 is a hard floor, never autonomous"
            )
        finally:
            self._restore_orch(orch, saved)

    def test_rejection_is_logged_for_missing_agent_id(self, tmp_path, capsys):
        """
        Rejecting a task without agent_id must produce a GATE log line and
        a record_rejection stdout line.
        """
        orch, queue_dir, task_md, saved = self._setup_orch(tmp_path)
        try:
            task_file = queue_dir / "unowned-task.md"
            task_file.write_text(
                "title: unowned-task\ngoal: mystery work\nscope:\n- ???\n"
            )
            assert orch._AUTHORITY_GATE_AVAILABLE

            orch.handle_idle({"status": "idle", "task_name": "?"}, dry_run=False)

            captured = capsys.readouterr()
            combined = captured.out + captured.err
            assert "REJECTED" in combined, "Expected GATE REJECTED log for missing agent_id"
            assert not task_md.exists()
        finally:
            self._restore_orch(orch, saved)

    def test_gate_disabled_bypasses_agent_id_check(self, tmp_path):
        """
        _TEST_DISABLE_AUTHORITY_GATE=True is the test-isolation escape hatch:
        a task without agent_id still gets promoted when gate is OFF.
        """
        orch, queue_dir, task_md, saved = self._setup_orch(tmp_path)
        try:
            task_file = queue_dir / "bypass-no-agent.md"
            task_file.write_text(
                "title: bypass-no-agent\ngoal: bypass test\nscope:\n- ok\n"
            )
            orch._TEST_DISABLE_AUTHORITY_GATE = True  # gate off

            orch.handle_idle({"status": "idle", "task_name": "?"}, dry_run=False)

            assert task_md.exists(), (
                "task.md should be written when gate is disabled (escape hatch)"
            )
        finally:
            self._restore_orch(orch, saved)
