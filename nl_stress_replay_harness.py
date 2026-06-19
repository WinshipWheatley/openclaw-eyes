#!/usr/bin/env python3
"""Replay natural-language repro prompts through OpenClaw and re-audit truth."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

import openclaw_request_processor
from polish_loop.answer_auditor import check_agent_claim
from polish_loop.pc4_heal_emitter import validate_heal_payload


ROOT = Path(__file__).resolve().parent
DEFAULT_PC_OUTPUT = ROOT / "polish_loop" / "current" / "pc_output.md"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("task payload must be a JSON object")
    return payload


def _write_pc_output(
    path: Path,
    *,
    status: str,
    changes: list[str],
    reasoning: list[str],
    truth: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "RUNNER: nl_stress_replay",
        "PASS: 1",
        f"STATUS: {status}",
        "",
        "CHANGES:",
        *[f"- {item}" for item in changes],
        "",
        "REASONING:",
        *[f"- {item}" for item in reasoning],
        "",
        "ROLLBACK PLAN:",
        "- Keep SEND_HOLD active and inspect the replay/audit evidence before retry.",
        "",
        "COST:",
        "- Local deterministic request processor replay only.",
        "",
        "TRUTH:",
        *[f"- {item}" for item in truth],
        "",
        "HEADROOM:",
        "- No model/provider headroom consumed by this harness.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _request_payload(prompt: str, request_id: str) -> dict[str, Any]:
    false_boundary = {
        "email_send_allowed": False,
        "gmail_read_allowed": False,
        "browser_allowed": False,
        "coupa_allowed": False,
        "submit_allowed": False,
        "ledger_mutation_allowed": False,
        "payment_allowed": False,
        "merge_allowed": False,
        "push_allowed": False,
        "worker_execution_allowed": False,
    }
    return {
        "schema_version": "operator_instruction_package_request_v0",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "request_type": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "request_id": request_id,
        "active_surface_ref": "operator_maestro_chat",
        "operator_text": prompt,
        "current_world_ref": "pc4_self_heal",
        "current_thread_ref": "nl_stress_replay",
        "authority_boundary": false_boundary,
    }


def _process_prompt(prompt: str, *, read_model_root: Path, work_dir: Path, index: int) -> Any:
    if hasattr(openclaw_request_processor, "process"):
        return openclaw_request_processor.process(prompt, read_model_root=read_model_root)
    request_path = work_dir / f"mission_control_operator_instruction_request_general_operator_instruction_pc4_{index}.json"
    request_path.write_text(
        json.dumps(_request_payload(prompt, f"pc4_nl_stress_{index}"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return openclaw_request_processor.process_request_path(
        request_path,
        export_root=read_model_root,
        duplicate_check=False,
    )


def _mapping_answer(payload: Mapping[str, Any]) -> str:
    detail = payload.get("detail_disclosure") if isinstance(payload.get("detail_disclosure"), Mapping) else {}
    layered = detail.get("layered_response_fields") if isinstance(detail.get("layered_response_fields"), Mapping) else {}
    for value in (
        payload.get("one_line_answer"),
        layered.get("one_line_answer"),
        payload.get("operator_message"),
        payload.get("operator_headline"),
        payload.get("headline"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def extract_actual_answer(result: Any) -> str:
    """Extract the newly produced answer that must be re-audited."""

    if isinstance(result, str):
        return result.strip()
    if isinstance(result, Mapping):
        return _mapping_answer(result)
    detail = getattr(result, "detail_disclosure", None)
    layered = detail.get("layered_response_fields") if isinstance(detail, Mapping) else {}
    for value in (
        layered.get("one_line_answer") if isinstance(layered, Mapping) else None,
        getattr(result, "operator_message", None),
        getattr(result, "operator_headline", None),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def run_replay(
    *,
    task_payload_path: str | Path,
    read_model_root: str | Path | None = None,
    pc_output_path: str | Path = DEFAULT_PC_OUTPUT,
) -> int:
    payload = validate_heal_payload(_load_json(Path(task_payload_path)))
    os.environ.setdefault("OPENCLAW_TEST_MODE", "1")
    os.environ.setdefault("OPENCLAW_SEND_HOLD", "1")
    truth_root = Path(read_model_root or payload.get("read_model_root") or "generated/read_models")
    prompts = [str(prompt) for prompt in payload.get("repro_prompts") or [] if str(prompt).strip()]
    if not prompts:
        prompts = [str((payload.get("bad_exchange") or {}).get("request") or payload.get("expected_behavior") or "")]

    processor_results: list[str] = []
    actual_answers: list[str] = []
    work_dir = Path(tempfile.mkdtemp(prefix="pc4-nl-stress-"))
    for index, prompt in enumerate(prompts, start=1):
        result = _process_prompt(prompt, read_model_root=truth_root, work_dir=work_dir, index=index)
        processor_results.append(type(result).__name__)
        actual_answer = extract_actual_answer(result)
        if actual_answer:
            actual_answers.append(actual_answer)

    if not actual_answers:
        _write_pc_output(
            Path(pc_output_path),
            status="BLOCKED",
            changes=["No heal was accepted by the NL-stress replay harness."],
            reasoning=["The replay produced no auditable answer; no fake green is allowed."],
            truth=[
                "Auditor verdict: fail.",
                "Truth source: processor result.",
                f"Processor result types: {', '.join(processor_results)}.",
            ],
        )
        print(work_dir.as_posix())
        return 1
    actual_claim_value = actual_answers[-1]

    finding = check_agent_claim(
        str(payload.get("agent_id") or payload.get("source_surface") or "unknown"),
        str(payload.get("claim_type") or "agent_presence_online_count"),
        actual_claim_value,
        read_model_root=truth_root,
    )
    if finding.verdict == "pass":
        _write_pc_output(
            Path(pc_output_path),
            status="DONE",
            changes=["Replayed repro prompts through the real OpenClaw request processor."],
            reasoning=["The post-heal factual claim passes against current read-model truth."],
            truth=[
                f"Auditor verdict: {finding.verdict}.",
                f"Truth source: {finding.truth_source}.",
                f"Actual answer audited: {actual_claim_value}.",
                f"Processor result types: {', '.join(processor_results)}.",
            ],
        )
        print(work_dir.as_posix())
        return 0

    _write_pc_output(
        Path(pc_output_path),
        status="BLOCKED",
        changes=["No heal was accepted by the NL-stress replay harness."],
        reasoning=[f"The post-heal factual claim was {finding.verdict}; no fake green is allowed."],
        truth=[
            f"Auditor verdict: {finding.verdict}.",
            f"Truth source: {finding.truth_source or 'missing'}.",
            f"Actual answer audited: {actual_claim_value}.",
            f"Delta: {finding.delta}.",
            f"Processor result types: {', '.join(processor_results)}.",
        ],
    )
    print(work_dir.as_posix())
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PC4 NL-stress replay against a heal task payload.")
    parser.add_argument("--task-payload", required=True)
    parser.add_argument("--read-model-root", default=None)
    parser.add_argument("--pc-output", default=str(DEFAULT_PC_OUTPUT))
    args = parser.parse_args(argv)
    try:
        return run_replay(
            task_payload_path=args.task_payload,
            read_model_root=args.read_model_root,
            pc_output_path=args.pc_output,
        )
    except Exception as exc:
        _write_pc_output(
            Path(args.pc_output),
            status="BLOCKED",
            changes=["No heal was accepted by the NL-stress replay harness."],
            reasoning=[f"Harness failed closed before replay: {exc}."],
            truth=["Auditor verdict: unverifiable."],
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
