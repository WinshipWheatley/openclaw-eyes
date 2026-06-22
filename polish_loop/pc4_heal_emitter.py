#!/usr/bin/env python3
"""Emit PC4 self-heal findings into the deterministic control-plane ledger."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # pragma: no cover
    from .answer_auditor import AuditFinding, check_agent_claim
    from .control_plane import (
        DEFAULT_GREEN_GATE,
        HEAL_TASK_PAYLOAD_FIELDS,
        ControlPlaneLedger,
        TaskRejected,
        make_acceptance_ref,
    )
except ImportError:  # pragma: no cover
    from answer_auditor import AuditFinding, check_agent_claim
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


def control_plane_emit_enabled() -> bool:
    """Whether the detector may admit heal tasks to the LIVE control-plane ledger.

    DEFAULT OFF. Wiring the detector into a live audit path therefore changes nothing
    in production until the operator explicitly flips OPENCLAW_CONTROL_PLANE_EMIT on.
    This is the reversible safety seam for the control-plane cutover: the code is in
    place and tested, but dormant until a deliberate, supervised enable.
    """
    return os.environ.get("OPENCLAW_CONTROL_PLANE_EMIT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def detect_and_emit_heal_task(
    ledger: ControlPlaneLedger,
    agent_id: str,
    claim_type: str,
    observed_answer: Any,
    *,
    read_model_root: str | Path,
    request_text: str,
    answer_text: str | None = None,
    repro_prompts: Sequence[str] = (),
    acceptance_path: str | Path = DEFAULT_ACCEPTANCE_PATH,
    enabled: bool | None = None,
) -> tuple[AuditFinding, str | None]:
    """Audit one agent claim and, on a FAILING finding, admit a heal task to the ledger.

    This is the control-plane cutover detector seam (CUTOVER-PLAN.md Step 1): the single
    place a live audit loop calls to turn a detected bad claim into a deterministically
    tracked heal task. Emission is gated by control_plane_emit_enabled() (default OFF)
    unless an explicit ``enabled`` is passed, so the wire is dormant until turned on.

    Returns (finding, task_id). task_id is None when the claim passes OR when emission
    is disabled -- a passing claim and a dormant detector both yield "no task", which is
    the safe default.
    """
    finding = check_agent_claim(
        agent_id, claim_type, observed_answer, read_model_root=read_model_root
    )
    if finding.verdict != "fail":
        return finding, None
    if enabled is None:
        enabled = control_plane_emit_enabled()
    if not enabled:
        return finding, None
    task_id = emit_heal_task(
        ledger,
        finding,
        request_text=request_text,
        answer_text=answer_text if answer_text is not None else str(observed_answer),
        repro_prompts=tuple(repro_prompts) or (request_text,),
        acceptance_path=acceptance_path,
    )
    return finding, task_id
