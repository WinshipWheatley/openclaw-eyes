import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import validate_read_only_email_connector_setup as validator


def _write_env(path: Path, **values: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    return path


def test_external_credential_and_token_paths_are_accepted_structurally(tmp_path):
    private = tmp_path / "private"
    credential = private / "credentials.json"
    token = private / "token.json"
    credential.parent.mkdir()
    credential.write_text("not inspected", encoding="utf-8")
    token.write_text("not inspected", encoding="utf-8")
    env_file = _write_env(
        tmp_path / "gmail.env",
        OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH=str(credential),
        OPENCLAW_GMAIL_READONLY_TOKEN_PATH=str(token),
    )

    result = validator.validate_setup(env_file=env_file, repo_root=tmp_path / "repo")

    assert result["setup_status"] == "credential_present_unvalidated"
    assert result["credential_path_external"] is True
    assert result["token_path_external"] is True
    assert result["denied_scopes_present"] == "unknown"
    assert result["oauth_consent_required"] is True
    assert result["connector_status"]["configured"] is False


def test_repo_local_google_secrets_paths_are_rejected(tmp_path):
    repo = tmp_path / "repo"
    credential = repo / ".google-secrets" / "credentials.json"
    token = repo / ".google-secrets" / "token.json"
    credential.parent.mkdir(parents=True)
    credential.write_text("not inspected", encoding="utf-8")
    token.write_text("not inspected", encoding="utf-8")
    env_file = _write_env(
        tmp_path / "gmail.env",
        OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH=str(credential),
        OPENCLAW_GMAIL_READONLY_TOKEN_PATH=str(token),
    )

    result = validator.validate_setup(env_file=env_file, repo_root=repo)

    assert result["setup_status"] == "blocked"
    assert result["credential_path_external"] is False
    assert result["token_path_external"] is False
    assert "credential_path_inside_repo" in result["blockers"]
    assert "token_path_inside_repo" in result["blockers"]


def test_env_file_inside_repo_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    credential = tmp_path / "private" / "credentials.json"
    token = tmp_path / "private" / "token.json"
    credential.parent.mkdir(parents=True)
    credential.write_text("not inspected", encoding="utf-8")
    token.write_text("not inspected", encoding="utf-8")
    env_file = _write_env(
        repo / "gmail.env",
        OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH=str(credential),
        OPENCLAW_GMAIL_READONLY_TOKEN_PATH=str(token),
    )

    result = validator.validate_setup(env_file=env_file, repo_root=repo)

    assert result["setup_status"] == "blocked"
    assert result["env_file_external"] is False
    assert "env_file_inside_repo" in result["blockers"]


def test_missing_token_is_unvalidated_not_crash(tmp_path):
    credential = tmp_path / "private" / "credentials.json"
    credential.parent.mkdir(parents=True)
    credential.write_text("not inspected", encoding="utf-8")
    env_file = _write_env(
        tmp_path / "gmail.env",
        OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH=str(credential),
    )

    result = validator.validate_setup(env_file=env_file, repo_root=tmp_path / "repo")

    assert result["setup_status"] == "token_missing"
    assert result["credential_path_external"] is True
    assert result["token_path_external"] is False
    assert "token_missing" in result["blockers"]


def test_validator_output_does_not_include_secret_values(tmp_path):
    credential = tmp_path / "private" / "credentials.json"
    token = tmp_path / "private" / "token.json"
    credential.parent.mkdir(parents=True)
    credential.write_text("client_secret=do-not-print", encoding="utf-8")
    token.write_text("refresh_token=do-not-print", encoding="utf-8")
    env_file = _write_env(
        tmp_path / "gmail.env",
        OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH=str(credential),
        OPENCLAW_GMAIL_READONLY_TOKEN_PATH=str(token),
    )

    result = validator.validate_setup(env_file=env_file, repo_root=tmp_path / "repo")
    encoded = json.dumps(result)

    assert "do-not-print" not in encoded
    assert "client_secret=do-not-print" not in encoded
    assert "refresh_token=do-not-print" not in encoded
    assert result["credential_file_read"] is False
    assert result["token_file_read"] is False


def test_denied_scope_request_is_blocked_without_reading_credentials(tmp_path):
    credential = tmp_path / "private" / "credentials.json"
    token = tmp_path / "private" / "token.json"
    credential.parent.mkdir(parents=True)
    credential.write_text("not inspected", encoding="utf-8")
    token.write_text("not inspected", encoding="utf-8")
    env_file = _write_env(
        tmp_path / "gmail.env",
        OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH=str(credential),
        OPENCLAW_GMAIL_READONLY_TOKEN_PATH=str(token),
        OPENCLAW_GMAIL_READONLY_REQUIRED_SCOPE="https://www.googleapis.com/auth/gmail.compose",
    )

    result = validator.validate_setup(env_file=env_file, repo_root=tmp_path / "repo")

    assert result["setup_status"] == "scope_invalid"
    assert result["denied_scopes_present"] is True
    assert "denied_scope_requested" in result["blockers"]
