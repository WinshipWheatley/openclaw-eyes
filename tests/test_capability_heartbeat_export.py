from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.export_capability_heartbeat_read_model import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    export_capability_heartbeat_read_model,
    format_summary,
    main,
)
from scripts.probe_capability_heartbeat import stable_json


ROOT = Path(__file__).resolve().parents[1]
SERVICE_TEMPLATE = ROOT / "systemd" / "user" / "openclaw-capability-heartbeat.service.in"
TIMER_TEMPLATE = ROOT / "systemd" / "user" / "openclaw-capability-heartbeat.timer.in"


REGISTRY_FIXTURE = """\
# Registry

### Personas & Services -- running brains (all \U0001f7e2 lit)
cassandra-listener · hermes-gateway

### Governance
| capability | status | what | light-up |
| --- | --- | --- | --- |
| sms | \U0001f7e1 dormant | SMS | Twilio |
"""


def test_export_writes_json_and_operator_read_models(tmp_path: Path) -> None:
    registry = tmp_path / "registry.md"
    registry.write_text(REGISTRY_FIXTURE, encoding="utf-8")
    export_root = tmp_path / "read_models"

    summary = export_capability_heartbeat_read_model(
        registry_path=registry,
        live_root=tmp_path,
        export_root=export_root,
        generated_at="2026-06-18T04:00:00+00:00",
    )

    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["read_only_probe"] is True
    assert summary["service_mutations"] is False
    assert summary["send_or_dispatch_calls"] is False
    assert payload["generated_at"] == "2026-06-18T04:00:00+00:00"
    assert payload["capability_count"] == 3
    assert "Capability Heartbeat Report" in operator_path.read_text(encoding="utf-8")


def test_check_mode_reports_current_then_stale(tmp_path: Path) -> None:
    registry = tmp_path / "registry.md"
    registry.write_text(REGISTRY_FIXTURE, encoding="utf-8")
    export_root = tmp_path / "read_models"
    kwargs = {
        "registry_path": registry,
        "live_root": tmp_path,
        "export_root": export_root,
        "generated_at": "2026-06-18T04:00:00+00:00",
    }

    export_capability_heartbeat_read_model(**kwargs)
    current = export_capability_heartbeat_read_model(**kwargs, check=True)
    (export_root / JSON_EXPORT_NAME).write_text(stable_json({"stale": True}), encoding="utf-8")
    stale = export_capability_heartbeat_read_model(**kwargs, check=True)

    assert current["check_status"] == "current"
    assert stale["check_status"] == "stale"
    assert (export_root / JSON_EXPORT_NAME).as_posix() in stale["stale_exports"]


def test_cli_json_output_is_machine_readable(tmp_path: Path, capsys) -> None:
    registry = tmp_path / "registry.md"
    registry.write_text(REGISTRY_FIXTURE, encoding="utf-8")

    exit_code = main(
        [
            "--registry",
            registry.as_posix(),
            "--live-root",
            tmp_path.as_posix(),
            "--export-root",
            (tmp_path / "read_models").as_posix(),
            "--generated-at",
            "2026-06-18T04:00:00+00:00",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["export_version"] == "capability_heartbeat_export_v0"
    assert payload["install_or_enable_performed"] is False


def test_summary_states_boundary_and_next_safe_move(tmp_path: Path) -> None:
    summary = {
        "json_path": "generated/read_models/capability_heartbeat.json",
        "operator_path": "generated/read_models/capability_heartbeat_OPERATOR.md",
        "capability_count": 3,
        "drift_count": 1,
        "live_status_counts": {"lit": 2, "dark": 1},
        "drift_capabilities": ["sms"],
    }

    text = format_summary(summary)

    assert "Evidence:" in text
    assert "Boundary:" in text
    assert "Next safe move:" in text
    assert "no service mutation" in text


def test_proposed_systemd_units_are_timer_only_and_do_not_install_or_enable() -> None:
    service = SERVICE_TEMPLATE.read_text(encoding="utf-8")
    timer = TIMER_TEMPLATE.read_text(encoding="utf-8")
    combined = service + "\n" + timer

    assert "export_capability_heartbeat_read_model.py" in service
    assert "--format summary" in service
    assert "OnUnitActiveSec=20min" in timer
    assert "Unit=openclaw-capability-heartbeat.service" in timer
    assert "WantedBy=timers.target" in timer
    assert "Type=oneshot" in service
    assert "NoNewPrivileges=true" in service

    forbidden_lifecycle = re.compile(
        r"\bsystemctl\b[^\n#]*\b(start|stop|restart|reload|enable|disable|daemon-reload)\b"
    )
    forbidden_commands = ("install ", "enable --now", "restart ", "daemon-reload")
    assert not forbidden_lifecycle.search(combined)
    assert not any(command in combined for command in forbidden_commands)
