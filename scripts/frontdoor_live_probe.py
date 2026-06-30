#!/usr/bin/env python3
"""Live front-door model-lane canary.

This is a probe harness only: it does not stage actions, send messages, mutate
ledgers, or grant authority. It verifies that the front-door profile is active
and that the delivered answer came from the local model lane.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protected_generate import protected_generate_with_receipt


DEFAULT_QUESTION = "Who is the operator?"
DEFAULT_TIMEOUT_S = 44.0


def _default_context_packet(question: str) -> dict[str, Any]:
    from maestro_context_packet import build_maestro_context_packet

    return dict(
        build_maestro_context_packet(
            question=question,
            session=None,
            source_surface="operator_maestro_chat",
            require_real_truth=True,
        )
    )


def run_probe(
    question: str = DEFAULT_QUESTION,
    *,
    context_packet: Mapping[str, Any] | None = None,
    agent: str = "maestro",
    audit_log_path: str | Path | None = None,
    interactive_timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    packet = dict(context_packet or _default_context_packet(question))
    outcome = protected_generate_with_receipt(
        question,
        context_packet=packet,
        audit_log_path=audit_log_path,
        allow_live_model=True,
        front_door_profile=True,
        interactive_timeout_s=interactive_timeout_s,
        agent=agent,
    )
    receipt = dict(outcome.receipt)
    frontdoor_used = receipt.get("front_door_profile_used") is True
    delivered_from_model = str(receipt.get("delivered_response_source") or "") == "model"
    passed = bool(frontdoor_used and delivered_from_model)
    return {
        "passed": passed,
        "failure_reason": "" if passed else "frontdoor_model_not_delivered",
        "question": question,
        "agent": agent,
        "answer": outcome.text,
        "receipt": receipt,
        "model_selected": receipt.get("model_selected"),
        "delivered_response_source": receipt.get("delivered_response_source"),
        "front_door_profile_used": receipt.get("front_door_profile_used"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe the live front-door model lane.")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--agent", default="maestro")
    parser.add_argument("--audit-log", default="")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    args = parser.parse_args(argv)

    result = run_probe(
        args.question,
        agent=args.agent,
        audit_log_path=args.audit_log or None,
        interactive_timeout_s=args.timeout,
    )
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
