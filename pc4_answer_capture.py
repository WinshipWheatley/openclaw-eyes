#!/usr/bin/env python3
"""Read finished OpenClaw answers from the scoped Mission Control response bus."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from polish_loop.answer_auditor import AuditFinding


DEFAULT_RESPONSE_DIR = Path(
    os.environ.get("OPENCLAW_RESPONSE_BRIDGE_ROOT", "/mnt/e/openclaw/mission_control_responses/to_mac")
)
RESPONSE_MANIFEST = "response_manifest.json"


@dataclass(frozen=True)
class CapturedAnswer:
    source_request_id: str
    response_kind: str
    one_line_answer: str
    agent_id: str
    proof_refs: tuple[str, ...]
    machine_proof: dict[str, Any]
    response_file: str
    source_request_filename: str = ""
    request_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof_refs"] = list(self.proof_refs)
        return payload


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        return tuple(str(item) for item in value if str(item))
    return ()


def _manifest_response_files(response_dir: Path) -> list[Path]:
    manifest = _load_json(response_dir / RESPONSE_MANIFEST)
    paths: list[Path] = []
    for row in manifest.get("responses") or []:
        if not isinstance(row, Mapping):
            continue
        ref = str(row.get("response_file") or "").strip()
        if ref:
            paths.append(Path(ref))
    return paths


def iter_response_files(response_dir: str | Path = DEFAULT_RESPONSE_DIR) -> list[Path]:
    root = Path(response_dir)
    files = _manifest_response_files(root)
    files.extend(sorted(root.glob("openclaw_response_for_mac_*.json")))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in files:
        if path.name in {RESPONSE_MANIFEST, "openclaw_response_for_mac_latest.json"}:
            continue
        resolved = str(path if path.is_absolute() else root / path)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(Path(resolved))
    return unique


def capture_answer_file(path: str | Path) -> CapturedAnswer | None:
    response_path = Path(path)
    payload = _load_json(response_path)
    if not payload:
        return None
    detail = payload.get("detail_disclosure") if isinstance(payload.get("detail_disclosure"), Mapping) else {}
    layered = detail.get("layered_response_fields") if isinstance(detail.get("layered_response_fields"), Mapping) else {}
    operator_display = detail.get("operator_display") if isinstance(detail.get("operator_display"), Mapping) else {}
    proof_refs = (
        _as_strings(payload.get("proof_refs"))
        or _as_strings(layered.get("proof_refs"))
        or _as_strings(detail.get("proof_refs"))
    )
    machine_proof = payload.get("machine_proof")
    if not isinstance(machine_proof, Mapping):
        machine_proof = detail.get("machine_proof") if isinstance(detail.get("machine_proof"), Mapping) else {}
    one_line = str(
        payload.get("one_line_answer")
        or layered.get("one_line_answer")
        or payload.get("operator_headline")
        or payload.get("headline")
        or ""
    )
    return CapturedAnswer(
        source_request_id=str(payload.get("source_request_id") or ""),
        response_kind=str(payload.get("response_kind") or payload.get("request_type") or payload.get("internal_status") or ""),
        one_line_answer=one_line,
        agent_id=str(operator_display.get("speaker_ref") or payload.get("agent_id") or "unknown"),
        proof_refs=proof_refs,
        machine_proof=dict(machine_proof),
        response_file=response_path.as_posix(),
        source_request_filename=str(payload.get("source_request_filename") or ""),
        request_text=str(payload.get("operator_text") or detail.get("operator_text") or ""),
    )


def capture_finished_answers(response_dir: str | Path = DEFAULT_RESPONSE_DIR) -> list[CapturedAnswer]:
    answers: list[CapturedAnswer] = []
    for path in iter_response_files(response_dir):
        answer = capture_answer_file(path)
        if answer is not None and answer.source_request_id:
            answers.append(answer)
    return answers


def detect_probe_timeout(
    *,
    agent_id: str,
    request_text: str,
    response_dir: str | Path = DEFAULT_RESPONSE_DIR,
    before_files: Iterable[str | Path] = (),
    timeout_seconds: int = 0,
) -> AuditFinding | None:
    """Return a hard fail finding when a probe produced no new bus response."""

    root = Path(response_dir)
    before = {Path(path).name for path in before_files}
    current = iter_response_files(root)
    new_files = [path for path in current if path.name not in before]
    if new_files:
        return None
    return AuditFinding(
        verdict="fail",
        agent_id=agent_id,
        claim_type="probe_response_timeout",
        claimed_value="response_expected",
        actual_value="no_response",
        truth_source=root.as_posix(),
        proof_refs=(root.as_posix(),),
        delta={
            "reason": "probe_timeout_zero_bus_activity",
            "request_text": request_text,
            "timeout_seconds": timeout_seconds,
            "response_count": 0,
        },
    )
