from __future__ import annotations

import json
import subprocess
from pathlib import Path

import scripts.probe_capability_heartbeat as heartbeat


REGISTRY_FIXTURE = """\
# Registry

### Comms
| capability | status | what | light-up |
| --- | --- | --- | --- |
| Gmail Draft Create | \U0001f7e2 lit | Draft without sending. | Operational. |
| Telegram Message Send | \U0001f7e1 dormant | Text send. | Token. |

### Personas & Services -- running brains (all \U0001f7e2 lit)
cassandra-listener · hermes-gateway · openclaw-request-response

### Governance
| capability | status | what | light-up |
| --- | --- | --- | --- |
| financial_transfer / payment / bill_pay | \u26ab dark | declared only | build |
"""


def test_parse_registry_tables_services_and_expanded_rows() -> None:
    records = heartbeat.parse_capability_registry(REGISTRY_FIXTURE)

    ids = [record.capability_id for record in records]

    assert "gmail_draft_create" in ids
    assert "telegram_message_send" in ids
    assert "cassandra_listener" in ids
    assert "hermes_gateway" in ids
    assert "openclaw_request_response" in ids
    assert "financial_transfer" in ids
    assert "payment" in ids
    assert "bill_pay" in ids
    assert next(record for record in records if record.capability_id == "payment").registry_status == "dark"


def test_systemd_active_probe_reports_lit_without_mutation(monkeypatch) -> None:
    monkeypatch.setattr(heartbeat.shutil, "which", lambda command: "/usr/bin/systemctl")

    commands: list[list[str]] = []

    def runner(command: list[str]) -> heartbeat.CommandResult:
        commands.append(command)
        return heartbeat.CommandResult(returncode=0, stdout="active\n")

    record = heartbeat.CapabilityRecord(
        capability_id="cassandra_listener",
        display_name="cassandra-listener",
        registry_status="lit",
        section="services",
    )

    outcome = heartbeat.probe_record(record, runner=runner, env_files=())

    assert outcome.live_status == "lit"
    assert outcome.drift is False
    assert commands == [["systemctl", "--user", "is-active", "cassandra-listener.service"]]


def test_drift_is_flagged_when_lit_service_is_inactive(monkeypatch) -> None:
    monkeypatch.setattr(heartbeat.shutil, "which", lambda command: "/usr/bin/systemctl")

    def runner(command: list[str]) -> heartbeat.CommandResult:
        return heartbeat.CommandResult(returncode=3, stdout="inactive\n")

    record = heartbeat.CapabilityRecord(
        capability_id="hermes_gateway",
        display_name="hermes-gateway",
        registry_status="lit",
        section="services",
    )

    outcome = heartbeat.probe_record(record, runner=runner, env_files=())

    assert outcome.live_status == "dark"
    assert outcome.drift is True
    assert "DRIFT" in outcome.flags


def test_env_probe_checks_presence_without_emitting_secret(tmp_path: Path) -> None:
    env_file = tmp_path / ".chief.env"
    env_file.write_text("PII_VAULT_KEY=super-secret-value\n", encoding="utf-8")

    result = heartbeat.env_present_check("PII_VAULT_KEY", (env_file,))

    assert result.status == "pass"
    assert "super-secret-value" not in result.evidence


def test_hold_block_keeps_capability_dormant() -> None:
    record = heartbeat.CapabilityRecord(
        capability_id="gmail_send",
        display_name="Gmail Send",
        registry_status="dormant",
        section="comms",
    )
    live_status, confidence, flags = heartbeat.infer_live_status(
        record,
        (
            heartbeat.CheckResult("source", "pass", "present"),
            heartbeat.CheckResult("hold", "block", "SEND_HOLD active"),
        ),
    )

    assert live_status == "dormant"
    assert confidence == "medium"
    assert "blocked_by_hold" in flags


def test_broken_registry_status_survives_required_check_failure() -> None:
    record = heartbeat.CapabilityRecord(
        capability_id="google_calendar_write",
        display_name="google-calendar-write",
        registry_status="broken",
        section="governance",
    )
    live_status, _confidence, flags = heartbeat.infer_live_status(
        record,
        (
            heartbeat.CheckResult("credentials", "pass", "present"),
            heartbeat.CheckResult("scope", "fail", "full calendar scope missing"),
        ),
    )

    assert live_status == "broken"
    assert "expected_breakage_still_observed" in flags


def test_report_and_operator_output_include_drift(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "registry.md"
    registry.write_text(REGISTRY_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(heartbeat.shutil, "which", lambda command: "/usr/bin/systemctl")

    def runner(command: list[str]) -> heartbeat.CommandResult:
        if command[-1] == "hermes-gateway.service":
            return heartbeat.CommandResult(returncode=3, stdout="inactive\n")
        return heartbeat.CommandResult(returncode=0, stdout="active\n")

    report = heartbeat.build_report(registry, runner=runner, env_files=())
    rendered = heartbeat.format_operator(report)

    assert report["read_only"] is True
    assert "hermes_gateway" in report["drift_capabilities"]
    assert "DRIFT" in rendered
    assert "no send, dispatch, merge, deploy, restart" in rendered


def test_cli_json_output(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "registry.md"
    registry.write_text(REGISTRY_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(heartbeat.shutil, "which", lambda command: None)

    completed = subprocess.run(
        [
            "python3",
            "scripts/probe_capability_heartbeat.py",
            "--registry",
            str(registry),
            "--format",
            "json",
        ],
        cwd=heartbeat.ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    payload = json.loads(completed.stdout)
    assert payload["schema_version"] == "capability_heartbeat_v0"
    assert payload["capability_count"] == 8
    assert payload["safety"]["service_mutations"] is False


def test_probe_script_does_not_contain_send_or_service_mutation_calls() -> None:
    source = (heartbeat.ROOT / "scripts" / "probe_capability_heartbeat.py").read_text(encoding="utf-8")
    forbidden = (
        "subprocess.run([\"systemctl\", \"--user\", \"start\"",
        "subprocess.run([\"systemctl\", \"--user\", \"restart\"",
        "subprocess.run([\"systemctl\", \"--user\", \"enable\"",
        "subprocess.run([\"systemctl\", \"--user\", \"stop\"",
        "requests.post(",
        ".send(",
        "process_callback(",
    )
    assert not any(marker in source for marker in forbidden)
