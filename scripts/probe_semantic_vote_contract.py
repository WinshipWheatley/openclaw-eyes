#!/usr/bin/env python3
"""Exercise the real bounded semantic-vote path without external authority."""

from __future__ import annotations

import json
import multiprocessing
import sys
import time
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import typed_contract_decision as contract
from vote_timeout_clarification import (
    clarification_for_vote_failure,
    classify_vote_failure_kind,
)


PROBE_TEXT = "Could you unpack that broader situation?"
PROBE_TIMEOUT_SECONDS = 8.0
HARD_WALL_TOLERANCE_SECONDS = 0.5


def run_probe(
    *,
    decide_fn: Callable[..., Any] = contract.decide_contract,
    active_children_fn: Callable[[], Any] = multiprocessing.active_children,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    before_vote_pids = {
        int(child.pid)
        for child in active_children_fn()
        if getattr(child, "name", "") == "contract-semantic-vote"
        and getattr(child, "pid", None) is not None
    }
    context = contract.ContractContext(
        agent="maestro",
        surface="operator_maestro_chat",
    )
    started = monotonic_fn()
    decision = decide_fn(
        PROBE_TEXT,
        context=context,
        semantic_vote_enabled=True,
        semantic_timeout_seconds=PROBE_TIMEOUT_SECONDS,
    )
    elapsed = round(monotonic_fn() - started, 3)
    remaining_vote_children = sorted(
        int(child.pid)
        for child in active_children_fn()
        if getattr(child, "name", "") == "contract-semantic-vote"
        and getattr(child, "pid", None) is not None
        and int(child.pid) not in before_vote_pids
    )

    receipt = decision.receipt.to_dict()
    failure_kind = classify_vote_failure_kind(decision).value
    clarification = clarification_for_vote_failure(decision)
    clarification_ok = failure_kind == "none" or bool(clarification)
    contract_ok = (
        contract.SEMANTIC_VOTE_MODEL == "qwen3:8b-q4_K_M"
        and contract.SEMANTIC_VOTE_NUM_CTX == 1024
        and contract.DEFAULT_SEMANTIC_TIMEOUT_SECONDS == PROBE_TIMEOUT_SECONDS
        and contract.SEMANTIC_VOTE_KEEP_ALIVE == "10m"
    )
    hard_wall_ok = elapsed <= PROBE_TIMEOUT_SECONDS + HARD_WALL_TOLERANCE_SECONDS
    passed = bool(
        contract_ok
        and hard_wall_ok
        and clarification_ok
        and not remaining_vote_children
    )
    return {
        "passed": passed,
        "model": contract.SEMANTIC_VOTE_MODEL,
        "num_ctx": contract.SEMANTIC_VOTE_NUM_CTX,
        "timeout_seconds": PROBE_TIMEOUT_SECONDS,
        "keep_alive": contract.SEMANTIC_VOTE_KEEP_ALIVE,
        "elapsed_seconds": elapsed,
        "hard_wall_ok": hard_wall_ok,
        "remaining_vote_children": remaining_vote_children,
        "label": decision.label.value,
        "action": decision.action.value,
        "semantic_vote_status": str(receipt.get("semantic_vote_status") or ""),
        "failure_kind": failure_kind,
        "clarification": clarification or "",
        "authority_granted": bool(receipt.get("authority_granted", False)),
    }


def main() -> int:
    result = run_probe()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
