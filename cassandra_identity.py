"""
cassandra_identity.py

Contact identity resolution for Cassandra.

Loads contact_nicknames.json, normalizes entries, and provides lookup/verification
functions used by cassandra_brain.py, cassandra_listener.py, and tests.

Public API
----------
find_contact_by_nickname(nickname)          — lookup by nickname
is_designated_contact_sender(name, chat_id) — boolean contact check
is_pinned_on_channel(nickname, channel)     — channel pin check
verify_sender_on_channel(name, id, channel) — full channel verification
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

_NICKNAMES_PATH = Path("/home/openclaw/contact_nicknames.json")


def _load_nicknames() -> dict:
    """Load contact_nicknames.json. Returns empty dict on any error."""
    try:
        data = json.loads(_NICKNAMES_PATH.read_text(encoding="utf-8"))
        return {k.lower(): v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


def _normalize_contact_entry(nickname: str, raw: object) -> dict:
    names: set[str] = {nickname.lower()}
    chat_ids: set[str] = set()
    if isinstance(raw, str):
        names.add(raw.lower())
        display_name = raw
    elif isinstance(raw, dict):
        display_name = (
            raw.get("name")
            or raw.get("display_name")
            or raw.get("real_name")
            or nickname
        )
        for key in ("name", "display_name", "real_name", "telegram_name", "sender_name"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                names.add(value.strip().lower())
        for key in ("aliases", "sender_names"):
            values = raw.get(key, [])
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and value.strip():
                        names.add(value.strip().lower())
        for key in ("telegram_chat_id", "chat_id"):
            value = raw.get(key)
            if value not in (None, ""):
                chat_ids.add(str(value))
        values = raw.get("telegram_chat_ids", [])
        if isinstance(values, list):
            for value in values:
                if value not in (None, ""):
                    chat_ids.add(str(value))
    else:
        display_name = nickname
    tier = raw.get("tier", "inner_circle") if isinstance(raw, dict) else "inner_circle"
    response_sla = raw.get("response_sla") if isinstance(raw, dict) else None
    pinned_email = None
    pinned_phone = None
    pinned_whatsapp = None
    if isinstance(raw, dict):
        v = raw.get("pinned_email")
        if isinstance(v, str):
            normalized = v.strip().lower()
            pinned_email = normalized or None
        v = raw.get("pinned_phone")
        pinned_phone = v if isinstance(v, str) else None
        v = raw.get("pinned_whatsapp")
        pinned_whatsapp = v if isinstance(v, str) else None
    return {
        "nickname": nickname,
        "display_name": display_name,
        "sender_names": names,
        "chat_ids": chat_ids,
        "tier": tier,
        "response_sla": response_sla,
        "pinned_email": pinned_email,
        "pinned_phone": pinned_phone,
        "pinned_whatsapp": pinned_whatsapp,
    }


def _normalize_outbound_lookup_text(text: str) -> str:
    normalized = str(text or "").strip().lower()
    normalized = re.sub(r"^\s*my\s+", "", normalized)
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _surname_from_display_name(display_name: str) -> str:
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    parts = [
        re.sub(r"[^a-z]", "", part.lower())
        for part in str(display_name or "").split()
    ]
    parts = [part for part in parts if part and part not in suffixes]
    return parts[-1] if parts else ""


def _outbound_contact_candidates(entry: dict) -> set[str]:
    candidates = {
        _normalize_outbound_lookup_text(entry["nickname"]),
        _normalize_outbound_lookup_text(entry["display_name"]),
    }
    candidates.update(_normalize_outbound_lookup_text(name) for name in entry["sender_names"])

    nickname = entry["nickname"].lower()
    surname = _surname_from_display_name(entry["display_name"])
    if nickname == "mom":
        candidates.update({"mom", "mother"})
        if surname:
            candidates.update({f"mrs {surname}", f"ms {surname}"})
    elif nickname == "dad":
        candidates.update({"dad", "father"})
        if surname:
            candidates.add(f"mr {surname}")

    return {candidate for candidate in candidates if candidate}


def _format_outbound_confirmation_name(candidate: str, fallback: str) -> str:
    words = []
    title_map = {"mr": "Mr.", "mrs": "Mrs.", "ms": "Ms."}
    for word in candidate.split():
        words.append(title_map.get(word, word.capitalize()))
    formatted = " ".join(words).strip()
    return formatted or fallback


def resolve_outbound_contact(name: str) -> dict:
    """Resolve an outbound-recipient phrase against local pinned contacts.

    Returns a dict with:
    - status: exact | fuzzy | ambiguous | not_found
    - email: resolved pinned email or ""
    - display_name: canonical display name or ""
    - nickname: canonical nickname or ""
    - confirmation_name: user-facing resolved label for fuzzy confirmation
    - candidates: list[str] of plausible display names for ambiguous matches
    """
    query = _normalize_outbound_lookup_text(name)
    if not query:
        return {
            "status": "not_found",
            "email": "",
            "display_name": "",
            "nickname": "",
            "confirmation_name": "",
            "candidates": [],
        }

    entries = []
    for nickname, raw in _load_nicknames().items():
        entry = _normalize_contact_entry(nickname, raw)
        if not entry["pinned_email"]:
            continue
        entries.append(entry)

    exact_matches = []
    scored = []
    for entry in entries:
        candidates = _outbound_contact_candidates(entry)
        if query in candidates:
            exact_matches.append(entry)
            continue
        best_candidate = ""
        best_score = 0.0
        for candidate in candidates:
            score = difflib.SequenceMatcher(None, query, candidate).ratio()
            if score > best_score:
                best_score = score
                best_candidate = candidate
        if best_candidate:
            scored.append((best_score, best_candidate, entry))

    if len(exact_matches) == 1:
        match = exact_matches[0]
        return {
            "status": "exact",
            "email": match["pinned_email"],
            "display_name": match["display_name"],
            "nickname": match["nickname"],
            "confirmation_name": match["display_name"],
            "candidates": [],
        }
    if len(exact_matches) > 1:
        return {
            "status": "ambiguous",
            "email": "",
            "display_name": "",
            "nickname": "",
            "confirmation_name": "",
            "candidates": sorted(match["display_name"] for match in exact_matches),
        }

    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return {
            "status": "not_found",
            "email": "",
            "display_name": "",
            "nickname": "",
            "confirmation_name": "",
            "candidates": [],
        }

    top_score, top_candidate, top_entry = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    if top_score >= 0.88 and (top_score - second_score >= 0.08 or second_score < 0.78):
        return {
            "status": "fuzzy",
            "email": top_entry["pinned_email"],
            "display_name": top_entry["display_name"],
            "nickname": top_entry["nickname"],
            "confirmation_name": _format_outbound_confirmation_name(top_candidate, top_entry["display_name"]),
            "candidates": [],
        }

    plausible = []
    for score, _, entry in scored:
        if score >= 0.72 and top_score - score <= 0.08:
            plausible.append(entry["display_name"])
    if len(set(plausible)) > 1:
        return {
            "status": "ambiguous",
            "email": "",
            "display_name": "",
            "nickname": "",
            "confirmation_name": "",
            "candidates": sorted(set(plausible)),
        }

    return {
        "status": "not_found",
        "email": "",
        "display_name": "",
        "nickname": "",
        "confirmation_name": "",
        "candidates": [],
    }


def _find_designated_contact(sender_name: str | None = None, sender_chat_id: object | None = None) -> dict | None:
    name_key = sender_name.strip().lower() if isinstance(sender_name, str) and sender_name.strip() else ""
    chat_key = str(sender_chat_id) if sender_chat_id not in (None, "") else ""
    for nickname, raw in _load_nicknames().items():
        entry = _normalize_contact_entry(nickname, raw)
        if name_key and name_key in entry["sender_names"]:
            return entry
        if chat_key and chat_key in entry["chat_ids"]:
            return entry
    return None


def find_contact_by_nickname(nickname: str) -> dict | None:
    """Finds a contact by its nickname, case-insensitive."""
    norm_nickname = nickname.lower()
    data = _load_nicknames()
    if norm_nickname in data:
        return _normalize_contact_entry(norm_nickname, data[norm_nickname])
    return None


def is_designated_contact_sender(
sender_name: str | None = None, sender_chat_id: object | None = None) -> bool:
    return _find_designated_contact(sender_name=sender_name, sender_chat_id=sender_chat_id) is not None


def _find_designated_contact_by_channel_id(channel: str, sender_id: str | None) -> dict | None:
    if sender_id in (None, ""):
        return None
    normalized_id = str(sender_id).strip()
    if channel == "email":
        normalized_id = normalized_id.lower()
    for nickname, raw in _load_nicknames().items():
        entry = _normalize_contact_entry(nickname, raw)
        if channel == "email" and entry["pinned_email"] == normalized_id:
            return entry
        if channel in ("sms", "phone") and entry["pinned_phone"] == normalized_id:
            return entry
        if channel == "whatsapp" and entry["pinned_whatsapp"] == normalized_id:
            return entry
    return None


def is_pinned_on_channel(nickname: str, channel: str) -> bool:
    """Check if a contact has a verified identity pin on the given channel.

    Args:
        nickname: Contact nickname (e.g., 'dad', 'mom', 'draper')
        channel: One of 'telegram', 'email', 'sms', 'phone', 'whatsapp'

    Returns:
        True if the contact has a non-null pin for this channel.
    """
    raw = _load_nicknames().get(nickname.lower())
    if raw is None:
        return False
    entry = _normalize_contact_entry(nickname.lower(), raw)
    if channel == "telegram":
        return bool(entry["chat_ids"])
    elif channel == "email":
        return entry["pinned_email"] is not None
    elif channel in ("sms", "phone"):
        return entry["pinned_phone"] is not None
    elif channel == "whatsapp":
        return entry["pinned_whatsapp"] is not None
    return False


def verify_sender_on_channel(
    sender_name: str | None,
    sender_id: str | None,
    channel: str,
) -> dict | None:
    """Find and verify a designated contact on the specified channel.

    Returns the contact entry if:
    - The sender matches a designated contact (by name or channel-specific ID)
    - AND the contact is pinned on this channel

    Returns None if:
    - No matching contact found
    - Contact found by name but NOT pinned on this channel (identity unverified)
    - sender_id is provided and does not match the stored pin value

    Callers must refuse to act when this returns None for a recognized name.
    """
    if channel == "telegram":
        contact = _find_designated_contact(sender_name=sender_name, sender_chat_id=sender_id)
        if contact is None:
            return None
        if not contact["chat_ids"]:
            return None
        if not sender_id or str(sender_id) not in contact["chat_ids"]:
            return None
        return contact

    contact = _find_designated_contact_by_channel_id(channel, sender_id)
    if contact is not None:
        return contact

    contact = _find_designated_contact(sender_name=sender_name, sender_chat_id=None)
    if contact is None:
        return None

    nickname = contact["nickname"]
    if not is_pinned_on_channel(nickname, channel):
        return None

    # For non-Telegram channels, also verify sender_id matches the stored pin
    if sender_id:
        if channel == "email":
            normalized_sender = sender_id.strip().lower()
            if contact["pinned_email"] and normalized_sender != contact["pinned_email"]:
                return None
        elif channel in ("sms", "phone"):
            if contact["pinned_phone"] and sender_id != contact["pinned_phone"]:
                return None
        elif channel == "whatsapp":
            if contact["pinned_whatsapp"] and sender_id != contact["pinned_whatsapp"]:
                return None

    return contact
