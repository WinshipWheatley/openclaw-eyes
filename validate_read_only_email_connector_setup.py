"""Validate external read-only Gmail connector setup without reading secrets."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import read_only_email_lookup_connector as connector


SCHEMA_VERSION = "gmail_readonly_credential_setup_validator_v0"
READY_STATUS = "OPENCLAW_GMAIL_READONLY_CREDENTIAL_SETUP_VALIDATOR_READY"
DEFAULT_OUTPUT_PATH = Path("/tmp/openclaw-mission-control/gmail_readonly_externalize_validate_v0/setup_validator_result.json")

CREDENTIAL_ENV_VARS = (
    "OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH",
    "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_CREDENTIAL_FILE",
    "OPENCLAW_READ_ONLY_GMAIL_CREDENTIAL_FILE",
    "OPENCLAW_READONLY_GMAIL_CREDENTIAL_FILE",
)
TOKEN_ENV_VARS = (
    "OPENCLAW_GMAIL_READONLY_TOKEN_PATH",
    "OPENCLAW_READ_ONLY_EMAIL_LOOKUP_TOKEN_FILE",
    "OPENCLAW_READ_ONLY_GMAIL_TOKEN_FILE",
)
SCOPE_ENV_VAR = "OPENCLAW_GMAIL_READONLY_REQUIRED_SCOPE"


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_root(repo_root: Path | str) -> Path:
    return Path(repo_root).expanduser().resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        return path.expanduser().resolve(strict=False).is_relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False


def _outside_repo(path_value: str, repo_root: Path) -> bool:
    if not path_value:
        return False
    return not _is_relative_to(Path(path_value), repo_root)


def _path_exists(path_value: str) -> bool:
    if not path_value:
        return False
    try:
        return Path(path_value).expanduser().exists()
    except OSError:
        return False


def _load_env_file(path: Path | str | None) -> dict[str, str]:
    if not path:
        return {}
    env_path = Path(path)
    try:
        text = env_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _first_value(env: Mapping[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = str(env.get(name) or "").strip()
        if value:
            return value
    return ""


def _redacted_path_status(path_value: str, repo_root: Path) -> dict[str, Any]:
    return {
        "path": path_value,
        "exists": _path_exists(path_value),
        "external": _outside_repo(path_value, repo_root),
        "inside_repo": _is_relative_to(Path(path_value), repo_root) if path_value else False,
    }


def _connector_status_for_validator(
    *,
    credential_path: str,
    token_path: str,
    repo_root: Path,
    generated_at: str,
) -> dict[str, Any]:
    status = connector.get_connector_status(env={}, generated_at=generated_at)
    status.update(
        {
            "configured": False,
            "credential_source": "env_private_path" if credential_path else "none",
            "token_source": "env_private_path" if token_path else "none",
            "credential_path_external": _outside_repo(credential_path, repo_root),
            "token_path_external": _outside_repo(token_path, repo_root),
            "credential_file_present": _path_exists(credential_path),
            "token_file_present": _path_exists(token_path),
            "credential_file_read": False,
            "token_file_read": False,
            "secret_material_loaded": False,
        }
    )
    return status


def validate_setup(
    *,
    env_file: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    repo_root: Path | str = "/home/openclaw",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    repo = _repo_root(repo_root)
    env_map = dict(os.environ if env is None else env)
    env_map.update(_load_env_file(env_file))

    env_file_path = Path(env_file).expanduser().resolve(strict=False) if env_file else None
    env_file_external = True
    if env_file_path is not None:
        env_file_external = not _is_relative_to(env_file_path, repo)

    credential_path = _first_value(env_map, CREDENTIAL_ENV_VARS)
    token_path = _first_value(env_map, TOKEN_ENV_VARS)
    requested_scope = str(env_map.get(SCOPE_ENV_VAR) or connector.READ_ONLY_GMAIL_SCOPE).strip()
    denied_scope_requested = requested_scope in connector.FORBIDDEN_GMAIL_SCOPES

    blockers: list[str] = []
    if env_file_path is not None and not env_file_external:
        blockers.append("env_file_inside_repo")
    credential_status = _redacted_path_status(credential_path, repo)
    token_status = _redacted_path_status(token_path, repo)
    if credential_path and not credential_status["external"]:
        blockers.append("credential_path_inside_repo")
    if token_path and not token_status["external"]:
        blockers.append("token_path_inside_repo")
    if denied_scope_requested:
        blockers.append("denied_scope_requested")

    credential_exists = credential_status["exists"] and credential_status["external"]
    token_exists = token_status["exists"] and token_status["external"]
    if not credential_exists and "credential_path_inside_repo" not in blockers:
        blockers.append("credential_missing")
    if credential_exists and not token_exists and "token_path_inside_repo" not in blockers:
        blockers.append("token_missing")

    if denied_scope_requested:
        setup_status = "scope_invalid"
    elif any(item.endswith("_inside_repo") for item in blockers):
        setup_status = "blocked"
    elif not credential_exists:
        setup_status = "credential_missing"
    elif not token_exists:
        setup_status = "token_missing"
    else:
        setup_status = "credential_present_unvalidated"

    connector_status = _connector_status_for_validator(
        credential_path=credential_path,
        token_path=token_path,
        repo_root=repo,
        generated_at=generated_at,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": READY_STATUS,
        "setup_status": setup_status,
        "created_at": generated_at,
        "env_file": str(env_file_path) if env_file_path else "",
        "env_file_external": env_file_external,
        "credential_path": credential_path,
        "token_path": token_path,
        "credential_path_external": bool(credential_status["external"]),
        "token_path_external": bool(token_status["external"]),
        "credential_file_exists": bool(credential_status["exists"]),
        "token_file_exists": bool(token_status["exists"]),
        "credential_file_read": False,
        "token_file_read": False,
        "secret_material_loaded": False,
        "required_scope": connector.READ_ONLY_GMAIL_SCOPE,
        "requested_scope": requested_scope,
        "denied_scopes_present": True if denied_scope_requested else "unknown",
        "denied_scopes": list(connector.FORBIDDEN_GMAIL_SCOPES),
        "oauth_consent_required": setup_status == "credential_present_unvalidated",
        "connector_status": connector_status,
        "blockers": blockers,
        "next_step": _next_step(setup_status),
        "authority_boundary": dict(connector.AUTHORITY_BOUNDARY),
    }


def _next_step(setup_status: str) -> str:
    if setup_status == "credential_present_unvalidated":
        return "Complete OAuth/read-only token validation without opening browser from backend; if consent is required, operator must perform it manually."
    if setup_status == "token_missing":
        return "Provide or authorize an external read-only Gmail token path outside the repo."
    if setup_status == "credential_missing":
        return "Provide an external Gmail OAuth client credential path outside the repo using only gmail.readonly."
    if setup_status == "scope_invalid":
        return "Replace the requested scope with https://www.googleapis.com/auth/gmail.readonly only."
    return "Move env/credential/token paths outside the repo and rerun the setup validator."


def write_result(payload: Mapping[str, Any], output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(stable_json(payload), encoding="utf-8")
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate external read-only Gmail connector setup without reading secrets.")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=Path("/home/openclaw"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)
    payload = validate_setup(env_file=args.env_file, repo_root=args.repo_root)
    write_result(payload, args.output)
    print(stable_json({"setup_status": payload["setup_status"], "output": str(args.output)}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
