"""Notice when Google access dies, before something armed needs it.

The Gmail/Calendar broker holds one shared ``token.json``. When it expires or
is revoked, every capability behind it fails at once — inbox reads, calendar
reads, and ``google.gmail.send``, which is what the armed LAMD monthly
auto-send runs on. Nothing in the fleet watched for that, so the credential
could sit dead until the day something needed it.

This cannot fix it. Re-authorising is an interactive OAuth flow and issuing a
credential is the operator's own act — a floor, not an inconvenience to route
around. What it can do is refuse to let the failure be quiet, and say exactly
what is downstream of it.

Liveness is proved by making the cheapest real read the broker offers, because
a token file that exists and parses can still be revoked server-side. Presence
is not health.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
READ_MODEL_PATH = ROOT / "generated" / "read_models" / "google_credential_health.json"
READ_MODEL_ID = "google_credential_health"

PROBE_AGENT = "cassandra"
PROBE_CAPABILITY = "google.gmail.read.metadata"  # Class A: no approval prompt

STATUS_OK = "GOOGLE_ACCESS_OK"
STATUS_EXPIRED = "GOOGLE_ACCESS_EXPIRED_OR_REVOKED"
STATUS_DEPS_MISSING = "GOOGLE_ACCESS_DEPS_MISSING"
STATUS_NOT_CONFIGURED = "GOOGLE_ACCESS_NOT_CONFIGURED"
STATUS_UNKNOWN = "GOOGLE_ACCESS_UNKNOWN"

REAUTH_COMMAND = "python3 google_access_broker.py --auth"

#: What stops working while this is down. Named so the blast radius is read
#: off the board instead of discovered by an automation on the day it fires.
DOWNSTREAM = (
    {
        "what": "LAMD monthly auto-send",
        "why": "runs on google.gmail.send through this same broker",
        "stake": "money-adjacent: an armed send that silently cannot fire",
        "source_ref": "lamd_monthly_autosend_runner.py",
    },
    {
        "what": "Cassandra inbound watch",
        "why": "reads the inbox to notice an unhappy client",
        "stake": "a client complaint goes unnoticed until it reaches the operator",
        "source_ref": "cassandra_inbound_watch.py",
    },
    {
        "what": "Calendar reads",
        "why": "same token",
        "stake": "scheduling answers go stale or unavailable",
        "source_ref": "google_access_broker.py",
    },
)

_EXPIRY_MARKERS = ("invalid_grant", "expired", "revoked", "could not be loaded", "--auth")
_DEPS_MARKERS = ("missing gmail broker runtime dependencies", "modulenotfound")
_UNCONFIGURED_MARKERS = ("not configured", "credentials.json", "no credentials")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_probe(agent: str, capability: str, params: dict) -> dict:
    from google_access_broker import call

    return call(agent, capability, params)


def classify(error: str) -> str:
    """Map a broker error onto a status. Unrecognised stays UNKNOWN, not OK."""

    lowered = str(error or "").lower()
    if not lowered:
        return STATUS_UNKNOWN
    if any(marker in lowered for marker in _DEPS_MARKERS):
        return STATUS_DEPS_MISSING
    if any(marker in lowered for marker in _UNCONFIGURED_MARKERS):
        return STATUS_NOT_CONFIGURED
    if any(marker in lowered for marker in _EXPIRY_MARKERS):
        return STATUS_EXPIRED
    return STATUS_UNKNOWN


def _remedy(status: str) -> str:
    if status == STATUS_EXPIRED:
        return (
            f"Re-authorise Google access from the terminal: {REAUTH_COMMAND}. "
            "Interactive OAuth — it needs the operator's own browser session, so no "
            "agent can do it."
        )
    if status == STATUS_DEPS_MISSING:
        return (
            "The Google client libraries are missing from the interpreter running this. "
            "Use the runtime interpreter (chief_env) or install them — installation is "
            "the operator's call."
        )
    if status == STATUS_NOT_CONFIGURED:
        return "No OAuth client secret is present. Place credentials.json, then run --auth."
    if status == STATUS_UNKNOWN:
        return "Broker failed for an unrecognised reason. Read the detail before assuming."
    return ""


def check_google_credentials(
    probe: Callable[[str, str, dict], dict] | None = None,
) -> dict[str, Any]:
    """Probe live Google access and report health with its blast radius."""

    caller = probe or _default_probe
    try:
        response = caller(PROBE_AGENT, PROBE_CAPABILITY, {"max_results": 1})
    except Exception as exc:  # a probe that throws is a failed probe, not a pass
        status = classify(str(exc))
        return _result(status, str(exc))

    if response.get("ok"):
        return _result(STATUS_OK, "")
    return _result(classify(str(response.get("error") or "")), str(response.get("error") or ""))


def _result(status: str, detail: str) -> dict[str, Any]:
    healthy = status == STATUS_OK
    return {
        "status": status,
        "healthy": healthy,
        "checked_at": utc_now(),
        "detail": detail,
        "remedy": _remedy(status),
        "probe": f"{PROBE_AGENT}:{PROBE_CAPABILITY}",
        "operator_action_required": not healthy,
        "agent_can_fix": False,
        "agent_cannot_fix_because": (
            "Issuing or refreshing a credential is the operator's own act. An agent "
            "routing around it would be exactly the bypass the floors forbid."
        ),
        "downstream_at_risk": [dict(row) for row in DOWNSTREAM] if not healthy else [],
    }


def build_read_model(health: dict[str, Any] | None = None) -> dict[str, Any]:
    result = health or check_google_credentials()
    return {
        "read_model_id": READ_MODEL_ID,
        "schema_version": f"{READ_MODEL_ID}_v0",
        "generated_at": utc_now(),
        "doctrine": (
            "Presence is not health. A token that exists can still be revoked, so "
            "liveness is proved by a real read. What cannot self-heal must self-report."
        ),
        **result,
        "source_refs": ["google_access_broker.py", "google_credential_health.py"],
    }


def export_read_model(
    health: dict[str, Any] | None = None, path: str | Path | None = None
) -> Path:
    target = Path(path) if path else READ_MODEL_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_read_model(health), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe live Google broker access health.")
    parser.add_argument("--export", action="store_true", help="write the read-model")
    args = parser.parse_args(argv)

    health = check_google_credentials()
    if args.export:
        export_read_model(health)
    print(json.dumps(health, indent=2, sort_keys=True))
    return 0 if health["healthy"] else 1


__all__ = [
    "DOWNSTREAM",
    "PROBE_CAPABILITY",
    "REAUTH_COMMAND",
    "STATUS_DEPS_MISSING",
    "STATUS_EXPIRED",
    "STATUS_NOT_CONFIGURED",
    "STATUS_OK",
    "STATUS_UNKNOWN",
    "build_read_model",
    "check_google_credentials",
    "classify",
    "export_read_model",
]


if __name__ == "__main__":
    raise SystemExit(main())
