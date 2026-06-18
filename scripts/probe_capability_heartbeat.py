#!/usr/bin/env python3
"""Read-only live heartbeat probes for the OpenClaw capability registry."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIVE_ROOT = Path("/home/openclaw")
DEFAULT_REGISTRY_PATH = Path("/mnt/e/openclaw/orchestration/artifacts/CAPABILITY_HEALTH_REGISTRY.md")
DEFAULT_SEND_HOLD_PATH = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")
DEFAULT_ENV_FILES = (
    ROOT / ".chief.env",
    ROOT / ".env",
    ROOT / ".cassandra.env",
    ROOT / ".openclaw.env",
    Path("/home/openclaw/.chief.env"),
    Path("/home/openclaw/.env"),
)
STATUS_MARKERS = {
    "\U0001f7e2": "lit",
    "\U0001f7e1": "dormant",
    "\U0001f534": "broken",
    "\u26ab": "dark",
    "\u2754": "unknown",
}
DRIFTING_STATUSES = {"lit", "dormant", "broken", "dark"}
UNSAFE_RUNTIME_MARKER_PARTS = (
    ("requests", ".post("),
    ("process", "_callback("),
    ('subprocess.run(["systemctl"', ', "--user", "start"'),
    ('subprocess.run(["systemctl"', ', "--user", "restart"'),
    ('subprocess.run(["systemctl"', ', "--user", "enable"'),
    ('subprocess.run(["systemctl"', ', "--user", "stop"'),
)


@dataclass(frozen=True)
class CapabilityRecord:
    capability_id: str
    display_name: str
    registry_status: str
    section: str
    description: str = ""
    light_up: str = ""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    evidence: str


@dataclass(frozen=True)
class ProbeOutcome:
    capability_id: str
    display_name: str
    registry_status: str
    live_status: str
    drift: bool
    confidence: str
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)
    flags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "display_name": self.display_name,
            "registry_status": self.registry_status,
            "live_status": self.live_status,
            "drift": self.drift,
            "confidence": self.confidence,
            "flags": list(self.flags),
            "checks": [
                {"name": check.name, "status": check.status, "evidence": check.evidence}
                for check in self.checks
            ],
        }


Runner = Callable[[list[str]], CommandResult]


def normalize_capability_id(value: str) -> str:
    text = value.strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return re.sub(r"_+", "_", text)


def _status_from_cell(cell: str) -> str:
    if "partly" in cell.lower() or "\U0001f7e2\U0001f7e1" in cell:
        return "partly_lit"
    for marker, status in STATUS_MARKERS.items():
        if marker in cell:
            return status
    lowered = cell.lower()
    for status in ("lit", "dormant", "broken", "dark", "unknown"):
        if status in lowered:
            return status
    return "unknown"


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _expand_capability_names(name_cell: str) -> list[str]:
    clean = re.sub(r"`([^`]+)`", r"\1", name_cell).strip()
    if " / " not in clean:
        return [clean]
    return [part.strip() for part in clean.split(" / ") if part.strip()]


def parse_capability_registry(markdown_text: str) -> list[CapabilityRecord]:
    records: list[CapabilityRecord] = []
    seen: set[str] = set()
    current_section = ""
    in_capability_table = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            current_section = line.removeprefix("### ").strip()
            in_capability_table = False
            continue

        if line.startswith("| capability | status |"):
            in_capability_table = True
            continue

        if line.startswith("| ---"):
            continue

        if in_capability_table:
            if not line.startswith("|"):
                in_capability_table = False
            else:
                cells = _split_markdown_row(line)
                if len(cells) >= 4:
                    for display_name in _expand_capability_names(cells[0]):
                        capability_id = normalize_capability_id(display_name)
                        if capability_id in seen:
                            continue
                        seen.add(capability_id)
                        records.append(
                            CapabilityRecord(
                                capability_id=capability_id,
                                display_name=display_name,
                                registry_status=_status_from_cell(cells[1]),
                                section=current_section,
                                description=cells[2],
                                light_up=cells[3],
                            )
                        )
                continue

        if current_section.startswith("Personas & Services") and "·" in line:
            for raw_name in line.split("·"):
                display_name = raw_name.strip()
                if not display_name:
                    continue
                capability_id = normalize_capability_id(display_name)
                if capability_id in seen:
                    continue
                seen.add(capability_id)
                records.append(
                    CapabilityRecord(
                        capability_id=capability_id,
                        display_name=display_name,
                        registry_status="lit",
                        section=current_section,
                        description="systemd persona/service listed as lit in registry",
                    )
                )

    return records


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _env_file_has_value(path: Path, var_name: str) -> bool:
    text = _read_text(path)
    if not text:
        return False
    pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(var_name)}\s*=\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return False
    value = match.group(1).strip().strip("'\"")
    return bool(value)


def env_present_check(name: str, env_files: Iterable[Path]) -> CheckResult:
    if os.environ.get(name):
        return CheckResult(name=f"env:{name}", status="pass", evidence="present in process environment")
    present_in = [path.as_posix() for path in env_files if _env_file_has_value(path, name)]
    if present_in:
        return CheckResult(name=f"env:{name}", status="pass", evidence=f"present in {len(present_in)} env file(s)")
    return CheckResult(name=f"env:{name}", status="fail", evidence="not present in configured env sources")


def file_present_check(path: Path, *, nonempty: bool = False) -> CheckResult:
    if not path.exists():
        return CheckResult(name=f"file:{path}", status="fail", evidence="missing")
    if nonempty and path.is_file() and path.stat().st_size == 0:
        return CheckResult(name=f"file:{path}", status="fail", evidence="present but empty")
    if path.is_file():
        size = path.stat().st_size
        evidence = "present"
        if nonempty:
            evidence = f"present and non-empty ({size} bytes)"
        return CheckResult(name=f"file:{path}", status="pass", evidence=evidence)
    return CheckResult(name=f"file:{path}", status="pass", evidence="present")


def file_declares_check(path: Path, *, nonempty: bool = False) -> CheckResult:
    result = file_present_check(path, nonempty=nonempty)
    if result.status == "pass":
        return CheckResult(name=result.name.replace("file:", "declared_file:", 1), status="info", evidence=result.evidence)
    return result


def send_hold_block_check(path: Path = DEFAULT_SEND_HOLD_PATH) -> CheckResult:
    if path.exists():
        return CheckResult(name=f"hold:{path}", status="block", evidence="SEND_HOLD active")
    return CheckResult(name=f"hold:{path}", status="pass", evidence="SEND_HOLD not present")


def source_contains_check(relative_path: str, needle: str) -> CheckResult:
    return source_contains_check_at(ROOT, relative_path, needle)


def source_contains_check_at(root: Path, relative_path: str, needle: str) -> CheckResult:
    path = root / relative_path
    text = _read_text(path)
    if needle in text:
        return CheckResult(name=f"source:{relative_path}", status="pass", evidence=f"found {needle}")
    return CheckResult(name=f"source:{relative_path}", status="fail", evidence=f"missing {needle}")


def source_declares_check(root: Path, relative_path: str, needle: str) -> CheckResult:
    path = root / relative_path
    text = _read_text(path)
    if needle in text:
        return CheckResult(name=f"declared:{relative_path}", status="info", evidence=f"declares {needle}")
    return CheckResult(name=f"declared:{relative_path}", status="fail", evidence=f"missing declaration {needle}")


def env_any_present_check(names: tuple[str, ...], env_files: Iterable[Path]) -> CheckResult:
    passed = [env_present_check(name, env_files) for name in names]
    for result in passed:
        if result.status == "pass":
            return CheckResult(
                name=f"env_any:{','.join(names)}",
                status="pass",
                evidence=f"{result.name.removeprefix('env:')} present",
            )
    return CheckResult(
        name=f"env_any:{','.join(names)}",
        status="fail",
        evidence="none present in configured env sources",
    )


def default_runner(command: list[str]) -> CommandResult:
    completed = subprocess.run(command, capture_output=True, text=True, shell=False, timeout=20)
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout[-2000:],
        stderr=completed.stderr[-2000:],
    )


def systemd_active_check(unit_name: str, runner: Runner) -> CheckResult:
    if shutil.which("systemctl") is None:
        return CheckResult(name=f"systemd:{unit_name}", status="unknown", evidence="systemctl unavailable")
    result = runner(["systemctl", "--user", "is-active", unit_name])
    stdout = result.stdout.strip()
    if result.returncode == 0 and stdout == "active":
        return CheckResult(name=f"systemd:{unit_name}", status="pass", evidence="active")
    if stdout in {"inactive", "failed", "activating", "deactivating"}:
        return CheckResult(name=f"systemd:{unit_name}", status="fail", evidence=stdout)
    evidence = stdout or result.stderr.strip() or f"returncode={result.returncode}"
    return CheckResult(name=f"systemd:{unit_name}", status="unknown", evidence=evidence)


def command_available_check(command_name: str) -> CheckResult:
    path = shutil.which(command_name)
    if path:
        return CheckResult(name=f"command:{command_name}", status="pass", evidence="available on PATH")
    return CheckResult(name=f"command:{command_name}", status="fail", evidence="missing from PATH")


SERVICE_UNITS = {
    "cassandra_briefing_scheduler": "cassandra-briefing-scheduler.service",
    "cassandra_listener": "cassandra-listener.service",
    "cassandra_watcher": "cassandra-watcher.service",
    "cassandra_voice_synthesis": "cassandra-voice-synthesis.service",
    "cassandra_messaging": "cassandra-messaging.service",
    "chief_email_brain": "chief-email-brain.service",
    "chief_memory_worker": "chief-memory-worker.service",
    "chief_state_worker": "chief-state-worker.service",
    "chief_watcher_brain": "chief-watcher-brain.service",
    "chief_worker": "chief-worker.service",
    "chief_guardian_listener": "chief-guardian-listener.service",
    "guardian_output_validation": "guardian-output-validation.service",
    "hermes_gateway": "hermes-gateway.service",
    "niles_notification_service": "niles-notification-service.service",
    "maestro_correspondence_watching": "maestro-correspondence-watching.service",
    "openclaw_request_response": "openclaw-request-response.service",
    "capability_registry": "capability-registry.service",
}


def google_file_checks(live_root: Path) -> tuple[CheckResult, ...]:
    secrets_dir = live_root / ".google-secrets"
    return (
        file_present_check(secrets_dir / "credentials.json", nonempty=True),
        file_present_check(secrets_dir / "token.json", nonempty=True),
    )


def build_checks(
    record: CapabilityRecord,
    *,
    runner: Runner,
    env_files: tuple[Path, ...],
    live_root: Path = DEFAULT_LIVE_ROOT,
) -> tuple[CheckResult, ...]:
    cap = record.capability_id
    if cap in SERVICE_UNITS:
        return (systemd_active_check(SERVICE_UNITS[cap], runner),)

    checks_by_capability: dict[str, tuple[CheckResult, ...]] = {
        "gmail_send": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", "_exec_gmail_send"),
            source_contains_check_at(live_root, "google_access_broker.py", "gmail.compose"),
            source_contains_check_at(live_root, "hitl_action_service.py", "ACTION_TYPE_EXACT_GMAIL_SEND"),
            send_hold_block_check(),
        ),
        "gmail_draft_create": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", "_exec_gmail_draft_create"),
            source_contains_check_at(live_root, "google_access_broker.py", "gmail.compose"),
        ),
        "gmail_read_metadata": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", "gmail.readonly"),
            source_contains_check_at(live_root, "google_access_broker.py", "_exec_gmail_read_metadata"),
        ),
        "gmail_read_body": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", "gmail.readonly"),
            source_contains_check_at(live_root, "google_access_broker.py", "_exec_gmail_read_body"),
            source_contains_check_at(live_root, "pii_vault.py", "redact_text"),
        ),
        "gmail_unread_count": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", "gmail.readonly"),
            source_contains_check_at(live_root, "google_access_broker.py", "_exec_gmail_unread_count"),
        ),
        "google_contacts_read": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", "contacts.readonly"),
            source_contains_check_at(live_root, "google_access_broker.py", "_exec_contacts_read"),
        ),
        "telegram_message_send": (
            env_any_present_check(("CASSANDRA_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"), env_files),
            source_contains_check_at(live_root, "cassandra_sender.py", "send_message"),
            source_contains_check_at(live_root, "operator_action.py", "TELEGRAM_SEND"),
            send_hold_block_check(),
        ),
        "telegram_voice_note_send": (
            env_any_present_check(("CASSANDRA_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"), env_files),
            source_contains_check_at(live_root, "cassandra_sender.py", "send_voice_note"),
            source_contains_check_at(live_root, "operator_action.py", "TELEGRAM_SEND"),
            send_hold_block_check(),
        ),
        "telegram_document_send": (
            env_any_present_check(("CASSANDRA_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"), env_files),
            source_contains_check_at(live_root, "cassandra_sender.py", "send_document"),
            source_contains_check_at(live_root, "operator_action.py", "TELEGRAM_SEND"),
            send_hold_block_check(),
        ),
        "operator_brief_send": (
            env_any_present_check(("CASSANDRA_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"), env_files),
            source_contains_check_at(live_root, "cassandra_sender.py", "send_operator_brief"),
            source_contains_check_at(live_root, "cassandra_briefing_scheduler.py", "send_operator_brief"),
            send_hold_block_check(),
        ),
        "email_reply_bridge": (
            source_contains_check_at(live_root, "maestro_correspondence_watcher.py", "correspondence"),
            source_contains_check_at(live_root, "hitl_action_service.py", "ACTION_TYPE_EXACT_GMAIL_SEND"),
        ),
        "hitl_action_dispatcher": (
            source_contains_check_at(live_root, "hitl_action_service.py", "create_pending_action"),
            source_contains_check_at(live_root, "hitl_action_service.py", "risk_tier_for_action_type"),
        ),
        "google_calendar_read": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", "calendar.read"),
        ),
        "google_calendar_write": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", '"https://www.googleapis.com/auth/calendar"'),
        ),
        "google_calendar_delete": (
            *google_file_checks(live_root),
            source_contains_check_at(live_root, "google_access_broker.py", "calendar.events"),
            source_contains_check_at(live_root, "google_access_broker.py", "_exec_calendar_delete"),
        ),
        "email_send": (
            source_declares_check(live_root, "hitl_action_service.py", '"email_send"'),
            send_hold_block_check(),
        ),
        "sms": (
            env_present_check("TWILIO_ACCOUNT_SID", env_files),
            env_present_check("TWILIO_AUTH_TOKEN", env_files),
            source_declares_check(live_root, "hitl_action_service.py", '"sms"'),
        ),
        "social_post": (
            source_declares_check(live_root, "hitl_action_service.py", '"social_post"'),
        ),
        "file_open": (
            source_declares_check(live_root, "hitl_action_service.py", '"file_open"'),
        ),
        "morning_brief": (
            systemd_active_check("cassandra-briefing-scheduler.service", runner),
            source_contains_check_at(live_root, "cassandra_briefing_brain.py", "protected"),
        ),
        "pii_tokenization_redaction": (
            source_contains_check_at(live_root, "pii_vault.py", "redact_text"),
            source_contains_check_at(live_root, "pii_vault.py", "rehydrate_text"),
        ),
        "privacy_request_readiness_gate1": (
            source_contains_check_at(live_root, "generated/read_models/gate1_privacy_request_readiness_OPERATOR.md", "STRICT_PRIVATE"),
            source_contains_check_at(live_root, "generated/read_models/gate1_privacy_request_readiness_OPERATOR.md", "CONFIDENTIAL"),
        ),
        "steel_thread_radar": (
            source_contains_check_at(live_root, "steel_thread_radar.py", "steel_thread_seed_signals"),
            systemd_active_check("steel-thread-radar.service", runner),
        ),
        "pii_vault_encrypted_store": (
            env_present_check("PII_VAULT_KEY", env_files),
            file_present_check(live_root / ".pii_vault.enc", nonempty=True),
        ),
        "polish_loop": (
            file_present_check(live_root / "polish_loop" / "orchestrator.py"),
            file_present_check(live_root / "polish_loop" / "status.json"),
            systemd_active_check("polish-loop.service", runner),
        ),
        "hermes_agent": (
            systemd_active_check("hermes-gateway.service", runner),
            file_present_check(live_root / "sidecars" / "hermes", nonempty=False),
        ),
        "gbrain": (
            file_present_check(live_root / "sidecars" / "gbrain_upstream", nonempty=False),
            systemd_active_check("gbrain.service", runner),
        ),
        "nemoclaw": (
            file_declares_check(live_root / ".nemoclaw" / "source", nonempty=False),
            systemd_active_check("nemoclaw.service", runner),
        ),
        "openclaw_builder": (
            file_present_check(live_root / "openclaw-builder" / "builder-task.sh"),
        ),
        "openclaw_workspace": (
            file_present_check(live_root / ".openclaw" / "workspace", nonempty=False),
            systemd_active_check("openclaw-workspace.service", runner),
        ),
    }
    if cap in {"financial_transfer", "payment", "bill_pay", "wire_transfer", "invoice_send", "refund", "charge"}:
        return (
            source_declares_check(live_root, "hitl_action_service.py", f'"{cap}"'),
            source_contains_check_at(live_root, "financial_broker.py", cap),
        )
    return checks_by_capability.get(cap, ())


def infer_live_status(record: CapabilityRecord, checks: tuple[CheckResult, ...]) -> tuple[str, str, tuple[str, ...]]:
    if not checks:
        return "unknown", "none", ("no_probe_spec",)
    statuses = {check.status for check in checks if check.status != "info"}
    if not statuses:
        return "unknown", "low", ("declaration_only",)
    if "block" in statuses:
        return "dormant", "medium", ("blocked_by_hold",)
    if record.registry_status == "broken" and "fail" in statuses:
        return "broken", "medium", ("expected_breakage_still_observed",)
    if statuses == {"pass"}:
        return "lit", "high", ()
    if "unknown" in statuses and "fail" not in statuses:
        return "unknown", "low", ("probe_unavailable",)
    if "pass" in statuses and "fail" in statuses:
        return "dormant", "medium", ("partial_live_evidence",)
    if statuses == {"fail"}:
        if record.registry_status == "broken":
            return "broken", "medium", ("expected_breakage_still_observed",)
        return "dark", "medium", ("no_live_evidence",)
    return "unknown", "low", ("mixed_probe_state",)


def probe_record(
    record: CapabilityRecord,
    *,
    runner: Runner,
    env_files: tuple[Path, ...],
    live_root: Path = DEFAULT_LIVE_ROOT,
) -> ProbeOutcome:
    checks = build_checks(record, runner=runner, env_files=env_files, live_root=live_root)
    live_status, confidence, flags = infer_live_status(record, checks)
    drift = (
        live_status in DRIFTING_STATUSES
        and record.registry_status in DRIFTING_STATUSES
        and live_status != record.registry_status
    )
    if drift:
        flags = (*flags, "DRIFT")
    return ProbeOutcome(
        capability_id=record.capability_id,
        display_name=record.display_name,
        registry_status=record.registry_status,
        live_status=live_status,
        drift=drift,
        confidence=confidence,
        checks=checks,
        flags=flags,
    )


def build_report(
    registry_path: Path,
    *,
    runner: Runner = default_runner,
    env_files: tuple[Path, ...] = DEFAULT_ENV_FILES,
    live_root: Path = DEFAULT_LIVE_ROOT,
) -> dict[str, Any]:
    records = parse_capability_registry(registry_path.read_text(encoding="utf-8"))
    outcomes = [
        probe_record(record, runner=runner, env_files=env_files, live_root=live_root)
        for record in records
    ]
    status_counts: dict[str, int] = {}
    for outcome in outcomes:
        status_counts[outcome.live_status] = status_counts.get(outcome.live_status, 0) + 1
    drift = [outcome for outcome in outcomes if outcome.drift]
    return {
        "schema_version": "capability_heartbeat_v0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": registry_path.as_posix(),
        "live_root": live_root.as_posix(),
        "read_only": True,
        "capability_count": len(records),
        "live_status_counts": dict(sorted(status_counts.items())),
        "drift_count": len(drift),
        "drift_capabilities": [outcome.capability_id for outcome in drift],
        "records": [outcome.as_dict() for outcome in outcomes],
        "safety": {
            "service_mutations": False,
            "send_or_dispatch_calls": False,
            "external_writes": False,
            "probe_boundary": "systemctl is-active, local file/env presence, and static source checks only",
        },
    }


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def format_operator(report: dict[str, Any]) -> str:
    lines = [
        "# Capability Heartbeat Report",
        "",
        f"Generated: {report['generated_at']}",
        f"Registry: `{report['registry_path']}`",
        f"Capabilities: {report['capability_count']}",
        f"Drift count: {report['drift_count']}",
        f"Live status counts: {report['live_status_counts']}",
        "",
        "| capability | registry | live | confidence | flags |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in report["records"]:
        flags = ", ".join(record["flags"]) if record["flags"] else "-"
        lines.append(
            f"| {record['display_name']} | {record['registry_status']} | "
            f"{record['live_status']} | {record['confidence']} | {flags} |"
        )
    lines.extend(
        [
            "",
            "Safety: read-only probes only; no send, dispatch, merge, deploy, restart, or service mutation attempted.",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_script_safety() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    unsafe_markers = ["".join(parts) for parts in UNSAFE_RUNTIME_MARKER_PARTS]
    violations = [marker for marker in unsafe_markers if marker in source]
    if violations:
        raise RuntimeError(f"unsafe probe markers present: {violations}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--live-root", type=Path, default=DEFAULT_LIVE_ROOT)
    parser.add_argument("--format", choices=("json", "operator"), default="operator")
    parser.add_argument("--output", type=Path, help="Optional output path. Parent must already exist.")
    parser.add_argument(
        "--env-file",
        action="append",
        type=Path,
        default=[],
        help="Additional env file to check for credential presence. Values are never printed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    validate_script_safety()
    if not args.registry.is_file():
        print(f"missing registry: {args.registry}", file=sys.stderr)
        return 2
    env_files = (*DEFAULT_ENV_FILES, *tuple(args.env_file))
    report = build_report(args.registry, env_files=env_files, live_root=args.live_root)
    rendered = stable_json(report) if args.format == "json" else format_operator(report)
    if args.output:
        if not args.output.parent.exists():
            print(f"missing output parent: {args.output.parent}", file=sys.stderr)
            return 2
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
