"""Live front-door resource probe for local model selection.

This module performs only local, non-model checks: GPU memory via nvidia-smi,
system RAM via /proc/meminfo, and resident Ollama model VRAM via /api/ps.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping
import urllib.request


DEFAULT_OLLAMA_PS_URL = "http://localhost:11434/api/ps"
WSL_NVIDIA_SMI = Path("/usr/lib/wsl/lib/nvidia-smi")
# Task 135: /api/ps intermittently reports NO resident models while nvidia-smi shows real
# card usage (observed live 2026-07-07 13:0x + 18:4x) -- residency credit lost entirely,
# forcing an unnecessary step-down from a genuinely resident model. Treat an empty ps result
# as UNKNOWN (not "genuinely idle") when the card shows more than this much used, and re-probe
# once before accepting it.
RESIDENCY_FLAKE_VRAM_USED_THRESHOLD_GB = 2.0


@dataclass(frozen=True)
class FrontdoorResourceSnapshot:
    available_vram_gb: float | None
    total_vram_gb: float | None
    available_ram_gb: float | None
    resident_models: list[dict[str, Any]]
    probe_errors: list[str]
    system_load_1m: float | None = None
    cpu_count: int | None = None
    residency_probe_flake: bool = False

    def to_receipt_fields(self) -> dict[str, Any]:
        return {
            "resource_probe_available_vram_gb": self.available_vram_gb,
            "resource_probe_total_vram_gb": self.total_vram_gb,
            "resource_probe_available_ram_gb": self.available_ram_gb,
            "resource_probe_resident_models": list(self.resident_models),
            "resource_probe_errors": list(self.probe_errors),
            "resource_probe_system_load_1m": self.system_load_1m,
            "resource_probe_cpu_count": self.cpu_count,
            "resource_probe_residency_probe_flake": self.residency_probe_flake,
        }

    def resident_vram_by_model_gb(self) -> dict[str, float]:
        by_model: dict[str, float] = {}
        for model in self.resident_models:
            name = str(model.get("name") or "").strip()
            size = model.get("size_vram_gb")
            if name and isinstance(size, (int, float)):
                by_model[name] = float(size)
        return by_model

    def offload_fraction_by_model(self) -> dict[str, float]:
        """Task 146: {model: size_vram/size} as recorded straight from /api/ps.

        1.0 = fully GPU-resident; lower = partially CPU-offloaded ("resident" but NOT
        fast -- the 2026-07-07 root cause was 6.0GB/2.4GB = 0.4, a 62s 20-token reply).
        Only models whose ps entry carried a usable total ``size`` appear; a missing
        entry means the fraction is UNKNOWN and selection must fail open to today's
        residency behavior.
        """
        by_model: dict[str, float] = {}
        for model in self.resident_models:
            name = str(model.get("name") or "").strip()
            fraction = model.get("offload_fraction")
            if name and isinstance(fraction, (int, float)):
                by_model[name] = float(fraction)
        return by_model

    def gpu_fraction_by_model(self, sizes: Mapping[str, Any]) -> dict[str, float]:
        return gpu_fraction_by_model(self.resident_vram_by_model_gb(), sizes)


def gpu_fraction_by_model(
    resident_vram_by_model_gb: Mapping[str, Any],
    sizes: Mapping[str, Any],
) -> dict[str, float]:
    """Return {model: resident_vram_gb / on_disk_size_gb}, clamped to 0..1."""

    fractions: dict[str, float] = {}
    for model, size_gb in dict(sizes or {}).items():
        name = str(model or "").strip()
        if not name or not isinstance(size_gb, (int, float)) or float(size_gb) <= 0:
            continue
        resident_gb = resident_vram_by_model_gb.get(name, 0.0) if resident_vram_by_model_gb else 0.0
        if not isinstance(resident_gb, (int, float)):
            resident_gb = 0.0
        fraction = float(resident_gb) / float(size_gb)
        fractions[name] = round(max(0.0, min(1.0, fraction)), 3)
    return fractions


def _round_gb(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def _nvidia_smi_path() -> str:
    return WSL_NVIDIA_SMI.as_posix() if WSL_NVIDIA_SMI.exists() else "nvidia-smi"


def _read_meminfo() -> str:
    return Path("/proc/meminfo").read_text(encoding="utf-8")


def _read_loadavg() -> str:
    return Path("/proc/loadavg").read_text(encoding="utf-8")


def _parse_mem_available_gb(meminfo: str) -> float | None:
    for line in str(meminfo or "").splitlines():
        if not line.startswith("MemAvailable:"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                return _round_gb(float(parts[1]) / (1024 * 1024))
            except ValueError:
                return None
    return None


def _parse_loadavg_1m(loadavg: str) -> float | None:
    first = str(loadavg or "").strip().split()[0:1]
    if not first:
        return None
    try:
        return round(float(first[0]), 3)
    except ValueError:
        return None


def _probe_gpu_memory(timeout: float) -> tuple[float | None, float | None, list[str]]:
    errors: list[str] = []
    try:
        result = subprocess.run(
            [
                _nvidia_smi_path(),
                "--query-gpu=memory.free,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return None, None, [f"nvidia_smi:{type(exc).__name__}"]
    if result.returncode != 0:
        errors.append(f"nvidia_smi_exit:{result.returncode}")
        return None, None, errors
    first = str(result.stdout or "").strip().splitlines()[0:1]
    if not first:
        return None, None, ["nvidia_smi_empty"]
    try:
        free_mib, total_mib = [float(part.strip()) for part in first[0].split(",", 1)]
    except (ValueError, IndexError):
        return None, None, ["nvidia_smi_parse"]
    return _round_gb(free_mib / 1024), _round_gb(total_mib / 1024), errors


def _probe_ollama_ps(url: str, timeout: float) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return [], [f"ollama_ps:{type(exc).__name__}"]
    models = payload.get("models") if isinstance(payload, dict) else []
    resident: list[dict[str, Any]] = []
    if not isinstance(models, list):
        return resident, ["ollama_ps_models_not_list"]
    for model in models:
        if not isinstance(model, dict):
            continue
        name = str(model.get("name") or model.get("model") or "").strip()
        size_vram = model.get("size_vram")
        if not name or not isinstance(size_vram, (int, float)):
            continue
        entry: dict[str, Any] = {"name": name, "size_vram_gb": _round_gb(float(size_vram) / 1e9)}
        # Task 146: "resident" alone lies -- /api/ps reported a model resident with
        # size=6.0GB but size_vram=2.4GB (60% CPU-offloaded, 62s for 20 tokens). Record
        # offload_fraction = size_vram/size so selection and receipts can see partial
        # offload. A missing/invalid total size leaves the fraction UNKNOWN (entry keeps
        # today's exact shape) so downstream behavior fails open.
        size_total = model.get("size")
        if isinstance(size_total, (int, float)) and float(size_total) > 0:
            entry["size_gb"] = _round_gb(float(size_total) / 1e9)
            entry["offload_fraction"] = round(
                max(0.0, min(1.0, float(size_vram) / float(size_total))), 3
            )
        resident.append(entry)
    return resident, []


def probe_frontdoor_resources(
    *,
    ollama_ps_url: str = DEFAULT_OLLAMA_PS_URL,
    timeout: float = 0.75,
) -> FrontdoorResourceSnapshot:
    errors: list[str] = []
    available_vram_gb, total_vram_gb, gpu_errors = _probe_gpu_memory(timeout)
    errors.extend(gpu_errors)
    try:
        available_ram_gb = _parse_mem_available_gb(_read_meminfo())
    except Exception as exc:
        available_ram_gb = None
        errors.append(f"meminfo:{type(exc).__name__}")
    try:
        system_load_1m = _parse_loadavg_1m(_read_loadavg())
    except Exception as exc:
        system_load_1m = None
        errors.append(f"loadavg:{type(exc).__name__}")
    try:
        cpu_count = os.cpu_count()
    except Exception as exc:
        cpu_count = None
        errors.append(f"cpu_count:{type(exc).__name__}")
    resident_models, ps_errors = _probe_ollama_ps(ollama_ps_url, timeout)
    errors.extend(ps_errors)
    residency_probe_flake = False
    vram_used_gb = (
        total_vram_gb - available_vram_gb
        if total_vram_gb is not None and available_vram_gb is not None
        else None
    )
    if (
        not resident_models
        and vram_used_gb is not None
        and vram_used_gb > RESIDENCY_FLAKE_VRAM_USED_THRESHOLD_GB
    ):
        # The card shows real usage but ps reported nothing resident -- likely a transient ps
        # flake, not a genuinely empty card. Re-probe once before concluding otherwise.
        retried_models, retry_errors = _probe_ollama_ps(ollama_ps_url, timeout)
        if retried_models:
            resident_models = retried_models
        else:
            residency_probe_flake = True
            errors.extend(f"residency_retry_{err}" for err in retry_errors)
    return FrontdoorResourceSnapshot(
        available_vram_gb=available_vram_gb,
        total_vram_gb=total_vram_gb,
        available_ram_gb=available_ram_gb,
        resident_models=resident_models,
        probe_errors=errors,
        system_load_1m=system_load_1m,
        cpu_count=cpu_count,
        residency_probe_flake=residency_probe_flake,
    )
