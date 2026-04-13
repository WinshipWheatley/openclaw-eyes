"""
Chief acceptance gate for the polish loop.

Consumes bounded evidence from a completed task pass and returns exactly
one of: APPROVE, REWORK, or INSUFFICIENT_EVIDENCE.

This module is standalone and testable without the orchestrator.
Step 2 (not yet implemented) will wire it into handle_mac_turn().
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from chief_llm import OLLAMA_URL, resolve_local_model

VERDICTS = frozenset({"APPROVE", "REWORK", "INSUFFICIENT_EVIDENCE"})
GATE_TIMEOUT_SECONDS = 15
GATE_LANE = "fast"

_PROMPT_TEMPLATE = """\
You are Chief, acting as a bounded acceptance gate for a completed task pass.

Review the evidence below and return EXACTLY ONE WORD on the first line:
  APPROVE             — evidence shows the task passed cleanly
  REWORK              — evidence shows a concrete defect that another pass could fix
  INSUFFICIENT_EVIDENCE — evidence is missing, empty, or too ambiguous to judge

Do not explain. Do not add commentary. Return only the verdict word.

--- EVIDENCE ---
Task: {task_name}
Pass: {pass_num}
Planner verdict: {mac_review_verdict}
PC output summary: {pc_output_summary}
Harness: {harness_summary}
--- END EVIDENCE ---

Verdict:"""


def _format_harness(manifest: dict | None) -> str:
    if not manifest:
        return "no harness run"
    flow = manifest.get("flow", "?")
    passed = manifest.get("passed", "?")
    failed = manifest.get("failed", "?")
    total = manifest.get("total_cases", "?")
    if failed and failed != 0 and failed != "?":
        return f"{flow}: {passed}/{total} passed, {failed} FAILED"
    return f"{flow}: {passed}/{total} passed, 0 failed"


def _build_prompt(evidence: dict) -> str:
    return _PROMPT_TEMPLATE.format(
        task_name=evidence.get("task_name", "?"),
        pass_num=evidence.get("pass_num", "?"),
        mac_review_verdict=evidence.get("mac_review_verdict", "?"),
        pc_output_summary=(evidence.get("pc_output_summary") or "(empty)")[:500],
        harness_summary=_format_harness(evidence.get("harness_manifest")),
    )


def _call_local(prompt: str) -> str:
    """Single-shot local model call. Returns raw text or empty string on failure."""
    model, _ = resolve_local_model(prompt, lane=GATE_LANE)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=GATE_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return str(data.get("response", "") or "").strip()
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return ""


def _extract_verdict(raw: str) -> str:
    """Extract a valid verdict from model output. Fail safe to INSUFFICIENT_EVIDENCE."""
    if not raw:
        return "INSUFFICIENT_EVIDENCE"
    first_line = raw.strip().splitlines()[0].strip().upper()
    # Strip any surrounding punctuation or markdown
    word = first_line.strip("*_`#. ")
    if word in VERDICTS:
        return word
    return "INSUFFICIENT_EVIDENCE"


def evaluate_evidence(evidence: dict) -> str:
    """
    Consume bounded task evidence, return APPROVE | REWORK | INSUFFICIENT_EVIDENCE.

    On any failure (LLM timeout, malformed output, missing evidence), returns
    INSUFFICIENT_EVIDENCE — fail safe, never fail open.
    """
    if not isinstance(evidence, dict):
        return "INSUFFICIENT_EVIDENCE"
    prompt = _build_prompt(evidence)
    raw = _call_local(prompt)
    return _extract_verdict(raw)
