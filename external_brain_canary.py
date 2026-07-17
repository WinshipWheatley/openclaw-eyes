"""One-shot PUBLIC synthetic canary for the default-off external-brain router."""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Sequence

from codex_app_server_client import CodexAppServerClient, open_direct_app_server_peer
from external_brain_runtime import run_external_brain_request
from packet_quality_telemetry import record_work_validation


CANARY_MARKER = "OPENCLAW_EXTERNAL_BRAIN_CANARY_OK"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one ephemeral PUBLIC external-brain canary.")
    parser.add_argument("--codex", required=True, help="Absolute Codex CLI path.")
    parser.add_argument("--cwd", required=True, help="Read-only working directory for the canary.")
    parser.add_argument(
        "--public-synthetic-canary",
        action="store_true",
        help="Required acknowledgment that this makes one subscription model turn.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.public_synthetic_canary:
        print(json.dumps({"ok": False, "reason": "explicit_public_canary_flag_required"}))
        return 2
    prompt = (
        "This is a synthetic PUBLIC transport canary. Reply with exactly this marker and nothing "
        f"else: {CANARY_MARKER}"
    )
    with open_direct_app_server_peer(args.codex, cwd=args.cwd) as peer:
        result = run_external_brain_request(
            raw_operator_prompt=prompt,
            context_aid={"classification": "PUBLIC synthetic canary", "expected_marker": CANARY_MARKER},
            privacy_metadata={
                "classification": "public",
                "original_pii_tier": "PUBLIC",
                "cloud_allowed": True,
                "local_required": False,
                "tokenization_applied": False,
                "package_minimized": True,
                "raw_values_included": False,
                "secrets_present": False,
            },
            task_type="quick synthetic transport canary",
            chain_lane="LM1_INTENT_PROPOSAL",
            client=CodexAppServerClient(peer),
            local_fallback=lambda: "LOCAL_FALLBACK_CANARY",
            cwd=args.cwd,
            activation_enabled=True,
        )
    marker_observed = result.text.strip() == CANARY_MARKER
    packet_quality = result.receipt.get("packet_quality") or {}
    report_id = str(packet_quality.get("report_id") or "")
    if report_id:
        record_work_validation(
            report_id=report_id,
            passed=marker_observed,
            validator_ref="external_brain_canary:exact_public_marker",
        )
    response_hash = "sha256:" + hashlib.sha256(result.text.encode("utf-8")).hexdigest()[:16]
    output = {
        "ok": result.source == "external_brain" and marker_observed,
        "source": result.source,
        "marker_observed": marker_observed,
        "response_hash": response_hash,
        "receipt": result.receipt,
    }
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
