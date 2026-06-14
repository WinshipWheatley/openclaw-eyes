"""Read-only external registry materializer for OpenClaw.

This module imports generated registry artifacts from canonical external repos
into a local cache for deterministic read-model/wiki consumption. It does not
make /home/openclaw the canonical owner of those registries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openclaw_reference_resolver import (
    OPENCLAW_EYES_MAIN_BRANCH,
    OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF,
    build_openclaw_reference_resolver,
    git_branch_ref_by_repo_ref,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXTERNAL_REGISTRY_ROOT = Path("generated/external_registries")
DEFAULT_EXTERNAL_SOURCE_ROOT = Path("generated/external_sources")

INDEX_JSON_NAME = "external_system_knowledge_registry_index.json"
OPERATOR_INDEX_NAME = "external_system_knowledge_registry_index_OPERATOR.md"
SCHEMA_VERSION = "external_system_knowledge_registry_materializer_v0"
READ_MODEL_VERSION = "external_system_knowledge_registry_index_v0"

OPENCLAW_EYES_REMOTE_URL = "git@github.com:WinshipWheatley/openclaw-eyes.git"
OPENCLAW_EYES_READONLY_REMOTE_URL = "https://github.com/WinshipWheatley/openclaw-eyes.git"
CANONICAL_OWNER = "openclaw-eyes"
LOCAL_ROLE = "READ_ONLY_EXTERNAL_INPUT"

EXPECTED_ARTIFACTS = (
    (
        "json",
        "generated/read_models/openclaw_system_knowledge_registry.json",
        "openclaw_system_knowledge_registry.json",
    ),
    (
        "operator",
        "generated/read_models/openclaw_system_knowledge_registry_OPERATOR.md",
        "openclaw_system_knowledge_registry_OPERATOR.md",
    ),
    (
        "sqlite",
        "generated/system_knowledge/openclaw_system_knowledge_registry.sqlite",
        "openclaw_system_knowledge_registry.sqlite",
    ),
    (
        "schema",
        "generated/system_knowledge/openclaw_system_knowledge_registry_SCHEMA.sql",
        "openclaw_system_knowledge_registry_SCHEMA.sql",
    ),
    (
        "seed",
        "generated/system_knowledge/openclaw_system_knowledge_registry_SEED.sql",
        "openclaw_system_knowledge_registry_SEED.sql",
    ),
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "read_model_only": True,
    "read_only_external_registry_import": True,
    "canonical_owner_changed": False,
    "services_started": False,
    "services_modified": False,
    "lm_called": False,
    "email_accessed": False,
    "gmail_accessed": False,
    "browser_accessed": False,
    "coupa_accessed": False,
    "workbook_cells_read": False,
    "pdf_generated_or_exported": False,
    "ledger_mutated": False,
    "production_state_mutated": False,
    "git_push_performed": False,
}


@dataclass(frozen=True)
class ExternalRegistryMaterializerResult:
    schema_version: str
    index_json_path: str
    operator_path: str
    import_status: str
    source_repo: str
    source_branch: str
    source_commit: str
    artifact_count: int
    missing_artifact_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def display_path(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sqlite_integrity(path: Path) -> str:
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return f"ERROR: {exc}"
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    except sqlite3.Error as exc:
        return f"ERROR: {exc}"
    finally:
        connection.close()


def json_parse_status(path: Path) -> str:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"ERROR: {exc}"
    return "ok"


def read_json_object(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _git(
    args: list[str],
    *,
    cwd: str | Path | None = None,
    timeout_seconds: int = 60,
) -> tuple[int, str, str]:
    if not args or args[0] not in {"clone", "fetch", "checkout", "rev-parse"}:
        raise ValueError("external registry materializer only allows bounded read-only git cache commands")
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _resolved_main_branch(reference_resolver_payload: dict[str, Any]) -> dict[str, Any]:
    return git_branch_ref_by_repo_ref(reference_resolver_payload, OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF)


def _checkout_head(path: Path) -> str:
    code, stdout, _stderr = _git(["rev-parse", "HEAD"], cwd=path, timeout_seconds=12)
    return stdout if code == 0 else ""


def _is_git_checkout(path: Path) -> bool:
    return (path / ".git").exists()


def _ensure_cached_checkout(
    *,
    cache_path: Path,
    remote_url: str,
    branch: str,
    commit: str,
    allow_network: bool,
) -> tuple[Path | None, str]:
    if not allow_network:
        return None, "external source checkout missing and network cache update disabled"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if _is_git_checkout(cache_path):
        code, _stdout, stderr = _git(["fetch", "--depth", "1", "origin", branch], cwd=cache_path)
        if code != 0:
            return None, f"git fetch failed: {stderr}"
    else:
        if cache_path.exists() and any(cache_path.iterdir()):
            return None, f"cache path exists but is not a git checkout: {cache_path}"
        code, _stdout, stderr = _git(
            ["clone", "--no-checkout", "--filter=blob:none", "--depth", "1", "--branch", branch, remote_url, str(cache_path)]
        )
        if code != 0 and remote_url != OPENCLAW_EYES_READONLY_REMOTE_URL:
            code, _stdout, stderr = _git(
                [
                    "clone",
                    "--no-checkout",
                    "--filter=blob:none",
                    "--depth",
                    "1",
                    "--branch",
                    branch,
                    OPENCLAW_EYES_READONLY_REMOTE_URL,
                    str(cache_path),
                ]
            )
        if code != 0:
            return None, f"git clone failed: {stderr}"
    code, _stdout, stderr = _git(["checkout", "--detach", commit], cwd=cache_path)
    if code != 0:
        return None, f"git checkout failed for {commit}: {stderr}"
    head = _checkout_head(cache_path)
    if head != commit:
        return None, f"cache checkout commit mismatch: expected {commit}, found {head}"
    return cache_path, ""


def _source_checkout_for_commit(
    *,
    source_checkout: str | Path | None,
    cache_path: Path,
    remote_url: str,
    branch: str,
    commit: str,
    allow_network: bool,
) -> tuple[Path | None, str]:
    if source_checkout:
        checkout = rooted(source_checkout)
        if _is_git_checkout(checkout):
            head = _checkout_head(checkout)
            if head == commit:
                return checkout, ""
            return None, f"source checkout commit mismatch: expected {commit}, found {head}"
        return None, f"source checkout is not a git checkout: {checkout}"
    return _ensure_cached_checkout(
        cache_path=cache_path,
        remote_url=remote_url,
        branch=branch,
        commit=commit,
        allow_network=allow_network,
    )


def _artifact_record(
    *,
    artifact_type: str,
    source_path: Path,
    cache_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    record = {
        "artifact_type": artifact_type,
        "source_path": display_path(source_path, repo_root=repo_root),
        "cache_path": display_path(cache_path, repo_root=repo_root),
        "sha256": sha256_file(cache_path),
        "byte_count": cache_path.stat().st_size,
    }
    if artifact_type == "sqlite":
        record["sqlite_integrity_check"] = sqlite_integrity(cache_path)
    if artifact_type == "json":
        record["json_parse_status"] = json_parse_status(cache_path)
    return record


def _build_failure_index(
    *,
    imported_at: str,
    source_repo: str,
    source_branch: str,
    source_commit: str,
    resolver_status: str,
    import_status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "imported_at": imported_at,
        "import_status": import_status,
        "reason": reason,
        "source_repo": source_repo,
        "source_branch": source_branch,
        "source_commit": source_commit,
        "resolver_target_ref": OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF,
        "resolver_status": resolver_status,
        "resolver_commit": source_commit,
        "commit_match": False,
        "canonical_owner": CANONICAL_OWNER,
        "local_role": LOCAL_ROLE,
        "artifact_count": 0,
        "artifacts": [],
        "missing_artifacts": [],
        "boundary_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def _write_index(index: dict[str, Any], *, read_model_root: str | Path, repo_root: str | Path) -> None:
    read_root = rooted(read_model_root, repo_root=repo_root)
    read_root.mkdir(parents=True, exist_ok=True)
    (read_root / INDEX_JSON_NAME).write_text(stable_json(index), encoding="utf-8")
    (read_root / OPERATOR_INDEX_NAME).write_text(format_operator_index(index), encoding="utf-8")


def build_external_system_knowledge_registry_index(
    *,
    repo: str = "openclaw-eyes",
    repo_root: str | Path = ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    external_registry_root: str | Path = DEFAULT_EXTERNAL_REGISTRY_ROOT,
    external_source_root: str | Path = DEFAULT_EXTERNAL_SOURCE_ROOT,
    source_checkout: str | Path | None = None,
    reference_resolver_payload: dict[str, Any] | None = None,
    generated_at: str | None = None,
    allow_network: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    if repo != "openclaw-eyes":
        raise ValueError("v0 materializer only supports --repo openclaw-eyes")
    root = Path(repo_root)
    imported_at = generated_at or utc_now()
    resolver_payload = reference_resolver_payload or build_openclaw_reference_resolver(
        generated_at=imported_at
    )
    main_ref = _resolved_main_branch(resolver_payload)
    source_branch = main_ref.get("branch") or OPENCLAW_EYES_MAIN_BRANCH
    source_commit = str(main_ref.get("current_head_commit") or "")
    resolver_status = str(main_ref.get("resolution_status") or "UNREACHABLE")
    remote_url = str(main_ref.get("remote_url") or OPENCLAW_EYES_REMOTE_URL)
    if resolver_status not in {"RESOLVED_LOCAL", "RESOLVED_REMOTE", "RESOLVED_MAC_BRIDGE"} or not source_commit:
        index = _build_failure_index(
            imported_at=imported_at,
            source_repo=repo,
            source_branch=source_branch,
            source_commit=source_commit,
            resolver_status=resolver_status,
            import_status="UNAVAILABLE",
            reason=f"reference resolver did not resolve {OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF}",
        )
        if write:
            _write_index(index, read_model_root=read_model_root, repo_root=root)
        return index

    registry_dir = rooted(external_registry_root, repo_root=root) / repo
    source_root = rooted(external_source_root, repo_root=root) / repo
    checkout, checkout_error = _source_checkout_for_commit(
        source_checkout=source_checkout,
        cache_path=source_root,
        remote_url=remote_url,
        branch=source_branch,
        commit=source_commit,
        allow_network=allow_network,
    )
    if checkout is None:
        index = _build_failure_index(
            imported_at=imported_at,
            source_repo=repo,
            source_branch=source_branch,
            source_commit=source_commit,
            resolver_status=resolver_status,
            import_status="UNAVAILABLE",
            reason=checkout_error,
        )
        if write:
            _write_index(index, read_model_root=read_model_root, repo_root=root)
        return index

    registry_dir.mkdir(parents=True, exist_ok=True)
    artifact_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for artifact_type, source_rel, output_name in EXPECTED_ARTIFACTS:
        source_path = checkout / source_rel
        cache_path = registry_dir / output_name
        if not source_path.is_file():
            missing_rows.append(
                {
                    "artifact_type": artifact_type,
                    "source_path": source_rel,
                    "reason": "expected generated registry artifact missing from source checkout",
                }
            )
            continue
        shutil.copy2(source_path, cache_path)
        artifact_rows.append(
            _artifact_record(
                artifact_type=artifact_type,
                source_path=source_path,
                cache_path=cache_path,
                repo_root=root,
            )
        )

    import_status = "IMPORTED" if not missing_rows else "MISSING_ARTIFACTS"
    index = {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "imported_at": imported_at,
        "import_status": import_status,
        "reason": "" if import_status == "IMPORTED" else "one or more expected registry artifacts were missing",
        "source_repo": repo,
        "source_remote_url": remote_url,
        "source_branch": source_branch,
        "source_commit": source_commit,
        "source_checkout_path": display_path(checkout, repo_root=root),
        "resolver_target_ref": OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF,
        "resolver_status": resolver_status,
        "resolver_commit": source_commit,
        "commit_match": _checkout_head(checkout) == source_commit,
        "canonical_owner": CANONICAL_OWNER,
        "local_role": LOCAL_ROLE,
        "artifact_count": len(artifact_rows),
        "artifacts": artifact_rows,
        "missing_artifacts": missing_rows,
        "cache_root": display_path(registry_dir, repo_root=root),
        "boundary_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    if write:
        _write_index(index, read_model_root=read_model_root, repo_root=root)
    return index


def format_operator_index(index: dict[str, Any]) -> str:
    lines = [
        "# External System Knowledge Registry Index",
        "",
        f"Imported at: {index.get('imported_at')}",
        f"Status: {index.get('import_status')}",
        "",
        "Source:",
        f"- Repo: {index.get('source_repo')}",
        f"- Branch: {index.get('source_branch')}",
        f"- Commit: {index.get('source_commit')}",
        f"- Canonical owner: {index.get('canonical_owner')}",
        f"- Local role: {index.get('local_role')}",
        "",
        "Imported Artifacts:",
    ]
    artifacts = index.get("artifacts", [])
    if artifacts:
        lines.extend(
            f"- {artifact.get('cache_path')} ({artifact.get('sha256')})"
            for artifact in artifacts
        )
    else:
        lines.append("- none")
    missing = index.get("missing_artifacts", [])
    if missing:
        lines.extend(["", "Missing Artifacts:"])
        lines.extend(f"- {item.get('source_path')}: {item.get('reason')}" for item in missing)
    if index.get("reason"):
        lines.extend(["", f"Reason: {index.get('reason')}"])
    lines.extend(
        [
            "",
            "Boundary:",
            "- Read-only external registry input cache only.",
            "- /home/openclaw is not the canonical owner of the imported registry.",
            "- No service, LM, email, browser, Coupa, workbook, PDF, ledger, production, or push action is performed.",
            "",
        ]
    )
    return "\n".join(lines)


def export_external_system_knowledge_registry(
    *,
    repo: str = "openclaw-eyes",
    repo_root: str | Path = ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    external_registry_root: str | Path = DEFAULT_EXTERNAL_REGISTRY_ROOT,
    external_source_root: str | Path = DEFAULT_EXTERNAL_SOURCE_ROOT,
    source_checkout: str | Path | None = None,
    reference_resolver_payload: dict[str, Any] | None = None,
    generated_at: str | None = None,
    allow_network: bool = True,
) -> ExternalRegistryMaterializerResult:
    index = build_external_system_knowledge_registry_index(
        repo=repo,
        repo_root=repo_root,
        read_model_root=read_model_root,
        external_registry_root=external_registry_root,
        external_source_root=external_source_root,
        source_checkout=source_checkout,
        reference_resolver_payload=reference_resolver_payload,
        generated_at=generated_at,
        allow_network=allow_network,
        write=True,
    )
    read_root = rooted(read_model_root, repo_root=repo_root)
    return ExternalRegistryMaterializerResult(
        schema_version=READ_MODEL_VERSION,
        index_json_path=display_path(read_root / INDEX_JSON_NAME, repo_root=repo_root),
        operator_path=display_path(read_root / OPERATOR_INDEX_NAME, repo_root=repo_root),
        import_status=str(index.get("import_status", "UNKNOWN")),
        source_repo=str(index.get("source_repo", repo)),
        source_branch=str(index.get("source_branch", "")),
        source_commit=str(index.get("source_commit", "")),
        artifact_count=int(index.get("artifact_count", 0)),
        missing_artifact_count=len(index.get("missing_artifacts", [])),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import an external system knowledge registry cache.")
    parser.add_argument("--repo", default="openclaw-eyes")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--external-registry-root", default=str(DEFAULT_EXTERNAL_REGISTRY_ROOT))
    parser.add_argument("--external-source-root", default=str(DEFAULT_EXTERNAL_SOURCE_ROOT))
    parser.add_argument("--source-checkout", default="")
    parser.add_argument("--reference-resolver-path", default="")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_external_system_knowledge_registry(
        repo=args.repo,
        read_model_root=args.read_model_root,
        external_registry_root=args.external_registry_root,
        external_source_root=args.external_source_root,
        source_checkout=args.source_checkout or None,
        reference_resolver_payload=read_json_object(args.reference_resolver_path)
        if args.reference_resolver_path
        else None,
        allow_network=not args.no_network,
    )
    index_path = rooted(result.index_json_path)
    if args.format == "json":
        print(index_path.read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print(rooted(result.operator_path).read_text(encoding="utf-8"), end="")
    else:
        print(f"External System Knowledge Registry: `{result.schema_version}`")
        print(f"- Index: `{result.index_json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- Status: {result.import_status}")
        print(f"- Source: {result.source_repo}/{result.source_branch} @ {result.source_commit}")
        print(f"- Artifacts: {result.artifact_count}")
        print(f"- Missing artifacts: {result.missing_artifact_count}")
    return 0 if result.import_status == "IMPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
