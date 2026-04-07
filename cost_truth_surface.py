#!/usr/bin/env python3
"""Execution receipt and reporting helpers for polish-loop builder runs.

This module is intentionally conservative:
- It records measured values only when a runner/provider surfaced them.
- It keeps estimates clearly labeled as estimates.
- It reports headroom only when there is real local evidence for it.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RECEIPT_DIR = Path("/home/openclaw/execution_receipts")
PC_OUTPUT_FILE = Path("/home/openclaw/polish_loop/current/pc_output.md")

SECTION_HEADERS = (
    "CHANGES:",
    "REASONING:",
    "ROLLBACK PLAN:",
    "COST:",
    "TRUTH:",
    "HEADROOM:",
    "NOT CHANGED:",
    "VAULT_CHANGES:",
    "CONCERNS:",
)

DEFAULT_HEADROOM = {
    "claude": {
        "available": False,
        "provenance": "unavailable",
        "reason": "No provider headroom report captured yet.",
        "captured_at": None,
        "rate_limits": {},
    },
    "codex": {
        "available": False,
        "provenance": "unavailable",
        "reason": "No local headroom API.",
        "captured_at": None,
        "rate_limits": {},
    },
    "gemini": {
        "available": False,
        "provenance": "unavailable",
        "reason": "No local headroom API.",
        "captured_at": None,
        "rate_limits": {},
    },
    "ollama": {
        "available": False,
        "provenance": "not_applicable",
        "reason": "Local runner with no external provider limits.",
        "captured_at": None,
        "rate_limits": {},
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", text.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:80] or "task"


def _read_json_file(path: str | Path | None) -> Any:
    if not path:
        return None
    try:
        raw = Path(path).read_text().strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def _find_first_key(node: Any, keys: set[str]) -> Any:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in keys:
                return value
            found = _find_first_key(value, keys)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_first_key(item, keys)
            if found is not None:
                return found
    return None


def _find_first_mapping(node: Any, keys: set[str]) -> dict[str, Any] | None:
    if isinstance(node, dict):
        if any(key in node for key in keys):
            return node
        for value in node.values():
            found = _find_first_mapping(value, keys)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_first_mapping(item, keys)
            if found is not None:
                return found
    return None


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_rate_limits(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}

    normalized: dict[str, Any] = {}
    items: list[tuple[str, Any]] = []
    if isinstance(raw, dict):
        items = list(raw.items())
    elif isinstance(raw, list):
        items = [(str(idx), value) for idx, value in enumerate(raw)]
    else:
        return {}

    for key, value in items:
        if not isinstance(value, dict):
            continue
        window_name = (
            value.get("window_name")
            or value.get("window")
            or value.get("name")
            or key
        )
        preferred_key = str(key) if str(key) not in {"0", "1", "2", "3"} else str(window_name)
        window_slug = _safe_slug(preferred_key)
        used_pct = (
            _to_float(value.get("used_percentage"))
            or _to_float(value.get("usedPercent"))
            or _to_float(value.get("percentage_used"))
            or _to_float(value.get("percent_used"))
        )
        if used_pct is None:
            used = _to_float(value.get("used"))
            limit = _to_float(value.get("limit"))
            if used is not None and limit not in (None, 0):
                used_pct = round((used / limit) * 100.0, 2)
        reset_at = value.get("reset_at") or value.get("resets_at") or value.get("resetAt")
        normalized[window_slug] = {
            "window": str(window_name),
            "used_percentage": used_pct,
            "remaining_percentage": round(max(0.0, 100.0 - used_pct), 2) if used_pct is not None else None,
            "reset_at": reset_at,
        }

    return normalized


def _extract_claude_facts(raw: Any, model_requested: str) -> dict[str, Any]:
    cost = _to_float(_find_first_key(raw, {"total_cost_usd"}))
    input_tokens = _to_int(_find_first_key(raw, {"input_tokens", "inputTokens"}))
    output_tokens = _to_int(_find_first_key(raw, {"output_tokens", "outputTokens"}))
    cache_read_tokens = _to_int(_find_first_key(raw, {"cache_read_tokens", "cacheReadTokens"}))
    fast_mode_state = _find_first_key(raw, {"fast_mode_state"})
    model_actual = _find_first_key(raw, {"model_actual", "model"})
    rate_limit_container = _find_first_mapping(raw, {"rate_limits", "rateLimits"})
    rate_limits = {}
    if rate_limit_container is not None:
        rate_limits = _normalize_rate_limits(
            rate_limit_container.get("rate_limits") or rate_limit_container.get("rateLimits")
        )

    return {
        "cost_total_usd": cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "fast_mode_state": fast_mode_state,
        "model_actual": str(model_actual) if model_actual else model_requested,
        "rate_limits": rate_limits,
        "provider_json_present": isinstance(raw, dict),
    }


def _extract_runner_facts(runner: str, provider_json_path: str | Path | None, model_requested: str) -> dict[str, Any]:
    raw = _read_json_file(provider_json_path)
    if runner == "claude" and raw is not None:
        return _extract_claude_facts(raw, model_requested)

    return {
        "cost_total_usd": None,
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "fast_mode_state": None,
        "model_actual": model_requested,
        "rate_limits": {},
        "provider_json_present": raw is not None,
    }


def _build_truth_section(
    *,
    runner: str,
    model_requested: str,
    model_actual: str,
    duration_ms: int,
    exit_code: int,
    budget_cap_usd: float | None,
    cost_total_usd: float | None,
    token_provenance: str,
    headroom: dict[str, Any],
) -> dict[str, list[str]]:
    verified = [
        f"runner={runner}",
        f"model_requested={model_requested}",
        f"model_actual={model_actual}",
        f"duration_ms={duration_ms}",
        f"exit_code={exit_code}",
    ]
    estimated: list[str] = []
    unavailable: list[str] = []

    if cost_total_usd is not None:
        verified.append("cost.total_cost_usd")
    elif budget_cap_usd is not None:
        estimated.append(f"budget_cap_usd={budget_cap_usd:.2f}")
    else:
        unavailable.append("cost.total_cost_usd")

    if token_provenance == "provider_reported":
        verified.append("token counts")
    else:
        unavailable.append("token counts")

    runner_headroom = headroom.get(runner, {})
    if runner_headroom.get("available"):
        verified.append("headroom snapshot")
    else:
        unavailable.append(f"{runner} headroom")

    return {
        "verified": verified,
        "estimated": estimated,
        "unavailable": unavailable,
    }


def build_receipt(
    *,
    task_id: str,
    runner: str,
    model_requested: str,
    tier: str,
    effort: str,
    budget_cap_usd: float | None,
    duration_ms: int,
    exit_code: int,
    started_at: str,
    ended_at: str,
    selection_reason: str,
    provider_json_path: str | Path | None = None,
) -> dict[str, Any]:
    runner_facts = _extract_runner_facts(runner, provider_json_path, model_requested)
    headroom = get_headroom()

    if runner == "claude" and runner_facts["rate_limits"]:
        headroom["claude"] = {
            "available": True,
            "provenance": "provider_reported",
            "reason": "Captured from Claude JSON output for this run.",
            "captured_at": _utc_now(),
            "rate_limits": runner_facts["rate_limits"],
        }

    cost_total = runner_facts["cost_total_usd"]
    tokens_provenance = "provider_reported" if runner_facts["input_tokens"] is not None or runner_facts["output_tokens"] is not None else "unavailable"
    truth = _build_truth_section(
        runner=runner,
        model_requested=model_requested,
        model_actual=runner_facts["model_actual"],
        duration_ms=duration_ms,
        exit_code=exit_code,
        budget_cap_usd=budget_cap_usd,
        cost_total_usd=cost_total,
        token_provenance=tokens_provenance,
        headroom=headroom,
    )

    return {
        "schema_version": "1.0",
        "task_id": task_id,
        "recorded_at": _utc_now(),
        "execution": {
            "runner": runner,
            "model_requested": model_requested,
            "model_actual": runner_facts["model_actual"],
            "tier": tier,
            "effort": effort,
            "budget_cap_usd": budget_cap_usd,
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "started_at": started_at,
            "ended_at": ended_at,
            "reason": selection_reason,
            "fast_mode_state": runner_facts["fast_mode_state"],
        },
        "cost": {
            "total_cost_usd": cost_total,
            "estimated_budget_cap_usd": budget_cap_usd,
            "provenance": "measured" if cost_total is not None else ("estimated" if budget_cap_usd is not None else "unavailable"),
        },
        "tokens": {
            "input_tokens": runner_facts["input_tokens"],
            "output_tokens": runner_facts["output_tokens"],
            "cache_read_tokens": runner_facts["cache_read_tokens"],
            "provenance": tokens_provenance,
        },
        "headroom": headroom,
        "truth": truth,
        "raw_capture": {
            "provider_json_present": runner_facts["provider_json_present"],
        },
    }


def write_receipt(**kwargs: Any) -> tuple[Path, dict[str, Any]]:
    receipt = build_receipt(**kwargs)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    task_slug = _safe_slug(str(receipt["task_id"]))
    path = RECEIPT_DIR / f"{task_slug}_{ts}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True))
    return path, receipt


def _receipt_sort_key(path: Path) -> tuple[float, str]:
    try:
        return (path.stat().st_mtime, path.name)
    except Exception:
        return (0.0, path.name)


def latest_receipts(limit: int = 5) -> list[dict[str, Any]]:
    if not RECEIPT_DIR.exists():
        return []
    paths = sorted(RECEIPT_DIR.glob("*.json"), key=_receipt_sort_key, reverse=True)
    receipts: list[dict[str, Any]] = []
    for path in paths[:limit]:
        data = _read_json_file(path)
        if isinstance(data, dict):
            receipts.append(data)
    return receipts


def load_receipt(task_id: str) -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    wanted = _safe_slug(task_id)
    matches = sorted(RECEIPT_DIR.glob(f"{wanted}_*.json"), key=_receipt_sort_key, reverse=True)
    for path in matches:
        data = _read_json_file(path)
        if isinstance(data, dict):
            return data
    return None


def get_headroom() -> dict[str, Any]:
    headroom = deepcopy(DEFAULT_HEADROOM)
    for receipt in latest_receipts(limit=20):
        receipt_headroom = receipt.get("headroom", {})
        claude = receipt_headroom.get("claude", {}) if isinstance(receipt_headroom, dict) else {}
        if claude.get("available"):
            if not claude.get("captured_at"):
                claude = deepcopy(claude)
                claude["captured_at"] = receipt.get("recorded_at")
            headroom["claude"] = claude
            break
    return headroom


def format_compact(receipt: dict[str, Any]) -> str:
    task_id = receipt.get("task_id", "unknown")
    execution = receipt.get("execution", {})
    cost = receipt.get("cost", {})
    total_cost = cost.get("total_cost_usd")
    if total_cost is None:
        spend = f"~${(cost.get('estimated_budget_cap_usd') or 0):.2f} (estimated)"
    else:
        spend = f"${total_cost:.4f} (measured)"
    return (
        f"{task_id} | {execution.get('runner', '?')}/{execution.get('model_actual', '?')} "
        f"| {spend}"
    )


def _is_section_header(line: str) -> bool:
    return line.strip().upper() in SECTION_HEADERS


def _drop_section(lines: list[str], header: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().upper() == header:
            i += 1
            while i < len(lines) and not _is_section_header(lines[i]):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def _insert_section(lines: list[str], header: str, body_lines: list[str], insert_before: str = "NOT CHANGED:") -> list[str]:
    block = [header, *body_lines, ""]
    try:
        idx = next(i for i, line in enumerate(lines) if line.strip().upper() == insert_before)
        return lines[:idx] + block + lines[idx:]
    except StopIteration:
        return lines + [""] + block if lines else block


def _format_money(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"${value:.4f}"


def _render_cost_lines(receipt: dict[str, Any]) -> list[str]:
    execution = receipt.get("execution", {})
    cost = receipt.get("cost", {})
    tokens = receipt.get("tokens", {})
    lines: list[str] = []

    if cost.get("total_cost_usd") is not None:
        lines.append(f"- Total spend: {_format_money(cost.get('total_cost_usd'))} (measured)")
    elif cost.get("estimated_budget_cap_usd") is not None:
        lines.append(f"- Budget cap ceiling: {_format_money(cost.get('estimated_budget_cap_usd'))} (estimated, not actual spend)")
    else:
        lines.append("- Spend: unavailable")

    if tokens.get("provenance") == "provider_reported":
        lines.append(
            "- Tokens: "
            f"in={tokens.get('input_tokens') or 0}, out={tokens.get('output_tokens') or 0}, "
            f"cache_read={tokens.get('cache_read_tokens') or 0} (provider-reported)"
        )
    else:
        lines.append("- Tokens: unavailable")

    lines.append(f"- Duration: {execution.get('duration_ms', 0)} ms (verified locally)")
    return lines


def _render_truth_lines(receipt: dict[str, Any]) -> list[str]:
    truth = receipt.get("truth", {})
    verified = ", ".join(truth.get("verified", [])) or "NONE"
    estimated = ", ".join(truth.get("estimated", [])) or "NONE"
    unavailable = ", ".join(truth.get("unavailable", [])) or "NONE"
    return [
        f"- Verified: {verified}",
        f"- Estimated: {estimated}",
        f"- Unavailable: {unavailable}",
    ]


def _render_headroom_lines(receipt: dict[str, Any]) -> list[str]:
    headroom = receipt.get("headroom", {})
    lines: list[str] = []
    for provider in ("claude", "codex", "gemini", "ollama"):
        entry = headroom.get(provider, {})
        if entry.get("available"):
            windows = entry.get("rate_limits", {})
            window_parts = []
            for window in windows.values():
                used = window.get("used_percentage")
                remaining = window.get("remaining_percentage")
                label = window.get("window", "window")
                if used is None:
                    continue
                window_parts.append(f"{label}: used={used}% headroom={remaining}%")
            detail = "; ".join(window_parts) if window_parts else entry.get("reason", "available")
            lines.append(f"- {provider.capitalize()}: {detail} ({entry.get('provenance', 'verified')})")
        else:
            lines.append(f"- {provider.capitalize()}: {entry.get('reason', 'unavailable')} ({entry.get('provenance', 'unavailable')})")
    return lines


def augment_pc_output(path: str | Path = PC_OUTPUT_FILE, receipt: dict[str, Any] | None = None) -> bool:
    output_path = Path(path)
    if receipt is None:
        return False
    if not output_path.exists():
        return False
    try:
        lines = output_path.read_text().splitlines()
    except Exception:
        return False

    for header in ("COST:", "TRUTH:", "HEADROOM:"):
        lines = _drop_section(lines, header)

    lines = _insert_section(lines, "COST:", _render_cost_lines(receipt))
    lines = _insert_section(lines, "TRUTH:", _render_truth_lines(receipt))
    lines = _insert_section(lines, "HEADROOM:", _render_headroom_lines(receipt))
    output_path.write_text("\n".join(lines).rstrip() + "\n")
    return True
