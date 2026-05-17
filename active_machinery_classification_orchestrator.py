"""Active machinery classification shard orchestrator v0.

Builds metadata-first inclusion records, safe header-only shard packets, and a
mock aggregation read-model for later external worker classification. The
orchestrator does not call models, execute discovered scripts, write SQLite,
walk private roots, or grant runtime authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from generated_read_model_files import iter_safe_generated_read_models
from openclaw_sensitive_policy import normalize_repo_path, path_policy_findings


ROOT = Path(__file__).resolve().parent
REPO_B_ROOT = Path("/home/openclaw_external/openclaw-runtime")

SCHEMA_VERSION = "active_machinery_classification_orchestrator_v0"
DRY_RUN_SCHEMA_VERSION = "active_machinery_privacy_inclusion_dry_run_v0"
SHARD_SCHEMA_VERSION = "active_machinery_classification_shard_v0"
WORKER_OUTPUT_SCHEMA_VERSION = "active_machinery_mock_worker_output_v0"

DEFAULT_OUTPUT_ROOT = Path("generated/audit_shards/active_machinery_v0")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_WORKER_PROMPT_PATH = Path("docs/operations/ACTIVE_MACHINERY_CLASSIFICATION_WORKER_PROMPT_V0.md")
DEFAULT_HEADER_LINE_LIMIT = 80
DEFAULT_SAFE_HEADER_MAX_BYTES = 200_000
DEFAULT_SHARD_SIZE = 25

SAFE_TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

SENSITIVE_PARTS = {
    ".chief.env",
    ".env",
    ".google-secrets",
    ".gnupg",
    ".private",
    ".ssh",
    "appdata",
    "bank",
    "client",
    "clients",
    "cpa",
    "finance",
    "legal",
    "private",
    "runtime_logs",
    "secrets",
    "spreadsheets",
    "tax",
    "telegram_logs",
    "vault",
    "vaults",
}

SENSITIVE_NAME_HINTS = (
    "approval_pending.json",
    "credential",
    "credentials",
    "secret",
    "token",
    ".env",
    "telegram",
    "bank",
    "spreadsheet",
)

SAFE_HIDDEN_HEADER_FILES = {
    ".gitignore",
}

SAFE_GITIGNORE_GLOB_PREFIXES = (
    "docs/operations/",
    "generated/read_models/",
    "scripts/",
    "tests/",
)

SOURCE_INVENTORY_PATH = Path("generated/read_models/source_inventory.json")

MACHINERY_TYPES = (
    "daemon_listener",
    "scheduler_watchdog",
    "sync_bridge",
    "importer_exporter",
    "approval_hitl",
    "send_external_api",
    "mcp_tool_plugin_surface",
    "state_mutator",
    "generated_read_model_artifact",
    "canonical_doctrine_docs",
    "legacy_reference_only",
    "unknown_operator_review",
)

MACHINERY_HEADINGS = {
    "daemon_listener": "daemon/listener",
    "scheduler_watchdog": "scheduler/watchdog",
    "sync_bridge": "sync bridge",
    "importer_exporter": "importer/exporter",
    "approval_hitl": "approval/HITL",
    "send_external_api": "send/external API",
    "mcp_tool_plugin_surface": "MCP/tool/plugin surface",
    "state_mutator": "state mutator",
    "generated_read_model_artifact": "generated/read-model artifact",
    "canonical_doctrine_docs": "canonical doctrine/docs",
    "legacy_reference_only": "legacy reference-only",
    "unknown_operator_review": "unknown/operator review",
}


@dataclass(frozen=True)
class CandidateSeed:
    repo_root: Path
    repo_role: str
    relative_path: str
    source_role: str
    source_category: str
    why_included: str
    source_basis: str
    blocked_reason: str = ""


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted_path(path: str | Path, *, root: Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return root / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _safe_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _repo_relative(path: Path, *, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _path_has_sensitive_hint(relative_path: str) -> bool:
    lowered = relative_path.lower()
    path_parts = Path(relative_path).parts
    parts = {part.lower() for part in path_parts}
    if path_parts and path_parts[0].startswith(".") and relative_path not in SAFE_HIDDEN_HEADER_FILES:
        return True
    if parts & SENSITIVE_PARTS:
        return True
    return any(hint in lowered for hint in SENSITIVE_NAME_HINTS)


def _source_role_for_path(relative_path: str, source_role: str = "") -> str:
    if source_role:
        return source_role
    if relative_path.startswith("generated/read_models/"):
        return "generated_read_model"
    if relative_path.startswith("docs/operations/"):
        return "docs"
    if relative_path.startswith("scripts/"):
        return "script"
    if relative_path.startswith("tests/"):
        return "test"
    if relative_path.endswith(".py"):
        return "source_code"
    return "unknown"


def _source_category_for_path(relative_path: str, source_category: str = "") -> str:
    if source_category:
        return source_category
    role = _source_role_for_path(relative_path)
    if role == "generated_read_model":
        return "generated_artifact"
    if role == "docs":
        return "canonical_doctrine_or_operations_doc"
    return role


def _seed_from_source_inventory(repo_root: Path) -> list[CandidateSeed]:
    payload = _load_json_if_present(repo_root / SOURCE_INVENTORY_PATH)
    if not payload:
        return []
    seeds: list[CandidateSeed] = []
    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue
        raw_path = str(record.get("path") or "").strip()
        if not raw_path:
            continue
        seeds.append(
            CandidateSeed(
                repo_root=repo_root,
                repo_role="canonical_repo_a",
                relative_path=raw_path,
                source_role=str(record.get("source_class") or "source_inventory_record"),
                source_category=str(record.get("source_class") or "source_inventory_record"),
                why_included=str(
                    record.get("reason_included")
                    or "Existing generated source inventory metadata record."
                ),
                source_basis="generated/read_models/source_inventory.json",
                blocked_reason=str(record.get("blocked_reason") or ""),
            )
        )
    return seeds


def _seed_from_generated_read_models(repo_root: Path) -> list[CandidateSeed]:
    read_model_root = repo_root / "generated/read_models"
    if not read_model_root.is_dir():
        return []
    return [
        CandidateSeed(
            repo_root=repo_root,
            repo_role="canonical_repo_a",
            relative_path=f"generated/read_models/{path.name}",
            source_role="generated_read_model",
            source_category="generated_artifact",
            why_included="Safe top-level generated read-model file selected by generated_read_model_files policy.",
            source_basis="generated_read_model_files.iter_safe_generated_read_models",
        )
        for path in iter_safe_generated_read_models(read_model_root, repo_root=repo_root)
    ]


def _safe_gitignore_glob_allowed(pattern: str) -> bool:
    if "**" in pattern:
        return False
    if pattern.startswith("polish_loop/tasks/"):
        return False
    if pattern.count("*") > 1:
        return False
    return any(pattern.startswith(prefix) for prefix in SAFE_GITIGNORE_GLOB_PREFIXES)


def _seed_from_gitignore_allowlist(repo_root: Path) -> list[CandidateSeed]:
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.is_file():
        return []

    seeds: list[CandidateSeed] = []
    for raw_line in gitignore_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("!") or line.startswith("!!"):
            continue
        pattern = line[1:].lstrip("/")
        if not pattern or pattern.endswith("/"):
            continue
        if pattern.startswith(".claude/") or pattern.startswith(".codex/"):
            continue
        if pattern.startswith("polish_loop/tasks/"):
            seeds.append(
                CandidateSeed(
                    repo_root=repo_root,
                    repo_role="canonical_repo_a",
                    relative_path=pattern,
                    source_role="polish_loop_task_pattern",
                    source_category="operator_review",
                    why_included="Existing .gitignore allowlist pattern; metadata classification only.",
                    source_basis=".gitignore allowlist",
                    blocked_reason="polish_loop/tasks is metadata-only in this lane",
                )
            )
            continue
        if "*" in pattern:
            if not _safe_gitignore_glob_allowed(pattern):
                continue
            parent = repo_root / Path(pattern).parent
            if not parent.is_dir():
                continue
            for path in sorted(parent.glob(Path(pattern).name), key=lambda item: item.as_posix()):
                if path.is_file() or path.is_symlink():
                    relative_path = path.relative_to(repo_root).as_posix()
                    seeds.append(
                        CandidateSeed(
                            repo_root=repo_root,
                            repo_role="canonical_repo_a",
                            relative_path=relative_path,
                            source_role=_source_role_for_path(relative_path),
                            source_category=_source_category_for_path(relative_path),
                            why_included="Existing .gitignore allowlist glob under safe selected prefix.",
                            source_basis=".gitignore allowlist",
                        )
                    )
            continue
        path = repo_root / pattern
        if path.exists() and (path.is_file() or path.is_symlink()):
            seeds.append(
                CandidateSeed(
                    repo_root=repo_root,
                    repo_role="canonical_repo_a",
                    relative_path=pattern,
                    source_role=_source_role_for_path(pattern),
                    source_category=_source_category_for_path(pattern),
                    why_included="Existing .gitignore explicit allowlist file.",
                    source_basis=".gitignore allowlist",
                )
            )
    return seeds


def _repo_b_reference_seed() -> CandidateSeed:
    return CandidateSeed(
        repo_root=REPO_B_ROOT,
        repo_role="pre_split_capability_tree_reference_only",
        relative_path=".",
        source_role="legacy_reference_root",
        source_category="reference_only",
        why_included="Repo B is modeled as pre-split capability tree metadata only.",
        source_basis="operator_repo_model",
        blocked_reason="Repo B runtime/code execution is forbidden; do not read headers in this orchestrator.",
    )


def collect_candidate_seeds(
    *,
    repo_root: str | Path = ROOT,
    include_gitignore_allowlist: bool = True,
    include_repo_b_reference: bool = True,
    extra_seeds: Iterable[CandidateSeed] = (),
) -> list[CandidateSeed]:
    root = Path(repo_root)
    seeds: list[CandidateSeed] = []
    seeds.extend(_seed_from_source_inventory(root))
    seeds.extend(_seed_from_generated_read_models(root))
    if include_gitignore_allowlist:
        seeds.extend(_seed_from_gitignore_allowlist(root))
    if include_repo_b_reference:
        seeds.append(_repo_b_reference_seed())
    seeds.extend(extra_seeds)

    deduped: dict[tuple[str, str], CandidateSeed] = {}
    for seed in seeds:
        key = (seed.repo_root.as_posix(), seed.relative_path)
        if key in deduped:
            existing = deduped[key]
            deduped[key] = CandidateSeed(
                repo_root=existing.repo_root,
                repo_role=existing.repo_role,
                relative_path=existing.relative_path,
                source_role=existing.source_role or seed.source_role,
                source_category=existing.source_category or seed.source_category,
                why_included=f"{existing.why_included}; {seed.why_included}",
                source_basis=f"{existing.source_basis}; {seed.source_basis}",
                blocked_reason=existing.blocked_reason or seed.blocked_reason,
            )
        else:
            deduped[key] = seed
    return sorted(deduped.values(), key=lambda item: (item.repo_role, item.relative_path))


def classify_candidate(
    seed: CandidateSeed,
    *,
    header_line_limit: int = DEFAULT_HEADER_LINE_LIMIT,
    safe_header_max_bytes: int = DEFAULT_SAFE_HEADER_MAX_BYTES,
) -> dict[str, Any]:
    repo_root = seed.repo_root
    repo_role = seed.repo_role
    extension = Path(seed.relative_path.rstrip("*")).suffix
    source_role = _source_role_for_path(seed.relative_path, seed.source_role)
    source_category = _source_category_for_path(seed.relative_path, seed.source_category)
    base = {
        "repo_root": repo_root.as_posix(),
        "repo_role": repo_role,
        "relative_path": seed.relative_path,
        "extension": extension,
        "source_role": source_role,
        "source_category": source_category,
        "sensitivity_privacy_status": "unknown",
        "eligibility": "operator_review",
        "body_read_allowed": False,
        "header_read_allowed": False,
        "header_lines_allowed": 0,
        "size_bytes": None,
        "exists": False,
        "is_symlink": False,
        "why_included": seed.why_included,
        "why_blocked": seed.blocked_reason,
        "source_basis": seed.source_basis,
    }

    if repo_role != "canonical_repo_a":
        return {
            **base,
            "sensitivity_privacy_status": "reference_only",
            "eligibility": "reference_only",
            "why_blocked": seed.blocked_reason or "non-canonical repo is reference-only",
        }

    normalized, inside_repo = normalize_repo_path(seed.relative_path, repo_root)
    if not inside_repo or normalized.startswith(".."):
        return {
            **base,
            "relative_path": normalized,
            "sensitivity_privacy_status": "blocked_no_go",
            "eligibility": "blocked_no_go",
            "why_blocked": "path escapes repo root",
        }

    findings = path_policy_findings([normalized], root=repo_root)
    if findings or _path_has_sensitive_hint(normalized):
        matched = ", ".join(f"{item.finding}:{item.matched}" for item in findings)
        return {
            **base,
            "relative_path": normalized,
            "sensitivity_privacy_status": "blocked_no_go",
            "eligibility": "blocked_no_go",
            "why_blocked": seed.blocked_reason or matched or "sensitive path hint",
        }

    if normalized.startswith("polish_loop/tasks/") or "*" in normalized:
        return {
            **base,
            "relative_path": normalized,
            "sensitivity_privacy_status": "metadata_only",
            "eligibility": "operator_review",
            "why_blocked": seed.blocked_reason or "metadata-only path pattern; no header read",
        }

    path = repo_root / normalized
    exists = path.exists() or path.is_symlink()
    is_symlink = path.is_symlink()
    if is_symlink:
        resolved = path.resolve()
        if _repo_relative(resolved, root=repo_root) is None:
            return {
                **base,
                "relative_path": normalized,
                "exists": exists,
                "is_symlink": True,
                "sensitivity_privacy_status": "blocked_no_go",
                "eligibility": "blocked_no_go",
                "why_blocked": "symlink resolves outside repo root",
            }
        return {
            **base,
            "relative_path": normalized,
            "exists": exists,
            "is_symlink": True,
            "sensitivity_privacy_status": "operator_review",
            "eligibility": "operator_review",
            "why_blocked": "symlink requires operator review before header read",
        }

    if not exists or not path.is_file():
        return {
            **base,
            "relative_path": normalized,
            "exists": exists,
            "sensitivity_privacy_status": "metadata_only",
            "eligibility": "metadata_only",
            "why_blocked": seed.blocked_reason or "path missing or not a file",
        }

    size_bytes = path.stat().st_size
    generated = normalized.startswith("generated/read_models/")
    if generated:
        eligibility = "generated_artifact"
        privacy = "generated_artifact"
    else:
        eligibility = "header_read_allowed"
        privacy = "repo_allowlisted_metadata"

    if extension.lower() not in SAFE_TEXT_SUFFIXES:
        return {
            **base,
            "relative_path": normalized,
            "exists": True,
            "size_bytes": size_bytes,
            "sensitivity_privacy_status": "metadata_only",
            "eligibility": "metadata_only",
            "why_blocked": "extension is not in safe text/header allowlist",
        }
    if size_bytes > safe_header_max_bytes:
        return {
            **base,
            "relative_path": normalized,
            "exists": True,
            "size_bytes": size_bytes,
            "sensitivity_privacy_status": "operator_review",
            "eligibility": "operator_review",
            "why_blocked": f"file larger than safe header threshold ({safe_header_max_bytes} bytes)",
        }

    return {
        **base,
        "relative_path": normalized,
        "exists": True,
        "size_bytes": size_bytes,
        "sensitivity_privacy_status": privacy,
        "eligibility": eligibility,
        "header_read_allowed": True,
        "header_lines_allowed": header_line_limit,
        "why_blocked": "",
    }


def build_privacy_inclusion_dry_run(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
    header_line_limit: int = DEFAULT_HEADER_LINE_LIMIT,
    safe_header_max_bytes: int = DEFAULT_SAFE_HEADER_MAX_BYTES,
    include_gitignore_allowlist: bool = True,
    include_repo_b_reference: bool = True,
    extra_seeds: Iterable[CandidateSeed] = (),
) -> dict[str, Any]:
    candidates = [
        classify_candidate(
            seed,
            header_line_limit=header_line_limit,
            safe_header_max_bytes=safe_header_max_bytes,
        )
        for seed in collect_candidate_seeds(
            repo_root=repo_root,
            include_gitignore_allowlist=include_gitignore_allowlist,
            include_repo_b_reference=include_repo_b_reference,
            extra_seeds=extra_seeds,
        )
    ]
    by_eligibility = Counter(candidate["eligibility"] for candidate in candidates)
    by_repo_role = Counter(candidate["repo_role"] for candidate in candidates)
    return {
        "schema_version": DRY_RUN_SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "mode": "privacy_inclusion_dry_run_metadata_first",
        "repo_model": {
            "repo_a_canonical": True,
            "repo_b_model": "pre_split_capability_tree_reference_only",
            "sqlite_coverage_complete": False,
        },
        "boundaries": {
            "llm_calls_made": False,
            "api_calls_made": False,
            "repo_b_executed": False,
            "raw_private_content_read": False,
            "body_read_allowed_default": False,
            "sqlite_written": False,
            "runtime_authority_changed": False,
            "files_moved_deleted_or_reorganized": False,
        },
        "header_policy": {
            "default_header_lines_allowed": header_line_limit,
            "safe_header_max_bytes": safe_header_max_bytes,
            "body_read_allowed": False,
        },
        "candidate_count": len(candidates),
        "header_read_allowed_count": sum(1 for item in candidates if item["header_read_allowed"]),
        "blocked_no_go_count": by_eligibility.get("blocked_no_go", 0),
        "operator_review_count": by_eligibility.get("operator_review", 0),
        "by_eligibility": dict(sorted(by_eligibility.items())),
        "by_repo_role": dict(sorted(by_repo_role.items())),
        "candidates": candidates,
    }


def _read_header_excerpt(path: Path, *, line_limit: int) -> tuple[str, int]:
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for _ in range(line_limit):
            line = handle.readline()
            if line == "":
                break
            lines.append(line.rstrip("\n"))
    return "\n".join(lines), len(lines)


def build_shards_from_dry_run(
    dry_run: dict[str, Any],
    *,
    shard_size: int = DEFAULT_SHARD_SIZE,
    header_line_limit: int = DEFAULT_HEADER_LINE_LIMIT,
) -> tuple[dict[str, Any], ...]:
    items = []
    for candidate in dry_run["candidates"]:
        if candidate.get("header_read_allowed") is not True:
            continue
        repo_root = Path(candidate["repo_root"])
        path = repo_root / candidate["relative_path"]
        excerpt, lines_read = _read_header_excerpt(path, line_limit=header_line_limit)
        items.append(
            {
                "repo_root": candidate["repo_root"],
                "repo_role": candidate["repo_role"],
                "relative_path": candidate["relative_path"],
                "extension": candidate["extension"],
                "source_role": candidate["source_role"],
                "source_category": candidate["source_category"],
                "content_header_excerpt": excerpt,
                "header_lines_read": lines_read,
                "body_read_allowed": False,
                "why_included": candidate["why_included"],
                "no_execution": True,
                "runtime_authority": False,
            }
        )

    shards: list[dict[str, Any]] = []
    for index in range(0, len(items), shard_size):
        shard_number = len(shards) + 1
        chunk = items[index : index + shard_size]
        shards.append(
            {
                "schema_version": SHARD_SCHEMA_VERSION,
                "shard_id": f"active_machinery_v0_shard_{shard_number:04d}",
                "shard_index": shard_number,
                "item_count": len(chunk),
                "header_line_limit": header_line_limit,
                "body_read_allowed": False,
                "no_execution": True,
                "llm_calls_made": False,
                "items": chunk,
            }
        )
    return tuple(shards)


def write_privacy_dry_run_and_shards(
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
    header_line_limit: int = DEFAULT_HEADER_LINE_LIMIT,
    safe_header_max_bytes: int = DEFAULT_SAFE_HEADER_MAX_BYTES,
    shard_size: int = DEFAULT_SHARD_SIZE,
) -> dict[str, Any]:
    output = _rooted_path(output_root)
    shard_root = output / "shards"
    dry_run = build_privacy_inclusion_dry_run(
        repo_root=repo_root,
        generated_at=generated_at,
        header_line_limit=header_line_limit,
        safe_header_max_bytes=safe_header_max_bytes,
    )
    shards = build_shards_from_dry_run(
        dry_run,
        shard_size=shard_size,
        header_line_limit=header_line_limit,
    )
    dry_run_path = output / "privacy_inclusion_dry_run.json"
    _safe_write_json(dry_run_path, dry_run)
    shard_paths = []
    for shard in shards:
        shard_path = shard_root / f"{shard['shard_id']}.json"
        _safe_write_json(shard_path, shard)
        shard_paths.append(_display_path(shard_path))
    manifest = {
        "schema_version": "active_machinery_shard_manifest_v0",
        "generated_at": generated_at or dry_run["generated_at"],
        "dry_run_path": _display_path(dry_run_path),
        "shard_count": len(shards),
        "candidate_count": dry_run["candidate_count"],
        "header_read_allowed_count": dry_run["header_read_allowed_count"],
        "shards": shard_paths,
        "boundaries": dry_run["boundaries"],
        "no_execution": True,
    }
    manifest_path = output / "shard_manifest.json"
    _safe_write_json(manifest_path, manifest)
    return {
        "dry_run": dry_run,
        "shards": shards,
        "manifest": manifest,
        "dry_run_path": _display_path(dry_run_path),
        "manifest_path": _display_path(manifest_path),
        "shard_paths": shard_paths,
    }


def _mock_worker_classification(item: dict[str, Any]) -> dict[str, Any]:
    relative_path = item["relative_path"]
    source_category = item.get("source_category") or ""
    if item.get("repo_role") != "canonical_repo_a":
        machinery_type = "legacy_reference_only"
        source_fate = "keep_reference_only"
        evidence = "Repo role is non-canonical reference-only."
        confidence = 0.3
    elif relative_path.startswith("generated/read_models/") or source_category == "generated_artifact":
        machinery_type = "generated_read_model_artifact"
        source_fate = "generated_artifact"
        evidence = "Path is a generated read-model artifact; worker must verify posture."
        confidence = 0.25
    elif relative_path.startswith("docs/operations/"):
        machinery_type = "canonical_doctrine_docs"
        source_fate = "keep_canonical_docs"
        evidence = "Path is an operations doctrine/spec document; worker must verify content."
        confidence = 0.2
    else:
        machinery_type = "unknown_operator_review"
        source_fate = "needs_worker_classification"
        evidence = "Mock placeholder; Gemini worker has not classified this item."
        confidence = 0.0

    return {
        "repo_root": item["repo_root"],
        "repo_role": item["repo_role"],
        "relative_path": relative_path,
        "is_active_machinery": None,
        "machinery_type": machinery_type,
        "source_fate": source_fate,
        "reads": "unknown_pending_worker_review",
        "writes": "unknown_pending_worker_review",
        "executes": "unknown_pending_worker_review",
        "sends_external": "unknown_pending_worker_review",
        "touches_private_data": "unknown_pending_worker_review",
        "authority_risk": "unknown_pending_worker_review",
        "recommended_fate": "worker_review_required",
        "confidence": confidence,
        "one_sentence_evidence": evidence,
        "mock_output": True,
        "no_execution": True,
    }


def write_mock_worker_outputs(
    shards: Iterable[dict[str, Any]],
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    generated_at: str | None = None,
) -> list[str]:
    worker_root = _rooted_path(output_root) / "mock_worker_outputs"
    paths: list[str] = []
    now = generated_at or utc_now()
    for shard in shards:
        payload = {
            "schema_version": WORKER_OUTPUT_SCHEMA_VERSION,
            "generated_at": now,
            "worker_model": "mock_no_llm_path_hint",
            "shard_id": shard["shard_id"],
            "mock_output": True,
            "llm_calls_made": False,
            "raw_private_content_read": False,
            "repo_b_executed": False,
            "items": [_mock_worker_classification(item) for item in shard["items"]],
        }
        path = worker_root / f"{shard['shard_id']}_mock_worker_output.json"
        _safe_write_json(path, payload)
        paths.append(_display_path(path))
    return paths


def _load_worker_outputs(worker_output_root: str | Path) -> list[dict[str, Any]]:
    root = _rooted_path(worker_output_root)
    if not root.is_dir():
        return []
    outputs: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json"), key=lambda item: item.name):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["_source_path"] = _display_path(path)
            outputs.append(payload)
    return outputs


def build_active_machinery_aggregation(
    *,
    dry_run: dict[str, Any],
    manifest: dict[str, Any],
    worker_outputs: Iterable[dict[str, Any]],
    generated_at: str | None = None,
    worker_prompt_path: str | Path = DEFAULT_WORKER_PROMPT_PATH,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in MACHINERY_TYPES}
    output_paths: list[str] = []
    worker_item_count = 0
    for output in worker_outputs:
        if output.get("_source_path"):
            output_paths.append(str(output["_source_path"]))
        for item in output.get("items", []):
            if not isinstance(item, dict):
                continue
            worker_item_count += 1
            machinery_type = str(item.get("machinery_type") or "unknown_operator_review")
            if machinery_type not in groups:
                machinery_type = "unknown_operator_review"
            groups[machinery_type].append(item)

    for candidate in dry_run.get("candidates", []):
        if candidate.get("eligibility") != "reference_only":
            continue
        groups["legacy_reference_only"].append(
            {
                "repo_root": candidate["repo_root"],
                "repo_role": candidate["repo_role"],
                "relative_path": candidate["relative_path"],
                "is_active_machinery": None,
                "machinery_type": "legacy_reference_only",
                "source_fate": "reference_only",
                "reads": "metadata_only",
                "writes": "none",
                "executes": "none",
                "sends_external": "none",
                "touches_private_data": "unknown_not_read",
                "authority_risk": "high_if_executed",
                "recommended_fate": "keep_reference_only",
                "confidence": 0.3,
                "one_sentence_evidence": "Repo role is pre-split reference-only and was not header-read.",
                "mock_output": True,
                "no_execution": True,
            }
        )

    group_payload = {
        key: {
            "display_name": MACHINERY_HEADINGS[key],
            "count": len(items),
            "items": items[:50],
        }
        for key, items in groups.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "mode": "mock_aggregator_for_future_gemini_workers",
        "classification_claims_final": False,
        "requires_gemini_worker_review": True,
        "llm_calls_made": False,
        "api_calls_made": False,
        "raw_private_content_read": False,
        "repo_b_executed": False,
        "runtime_authority_changed": False,
        "sqlite_written": False,
        "files_moved_deleted_or_reorganized": False,
        "dry_run_path": manifest["dry_run_path"],
        "shard_manifest_path": manifest.get("manifest_path", "generated/audit_shards/active_machinery_v0/shard_manifest.json"),
        "worker_prompt_path": _display_path(worker_prompt_path),
        "worker_outputs_consumed": output_paths,
        "worker_output_count": len(output_paths),
        "worker_item_count": worker_item_count,
        "candidate_counts": {
            "candidate_count": dry_run["candidate_count"],
            "header_read_allowed_count": dry_run["header_read_allowed_count"],
            "blocked_no_go_count": dry_run["blocked_no_go_count"],
            "operator_review_count": dry_run["operator_review_count"],
            "by_eligibility": dry_run["by_eligibility"],
        },
        "shards_generated": manifest["shard_count"],
        "shards_ready_for_gemini": manifest["shard_count"] > 0,
        "group_counts": {key: value["count"] for key, value in group_payload.items()},
        "groups": group_payload,
        "next_prompt_target": "Gemini 3.1 Pro",
        "next_safe_move": "Send shard packets and worker prompt to Gemini 3.1 Pro for JSON-only classification.",
        "boundaries": dry_run["boundaries"],
    }


def format_active_machinery_operator_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Active Machinery Classification Orchestrator v0",
        "",
        "Status:",
        f"- Shards ready for Gemini: `{str(payload['shards_ready_for_gemini']).lower()}`.",
        f"- LLM calls made: `{str(payload['llm_calls_made']).lower()}`.",
        f"- Raw private content read: `{str(payload['raw_private_content_read']).lower()}`.",
        f"- Repo B executed: `{str(payload['repo_b_executed']).lower()}`.",
        f"- Classification claims final: `{str(payload['classification_claims_final']).lower()}`.",
        "",
        "## Counts",
        f"- Candidates: `{payload['candidate_counts']['candidate_count']}`.",
        f"- Header-readable shard items: `{payload['candidate_counts']['header_read_allowed_count']}`.",
        f"- Blocked/no-go candidates: `{payload['candidate_counts']['blocked_no_go_count']}`.",
        f"- Shards generated: `{payload['shards_generated']}`.",
        "",
        "## Groups",
    ]
    for machinery_type in MACHINERY_TYPES:
        group = payload["groups"][machinery_type]
        lines.append(f"### {group['display_name']}")
        lines.append(f"- Count: `{group['count']}`")
        if not group["items"]:
            lines.append("- No mocked worker rows yet.")
        else:
            for item in group["items"][:10]:
                lines.append(
                    f"- `{item['relative_path']}` -> {item['recommended_fate']} "
                    f"({item['one_sentence_evidence']})"
                )
        lines.append("")

    lines.extend(
        [
            "## Worker Prompt",
            f"- `{payload['worker_prompt_path']}`",
            "",
            "## Next Safe Move",
            f"- {payload['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def worker_prompt_text() -> str:
    return """# Active Machinery Classification Worker Prompt v0

You are classifying OpenClaw shard packets for active machinery and source fate.

Rules:
- Return JSON only. Do not include Markdown outside the JSON object.
- Use only the provided shard JSON. Do not browse, fetch, open files, run code, call tools, or infer from private data.
- Do not execute scripts, commands, shells, daemons, listeners, tests, imports, notebooks, apps, or package managers.
- Do not request or include secrets, env values, raw Telegram logs, raw private/client data, bank data, spreadsheet cells, credential paths, or no-go root contents.
- Treat `body_read_allowed=false` as absolute. Header excerpts are the only content you may use.
- Repo B rows are reference-only and must not be classified as current runtime authority.
- If evidence is insufficient, use `unknown_operator_review` and low confidence.

Input:
- One `active_machinery_classification_shard_v0` JSON packet.

Output JSON schema:
{
  "schema_version": "active_machinery_worker_output_v0",
  "worker_model": "Gemini 3.1 Pro",
  "shard_id": "<copy from input>",
  "llm_or_worker_calls_made": true,
  "raw_private_content_read": false,
  "repo_b_executed": false,
  "items": [
    {
      "repo_root": "<copy>",
      "repo_role": "<copy>",
      "relative_path": "<copy>",
      "is_active_machinery": true,
      "machinery_type": "daemon_listener | scheduler_watchdog | sync_bridge | importer_exporter | approval_hitl | send_external_api | mcp_tool_plugin_surface | state_mutator | generated_read_model_artifact | canonical_doctrine_docs | legacy_reference_only | unknown_operator_review",
      "source_fate": "already_governed | keep_canonical | compatibility_only | replace | retire_later | block_no_go | reference_only | generated_artifact | operator_review",
      "reads": "none | metadata | headers | sqlite | json_state | generated_read_model | unknown",
      "writes": "none | sqlite | json_state | generated_artifact | external | unknown",
      "executes": "none | imports_only | script_entrypoint | daemon_loop | shell | unknown",
      "sends_external": "none | telegram | gmail | smtp | portal | network_api | unknown",
      "touches_private_data": "no | possible | yes | unknown",
      "authority_risk": "low | medium | high | critical | unknown",
      "recommended_fate": "keep | wrap | shadow | block | port_logic | retire | operator_review",
      "confidence": 0.0,
      "one_sentence_evidence": "One concise sentence grounded in the header/path only."
    }
  ]
}
"""


def write_worker_prompt(path: str | Path = DEFAULT_WORKER_PROMPT_PATH) -> str:
    prompt_path = _rooted_path(path)
    _safe_write_text(prompt_path, worker_prompt_text())
    return _display_path(prompt_path)


def run_all(
    *,
    repo_root: str | Path = ROOT,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    worker_prompt_path: str | Path = DEFAULT_WORKER_PROMPT_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    shard_result = write_privacy_dry_run_and_shards(
        output_root=output_root,
        repo_root=repo_root,
        generated_at=generated,
    )
    worker_paths = write_mock_worker_outputs(
        shard_result["shards"],
        output_root=output_root,
        generated_at=generated,
    )
    prompt_path = write_worker_prompt(worker_prompt_path)
    worker_outputs = _load_worker_outputs(_rooted_path(output_root) / "mock_worker_outputs")
    manifest = {**shard_result["manifest"], "manifest_path": shard_result["manifest_path"]}
    aggregate = build_active_machinery_aggregation(
        dry_run=shard_result["dry_run"],
        manifest=manifest,
        worker_outputs=worker_outputs,
        generated_at=generated,
        worker_prompt_path=worker_prompt_path,
    )
    read_model_output = _rooted_path(read_model_root)
    json_path = read_model_output / "active_machinery_classification_orchestrator.json"
    operator_path = read_model_output / "active_machinery_classification_orchestrator_OPERATOR.md"
    _safe_write_json(json_path, aggregate)
    _safe_write_text(operator_path, format_active_machinery_operator_packet(aggregate))
    return {
        "schema_version": SCHEMA_VERSION,
        "dry_run_path": shard_result["dry_run_path"],
        "shard_manifest_path": shard_result["manifest_path"],
        "worker_output_paths": worker_paths,
        "worker_prompt_path": prompt_path,
        "read_model_json_path": _display_path(json_path),
        "read_model_operator_path": _display_path(operator_path),
        "candidate_count": shard_result["dry_run"]["candidate_count"],
        "blocked_no_go_count": shard_result["dry_run"]["blocked_no_go_count"],
        "shards_generated": shard_result["manifest"]["shard_count"],
        "shards_ready_for_gemini": aggregate["shards_ready_for_gemini"],
        "llm_calls_made": False,
        "raw_private_content_read": False,
        "repo_b_executed": False,
        "next_prompt_target": aggregate["next_prompt_target"],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build active machinery classification shards.")
    parser.add_argument(
        "--mode",
        choices=("dry-run", "shards", "mock-aggregate", "all"),
        default="all",
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    parser.add_argument("--read-model-root", default=DEFAULT_READ_MODEL_ROOT.as_posix())
    parser.add_argument("--format", choices=("json", "operator"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.mode == "dry-run":
        payload = build_privacy_inclusion_dry_run(repo_root=args.repo_root)
    elif args.mode == "shards":
        payload = write_privacy_dry_run_and_shards(
            output_root=args.output_root,
            repo_root=args.repo_root,
        )["manifest"]
    else:
        payload = run_all(
            repo_root=args.repo_root,
            output_root=args.output_root,
            read_model_root=args.read_model_root,
        )

    if args.format == "operator" and args.mode in {"mock-aggregate", "all"}:
        read_model = _load_json_if_present(
            _rooted_path(args.read_model_root) / "active_machinery_classification_orchestrator.json"
        )
        if read_model:
            print(format_active_machinery_operator_packet(read_model), end="")
        else:
            print(stable_json(payload), end="")
    else:
        print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
