from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import runner_profiles  # noqa: E402
import runner_registry  # noqa: E402
from runner_registry import Runner  # noqa: E402


CLOUD_CAPABLE_RUNNERS = {"aider", "claude", "codex", "gemini"}
LOCAL_ONLY_RUNNERS = {"ollama"}


def _make_runner(name: str, *, runner_type: str, cost_tier: str, models: list[str] | None = None) -> Runner:
    return Runner(
        name=name,
        binary=f"/usr/local/bin/{name}",
        version="1.0",
        available=True,
        runner_type=runner_type,
        models=models or ["default"],
        flags=[],
        strengths=[],
        weaknesses=[],
        cost_tier=cost_tier,
        max_timeout=900,
        invoke_pattern="",
        headless_flag="",
        discovered_at="2026-04-29T00:00:00",
        source="unit-test",
        extra={},
    )


@pytest.fixture
def runner_policy_context(monkeypatch, tmp_path):
    runners = {
        "codex": _make_runner("codex", runner_type="cloud", cost_tier="moderate"),
        "gemini": _make_runner("gemini", runner_type="cloud", cost_tier="cheap"),
        "claude": _make_runner("claude", runner_type="cloud", cost_tier="moderate", models=["sonnet", "opus"]),
        "aider": _make_runner("aider", runner_type="hybrid", cost_tier="variable"),
        "ollama": _make_runner("ollama", runner_type="local", cost_tier="free", models=["chief-fast:latest"]),
    }

    ranked = [
        runners["codex"],
        runners["gemini"],
        runners["claude"],
        runners["aider"],
        runners["ollama"],
    ]

    fake_budget_tracker = SimpleNamespace(
        get_runner_allowance=lambda runner, model, tier: {
            "allowed": True,
            "max_budget": 2.0,
            "reason": "unit-test allowance",
        }
    )

    monkeypatch.setitem(sys.modules, "budget_tracker", fake_budget_tracker)
    monkeypatch.setattr(runner_registry, "get_runners_for_task", lambda task_type: list(ranked))
    monkeypatch.setattr(runner_registry, "get_runner", lambda name: runners.get(name))
    monkeypatch.setattr(
        runner_profiles,
        "_check_headroom_policy",
        lambda runner, tier, task_meta: {
            "allow": True,
            "reason": "unit-test headroom passthrough",
            "headroom_state": {},
        },
    )
    monkeypatch.setattr(runner_profiles, "_check_deferral", lambda task_id, tier, is_blocking: None)
    monkeypatch.setattr(runner_profiles, "_get_recent_runner_ratio", lambda *args, **kwargs: (0, 0))
    monkeypatch.setattr(runner_profiles, "TASK_QUEUE_DIR", tmp_path / "tasks")
    monkeypatch.setattr(runner_profiles, "ARCHIVE_DIR", tmp_path / "archive")

    return SimpleNamespace(runners=runners, ranked=ranked)


def _task(goal: str, *, frontmatter: str = "") -> str:
    extra = f"{frontmatter}\n" if frontmatter else ""
    return (
        "title: Runner cloud policy fixture\n"
        "profile: standard\n"
        f"{extra}"
        f"goal: {goal}\n"
    )


def _assert_local_only_or_fail_closed(profile: dict) -> None:
    runner = profile.get("runner")
    assert runner not in CLOUD_CAPABLE_RUNNERS
    assert (
        runner in LOCAL_ONLY_RUNNERS
        or profile.get("defer") is True
        or profile.get("fail_closed") is True
        or profile.get("blocked") is True
    )


@pytest.mark.parametrize(
    "goal",
    [
        "Review files under /mnt/c/OpenClawLegalPrivate for a synthetic legal intake issue.",
        "Summarize a Gmail body and private correspondence thread for a drafting task.",
        "Inspect a .env file for configuration drift.",
        "Audit tokens referenced by a local integration setup.",
        "Rotate secrets in a local-only application fixture.",
        "Check a PII vault export for malformed records.",
    ],
    ids=[
        "legal-private-path",
        "gmail-body-private-correspondence",
        "dotenv",
        "tokens",
        "secrets",
        "pii-vault",
    ],
)
def test_sensitive_or_private_task_text_cannot_select_cloud_runners(runner_policy_context, goal):
    profile = runner_profiles.select_profile(_task(goal))

    _assert_local_only_or_fail_closed(profile)


def test_explicit_sensitive_frontmatter_routes_local_only(runner_policy_context):
    profile = runner_profiles.select_profile(
        _task(
            "Retest private correspondence parsing with local evidence only.",
            frontmatter="sensitive: true\nlocal_required: true",
        )
    )

    _assert_local_only_or_fail_closed(profile)


def test_unclassified_task_does_not_select_cloud_runner_by_default(runner_policy_context):
    profile = runner_profiles.select_profile(
        _task("Update a small helper test without an explicit data classification.")
    )

    _assert_local_only_or_fail_closed(profile)


def test_explicit_non_sensitive_cloud_allowed_task_may_select_cloud_runner(runner_policy_context):
    profile = runner_profiles.select_profile(
        _task(
            "Update a public fixture using the normal runner pool.",
            frontmatter="data_classification: non_sensitive\ncloud_allowed: true",
        )
    )

    assert profile["runner"] in CLOUD_CAPABLE_RUNNERS


def test_unclassified_local_failure_does_not_silently_fallback_to_cloud(monkeypatch, runner_policy_context):
    ranked_after_local_failure = [
        runner_policy_context.runners["ollama"],
        runner_policy_context.runners["codex"],
        runner_policy_context.runners["gemini"],
        runner_policy_context.runners["claude"],
        runner_policy_context.runners["aider"],
    ]
    monkeypatch.setattr(runner_registry, "get_runners_for_task", lambda task_type: list(ranked_after_local_failure))

    fallback_runner = runner_registry.get_fallback_runner("ollama", task_type="standard")

    assert fallback_runner is None or fallback_runner not in CLOUD_CAPABLE_RUNNERS


def test_coding_runner_cloud_override_is_denied_for_sensitive_task_text(runner_policy_context):
    profile = runner_profiles.select_profile(
        _task(
            "Read Gmail body private correspondence for a local-only check.",
            frontmatter="sensitive: true",
        )
    )
    assert profile["runner"] in LOCAL_ONLY_RUNNERS

    source = (ROOT / "builder_watcher.sh").read_text(encoding="utf-8")
    override_marker = "# Override runner if explicitly requested via CODING_RUNNER"
    override_start = source.index(override_marker)
    override_end = source.index("LAST_EFFECTIVE_RUNNER", override_start)
    override_block = source[override_start:override_end].lower()

    assert 'p_runner="$runner_preferred"' not in override_block or re.search(
        r"sensitive|local_required|private|cloud_allowed|classification|fail[_ -]?closed",
        override_block,
    )
