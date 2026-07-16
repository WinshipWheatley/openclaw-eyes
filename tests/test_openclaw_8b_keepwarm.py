from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import local_model_governance as governance
import openclaw_8b_keepwarm as keepwarm


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_openclaw_stack.sh"
SERVICE = ROOT / "systemd" / "user" / "openclaw-8b-keepwarm.service.in"
TIMER = ROOT / "systemd" / "user" / "openclaw-8b-keepwarm.timer.in"
RUNBOOK = ROOT / "docs" / "operations" / "OPENCLAW_8B_KEEPWARM_RUNBOOK.md"


def test_warmer_uses_only_strict_interactive_governance_and_shared_profile() -> None:
    observed: dict = {}

    def fake_run(call_model, **kwargs):
        observed["runner_kwargs"] = kwargs
        return governance.GovernedCallOutcome(
            "completed", "interactive_window", call_model()
        )

    def fake_ollama(prompt, **kwargs):
        observed["prompt"] = prompt
        observed["ollama_kwargs"] = kwargs
        return {
            "status": "success",
            "done_reason": "length",
            "elapsed_ms": 25,
            "model": governance.INTERACTIVE_MODEL,
            "text": "x",
        }

    receipt = keepwarm.run_keepwarm_once(
        run_interactive_fn=fake_run,
        resident_models_fn=set,
        ollama_call_fn=fake_ollama,
    )

    assert receipt["status"] == "warmed"
    assert receipt["reason"] == "interactive_window"
    assert observed["runner_kwargs"] == {
        "holder_id": "keepwarm:openclaw-8b",
        "require_idle_lease": True,
        "model_slot_max_wait_seconds": 0,
    }
    assert observed["prompt"] == "warm"
    assert observed["ollama_kwargs"]["model"] == governance.INTERACTIVE_MODEL
    assert observed["ollama_kwargs"]["timeout"] == 10
    assert observed["ollama_kwargs"]["attempts"] == 1
    assert observed["ollama_kwargs"]["think"] is False
    assert observed["ollama_kwargs"]["num_predict"] == 1
    assert observed["ollama_kwargs"]["options"] == governance.interactive_runner_options()
    assert observed["ollama_kwargs"]["keep_alive"] == "30m"
    assert observed["ollama_kwargs"]["return_metadata"] is True
    assert receipt["model_num_ctx"] == governance.INTERACTIVE_NUM_CTX == 2048


def test_warmer_defers_without_model_call_when_another_model_is_resident() -> None:
    model_called = False

    def fake_run(call_model, **_kwargs):
        return governance.GovernedCallOutcome(
            "completed", "interactive_window", call_model()
        )

    def fake_ollama(*_args, **_kwargs):
        nonlocal model_called
        model_called = True
        return {"status": "success"}

    receipt = keepwarm.run_keepwarm_once(
        run_interactive_fn=fake_run,
        resident_models_fn=lambda: {"mistral-small:latest"},
        ollama_call_fn=fake_ollama,
    )

    assert receipt["status"] == "deferred"
    assert receipt["reason"] == "other_model_resident"
    assert receipt["resident_model_count"] == 1
    assert model_called is False


def test_warmer_preserves_governance_defer_without_calling_ollama() -> None:
    model_called = False

    def fake_run(_call_model, **_kwargs):
        return governance.GovernedCallOutcome("deferred", "gpu_lease_active:build")

    def fake_ollama(*_args, **_kwargs):
        nonlocal model_called
        model_called = True

    receipt = keepwarm.run_keepwarm_once(
        run_interactive_fn=fake_run,
        resident_models_fn=set,
        ollama_call_fn=fake_ollama,
    )

    assert receipt["status"] == "deferred"
    assert receipt["reason"] == "gpu_lease_active:build"
    assert model_called is False


def test_receipt_is_atomic_private_and_excludes_model_text(tmp_path: Path) -> None:
    path = tmp_path / "receipts" / "latest.json"
    payload = {
        "schema_version": "openclaw_8b_keepwarm_receipt_v1",
        "status": "warmed",
        "reason": "interactive_window",
        "model": governance.INTERACTIVE_MODEL,
    }

    keepwarm.write_receipt(payload, path=path)

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == payload
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert not list(path.parent.glob("*.tmp"))
    assert "prompt" not in stored
    assert "response" not in stored
    assert "text" not in stored


def test_systemd_shape_uses_one_shot_ten_minute_timer_and_shared_runtime() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    timer = TIMER.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "Type=oneshot" in service
    assert "@PYTHON@ @REPO_ROOT@/openclaw_8b_keepwarm.py --once" in service
    assert "TimeoutStartSec=12" in service
    assert "Restart=" not in service
    assert "NoNewPrivileges=true" in service
    assert "PrivateTmp=true" in service
    assert "OnBootSec=2min" in timer
    assert "OnUnitActiveSec=10min" in timer
    assert "Persistent=false" in timer
    assert "Unit=openclaw-8b-keepwarm.service" in timer
    assert "WantedBy=timers.target" in timer
    assert "resident within 15 minutes" in runbook
    assert "first-touch latency" in runbook
    assert "systemctl --user disable --now openclaw-8b-keepwarm.timer" in runbook


def test_rendered_systemd_units_verify(tmp_path: Path) -> None:
    replacements = {
        "@REPO_ROOT@": str(ROOT),
        "@PYTHON@": "/home/openclaw/chief_env/bin/python",
    }
    rendered_paths = []
    for template in (SERVICE, TIMER):
        rendered = template.read_text(encoding="utf-8")
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        destination = tmp_path / template.name.removesuffix(".in")
        destination.write_text(rendered, encoding="utf-8")
        rendered_paths.append(destination)

    completed = subprocess.run(
        ["systemd-analyze", "verify", *(str(path) for path in rendered_paths)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_scoped_installer_adds_and_enables_only_keepwarm_units(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "systemctl.calls"
    fake_systemctl = fake_bin / "systemctl"
    fake_systemctl.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"${SYSTEMCTL_CALLS}\"\n",
        encoding="utf-8",
    )
    fake_systemctl.chmod(0o755)
    home = tmp_path / "home"
    env = dict(os.environ)
    env.update(
        HOME=str(home),
        PATH=f"{fake_bin}:{env['PATH']}",
        SYSTEMCTL_CALLS=str(calls),
    )

    completed = subprocess.run(
        [
            "bash",
            str(INSTALLER),
            "--apply",
            "--enable",
            "--keepwarm-only",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    installed = {
        path.name for path in (home / ".config" / "systemd" / "user").iterdir()
    }
    assert installed == {
        "openclaw-8b-keepwarm.service",
        "openclaw-8b-keepwarm.timer",
    }
    assert calls.read_text(encoding="utf-8").splitlines() == [
        "--user daemon-reload",
        "--user enable --now openclaw-8b-keepwarm.timer",
    ]


def test_keepwarm_units_are_excluded_from_unscoped_installer_collection() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert "--keepwarm-only" in source
    assert "KEEPWARM_UNIT_NAMES=(" in source
    assert "skip_keepwarm_in_broad_mode" in source
