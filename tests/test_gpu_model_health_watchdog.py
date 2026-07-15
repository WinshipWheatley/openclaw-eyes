from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 13, 16, 0, tzinfo=timezone.utc).timestamp()
NOW_TEXT = datetime.fromtimestamp(NOW, timezone.utc).isoformat().replace("+00:00", "Z")


def _watchdog():
    return importlib.import_module("gpu_model_health_watchdog")


def _loaded(model: str = "model-a", *, size: int = 1_000, size_vram: int = 600) -> dict:
    return {
        "model": model,
        "size_bytes": size,
        "size_vram_bytes": size_vram,
        "vram_fraction": size_vram / size,
    }


def _vote(**overrides: object) -> dict:
    vote = {
        "timestamp": NOW_TEXT,
        "model": "model-a",
        "status": "success",
        "done_reason": "stop",
        "elapsed_ms": 7_999,
        "timeout": 8.0,
    }
    vote.update(overrides)
    return vote


def _evaluate(*, votes: list[dict] | None = None, loaded_models: list[dict] | None = None,
              reachable: bool = True) -> dict:
    watchdog = _watchdog()
    return watchdog.evaluate_health(
        ollama_reachable=reachable,
        loaded_models=[_loaded()] if loaded_models is None else loaded_models,
        vote_evidence=[_vote()] if votes is None else votes,
        gpu_memory={"available": True, "used_mib": 300, "free_mib": 700, "total_mib": 1_000},
        now_epoch=NOW,
        budget_seconds=8.0,
        freshness_seconds=300.0,
    )


def test_vote_log_retains_only_allowlisted_contract_vote_fields(tmp_path: Path) -> None:
    watchdog = _watchdog()
    path = tmp_path / "ollama_diagnostics.jsonl"
    rows = [
        {"task_class": "other", "prompt": "ignore-me"},
        {
            "task_class": "contract_semantic_vote",
            "timestamp": NOW_TEXT,
            "model": "model-a",
            "status": "exception",
            "done_reason": "timeout",
            "elapsed_ms": 8_001,
            "timeout": 8,
            "exception_type": "TimeoutError",
            "exception": "raw-secret-exception",
            "response_metadata": {"secret": "metadata-secret"},
            "context": "private-context",
            "prompt": "private-prompt",
            "messages": ["private-message"],
        },
        "not-json",
    ]
    path.write_text("\n".join(json.dumps(row) if isinstance(row, dict) else row for row in rows) + "\n")

    evidence = watchdog.read_vote_evidence(path)

    assert evidence == [{
        "timestamp": NOW_TEXT,
        "model": "model-a",
        "status": "exception",
        "done_reason": "timeout",
        "elapsed_ms": 8_001,
        "timeout": 8,
        "exception_type": "TimeoutError",
    }]
    serialized = json.dumps(evidence)
    assert not any(secret in serialized for secret in (
        "raw-secret-exception", "metadata-secret", "private-context",
        "private-prompt", "private-message",
    ))


def test_vote_log_neutralizes_control_and_markdown_delimiter_characters(
    tmp_path: Path,
) -> None:
    watchdog = _watchdog()
    path = tmp_path / "ollama_diagnostics.jsonl"
    path.write_text(
        json.dumps({
            "task_class": "contract_semantic_vote",
            "timestamp": NOW_TEXT,
            "model": "model-a\n`injected`",
            "status": "success\rnext-line",
            "exception_type": "ValueError\u007fhidden",
        }) + "\n",
        encoding="utf-8",
    )

    evidence = watchdog.read_vote_evidence(path)

    assert evidence == [{
        "timestamp": NOW_TEXT,
        "model": "model-a 'injected'",
        "status": "success next-line",
        "exception_type": "ValueError hidden",
    }]
    assert not any(char in json.dumps(evidence) for char in ("`", "\\n", "\\r", "\\u007f"))


def test_vote_log_tail_is_bounded_to_256_kib_and_200_rows(tmp_path: Path) -> None:
    watchdog = _watchdog()
    path = tmp_path / "ollama_diagnostics.jsonl"
    old_secret = "DO-NOT-EXPORT-OLD-SECRET"
    oversized_old_row = {
        "task_class": "contract_semantic_vote",
        "timestamp": NOW_TEXT,
        "model": "old-model",
        "status": "success",
        "prompt": old_secret + ("x" * (watchdog.MAX_TAIL_BYTES + 1_024)),
    }
    rows = [oversized_old_row] + [
        {
            "task_class": "contract_semantic_vote",
            "timestamp": NOW_TEXT,
            "model": f"model-{index}",
            "status": "success",
            "elapsed_ms": index,
        }
        for index in range(205)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    evidence = watchdog.read_vote_evidence(path)

    assert len(evidence) == 200
    assert evidence[0]["model"] == "model-5"
    assert evidence[-1]["model"] == "model-204"
    assert old_secret not in json.dumps(evidence)
    assert watchdog.MAX_TAIL_BYTES == 256 * 1024
    assert watchdog.MAX_TAIL_ROWS == 200


def test_ollama_ps_and_nvidia_smi_parsing_are_minimal_and_aggregate() -> None:
    watchdog = _watchdog()
    models = watchdog.sanitize_ollama_ps({
        "models": [{
            "name": "model-a",
            "size": 1_000,
            "size_vram": 600,
            "details": {"private": "drop-me"},
            "digest": "drop-me-too",
        }]
    })

    assert models == [_loaded()]
    assert watchdog.parse_nvidia_smi("100, 900, 1024\n200, 800, 1024\n") == {
        "available": True,
        "gpu_count": 2,
        "used_mib": 300,
        "free_mib": 1_700,
        "total_mib": 2_048,
    }


def test_ollama_ps_rejects_zero_size_model_row() -> None:
    watchdog = _watchdog()

    models = watchdog.sanitize_ollama_ps({
        "models": [{"name": "model-a", "size": 0, "size_vram": 0}],
    })

    assert models == []


def test_live_probes_use_get_and_read_only_nvidia_query() -> None:
    watchdog = _watchdog()
    seen: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return b'{"models": []}'

    def opener(request, *, timeout: float):
        seen["request"] = request
        seen["timeout"] = timeout
        return Response()

    def runner(command, **kwargs):
        seen["command"] = command
        seen["run_kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="64, 960, 1024\n", stderr="")

    ollama = watchdog.fetch_ollama_ps(opener=opener)
    gpu = watchdog.read_nvidia_memory(run=runner)

    request = seen["request"]
    assert request.full_url == "http://127.0.0.1:11434/api/ps"
    assert request.get_method() == "GET"
    assert request.data is None
    assert ollama == {"reachable": True, "loaded_models": []}
    assert seen["command"] == [
        "nvidia-smi",
        "--query-gpu=memory.used,memory.free,memory.total",
        "--format=csv,noheader,nounits",
    ]
    assert seen["run_kwargs"]["shell"] is False
    assert gpu["used_mib"] == 64
    assert gpu["free_mib"] == 960
    assert gpu["total_mib"] == 1_024


@pytest.mark.parametrize(
    ("vote", "reason"),
    [
        (_vote(status="timeout", done_reason="timeout"), "recent_vote_timeout"),
        (_vote(status="exception", exception_type="RuntimeError"), "recent_vote_exception"),
        (_vote(elapsed_ms=8_001), "vote_elapsed_over_budget"),
    ],
)
def test_recent_timeout_exception_or_over_budget_is_degraded(vote: dict, reason: str) -> None:
    result = _evaluate(votes=[vote])

    assert result["status"] == "degraded"
    assert reason in result["reason_codes"]


def test_ollama_unreachable_is_degraded_even_without_vote_evidence() -> None:
    result = _evaluate(reachable=False, votes=[], loaded_models=[])

    assert result["status"] == "degraded"
    assert result["reason_codes"] == ["ollama_unreachable"]


def test_selected_model_below_half_vram_is_degraded() -> None:
    result = _evaluate(loaded_models=[_loaded(size_vram=499)])

    assert result["status"] == "degraded"
    assert "selected_model_mostly_cpu_offloaded" in result["reason_codes"]


@pytest.mark.parametrize("fraction", [None, float("nan"), float("inf")])
def test_loaded_model_with_unmeasurable_vram_fraction_is_unknown(fraction: float | None) -> None:
    loaded = _loaded()
    loaded["vram_fraction"] = fraction

    result = _evaluate(loaded_models=[loaded])

    assert result["status"] == "unknown"
    assert result["reason_codes"] == ["selected_model_vram_fraction_unknown"]


@pytest.mark.parametrize(
    ("votes", "loaded_models", "reason"),
    [
        ([], [_loaded()], "vote_evidence_missing"),
        ([_vote(timestamp="2026-07-13T15:54:59Z")], [_loaded()], "vote_evidence_stale"),
        ([_vote()], [], "selected_model_unloaded"),
    ],
)
def test_missing_stale_or_unloaded_evidence_is_unknown(
    votes: list[dict], loaded_models: list[dict], reason: str,
) -> None:
    result = _evaluate(votes=votes, loaded_models=loaded_models)

    assert result["status"] == "unknown"
    assert reason in result["reason_codes"]


def test_recent_success_under_budget_with_loaded_model_can_be_healthy() -> None:
    result = _evaluate()

    assert result["status"] == "healthy"
    assert result["reason_codes"] == ["recent_vote_success_under_budget"]
    assert result["selected_model"]["vram_fraction"] == pytest.approx(0.6)


def test_collection_uses_typed_contract_vote_budget(monkeypatch, tmp_path: Path) -> None:
    watchdog = _watchdog()
    diagnostics = tmp_path / "ollama_diagnostics.jsonl"
    diagnostics.write_text(json.dumps({"task_class": "contract_semantic_vote", **_vote()}) + "\n")
    monkeypatch.setattr("typed_contract_decision.semantic_vote_timeout_seconds", lambda: 8.0)

    snapshot = watchdog.collect_health_snapshot(
        diagnostics_path=diagnostics,
        now_epoch=NOW,
        fetch_ollama_fn=lambda: {"reachable": True, "loaded_models": [_loaded()]},
        read_gpu_memory_fn=lambda: {
            "available": True, "gpu_count": 1, "used_mib": 300,
            "free_mib": 700, "total_mib": 1_000,
        },
    )

    assert snapshot["budget_seconds"] == 8.0
    assert snapshot["status"] == "healthy"
    assert snapshot["authority"] == {
        "observation_only": True,
        "model_invocation_allowed": False,
        "service_or_process_mutation_allowed": False,
        "external_notification_allowed": False,
    }


def test_read_models_are_atomic_lf_only_and_leave_no_temp_files(
    monkeypatch, tmp_path: Path,
) -> None:
    watchdog = _watchdog()
    snapshot = _evaluate()
    snapshot.update({"schema_version": "gpu_model_health.v1", "generated_at": NOW_TEXT})
    replacements: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def replace(source, target) -> None:
        source_path, target_path = Path(source), Path(target)
        assert source_path.exists()
        assert source_path.parent == target_path.parent
        replacements.append((source_path, target_path))
        real_replace(source_path, target_path)

    monkeypatch.setattr(watchdog.os, "replace", replace)

    paths = watchdog.write_read_models(snapshot, output_dir=tmp_path)

    assert paths["json"] == tmp_path / "gpu_model_health.json"
    assert paths["operator"] == tmp_path / "gpu_model_health_OPERATOR.md"
    assert len(replacements) == 2
    for path in paths.values():
        content = path.read_bytes()
        assert b"\r" not in content
        assert content.endswith(b"\n")
    assert json.loads(paths["json"].read_text()) == snapshot
    assert not list(tmp_path.glob("*.tmp"))


def test_source_is_observation_only_and_contains_no_mutation_or_model_call_paths() -> None:
    source = (ROOT / "gpu_model_health_watchdog.py").read_text(encoding="utf-8").lower()
    forbidden = (
        "/api/generate", "keep_alive", "ollama run", "ollama pull",
        "systemctl restart", "service mutation", "process mutation",
        "hermes_observer",
    )

    assert not any(value in source for value in forbidden)
    assert not re.search(r"\b(?:kill|pkill)\b", source)
    assert "8b" not in source
    assert 'method="post"' not in source and "method='post'" not in source


def _shell_array(source: str, name: str) -> str:
    match = re.search(rf"{name}=\(\n(?P<body>.*?)\n\)", source, flags=re.DOTALL)
    assert match is not None
    return match.group("body")


def test_systemd_timer_boot_manifest_runbook_and_tracking_contracts() -> None:
    service = (ROOT / "systemd/user/openclaw-gpu-model-health.service.in").read_text()
    timer = (ROOT / "systemd/user/openclaw-gpu-model-health.timer.in").read_text()
    manifest = (ROOT / "scripts/openclaw_boot_manifest.sh").read_text()
    runbook = (ROOT / "docs/operations/GPU_MODEL_HEALTH_WATCHDOG_RUNBOOK.md").read_text()

    assert "Type=oneshot" in service
    assert "@REPO_ROOT@/chief_env/bin/python" in service
    assert "@REPO_ROOT@/gpu_model_health_watchdog.py --once" in service
    assert "ExecStartPost=" not in service
    assert "hermes_observer.py" not in service
    assert "TimeoutStartSec=30" in service
    assert "NoNewPrivileges=true" in service
    assert "PrivateTmp=true" in service
    assert "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/lib/wsl/lib" in service
    assert "UnsetEnvironment=HTTP_PROXY HTTPS_PROXY ALL_PROXY" in service
    assert "UnsetEnvironment=http_proxy https_proxy all_proxy" in service
    assert "OnBootSec=2min" in timer
    assert "OnUnitActiveSec=60s" in timer
    assert "AccuracySec=10s" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer
    assert "openclaw-gpu-model-health.timer" in _shell_array(manifest, "OPENCLAW_BOOT_AUX_TIMERS")
    assert "openclaw-gpu-model-health.service" not in _shell_array(manifest, "OPENCLAW_BOOT_SERVICES")
    assert "openclaw-gpu-model-health.service" not in _shell_array(manifest, "OPENCLAW_BOOT_AUX_SERVICES")
    assert "operator approval" in runbook.lower()
    assert "Hermes" not in runbook

    from generated_read_model_files import VOLATILE_SELF_REPORT_READ_MODEL_FILES

    assert "gpu_model_health.json" in VOLATILE_SELF_REPORT_READ_MODEL_FILES
    assert "gpu_model_health_OPERATOR.md" in VOLATILE_SELF_REPORT_READ_MODEL_FILES
    for relative_path in ("gpu_model_health_watchdog.py", "tests/test_gpu_model_health_watchdog.py"):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", relative_path], cwd=ROOT, check=False,
        )
        assert ignored.returncode != 0
