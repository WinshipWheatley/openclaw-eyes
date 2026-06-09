"""Validate external read-only Gmail connector setup without reading secrets."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import read_only_email_lookup_connector as connector


SCHEMA_VERSION = "gmail_readonly_credential_setup_validator_v0"
SCOPE_VALIDATION_SCHEMA_VERSION = "gmail_readonly_scope_validation_v0"
SCOPE_VALIDATION_READ_MODEL_ID = "GMAIL_READONLY_SCOPE_VALIDATION_V0"
READY_STATUS = "OPENCLAW_GMAIL_READONLY_CREDENTIAL_SETUP_VALIDATOR_READY"
DEFAULT_OUTPUT_PATH = Path("/tmp/openclaw-mission-control/gmail_readonly_externalize_validate_v0/setup_validator_result.json")
DEFAULT_SCOPE_OUTPUT_PATH = Path("/tmp/openclaw-mission-control/gmail_readonly_scope_validate_v0/scope_validation_result.json")
VALIDATOR_DEPENDENCY_MISSING = "VALIDATOR_DEPENDENCY_MISSING"

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
SETUP_STATUS_ENV_VAR = "OPENCLAW_GMAIL_READONLY_SETUP_STATUS"
GRANTED_SCOPES_STATUS_ENV_VAR = "OPENCLAW_GMAIL_READONLY_GRANTED_SCOPES_STATUS"

OAuthScopeProbe = Callable[..., Mapping[str, Any]]


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


def _normalize_scopes(scopes: Any) -> list[str]:
    if not scopes:
        return []
    if isinstance(scopes, str):
        raw = scopes.replace(",", " ").split()
    else:
        raw = [str(scope) for scope in scopes]
    return sorted({scope.strip() for scope in raw if scope and scope.strip()})


def _scope_policy_status(granted_scopes: Sequence[str]) -> tuple[str, list[str]]:
    scopes = _normalize_scopes(granted_scopes)
    denied = sorted(
        scope
        for scope in scopes
        if scope in connector.FORBIDDEN_GMAIL_SCOPES or scope != connector.READ_ONLY_GMAIL_SCOPE
    )
    if denied:
        return "denied_scope_present", denied
    if connector.READ_ONLY_GMAIL_SCOPE not in scopes:
        return "missing_required_scope", []
    return "readonly_only", []


def _google_oauth_dependency_status() -> dict[str, Any]:
    missing: list[str] = []
    for module_name in (
        "google.oauth2.credentials",
        "google.auth.transport.requests",
    ):
        try:
            __import__(module_name)
        except Exception:
            missing.append(module_name)
    return {
        "dependency_status": VALIDATOR_DEPENDENCY_MISSING if missing else "present",
        "missing_dependencies": missing,
    }


def _extract_credential_scopes(credentials: Any) -> list[str]:
    for attr in ("scopes", "_scopes"):
        value = getattr(credentials, attr, None)
        scopes = _normalize_scopes(value)
        if scopes:
            return scopes
    return []


def _tokeninfo_scopes(access_token: str) -> list[str]:
    if not access_token:
        return []
    query = urllib.parse.urlencode({"access_token": access_token})
    request = urllib.request.Request(f"https://oauth2.googleapis.com/tokeninfo?{query}", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    return _normalize_scopes(payload.get("scope"))


def _probe_google_oauth_scopes(
    *,
    credential_path: str,
    token_path: str,
    token_path_external: bool,
    requested_scope: str,
) -> dict[str, Any]:
    dependency = _google_oauth_dependency_status()
    if dependency["dependency_status"] == VALIDATOR_DEPENDENCY_MISSING:
        return {
            **dependency,
            "probe_status": "dependency_missing",
            "granted_scopes": [],
            "token_refresh_attempted": False,
            "token_refresh_succeeded": False,
            "token_valid": False,
            "token_file_read": False,
        }

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except Exception:
        return {
            "dependency_status": VALIDATOR_DEPENDENCY_MISSING,
            "missing_dependencies": ["google.oauth2.credentials", "google.auth.transport.requests"],
            "probe_status": "dependency_missing",
            "granted_scopes": [],
            "token_refresh_attempted": False,
            "token_refresh_succeeded": False,
            "token_valid": False,
            "token_file_read": False,
        }

    del credential_path, requested_scope
    try:
        credentials = Credentials.from_authorized_user_file(token_path)
    except Exception:
        return {
            "dependency_status": "present",
            "missing_dependencies": [],
            "probe_status": "token_invalid_or_expired",
            "granted_scopes": [],
            "token_refresh_attempted": False,
            "token_refresh_succeeded": False,
            "token_valid": False,
            "token_file_read": True,
        }

    token_refresh_attempted = False
    token_refresh_succeeded = False
    if not getattr(credentials, "valid", False):
        if getattr(credentials, "expired", False) and getattr(credentials, "refresh_token", None):
            token_refresh_attempted = True
            try:
                credentials.refresh(Request())
                token_refresh_succeeded = bool(getattr(credentials, "valid", False))
                if token_refresh_succeeded and token_path_external:
                    Path(token_path).write_text(credentials.to_json(), encoding="utf-8")
            except Exception:
                return {
                    "dependency_status": "present",
                    "missing_dependencies": [],
                    "probe_status": "token_invalid_or_expired",
                    "granted_scopes": _extract_credential_scopes(credentials),
                    "token_refresh_attempted": True,
                    "token_refresh_succeeded": False,
                    "token_valid": False,
                    "token_file_read": True,
                }
        else:
            return {
                "dependency_status": "present",
                "missing_dependencies": [],
                "probe_status": "oauth_human_consent_required",
                "granted_scopes": _extract_credential_scopes(credentials),
                "token_refresh_attempted": False,
                "token_refresh_succeeded": False,
                "token_valid": False,
                "token_file_read": True,
            }

    granted_scopes = _extract_credential_scopes(credentials)
    if not granted_scopes:
        granted_scopes = _tokeninfo_scopes(str(getattr(credentials, "token", "") or ""))
    return {
        "dependency_status": "present",
        "missing_dependencies": [],
        "probe_status": "ok" if granted_scopes else "scope_unknown",
        "granted_scopes": granted_scopes,
        "token_refresh_attempted": token_refresh_attempted,
        "token_refresh_succeeded": token_refresh_succeeded,
        "token_valid": bool(getattr(credentials, "valid", False)),
        "token_file_read": True,
    }


def _connector_status_for_validator(
    *,
    credential_path: str,
    token_path: str,
    repo_root: Path,
    generated_at: str,
    setup_status: str = "credential_present_unvalidated",
    granted_scopes_status: str = "unknown",
) -> dict[str, Any]:
    status = connector.get_connector_status(
        env={
            "OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH": credential_path,
            SETUP_STATUS_ENV_VAR: setup_status,
            GRANTED_SCOPES_STATUS_ENV_VAR: granted_scopes_status,
        },
        generated_at=generated_at,
    )
    status.update(
        {
            "configured": bool(credential_path and _outside_repo(credential_path, repo_root) and _path_exists(credential_path)),
            "credential_source": "env_private_path" if credential_path else "none",
            "token_source": "env_private_path" if token_path else "none",
            "credential_path_external": _outside_repo(credential_path, repo_root),
            "token_path_external": _outside_repo(token_path, repo_root),
            "credential_file_present": _path_exists(credential_path),
            "token_file_present": _path_exists(token_path),
            "credential_file_read": False,
            "secret_material_loaded": False,
            "setup_status": setup_status,
            "granted_scopes_status": granted_scopes_status,
            "validated_readonly": setup_status == "validated_readonly" and granted_scopes_status == "readonly_only",
        }
    )
    return status


def validate_setup(
    *,
    env_file: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    repo_root: Path | str = "/home/openclaw",
    generated_at: str | None = None,
    oauth_scope_probe: OAuthScopeProbe | None = None,
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

    probe_result: Mapping[str, Any] = {}
    token_refresh_attempted = False
    token_refresh_succeeded = False
    granted_scopes_status = "unknown"
    denied_scopes_detected: list[str] = []
    missing_validator_dependencies: list[str] = []
    validator_dependency_status = "not_required"

    if denied_scope_requested:
        setup_status = "scope_invalid"
        granted_scopes_status = "denied_scope_present"
        denied_scopes_detected = [requested_scope]
    elif any(item.endswith("_inside_repo") for item in blockers):
        setup_status = "credential_validation_blocked"
    elif not credential_exists:
        setup_status = "credential_validation_blocked"
    elif not token_exists:
        setup_status = "oauth_human_consent_required"
        granted_scopes_status = "oauth_human_consent_required"
    else:
        probe = oauth_scope_probe or _probe_google_oauth_scopes
        probe_result = probe(
            credential_path=credential_path,
            token_path=token_path,
            token_path_external=bool(token_status["external"]),
            requested_scope=requested_scope,
        )
        token_refresh_attempted = bool(probe_result.get("token_refresh_attempted"))
        token_refresh_succeeded = bool(probe_result.get("token_refresh_succeeded"))
        validator_dependency_status = str(probe_result.get("dependency_status") or "present")
        missing_validator_dependencies = [str(item) for item in probe_result.get("missing_dependencies") or []]
        probe_status = str(probe_result.get("probe_status") or "")
        if validator_dependency_status == VALIDATOR_DEPENDENCY_MISSING or probe_status == "dependency_missing":
            setup_status = "credential_validation_blocked"
            granted_scopes_status = "unknown"
        elif probe_status == "oauth_human_consent_required":
            setup_status = "oauth_human_consent_required"
            granted_scopes_status = "oauth_human_consent_required"
        elif probe_status == "token_invalid_or_expired":
            setup_status = "token_invalid_or_expired"
            granted_scopes_status = "token_invalid_or_expired"
        else:
            granted_scopes_status, denied_scopes_detected = _scope_policy_status(
                _normalize_scopes(probe_result.get("granted_scopes"))
            )
            if granted_scopes_status == "readonly_only":
                setup_status = "validated_readonly"
            elif granted_scopes_status == "denied_scope_present":
                setup_status = "scope_invalid"
            elif granted_scopes_status == "missing_required_scope":
                setup_status = "scope_invalid"
            else:
                setup_status = "credential_validation_blocked"

    connector_status = _connector_status_for_validator(
        credential_path=credential_path,
        token_path=token_path,
        repo_root=repo,
        generated_at=generated_at,
        setup_status=setup_status,
        granted_scopes_status=granted_scopes_status,
    )
    active_next_step = _next_step(
        setup_status,
        blockers=blockers,
        validator_dependency_status=validator_dependency_status,
    )
    validation_id = f"gmail_readonly_scope_validation:{connector._short_hash(credential_path, token_path, generated_at)}"
    denied_scopes_present: bool | str
    if granted_scopes_status == "unknown":
        denied_scopes_present = "unknown"
    else:
        denied_scopes_present = bool(denied_scopes_detected)
    return {
        "schema_version": SCOPE_VALIDATION_SCHEMA_VERSION,
        "read_model_id": SCOPE_VALIDATION_READ_MODEL_ID,
        "status": READY_STATUS,
        "validation_id": validation_id,
        "setup_id": "gmail_readonly_external_setup_v0",
        "provider": "gmail",
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
        "token_file_read": bool(probe_result.get("token_file_read")),
        "secret_material_loaded": False,
        "required_scope": connector.READ_ONLY_GMAIL_SCOPE,
        "requested_scope": requested_scope,
        "granted_scopes_status": granted_scopes_status,
        "denied_scopes_detected": denied_scopes_detected,
        "denied_scopes_present": denied_scopes_present,
        "denied_scopes": list(connector.FORBIDDEN_GMAIL_SCOPES),
        "token_refresh_attempted": token_refresh_attempted,
        "token_refresh_succeeded": token_refresh_succeeded,
        "live_mailbox_access_performed": False,
        "browser_opened": False,
        "secrets_printed": False,
        "validator_dependency_status": validator_dependency_status,
        "missing_validator_dependencies": missing_validator_dependencies,
        "oauth_consent_required": setup_status == "oauth_human_consent_required",
        "connector_status": connector_status,
        "blockers": blockers,
        "active_next_step": active_next_step,
        "next_step": active_next_step,
        "receipt_ref": f"gmail_readonly_scope_validation_receipt:{connector._short_hash(validation_id, setup_status)}",
        "authority_boundary": dict(connector.AUTHORITY_BOUNDARY),
    }


def _next_step(
    setup_status: str,
    *,
    blockers: Sequence[str] = (),
    validator_dependency_status: str = "not_required",
) -> str:
    if setup_status == "validated_readonly":
        return "run authorized read-only lookup"
    if validator_dependency_status == VALIDATOR_DEPENDENCY_MISSING:
        return "Install or enable Google OAuth validator dependencies, then rerun validator."
    if setup_status == "oauth_human_consent_required":
        return "Complete OAuth consent externally for gmail.readonly only using the existing external credential path, then rerun validator."
    if setup_status == "token_invalid_or_expired":
        return "Reauthorize externally with gmail.readonly only, then rerun validator."
    if setup_status == "scope_invalid":
        return "Reauthorize externally with gmail.readonly only."
    if "credential_missing" in blockers:
        return "Fix external Gmail credential path, then rerun validator."
    if "token_missing" in blockers:
        return "Complete OAuth consent externally for gmail.readonly only using the existing external credential path, then rerun validator."
    return "Move env/credential/token paths outside the repo and rerun validator."


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
