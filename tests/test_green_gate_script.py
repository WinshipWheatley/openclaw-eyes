from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "green_gate.sh"
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")


def _gate_python() -> str:
    candidates = [
        os.environ.get("OPENCLAW_TEST_GATE_PYTHON", ""),
        "/home/openclaw/.venv/bin/python",
        sys.executable,
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).exists():
            continue
        result = subprocess.run(
            [candidate, "-c", "import pytest, pytest_timeout"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    return sys.executable


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
    assert "origin/codex/pc4-self-healing" in SCRIPT
    assert 'git checkout "$TRUSTED_TEST_REF" -- tests/' in SCRIPT


def test_green_gate_full_mode_has_atomic_lock_and_stale_reap() -> None:
    assert "OPENCLAW_GREEN_GATE_LOCK_DIR" in SCRIPT
    assert "OPENCLAW_GREEN_GATE_LOCK_STALE_SECONDS" in SCRIPT
    assert 'mkdir "$LOCK_DIR"' in SCRIPT
    assert "acquire_full_gate_lock" in SCRIPT
    assert "release_full_gate_lock" in SCRIPT
    assert "reap_stale_full_gate_lock" in SCRIPT
    assert "kill -0" in SCRIPT
    assert "FULL gate lock acquired" in SCRIPT


def test_green_gate_fast_mode_is_parallel_safe_and_skips_full_lock() -> None:
    assert "--fast" in SCRIPT
    assert "FAST pre-gate" in SCRIPT
    assert "MODE=\"fast\"" in SCRIPT
    assert 'if [ "$MODE" = "full" ]; then' in SCRIPT
    assert "acquire_full_gate_lock" in SCRIPT
    assert "OPENCLAW_GREEN_GATE_FAST_LOCK_ROOT" in SCRIPT
    assert "acquire_fast_gate_lock" in SCRIPT
    assert "FAST branch lock acquired" in SCRIPT
    assert "no full-gate lock" in SCRIPT
    assert "OPENCLAW_FAST_PYTEST_ARGS" in SCRIPT
    assert "OPENCLAW_FAST_BASE_REF" in SCRIPT
    assert "map_changed_paths_to_pytest_args" in SCRIPT


def test_green_gate_uses_run_scoped_tmp_log_and_sqlite_sandbox() -> None:
    assert "OPENCLAW_GREEN_GATE_RUN_ROOT" in SCRIPT
    assert "RUN_TMP" in SCRIPT
    assert 'LOG="$RUN_TMP/pytest.log"' in SCRIPT
    assert 'export TMPDIR="$RUN_TMP/tmp"' in SCRIPT
    assert "OPENCLAW_PYTEST_REDIRECT_TMP_SQLITE" in SCRIPT
    assert "OPENCLAW_PYTEST_TMP_SQLITE_ROOT" in SCRIPT


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
            "OPENCLAW_VENV": _gate_python(),
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


def test_green_gate_reaps_stale_atomic_lock_before_full_run(tmp_path) -> None:
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
    (tests_dir / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "trusted tests"], cwd=repo, check=True, capture_output=True, text=True)

    lock_dir = tmp_path / "full-gate.lock"
    lock_dir.mkdir()
    (lock_dir / "holder.env").write_text("pid=99999999\nstarted_epoch=1\n", encoding="utf-8")
    os.utime(lock_dir, (1, 1))

    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_REPO": str(repo),
            "OPENCLAW_VENV": _gate_python(),
            "OPENCLAW_GREEN_GATE_WORKTREE_ROOT": str(tmp_path / "gate-worktrees"),
            "OPENCLAW_GREEN_GATE_RUN_ROOT": str(tmp_path / "gate-runs"),
            "OPENCLAW_GREEN_GATE_LOCK_DIR": str(lock_dir),
            "OPENCLAW_GREEN_GATE_LOCK_STALE_SECONDS": "0",
            "OPENCLAW_GREEN_GATE_LOCK_POLL_SECONDS": "0",
            "OPENCLAW_TRUSTED_TEST_REF": "trusted",
            "OPENCLAW_PYTEST_TIMEOUT_SECONDS": "10",
        }
    )
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "trusted"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "reaping stale full gate lock" in output
    assert "FULL gate lock acquired" in output
    assert "PASS" in output
    assert not lock_dir.exists()


def test_green_gate_fast_mode_runs_subset_without_atomic_lock(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "pc4-harden@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "PC4 Harden Test"], cwd=repo, check=True)
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_fast.py").write_text("def test_fast():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "fast tests"], cwd=repo, check=True, capture_output=True, text=True)

    lock_dir = tmp_path / "full-gate.lock"
    lock_dir.mkdir()
    (lock_dir / "holder.env").write_text(f"pid={os.getpid()}\nstarted_epoch=1\n", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_REPO": str(repo),
            "OPENCLAW_VENV": _gate_python(),
            "OPENCLAW_GREEN_GATE_WORKTREE_ROOT": str(tmp_path / "gate-worktrees"),
            "OPENCLAW_GREEN_GATE_RUN_ROOT": str(tmp_path / "gate-runs"),
            "OPENCLAW_GREEN_GATE_LOCK_DIR": str(lock_dir),
            "OPENCLAW_GREEN_GATE_FAST_LOCK_ROOT": str(tmp_path / "fast-locks"),
            "OPENCLAW_FAST_PYTEST_ARGS": "tests/test_fast.py",
            "OPENCLAW_TRUSTED_TEST_REF": "main",
            "OPENCLAW_PYTEST_TIMEOUT_SECONDS": "10",
        }
    )
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--fast", "main"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "running FAST pre-gate" in output
    assert "restoring trusted tests from main" in output
    assert "FAST branch lock acquired" in output
    assert "FULL gate lock acquired" not in output
    assert lock_dir.exists()


def test_green_gate_fast_mode_auto_maps_changed_module_to_test(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "pc4-harden@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "PC4 Harden Test"], cwd=repo, check=True)
    (repo / "foo_bar.py").write_text("VALUE = 1\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo_bar.py").write_text(
        "import foo_bar\n\n\ndef test_foo_bar():\n    assert foo_bar.VALUE == 2\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "main"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "foo_bar.py").write_text("VALUE = 2\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "change module"], cwd=repo, check=True, capture_output=True, text=True)

    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_REPO": str(repo),
            "OPENCLAW_VENV": _gate_python(),
            "OPENCLAW_GREEN_GATE_WORKTREE_ROOT": str(tmp_path / "gate-worktrees"),
            "OPENCLAW_GREEN_GATE_RUN_ROOT": str(tmp_path / "gate-runs"),
            "OPENCLAW_GREEN_GATE_LOCK_DIR": str(tmp_path / "full.lock"),
            "OPENCLAW_GREEN_GATE_FAST_LOCK_ROOT": str(tmp_path / "fast-locks"),
            "OPENCLAW_FAST_BASE_REF": "main",
            "OPENCLAW_TRUSTED_TEST_REF": "main",
            "OPENCLAW_PYTEST_TIMEOUT_SECONDS": "10",
        }
    )
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--fast", "feature"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "auto-selected FAST pytest args from changed paths" in output
    assert "tests/test_foo_bar.py" in output
    assert "FULL gate lock acquired" not in output
