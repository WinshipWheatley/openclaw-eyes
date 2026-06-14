import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import read_only_email_lookup_connector as connector
import validate_read_only_email_connector_setup as validator


def _write_env(path: Path, **values: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    return path


def _private_env(tmp_path: Path, *, token: bool = True, scope: str | None = None):
    private = tmp_path / "private"
    credential = private / "credentials.json"
    token_path = private / "token.json"
    private.mkdir()
    credential.write_text("client_secret=do-not-print", encoding="utf-8")
    if token:
        token_path.write_text("refresh_token=do-not-print", encoding="utf-8")
    values = {
        "OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH": str(credential),
        "OPENCLAW_GMAIL_READONLY_TOKEN_PATH": str(token_path),
    }
    if scope:
        values["OPENCLAW_GMAIL_READONLY_REQUIRED_SCOPE"] = scope
    return _write_env(tmp_path / "gmail.env", **values), credential, token_path


def _probe_with_scopes(scopes):
    def probe(**_kwargs):
        return {
            "dependency_status": "present",
            "missing_dependencies": [],
            "granted_scopes": list(scopes),
            "token_refresh_attempted": False,
            "token_refresh_succeeded": False,
            "token_valid": True,
            "probe_status": "ok",
        }

    return probe


def test_scope_validator_reports_validated_readonly_when_required_scope_is_present(tmp_path):
    env_file, _credential, _token = _private_env(tmp_path)

    result = validator.validate_setup(
        env_file=env_file,
        repo_root=tmp_path / "repo",
        oauth_scope_probe=_probe_with_scopes([connector.READ_ONLY_GMAIL_SCOPE]),
    )

    assert result["read_model_id"] == "GMAIL_READONLY_SCOPE_VALIDATION_V0"
    assert result["setup_status"] == "validated_readonly"
    assert result["granted_scopes_status"] == "readonly_only"
    assert result["denied_scopes_detected"] == []
    assert result["token_refresh_attempted"] is False
    assert result["token_refresh_succeeded"] is False
    assert result["live_mailbox_access_performed"] is False
    assert result["browser_opened"] is False
    assert result["secrets_printed"] is False
    assert result["connector_status"]["setup_status"] == "validated_readonly"
    assert result["active_next_step"] == "run authorized read-only lookup"


def test_scope_validator_reports_scope_invalid_when_denied_scope_is_detected(tmp_path):
    env_file, _credential, _token = _private_env(tmp_path)

    result = validator.validate_setup(
        env_file=env_file,
        repo_root=tmp_path / "repo",
        oauth_scope_probe=_probe_with_scopes(
            [
                connector.READ_ONLY_GMAIL_SCOPE,
                "https://www.googleapis.com/auth/gmail.send",
            ]
        ),
    )

    assert result["setup_status"] == "scope_invalid"
    assert result["granted_scopes_status"] == "denied_scope_present"
    assert result["denied_scopes_detected"] == ["https://www.googleapis.com/auth/gmail.send"]
    assert result["active_next_step"] == "Reauthorize externally with gmail.readonly only."


def test_scope_validator_reports_oauth_human_consent_required_without_opening_browser(tmp_path):
    env_file, _credential, _token = _private_env(tmp_path, token=False)

    result = validator.validate_setup(env_file=env_file, repo_root=tmp_path / "repo")

    assert result["setup_status"] == "oauth_human_consent_required"
    assert result["granted_scopes_status"] == "oauth_human_consent_required"
    assert result["token_refresh_attempted"] is False
    assert result["browser_opened"] is False
    assert result["active_next_step"] == (
        "Complete OAuth consent externally for gmail.readonly only using the existing external credential path, then rerun validator."
    )


def test_scope_validator_reports_dependency_missing_without_installing_or_opening_browser(tmp_path):
    env_file, _credential, _token = _private_env(tmp_path)

    def missing_probe(**_kwargs):
        return {
            "dependency_status": "VALIDATOR_DEPENDENCY_MISSING",
            "missing_dependencies": ["google.oauth2.credentials"],
            "granted_scopes": [],
            "token_refresh_attempted": False,
            "token_refresh_succeeded": False,
            "token_valid": False,
            "probe_status": "dependency_missing",
        }

    result = validator.validate_setup(env_file=env_file, repo_root=tmp_path / "repo", oauth_scope_probe=missing_probe)

    assert result["setup_status"] == "credential_validation_blocked"
    assert result["validator_dependency_status"] == "VALIDATOR_DEPENDENCY_MISSING"
    assert result["granted_scopes_status"] == "unknown"
    assert result["token_refresh_attempted"] is False
    assert result["browser_opened"] is False
    assert "google.oauth2.credentials" in result["missing_validator_dependencies"]
    assert result["active_next_step"] == "Install or enable Google OAuth validator dependencies, then rerun validator."


def test_scope_validator_rejects_paths_inside_openclaw_repo(tmp_path):
    repo = tmp_path / "repo"
    credential = repo / ".google-secrets" / "credentials.json"
    token = repo / ".google-secrets" / "token.json"
    credential.parent.mkdir(parents=True)
    credential.write_text("client_secret=do-not-print", encoding="utf-8")
    token.write_text("refresh_token=do-not-print", encoding="utf-8")
    env_file = _write_env(
        tmp_path / "gmail.env",
        OPENCLAW_GMAIL_READONLY_CREDENTIAL_PATH=str(credential),
        OPENCLAW_GMAIL_READONLY_TOKEN_PATH=str(token),
    )

    result = validator.validate_setup(
        env_file=env_file,
        repo_root=repo,
        oauth_scope_probe=_probe_with_scopes([connector.READ_ONLY_GMAIL_SCOPE]),
    )

    assert result["setup_status"] == "credential_validation_blocked"
    assert result["credential_path_external"] is False
    assert result["token_path_external"] is False
    assert result["token_refresh_attempted"] is False
    assert "credential_path_inside_repo" in result["blockers"]
    assert "token_path_inside_repo" in result["blockers"]


def test_scope_validator_never_prints_token_or_secret_contents(tmp_path):
    env_file, _credential, _token = _private_env(tmp_path)

    result = validator.validate_setup(
        env_file=env_file,
        repo_root=tmp_path / "repo",
        oauth_scope_probe=_probe_with_scopes([connector.READ_ONLY_GMAIL_SCOPE]),
    )
    encoded = json.dumps(result)

    assert "do-not-print" not in encoded
    assert "client_secret=do-not-print" not in encoded
    assert "refresh_token=do-not-print" not in encoded
    assert result["secrets_printed"] is False
