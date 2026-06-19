#!/usr/bin/env python3
"""Emit PC4 self-heal findings into the deterministic control-plane ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # pragma: no cover
    from .answer_auditor import AuditFinding
    from .control_plane import (
        DEFAULT_GREEN_GATE,
        HEAL_TASK_PAYLOAD_FIELDS,
        ControlPlaneLedger,
        TaskRejected,
        make_acceptance_ref,
    )
except ImportError:  # pragma: no cover
    from answer_auditor import AuditFinding
    from control_plane import (
        DEFAULT_GREEN_GATE,
        HEAL_TASK_PAYLOAD_FIELDS,
        ControlPlaneLedger,
        TaskRejected,
        make_acceptance_ref,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACCEPTANCE_PATH = ROOT / "tests" / "test_pc4_self_healing.py"


def validate_heal_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in HEAL_TASK_PAYLOAD_FIELDS if field not in payload]
    if missing:
        raise TaskRejected(f"heal payload missing required fields: {', '.join(missing)}")
    clean = dict(payload)
    for field in HEAL_TASK_PAYLOAD_FIELDS:
        value = clean.get(field)
        if value in ("", None, [], {}):
            raise TaskRejected(f"heal payload empty required field: {field}")
    if clean.get("rollback_no_send") is not True:
        raise TaskRejected("heal payload must set rollback_no_send=true")
    return clean


def build_heal_payload(
    finding: AuditFinding,
    *,
    request_text: str,
    answer_text: str,
    source_surface: str | None = None,
    repro_prompts: Sequence[str] = (),
    acceptance_tests: Sequence[str] | None = None,
) -> dict[str, Any]:
    source = source_surface or finding.agent_id or "unknown_agent"
    prompts = tuple(repro_prompts) or (request_text or str(finding.claimed_value),)
    return validate_heal_payload(
        {
            "source_surface": source,
            "bad_exchange": {
                "request": request_text,
                "answer": answer_text,
                "claim_type": finding.claim_type,
                "claimed_value": finding.claimed_value,
            },
            "expected_behavior": finding.actual_value,
            "truth_inputs": list(finding.proof_refs),
            "bounds": {"OPENCLAW_TEST_MODE": "1", "OPENCLAW_SEND_HOLD": "1"},
            "allowed_tools_class": "read_only_readmodels",
            "pii_rules": "no vault, no LegalPrivate, no FinancePrivate, no .chief.env",
            "repro_prompts": list(prompts),
            "acceptance_tests": list(acceptance_tests or (DEFAULT_ACCEPTANCE_PATH.as_posix(),)),
            "rollback_no_send": True,
            "agent_id": finding.agent_id,
            "claim_type": finding.claim_type,
            "claim_value": finding.actual_value,
            "audit_finding": finding.to_dict(),
        }
    )


def admit_task_kwargs_for_payload(
    payload: Mapping[str, Any],
    *,
    acceptance_path: str | Path = DEFAULT_ACCEPTANCE_PATH,
    green_gate_path: str | Path = DEFAULT_GREEN_GATE,
    repo_ref: str = "HEAD",
    max_attempts: int = 3,
    budget_cap: float = 0.0,
) -> dict[str, Any]:
    clean = validate_heal_payload(payload)
    return {
        "source": "detector",
        "task_type": "agent_heal",
        "requested_status": "READY",
        "payload": clean,
        "acceptance_ref": make_acceptance_ref(
            acceptance_path,
            green_gate_path,
            repo_ref=repo_ref,
            trusted_acceptance_ref=repo_ref,
            trusted_acceptance_paths=("tests/test_pc4_self_healing.py",),
        ),
        "max_attempts": max_attempts,
        "budget_cap": budget_cap,
    }


def emit_heal_task(
    ledger: ControlPlaneLedger,
    finding: AuditFinding,
    *,
    request_text: str,
    answer_text: str,
    source_surface: str | None = None,
    repro_prompts: Sequence[str] = (),
    acceptance_path: str | Path = DEFAULT_ACCEPTANCE_PATH,
    green_gate_path: str | Path = DEFAULT_GREEN_GATE,
    repo_ref: str = "HEAD",
) -> str | None:
    if finding.verdict != "fail":
        return None
    payload = build_heal_payload(
        finding,
        request_text=request_text,
        answer_text=answer_text,
        source_surface=source_surface,
        repro_prompts=repro_prompts,
    )
    kwargs = admit_task_kwargs_for_payload(
        payload,
        acceptance_path=acceptance_path,
        green_gate_path=green_gate_path,
        repo_ref=repo_ref,
    )
    return ledger.admit_task(**kwargs)
