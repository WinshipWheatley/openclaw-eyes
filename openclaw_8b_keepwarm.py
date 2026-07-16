"""Governed one-shot keep-warm entry point for the interactive 8B model."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import chief_llm
import local_model_governance as governance


DEFAULT_RECEIPT_PATH = Path.home() / ".openclaw" / "receipts" / "openclaw_8b_keepwarm_latest.json"
HOLDER_ID = "keepwarm:openclaw-8b"
WARM_TIMEOUT_SECONDS = 10


def _base_receipt(*, status: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "openclaw_8b_keepwarm_receipt_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "reason": reason,
        "model": governance.INTERACTIVE_MODEL,
        "model_keep_alive": governance.INTERACTIVE_KEEP_ALIVE,
        "model_num_ctx": governance.INTERACTIVE_NUM_CTX,
        "model_num_gpu": governance.INTERACTIVE_NUM_GPU,
        "model_num_batch": governance.INTERACTIVE_NUM_BATCH,
    }


def run_keepwarm_once(
    *,
    run_interactive_fn: Callable[..., governance.GovernedCallOutcome] = governance.run_interactive_model_call,
    resident_models_fn: Callable[[], set[str]] = governance._resident_models,
    ollama_call_fn: Callable[..., Any] = chief_llm.ollama_call,
) -> dict[str, Any]:
    """Attempt one no-wait warm call without evicting or preempting work."""

    started = time.monotonic()

    def admitted_warm() -> dict[str, Any]:
        try:
            residents = set(resident_models_fn())
        except Exception as exc:
            receipt = _base_receipt(
                status="deferred",
                reason=f"resident_probe_error:{type(exc).__name__}",
            )
            receipt["resident_model_count"] = 0
            return receipt

        other_models = residents - {governance.INTERACTIVE_MODEL}
        if other_models:
            receipt = _base_receipt(
                status="deferred",
                reason="other_model_resident",
            )
            receipt["resident_model_count"] = len(residents)
            return receipt

        result = ollama_call_fn(
            "warm",
            model=governance.INTERACTIVE_MODEL,
            timeout=WARM_TIMEOUT_SECONDS,
            attempts=1,
            think=False,
            num_predict=1,
            options=governance.interactive_runner_options(),
            keep_alive=governance.INTERACTIVE_KEEP_ALIVE,
            return_metadata=True,
        )
        successful = isinstance(result, Mapping) and result.get("status") == "success"
        receipt = _base_receipt(
            status="warmed" if successful else "failed",
            reason="interactive_window" if successful else "ollama_warm_failed",
        )
        receipt["resident_model_count"] = len(residents)
        if isinstance(result, Mapping):
            receipt["ollama_status"] = str(result.get("status") or "unknown")
            receipt["done_reason"] = str(result.get("done_reason") or "")
            elapsed_ms = result.get("elapsed_ms")
            if isinstance(elapsed_ms, int) and elapsed_ms >= 0:
                receipt["ollama_elapsed_ms"] = elapsed_ms
        return receipt

    outcome = run_interactive_fn(
        admitted_warm,
        holder_id=HOLDER_ID,
        require_idle_lease=True,
        model_slot_max_wait_seconds=0,
    )
    if outcome.status != "completed":
        receipt = _base_receipt(status="deferred", reason=outcome.reason)
    elif isinstance(outcome.value, Mapping):
        receipt = dict(outcome.value)
    else:
        receipt = _base_receipt(status="failed", reason="invalid_warm_outcome")
    receipt["wall_elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return receipt


def write_receipt(
    payload: Mapping[str, Any],
    *,
    path: str | Path = DEFAULT_RECEIPT_PATH,
) -> Path:
    """Atomically replace the private latest-attempt receipt."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, destination)
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run one governed warm attempt")
    parser.add_argument(
        "--receipt-path",
        default=os.environ.get(
            "OPENCLAW_8B_KEEPWARM_RECEIPT_PATH", str(DEFAULT_RECEIPT_PATH)
        ),
    )
    args = parser.parse_args(argv)
    if not args.once:
        parser.error("--once is required")

    receipt = run_keepwarm_once()
    write_receipt(receipt, path=args.receipt_path)
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return 1 if receipt["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
