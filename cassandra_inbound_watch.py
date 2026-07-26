"""Cassandra notices a client is unhappy without being asked.

The escalation rail already carries a client's words to Chief — but only once
somebody decides to file. That leaves the noticing to whoever happens to read
the mail, which on a bad week is the operator, which is the failure the whole
doctrine exists to prevent.

So this scans the inbox itself, deterministically, and files what it finds.

**No model runs here.** Detection is scoring, not judgement, so an idle scan
costs nothing and wakes nobody. An LM is involved only after something real is
found, and only downstream. This is the "watcher waits, LM wakes on a message"
shape, not a heartbeat.

**It reads only what it is allowed to read.** ``google.gmail.read.metadata`` is
a Class A capability and carries Gmail's own snippet — the client's opening
words, which is what a quote needs. ``google.gmail.read.body`` is Class B and
would put an approval prompt in the path of an unattended scan. So the scan
works from subject and snippet, and every item it files records
``quote_source: gmail_snippet`` so nobody mistakes a preview for the whole
letter. Reading further is a deliberate, gated act and stays that way.

**Precision over recall, with the misses named.** A repair item is only opened
for a sender the contacts registry recognises — a stranger's angry cold email
is not a client repair. Unrecognised senders who *did* read as unhappy are
returned as ``unrecognised`` rather than dropped, so the gap is visible instead
of silent.

**Polling is the exception here, and an honest one.** Gmail has no local file
to watch and push delivery needs Cloud Pub/Sub the fleet does not run. This is
a pure function plus a CLI so an existing scheduled lane can call it; it
deliberately does not add another daemon.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import client_repair_escalation as escalation

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "cassandra" / "inbound_watch_seen.json"
READ_MODEL_PATH = ROOT / "generated" / "read_models" / "cassandra_inbound_watch.json"
READ_MODEL_ID = "cassandra_inbound_watch"

AGENT = "cassandra"
METADATA_CAPABILITY = "google.gmail.read.metadata"
DEFAULT_MAX_RESULTS = 25

#: Never treated as a client. The operator is the captain, not a counterparty.
OPERATOR_ADDRESSES = frozenset({"winshiplive@gmail.com"})

#: Senders that are machinery, not people.
_AUTOMATED_MARKERS = (
    "noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon",
    "postmaster", "notifications@", "notification@", "bounce", "automated",
    "alerts@", "support@github", "calendar-notification",
)

#: How many message ids to remember. Comfortably more than any scan window,
#: small enough that the state file stays trivial.
SEEN_LIMIT = 2_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_seen(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = payload.get("seen_message_ids") if isinstance(payload, dict) else payload
    return [str(row) for row in rows or () if str(row)]


def _save_seen(path: Path, seen: Iterable[str]) -> None:
    rows = list(dict.fromkeys(str(row) for row in seen if str(row)))[-SEEN_LIMIT:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": "cassandra_inbound_watch_seen_v1",
                    "updated_at": utc_now(),
                    "seen_message_ids": rows}, indent=2) + "\n",
        encoding="utf-8",
    )


def is_automated(from_email: str) -> bool:
    address = str(from_email or "").strip().lower()
    return any(marker in address for marker in _AUTOMATED_MARKERS)


def _default_broker_call(agent: str, capability: str, params: dict) -> dict:
    from google_access_broker import call

    return call(agent, capability, params)


def _default_resolve_contact(from_email: str) -> dict[str, Any] | None:
    try:
        from contacts_registry import get_contact

        return get_contact(str(from_email or "").strip())
    except Exception:
        return None


def _client_ref(contact: Mapping[str, Any] | None, from_email: str) -> str:
    """Prefer the counterparty's registered name; fall back to the address."""

    if contact:
        for key in ("client_slug", "name", "display_name"):
            value = str(contact.get(key) or "").strip()
            if value:
                return value
    return str(from_email or "").strip().lower()


def scan_inbound(
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    query: str = "",
    broker_call: Callable[[str, str, dict], dict] | None = None,
    resolve_contact: Callable[[str], Mapping[str, Any] | None] | None = None,
    state_path: str | Path | None = None,
    queue_path: str | Path | None = None,
    dry_run: bool = False,
    test_mode: bool = False,
) -> dict[str, Any]:
    """Scan recent inbox mail and file repair items for unhappy clients.

    ``dry_run`` reports what it would file without filing, so the scan can be
    inspected before it is armed.
    """

    caller = broker_call or _default_broker_call
    resolver = resolve_contact or _default_resolve_contact
    state = Path(state_path) if state_path else STATE_PATH
    seen = _load_seen(state)
    seen_set = set(seen)

    params: dict[str, Any] = {"max_results": max_results}
    if query:
        params["query"] = query
    response = caller(AGENT, METADATA_CAPABILITY, params)

    if not response.get("ok"):
        # The real failure is named. A scan that could not read the inbox is
        # not a scan that found nothing.
        return {
            "status": "INBOUND_SCAN_FAILED",
            "scanned_at": utc_now(),
            "detail": str(response.get("error") or "gmail metadata read failed"),
            "examined": 0,
            "filed": [],
            "unrecognised": [],
            "skipped": [],
        }

    messages = [row for row in (response.get("data") or ()) if isinstance(row, Mapping)]
    filed: list[dict[str, Any]] = []
    unrecognised: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    newly_seen: list[str] = []

    for message in messages:
        message_id = str(message.get("message_id") or "")
        from_email = str(message.get("from_email") or "").strip().lower()
        subject = str(message.get("subject") or "")
        snippet = str(message.get("snippet") or "")

        if message_id and message_id in seen_set:
            continue
        if message_id:
            newly_seen.append(message_id)

        if not from_email or from_email in OPERATOR_ADDRESSES:
            skipped.append({"message_id": message_id, "reason": "operator_or_unknown_sender"})
            continue
        if is_automated(from_email):
            skipped.append({"message_id": message_id, "reason": "automated_sender"})
            continue

        # Gmail's snippet is the client's own opening words, which is exactly
        # what a verbatim quote needs. The subject leads it so a complaint
        # stated in the subject line is not missed.
        text = f"{subject}. {snippet}".strip()
        verdict = escalation.detect_dissatisfaction(text)
        if not verdict["escalate"]:
            skipped.append({"message_id": message_id, "reason": "no_dissatisfaction_signal"})
            continue

        contact = resolver(from_email)
        if not contact:
            unrecognised.append({
                "message_id": message_id,
                "from_email": from_email,
                "severity": verdict["severity"],
                "note": "reads as unhappy but the sender is not a known counterparty",
            })
            continue

        client_ref = _client_ref(contact, from_email)
        what_broke = (
            f"Inbound mail from {client_ref} reads as {verdict['severity']}. "
            f"Subject: {subject!r}. Detected by scan, not yet diagnosed."
        )
        if dry_run:
            filed.append({
                "message_id": message_id,
                "client_ref": client_ref,
                "severity": verdict["severity"],
                "verbatim": verdict["verbatim"],
                "dry_run": True,
            })
            continue

        result = escalation.escalate_from_message(
            client_ref=client_ref,
            client_message=text,
            what_broke=what_broke,
            surface="inbound_email_scan",
            queue_path=queue_path,
            test_mode=test_mode,
        )
        if result.get("filed"):
            item = dict(result["item"])
            item["quote_source"] = "gmail_snippet"
            item["message_id"] = message_id
            filed.append(item)
        else:
            skipped.append({
                "message_id": message_id,
                "reason": result.get("status", "not_filed"),
            })

    if newly_seen and not dry_run:
        _save_seen(state, [*seen, *newly_seen])

    return {
        "status": "INBOUND_SCAN_COMPLETE",
        "scanned_at": utc_now(),
        "detail": "",
        "examined": len(messages),
        "filed": filed,
        "unrecognised": unrecognised,
        "skipped": skipped,
        "quote_source": "gmail_snippet",
        "body_read": False,
        "body_read_note": (
            "Full message bodies are Class B and would put an approval prompt in an "
            "unattended scan. Detection works from subject and snippet by design."
        ),
    }


def build_read_model(scan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "read_model_id": READ_MODEL_ID,
        "schema_version": f"{READ_MODEL_ID}_v0",
        "generated_at": utc_now(),
        "owner": AGENT,
        "doctrine": (
            "Cassandra notices a client is unhappy without being asked, and hands it to "
            "Chief in the client's own words."
        ),
        "status": scan.get("status"),
        "detail": scan.get("detail", ""),
        "examined": scan.get("examined", 0),
        "filed_count": len(scan.get("filed") or ()),
        "unrecognised_count": len(scan.get("unrecognised") or ()),
        "unrecognised": scan.get("unrecognised") or [],
        "quote_source": scan.get("quote_source", ""),
        "body_read": scan.get("body_read", False),
        "body_read_note": scan.get("body_read_note", ""),
        "source_refs": ["cassandra_inbound_watch.py", "client_repair_escalation.py"],
    }


def export_read_model(scan: Mapping[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path) if path else READ_MODEL_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_read_model(scan), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan inbound client mail and escalate dissatisfaction to Chief."
    )
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument("--query", default="", help="optional Gmail search query")
    parser.add_argument("--dry-run", action="store_true", help="report without filing")
    parser.add_argument("--test-mode", action="store_true", help="mark filed items as rehearsal")
    parser.add_argument("--export", action="store_true", help="write the read-model")
    args = parser.parse_args(argv)

    scan = scan_inbound(
        max_results=args.max_results,
        query=args.query,
        dry_run=args.dry_run,
        test_mode=args.test_mode,
    )
    if args.export:
        export_read_model(scan)
        escalation.export_read_model()
    print(json.dumps(scan, indent=2, sort_keys=True, default=str))
    return 0 if scan["status"] == "INBOUND_SCAN_COMPLETE" else 1


__all__ = [
    "AGENT",
    "METADATA_CAPABILITY",
    "OPERATOR_ADDRESSES",
    "READ_MODEL_ID",
    "build_read_model",
    "export_read_model",
    "is_automated",
    "scan_inbound",
]


if __name__ == "__main__":
    raise SystemExit(main())
