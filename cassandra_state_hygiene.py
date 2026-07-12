"""Schema-aware prevention and quarantine for Cassandra prompt-fed state."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import tempfile
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from control_language_policy import (
    ControlLanguageClassification,
    classify_control_language,
)


STATE_HYGIENE_SCHEMA_VERSION = "cassandra_state_hygiene_v1"
_FUTURE_PROMPT_LIST_SUFFIXES = (
    "_prompt_items",
    "_context_items",
    "_cues",
    "_concerns",
    "_instructions",
)
_OVERRIDE_TEXT_FIELDS = frozenset(
    {"summary", "value", "at", "provenance", "source_surface", "source_text"}
)
_MISSING = object()


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_text(value: Any) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _state_hash(value: Any) -> str:
    stable = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(stable).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class StateHygieneFinding:
    field_path: str
    leaf_sha256: str
    reason_codes: tuple[str, ...]
    action: str


@dataclass(frozen=True, slots=True)
class StateSanitizationReceipt:
    stage: str
    changed: bool
    source_state_sha256: str
    sanitized_state_sha256: str
    quarantined_count: int
    counts_by_reason: Mapping[str, int]
    findings: tuple[StateHygieneFinding, ...]
    authority: Mapping[str, bool]
    raw_values_included: bool = False
    schema_version: str = STATE_HYGIENE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StateSanitizationResult:
    state: dict[str, Any]
    changed: bool
    receipt: StateSanitizationReceipt


@dataclass(slots=True)
class StateFileResult:
    state: dict[str, Any]
    receipt: StateSanitizationReceipt
    backup_path: Path | None = None
    receipt_path: Path | None = None
    backup_reused: bool = False


Classifier = Callable[[str], ControlLanguageClassification]


@dataclass(frozen=True, slots=True)
class _BackupArtifact:
    role: str
    path: Path
    reused: bool


def _safe_dynamic_key(value: Any) -> str:
    return "<key#" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:10] + ">"


def _safe_stage(value: Any) -> str:
    normalized = " ".join(str(value or "unknown").split())[:32] or "unknown"
    if normalized in {"assembly", "load", "save"}:
        return normalized
    return "<stage#" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10] + ">"


def _is_future_prompt_list_field(value: Any) -> bool:
    return str(value or "").endswith(_FUTURE_PROMPT_LIST_SUFFIXES)


def sanitize_cassandra_state(
    state: Mapping[str, Any] | None,
    *,
    stage: str,
    classifier: Classifier = classify_control_language,
) -> StateSanitizationResult:
    """Deep-copy and quarantine only registered prompt-bearing leaves."""

    source: dict[str, Any] = copy.deepcopy(dict(state or {}))
    clean: dict[str, Any] = copy.deepcopy(source)
    findings: list[StateHygieneFinding] = []

    def unsafe(value: Any, path: str, action: str) -> bool:
        if not isinstance(value, str):
            return False
        try:
            classification = classifier(value)
            if not isinstance(classification, ControlLanguageClassification):
                raise TypeError("invalid classifier result")
            if not classification.is_control_language:
                return False
            reason_codes = classification.reason_codes
        except Exception:
            reason_codes = ("classifier_unavailable",)
        findings.append(
            StateHygieneFinding(
                field_path=path,
                leaf_sha256=_hash_text(value),
                reason_codes=tuple(reason_codes),
                action=action,
            )
        )
        return True

    def schema_reset(root: str, default: Any) -> None:
        findings.append(
            StateHygieneFinding(
                field_path=root,
                leaf_sha256=_hash_text(type(clean.get(root)).__name__),
                reason_codes=("schema_type_mismatch",),
                action="reset_root_default",
            )
        )
        clean[root] = copy.deepcopy(default)

    cues = clean.get("human_cues", _MISSING)
    if cues is not _MISSING and not isinstance(cues, list):
        schema_reset("human_cues", [])
    elif isinstance(cues, list):
        safe_cues: list[dict[str, Any]] = []
        for index, item in enumerate(cues):
            if not isinstance(item, Mapping) or not isinstance(item.get("cue"), str):
                findings.append(
                    StateHygieneFinding(
                        field_path=f"human_cues[{index}]",
                        leaf_sha256=_hash_text(type(item).__name__),
                        reason_codes=("schema_type_mismatch",),
                        action="drop_list_item",
                    )
                )
                continue
            if unsafe(item["cue"], f"human_cues[{index}].cue", "drop_list_item"):
                continue
            safe_cues.append(copy.deepcopy(dict(item)))
        clean["human_cues"] = safe_cues

    mood = clean.get("project_mood", "neutral")
    if not isinstance(mood, str):
        schema_reset("project_mood", "neutral")
    elif unsafe(mood, "project_mood", "reset_default"):
        clean["project_mood"] = "neutral"

    concerns = clean.get("recurring_concerns", _MISSING)
    if concerns is not _MISSING and not isinstance(concerns, list):
        schema_reset("recurring_concerns", [])
    elif isinstance(concerns, list):
        safe_concerns: list[str] = []
        for index, item in enumerate(concerns):
            if not isinstance(item, str):
                findings.append(
                    StateHygieneFinding(
                        field_path=f"recurring_concerns[{index}]",
                        leaf_sha256=_hash_text(type(item).__name__),
                        reason_codes=("schema_type_mismatch",),
                        action="drop_list_item",
                    )
                )
                continue
            if not unsafe(item, f"recurring_concerns[{index}]", "drop_list_item"):
                safe_concerns.append(item)
        clean["recurring_concerns"] = safe_concerns

    overrides = clean.get("session_fact_overrides", _MISSING)
    if overrides is not _MISSING and not isinstance(overrides, Mapping):
        schema_reset("session_fact_overrides", {})
    elif isinstance(overrides, Mapping):
        safe_overrides: dict[str, Any] = {}
        for key, item in overrides.items():
            key_path = f"session_fact_overrides.{_safe_dynamic_key(key)}"
            if unsafe(str(key), key_path, "drop_mapping_entry"):
                continue
            if not isinstance(item, Mapping):
                findings.append(
                    StateHygieneFinding(
                        field_path=key_path,
                        leaf_sha256=_hash_text(type(item).__name__),
                        reason_codes=("schema_type_mismatch",),
                        action="drop_mapping_entry",
                    )
                )
                continue
            safe_item = copy.deepcopy(dict(item))
            for field_name in _OVERRIDE_TEXT_FIELDS:
                value = safe_item.get(field_name, _MISSING)
                if value is _MISSING:
                    continue
                path = f"{key_path}.{field_name}"
                if not isinstance(value, str):
                    findings.append(
                        StateHygieneFinding(
                            field_path=path,
                            leaf_sha256=_hash_text(type(value).__name__),
                            reason_codes=("schema_type_mismatch",),
                            action="drop_leaf",
                        )
                    )
                    safe_item.pop(field_name, None)
                elif unsafe(value, path, "drop_leaf"):
                    safe_item.pop(field_name, None)
            if str(safe_item.get("summary") or safe_item.get("value") or "").strip():
                safe_overrides[str(key)] = safe_item
        clean["session_fact_overrides"] = safe_overrides

    def sanitize_prompt_value(value: Any, path: str) -> Any:
        """Sanitize all leaves once a registered prompt-list boundary is crossed."""

        if isinstance(value, str):
            return _MISSING if unsafe(value, path, "drop_leaf") else value
        if isinstance(value, list):
            output: list[Any] = []
            for index, item in enumerate(value):
                sanitized = sanitize_prompt_value(item, f"{path}[{index}]")
                if sanitized is not _MISSING and sanitized not in ({}, []):
                    output.append(sanitized)
            return output
        if isinstance(value, Mapping):
            output_dict: dict[str, Any] = {}
            for key, item in value.items():
                key_label = _safe_dynamic_key(key)
                if unsafe(str(key), f"{path}.{key_label}", "drop_mapping_entry"):
                    continue
                child_path = f"{path}.{key_label}"
                if _is_future_prompt_list_field(key) and not isinstance(item, list):
                    findings.append(
                        StateHygieneFinding(
                            field_path=child_path,
                            leaf_sha256=_hash_text(type(item).__name__),
                            reason_codes=("schema_type_mismatch",),
                            action="reset_list_default",
                        )
                    )
                    sanitized = []
                else:
                    sanitized = sanitize_prompt_value(item, child_path)
                if sanitized is not _MISSING:
                    output_dict[str(key)] = sanitized
            return output_dict
        return copy.deepcopy(value)

    def sanitize_future_prompt_fields(value: Any, path: str) -> Any:
        """Find registered future list fields without scrubbing unrelated state."""

        if isinstance(value, list):
            return [
                sanitize_future_prompt_fields(item, f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        if not isinstance(value, Mapping):
            return copy.deepcopy(value)
        output: dict[str, Any] = {}
        for key, item in value.items():
            key_path = f"{path}.{_safe_dynamic_key(key)}"
            if _is_future_prompt_list_field(key):
                if unsafe(str(key), key_path, "drop_mapping_entry"):
                    continue
                if not isinstance(item, list):
                    findings.append(
                        StateHygieneFinding(
                            field_path=key_path,
                            leaf_sha256=_hash_text(type(item).__name__),
                            reason_codes=("schema_type_mismatch",),
                            action="reset_list_default",
                        )
                    )
                    output[str(key)] = []
                else:
                    output[str(key)] = sanitize_prompt_value(item, key_path)
            else:
                output[str(key)] = sanitize_future_prompt_fields(item, key_path)
        return output

    for root, value in list(clean.items()):
        if root in {
            "human_cues",
            "project_mood",
            "recurring_concerns",
            "session_fact_overrides",
        }:
            continue
        root_path = f"state.{_safe_dynamic_key(root)}"
        if _is_future_prompt_list_field(root):
            if unsafe(str(root), root_path, "drop_mapping_entry"):
                clean.pop(root, None)
                continue
            if not isinstance(value, list):
                findings.append(
                    StateHygieneFinding(
                        field_path=root_path,
                        leaf_sha256=_hash_text(type(value).__name__),
                        reason_codes=("schema_type_mismatch",),
                        action="reset_list_default",
                    )
                )
                clean[root] = []
            else:
                clean[root] = sanitize_prompt_value(value, root_path)
        elif root == "mood" and isinstance(value, str):
            if unsafe(value, "mood", "reset_default"):
                clean[root] = "neutral"
        elif root == "overrides" and isinstance(value, Mapping):
            clean[root] = sanitize_prompt_value(value, "overrides")
        else:
            clean[root] = sanitize_future_prompt_fields(value, root_path)

    source_hash = _state_hash(source)
    sanitized_hash = _state_hash(clean)
    counts = Counter(
        reason for finding in findings for reason in finding.reason_codes
    )
    receipt = StateSanitizationReceipt(
        stage=_safe_stage(stage),
        changed=source_hash != sanitized_hash,
        source_state_sha256=source_hash,
        sanitized_state_sha256=sanitized_hash,
        quarantined_count=len(findings),
        counts_by_reason=dict(sorted(counts.items())),
        findings=tuple(findings),
        authority={
            "external_action": False,
            "business_action": False,
            "approval": False,
        },
    )
    return StateSanitizationResult(clean, receipt.changed, receipt)


def sanitize_state_for_prompt(state: Mapping[str, Any] | None) -> StateSanitizationResult:
    return sanitize_cassandra_state(state, stage="assembly")


def _quarantine_root(path: Path) -> Path:
    return path.parent / ".cassandra_state_quarantine"


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _atomic_write(path: Path, payload: bytes) -> None:
    # The canonical state parent is operator-owned.  Only quarantine
    # directories are made private by their callers.
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _state_lock(path: Path):
    lock_path = path.with_name(f".{path.name}.hygiene.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _backup_bytes(path: Path, payload: bytes) -> tuple[Path, bool]:
    quarantine_root = _quarantine_root(path)
    _ensure_private_directory(quarantine_root)
    backup_dir = quarantine_root / "backups"
    _ensure_private_directory(backup_dir)
    digest = _hash_bytes(payload)
    backup_path = backup_dir / f"{digest}.json"
    if backup_path.exists():
        if _hash_bytes(backup_path.read_bytes()) != digest:
            raise RuntimeError("state hygiene backup hash mismatch")
        return backup_path, True
    _atomic_write(backup_path, payload)
    return backup_path, False


def _receipt_backup_payload(path: Path, artifact: _BackupArtifact) -> dict[str, Any]:
    return {
        "role": artifact.role,
        "created": not artifact.reused,
        "reused": artifact.reused,
        "sha256": "sha256:" + artifact.path.stem,
        "ref": str(artifact.path.relative_to(path.parent)),
    }


def _prepare_receipt(
    path: Path,
    receipt: StateSanitizationReceipt,
    *,
    artifacts: list[_BackupArtifact],
) -> tuple[Path, dict[str, Any]]:
    if not artifacts:
        raise ValueError("state hygiene receipt requires a quarantine artifact")
    quarantine_root = _quarantine_root(path)
    _ensure_private_directory(quarantine_root)
    receipt_dir = quarantine_root / "receipts"
    _ensure_private_directory(receipt_dir)
    material = (
        f"{receipt.stage}|{receipt.source_state_sha256}|{receipt.sanitized_state_sha256}|"
        f"{time.time_ns()}"
    )
    receipt_id = "state-hygiene-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    backups = [_receipt_backup_payload(path, artifact) for artifact in artifacts]
    payload: dict[str, Any] = {
        **receipt.to_dict(),
        "receipt_id": receipt_id,
        "status": "prepared",
        "prepared_at": _utc_now(),
        "committed_at": None,
        # Keep the singular field for older receipt readers while carrying
        # every independently quarantined input in the plural field.
        "backup": backups[0],
        "backups": backups,
    }
    receipt_path = receipt_dir / f"{receipt_id}.json"
    _atomic_write(receipt_path, _json_bytes(payload))
    return receipt_path, payload


def _commit_receipt(receipt_path: Path, prepared_payload: Mapping[str, Any]) -> None:
    committed_payload = copy.deepcopy(dict(prepared_payload))
    committed_payload["status"] = "committed"
    committed_payload["committed_at"] = _utc_now()
    # Atomic replacement means a failure here leaves the durable prepared
    # receipt behind to identify an ambiguous post-replace transaction.
    _atomic_write(receipt_path, _json_bytes(committed_payload))


def _sanitize_serialized_state(
    original: bytes,
    *,
    stage: str,
    default_factory: Callable[[], Mapping[str, Any]],
) -> StateSanitizationResult:
    invalid_reason: str | None = None
    try:
        parsed = json.loads(original.decode("utf-8"))
    except Exception:
        parsed = copy.deepcopy(dict(default_factory()))
        invalid_reason = "invalid_json"
    if not isinstance(parsed, Mapping):
        parsed = copy.deepcopy(dict(default_factory()))
        invalid_reason = "schema_type_mismatch"
    result = sanitize_cassandra_state(parsed, stage=stage)
    if invalid_reason is None:
        return result
    invalid_finding = StateHygieneFinding(
        field_path="<state-file>",
        leaf_sha256="sha256:" + _hash_bytes(original),
        reason_codes=(invalid_reason,),
        action="replace_with_default",
    )
    counts = dict(result.receipt.counts_by_reason)
    counts[invalid_reason] = counts.get(invalid_reason, 0) + 1
    result.receipt = replace(
        result.receipt,
        changed=True,
        source_state_sha256="sha256:" + _hash_bytes(original),
        quarantined_count=result.receipt.quarantined_count + 1,
        counts_by_reason=dict(sorted(counts.items())),
        findings=(invalid_finding, *result.receipt.findings),
    )
    result.changed = True
    return result


def _combine_save_receipts(
    candidate: StateSanitizationReceipt,
    existing: StateSanitizationReceipt | None,
) -> StateSanitizationReceipt:
    sources: list[tuple[str, StateSanitizationReceipt]] = []
    if existing is not None and existing.changed:
        sources.append(("canonical_existing", existing))
    if candidate.changed:
        sources.append(("candidate", candidate))
    if not sources:
        return candidate
    findings = tuple(
        replace(finding, field_path=f"{role}.{finding.field_path}")
        for role, receipt in sources
        for finding in receipt.findings
    )
    counts = Counter(
        reason
        for _role, receipt in sources
        for finding in receipt.findings
        for reason in finding.reason_codes
    )
    return StateSanitizationReceipt(
        stage="save",
        changed=True,
        source_state_sha256=candidate.source_state_sha256,
        sanitized_state_sha256=candidate.sanitized_state_sha256,
        quarantined_count=len(findings),
        counts_by_reason=dict(sorted(counts.items())),
        findings=findings,
        authority={
            "external_action": False,
            "business_action": False,
            "approval": False,
        },
    )


def load_sanitized_cassandra_state(
    path: str | Path,
    *,
    default_factory: Callable[[], Mapping[str, Any]],
) -> StateFileResult:
    target = Path(path)
    with _state_lock(target):
        if not target.is_file():
            clean_default = copy.deepcopy(dict(default_factory()))
            result = sanitize_cassandra_state(clean_default, stage="load")
            return StateFileResult(result.state, result.receipt)
        original = target.read_bytes()
        result = _sanitize_serialized_state(
            original,
            stage="load",
            default_factory=default_factory,
        )
        if not result.changed:
            return StateFileResult(result.state, result.receipt)
        backup_path, reused = _backup_bytes(target, original)
        artifact = _BackupArtifact("canonical_load", backup_path, reused)
        receipt_path, prepared_payload = _prepare_receipt(
            target,
            result.receipt,
            artifacts=[artifact],
        )
        _atomic_write(target, _json_bytes(result.state))
        _commit_receipt(receipt_path, prepared_payload)
        return StateFileResult(
            result.state,
            result.receipt,
            backup_path,
            receipt_path,
            reused,
        )


def save_sanitized_cassandra_state(
    path: str | Path,
    state: Mapping[str, Any],
) -> StateFileResult:
    target = Path(path)
    with _state_lock(target):
        raw_candidate = _json_bytes(copy.deepcopy(dict(state)))
        candidate_result = sanitize_cassandra_state(state, stage="save")
        existing_result: StateSanitizationResult | None = None
        existing_bytes: bytes | None = None
        if target.is_file():
            existing_bytes = target.read_bytes()
            existing_result = _sanitize_serialized_state(
                existing_bytes,
                stage="save",
                default_factory=dict,
            )

        artifacts: list[_BackupArtifact] = []
        if (
            existing_bytes is not None
            and existing_result is not None
            and existing_result.changed
        ):
            backup_path, reused = _backup_bytes(target, existing_bytes)
            artifacts.append(
                _BackupArtifact("canonical_before_save", backup_path, reused)
            )
        if candidate_result.changed:
            backup_path, reused = _backup_bytes(target, raw_candidate)
            artifacts.append(_BackupArtifact("candidate", backup_path, reused))

        receipt = _combine_save_receipts(
            candidate_result.receipt,
            existing_result.receipt if existing_result is not None else None,
        )
        receipt_path: Path | None = None
        prepared_payload: dict[str, Any] | None = None
        if artifacts:
            receipt_path, prepared_payload = _prepare_receipt(
                target,
                receipt,
                artifacts=artifacts,
            )
        _atomic_write(target, _json_bytes(candidate_result.state))
        if receipt_path is not None and prepared_payload is not None:
            _commit_receipt(receipt_path, prepared_payload)
        primary = artifacts[0] if artifacts else None
        return StateFileResult(
            candidate_result.state,
            receipt,
            primary.path if primary is not None else None,
            receipt_path,
            primary.reused if primary is not None else False,
        )


def sanitize_cassandra_state_file(
    path: str | Path,
    *,
    default_factory: Callable[[], Mapping[str, Any]],
) -> StateFileResult:
    """Explicit deploy/ops entry point; never invoked automatically by this module."""

    return load_sanitized_cassandra_state(path, default_factory=default_factory)


__all__ = [
    "STATE_HYGIENE_SCHEMA_VERSION",
    "StateFileResult",
    "StateHygieneFinding",
    "StateSanitizationReceipt",
    "StateSanitizationResult",
    "load_sanitized_cassandra_state",
    "sanitize_cassandra_state",
    "sanitize_cassandra_state_file",
    "sanitize_state_for_prompt",
    "save_sanitized_cassandra_state",
]
