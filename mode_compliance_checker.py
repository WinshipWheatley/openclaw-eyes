#!/usr/bin/env python3
"""Mode compliance checker for OpenClaw polish loop.

Compares intended execution mode (from task artifact frontmatter) against
actual execution (from execution receipts) and produces per-dimension
compliance verdicts with honest proof-quality labels.

Public API:
    check_compliance(task_file, receipt_file) -> dict
    check_latest(task_id) -> dict | None
    latest_verdicts(n) -> list[dict]
    format_compact(verdict) -> str

Internal helpers (also importable for testing):
    _parse_intended_mode(task_file) -> dict
    _compare_dimension(name, intended, actual, proof_quality, proof_source, **kw) -> dict
    _classify_deviation(receipt, dimension_results) -> list[str]
"""

from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERDICT_DIR = Path("/home/openclaw/compliance_verdicts")
TASK_DIR = Path("/home/openclaw/polish_loop/tasks")
ACTIVE_TASK_FILE = Path("/home/openclaw/polish_loop/task.md")

VALID_OVERALL_VERDICTS = ("compliant", "noncompliant", "partially-verified", "unknown-proof-missing")

# Maps execution_mode label fragments → normalized runner name
_RUNNER_PATTERNS = [
    (re.compile(r"claude\s+code", re.IGNORECASE), "claude"),
    (re.compile(r"\bclaude\b", re.IGNORECASE), "claude"),
    (re.compile(r"\bcodex\b", re.IGNORECASE), "codex"),
    (re.compile(r"\bgemini\b", re.IGNORECASE), "gemini"),
    (re.compile(r"\bollama\b", re.IGNORECASE), "ollama"),
]

# Maps small_model_suitable values → bool
_SMALL_MODEL_TRUE = re.compile(r"^\s*yes\b", re.IGNORECASE)
_SMALL_MODEL_FALSE = re.compile(r"^\s*no\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def _strip_md_bold(value: str) -> str:
    """Remove surrounding ** from a markdown-bold value."""
    return re.sub(r"\*\*", "", value).strip()


def _extract_bold_field(text: str, field_name: str) -> str | None:
    """Extract value from a line like '**Field name:** value' (case-insensitive)."""
    pattern = re.compile(
        r"^\s*\*\*" + re.escape(field_name) + r"\s*:?\*\*\s*:?\s*(.+)",
        re.IGNORECASE | re.MULTILINE,
    )
    m = pattern.search(text)
    if m:
        return m.group(1).strip()
    return None


def _extract_yaml_field(text: str, field_name: str) -> str | None:
    """Extract value from a YAML-style 'field: value' line (case-insensitive)."""
    pattern = re.compile(
        r"^" + re.escape(field_name) + r"\s*:\s*(.+)",
        re.IGNORECASE | re.MULTILINE,
    )
    m = pattern.search(text)
    if m:
        return m.group(1).strip()
    return None


def _parse_runner_from_execution_mode(execution_mode_raw: str) -> str | None:
    """Normalize an execution_mode string to a runner name."""
    for pattern, runner in _RUNNER_PATTERNS:
        if pattern.search(execution_mode_raw):
            return runner
    return None


def _parse_intended_mode(task_file: str) -> dict[str, Any]:
    """Parse task artifact frontmatter for intended execution mode.

    Reads both Markdown-bold format (**Key:** value) and YAML-style (key: value).
    Returns a dict with normalized mode fields. Missing fields are None (not absent).
    """
    try:
        text = Path(task_file).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {
            "execution_mode_raw": None,
            "runner": None,
            "model": None,
            "simplify_intended": False,
            "batch_intended": False,
            "small_model_suitable": None,
            "profile": None,
            "runner_preference": None,
            "model_preference": None,
            "sensitive": None,
            "local_required": None,
            "assigned_to": None,
            "parse_source": str(task_file),
            "parse_error": str(e),
        }

    # --- Execution mode (bold format preferred) ---
    execution_mode_raw = _extract_bold_field(text, "Execution mode")
    runner = None
    simplify_intended = False
    batch_intended = False

    if execution_mode_raw:
        runner = _parse_runner_from_execution_mode(execution_mode_raw)
        # Detect /simplify mode
        if re.search(r"/simplify", execution_mode_raw, re.IGNORECASE):
            simplify_intended = True
        # Detect /batch mode
        if re.search(r"/batch", execution_mode_raw, re.IGNORECASE):
            batch_intended = True

    # --- Small-model-suitable ---
    small_model_raw = _extract_bold_field(text, "Small-model-suitable")
    small_model_suitable: bool | None = None
    if small_model_raw is not None:
        if _SMALL_MODEL_TRUE.match(small_model_raw):
            small_model_suitable = True
        elif _SMALL_MODEL_FALSE.match(small_model_raw):
            small_model_suitable = False
        # "Yes (if ...)" → True; "No (requires ...)" → False
        # Already handled by the regex anchored at start

    # --- Assigned-to ---
    assigned_to = _extract_bold_field(text, "Assigned to")

    # --- Profile (YAML-style frontmatter or bold) ---
    profile = _extract_yaml_field(text, "profile")
    if profile is None:
        profile = _extract_bold_field(text, "profile")

    # --- Runner and model preferences ---
    runner_preference = _extract_yaml_field(text, "runner_preference")
    if runner_preference is None:
        runner_preference = _extract_bold_field(text, "runner_preference")

    model_preference = _extract_yaml_field(text, "model_preference")
    if model_preference is None:
        model_preference = _extract_bold_field(text, "model_preference")

    # --- Sensitive / local_required (YAML frontmatter) ---
    sensitive_raw = _extract_yaml_field(text, "sensitive")
    sensitive: bool | None = None
    if sensitive_raw is not None:
        sensitive = sensitive_raw.lower() in ("true", "yes", "1")

    local_required_raw = _extract_yaml_field(text, "local_required")
    local_required: bool | None = None
    if local_required_raw is not None:
        local_required = local_required_raw.lower() in ("true", "yes", "1")

    return {
        "execution_mode_raw": execution_mode_raw,
        "runner": runner,
        "model": model_preference,
        "simplify_intended": simplify_intended,
        "batch_intended": batch_intended,
        "small_model_suitable": small_model_suitable,
        "profile": profile,
        "runner_preference": runner_preference,
        "model_preference": model_preference,
        "sensitive": sensitive,
        "local_required": local_required,
        "assigned_to": assigned_to,
        "parse_source": str(task_file),
    }


# ---------------------------------------------------------------------------
# Per-dimension comparison
# ---------------------------------------------------------------------------

def _normalize(value: Any) -> str:
    """Normalize a value for comparison (lowercase string)."""
    if value is None:
        return ""
    return str(value).strip().lower()


def _compare_dimension(
    name: str,
    intended: Any,
    actual: Any,
    proof_quality: str,
    proof_source: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Compare one compliance dimension and return a verdict dict.

    proof_quality: measured | provider_reported | locally_inferred | unavailable
    """
    if intended is None and actual is None:
        verdict = "not-applicable"
    elif intended is None:
        verdict = "intended-unspecified"
    elif actual is None:
        verdict = "unknown-proof-missing"
    elif _normalize(intended) == _normalize(actual):
        verdict = "compliant"
    else:
        verdict = "noncompliant"

    result: dict[str, Any] = {
        "dimension": name,
        "intended": intended,
        "actual": actual,
        "verdict": verdict,
        "proof_quality": proof_quality,
        "proof_source": proof_source,
    }
    result.update(kwargs)
    return result


# ---------------------------------------------------------------------------
# Deviation classification
# ---------------------------------------------------------------------------

def _classify_deviation(receipt: dict[str, Any], dimension_results: list[dict[str, Any]]) -> list[str]:
    """Determine deviation categories for any noncompliant dimensions.

    Returns a list of category strings. Empty list means no deviations.
    """
    noncompliant = [d for d in dimension_results if d["verdict"] == "noncompliant"]
    if not noncompliant:
        return []

    execution = receipt.get("execution", {})
    reason = str(execution.get("reason") or "").lower()
    runner = str(execution.get("runner") or "").lower()
    categories: list[str] = []

    for dim in noncompliant:
        cat = None
        if "headroom_divert" in reason:
            cat = "headroom_policy"
        elif "budget" in reason and dim["dimension"] == "model":
            cat = "budget_fallback"
        elif runner == "ollama" and "stuck_loop" in reason:
            cat = "stuck_loop_safety"
        elif "coding_runner" in reason or "human_override" in reason:
            cat = "human_override"
        elif "sensitive" in reason or "local_required" in reason:
            cat = "security_policy"
        else:
            cat = "unexplained"

        # Tag the dimension with its category (mutate in place)
        dim["deviation_category"] = cat
        if cat not in categories:
            categories.append(cat)

    return categories


# ---------------------------------------------------------------------------
# Overall verdict computation
# ---------------------------------------------------------------------------

def _compute_overall_verdict(dimensions: list[dict[str, Any]]) -> tuple[str, str]:
    """Compute overall verdict and reason string from dimension results."""
    total = len(dimensions)
    checkable = [
        d for d in dimensions
        if d["verdict"] not in ("not-applicable", "intended-unspecified")
    ]
    noncompliant_dims = [d for d in checkable if d["verdict"] == "noncompliant"]
    unknown_dims = [d for d in checkable if d["verdict"] == "unknown-proof-missing"]
    compliant_dims = [d for d in checkable if d["verdict"] == "compliant"]

    if not checkable:
        return (
            "unknown-proof-missing",
            f"No checkable dimensions ({total} total, all unspecified or not-applicable)",
        )

    if noncompliant_dims:
        dim_names = ", ".join(d["dimension"] for d in noncompliant_dims)
        return (
            "noncompliant",
            f"{len(noncompliant_dims)}/{len(checkable)} dimensions noncompliant: {dim_names}",
        )

    if unknown_dims:
        unknown_names = ", ".join(d["dimension"] for d in unknown_dims)
        if compliant_dims:
            return (
                "partially-verified",
                f"{len(compliant_dims)}/{len(checkable)} compliant, "
                f"{len(unknown_dims)}/{len(checkable)} unknown-proof-missing ({unknown_names})",
            )
        return (
            "unknown-proof-missing",
            f"No compliant dimensions verified, {len(unknown_dims)} unknown-proof-missing ({unknown_names})",
        )

    return (
        "compliant",
        f"All {len(compliant_dims)}/{len(checkable)} checkable dimensions compliant",
    )


# ---------------------------------------------------------------------------
# Provenance summary
# ---------------------------------------------------------------------------

def _provenance_summary(dimensions: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"measured": 0, "provider_reported": 0, "locally_inferred": 0, "unavailable": 0}
    for d in dimensions:
        key = d.get("proof_quality", "unavailable")
        if key in summary:
            summary[key] += 1
    return summary


# ---------------------------------------------------------------------------
# Core comparison logic
# ---------------------------------------------------------------------------

def check_compliance(task_file: str, receipt_file: str) -> dict[str, Any]:
    """Compare intended mode (task artifact) against actual execution (receipt).

    Returns a compliance verdict dict and writes it to compliance_verdicts/.
    """
    intended = _parse_intended_mode(task_file)

    try:
        receipt = json.loads(Path(receipt_file).read_text())
    except Exception as e:
        return {
            "schema_version": "1.0",
            "task_id": intended.get("parse_source", "unknown"),
            "timestamp": _utc_now(),
            "receipt_file": receipt_file,
            "task_artifact": task_file,
            "error": f"Could not load receipt: {e}",
            "overall_verdict": "unknown-proof-missing",
            "overall_reason": "Receipt file unreadable",
            "intended_mode": intended,
            "dimensions": [],
            "deviation_categories": [],
            "provenance_summary": _provenance_summary([]),
        }

    execution = receipt.get("execution", {})
    cost = receipt.get("cost", {})
    task_id = receipt.get("task_id", Path(task_file).stem)
    timestamp = receipt.get("recorded_at", _utc_now())

    actual_runner = execution.get("runner")
    actual_model_requested = execution.get("model_requested")
    actual_model_actual = execution.get("model_actual")
    actual_tier = execution.get("tier")
    actual_effort = execution.get("effort")
    actual_fast_mode = execution.get("fast_mode_state")  # "on"/"off"/None
    total_cost = cost.get("total_cost_usd")

    # --- Model fallback detection ---
    model_fallback = (
        actual_model_requested is not None
        and actual_model_actual is not None
        and _normalize(actual_model_requested) != _normalize(actual_model_actual)
    )

    dimensions: list[dict[str, Any]] = []

    # --- runner dimension ---
    dimensions.append(_compare_dimension(
        "runner",
        intended.get("runner"),
        actual_runner,
        "measured",
        "execution_receipt.execution.runner",
    ))

    # --- model dimension ---
    model_note = "model_requested == model_actual (no fallback)" if not model_fallback else f"fallback detected: {actual_model_requested} → {actual_model_actual}"
    model_dim = _compare_dimension(
        "model",
        intended.get("model"),
        actual_model_actual,
        "measured",
        "execution_receipt.execution.model_actual",
        note=model_note,
    )
    if model_fallback and model_dim["verdict"] == "intended-unspecified":
        model_dim["note"] = model_note
    dimensions.append(model_dim)

    # --- tier/profile dimension ---
    dimensions.append(_compare_dimension(
        "tier",
        intended.get("profile"),
        actual_tier,
        "locally_inferred",
        "execution_receipt.execution.tier",
    ))

    # --- effort dimension ---
    # Infer expected effort from tier if not explicitly stated
    dimensions.append(_compare_dimension(
        "effort",
        None,  # effort not typically specified in frontmatter; leave as intended-unspecified
        actual_effort,
        "locally_inferred",
        "execution_receipt.execution.effort (from --effort flag)",
    ))

    # --- simplify_mode dimension ---
    simplify_intended: bool = intended.get("simplify_intended", False)
    if actual_fast_mode is not None:
        # We have proof: fast_mode_state was captured
        simplify_actual = actual_fast_mode == "on"
        proof_q = "provider_reported"
        proof_s = "execution_receipt.execution.fast_mode_state"
        simplify_dim = _compare_dimension(
            "simplify_mode",
            simplify_intended,
            simplify_actual,
            proof_q,
            proof_s,
        )
    else:
        # No proof surface
        simplify_dim = _compare_dimension(
            "simplify_mode",
            simplify_intended,
            None,
            "unavailable",
            "fast_mode_state not present in receipt",
            note="Claude JSON may not include fast_mode_state in all configurations",
        )
    dimensions.append(simplify_dim)

    # --- batch_mode dimension ---
    # Batch mode is always unknown-proof-missing — no post-execution evidence surface
    batch_dim = _compare_dimension(
        "batch_mode",
        intended.get("batch_intended", False),
        None,
        "unavailable",
        "No post-execution evidence surface exists for /batch",
        note="/batch is an interactive command — undetectable in --print mode",
    )
    # Override verdict to always be unknown-proof-missing regardless of intended value
    batch_dim["verdict"] = "unknown-proof-missing"
    dimensions.append(batch_dim)

    # --- sensitive_local_only dimension ---
    sensitive = intended.get("sensitive") or intended.get("local_required")
    if sensitive:
        # If task requires local-only, runner must be ollama
        sensitive_actual = actual_runner == "ollama" if actual_runner else None
        sensitive_dim = _compare_dimension(
            "sensitive_local_only",
            True,  # required
            sensitive_actual,
            "measured",
            "execution_receipt.execution.runner (must be ollama for sensitive tasks)",
        )
    else:
        # Not sensitive — runner can be anything
        sensitive_dim = _compare_dimension(
            "sensitive_local_only",
            False,
            False,
            "measured",
            "execution_receipt.execution.runner != ollama required, sensitive not required",
        )
    dimensions.append(sensitive_dim)

    # --- small_model_suitability dimension (advisory) ---
    small_suitable = intended.get("small_model_suitable")
    if small_suitable is True and actual_model_actual is not None:
        # Advisory: if task says small-model suitable but opus was used, flag advisory
        model_lower = _normalize(actual_model_actual)
        if "opus" in model_lower:
            sms_dim = {
                "dimension": "small_model_suitability",
                "intended": True,
                "actual": actual_model_actual,
                "verdict": "advisory-mismatch",
                "proof_quality": "measured",
                "proof_source": "execution_receipt.execution.model_actual",
                "note": "Task marked small-model-suitable but opus model was used — not a compliance failure",
            }
        else:
            sms_dim = _compare_dimension(
                "small_model_suitability",
                True,
                True,
                "measured",
                "execution_receipt.execution.model_actual",
                note="Advisory dimension only — model class consistent with small-model-suitable=Yes",
            )
        dimensions.append(sms_dim)

    # --- Classify deviations ---
    deviation_categories = _classify_deviation(receipt, dimensions)

    # --- Overall verdict ---
    # For overall verdict computation, exclude advisory-mismatch from noncompliant
    checkable_dims = [d for d in dimensions if d.get("verdict") not in ("advisory-mismatch",)]
    overall_verdict, overall_reason = _compute_overall_verdict(checkable_dims)

    # --- Provenance summary ---
    prov_summary = _provenance_summary(dimensions)

    verdict: dict[str, Any] = {
        "schema_version": "1.0",
        "task_id": task_id,
        "timestamp": timestamp,
        "receipt_file": str(receipt_file),
        "task_artifact": str(task_file),
        "intended_mode": {
            "execution_mode": intended.get("execution_mode_raw"),
            "small_model_suitable": intended.get("small_model_suitable"),
            "profile": intended.get("profile"),
            "runner_preference": intended.get("runner_preference"),
            "model_preference": intended.get("model_preference"),
            "parse_source": intended.get("parse_source"),
        },
        "overall_verdict": overall_verdict,
        "overall_reason": overall_reason,
        "dimensions": dimensions,
        "deviation_categories": deviation_categories,
        "provenance_summary": prov_summary,
    }
    if total_cost is not None:
        verdict["cost_usd"] = total_cost

    # --- Write verdict file ---
    _write_verdict(verdict)

    return verdict


def _write_verdict(verdict: dict[str, Any]) -> Path:
    """Write compliance verdict to compliance_verdicts/<task_id>_<timestamp>_compliance.json."""
    VERDICT_DIR.mkdir(parents=True, exist_ok=True)
    task_slug = _safe_slug(str(verdict.get("task_id", "task")))
    ts_raw = verdict.get("timestamp", _utc_now())
    # Normalize timestamp to filename-safe form
    ts_safe = re.sub(r"[^\d]", "-", ts_raw)[:19]
    filename = f"{task_slug}_{ts_safe}_compliance.json"
    path = VERDICT_DIR / filename
    path.write_text(json.dumps(verdict, indent=2, sort_keys=True))
    return path


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", text.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:80] or "task"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public read-only accessors
# ---------------------------------------------------------------------------

def check_latest(task_id: str) -> dict[str, Any] | None:
    """Find the most recent receipt for task_id and run compliance check.

    Returns None if no receipt or task artifact found.
    """
    # Locate task artifact
    task_file: str | None = None
    candidate = TASK_DIR / f"{task_id}.md"
    if candidate.exists():
        task_file = str(candidate)
    elif ACTIVE_TASK_FILE.exists():
        # Check if the active task.md matches this task_id
        try:
            content = ACTIVE_TASK_FILE.read_text()
            if task_id in content:
                task_file = str(ACTIVE_TASK_FILE)
        except Exception:
            pass

    if task_file is None:
        return None

    # Locate most recent receipt
    try:
        from cost_truth_surface import load_receipt
        receipt = load_receipt(task_id)
    except Exception:
        receipt = None

    if receipt is None:
        return None

    # Find receipt file path for the returned receipt
    receipt_dir = Path("/home/openclaw/execution_receipts")
    wanted = _safe_slug(task_id)
    matches = sorted(
        receipt_dir.glob(f"{wanted}_*.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    receipt_file = str(matches[0]) if matches else "(in-memory)"

    return check_compliance(task_file, receipt_file)


def latest_verdicts(n: int = 10) -> list[dict[str, Any]]:
    """Return N most recent compliance verdicts, newest first."""
    if not VERDICT_DIR.exists():
        return []
    paths = sorted(
        VERDICT_DIR.glob("*_compliance.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    results: list[dict[str, Any]] = []
    for path in paths[:n]:
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                results.append(data)
        except Exception:
            continue
    return results


def format_compact(verdict: dict[str, Any]) -> str:
    """Format a compliance verdict as a single scannable line.

    Format:
        task-id | intended=runner/model/tier → actual=runner/model/tier | overall-verdict (N/M) | $cost
    """
    task_id = verdict.get("task_id", "unknown")
    intended_mode = verdict.get("intended_mode", {})
    dimensions = verdict.get("dimensions", [])
    overall = verdict.get("overall_verdict", "unknown")
    deviation_cats = verdict.get("deviation_categories", [])

    # Build intended/actual shorthand from dimension results
    def _dim_actual(name: str) -> str:
        for d in dimensions:
            if d.get("dimension") == name:
                return str(d.get("actual") or "?")
        return "?"

    def _dim_intended(name: str) -> str:
        for d in dimensions:
            if d.get("dimension") == name:
                return str(d.get("intended") or "?")
        return "?"

    intended_runner = intended_mode.get("runner") or _dim_intended("runner") or "?"
    intended_model = intended_mode.get("model_preference") or "?"
    intended_tier = intended_mode.get("profile") or "?"
    actual_runner = _dim_actual("runner")
    actual_model = _dim_actual("model")
    actual_tier = _dim_actual("tier")

    # Count checked vs total
    checkable = [
        d for d in dimensions
        if d.get("verdict") not in ("not-applicable", "intended-unspecified", "advisory-mismatch")
    ]
    compliant_count = sum(1 for d in checkable if d.get("verdict") == "compliant")
    total_checkable = len(checkable)

    # Cost
    cost_usd = verdict.get("cost_usd")
    if cost_usd is not None:
        cost_str = f"${cost_usd:.3f}"
    else:
        cost_str = "$?"

    intended_str = f"{intended_runner}/{intended_model}/{intended_tier}"
    actual_str = f"{actual_runner}/{actual_model}/{actual_tier}"

    base = (
        f"{task_id} | {intended_str} → {actual_str} "
        f"| {overall} ({compliant_count}/{total_checkable}) | {cost_str}"
    )

    if deviation_cats:
        cats_str = ", ".join(deviation_cats)
        base += f" [{cats_str}]"

    return base
