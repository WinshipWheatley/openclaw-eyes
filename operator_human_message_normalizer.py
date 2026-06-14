"""Human-first operator message normalization.

The helpers here are intentionally small and local. They make first-class
operator messages resilient to typo-heavy, fragmentary phrasing without turning
natural language into authority to execute protected actions.
"""

from __future__ import annotations

import re


TOKEN_REWRITES = {
    "ablum": "album",
    "albm": "album",
    "attachh": "attach",
    "attch": "attach",
    "calandar": "calendar",
    "calander": "calendar",
    "calndr": "calendar",
    "calendr": "calendar",
    "calender": "calendar",
    "calndar": "calendar",
    "casandra": "cassandra",
    "cassndra": "cassandra",
    "cheif": "chief",
    "confrim": "confirm",
    "confriming": "confirming",
    "cont": "continue",
    "contiue": "continue",
    "contin": "continue",
    "continuw": "continue",
    "daata": "data",
    "dat": "data",
    "emial": "email",
    "emaill": "email",
    "evidnce": "evidence",
    "frm": "from",
    "frum": "from",
    "gamil": "gmail",
    "gmial": "gmail",
    "hapens": "happens",
    "happns": "happens",
    "herms": "hermes",
    "invocie": "invoice",
    "invoce": "invoice",
    "ledgr": "ledger",
    "legeer": "ledger",
    "niels": "niles",
    "nieles": "niles",
    "paied": "paid",
    "payd": "paid",
    "payed": "paid",
    "plz": "please",
    "prof": "proof",
    "proff": "proof",
    "maek": "make",
    "resum": "resume",
    "rom": "room",
    "rm": "room",
    "scedule": "schedule",
    "schedual": "schedule",
    "schedul": "schedule",
    "submitt": "submit",
    "wat": "what",
    "wht": "what",
    "wut": "what",
}

PHRASE_REWRITES = (
    ("data rm", "data room"),
    ("dat room", "data room"),
    ("dataroom", "data room"),
    ("cal event", "calendar event"),
    ("g cal", "google calendar"),
    ("what break", "what broke"),
    ("what brok", "what broke"),
    ("what borke", "what broke"),
)

LOW_SIGNAL_ADDRESS_PREFIXES = {
    "actually",
    "also",
    "anyway",
    "bro",
    "btw",
    "dude",
    "honestly",
    "idk",
    "like",
    "look",
    "nah",
    "no",
    "ok",
    "okay",
    "right",
    "so",
    "uh",
    "umm",
    "well",
    "yeah",
    "yes",
}


def normalize_human_text(text: str) -> str:
    """Return typo-tolerant lower-case text for intent matching."""

    lowered = str(text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    lowered = lowered.replace("?", " ").replace("!", " ")
    rough = " ".join(re.sub(r"[^a-z0-9'$.:_-]+", " ", lowered).split())
    tokens = [TOKEN_REWRITES.get(token, token) for token in rough.split()]
    normalized = " ".join(tokens)
    for before, after in PHRASE_REWRITES:
        normalized = re.sub(rf"\b{re.escape(before)}\b", after, normalized)
    return " ".join(normalized.split())


def is_low_signal_address_prefix(value: str) -> bool:
    """True when a comma-preface is conversational filler, not an agent name."""

    normalized = normalize_human_text(value).strip(" .,:;")
    if normalized in LOW_SIGNAL_ADDRESS_PREFIXES:
        return True
    return normalized.startswith(("ok ", "okay ", "idk ", "yeah ", "so ", "well "))
