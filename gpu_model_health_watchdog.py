"""One-shot, observation-only GPU model health read-model exporter."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
OLLAMA_PS_URL = "http://127.0.0.1:11434/api/ps"
DIAGNOSTICS_PATH = Path("/mnt/c/OpenClaw/logs/ollama_diagnostics.jsonl")
READ_MODEL_DIR = ROOT / "generated" / "read_models"
MAX_TAIL_BYTES = 256 * 1024
MAX_TAIL_ROWS = 200
MAX_OLLAMA_RESPONSE_BYTES = 1024 * 1024
DEFAULT_FRESHNESS_SECONDS = 300.0
MIN_VRAM_FRACTION = 0.5
VOTE_FIELDS = (
    "timestamp",
    "model",
    "status",
    "done_reason",
    "elapsed_ms",
    "timeout",
    "exception_type",
)


def _bounded_tail_lines(
    path: Path,
    *,
    max_bytes: int = MAX_TAIL_BYTES,
    max_rows: int = MAX_TAIL_ROWS,
) -> list[str]:
    """Read at most the bounded suffix and discard an initial partial row."""
    try:
        size = path.stat().st_size
        amount = min(size, max_bytes)
        with path.open("rb") as handle:
            handle.seek(size - amount)
            payload = handle.read(amount)
    except (FileNotFoundError, OSError):
        return []

    if size > amount:
        separator = payload.find(b"\n")
        if separator < 0:
            return []
        payload = payload[separator + 1:]
    return payload.decode("utf-8", errors="replace").splitlines()[-max_rows:]


def _safe_text(value: str, *, limit: int = 240) -> str:
    neutralized = "".join(
        " " if ord(character) < 32 or ord(character) == 127 else character
        for character in value
    )
    return neutralized.replace("`", "'")[:limit]


def _safe_vote_value(key: str, value: Any) -> Any | None:
    if key in {"elapsed_ms", "timeout"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        if not math.isfinite(number) or number < 0:
            return None
        return value
    if key == "timestamp" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return value if math.isfinite(float(value)) else None
    if not isinstance(value, str):
        return None
    return _safe_text(value)


def read_vote_evidence(
    path: str | Path = DIAGNOSTICS_PATH,
    *,
    max_bytes: int = MAX_TAIL_BYTES,
    max_rows: int = MAX_TAIL_ROWS,
) -> list[dict[str, Any]]:
    """Return sanitized semantic-vote rows from a bounded diagnostic suffix."""
    evidence: list[dict[str, Any]] = []
    for line in _bounded_tail_lines(Path(path), max_bytes=max_bytes, max_rows=max_rows):
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(row, Mapping) or row.get("task_class") != "contract_semantic_vote":
            continue
        sanitized: dict[str, Any] = {}
        for key in VOTE_FIELDS:
            if key not in row:
                continue
            value = _safe_vote_value(key, row.get(key))
            if value is not None:
                sanitized[key] = value
        if sanitized:
            evidence.append(sanitized)
    return evidence[-max_rows:]


def sanitize_ollama_ps(payload: Mapping[str, Any] | Any) -> list[dict[str, Any]]:
    models = payload.get("models") if isinstance(payload, Mapping) else None
    if not isinstance(models, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for row in models:
        if not isinstance(row, Mapping):
            continue
        name = row.get("name") or row.get("model")
        size = row.get("size")
        size_vram = row.get("size_vram")
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(size, bool) or not isinstance(size, (int, float)):
            continue
        size_number = float(size)
        if not math.isfinite(size_number) or size_number <= 0:
            continue
        if isinstance(size_vram, bool) or not isinstance(size_vram, (int, float)):
            continue
        size_vram_number = float(size_vram)
        if not math.isfinite(size_vram_number) or size_vram_number < 0:
            continue
        fraction = size_vram_number / size_number
        safe_name = _safe_text(name).strip()
        sanitized.append({
            "model": safe_name,
            "size_bytes": size,
            "size_vram_bytes": size_vram,
            "vram_fraction": fraction,
        })
    return sanitized


def fetch_ollama_ps(
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    request = urllib.request.Request(OLLAMA_PS_URL, method="GET")
    try:
        with opener(request, timeout=timeout_seconds) as response:
            raw = response.read(MAX_OLLAMA_RESPONSE_BYTES + 1)
        if len(raw) > MAX_OLLAMA_RESPONSE_BYTES:
            raise ValueError("response_too_large")
        payload = json.loads(raw.decode("utf-8"))
        return {"reachable": True, "loaded_models": sanitize_ollama_ps(payload)}
    except Exception as exc:
        return {
            "reachable": False,
            "loaded_models": [],
            "exception_type": type(exc).__name__,
        }


def _memory_number(value: str) -> int | float:
    number = float(value.strip())
    if not math.isfinite(number) or number < 0:
        raise ValueError("invalid_gpu_memory_value")
    return int(number) if number.is_integer() else number


def parse_nvidia_smi(text: str) -> dict[str, Any]:
    used_total: int | float = 0
    free_total: int | float = 0
    count = 0
    for line in str(text or "").splitlines():
        if not line.strip():
            continue
        columns = line.split(",")
        if len(columns) != 2:
            raise ValueError("unexpected_gpu_memory_columns")
        used_total += _memory_number(columns[0])
        free_total += _memory_number(columns[1])
        count += 1
    if count == 0:
        raise ValueError("gpu_memory_rows_missing")
    return {
        "available": True,
        "gpu_count": count,
        "used_mib": used_total,
        "free_mib": free_total,
        "total_mib": used_total + free_total,
    }


def read_nvidia_memory(
    *,
    run: Callable[..., Any] = subprocess.run,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError("gpu_query_failed")
        return parse_nvidia_smi(result.stdout)
    except Exception as exc:
        return {"available": False, "exception_type": type(exc).__name__}


def _timestamp_epoch(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(float(value)) else None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.timestamp()


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def evaluate_health(
    *,
    ollama_reachable: bool,
    loaded_models: Sequence[Mapping[str, Any]],
    vote_evidence: Sequence[Mapping[str, Any]],
    gpu_memory: Mapping[str, Any],
    now_epoch: float,
    budget_seconds: float,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
) -> dict[str, Any]:
    """Classify only current observations; absence never becomes healthy."""
    result: dict[str, Any] = {
        "status": "unknown",
        "reason_codes": [],
        "selected_model": None,
        "latest_vote": dict(vote_evidence[-1]) if vote_evidence else None,
        "gpu_memory": dict(gpu_memory),
    }
    if not ollama_reachable:
        result.update(status="degraded", reason_codes=["ollama_unreachable"])
        return result
    if not vote_evidence:
        result["reason_codes"] = ["vote_evidence_missing"]
        return result

    latest = dict(vote_evidence[-1])
    event_epoch = _timestamp_epoch(latest.get("timestamp"))
    if event_epoch is None:
        result["reason_codes"] = ["vote_evidence_stale"]
        return result
    age_seconds = float(now_epoch) - event_epoch
    result["evidence_age_seconds"] = max(0.0, age_seconds)
    if age_seconds < 0 or age_seconds > freshness_seconds:
        result["reason_codes"] = ["vote_evidence_stale"]
        return result

    status = str(latest.get("status") or "").strip().lower()
    done_reason = str(latest.get("done_reason") or "").strip().lower()
    exception_type = str(latest.get("exception_type") or "").strip()
    elapsed_ms = _finite_number(latest.get("elapsed_ms"))
    degraded_reasons: list[str] = []
    is_timeout = status == "timeout" or done_reason == "timeout"
    if is_timeout:
        degraded_reasons.append("recent_vote_timeout")
    if (status == "exception" or exception_type) and not is_timeout:
        degraded_reasons.append("recent_vote_exception")
    if elapsed_ms is not None and elapsed_ms > float(budget_seconds) * 1000.0:
        degraded_reasons.append("vote_elapsed_over_budget")
    if degraded_reasons:
        result.update(status="degraded", reason_codes=degraded_reasons)
        return result

    selected_name = latest.get("model")
    if not isinstance(selected_name, str) or not selected_name.strip():
        result["reason_codes"] = ["selected_model_missing"]
        return result
    selected_name = selected_name.strip()
    selected = next(
        (dict(model) for model in loaded_models if model.get("model") == selected_name),
        None,
    )
    if selected is None:
        result["selected_model"] = {"model": selected_name, "loaded": False}
        result["reason_codes"] = ["selected_model_unloaded"]
        return result
    selected["loaded"] = True
    result["selected_model"] = selected

    fraction = _finite_number(selected.get("vram_fraction"))
    if fraction is None:
        result["reason_codes"] = ["selected_model_vram_fraction_unknown"]
        return result
    if fraction < MIN_VRAM_FRACTION:
        result.update(
            status="degraded",
            reason_codes=["selected_model_mostly_cpu_offloaded"],
        )
        return result
    if status == "success" and elapsed_ms is not None and elapsed_ms <= float(budget_seconds) * 1000.0:
        result.update(status="healthy", reason_codes=["recent_vote_success_under_budget"])
        return result
    result["reason_codes"] = ["recent_vote_not_successful"]
    return result


def _utc_text(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def collect_health_snapshot(
    *,
    diagnostics_path: str | Path = DIAGNOSTICS_PATH,
    now_epoch: float | None = None,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
    fetch_ollama_fn: Callable[[], Mapping[str, Any]] = fetch_ollama_ps,
    read_gpu_memory_fn: Callable[[], Mapping[str, Any]] = read_nvidia_memory,
) -> dict[str, Any]:
    from typed_contract_decision import semantic_vote_timeout_seconds

    observed_epoch = time.time() if now_epoch is None else float(now_epoch)
    budget_seconds = float(semantic_vote_timeout_seconds())
    ollama = dict(fetch_ollama_fn())
    loaded_models = list(ollama.get("loaded_models") or [])
    gpu_memory = dict(read_gpu_memory_fn())
    votes = read_vote_evidence(diagnostics_path)
    assessment = evaluate_health(
        ollama_reachable=bool(ollama.get("reachable")),
        loaded_models=loaded_models,
        vote_evidence=votes,
        gpu_memory=gpu_memory,
        now_epoch=observed_epoch,
        budget_seconds=budget_seconds,
        freshness_seconds=freshness_seconds,
    )
    return {
        "schema_version": "gpu_model_health.v1",
        "generated_at": _utc_text(observed_epoch),
        "status": assessment["status"],
        "reason_codes": assessment["reason_codes"],
        "budget_seconds": budget_seconds,
        "freshness_seconds": freshness_seconds,
        "ollama": {
            "endpoint": OLLAMA_PS_URL,
            "reachable": bool(ollama.get("reachable")),
            "loaded_models": loaded_models,
            **(
                {"exception_type": ollama["exception_type"]}
                if isinstance(ollama.get("exception_type"), str) else {}
            ),
        },
        "gpu_memory": gpu_memory,
        "selected_model": assessment.get("selected_model"),
        "evidence_age_seconds": assessment.get("evidence_age_seconds"),
        "latest_vote": assessment.get("latest_vote"),
        "vote_evidence": votes,
        "authority": {
            "observation_only": True,
            "model_invocation_allowed": False,
            "service_or_process_mutation_allowed": False,
            "external_notification_allowed": False,
        },
    }


def _operator_markdown(snapshot: Mapping[str, Any]) -> str:
    selected = snapshot.get("selected_model")
    selected_text = "none"
    if isinstance(selected, Mapping):
        selected_text = str(selected.get("model") or "unknown")
        if selected.get("loaded") is False:
            selected_text += " (not loaded)"
        elif isinstance(selected.get("vram_fraction"), (int, float)):
            selected_text += f" ({float(selected['vram_fraction']):.1%} in VRAM)"
    gpu = snapshot.get("gpu_memory") if isinstance(snapshot.get("gpu_memory"), Mapping) else {}
    latest = snapshot.get("latest_vote") if isinstance(snapshot.get("latest_vote"), Mapping) else {}
    reasons = snapshot.get("reason_codes") if isinstance(snapshot.get("reason_codes"), list) else []
    lines = [
        "# GPU Model Health",
        "",
        f"- Status: `{snapshot.get('status', 'unknown')}`",
        f"- Observed: `{snapshot.get('generated_at', 'unknown')}`",
        f"- Reason codes: `{', '.join(str(item) for item in reasons) or 'none'}`",
        f"- Semantic-vote budget: `{snapshot.get('budget_seconds', 'unknown')}s`",
        f"- Selected model: `{selected_text}`",
        f"- Ollama reachable: `{str(bool((snapshot.get('ollama') or {}).get('reachable'))).lower()}`",
        f"- GPU memory used/free: `{gpu.get('used_mib', 'unknown')} / {gpu.get('free_mib', 'unknown')} MiB`",
        "",
        "Latest bounded vote evidence:",
    ]
    for key in VOTE_FIELDS:
        if key in latest:
            lines.append(f"- `{key}`: `{latest[key]}`")
    lines.extend([
        "",
        "Boundary:",
        "- This report observes local health and writes read-model files only.",
        "- It does not invoke a model, change runtime state, or send a notification.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text.replace("\r\n", "\n").replace("\r", "\n"))
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_read_models(
    snapshot: Mapping[str, Any],
    *,
    output_dir: str | Path = READ_MODEL_DIR,
) -> dict[str, Path]:
    output = Path(output_dir)
    json_path = output / "gpu_model_health.json"
    operator_path = output / "gpu_model_health_OPERATOR.md"
    json_text = json.dumps(dict(snapshot), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    _atomic_write_text(json_path, json_text)
    _atomic_write_text(operator_path, _operator_markdown(snapshot))
    return {"json": json_path, "operator": operator_path}


def run_once() -> dict[str, Any]:
    snapshot = collect_health_snapshot()
    write_read_models(snapshot)
    return snapshot


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run one observation pass")
    parser.parse_args(argv)
    snapshot = run_once()
    print(json.dumps({
        "status": snapshot["status"],
        "reason_codes": snapshot["reason_codes"],
        "generated_at": snapshot["generated_at"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
