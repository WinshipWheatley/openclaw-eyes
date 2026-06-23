#!/usr/bin/env python3
"""Worker packet dankness scorer — the lane-3 extension of the self-improving loop.

A heal task goes to a worker with a payload that carries everything the worker needs
to attempt a real fix. When a worker can't make progress, it goes BLOCKED. That BLOCKED
event is either a genuine fix failure (the problem is hard) or a thin-packet signal
(the task didn't carry enough context for the worker to know what to do).

This module scores worker task payloads and classifies BLOCKED terminal reasons, closing
the same dankness loop that the packet critic runs on operator-facing packets.

THE LOAD-BEARING RULE (inherited, do not remove): the loop may only ever ADD GROUNDED
facts (wire a real source) or FLAG a data gap. It must NEVER fabricate content to raise a
score. ``score_worker_packet`` identifies which required fields are missing; the downstream
enricher (or operator) must fill them from real sources — never invented.
"""
from __future__ import annotations

import dataclasses
import os
import sys
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from polish_loop.control_plane import ControlPlaneLedger


def _import_ledger() -> type:
    """Lazy import of ControlPlaneLedger — avoids a hard module-level dependency.

    The scorer and classifier are pure (no I/O, no ledger); only
    ``emit_worker_packet_enrich_tasks`` needs the ledger.  Importing lazily
    lets the module load cleanly in worktree / sandbox contexts where the
    polish_loop package is not yet on sys.path at import time.
    """
    # /home/openclaw is blocked by the pytest sandbox; /home/openclaw/polish_loop
    # (a subdirectory) is NOT blocked.  Use os.path.isdir (unpatched) to avoid
    # the sandbox's Path.is_dir override.
    _polish_loop = "/home/openclaw/polish_loop"
    if os.path.isdir(_polish_loop) and _polish_loop not in sys.path:
        sys.path.insert(0, _polish_loop)
    try:
        from polish_loop.control_plane import ControlPlaneLedger as _CL  # type: ignore
        return _CL
    except ImportError:
        from control_plane import ControlPlaneLedger as _CL  # type: ignore
        return _CL


# ──────────────────────────────────────────────────────────────────
# Required-field set: what a worker needs to attempt a real fix.
#
# These correspond to the fields in HEAL_TASK_PAYLOAD_FIELDS that carry
# CONTEXT (not just metadata), plus the bounds safety guard.
#
# Reasoning per field:
#   source_surface   — which agent/surface is broken; without it the worker
#                      won't know where to look.
#   bad_exchange     — the concrete failing interaction (request + answer);
#                      the only reproducible entry point.
#   expected_behavior — ground truth for "fixed"; without it, acceptance is
#                       undefined.
#   truth_inputs     — grounded read-model refs the worker must use; absent
#                      means no truth anchor.
#   bounds           — safety rails (SEND_HOLD, TEST_MODE); non-negotiable
#                      for a bounded worker.
#   repro_prompts    — exact prompts to replay the bad exchange; empty means
#                      the worker cannot reproduce.
#   acceptance_tests — the test files that gate DONE; empty means the green
#                      gate has nothing to run.
# ──────────────────────────────────────────────────────────────────
WORKER_REQUIRED_FIELDS: tuple[str, ...] = (
    "source_surface",
    "bad_exchange",
    "expected_behavior",
    "truth_inputs",
    "bounds",
    "repro_prompts",
    "acceptance_tests",
)

# Terminal reasons that are unambiguously genuine fix-failure causes.
# BLOCKED for any of these is NOT a thin-packet signal — the packet reached
# a worker but failed for a reason that packet enrichment cannot cure.
_GENUINE_FAILURE_REASONS: frozenset[str] = frozenset({
    "max_attempts_exhausted",
    "repeated_failure_fingerprint",
    "budget_cap_exhausted",
    "green_gate_failed",
    "acceptance_ref_missing",
    "acceptance_ref_hash_mismatch",
    "candidate_output_too_short",
    "candidate_output_empty",
    "candidate_output_validation_failed",
    "candidate_evidence_missing_output",
})

# Substrings in a terminal_reason that suggest the packet was too thin —
# the worker could not start because context was absent.
_THIN_PACKET_KEYWORDS: tuple[str, ...] = (
    "missing_context",
    "no_repro",
    "no_truth_inputs",
    "no_expected_behavior",
    "missing_payload",
    "thin_packet",
    "empty_payload",
    "missing_source",
    "no_source_surface",
    "unknown_surface",
    "failed_to_start",
    "local_builder_missing",
    "runner_failed_to_start",
    "missing_acceptance",
    "no_acceptance",
    "missing_bounds",
)


@dataclasses.dataclass(frozen=True)
class WorkerPacketScore:
    """Deterministic score of a heal payload's worker-context completeness.

    completeness: fraction of required fields that are non-empty (0.0–1.0).
    missing:      tuple of field names that are absent or empty.
    gaps:         grounded gap specs suitable for a thin-packet enrichment
                  task — one entry per missing field.  Never fabricated.
    is_dank:      True when every required field is present and non-empty.
    """

    completeness: float
    missing: tuple[str, ...]
    gaps: tuple[dict[str, Any], ...]
    is_dank: bool


def _is_empty(value: Any) -> bool:
    """Return True for values that carry no worker-usable content."""
    if value is None:
        return True
    if isinstance(value, (str, list, tuple, dict, set)):
        return len(value) == 0
    # Booleans (e.g. rollback_no_send=True) are never "empty".
    return False


def score_worker_packet(payload: Mapping[str, Any]) -> WorkerPacketScore:
    """Score a heal payload's worker-context completeness.  Deterministic; no I/O.

    Checks whether each required worker-context field is present AND non-empty.
    Never inspects semantic quality — only structural presence.  Gaps are
    grounded task specs (what field is missing); the gap never invents what the
    content should be.

    Safe to call on any dict-like payload; missing keys are treated as empty.
    """
    missing: list[str] = []
    gaps: list[dict[str, Any]] = []

    for field in WORKER_REQUIRED_FIELDS:
        value = payload.get(field)
        if _is_empty(value):
            missing.append(field)
            gaps.append({
                "kind": "missing_worker_context",
                "field": field,
                "detail": (
                    f"heal payload missing required worker-context field '{field}' — "
                    f"a grounded source or the operator must supply it before the worker "
                    f"can attempt a fix (never fabricate)"
                ),
            })

    n_required = len(WORKER_REQUIRED_FIELDS)
    completeness = round((n_required - len(missing)) / n_required, 4)
    return WorkerPacketScore(
        completeness=completeness,
        missing=tuple(missing),
        gaps=tuple(gaps),
        is_dank=len(missing) == 0,
    )


def worker_block_is_thin_packet(
    terminal_reason: str | None,
    payload: Mapping[str, Any],
) -> bool | dict[str, Any]:
    """Classify whether a BLOCKED task's terminal_reason signals a thin packet.

    Returns:
        False   — the BLOCKED reason is a genuine fix failure (packet quality
                  is not the cause; don't re-enrich).
        dict    — the BLOCKED reason matches a thin-packet keyword OR the
                  payload scores below 1.0 completeness; the dict carries the
                  gap analysis (a grounded spec, not fabricated content).

    This is a dankness SIGNAL — it tells the operator or the dankifier loop
    that the task packet itself is why the worker got stuck, not the difficulty
    of the underlying fix.
    """
    reason = str(terminal_reason or "").strip().lower()

    if reason in _GENUINE_FAILURE_REASONS:
        # Exception: max_attempts exhausted with a thin payload means both
        # things are true.  Report the thin-packet gap so the enricher can
        # fill it before re-queuing.
        if reason == "max_attempts_exhausted":
            score = score_worker_packet(payload)
            if not score.is_dank:
                return {
                    "signal": "thin_packet_exhausted_attempts",
                    "terminal_reason": terminal_reason,
                    "completeness": score.completeness,
                    "missing_fields": list(score.missing),
                    "gaps": [dict(g) for g in score.gaps],
                    "detail": (
                        "task exhausted max_attempts with a thin payload; "
                        "enrich the packet before re-queuing"
                    ),
                }
        return False

    # Explicit thin-packet keyword in the terminal_reason.
    for kw in _THIN_PACKET_KEYWORDS:
        if kw in reason:
            score = score_worker_packet(payload)
            return {
                "signal": "thin_packet_keyword",
                "terminal_reason": terminal_reason,
                "matched_keyword": kw,
                "completeness": score.completeness,
                "missing_fields": list(score.missing),
                "gaps": [dict(g) for g in score.gaps],
                "detail": (
                    f"terminal_reason matched thin-packet keyword '{kw}'; "
                    f"packet completeness {score.completeness:.0%}"
                ),
            }

    # No definitive classification in the reason string — score the payload.
    # If the payload is thin, treat it as a thin-packet signal.
    score = score_worker_packet(payload)
    if not score.is_dank:
        return {
            "signal": "thin_packet_unknown_reason",
            "terminal_reason": terminal_reason,
            "completeness": score.completeness,
            "missing_fields": list(score.missing),
            "gaps": [dict(g) for g in score.gaps],
            "detail": (
                f"terminal_reason '{terminal_reason}' unclassified but payload "
                f"is missing {len(score.missing)} required fields"
            ),
        }

    return False


# ──────────────────────────────────────────────────────────────────
# Optional helper: emit a worker_packet_enrich task for a thin packet.
# ──────────────────────────────────────────────────────────────────

def _worker_dankify_emit_enabled() -> bool:
    """Whether thin-worker-packet enrichment tasks may be queued.  DEFAULT ON.

    Mirrors the same env-flag pattern as the operator dankifier.  The safety
    contract is the same: queuing a gap spec is itself harmless — it records
    what is missing; the downstream enricher (or operator) must supply the
    grounded value, never fabricate it.
    Set OPENCLAW_WORKER_PACKET_DANKIFY_EMIT=0/false/no/off to disable.
    """
    return os.environ.get(
        "OPENCLAW_WORKER_PACKET_DANKIFY_EMIT", "on"
    ).strip().lower() not in {"0", "false", "no", "off"}


def emit_worker_packet_enrich_tasks(
    ledger: Any,  # ControlPlaneLedger — typed as Any to avoid module-level import
    score: WorkerPacketScore,
    *,
    task_id: str,
    source_surface: str,
    enabled: bool | None = None,
) -> list[str]:
    """Queue one grounded worker_packet_enrich task per missing field.

    Each task is a GROUNDED SPEC (which required field is absent) — never
    content to add.  The enricher or operator must supply the real value from
    a trusted source.  Returns list of admitted task IDs.

    Args:
        ledger:         the live control-plane ledger.
        score:          result of ``score_worker_packet()`` for the thin payload.
        task_id:        the original blocked/thin heal task id (for traceability).
        source_surface: agent/surface the heal task was for.
        enabled:        override the env-flag; None reads from env.
    """
    if enabled is None:
        enabled = _worker_dankify_emit_enabled()
    if not enabled or not score.gaps:
        return []

    admitted: list[str] = []
    for gap in score.gaps:
        payload = {
            "kind": "worker_packet_enrich",
            "original_task_id": task_id,
            "source_surface": source_surface,
            "gap": dict(gap),
            "completeness": score.completeness,
            "grounded_only": True,  # enricher contract: real value or escalate; never fabricate
            "rollback_no_send": True,
        }
        t = ledger.admit_task(
            source="detector",
            task_type="worker_packet_enrich",
            requested_status="READY",
            payload=payload,
            max_attempts=2,
        )
        if t:
            admitted.append(t)
    return admitted
