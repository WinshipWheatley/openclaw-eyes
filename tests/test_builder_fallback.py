"""test_builder_fallback.py — Tests for builder output validation and fallback logic.

Covers:
  - validate() correctly identifies each invalid-output reason code
  - validate() passes well-formed pc_output.md
  - validate() handles the optional RUNNER: prefix line
  - Simulated quota-message scenario that would trigger fallback runner selection
  - get_fallback_runner() returns the next best available runner from live registry
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
POLISH_LOOP_DIR = ROOT / "polish_loop"

if str(POLISH_LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(POLISH_LOOP_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builder_output_validator import validate  # noqa: E402
from runner_registry import get_fallback_runner, Runner  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers shared across sections
# ---------------------------------------------------------------------------

def _make_runner(name: str, **kwargs) -> Runner:
    """Build a minimal Runner fixture for testing."""
    defaults = dict(
        binary=f"/usr/local/bin/{name}",
        version="1.0",
        available=True,
        runner_type="cloud",
        models=[],
        flags=[],
        strengths=[],
        weaknesses=[],
        cost_tier="moderate",
        max_timeout=900,
        invoke_pattern="",
        headless_flag="",
        discovered_at="2026-04-03T00:00:00",
        source="auto",
        extra={},
    )
    defaults.update(kwargs)
    return Runner(name=name, **defaults)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "pc_output.md"
    p.write_text(content)
    return p


def _minimal_valid_output(pass_num: int = 1) -> str:
    return "\n".join([
        f"PASS: {pass_num}",
        "STATUS: DONE",
        "",
        "CHANGES:",
        "- builder_watcher.sh: added output validation fallback",
        "",
        "REASONING:",
        "- Fallback ensures loop resilience when preferred runner fails.",
        "",
        "ROLLBACK PLAN:",
        "- Revert builder_watcher.sh to previous version.",
        "",
        "COST:",
        "- Spend unavailable.",
        "",
        "TRUTH:",
        "- Verified: validate() returns ok for this file.",
        "",
        "HEADROOM:",
        "- Not applicable.",
        "",
    ])


# ---------------------------------------------------------------------------
# Missing / empty
# ---------------------------------------------------------------------------

def test_validate_missing_file(tmp_path):
    ok, reason = validate(tmp_path / "nonexistent.md")
    assert ok is False
    assert reason == "missing"


def test_validate_empty_file(tmp_path):
    p = _write(tmp_path, "")
    ok, reason = validate(p)
    assert ok is False
    assert reason == "empty"


def test_validate_whitespace_only_file(tmp_path):
    p = _write(tmp_path, "   \n\n\t\n")
    ok, reason = validate(p)
    assert ok is False
    assert reason == "empty"


# ---------------------------------------------------------------------------
# Missing PASS: line
# ---------------------------------------------------------------------------

def test_validate_no_pass_line(tmp_path):
    p = _write(tmp_path, "Some random output without a PASS line\nmore text\n")
    ok, reason = validate(p)
    assert ok is False
    assert reason == "no_pass_line"


def test_validate_error_prefix_no_pass(tmp_path):
    p = _write(tmp_path, "Error: claude: command not found\n")
    ok, reason = validate(p)
    assert ok is False
    assert reason in ("no_pass_line",)


# ---------------------------------------------------------------------------
# Quota / rate-limit detection
# ---------------------------------------------------------------------------

def test_validate_quota_message_plain(tmp_path):
    quota_content = (
        "You have exceeded your quota for Claude. "
        "Please wait before making more requests.\n"
    )
    p = _write(tmp_path, quota_content)
    ok, reason = validate(p)
    assert ok is False
    assert reason == "quota_message"


def test_validate_rate_limit_message(tmp_path):
    p = _write(tmp_path, "Error: rate limit exceeded — retry after 60 seconds\n")
    ok, reason = validate(p)
    assert ok is False
    assert reason == "quota_message"


def test_validate_overloaded_message(tmp_path):
    p = _write(tmp_path, "The model is currently overloaded. Please try again later.\n")
    ok, reason = validate(p)
    assert ok is False
    assert reason == "quota_message"


def test_validate_too_many_requests(tmp_path):
    p = _write(tmp_path, "429 Too Many Requests\n\nYou have sent too many requests.\n")
    ok, reason = validate(p)
    assert ok is False
    assert reason == "quota_message"


# ---------------------------------------------------------------------------
# Valid output
# ---------------------------------------------------------------------------

def test_validate_valid_output(tmp_path):
    p = _write(tmp_path, _minimal_valid_output(pass_num=1))
    ok, reason = validate(p)
    assert ok is True
    assert reason == "ok"


def test_validate_valid_output_pass2(tmp_path):
    p = _write(tmp_path, _minimal_valid_output(pass_num=2))
    ok, reason = validate(p)
    assert ok is True
    assert reason == "ok"


# ---------------------------------------------------------------------------
# RUNNER: prefix support
# ---------------------------------------------------------------------------

def test_validate_runner_prefix_valid(tmp_path):
    """RUNNER: header line before PASS: is accepted."""
    content = "RUNNER: claude\n" + _minimal_valid_output(pass_num=1)
    p = _write(tmp_path, content)
    ok, reason = validate(p)
    assert ok is True
    assert reason == "ok"


def test_validate_runner_prefix_valid_gemini(tmp_path):
    """RUNNER: gemini fallback output is accepted."""
    content = "RUNNER: gemini\n" + _minimal_valid_output(pass_num=1)
    p = _write(tmp_path, content)
    ok, reason = validate(p)
    assert ok is True
    assert reason == "ok"


def test_validate_runner_prefix_only_is_invalid(tmp_path):
    """RUNNER: header with no PASS: line after it is invalid."""
    p = _write(tmp_path, "RUNNER: claude\n")
    ok, reason = validate(p)
    assert ok is False
    assert reason == "no_pass_line"


def test_validate_runner_prefix_wrong_second_line(tmp_path):
    """RUNNER: header followed by non-PASS: content is invalid."""
    p = _write(tmp_path, "RUNNER: claude\nSome error happened\n")
    ok, reason = validate(p)
    assert ok is False
    assert reason in ("no_pass_line", "quota_message")


# ---------------------------------------------------------------------------
# Quota-detection boundary: word "quota" in CONCERNS should not false-positive
# ---------------------------------------------------------------------------

def test_validate_quota_word_in_concerns_does_not_flag(tmp_path):
    """'quota' appearing deep in CONCERNS section should not trip quota detection."""
    content = _minimal_valid_output(pass_num=1) + "\nCONCERNS:\n- Claude quota may be a concern next week.\n"
    p = _write(tmp_path, content)
    ok, reason = validate(p)
    # The word "quota" is far from the top (>400 chars in), so it should pass.
    assert ok is True
    assert reason == "ok"


# ---------------------------------------------------------------------------
# Fallback runner selection — conceptual scenario test
# ---------------------------------------------------------------------------

def test_fallback_runner_selection_logic(tmp_path):
    """Simulate: preferred cloud runner produced a quota message.
    The validator detects this; the system should select the fallback runner.
    """
    # Step 1: A cloud runner produces a quota message as its output
    quota_output = "Error: rate limit exceeded. Please retry later.\n"
    pc_output = _write(tmp_path, quota_output)

    ok, reason = validate(pc_output)
    assert ok is False, "Quota output should be invalid"
    assert reason == "quota_message"

    # Step 2: Confirm fallback runner mapping (mirrors fallback_runner_for() in bash)
    fallback_map = {"codex": "gemini", "gemini": "ollama"}
    preferred_runner = "codex"
    fallback_runner = fallback_map.get(preferred_runner, "ollama")
    assert fallback_runner == "gemini", "Fallback for codex should be gemini"

    # Step 3: Simulate fallback runner producing valid output
    pc_output.write_text("RUNNER: gemini\n" + _minimal_valid_output(pass_num=1))
    ok2, reason2 = validate(pc_output)
    assert ok2 is True, "Fallback runner output should be valid"
    assert reason2 == "ok"

    # Verify the RUNNER: header records which runner actually executed
    first_line = pc_output.read_text().splitlines()[0]
    assert first_line.startswith("RUNNER: gemini"), "RUNNER: header should name the fallback runner"


def test_empty_output_triggers_fallback_scenario(tmp_path):
    """Simulate: preferred runner exited 0 but wrote nothing to pc_output.md."""
    # File is missing entirely (runner crashed before writing)
    missing_path = tmp_path / "pc_output.md"
    ok, reason = validate(missing_path)
    assert ok is False
    assert reason == "missing"

    # System should fall back; after fallback, output is valid
    missing_path.write_text("RUNNER: gemini\n" + _minimal_valid_output(pass_num=1))
    ok2, reason2 = validate(missing_path)
    assert ok2 is True
    assert reason2 == "ok"


# ---------------------------------------------------------------------------
# get_fallback_runner() — live registry-based fallback selection
# ---------------------------------------------------------------------------

def test_get_fallback_runner_basic():
    """When two runners are available, fallback is the other one."""
    claude = _make_runner("claude")
    gemini = _make_runner("gemini")

    with patch("runner_registry.get_runners_for_task", return_value=[claude, gemini]):
        result = get_fallback_runner("claude")
    assert result == "gemini"


def test_get_fallback_runner_skips_failed():
    """get_fallback_runner never returns the failed runner or human-only Claude."""
    gemini = _make_runner("gemini")
    claude = _make_runner("claude")

    with patch("runner_registry.get_runners_for_task", return_value=[gemini, claude]):
        result = get_fallback_runner("gemini")
    assert result is None


def test_get_fallback_runner_no_alternative_returns_none():
    """When only the failed runner is registered, returns None."""
    claude = _make_runner("claude")

    with patch("runner_registry.get_runners_for_task", return_value=[claude]):
        result = get_fallback_runner("claude")
    assert result is None


def test_get_fallback_runner_empty_registry_returns_none():
    """When the registry is empty, returns None gracefully."""
    with patch("runner_registry.get_runners_for_task", return_value=[]):
        result = get_fallback_runner("claude")
    assert result is None


def test_get_fallback_runner_uses_ranked_order():
    """Fallback respects ranking while skipping human-only Claude."""
    codex = _make_runner("codex")
    claude = _make_runner("claude")
    gemini = _make_runner("gemini")
    # Ranked: codex > claude > gemini. Failed: codex. Expect: gemini.
    with patch("runner_registry.get_runners_for_task", return_value=[codex, claude, gemini]):
        result = get_fallback_runner("codex")
    assert result == "gemini"


def test_local_runner_failure_never_falls_back_to_cloud_runner():
    """A local-only failure is not promoted into cloud fallback without metadata."""
    ollama = _make_runner("ollama", runner_type="local", cost_tier="free")
    codex = _make_runner("codex")
    gemini = _make_runner("gemini")

    with patch("runner_registry.get_runners_for_task", return_value=[ollama, codex, gemini]):
        result = get_fallback_runner("ollama")

    assert result is None


def test_get_fallback_runner_quota_scenario(tmp_path):
    """End-to-end scenario: quota message detected → registry fallback selected → valid output."""
    # Step 1: Preferred runner (claude) produces a quota message
    quota_output = "You have exceeded your quota for Claude API.\nPlease retry later.\n"
    pc_output = tmp_path / "pc_output.md"
    pc_output.write_text(quota_output)

    ok, reason = validate(pc_output)
    assert ok is False
    assert reason == "quota_message"

    # Step 2: Registry selects the fallback runner
    claude_r = _make_runner("claude")
    gemini_r = _make_runner("gemini")
    with patch("runner_registry.get_runners_for_task", return_value=[claude_r, gemini_r]):
        fallback = get_fallback_runner("claude")
    assert fallback == "gemini", "Fallback for claude should be gemini when gemini is available"

    # Step 3: Fallback runner produces valid output
    pc_output.write_text("RUNNER: gemini\n" + _minimal_valid_output(pass_num=1))
    ok2, reason2 = validate(pc_output)
    assert ok2 is True
    assert reason2 == "ok"

    first_line = pc_output.read_text().splitlines()[0]
    assert first_line.startswith("RUNNER: gemini")


def test_get_fallback_runner_forced_error_scenario(tmp_path):
    """End-to-end: runner binary missing (no_pass_line) → fallback selected from registry."""
    # Runner wrote a CLI error message instead of valid output
    error_output = "Error: claude: command not found\n"
    pc_output = tmp_path / "pc_output.md"
    pc_output.write_text(error_output)

    ok, reason = validate(pc_output)
    assert ok is False
    assert reason in ("no_pass_line",)

    # Registry provides the fallback
    codex_r = _make_runner("codex")
    claude_r = _make_runner("claude")
    with patch("runner_registry.get_runners_for_task", return_value=[codex_r, claude_r]):
        fallback = get_fallback_runner("codex")
    assert fallback is None
