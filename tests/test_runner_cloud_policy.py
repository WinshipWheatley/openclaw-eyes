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


CLOUD_CAPABLE_RUNNERS = {"aider", "codex", "gemini"}
HUMAN_ONLY_RUNNERS = {"claude"}
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
    assert profile["runner"] not in HUMAN_ONLY_RUNNERS


def test_planner_mode_does_not_override_unclassified_local_only_policy(runner_policy_context):
    profile = runner_profiles.select_profile(
        _task("Review an ordinary helper without sensitivity metadata."),
        planner_mode=True,
    )

    _assert_local_only_or_fail_closed(profile)
    assert profile["role"] == "planner"
    assert profile["cloud_allowed"] is False
    assert profile["cloud_policy"] == "local_only_unclassified"


def test_planner_mode_gemini_override_requires_explicit_cloud_safe_metadata(runner_policy_context):
    profile = runner_profiles.select_profile(
        _task(
            "Review a synthetic public fixture using the planner runner pool.",
            frontmatter="data_classification: synthetic_public\ncloud_allowed: true",
        ),
        planner_mode=True,
    )

    assert profile["role"] == "planner"
    assert profile["cloud_allowed"] is True
    assert profile["runner"] == "gemini"


@pytest.mark.parametrize(
    "goal",
    [
        "Review a Legal matter packet for a law firm client.",
        "Summarize Music Law contract royalties and split sheet disputes.",
        "Classify CPA tax, income, invoice, and payment details.",
        "Update Publishing catalog registrations, splits, and private rights admin data.",
        "Analyze Gmail private correspondence tied to a client invoice.",
    ],
    ids=["legal", "musiclaw", "cpa", "publishing", "gmail"],
)
def test_professional_packets_block_cloud_even_with_non_sensitive_cloud_metadata(runner_policy_context, goal):
    profile = runner_profiles.select_profile(
        _task(
            goal,
            frontmatter="data_classification: non_sensitive\ncloud_allowed: true",
        )
    )

    _assert_local_only_or_fail_closed(profile)
    assert profile["cloud_allowed"] is False
    assert profile["cloud_policy"] == "local_only_sensitive"


@pytest.mark.parametrize("cloud_flag", ["cloud_allowed", "allow_cloud", "cloud_ok"])
def test_cloud_allowance_aliases_cannot_override_professional_markers(runner_policy_context, cloud_flag):
    profile = runner_profiles.select_profile(
        _task(
            "Legal matter packet with Gmail private correspondence and client payment details.",
            frontmatter=f"data_classification: non_sensitive\n{cloud_flag}: true",
        )
    )

    _assert_local_only_or_fail_closed(profile)
    assert profile["cloud_allowed"] is False
    assert profile["cloud_policy"] == "local_only_sensitive"


def test_unclassified_packet_policy_fails_closed_before_runner_choice(runner_policy_context):
    profile = runner_profiles.select_profile(
        _task("Update an ordinary helper without sensitivity metadata.")
    )

    _assert_local_only_or_fail_closed(profile)
    assert profile["cloud_allowed"] is False
    assert profile["cloud_policy"] == "local_only_unclassified"


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


def test_cloud_runner_selection_static_surface_is_policy_wrapped():
    profiles_source = (ROOT / "runner_profiles.py").read_text(encoding="utf-8")
    task_allows_start = profiles_source.index("def _task_allows_cloud")
    task_allows_end = profiles_source.index("def _get_recent_runner_ratio", task_allows_start)
    task_allows_block = profiles_source[task_allows_start:task_allows_end]

    pick_runner_start = profiles_source.index("def _pick_runner")
    registry_lookup = profiles_source.index("runner_registry.get_runners_for_task", pick_runner_start)
    pick_runner_gate_block = profiles_source[pick_runner_start:registry_lookup]

    assert "external_model_packet_policy" in task_allows_block
    assert "if not task_meta:" in pick_runner_gate_block
    assert "_task_is_sensitive(task_meta)" in pick_runner_gate_block
    assert "not _task_allows_cloud(task_meta)" in pick_runner_gate_block
    assert 'planner_mode and result["cloud_allowed"]' in profiles_source

    registry_source = (ROOT / "runner_registry.py").read_text(encoding="utf-8")
    assert 'CLOUD_CAPABLE_RUNNERS = {"aider", "codex", "gemini"}' in registry_source

    watcher_source = (ROOT / "builder_watcher.sh").read_text(encoding="utf-8")
    assert "python3 runner_profiles.py" in watcher_source
    assert "p_cloud_allowed=" in watcher_source
    override_marker = "# Override runner if explicitly requested via CODING_RUNNER"
    override_start = watcher_source.index(override_marker)
    override_end = watcher_source.index("LAST_EFFECTIVE_RUNNER", override_start)
    override_block = watcher_source[override_start:override_end]

    for runner_name in CLOUD_CAPABLE_RUNNERS:
        assert f'RUNNER_PREFERRED" = "{runner_name}"' in override_block
    assert 'p_cloud_allowed" != "True"' in override_block
    assert "Explicit cloud runner override denied" in override_block


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


def test_claude_is_not_registered_as_agent_runner():
    assert "claude" not in runner_registry.KNOWN_RUNNERS
    assert "claude" not in runner_registry.CLOUD_CAPABLE_RUNNERS
    assert "claude" in runner_registry.HUMAN_ONLY_RUNNERS


def test_claude_is_not_cloud_capable_in_runner_profiles():
    assert "claude" not in runner_profiles.CLOUD_CAPABLE_RUNNERS
    assert "claude" in runner_profiles.HUMAN_ONLY_RUNNERS


def test_builder_watcher_hard_denies_claude_runner():
    source = (ROOT / "builder_watcher.sh").read_text(encoding="utf-8")

    assert 'RUNNER_PREFERRED" = "claude"' in source
    assert 'Explicit Claude runner override denied by human-only policy' in source
    assert 'p_runner" = "claude"' in source
    assert 'Claude runner denied by human-only policy' in source
    assert '--output-format json' not in source
