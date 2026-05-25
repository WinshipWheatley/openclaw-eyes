import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import google_broker_readonly_wrapper as wrapper
from scripts.run_google_broker_readonly_wrapper import main as run_main


FIXED_NOW = "2026-05-25T19:00:00+00:00"


def test_allowed_read_capabilities_accept_fixture_or_request():
    for capability in wrapper.SUPPORTED_READ_CAPABILITIES:
        request = wrapper.make_request(capability=capability, generated_at=FIXED_NOW)
        status, blockers = wrapper.validate_request(request)
        assert status is None, capability
        assert blockers == ()


def test_send_write_body_attachment_capabilities_blocked():
    cases = {
        "google.gmail.send": "BLOCKED_WRITE_CAPABILITY",
        "google.gmail.draft.create": "BLOCKED_WRITE_CAPABILITY",
        "google.calendar.write": "BLOCKED_WRITE_CAPABILITY",
        "google.contacts.write": "BLOCKED_WRITE_CAPABILITY",
        "google.gmail.read.body": "BLOCKED_BODY_READ",
        "attachment.download": "BLOCKED_UNSUPPORTED_CAPABILITY",
    }
    for capability, expected in cases.items():
        request = wrapper.make_request(capability=capability, generated_at=FIXED_NOW)
        status, blockers = wrapper.validate_request(request)
        assert status == expected
        assert blockers


def test_unsupported_capability_blocked():
    request = wrapper.make_request(capability="google.drive.read", generated_at=FIXED_NOW)
    status, blockers = wrapper.validate_request(request)

    assert status == "BLOCKED_UNSUPPORTED_CAPABILITY"
    assert blockers[0].blocker_type == "UNKNOWN_CAPABILITY"


def test_contacts_fixture_tokenizes_and_exports_no_raw_pii(tmp_path, capsys):
    assert run_main(
        [
            "--fixture",
            "contacts",
            "--export-root",
            str(tmp_path),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    output_text = json.dumps(payload)

    assert payload["readback"]["status"] == "FIXTURE_READBACK_READY"
    assert payload["readback"]["tokenized_results"]
    result = payload["readback"]["tokenized_results"][0]
    assert result["tokenized_display_name_ref"]
    assert result["tokenized_email_ref"]
    assert result["tokenized_phone_ref"]
    assert "fixture.alpha@example.invalid" not in output_text
    assert "555-010-2200" not in output_text
    assert payload["readback"]["credential_exposure"] is False
    assert payload["readback"]["raw_body_exposure"] is False


def test_gmail_metadata_fixture_tokenizes_subject_and_snippet(tmp_path, capsys):
    assert run_main(
        [
            "--fixture",
            "gmail_metadata",
            "--export-root",
            str(tmp_path),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    output_text = json.dumps(payload)
    result = payload["readback"]["tokenized_results"][0]

    assert payload["readback"]["status"] == "FIXTURE_READBACK_READY"
    assert result["tokenized_subject_ref"]
    assert result["tokenized_snippet_ref"]
    assert "Fixture metadata subject" not in output_text
    assert "Fixture snippet" not in output_text
    assert payload["security_summary"]["send_or_write"] is False


def test_operator_markdown_contains_safe_summary_only(tmp_path):
    payload = wrapper.build_from_fixture("contacts", generated_at=FIXED_NOW)
    _json_path, operator_path = wrapper.write_exports(payload, tmp_path)
    text = operator_path.read_text(encoding="utf-8")

    assert "tokenized metadata only" in text
    assert "fixture.alpha@example.invalid" not in text
    assert "555-010-2200" not in text
    assert "Gmail body" in text


def test_wrapper_does_not_directly_import_repo_b_broker_in_repo_a_runtime():
    source = Path("google_broker_readonly_wrapper.py").read_text(encoding="utf-8")
    assert "from google_access_broker import" not in source
    assert "\nimport google_access_broker" not in source
    assert "subprocess.run" in source
    assert "OPENCLAW_GOOGLE_SEND_ALLOWED" in source


def test_subprocess_timeout_is_modeled(monkeypatch):
    request = wrapper.make_request(capability="google.contacts.read", generated_at=FIXED_NOW)

    def _timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="fixture", timeout=0.001)

    monkeypatch.setattr(wrapper.subprocess, "run", _timeout)
    status, result, blockers = wrapper.run_repo_b_broker_subprocess(request, timeout_ms=1)

    assert status == "SUBPROCESS_TIMEOUT"
    assert result is None
    assert blockers[0].blocker_type == "SUBPROCESS_TIMEOUT"


def test_live_not_requested_returns_broker_unavailable_without_calling_subprocess(monkeypatch):
    called = False

    def _run(*_args, **_kwargs):
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(wrapper, "run_repo_b_broker_subprocess", _run)
    request = wrapper.make_request(capability="google.contacts.read", generated_at=FIXED_NOW)
    payload = wrapper.build_readback(request, mode=wrapper.GOOGLE_READ_ONLY_BRIDGE, live=False)

    assert payload["readback"]["status"] == "BROKER_UNAVAILABLE"
    assert called is False
    assert payload["readback"]["external_actions"] is False


def test_generated_readback_all_external_authority_false_except_fixture(tmp_path):
    payload = wrapper.build_from_fixture("gmail_metadata", generated_at=FIXED_NOW)
    wrapper.write_exports(payload, tmp_path)
    data = json.loads((tmp_path / wrapper.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert data["machine_proof"]["gmail_send_performed"] is False
    assert data["machine_proof"]["calendar_write_performed"] is False
    assert data["machine_proof"]["contacts_write_performed"] is False
    assert data["machine_proof"]["gmail_body_read_performed"] is False
    assert data["machine_proof"]["attachment_read_or_download_performed"] is False
    assert data["machine_proof"]["all_authority_boundary_flags_false_except_fixture"] is True
    for key, value in data["authority_boundary"].items():
        if key == "google_read_only_fixture_allowed":
            assert value is True
        else:
            assert value is False, key
