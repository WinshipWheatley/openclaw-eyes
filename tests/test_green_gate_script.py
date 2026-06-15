from __future__ import annotations

from pathlib import Path


SCRIPT = Path("scripts/green_gate.sh").read_text(encoding="utf-8")


def test_green_gate_uses_pytest_timeout_thread_method() -> None:
    assert "OPENCLAW_PYTEST_TIMEOUT_SECONDS" in SCRIPT
    assert "OPENCLAW_PYTEST_TIMEOUT_METHOD" in SCRIPT
    assert 'TIMEOUT_METHOD="${OPENCLAW_PYTEST_TIMEOUT_METHOD:-thread}"' in SCRIPT
    assert "import pytest_timeout" in SCRIPT
    assert '--timeout="$TIMEOUT_SECONDS"' in SCRIPT
    assert '--timeout-method="$TIMEOUT_METHOD"' in SCRIPT
    assert "-rA" in SCRIPT


def test_green_gate_rejects_network_mounts_and_requires_local_ext4() -> None:
    assert "OPENCLAW_GREEN_GATE_WORKTREE_ROOT" in SCRIPT
    assert "/mnt/e/*|/mnt/c/*" in SCRIPT
    assert "/tmp/*|/home/openclaw/*" in SCRIPT
    assert "df -PT" in SCRIPT
    assert "ext2|ext3|ext4" in SCRIPT
    assert "WORKTREE_CREATED=0" in SCRIPT
    assert 'if [ "$WORKTREE_CREATED" -eq 1 ]; then' in SCRIPT


def test_green_gate_checks_venv_and_clean_checkout_fixture_parity() -> None:
    assert "OPENCLAW_VENV" in SCRIPT
    assert "pytest-timeout is not importable" in SCRIPT
    assert "REQUIRED_CLEAN_FIXTURES" in SCRIPT
    assert "generated/read_models/helm_composer_contract.json" in SCRIPT
    assert "generated/read_models/mac_controller_real_use_smoke_status.json" in SCRIPT
    assert "generated/read_models/cassandra_human_edge_lab.json" in SCRIPT
    assert "clean-room fixture parity check passed" in SCRIPT
