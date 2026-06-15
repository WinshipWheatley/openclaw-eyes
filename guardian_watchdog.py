"""Deterministic Guardian watchdog rules.

Guardian detects focus and lane-discipline problems and records alerts. It does
not call LMs, send messages, restart services, or fix state.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from business_ops_ledger import (
    append_event,
    append_operator_explanation,
    append_packet_receipt,
    init_business_ops_ledger,
    resolve_business_ops_ledger_path,
)


DEFAULT_BRIEFING_DIR = Path("/mnt/c/OpenClaw/logs/cassandra_briefings")
DEFAULT_SESSION_STATE_PATH = Path("/home/openclaw/OpenClaw/state/chief_session.json")

DEFAULT_OWNER_BY_WORK = {
    "morning_brief": "cassandra",
    "operator_morning_brief": "cassandra",
    "cassandra_morning_brief": "cassandra",
    "cassandra_operator_brief": "cassandra",
}


@dataclass(frozen=True)
class WatchdogConfig:
    morning_brief_max_age_days: int = 1
    active_session_max_hours: float = 8.0
    owner_by_work: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_OWNER_BY_WORK))


@dataclass(frozen=True)
class WatchdogAlert:
    alert_id: str
    rule_id: str
    severity: str
    summary: str
    subject_ref: str
    observed_at: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WatchdogRunResult:
    alerts: tuple[WatchdogAlert, ...]
    emitted_alert_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "alerts": [alert.to_dict() for alert in self.alerts],
            "emitted_alert_ids": list(self.emitted_alert_ids),
            "alert_count": len(self.alerts),
        }


def _utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsers = (
        datetime.fromisoformat,
        lambda text: datetime.strptime(text, "%Y-%m-%d %H:%M:%S"),
        lambda text: datetime.strptime(text, "%Y-%m-%d"),
    )
    for parser in parsers:
        try:
            return _utc_naive(parser(raw))
        except Exception:
            continue
    return None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _stable_alert_id(rule_id: str, subject_ref: str, observed_at: str, summary: str) -> str:
    digest = hashlib.sha256(
        json.dumps(
            [rule_id, subject_ref, observed_at, summary],
            sort_keys=True,
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"guardian_watchdog:{rule_id}:{digest}"


def _alert(
    *,
    rule_id: str,
    severity: str,
    summary: str,
    subject_ref: str,
    observed_at: datetime,
    details: Mapping[str, Any],
) -> WatchdogAlert:
    observed = _utc_naive(observed_at).isoformat(timespec="seconds")
    return WatchdogAlert(
        alert_id=_stable_alert_id(rule_id, subject_ref, observed, summary),
        rule_id=rule_id,
        severity=severity,
        summary=summary,
        subject_ref=subject_ref,
        observed_at=observed,
        details=dict(details),
    )


def _latest_morning_brief_at(briefing_dir: Path) -> tuple[datetime | None, str]:
    latest: datetime | None = None
    latest_ref = ""
    if not briefing_dir.exists():
        return None, str(briefing_dir)

    for path in sorted(briefing_dir.glob("????-??-??_morning.json")):
        data = _read_json(path)
        candidate = (
            _parse_datetime(data.get("generated_at"))
            or _parse_datetime(data.get("delivered_at"))
            or _parse_datetime(data.get("date"))
        )
        if candidate is None:
            continue
        if latest is None or candidate > latest:
            latest = candidate
            latest_ref = str(path)
    return latest, latest_ref or str(briefing_dir)


def evaluate_morning_brief_rule(
    *,
    briefing_dir: str | Path = DEFAULT_BRIEFING_DIR,
    now: datetime | None = None,
    config: WatchdogConfig | None = None,
) -> WatchdogAlert | None:
    cfg = config or WatchdogConfig()
    current = _utc_naive(now or datetime.now())
    latest, source_ref = _latest_morning_brief_at(Path(briefing_dir))
    threshold_days = max(0, int(cfg.morning_brief_max_age_days))

    if latest is None:
        return _alert(
            rule_id="no_morning_brief_produced",
            severity="warning",
            summary=f"No Cassandra morning brief was found within the configured {threshold_days} day window.",
            subject_ref=str(source_ref),
            observed_at=current,
            details={
                "threshold_days": threshold_days,
                "latest_morning_brief_at": None,
                "guardian_action": "alert_only",
            },
        )

    age_days = (current - latest).total_seconds() / 86400
    if age_days > threshold_days:
        return _alert(
            rule_id="no_morning_brief_produced",
            severity="warning",
            summary=(
                "Cassandra morning brief is stale: "
                f"latest production was {age_days:.2f} days ago."
            ),
            subject_ref=source_ref,
            observed_at=current,
            details={
                "threshold_days": threshold_days,
                "age_days": round(age_days, 4),
                "latest_morning_brief_at": latest.isoformat(timespec="seconds"),
                "guardian_action": "alert_only",
            },
        )
    return None


def _session_is_active(state: Mapping[str, Any]) -> bool:
    workflow_state = state.get("workflow_state")
    workflow = workflow_state if isinstance(workflow_state, Mapping) else {}
    return bool(
        str(state.get("status", "")).lower() == "active"
        or state.get("active_workflow")
        or workflow.get("active") is True
    )


def _session_started_at(state: Mapping[str, Any]) -> datetime | None:
    workflow_state = state.get("workflow_state")
    workflow = workflow_state if isinstance(workflow_state, Mapping) else {}
    for source in (state, workflow):
        for key in (
            "started_at",
            "active_since",
            "created_at",
            "updated_at",
            "last_updated_at",
            "last_activity_at",
        ):
            parsed = _parse_datetime(source.get(key))
            if parsed is not None:
                return parsed
    return None


def evaluate_active_session_rule(
    *,
    session_state: Mapping[str, Any] | None = None,
    session_state_path: str | Path = DEFAULT_SESSION_STATE_PATH,
    now: datetime | None = None,
    config: WatchdogConfig | None = None,
) -> WatchdogAlert | None:
    cfg = config or WatchdogConfig()
    current = _utc_naive(now or datetime.now())
    state = dict(session_state) if session_state is not None else _read_json(Path(session_state_path))
    if not _session_is_active(state):
        return None

    threshold_hours = float(cfg.active_session_max_hours)
    started_at = _session_started_at(state)
    workflow = str(state.get("active_workflow") or state.get("workflow") or "unknown_workflow")
    subject_ref = f"session:{workflow}"
    if started_at is None:
        return _alert(
            rule_id="active_session_missing_started_at",
            severity="warning",
            summary=f"Active session {workflow} has no deterministic start timestamp.",
            subject_ref=subject_ref,
            observed_at=current,
            details={
                "threshold_hours": threshold_hours,
                "active_workflow": workflow,
                "guardian_action": "alert_only",
            },
        )

    age_hours = (current - started_at).total_seconds() / 3600
    if age_hours > threshold_hours:
        return _alert(
            rule_id="active_session_too_old",
            severity="warning",
            summary=f"Active session {workflow} has been active for {age_hours:.2f} hours.",
            subject_ref=subject_ref,
            observed_at=current,
            details={
                "threshold_hours": threshold_hours,
                "age_hours": round(age_hours, 4),
                "started_at": started_at.isoformat(timespec="seconds"),
                "active_workflow": workflow,
                "guardian_action": "alert_only",
            },
        )
    return None


def _normalize_agent(value: object) -> str:
    lower = str(value or "").strip().lower()
    if "niles" in lower:
        return "niles"
    if "cassandra" in lower:
        return "cassandra"
    if "chief" in lower:
        return "chief"
    if "guardian" in lower:
        return "guardian"
    if "hermes" in lower:
        return "hermes"
    return re.sub(r"[^a-z0-9]+", "_", lower).strip("_")


def _work_key(record: Mapping[str, Any]) -> str:
    for key in ("work_type", "artifact_type", "intent_name", "task_ref", "surface", "briefing_type"):
        value = str(record.get(key) or "").strip()
        if value:
            return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return ""


def evaluate_cross_role_rule(
    record: Mapping[str, Any],
    *,
    now: datetime | None = None,
    config: WatchdogConfig | None = None,
) -> WatchdogAlert | None:
    cfg = config or WatchdogConfig()
    work_key = _work_key(record)
    declared_owner = str(record.get("declared_owner") or cfg.owner_by_work.get(work_key, "")).strip()
    observed_author = str(
        record.get("actual_author")
        or record.get("author")
        or record.get("actor_name")
        or record.get("created_by")
        or ""
    ).strip()
    if not work_key or not declared_owner or not observed_author:
        return None

    expected = _normalize_agent(declared_owner)
    observed = _normalize_agent(observed_author)
    if expected == observed:
        return None

    current = _utc_naive(now or datetime.now())
    subject = str(record.get("artifact_ref") or record.get("packet_id") or work_key)
    return _alert(
        rule_id="cross_role_owner_violation",
        severity="warning",
        summary=(
            f"Cross-role ownership mismatch: {work_key} is owned by {expected}, "
            f"but was authored by {observed}."
        ),
        subject_ref=subject,
        observed_at=current,
        details={
            "work_key": work_key,
            "declared_owner": expected,
            "observed_author": observed,
            "raw_declared_owner": declared_owner,
            "raw_observed_author": observed_author,
            "guardian_action": "alert_only",
        },
    )


def evaluate_guardian_watchdog(
    *,
    briefing_dir: str | Path = DEFAULT_BRIEFING_DIR,
    session_state: Mapping[str, Any] | None = None,
    session_state_path: str | Path = DEFAULT_SESSION_STATE_PATH,
    role_records: Sequence[Mapping[str, Any]] = (),
    now: datetime | None = None,
    config: WatchdogConfig | None = None,
) -> tuple[WatchdogAlert, ...]:
    cfg = config or WatchdogConfig()
    current = _utc_naive(now or datetime.now())
    alerts: list[WatchdogAlert] = []

    morning_alert = evaluate_morning_brief_rule(
        briefing_dir=briefing_dir,
        now=current,
        config=cfg,
    )
    if morning_alert:
        alerts.append(morning_alert)

    session_alert = evaluate_active_session_rule(
        session_state=session_state,
        session_state_path=session_state_path,
        now=current,
        config=cfg,
    )
    if session_alert:
        alerts.append(session_alert)

    for record in role_records:
        alert = evaluate_cross_role_rule(record, now=current, config=cfg)
        if alert:
            alerts.append(alert)

    return tuple(alerts)


def emit_alerts_to_ledger(
    alerts: Sequence[WatchdogAlert],
    *,
    db_path: str | Path | None = None,
) -> tuple[str, ...]:
    """Record watchdog alerts as ledger events, packets, and operator explanations."""
    if not alerts:
        return ()

    path = resolve_business_ops_ledger_path(str(db_path) if db_path is not None else None)
    init_business_ops_ledger(path)
    emitted: list[str] = []
    for alert in alerts:
        event_ok = append_event(
            event_id=alert.alert_id,
            event_type="guardian_watchdog_alert",
            actor="guardian",
            operator_visible_summary=alert.summary,
            raw_sensitive_data_stored=False,
            replay_safe=True,
            db_path=path,
        )
        packet_ok = append_packet_receipt(
            {
                "packet_id": alert.alert_id,
                "intent_name": "guardian_watchdog_alert",
                "request_category": alert.rule_id,
                "actor_name": "guardian",
                "execution_authority": False,
                "approval_required": False,
                "approval_tier": None,
                "action_status": "alert_recorded",
                "alert": alert.to_dict(),
                "guardian_action": "alert_only",
                "external_send_performed": False,
                "service_restart_performed": False,
                "state_mutation_performed": False,
            },
            event_id=alert.alert_id,
            db_path=path,
        )
        explanation_ok = append_operator_explanation(
            summary=alert.summary,
            event_id=alert.alert_id,
            packet_id=alert.alert_id,
            safe_for_telegram=True,
            db_path=path,
        )
        if event_ok and packet_ok and explanation_ok:
            emitted.append(alert.alert_id)
    return tuple(emitted)


def run_guardian_watchdog(
    *,
    briefing_dir: str | Path = DEFAULT_BRIEFING_DIR,
    session_state: Mapping[str, Any] | None = None,
    session_state_path: str | Path = DEFAULT_SESSION_STATE_PATH,
    role_records: Sequence[Mapping[str, Any]] = (),
    now: datetime | None = None,
    config: WatchdogConfig | None = None,
    emit: bool = False,
    db_path: str | Path | None = None,
) -> WatchdogRunResult:
    alerts = evaluate_guardian_watchdog(
        briefing_dir=briefing_dir,
        session_state=session_state,
        session_state_path=session_state_path,
        role_records=role_records,
        now=now,
        config=config,
    )
    emitted = emit_alerts_to_ledger(alerts, db_path=db_path) if emit else ()
    return WatchdogRunResult(alerts=alerts, emitted_alert_ids=emitted)


def query_watchdog_alert_packets(db_path: str | Path) -> list[dict[str, Any]]:
    """Small operator-surface helper used by tests and manual inspection."""
    path = resolve_business_ops_ledger_path(str(db_path))
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT packet_id, request_category, action_status, packet_json_safe
                FROM packets
                WHERE intent_name = 'guardian_watchdog_alert'
                ORDER BY packet_id
                """
            ).fetchall()
    except Exception:
        return []
    return [dict(row) for row in rows]


__all__ = [
    "DEFAULT_OWNER_BY_WORK",
    "WatchdogAlert",
    "WatchdogConfig",
    "WatchdogRunResult",
    "emit_alerts_to_ledger",
    "evaluate_active_session_rule",
    "evaluate_cross_role_rule",
    "evaluate_guardian_watchdog",
    "evaluate_morning_brief_rule",
    "query_watchdog_alert_packets",
    "run_guardian_watchdog",
]
