"""Sanctioned model lane registry and fail-closed dispatch helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import os
import re
import subprocess
import time
from typing import Any, Mapping


PROVIDER_PRIVILEGE_ORDER = (
    "LOW_METADATA",
    "TOKENIZED_METADATA",
    "TOKENIZED_CLIENT_FINANCE_METADATA",
    "TOKENIZED_PERSONAL_FINANCE_METADATA",
    "TOKENIZED_LEGAL_DISCOVERY_METADATA",
    "TOKENIZED_SENSITIVE_METADATA",
    "STRICT_PRIVATE_CLIENT_METADATA",
    "RAW_PRIVATE_BODY",
)
KNOWN_EXTERNAL_OK_LEVELS = frozenset(PROVIDER_PRIVILEGE_ORDER[:6])


def rank(level: str) -> int:
    try:
        return PROVIDER_PRIVILEGE_ORDER.index(str(level or "").upper())
    except ValueError:
        return len(PROVIDER_PRIVILEGE_ORDER)


@dataclass(frozen=True)
class ProviderCandidate:
    candidate_id: str
    transport: str
    model_ref: str
    model_arg: str
    is_cloud: bool
    is_subscription: bool
    is_metered_api: bool
    cost_tier: str
    quality_tier: str
    max_privacy_level: str
    auth_probe_provider: str
    auth_env_var: str
    dispatch_enabled: bool
    policy_note: str = ""


CANDIDATES = (
    ProviderCandidate(
        candidate_id="local_qwen_fast",
        transport="ollama",
        model_ref="ollama:qwen2.5-coder:7b",
        model_arg="",
        is_cloud=False,
        is_subscription=False,
        is_metered_api=False,
        cost_tier="local_free",
        quality_tier="fast",
        max_privacy_level="RAW_PRIVATE_BODY",
        auth_probe_provider="local_ollama_runtime",
        auth_env_var="",
        dispatch_enabled=True,
    ),
    ProviderCandidate(
        candidate_id="local_qwen_strong",
        transport="ollama",
        model_ref="ollama:qwen2.5-coder:14b",
        model_arg="",
        is_cloud=False,
        is_subscription=False,
        is_metered_api=False,
        cost_tier="local_free",
        quality_tier="balanced",
        max_privacy_level="RAW_PRIVATE_BODY",
        auth_probe_provider="local_ollama_runtime",
        auth_env_var="",
        dispatch_enabled=True,
    ),
    ProviderCandidate(
        candidate_id="local_deep",
        transport="ollama",
        model_ref="ollama:qwen2.5-coder:14b",
        model_arg="",
        is_cloud=False,
        is_subscription=False,
        is_metered_api=False,
        cost_tier="local_free",
        quality_tier="deep",
        max_privacy_level="RAW_PRIVATE_BODY",
        auth_probe_provider="local_ollama_runtime",
        auth_env_var="",
        dispatch_enabled=True,
    ),
    ProviderCandidate(
        candidate_id="kimi_openrouter",
        transport="openrouter",
        model_ref="openrouter:moonshotai/kimi-k2",
        model_arg="moonshotai/kimi-k2",
        is_cloud=True,
        is_subscription=False,
        is_metered_api=False,
        cost_tier="prepaid_capped",
        quality_tier="fast",
        max_privacy_level="TOKENIZED_SENSITIVE_METADATA",
        auth_probe_provider="",
        auth_env_var="OPENROUTER_API_KEY",
        dispatch_enabled=True,
    ),
    ProviderCandidate(
        candidate_id="codex_exec",
        transport="codex",
        model_ref="codex:subscription",
        model_arg="",
        is_cloud=True,
        is_subscription=True,
        is_metered_api=False,
        cost_tier="subscription_flat",
        quality_tier="deep",
        max_privacy_level="TOKENIZED_SENSITIVE_METADATA",
        auth_probe_provider="openai_codex_cli",
        auth_env_var="",
        dispatch_enabled=False,
        policy_note="dispatch_dark_p0",
    ),
    ProviderCandidate(
        candidate_id="claude_cli",
        transport="claude",
        model_ref="claude:opus",
        model_arg="opus",
        is_cloud=True,
        is_subscription=True,
        is_metered_api=False,
        cost_tier="subscription_flat",
        quality_tier="deep",
        max_privacy_level="TOKENIZED_SENSITIVE_METADATA",
        auth_probe_provider="anthropic_claude_cli",
        auth_env_var="",
        dispatch_enabled=True,
        policy_note="human_directed_only",
    ),
)

CANDIDATES_BY_ID = {candidate.candidate_id: candidate for candidate in CANDIDATES}

assert all(not candidate.is_metered_api for candidate in CANDIDATES), (
    "No shipped candidate may be metered in P0; adding one needs explicit budget plumbing."
)
assert all(candidate.transport in {"ollama", "codex", "claude", "openrouter"} for candidate in CANDIDATES), (
    "Only sanctioned transports may ship in P0."
)

LANES = {
    "fast": ("local_qwen_fast", "kimi_openrouter", "codex_exec", "local_qwen_fast"),
    "balanced": ("local_qwen_strong", "codex_exec", "kimi_openrouter", "local_qwen_strong"),
    "deep": ("codex_exec", "claude_cli", "local_deep"),
    "code": ("codex_exec", "claude_cli", "local_deep"),
    "cheap_bulk": ("kimi_openrouter", "local_qwen_fast"),
    "local_only": ("local_qwen_strong",),
}

DEFAULT_FAST_EXTERNAL_CANDIDATE = "kimi_openrouter"
DEFAULT_STRONG_EXTERNAL_CANDIDATE = "codex_exec"
DEFAULT_CODE_CANDIDATE = "codex_exec"
LOCAL_FLOOR_CANDIDATE = "local_qwen_strong"


class CostGuardRefusal(Exception):
    def __init__(self, candidate_id: str, reason: str):
        super().__init__(f"{candidate_id}: {reason}")
        self.candidate_id = candidate_id
        self.reason = reason


def get_candidate(candidate_id: str) -> ProviderCandidate | None:
    return CANDIDATES_BY_ID.get(str(candidate_id or ""))


def lane_candidates(lane_id: str) -> tuple[str, ...]:
    return tuple(LANES.get(str(lane_id or ""), ()))


def public_lane_table() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for lane_id, candidate_ids in LANES.items():
        rows.append(
            {
                "lane_id": lane_id,
                "candidate_ids": candidate_ids,
                "candidates": tuple(asdict(CANDIDATES_BY_ID[candidate_id]) for candidate_id in candidate_ids),
                "local_floor_candidate_id": candidate_ids[-1] if candidate_ids else "",
            }
        )
    return tuple(rows)


def _env_float(name: str, default: float = 0.0) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _openrouter_within_prepaid_balance() -> bool:
    """Return whether the prepaid OpenRouter enable gate has headroom.

    P0 treats OPENROUTER_PREPAID_CAP_USD as an enable gate, not a running
    spend ceiling. This helper does not decrement spend or call billing APIs;
    the real hard bound is the prepaid account balance with auto-top-up off.
    """
    if os.environ.get("OPENROUTER_AUTOTOPUP", "").strip() == "1":
        return False
    cap = _env_float("OPENROUTER_PREPAID_CAP_USD", 0.0)
    spent = _env_float("OPENROUTER_SPENT_USD", 0.0)
    return (cap - spent) > 0


def cost_guard_check(cand: ProviderCandidate, *, per_call_budget_usd: float | None = None) -> None:
    """Raise CostGuardRefusal unless the candidate is allowed by cost policy.

    Local candidates are free. Subscription CLI candidates are flat-rate here;
    their billing-mode proof is enforced separately inside run_candidate.
    OpenRouter is allowed only when the prepaid enable gate has headroom and
    auto-top-up is off. In P0 that gate is not a running spend ceiling because
    no decrement-on-spend tally is wired yet. Metered candidates are refused by
    default and no metered candidate ships in this registry.
    """
    if cand.transport == "ollama":
        return
    if cand.is_subscription:
        return
    if cand.transport == "openrouter":
        if _openrouter_within_prepaid_balance():
            return
        raise CostGuardRefusal(cand.candidate_id, "openrouter_prepaid_gate_closed")
    if cand.is_metered_api:
        if per_call_budget_usd and per_call_budget_usd > 0 and os.environ.get("OPENCLAW_ALLOW_METERED_API") == "1":
            return
        raise CostGuardRefusal(cand.candidate_id, "metered_api_refused")
    raise CostGuardRefusal(cand.candidate_id, "unknown_cost_tier")


def build_cli_command(cand: ProviderCandidate, prompt: str) -> list[str]:
    if cand.transport == "codex":
        return ["codex", "exec", prompt]
    if cand.transport == "claude":
        return ["claude", "-p", prompt, "--model", cand.model_arg]
    raise ValueError(f"non-CLI transport: {cand.transport}")


_SECRET_NAME_RE = re.compile(r"(?i)(key|token|secret|credential|password)")


def _minimal_cli_env(cand: ProviderCandidate, *, source_env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if source_env is None else source_env
    allowed = {"PATH", "HOME"}
    allowed.update(key for key in ("LANG", "LC_ALL", "TERM") if key in source)
    if cand.transport == "codex":
        allowed.update({"CODEX_HOME", "OPENCLAW_CODEX_CLI_PATH"})
    child = {key: str(source[key]) for key in sorted(allowed) if key in source}
    assert not any(_SECRET_NAME_RE.search(key) for key in child)
    return child


def _run_cli_candidate(cand: ProviderCandidate, prompt: str, *, timeout_seconds: int = 360) -> str:
    cost_guard_check(cand)
    if not cand.dispatch_enabled:
        return ""
    argv = build_cli_command(cand, prompt)
    prompt_words = len(str(prompt or "").split())
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            input=None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            env=_minimal_cli_env(cand),
        )
    except (OSError, subprocess.TimeoutExpired):
        _log_external(cand.model_ref, prompt_words, 0, int((time.monotonic() - started) * 1000), False)
        return ""
    result = (completed.stdout or "").strip()
    success = completed.returncode == 0 and bool(result)
    _log_external(cand.model_ref, prompt_words, len(result.split()) if success else 0, int((time.monotonic() - started) * 1000), success)
    return result if success else ""


def _log_external(model: str, prompt_words: int, response_words: int, latency_ms: int, success: bool) -> None:
    try:
        import chief_llm

        chief_llm._log_external_call(model, prompt_words, response_words, latency_ms, success)
    except Exception:
        pass


def _run_openrouter_candidate(
    cand: ProviderCandidate,
    prompt: str,
    *,
    metadata: dict[str, Any] | None,
    timeout_seconds: int,
) -> str:
    try:
        cost_guard_check(cand)
    except CostGuardRefusal:
        return ""
    import chief_llm

    return chief_llm.openrouter_call(prompt, model=cand.model_arg, metadata=metadata, timeout=timeout_seconds)


def _local_lane(cand: ProviderCandidate) -> str:
    if cand.quality_tier == "fast":
        return "fast"
    if cand.quality_tier == "deep":
        return "deep"
    if cand.quality_tier == "code":
        return "code_challenger"
    return "strong"


def _run_local_candidate(
    cand: ProviderCandidate,
    prompt: str,
    *,
    task_class: str | None,
    timeout_seconds: int,
) -> str:
    try:
        cost_guard_check(cand)
    except CostGuardRefusal:
        return ""
    import chief_llm

    return chief_llm.ollama_call(prompt, lane=_local_lane(cand), task_class=task_class, timeout=timeout_seconds)


def candidate_available(candidate_id: str, *, observations: Mapping[str, Any] | None = None) -> dict[str, Any]:
    import provider_access_auth_status

    return provider_access_auth_status.candidate_available(candidate_id, observations=observations)


def run_candidate(
    candidate_id: str,
    prompt: str,
    *,
    metadata: dict[str, Any] | None = None,
    task_class: str | None = None,
    timeout_seconds: int = 360,
    allow_claude_cli: bool = False,
    observations: Mapping[str, Any] | None = None,
) -> str:
    cand = get_candidate(candidate_id)
    if cand is None:
        return ""
    if cand.transport == "claude" and not allow_claude_cli:
        return ""
    if cand.transport in {"codex", "claude"}:
        import provider_access_auth_status

        availability = provider_access_auth_status.candidate_available(candidate_id, observations=observations)
        if not availability.get("available"):
            return ""
        if str(availability.get("reason") or "") in {
            "billing_mode_unproven",
            "dispatch_disabled_p0",
            "unknown_candidate",
            "not_available",
        }:
            return ""
    if cand.transport == "ollama":
        return _run_local_candidate(cand, prompt, task_class=task_class, timeout_seconds=timeout_seconds)
    if cand.transport == "openrouter":
        return _run_openrouter_candidate(cand, prompt, metadata=metadata, timeout_seconds=timeout_seconds)
    if cand.transport in {"codex", "claude"}:
        try:
            return _run_cli_candidate(cand, prompt, timeout_seconds=timeout_seconds)
        except CostGuardRefusal:
            return ""
    return ""


def synthetic_metered_candidate() -> ProviderCandidate:
    return replace(
        CANDIDATES_BY_ID["kimi_openrouter"],
        candidate_id="synthetic_metered",
        transport="metered",
        is_subscription=False,
        is_metered_api=True,
        cost_tier="metered_api",
        dispatch_enabled=False,
    )
