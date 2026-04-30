import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "demo_cassandra_email_triage.py"


def _load_demo_module():
    spec = importlib.util.spec_from_file_location("demo_cassandra_email_triage", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_demo_runs_in_text_mode_with_metadata_only_no_action_language():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Cassandra email triage training" in result.stdout
    assert "Metadata-only display" in result.stdout
    assert "No Gmail action will be taken" in result.stdout
    assert "Delivery status: not_sent" in result.stdout
    assert "Gear Digest <digest@example.com>" in result.stdout
    assert "Weekly newsletter sale on cases" in result.stdout
    assert "delete/archive/label/reply/send/draft" in result.stdout
    assert result.stderr == ""


def test_demo_json_mode_returns_parseable_display_payload():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["display_type"] == "email_triage_training.operator_display"
    assert payload["delivery_status"] == "not_sent"
    assert payload["packet"]["delivery_status"] == "not_sent"
    assert payload["message_id"] == "demo-newsletter-002"
    assert "No Gmail action will be taken" in payload["display_text"]
    assert result.stderr == ""


def test_demo_does_not_write_files(tmp_path, monkeypatch, capsys):
    demo = _load_demo_module()
    monkeypatch.chdir(tmp_path)

    assert demo.main([]) == 0

    captured = capsys.readouterr()
    assert "Metadata-only display" in captured.out
    assert list(tmp_path.iterdir()) == []


def test_demo_source_has_no_live_surface_imports_or_calls():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    forbidden_tokens = (
        "os.environ",
        "dotenv",
        "google_access_broker",
        "broker_call",
        "cassandra_sender",
        "send_message",
        "chief_guardian",
        "chief_approval",
        "create_gmail_draft",
        "google.gmail.draft.create",
        "google.gmail.send",
        "google.gmail.read.body",
        "archive_email",
        "delete_email",
        "move_email",
        "apple mail",
        "ollama_call",
        "nemotron_call",
        "claude",
        "gemini",
        "codex",
        "aider",
        "external_model_packet_policy",
        "cassandra_watcher",
    )
    lowered_source = source.lower()

    for token in forbidden_tokens:
        assert token not in lowered_source