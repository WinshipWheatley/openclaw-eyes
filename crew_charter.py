"""Deliver each agent its post and the crew standing orders, every packet.

The roster read-model (``fleet_crew_roster.json``) is orientation for a human
reading the board. This is the half that makes it bind: it turns the same
file into a small, deterministic packet section so every agent is told, on
every turn, what its post is and which standing orders it is under.

Shaped after :func:`gig_business_doctrine.build_doctrine_delivery` — same
status vocabulary, same freshness-fails-loud posture — because that seam is
proven in the packet engine and a second dialect would be a liability.

Two differences, both deliberate:

* **Always relevant.** Doctrine is question-class gated; a post is not. An
  agent that does not know it is at the client boundary will behave like one.
* **Small on purpose.** This rides in every packet, so it is capped hard.
  ~70 tokens buys the post, the binding orders and the escalation path.

Unavailable is not silent. If the roster cannot be read the delivery reports
``CREW_CHARTER_UNAVAILABLE`` and says so in the packet text, rather than
letting an agent operate with no idea which chair it is in.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
ROSTER_PATH = ROOT / "generated" / "read_models" / "fleet_crew_roster.json"
CANONICAL_PATH = "generated/read_models/fleet_crew_roster.json"
CHARTER_REF = "crew_charter_v1"

STATUS_READY = "READY"
STATUS_UNAVAILABLE = "CREW_CHARTER_UNAVAILABLE"

#: Hard ceiling on the delivered text. The charter rides in *every* packet;
#: it earns its place by staying small.
CHARTER_TEXT_CHARS = 900

UNAVAILABLE_TEXT = (
    "CREW CHARTER UNAVAILABLE: proceed under the floors only — the captain's "
    "direct word for money, external send, delete, install or cutover; never "
    "route around a gate; report what is true rather than inventing it."
)


def _short_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_roster(path: str | Path | None = None) -> dict[str, Any]:
    """Return the roster payload, or ``{}`` if it cannot be read."""

    target = Path(path) if path is not None else ROSTER_PATH
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def officer_for(agent_id: str, roster: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return the roster row for ``agent_id``, or ``{}`` when unlisted."""

    agent = str(agent_id or "").strip().lower()
    payload = roster if roster is not None else load_roster()
    for row in payload.get("crew", ()) or ():
        if isinstance(row, Mapping) and str(row.get("agent_id") or "").lower() == agent:
            return dict(row)
    return {}


def _binding_orders(agent: str, roster: Mapping[str, Any]) -> list[str]:
    """Standing orders that bind this agent.

    An order that names an officer binds that officer first; the rest bind
    everyone. Ordering puts the named ones first so a truncated packet keeps
    the part that is most specifically about the reader.
    """

    orders = [str(row) for row in roster.get("standing_orders", ()) or () if str(row).strip()]
    named = [row for row in orders if agent and agent in row.lower()]
    universal = [row for row in orders if row not in named]
    return [*named, *universal]


def build_charter_delivery(
    *,
    agent_id: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Return this agent's post, binding orders and escalation path."""

    agent = str(agent_id or "").strip().lower()
    roster = load_roster(path)
    officer = officer_for(agent, roster) if roster else {}

    if not roster or not officer:
        return {
            "status": STATUS_UNAVAILABLE,
            "charter_ref": CHARTER_REF,
            "canonical_path": CANONICAL_PATH,
            "agent_id": agent,
            "post": "",
            "standing_orders": [],
            "escalation": {},
            "packet_text": UNAVAILABLE_TEXT,
            "source_ref": "",
            "receipt": {
                "schema_version": "crew_charter_delivery_receipt_v1",
                "receipt_id": f"crew_charter:{_short_hash([agent, 'unavailable'])[:12]}",
                "status": STATUS_UNAVAILABLE,
                "agent_id": agent,
                "roster_loaded": bool(roster),
                "officer_found": bool(officer),
            },
        }

    orders = _binding_orders(agent, roster)
    escalation = dict(roster.get("escalation") or {})
    post = str(officer.get("post") or "")
    callsign = str(officer.get("callsign") or agent.title())

    lines = [f"YOUR POST — {callsign}: {post}."]
    lines.extend(f"- {order}" for order in orders)
    if escalation.get("path"):
        never = str(escalation.get("never") or "")
        lines.append(
            f"ESCALATION: {escalation['path']}"
            + (f" — never {never}." if never else ".")
        )
    text = "\n".join(lines)[:CHARTER_TEXT_CHARS]

    source_ref = f"{CANONICAL_PATH}#{_short_hash(roster)[:16]}"
    return {
        "status": STATUS_READY,
        "charter_ref": CHARTER_REF,
        "canonical_path": CANONICAL_PATH,
        "agent_id": agent,
        "callsign": callsign,
        "post": post,
        "standing_orders": orders,
        "escalation": escalation,
        "packet_text": text,
        "source_ref": source_ref,
        "receipt": {
            "schema_version": "crew_charter_delivery_receipt_v1",
            "receipt_id": f"crew_charter:{_short_hash([agent, text])[:12]}",
            "status": STATUS_READY,
            "agent_id": agent,
            "post": post,
            "order_count": len(orders),
            "source_ref": source_ref,
        },
    }


def charter_fact(delivery: Mapping[str, Any]) -> dict[str, str]:
    """Render a charter delivery as one packet fact."""

    return {
        "fact_id": f"crew_charter:{delivery.get('agent_id') or 'unknown'}",
        "topic": "crew_charter",
        "label": "Your post and standing orders",
        "value": str(delivery.get("packet_text") or ""),
        "provenance": "crew_charter",
        "source_ref": str(delivery.get("source_ref") or CANONICAL_PATH),
        "pii_tier": "INTERNAL",
    }


__all__ = [
    "CANONICAL_PATH",
    "CHARTER_REF",
    "CHARTER_TEXT_CHARS",
    "STATUS_READY",
    "STATUS_UNAVAILABLE",
    "build_charter_delivery",
    "charter_fact",
    "load_roster",
    "officer_for",
]
