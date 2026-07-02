from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polish_loop.build_lifecycle_registry import BuildLifecycleRegistry
from polish_loop.control_plane import ControlPlaneLedger
from polish_loop.gpu_arbiter import GPUArbiter
from polish_loop.worker_runtime import WorkerRuntimeConfig, run_local_builder_worker


def _ledger(tmp_path: Path) -> ControlPlaneLedger:
    return ControlPlaneLedger(tmp_path / "control.sqlite3")


def _admit_and_claim(ledger: ControlPlaneLedger, *, task_id: str = "resource-aware-task"):
    ledger.admit_task(
        task_id=task_id,
        source="human_intent",
        task_type="synthetic_resource_aware",
        requested_status="READY",
        payload={"goal": "prove resource-aware build wiring", "synthetic": True},
        acceptance_ref={"synthetic": True},
    )
    lease = ledger.claim_task(task_id, owner="worker-test", lease_seconds=900)
    assert lease is not None
    return lease


def _config(tmp_path: Path, **overrides) -> WorkerRuntimeConfig:
    loop_dir = tmp_path / "loop"
    defaults = dict(
        local_builder_path=tmp_path / "never-run-local-builder.py",
        loop_dir=loop_dir,
        task_path=loop_dir / "task.md",
        pc_output_path=loop_dir / "current" / "pc_output.md",
        artifact_dir=loop_dir / "current",
        subprocess_timeout_seconds=2,
        gpu_heartbeat_interval_seconds=0.05,
    )
    defaults.update(overrides)
    return WorkerRuntimeConfig(**defaults)


def _success_runner(command, *, cwd, env, capture_output, text, timeout, check):
    Path(env["PHASE_C_PC_OUTPUT"]).parent.mkdir(parents=True, exist_ok=True)
    Path(env["PHASE_C_PC_OUTPUT"]).write_text("PASS: 1\nSTATUS: DONE\n", encoding="utf-8")
    return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")


def test_lease_and_lifecycle_dbs_default_under_loop_dir_not_real_home(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path)

    result = run_local_builder_worker(ledger, lease, config=config, runner=_success_runner)

    assert result.submitted_candidate is True
    assert (config.loop_dir / "gpu_leases.sqlite").exists()
    assert (config.loop_dir / "build_lifecycle.sqlite").exists()
    assert not Path("/home/openclaw/.openclaw/polish_loop/gpu_leases.sqlite").exists()
    assert not Path("/home/openclaw/.openclaw/polish_loop/build_lifecycle.sqlite").exists()


def test_happy_path_acquires_and_releases_lease_and_records_lifecycle(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path)

    result = run_local_builder_worker(ledger, lease, config=config, runner=_success_runner)

    assert result.submitted_candidate is True
    assert getattr(result, "deferred", False) is False
    arbiter = GPUArbiter(config.loop_dir / "gpu_leases.sqlite")
    assert arbiter.current() is None  # lease was released, not leaked

    registry = BuildLifecycleRegistry(config.loop_dir / "build_lifecycle.sqlite")
    build_unit_id = f"{lease.task_id}:{lease.attempt_no}"
    stages = [event["stage"] for event in registry.history(build_unit_id)]
    assert stages[0] == "requested"
    assert "routed" in stages
    assert "leased" in stages
    assert "running" in stages
    assert "released" in stages
    assert stages[-1] == "verified"


def test_defers_when_interactive_lease_is_active_and_never_invokes_runner(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path)
    arbiter = GPUArbiter(config.loop_dir / "gpu_leases.sqlite")
    arbiter.acquire("interactive", "cassandra-chat", ttl_seconds=900)

    def forbidden_runner(*args, **kwargs):
        raise AssertionError("local model must not be invoked while GPU is interactive-held")

    result = run_local_builder_worker(ledger, lease, config=config, runner=forbidden_runner)

    assert result.deferred is True
    assert result.defer_reason == "interactive_gpu_lease_active"
    assert result.submitted_candidate is False
    assert result.failure_recorded is False

    # Honest deferral: the ledger lease must not be falsely marked failed/blocked.
    row = ledger.get_task(lease.task_id)
    assert row["status"] == "LEASED"

    registry = BuildLifecycleRegistry(config.loop_dir / "build_lifecycle.sqlite")
    build_unit_id = f"{lease.task_id}:{lease.attempt_no}"
    stages = [event["stage"] for event in registry.history(build_unit_id)]
    assert stages == ["requested", "deferred"]
    # The interactive holder must be completely unaffected by our defer.
    assert arbiter.current()["holder_id"] == "cassandra-chat"


def test_defers_when_acquire_is_denied_at_mechanism_level(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path)
    arbiter = GPUArbiter(config.loop_dir / "gpu_leases.sqlite")
    # route_build_capability only defers at the policy layer for an active
    # *interactive* lease; a second concurrent *build* holder is invisible to that
    # snapshot check and only surfaces when we actually try to acquire.
    arbiter.acquire("build", "other-build-unit", ttl_seconds=900)

    def forbidden_runner(*args, **kwargs):
        raise AssertionError("local model must not be invoked when the GPU lease acquire is denied")

    result = run_local_builder_worker(ledger, lease, config=config, runner=forbidden_runner)

    assert result.deferred is True
    assert "resource_busy" in result.defer_reason
    assert result.submitted_candidate is False

    registry = BuildLifecycleRegistry(config.loop_dir / "build_lifecycle.sqlite")
    build_unit_id = f"{lease.task_id}:{lease.attempt_no}"
    stages = [event["stage"] for event in registry.history(build_unit_id)]
    assert "lease_denied" in stages


def test_heartbeats_during_a_slow_runner(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path, gpu_heartbeat_interval_seconds=0.02, subprocess_timeout_seconds=5)
    heartbeat_calls: list[dict] = []
    original_heartbeat = GPUArbiter.heartbeat

    def spying_heartbeat(self, *args, **kwargs):
        result = original_heartbeat(self, *args, **kwargs)
        heartbeat_calls.append(result)
        return result

    monkeypatch.setattr(GPUArbiter, "heartbeat", spying_heartbeat)

    def slow_runner(command, *, cwd, env, capture_output, text, timeout, check):
        time.sleep(0.3)
        Path(env["PHASE_C_PC_OUTPUT"]).parent.mkdir(parents=True, exist_ok=True)
        Path(env["PHASE_C_PC_OUTPUT"]).write_text("PASS: 1\nSTATUS: DONE\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    result = run_local_builder_worker(ledger, lease, config=config, runner=slow_runner)

    assert result.submitted_candidate is True
    assert len(heartbeat_calls) >= 1
    assert all(call["status"] == "heartbeat_recorded" for call in heartbeat_calls)


def test_preemption_mid_run_triggers_model_unload(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path, gpu_heartbeat_interval_seconds=0.02, subprocess_timeout_seconds=5)
    unload_calls: list[str] = []

    import polish_loop.worker_runtime as worker_runtime_module

    def fake_unload(model, *, base_url=None, timeout=None):
        unload_calls.append(model)
        return {"status": "unloaded", "model": model}

    monkeypatch.setattr(worker_runtime_module, "unload_model", fake_unload)

    def preempting_runner(command, *, cwd, env, capture_output, text, timeout, check):
        # Simulate an interactive session grabbing the GPU mid-build.
        interactive_arbiter = GPUArbiter(config.loop_dir / "gpu_leases.sqlite")
        interactive_arbiter.acquire("interactive", "cassandra-chat", ttl_seconds=900)
        time.sleep(0.25)  # give the background heartbeat thread a chance to notice
        Path(env["PHASE_C_PC_OUTPUT"]).parent.mkdir(parents=True, exist_ok=True)
        Path(env["PHASE_C_PC_OUTPUT"]).write_text("PASS: 1\nSTATUS: DONE\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    run_local_builder_worker(ledger, lease, config=config, runner=preempting_runner)

    assert unload_calls == [config.model]

    registry = BuildLifecycleRegistry(config.loop_dir / "build_lifecycle.sqlite")
    build_unit_id = f"{lease.task_id}:{lease.attempt_no}"
    stages = [event["stage"] for event in registry.history(build_unit_id)]
    assert "preempted" in stages


def test_initial_acquire_preemption_signal_unloads_before_running(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path)
    unload_calls: list[str] = []

    import polish_loop.worker_runtime as worker_runtime_module

    def fake_unload(model, *, base_url=None, timeout=None):
        unload_calls.append(model)
        return {"status": "unloaded", "model": model}

    monkeypatch.setattr(worker_runtime_module, "unload_model", fake_unload)

    def fake_acquire(self, holder_type, holder_id, **kwargs):
        return {
            "status": "acquired_preempted_build",
            "holder_type": holder_type,
            "holder_id": holder_id,
            "lease_nonce": "fake-nonce",
            "preemption_required": True,
            "recommended_keep_alive": "0",
        }

    monkeypatch.setattr(GPUArbiter, "acquire", fake_acquire)
    monkeypatch.setattr(GPUArbiter, "heartbeat", lambda self, *a, **k: {"status": "heartbeat_recorded"})
    monkeypatch.setattr(GPUArbiter, "release", lambda self, *a, **k: {"status": "released"})

    run_local_builder_worker(ledger, lease, config=config, runner=_success_runner)

    assert config.model in unload_calls


def test_lease_is_released_even_when_runner_raises_timeout(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path, subprocess_timeout_seconds=1)

    def timing_out_runner(command, *, cwd, env, capture_output, text, timeout, check):
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

    result = run_local_builder_worker(ledger, lease, config=config, runner=timing_out_runner)

    assert result.failure_recorded is True
    arbiter = GPUArbiter(config.loop_dir / "gpu_leases.sqlite")
    assert arbiter.current() is None  # released despite the timeout

    registry = BuildLifecycleRegistry(config.loop_dir / "build_lifecycle.sqlite")
    build_unit_id = f"{lease.task_id}:{lease.attempt_no}"
    stages = [event["stage"] for event in registry.history(build_unit_id)]
    assert "released" in stages
    assert "failed" in stages


def test_lease_is_released_even_when_runner_missing(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    config = _config(tmp_path)

    def missing_runner(command, *, cwd, env, capture_output, text, timeout, check):
        raise FileNotFoundError("local_builder.py not found")

    result = run_local_builder_worker(ledger, lease, config=config, runner=missing_runner)

    assert result.failure_recorded is True
    arbiter = GPUArbiter(config.loop_dir / "gpu_leases.sqlite")
    assert arbiter.current() is None  # released despite failing to start
