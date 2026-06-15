from pathlib import Path


def test_green_gate_uses_pytest_timeout_guard():
    script = Path("scripts/green_gate.sh").read_text(encoding="utf-8")

    assert "OPENCLAW_PYTEST_TIMEOUT_SECONDS" in script
    assert "OPENCLAW_PYTEST_TIMEOUT_METHOD" in script
    assert "import pytest_timeout" in script
    assert '--timeout="$PYTEST_TIMEOUT_SECONDS"' in script
    assert '--timeout-method="$PYTEST_TIMEOUT_METHOD"' in script
    assert "-rA" in script


def test_green_gate_fails_loudly_when_pytest_timeout_missing():
    script = Path("scripts/green_gate.sh").read_text(encoding="utf-8")

    assert "pytest-timeout is required for per-test timeout guard" in script
    assert "$VENV -m pip install pytest-timeout" in script
