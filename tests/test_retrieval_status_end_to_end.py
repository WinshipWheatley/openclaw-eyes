"""The last hop: loader knows why, packet carries it, bridge sends it, operator reads it.

Every stage of this chain existed and was tested in isolation while the chain itself
was broken — which is exactly why Maestro answered a bare UNKNOWN with its named
source file sitting on disk at 30KB.

One honest limitation, stated rather than worked around: the pytest sandbox blocks a
full ``build_maestro_context_packet`` call, because it deliberately isolates tests
from live operator truth and read models. That guard predates this work (verified by
stash-and-rerun) and is worth keeping. So the builder's own stage is proven here by
the attachment function plus a source assertion on the call site, and the real
end-to-end build is verified outside pytest — see the commit message for that run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent_reply_egress as egress
import maestro_context_packet as mcp
import packet_retrieval_status as prs
import workflow_package_request_consumer as consumer

QUESTION = "What is the current top blocker?"


def _ledger(tmp_path: Path, *, tables: bool) -> Path:
    db = tmp_path / "ledger.sqlite"
    conn = sqlite3.connect(db)
    if tables:
        conn.execute(
            "CREATE TABLE canonical_facts (fact_id TEXT PRIMARY KEY, "
            "temporal_or_doctrine TEXT, doc_category TEXT)"
        )
    else:
        conn.execute("CREATE TABLE unrelated (x TEXT)")
    conn.commit()
    conn.close()
    return db


def _status_for(ledger: Path | str) -> dict:
    status: dict = {}
    mcp._sqlite_canonical_facts(QUESTION, ledger_path=str(ledger), status_out=status)
    return status


# ───────────────────────────────── stage 1: loader status onto the packet

def test_a_real_failure_status_is_attached() -> None:
    packet: dict = {"facts": []}
    mcp.attach_retrieval_status(packet, _status_for("/nowhere/absent.sqlite"))
    assert packet["retrieval_status"]["status"] == prs.LEDGER_MISSING


def test_missing_tables_are_attached(tmp_path: Path) -> None:
    packet: dict = {"facts": []}
    mcp.attach_retrieval_status(packet, _status_for(_ledger(tmp_path, tables=False)))
    assert packet["retrieval_status"]["status"] == prs.TABLES_MISSING


def test_an_honest_empty_is_attached_as_such(tmp_path: Path) -> None:
    """NON-VACUITY: a builder that always reported failure would pass the two above."""

    packet: dict = {"facts": []}
    mcp.attach_retrieval_status(packet, _status_for(_ledger(tmp_path, tables=True)))
    assert packet["retrieval_status"]["status"] == prs.EMPTY_BY_QUERY


@pytest.mark.parametrize("nothing", [None, {}, {"status": ""}, "junk", 42])
def test_nothing_is_attached_when_there_is_nothing_to_report(nothing) -> None:
    """An absent key is what keeps the egress quiet on every ordinary turn."""

    packet: dict = {"facts": []}
    mcp.attach_retrieval_status(packet, nothing)
    assert "retrieval_status" not in packet


def test_the_call_site_actually_threads_status_out() -> None:
    """Deleting the thread breaks this even if every unit test still passes."""

    import inspect

    source = inspect.getsource(mcp)
    assert "status_out=_retrieval_status" in source
    assert "_attach_retrieval_status(packet" in source


# ──────────────────────────── stage 2+3: packet -> bridge -> operator reply

def test_a_failure_survives_bridge_serialization(tmp_path: Path) -> None:
    packet: dict = {"source_refs": ["chief_status_rail.json"], "facts": []}
    mcp.attach_retrieval_status(packet, _status_for(_ledger(tmp_path, tables=False)))

    payload = consumer._grounded_answer_provenance(
        SimpleNamespace(packet=packet), source_text=QUESTION
    )
    assert payload["retrieval_status"]["status"] == prs.TABLES_MISSING
    assert payload["source_refs"] == ["chief_status_rail.json"]


def test_the_operator_reply_names_the_failure_end_to_end(tmp_path: Path) -> None:
    """THE WHOLE CHAIN, from a real loader status to the text a person reads."""

    packet: dict = {"source_refs": ["chief_status_rail.json"], "facts": []}
    mcp.attach_retrieval_status(packet, _status_for(_ledger(tmp_path, tables=False)))
    payload = consumer._grounded_answer_provenance(
        SimpleNamespace(packet=packet), source_text=QUESTION
    )
    reply = egress.finalize_agent_reply("maestro", "UNKNOWN.", payload=payload)

    assert prs.TABLES_MISSING in reply
    assert "chief_status_rail.json" in reply
    assert "No answer is possible" in reply
    assert reply.strip() != "UNKNOWN.", "the operator still got a bare UNKNOWN"


def test_an_honest_empty_produces_no_failure_text_end_to_end(tmp_path: Path) -> None:
    """NON-VACUITY: EMPTY_BY_QUERY stays silent all the way to the operator."""

    packet: dict = {"source_refs": ["cal.json"], "facts": []}
    mcp.attach_retrieval_status(packet, _status_for(_ledger(tmp_path, tables=True)))
    payload = consumer._grounded_answer_provenance(
        SimpleNamespace(packet=packet), source_text=QUESTION
    )
    reply = egress.finalize_agent_reply("maestro", "Nothing to report.", payload=payload)

    assert "Retrieval failed" not in reply
    assert "Nothing to report." in reply
