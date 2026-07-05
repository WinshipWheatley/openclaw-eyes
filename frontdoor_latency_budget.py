"""Pure front-door latency budget estimator.

No probing or model calls live here. Callers inject the model/resource signals
they already observed, and this module returns a conservative expected latency
plus a timeout suitable for later front-door wiring.
"""

from __future__ import annotations

from typing import Any, Mapping


DEFAULT_MARGIN = 0.5
DEFAULT_SLACK_S = 3.0
DEFAULT_SYNC_WINDOW_S = 45.0
DEFAULT_SIZE_GB = 9.0
DEFAULT_NUM_PREDICT = 240
DEFAULT_PROMPT_TOKENS = 1024

DEFAULT_TPS_TABLE: dict[str, dict[str, float]] = {
    "small": {
        "gpu_tps": 24.0,
        "cpu_tps": 6.0,
        "prefill_tps": 256.0,
        "load_bw_gbs": 1.25,
    },
    "qwen3_8b_q4": {
        "gpu_tps": 22.0,
        "cpu_tps": 5.5,
        "prefill_tps": 220.0,
        "load_bw_gbs": 1.0,
    },
    "ornith_9b": {
        "gpu_tps": 14.0,
        "cpu_tps": 7.6,
        "prefill_tps": 180.0,
        "load_bw_gbs": 1.0,
    },
    "large": {
        "gpu_tps": 12.0,
        "cpu_tps": 4.0,
        "prefill_tps": 128.0,
        "load_bw_gbs": 1.0,
    },
}


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _positive_float(value: Any) -> float | None:
    number = _as_float(value)
    if number is None or number <= 0:
        return None
    return number


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value > 0:
        return int(value)
    return None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value >= 0:
        return int(value)
    return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _model_latency_class(model: str | None, size_gb: float | None) -> str:
    lowered = str(model or "").lower()
    if "ornith" in lowered and "9" in lowered:
        return "ornith_9b"
    if "qwen3" in lowered and "8b" in lowered:
        return "qwen3_8b_q4"
    if size_gb is None:
        return "large"
    if size_gb <= 4.5:
        return "small"
    if size_gb <= 6.5:
        return "qwen3_8b_q4"
    return "large"


def _merged_tps_table(tps_table: Mapping[str, Mapping[str, Any]] | None) -> dict[str, dict[str, float]]:
    merged = {name: dict(values) for name, values in DEFAULT_TPS_TABLE.items()}
    if not isinstance(tps_table, Mapping):
        return merged
    for class_name, values in tps_table.items():
        if not isinstance(values, Mapping):
            continue
        base = dict(merged.get(str(class_name), {}))
        for key in ("gpu_tps", "cpu_tps", "prefill_tps", "load_bw_gbs"):
            parsed = _positive_float(values.get(key))
            if parsed is not None:
                base[key] = parsed
        if base:
            merged[str(class_name)] = base
    return merged


def classify_latency(
    *,
    expected_s: float,
    timeout_s: float,
    elapsed_ms: int | float,
    sync_window_s: float,
) -> str:
    """Classify observed latency against the condition-derived budget."""

    elapsed_s = max(0.0, float(elapsed_ms) / 1000.0)
    expected = max(0.0, float(expected_s))
    timeout = max(0.0, float(timeout_s))
    sync_window = max(0.0, float(sync_window_s))
    if elapsed_s > timeout:
        return "ANOMALY"
    if expected > sync_window or elapsed_s > expected:
        return "EXPECTED_SLOW"
    return "WITHIN"


def estimate_frontdoor_budget(
    *,
    model: str | None,
    size_gb: float | None,
    gpu_fraction: float | None,
    warm: bool | None,
    num_predict: int | None,
    prompt_tokens: int | None,
    sync_window_s: float | None,
    margin: float | None = DEFAULT_MARGIN,
    slack: float | None = DEFAULT_SLACK_S,
    tps_table: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Estimate front-door latency from injected resource/model signals.

    Missing signals intentionally fall toward a larger expected latency rather
    than an optimistic timeout.
    """

    missing: list[str] = []
    parsed_size_gb = _positive_float(size_gb)
    if parsed_size_gb is None:
        missing.append("size_gb")
        parsed_size_gb = DEFAULT_SIZE_GB

    parsed_gpu_fraction = _as_float(gpu_fraction)
    if parsed_gpu_fraction is None:
        missing.append("gpu_fraction")
        parsed_gpu_fraction = 0.0
    parsed_gpu_fraction = _clamp(parsed_gpu_fraction, 0.0, 1.0)

    if warm is None:
        missing.append("warm")
        parsed_warm = False
    else:
        parsed_warm = bool(warm)

    parsed_num_predict = _positive_int(num_predict)
    if parsed_num_predict is None:
        missing.append("num_predict")
        parsed_num_predict = DEFAULT_NUM_PREDICT

    parsed_prompt_tokens = _nonnegative_int(prompt_tokens)
    if parsed_prompt_tokens is None:
        missing.append("prompt_tokens")
        parsed_prompt_tokens = DEFAULT_PROMPT_TOKENS

    parsed_sync_window_s = _positive_float(sync_window_s) or DEFAULT_SYNC_WINDOW_S
    parsed_margin = _as_float(margin)
    parsed_margin = DEFAULT_MARGIN if parsed_margin is None or parsed_margin < 0 else parsed_margin
    parsed_slack = _as_float(slack)
    parsed_slack = DEFAULT_SLACK_S if parsed_slack is None or parsed_slack < 0 else parsed_slack

    parsed_model = str(model).strip() if model is not None and str(model).strip() else None
    if parsed_model is None:
        missing.append("model")

    latency_class = _model_latency_class(parsed_model, parsed_size_gb if "size_gb" not in missing else None)
    table = _merged_tps_table(tps_table)
    constants = table.get(latency_class) or table["large"]
    gpu_tps = constants["gpu_tps"]
    cpu_tps = constants["cpu_tps"]
    prefill_tps = constants["prefill_tps"]
    load_bw_gbs = constants["load_bw_gbs"]

    eff_tps = max(0.1, (parsed_gpu_fraction * gpu_tps) + ((1.0 - parsed_gpu_fraction) * cpu_tps))
    load_penalty_s = 0.0 if parsed_warm else parsed_size_gb / load_bw_gbs
    prefill_s = parsed_prompt_tokens / prefill_tps
    decode_s = parsed_num_predict / eff_tps
    expected_s = load_penalty_s + prefill_s + decode_s
    timeout_s = (expected_s * (1.0 + parsed_margin)) + parsed_slack

    return {
        "expected_s": expected_s,
        "timeout_s": timeout_s,
        "class_hint": classify_latency(
            expected_s=expected_s,
            timeout_s=timeout_s,
            elapsed_ms=expected_s * 1000.0,
            sync_window_s=parsed_sync_window_s,
        ),
        "basis": {
            "model": parsed_model,
            "size_gb": parsed_size_gb,
            "gpu_fraction": parsed_gpu_fraction,
            "warm": parsed_warm,
            "num_predict": parsed_num_predict,
            "prompt_tokens": parsed_prompt_tokens,
            "sync_window_s": parsed_sync_window_s,
            "margin": parsed_margin,
            "slack": parsed_slack,
            "latency_class": latency_class,
            "gpu_tps": gpu_tps,
            "cpu_tps": cpu_tps,
            "eff_tps": eff_tps,
            "prefill_tps": prefill_tps,
            "prefill_s": prefill_s,
            "load_bw_gbs": load_bw_gbs,
            "load_penalty_s": load_penalty_s,
            "decode_s": decode_s,
            "missing_signals": missing,
        },
    }


__all__ = [
    "DEFAULT_TPS_TABLE",
    "classify_latency",
    "estimate_frontdoor_budget",
]
