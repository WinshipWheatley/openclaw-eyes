"""Carry a client's real reaction back to Chief, unsoftened.

Escalation path: ``client → Cassandra → Chief → fixed``. The path that must
never run is ``client → captain-as-developer`` — a fault that reaches the
operator as a surprise has already cost him the chair.

The failure mode this module exists to prevent is not the fault. It is the
*softening*: a client says "this is the third time and I'm done hearing about
your software", and it arrives at Chief as "client would appreciate an
update". Chief then fixes the wrong thing, or nothing, and the operator finds
out later.

So the honesty is **checked, not requested**. ``client_verbatim`` must appear
literally in the client's message. A paraphrase is rejected — there is no
polite way to file one, which is the point. An agent that cannot quote the
client cannot open the ticket.

Filing a repair item is an internal write with no outward effect and no money
attached; it is deliberately ungated so nothing is ever swallowed for want of
an approval. What Chief then *does* about it keeps every gate it already had.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parent
QUEUE_PATH = ROOT / "generated" / "receipts" / "client_repair_queue.jsonl"
READ_MODEL_PATH = ROOT / "generated" / "read_models" / "client_repair_queue.json"
READ_MODEL_ID = "client_repair_queue"
SCHEMA_VERSION = "client_repair_item_v1"

STATUS_FILED = "CLIENT_REPAIR_FILED"
STATUS_REJECTED_PARAPHRASE = "CLIENT_REPAIR_REJECTED_PARAPHRASE"
STATUS_REJECTED_EMPTY = "CLIENT_REPAIR_REJECTED_EMPTY"

#: Who a repair item is addressed to. Chief runs the ship.
OWNER = "chief"
#: Who files it. Cassandra holds the client boundary.
REPORTER = "cassandra"

SEVERITY_ORDER = ("routine", "elevated", "trust_damage")

#: Phrases that mean the client's patience is the thing at stake, not the
#: task. These raise severity because a repair that lands after the trust is
#: gone is not a repair.
_TRUST_DAMAGE = (
    "third time", "again", "still waiting", "every time", "unacceptable",
    "unprofessional", "done hearing", "fed up", "frustrated", "disappointed",
    "not okay", "not ok", "losing confidence", "find someone else",
    "cancel", "refund", "last chance", "keeps happening",
)
_ELEVATED = (
    "delay", "delayed", "late", "missing", "wrong", "incorrect", "confused",
    "unclear", "chase", "chasing", "follow up", "followed up", "no response",
    "haven't heard", "concerned",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize(text: str) -> str:
    """Collapse whitespace and smart punctuation for substring comparison."""

    lowered = str(text or "").lower()
    for fancy, plain in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                         ("—", "-"), ("–", "-")):
        lowered = lowered.replace(fancy, plain)
    return re.sub(r"\s+", " ", lowered).strip()


def is_verbatim(quote: str, source: str) -> bool:
    """True when ``quote`` is literally present in ``source``.

    Whitespace and curly-quote normalization only. Nothing else is forgiven:
    a reworded quote is a paraphrase, and the whole point is that a paraphrase
    cannot be filed as the client's words.
    """

    needle, haystack = _normalize(quote), _normalize(source)
    return bool(needle) and needle in haystack


def assess_severity(client_message: str) -> str:
    """Rate how much of the client's patience is already spent."""

    lowered = _normalize(client_message)
    if any(phrase in lowered for phrase in _TRUST_DAMAGE):
        return "trust_damage"
    if any(phrase in lowered for phrase in _ELEVATED):
        return "elevated"
    return "routine"


def detect_dissatisfaction(client_message: str) -> dict[str, Any]:
    """Decide whether a client message warrants a repair item, and quote it.

    Choosing *which* sentence to hand Chief is the judgement most likely to go
    soft — a model asked to summarise will reach for the politest line in the
    message. So the harness picks instead: the sentence carrying the strongest
    signal wins, verbatim, and it is by construction a real substring of what
    the client wrote.
    """

    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?\n])\s+", str(client_message or ""))
        if part.strip()
    ]
    best: tuple[int, str] = (0, "")
    for sentence in sentences:
        lowered = _normalize(sentence)
        score = 3 * sum(1 for phrase in _TRUST_DAMAGE if phrase in lowered)
        score += sum(1 for phrase in _ELEVATED if phrase in lowered)
        if score > best[0]:
            best = (score, sentence.rstrip())
    severity = assess_severity(client_message)
    return {
        "escalate": bool(best[1]) and severity != "routine",
        "severity": severity,
        "verbatim": best[1],
        "signal_strength": best[0],
    }


def escalate_from_message(
    *,
    client_ref: str,
    client_message: str,
    what_broke: str,
    reporter: str = REPORTER,
    surface: str = "inbound_client_message",
    queue_path: str | Path | None = None,
    test_mode: bool = False,
) -> dict[str, Any]:
    """File a repair item from a raw client message, quoting it for the caller.

    The caller supplies what broke. It does not get to choose how gently the
    client is quoted.
    """

    verdict = detect_dissatisfaction(client_message)
    if not verdict["escalate"]:
        return {
            "status": "NO_ESCALATION_NEEDED",
            "filed": False,
            "detection": verdict,
            "detail": "Nothing in the message reads as dissatisfaction.",
            "remedy": "",
        }
    result = escalate_client_dissatisfaction(
        client_ref=client_ref,
        client_message=client_message,
        client_verbatim=verdict["verbatim"],
        what_broke=what_broke,
        reporter=reporter,
        surface=surface,
        queue_path=queue_path,
        test_mode=test_mode,
    )
    result["detection"] = verdict
    return result


def _item_id(payload: Mapping[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"repair:{hashlib.sha256(blob).hexdigest()[:16]}"


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def escalate_client_dissatisfaction(
    *,
    client_ref: str,
    client_message: str,
    client_verbatim: str,
    what_broke: str,
    reporter: str = REPORTER,
    surface: str = "",
    queue_path: str | Path | None = None,
    test_mode: bool = False,
) -> dict[str, Any]:
    """File a repair item for Chief, carrying the client's own words.

    Returns the item on success, or a rejection explaining what is missing.
    Rejection is never silent: the caller is told exactly why, so it can quote
    properly rather than give up.
    """

    client_ref = str(client_ref or "").strip()
    client_message = str(client_message or "").strip()
    client_verbatim = str(client_verbatim or "").strip()
    what_broke = str(what_broke or "").strip()

    if not (client_ref and client_message and client_verbatim and what_broke):
        missing = [
            name
            for name, value in (
                ("client_ref", client_ref),
                ("client_message", client_message),
                ("client_verbatim", client_verbatim),
                ("what_broke", what_broke),
            )
            if not value
        ]
        return {
            "status": STATUS_REJECTED_EMPTY,
            "filed": False,
            "detail": f"Cannot file a repair item without: {', '.join(missing)}.",
            "remedy": "Quote the client directly and name what actually broke.",
        }

    if not is_verbatim(client_verbatim, client_message):
        return {
            "status": STATUS_REJECTED_PARAPHRASE,
            "filed": False,
            "detail": (
                "client_verbatim is not present in the client's message, so it is a "
                "paraphrase. The escalation was not filed."
            ),
            "remedy": (
                "Paste the client's own sentence. Softening it on the way to Chief is "
                "how a fault reaches the captain as a surprise."
            ),
        }

    severity = assess_severity(client_message)
    core = {
        "schema_version": SCHEMA_VERSION,
        "client_ref": client_ref,
        "client_verbatim": client_verbatim,
        "what_broke": what_broke,
        "severity": severity,
        "surface": surface,
        "reporter": str(reporter or REPORTER).lower(),
        "owner": OWNER,
        "state": "open",
    }
    item = {
        **core,
        "item_id": _item_id(core),
        "filed_at": utc_now(),
        "escalation_path": "client -> cassandra -> chief -> fixed",
        "answer_with": "a repair, not an explanation",
        "captain_involvement": "outcome only — never the debugging",
        "test_mode": bool(test_mode),
    }
    _append_jsonl(Path(queue_path) if queue_path else QUEUE_PATH, item)
    return {"status": STATUS_FILED, "filed": True, "item": item, "detail": "", "remedy": ""}


def escalate_blocked_copy(
    *,
    client_ref: str,
    review: Mapping[str, Any],
    draft_body: str = "",
    queue_path: str | Path | None = None,
    test_mode: bool = False,
) -> dict[str, Any]:
    """File the repair item implied by a blocked client draft.

    When the copy guard catches an excuse on its way out, the fault it was
    about is real and still unfixed. Filing it here is what makes the block a
    self-heal rather than a dead end: the client never sees the excuse, and
    Chief gets the underlying fault without the operator touching it.
    """

    violations = list(review.get("violations") or ())
    if not violations:
        return {"status": "NO_ESCALATION_NEEDED", "filed": False, "detail": "", "remedy": ""}

    first = dict(violations[0])
    sentence = str(first.get("sentence") or "")
    source = draft_body or sentence
    what_broke = (
        f"An outbound draft to {client_ref or 'a client'} tried to explain our own "
        f"{first.get('apparatus') or 'machinery'} to them "
        f"({first.get('phrase')!r}). The send was blocked; the underlying fault is unfixed."
    )
    return escalate_client_dissatisfaction(
        client_ref=client_ref or "unknown_client",
        client_message=source,
        client_verbatim=sentence,
        what_broke=what_broke,
        reporter=REPORTER,
        surface="blocked_client_copy",
        queue_path=queue_path,
        test_mode=test_mode,
    )


def load_queue(queue_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(queue_path) if queue_path else QUEUE_PATH
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def build_read_model(
    queue_path: str | Path | None = None,
    rows: Iterable[Mapping[str, Any]] | None = None,
    include_test: bool = False,
) -> dict[str, Any]:
    """Project the queue onto Chief's board, worst first.

    Rehearsal rows are kept in the queue for audit but stay off the board: a
    board that counts drills as client complaints is lying about how much
    trust is actually at stake. They are counted, never silently dropped.
    """

    items = [dict(row) for row in (rows if rows is not None else load_queue(queue_path))]
    open_items = [row for row in items if str(row.get("state") or "open") == "open"]
    test_items = [row for row in open_items if row.get("test_mode")]
    if not include_test:
        open_items = [row for row in open_items if not row.get("test_mode")]
    open_items.sort(
        key=lambda row: (
            -SEVERITY_ORDER.index(str(row.get("severity") or "routine"))
            if str(row.get("severity") or "routine") in SEVERITY_ORDER
            else 0,
            str(row.get("filed_at") or ""),
        )
    )
    return {
        "read_model_id": READ_MODEL_ID,
        "schema_version": f"{READ_MODEL_ID}_v0",
        "generated_at": utc_now(),
        "owner": OWNER,
        "reporter": REPORTER,
        "doctrine": (
            "Client dissatisfaction reaches Chief in the client's own words. Chief answers "
            "it with a repair, not an explanation. The captain hears the outcome."
        ),
        "escalation_path": "client -> cassandra -> chief -> fixed",
        "never": "client -> captain-as-developer",
        "open_count": len(open_items),
        "trust_damage_count": sum(
            1 for row in open_items if row.get("severity") == "trust_damage"
        ),
        "rehearsal_count": len(test_items),
        "rehearsal_note": (
            "Rehearsal rows are held in the queue for audit and kept off the board."
        ),
        "items": open_items,
        "source_refs": ["client_repair_escalation.py", str(QUEUE_PATH.name)],
    }


def export_read_model(
    queue_path: str | Path | None = None,
    export_path: str | Path | None = None,
) -> Path:
    payload = build_read_model(queue_path)
    target = Path(export_path) if export_path else READ_MODEL_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Client repair escalation queue (Cassandra -> Chief)")
    parser.add_argument("--export", action="store_true", help="rebuild the read-model from the queue")
    args = parser.parse_args(argv)
    if args.export:
        print(export_read_model())
        return 0
    payload = build_read_model()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


__all__ = [
    "OWNER",
    "READ_MODEL_ID",
    "REPORTER",
    "STATUS_FILED",
    "STATUS_REJECTED_EMPTY",
    "STATUS_REJECTED_PARAPHRASE",
    "assess_severity",
    "build_read_model",
    "escalate_blocked_copy",
    "escalate_client_dissatisfaction",
    "export_read_model",
    "is_verbatim",
    "load_queue",
]


if __name__ == "__main__":
    raise SystemExit(main())
