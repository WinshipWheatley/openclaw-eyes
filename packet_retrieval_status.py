"""An empty packet must say whether it is empty or broken.

Maestro named ``chief_status_rail.json`` as its source and answered ``UNKNOWN``
while that file sat on disk at 30 KB. It was not lying. The canonical-facts loader
documents *"Returns [] gracefully on ANY error (missing file, locked db, etc.)"*
and means it, so a missing ledger, an absent table, a locked database and a query
that genuinely matched nothing all arrive as the same value: ``[]``.

``[]`` therefore means two incompatible things — *retrieval failed* and *there are
no relevant facts* — and no consumer can tell them apart. The agent did the only
honest thing available and said it didn't know. It was being lied to by its own
retrieval layer.

This module makes the difference expressible. ``EMPTY_BY_QUERY`` is the single
status where zero facts is the truth; everything else names a failure that a person
can act on. It also carries the provenance contract: a packet that declares a
``source_ref`` must carry a fact from that source or a named reason why not, because
citing a source you did not read is the packet-layer version of a receipt naming an
artifact that isn't there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "packet_retrieval_status_v1"

OK = "OK"
EMPTY_BY_QUERY = "EMPTY_BY_QUERY"
LEDGER_MISSING = "LEDGER_MISSING"
TABLES_MISSING = "TABLES_MISSING"
QUERY_FAILED = "QUERY_FAILED"
DECODE_FAILED = "DECODE_FAILED"

#: The only two statuses under which zero facts is a true statement about the world.
TRUTHFULLY_EMPTY = frozenset({OK, EMPTY_BY_QUERY})

#: Everything else means the retrieval layer failed and must say so out loud.
FAILURE_STATUSES = frozenset({LEDGER_MISSING, TABLES_MISSING, QUERY_FAILED, DECODE_FAILED})

_HUMAN_REASON = {
    LEDGER_MISSING: "the canonical-facts ledger file was not present",
    TABLES_MISSING: "the ledger exists but its canonical_facts tables are absent",
    QUERY_FAILED: "the ledger could not be queried (locked, corrupt, or schema drift)",
    DECODE_FAILED: "a stored fact could not be decoded",
    EMPTY_BY_QUERY: "the ledger was read successfully and held nothing relevant",
    OK: "",
}


@dataclass
class RetrievalResult:
    """Facts plus the truth about how they were obtained."""

    facts: list[dict[str, Any]] = field(default_factory=list)
    status: str = OK
    detail: str = ""
    source_path: str = ""

    @property
    def failed(self) -> bool:
        return self.status in FAILURE_STATUSES

    @property
    def trustworthy_empty(self) -> bool:
        """True only when zero facts is a fact about the world, not about us."""

        return not self.facts and self.status in TRUTHFULLY_EMPTY

    def human_reason(self) -> str:
        base = _HUMAN_REASON.get(self.status, f"unrecognised retrieval status {self.status}")
        return f"{base} ({self.detail})" if self.detail else base

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "detail": self.detail,
            "source_path": self.source_path,
            "fact_count": len(self.facts),
            "failed": self.failed,
            "human_reason": self.human_reason(),
        }


def failure(status: str, detail: str = "", source_path: str = "") -> RetrievalResult:
    if status not in FAILURE_STATUSES:
        raise ValueError(f"{status} is not a failure status")
    return RetrievalResult(facts=[], status=status, detail=detail, source_path=source_path)


def empty_by_query(source_path: str = "") -> RetrievalResult:
    return RetrievalResult(facts=[], status=EMPTY_BY_QUERY, source_path=source_path)


def ok(facts: Sequence[Mapping[str, Any]], source_path: str = "") -> RetrievalResult:
    rows = [dict(f) for f in facts]
    if not rows:
        # A caller that says OK with nothing to show is asserting the ledger was
        # read and held nothing. Say that explicitly rather than let OK+[] become
        # the new ambiguous value.
        return empty_by_query(source_path)
    return RetrievalResult(facts=rows, status=OK, source_path=source_path)


# ── Provenance contract ──────────────────────────────────────────────────────

MISSING_SOURCE_FACTS = "declared_source_carried_no_facts"


def declared_source_refs(packet: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for key in ("source_refs", "packet_source_refs"):
        value = packet.get(key)
        if isinstance(value, (list, tuple)):
            refs.extend(str(v).strip() for v in value if str(v).strip())
    return tuple(dict.fromkeys(refs))


def facts_by_source(packet: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in packet.get("facts", ()) or ():
        if not isinstance(row, Mapping):
            continue
        ref = str(row.get("source_ref") or "").strip()
        if ref:
            counts[ref] = counts.get(ref, 0) + 1
    return counts


def verify_source_refs(
    packet: Mapping[str, Any],
    *,
    retrieval: RetrievalResult | None = None,
) -> tuple[bool, tuple[dict[str, str], ...]]:
    """Every declared source must have carried a fact, or have a named reason.

    Returns ``(ok, violations)``. A declared-but-empty source is only acceptable
    when the retrieval layer explains itself; otherwise the packet is citing
    something it did not read.
    """

    counts = facts_by_source(packet)
    violations: list[dict[str, str]] = []
    for ref in declared_source_refs(packet):
        if counts.get(ref):
            continue
        if retrieval is not None and retrieval.failed:
            continue  # named reason present; the answer must surface it
        violations.append({
            "source_ref": ref,
            "reason": MISSING_SOURCE_FACTS,
            "detail": ("packet declared this source but carried no fact from it, and "
                       "no retrieval failure explains the absence"),
        })
    return (not violations), tuple(violations)


def provenance_line(packet: Mapping[str, Any]) -> str:
    """The citation a grounded answer must carry. Empty when there is nothing true to say."""

    counts = facts_by_source(packet)
    used = [ref for ref, n in sorted(counts.items()) if n]
    return "Evidence: " + ", ".join(used) if used else ""


def answer_suffix(
    packet: Mapping[str, Any],
    *,
    retrieval: RetrievalResult | None = None,
) -> str:
    """What must be appended to a grounded answer so a refusal is actionable.

    A bare ``UNKNOWN`` is not actionable. ``UNKNOWN — chief_status_rail selected,
    ledger unreadable (TABLES_MISSING)`` tells the operator which lever to pull.
    """

    if retrieval is not None and retrieval.failed:
        declared = declared_source_refs(packet)
        named = declared[0] if declared else (retrieval.source_path or "the ledger")
        return (f"Retrieval failed: {named} selected, but {retrieval.human_reason()}. "
                f"[{retrieval.status}] No answer is possible from this packet.")
    line = provenance_line(packet)
    return line


__all__ = [
    "DECODE_FAILED",
    "EMPTY_BY_QUERY",
    "FAILURE_STATUSES",
    "LEDGER_MISSING",
    "MISSING_SOURCE_FACTS",
    "OK",
    "QUERY_FAILED",
    "RetrievalResult",
    "TABLES_MISSING",
    "TRUTHFULLY_EMPTY",
    "answer_suffix",
    "declared_source_refs",
    "empty_by_query",
    "facts_by_source",
    "failure",
    "ok",
    "provenance_line",
    "verify_source_refs",
]
