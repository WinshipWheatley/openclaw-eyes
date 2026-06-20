from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "green_gate.sh"
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")
PINNED_TRUSTED_TEST_REF = "2f6f37e046ef345022bdda4de932fd35631cb756"


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


def test_green_gate_restores_trusted_tests_before_pytest() -> None:
    assert "OPENCLAW_TRUSTED_TEST_REF" in SCRIPT
    assert f'PINNED_TRUSTED_TEST_REF="{PINNED_TRUSTED_TEST_REF}"' in SCRIPT
    assert "origin/codex/pc4-self-healing" not in SCRIPT
    assert 'git checkout "$TRUSTED_TEST_REF" -- tests/' in SCRIPT


def test_green_gate_default_trusted_ref_is_immutable_snapshot() -> None:
    assert PINNED_TRUSTED_TEST_REF in SCRIPT
    assert "OPENCLAW_TRUSTED_ACCEPTANCE_REF" in SCRIPT
    assert "OPENCLAW_TRUSTED_TEST_REF" in SCRIPT
    assert "${OPENCLAW_TRUSTED_ACCEPTANCE_REF:-$PINNED_TRUSTED_TEST_REF}" in SCRIPT


def test_green_gate_rejects_branch_that_weakens_trusted_test(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "trusted"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "pc4-harden@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "PC4 Harden Test"], cwd=repo, check=True)
    for fixture in (
        "generated/read_models/helm_composer_contract.json",
        "generated/read_models/mac_controller_real_use_smoke_status.json",
        "generated/read_models/mac_dynamic_card_renderer_status.json",
        "generated/read_models/cassandra_human_edge_lab.json",
        "generated/read_models/proof_to_response_runtime_status.json",
        "generated/read_models/proof_to_response_schema_adapter_status.json",
    ):
        path = repo / fixture
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_pc4_self_healing.py").write_text(
        "def test_trusted_acceptance_still_runs():\n    assert False\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "trusted tests"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "builder-weakens-tests"], cwd=repo, check=True, capture_output=True, text=True)
    (tests_dir / "test_pc4_self_healing.py").write_text(
        "def test_trusted_acceptance_still_runs():\n    assert True\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "commit", "-am", "weaken test"], cwd=repo, check=True, capture_output=True, text=True)

    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_REPO": str(repo),
            "OPENCLAW_VENV": sys.executable,
            "OPENCLAW_GREEN_GATE_WORKTREE_ROOT": str(tmp_path / "gate-worktrees"),
            "OPENCLAW_TRUSTED_TEST_REF": "trusted",
            "OPENCLAW_PYTEST_TIMEOUT_SECONDS": "10",
        }
    )
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "builder-weakens-tests"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "restoring trusted tests from trusted" in output
    assert "1 failed" in output or "FAIL" in output
