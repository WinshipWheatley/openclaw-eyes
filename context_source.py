"""Shared ledger-backed context source for OpenClaw packet builders.

The business-ops ledger is the source of truth. This module keeps packet
builders small by returning capped, metadata-safe facts and by attaching an
explicit ledger provenance record to legacy packet facts that still expose
their original read-model source_ref for compatibility.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from business_ops_ledger import resolve_business_ops_ledger_path


LEDGER_SOURCE_OF_TRUTH = "business_ops_ledger"
DEFAULT_FACT_LIMIT = 12
DEFAULT_LEDGER_DRIFT_RECEIPT_PATH = Path(
    "/home/openclaw/.openclaw/business_ops/ledger_runtime_drift_receipts.jsonl"
)
DENY_SENSITIVITY_FRAGMENTS = (
    "secret",
    "credential",
    "token",
    "oauth",
    "password",
    "vault",
    "private_raw",
    "legal_private",
    "finance_private",
    "no_go",
    "max",
)
DENY_PATH_FRAGMENTS = (
    ".env",
    ".chief.env",
    ".google-secrets",
    ".ssh",
    "openclegalprivate",
    "legalprivate",
    "vault",
    "secret",
)


def resolve_ledger_path(db_path: str | Path | None = None) -> Path:
    return Path(resolve_business_ops_ledger_path(db_path)).expanduser()


def ledger_source_ref(db_path: str | Path | None = None) -> str:
    return f"ledger:{resolve_ledger_path(db_path).resolve(strict=False)}"


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_ledger_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _compact(value: Any, *, limit: int = 700) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    return text[: limit - 3].rstrip() + "..." if len(text) > limit else text


def _short_hash(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _sensitivity_allowed(*values: Any) -> bool:
    joined = " ".join(str(v or "") for v in values).lower()
    return not any(fragment in joined for fragment in DENY_SENSITIVITY_FRAGMENTS)


def _path_allowed(*values: Any) -> bool:
    joined = " ".join(str(v or "") for v in values).lower()
    return not any(fragment in joined for fragment in DENY_PATH_FRAGMENTS)


def _allowed_actor(raw_actors: Any, agent_id: str) -> bool:
    if not agent_id:
        return True
    try:
        actors = json.loads(str(raw_actors or "[]"))
    except json.JSONDecodeError:
        actors = []
    if not isinstance(actors, Sequence) or isinstance(actors, (str, bytes)):
        return False
    normalized = {str(actor).lower() for actor in actors}
    return "all" in normalized or agent_id.lower() in normalized


def make_ledger_provenance(
    *,
    source_table: str,
    source_id: str = "",
    source_path: str = "",
    db_path: str | Path | None = None,
    builder_name: str = "",
    projection_source_ref: str = "",
    status: str = "ledger_query",
) -> dict[str, Any]:
    return {
        "source_of_truth": LEDGER_SOURCE_OF_TRUTH,
        "ledger_path": str(resolve_ledger_path(db_path).resolve(strict=False)),
        "source_table": source_table,
        "source_id": source_id,
        "source_path": source_path,
        "builder_name": builder_name,
        "projection_source_ref": projection_source_ref,
        "status": status,
    }


def make_ledger_fact(
    *,
    topic: str,
    label: str,
    value: str,
    source_table: str,
    source_id: str,
    db_path: str | Path | None = None,
    freshness_as_of: str = "",
    pii_tier: str = "PUBLIC",
    source_path: str = "",
) -> dict[str, Any]:
    provenance = make_ledger_provenance(
        source_table=source_table,
        source_id=source_id,
        source_path=source_path,
        db_path=db_path,
    )
    source_ref = f"{ledger_source_ref(db_path)}#{source_table}:{source_id or _short_hash(label, value)}"
    return {
        "fact_id": f"ledger_{topic}:{_short_hash(topic, label, value, source_id)}",
        "topic": topic,
        "label": _compact(label, limit=160),
        "value": _compact(value),
        "provenance": "business_ops_ledger",
        "freshness": {"as_of": freshness_as_of, "source_ref": source_ref},
        "source_ref": source_ref,
        "ledger_source_ref": ledger_source_ref(db_path),
        "ledger_provenance": provenance,
        "pii_tier": str(pii_tier or "PUBLIC").upper(),
    }


def _has_recorded_projection(
    conn: sqlite3.Connection,
    source_ref: str,
) -> bool:
    if not _table_exists(conn, "context_packet_items"):
        return False
    row = conn.execute(
        "SELECT 1 FROM context_packet_items WHERE source_path=? LIMIT 1",
        (source_ref,),
    ).fetchone()
    return row is not None


def annotate_facts_with_ledger_provenance(
    facts: Iterable[Mapping[str, Any]],
    *,
    builder_name: str,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Add ledger provenance metadata without rewriting legacy source_ref values."""
    out: list[dict[str, Any]] = []
    conn: sqlite3.Connection | None = None
    try:
        if resolve_ledger_path(db_path).exists():
            conn = _connect(db_path)
    except sqlite3.Error:
        conn = None

    for index, fact in enumerate(facts):
        item = dict(fact)
        if isinstance(item.get("ledger_provenance"), Mapping):
            out.append(item)
            continue
        source_ref = str(item.get("source_ref") or "")
        projection_recorded = False
        if conn is not None and source_ref:
            try:
                projection_recorded = _has_recorded_projection(conn, source_ref)
            except sqlite3.Error:
                projection_recorded = False
        status = (
            "ledger_recorded_projection"
            if projection_recorded
            else "ledger_packet_context_annotation"
        )
        item["ledger_source_ref"] = ledger_source_ref(db_path)
        item["ledger_provenance"] = make_ledger_provenance(
            source_table="context_packet_items" if projection_recorded else "packet_builder_context",
            source_id=str(item.get("fact_id") or f"{builder_name}:{index}"),
            source_path=source_ref,
            db_path=db_path,
            builder_name=builder_name,
            projection_source_ref=source_ref,
            status=status,
        )
        out.append(item)
    if conn is not None:
        conn.close()
    return out


def fact_has_ledger_provenance(fact: Mapping[str, Any]) -> bool:
    provenance = fact.get("ledger_provenance")
    if not isinstance(provenance, Mapping):
        return False
    if provenance.get("source_of_truth") != LEDGER_SOURCE_OF_TRUTH:
        return False
    if not provenance.get("ledger_path"):
        return False
    return True


def facts_have_ledger_provenance(facts: Iterable[Mapping[str, Any]]) -> bool:
    for fact in facts:
        if not fact_has_ledger_provenance(fact):
            return False
    return True


def source_refs_from_facts(facts: Iterable[Mapping[str, Any]]) -> list[str]:
    refs: list[str] = []
    for fact in facts:
        for key in ("source_ref", "ledger_source_ref"):
            ref = str(fact.get(key) or "")
            if ref and ref not in refs:
                refs.append(ref)
    return refs


def _append_canonical_facts(
    conn: sqlite3.Connection,
    facts: list[dict[str, Any]],
    *,
    agent_id: str,
    db_path: str | Path | None,
    limit: int,
) -> None:
    if len(facts) >= limit or not _table_exists(conn, "canonical_facts"):
        return
    rows = conn.execute(
        """
        SELECT fact_id, source_file, section_heading, fact_text, sensitivity_class,
               allowed_actors, doc_category, ingested_at
        FROM canonical_facts
        ORDER BY COALESCE(ingested_at, '') DESC, fact_id
        LIMIT 60
        """
    ).fetchall()
    for row in rows:
        if len(facts) >= limit:
            return
        if not _allowed_actor(row["allowed_actors"], agent_id):
            continue
        if not _sensitivity_allowed(row["sensitivity_class"], row["source_file"]):
            continue
        facts.append(
            make_ledger_fact(
                topic=str(row["doc_category"] or "canonical_facts"),
                label=str(row["section_heading"] or row["fact_id"]),
                value=str(row["fact_text"] or ""),
                source_table="canonical_facts",
                source_id=str(row["fact_id"]),
                source_path=str(row["source_file"] or ""),
                db_path=db_path,
                freshness_as_of=str(row["ingested_at"] or ""),
                pii_tier="PUBLIC",
            )
        )


def _append_agent_lane_facts(
    conn: sqlite3.Connection,
    facts: list[dict[str, Any]],
    *,
    db_path: str | Path | None,
    limit: int,
) -> None:
    if len(facts) >= limit or not _table_exists(conn, "agent_lanes"):
        return
    rows = conn.execute(
        """
        SELECT agent_id, display_name, lane_id, lane_label, status, authority_level,
               role_summary, updated_at
        FROM agent_lanes
        ORDER BY agent_id
        LIMIT 12
        """
    ).fetchall()
    for row in rows:
        if len(facts) >= limit:
            return
        facts.append(
            make_ledger_fact(
                topic="agent_lanes",
                label=f"{row['display_name'] or row['agent_id']} lane",
                value=(
                    f"{row['agent_id']} is {row['status']} on lane {row['lane_id']} "
                    f"with authority {row['authority_level']}: {row['role_summary']}"
                ),
                source_table="agent_lanes",
                source_id=str(row["agent_id"] or ""),
                db_path=db_path,
                freshness_as_of=str(row["updated_at"] or ""),
            )
        )


def _append_repo_root_facts(
    conn: sqlite3.Connection,
    facts: list[dict[str, Any]],
    *,
    db_path: str | Path | None,
    limit: int,
) -> None:
    if len(facts) >= limit:
        return
    for table in ("corpus_roots", "repo_b_roots", "legacy_repo_intake_roots"):
        if len(facts) >= limit or not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        if table == "corpus_roots" and {"root_id", "absolute_root"}.issubset(cols):
            sql = """
                SELECT root_id AS id, COALESCE(repo_name, root_label, root_id) AS name,
                       absolute_root AS path, COALESCE(canonical_status, status, '') AS status,
                       COALESCE(updated_at, created_at, '') AS updated_at
                FROM corpus_roots
                ORDER BY root_id
                LIMIT 8
            """
        elif table == "repo_b_roots":
            sql = """
                SELECT root_id AS id, COALESCE(source_repo, root_id) AS name,
                       repo_path AS path, canonical_status AS status,
                       observed_at AS updated_at
                FROM repo_b_roots
                ORDER BY root_id
                LIMIT 8
            """
        else:
            sql = """
                SELECT legacy_root_id AS id, COALESCE(repo_name, root_id) AS name,
                       COALESCE(repo_url, root_id) AS path, canonical_status AS status,
                       updated_at
                FROM legacy_repo_intake_roots
                ORDER BY legacy_root_id
                LIMIT 8
            """
        for row in conn.execute(sql).fetchall():
            if len(facts) >= limit:
                return
            if not _path_allowed(row["path"]):
                continue
            facts.append(
                make_ledger_fact(
                    topic="repo_roots",
                    label=f"Repository/root: {row['name']}",
                    value=f"{row['name']} at {row['path']} ({row['status']})",
                    source_table=table,
                    source_id=str(row["id"] or ""),
                    source_path=str(row["path"] or ""),
                    db_path=db_path,
                    freshness_as_of=str(row["updated_at"] or ""),
                )
            )


def _append_corpus_path_facts(
    conn: sqlite3.Connection,
    facts: list[dict[str, Any]],
    *,
    db_path: str | Path | None,
    limit: int,
) -> None:
    if len(facts) >= limit or not _table_exists(conn, "corpus_paths"):
        return
    rows = conn.execute(
        """
        SELECT cp.path_id, cp.relative_path, cp.absolute_path, cp.path_type,
               cp.tracked_status, cp.mtime, cp.sensitivity_label,
               cp.raw_content_eligibility, cp.canonicality,
               csl.sensitivity_label AS joined_sensitivity
        FROM corpus_paths cp
        LEFT JOIN corpus_sensitivity_labels csl ON csl.path_id = cp.path_id
        WHERE cp.path_type='file'
          AND (
            cp.relative_path LIKE '%context_packet.py'
            OR cp.relative_path LIKE '%fact_packet.py'
            OR cp.relative_path LIKE 'polish_loop/%'
            OR cp.relative_path LIKE 'packet_dankness_%'
          )
        ORDER BY COALESCE(cp.mtime, '') DESC, cp.relative_path
        LIMIT 30
        """
    ).fetchall()
    seen: set[str] = set()
    for row in rows:
        if len(facts) >= limit:
            return
        rel = str(row["relative_path"] or "")
        if rel in seen:
            continue
        seen.add(rel)
        if not _path_allowed(rel, row["absolute_path"]):
            continue
        if not _sensitivity_allowed(row["sensitivity_label"], row["joined_sensitivity"]):
            continue
        facts.append(
            make_ledger_fact(
                topic="system_files",
                label=f"Ledger-indexed file: {rel}",
                value=(
                    f"{rel} is indexed in corpus_paths as {row['tracked_status']} "
                    f"with canonicality {row['canonicality'] or 'unknown'}."
                ),
                source_table="corpus_paths",
                source_id=str(row["path_id"] or ""),
                source_path=rel,
                db_path=db_path,
                freshness_as_of=str(row["mtime"] or ""),
            )
        )


def build_ledger_context_facts(
    *,
    question: str = "",
    agent_id: str = "",
    db_path: str | Path | None = None,
    limit: int = DEFAULT_FACT_LIMIT,
) -> list[dict[str, Any]]:
    """Return capped, sensitivity-filtered facts directly from the ledger."""
    del question  # Future selector hook; current query remains deterministic.
    limit = max(0, int(limit))
    if limit == 0:
        return []
    try:
        conn = _connect(db_path)
    except sqlite3.Error:
        return [
            make_ledger_fact(
                topic="ledger_status",
                label="Ledger unavailable",
                value="The business-ops ledger could not be opened; packet facts must fail closed.",
                source_table="ledger_status",
                source_id="unavailable",
                db_path=db_path,
            )
        ]
    facts: list[dict[str, Any]] = []
    try:
        _append_canonical_facts(conn, facts, agent_id=agent_id, db_path=db_path, limit=limit)
        _append_agent_lane_facts(conn, facts, db_path=db_path, limit=limit)
        _append_repo_root_facts(conn, facts, db_path=db_path, limit=limit)
        _append_corpus_path_facts(conn, facts, db_path=db_path, limit=limit)
    except sqlite3.Error:
        # A locked/failing ledger mid-query (live cron folds write while listeners
        # read) must degrade to the same honest fail-closed fact as a failed open,
        # not raise into callers who would then answer from unverified packets.
        return [
            make_ledger_fact(
                topic="ledger_status",
                label="Ledger unavailable",
                value="The business-ops ledger could not be read; packet facts must fail closed.",
                source_table="ledger_status",
                source_id="unavailable",
                db_path=db_path,
            )
        ]
    finally:
        conn.close()
    return facts[:limit]


def build_ledger_context_packet(
    *,
    question: str = "",
    agent_id: str = "",
    db_path: str | Path | None = None,
    limit: int = DEFAULT_FACT_LIMIT,
    packet_id_prefix: str = "ledger_context_packet",
) -> dict[str, Any]:
    facts = build_ledger_context_facts(
        question=question,
        agent_id=agent_id,
        db_path=db_path,
        limit=limit,
    )
    basis = {
        "packet_id_prefix": packet_id_prefix,
        "agent_id": agent_id,
        "question": question,
        "source_refs": source_refs_from_facts(facts),
        "fact_count": len(facts),
    }
    return {
        "schema_version": "ledger_context_source_v0",
        "packet_id": f"{packet_id_prefix}:{_short_hash(basis)}",
        "status": "READY",
        "agent_id": agent_id,
        "question": _compact(question, limit=300),
        "facts": facts,
        "source_refs": source_refs_from_facts(facts),
        "machine_proof": ledger_machine_proof(
            builder_name=packet_id_prefix,
            facts=facts,
            db_path=db_path,
        ),
    }


def ledger_machine_proof(
    *,
    builder_name: str,
    facts: Iterable[Mapping[str, Any]],
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    fact_list = list(facts)
    return {
        "ledger_context_source": "context_source",
        "ledger_source_of_truth": LEDGER_SOURCE_OF_TRUTH,
        "ledger_path": str(resolve_ledger_path(db_path).resolve(strict=False)),
        "builder_name": builder_name,
        "facts_have_ledger_provenance": facts_have_ledger_provenance(fact_list),
        "ledger_annotated_fact_count": len(fact_list),
    }


def _packet_facts(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    values = packet.get("facts")
    if not isinstance(values, list):
        return []
    return [dict(value) for value in values if isinstance(value, Mapping)]


def _receipt_safe_source_refs(packet: Mapping[str, Any], facts: Iterable[Mapping[str, Any]]) -> list[str]:
    refs: list[str] = []
    raw_refs = packet.get("source_refs")
    if isinstance(raw_refs, list):
        refs.extend(str(ref) for ref in raw_refs if ref)
    refs.extend(source_refs_from_facts(facts))
    out: list[str] = []
    for ref in refs:
        if ref and ref not in out:
            out.append(ref)
    return out


def record_ledger_drift_receipt(
    *,
    builder_name: str,
    packet_id: str,
    agent_id: str,
    status: str,
    original_fact_count: int,
    repair_fact_count: int,
    original_source_refs: Sequence[str],
    repair_source_refs: Sequence[str],
    drift_log_path: str | Path = DEFAULT_LEDGER_DRIFT_RECEIPT_PATH,
) -> dict[str, Any]:
    """Append a metadata-only receipt for a runtime ledger grounding repair."""
    receipt = {
        "schema_version": "ledger_runtime_drift_receipt_v0",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "builder_name": builder_name,
        "packet_id": packet_id,
        "agent_id": agent_id,
        "status": status,
        "source_of_truth": LEDGER_SOURCE_OF_TRUTH,
        "original_fact_count": int(original_fact_count),
        "repair_fact_count": int(repair_fact_count),
        "original_source_refs": list(original_source_refs),
        "repair_source_refs": list(repair_source_refs),
    }
    path = Path(drift_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, ensure_ascii=True) + "\n")
    return receipt


def ensure_packet_ledger_grounded(
    packet: Mapping[str, Any],
    *,
    builder_name: str,
    question: str = "",
    agent_id: str = "",
    db_path: str | Path | None = None,
    limit: int = DEFAULT_FACT_LIMIT,
    drift_log_path: str | Path | None = None,
) -> dict[str, Any]:
    """Runtime guard: repair ungrounded packets from the one ledger and flag the drift.

    This is the runtime sibling of the context-packet contract test. A healthy packet is
    returned unchanged. If the active fact set is empty or lacks ledger provenance, the
    active facts are replaced with canonical ledger facts for the same question/agent. The
    ungrounded facts are retained only as metadata counts/ids, so downstream consumers see
    ledger-grounded facts instead of a mixed trusted/untrusted fact set.
    """
    fact_list = _packet_facts(packet)
    if fact_list and facts_have_ledger_provenance(fact_list):
        return dict(packet)

    packet_id = str(packet.get("packet_id") or f"{builder_name}:unknown")
    resolved_agent_id = str(agent_id or packet.get("agent_id") or "")
    resolved_question = str(question or packet.get("question") or "")
    original_source_refs = _receipt_safe_source_refs(packet, fact_list)
    grounded_facts = [dict(fact) for fact in fact_list if fact_has_ledger_provenance(fact)]
    dropped_fact_ids = [
        str(fact.get("fact_id") or "")
        for fact in fact_list
        if not fact_has_ledger_provenance(fact) and fact.get("fact_id")
    ]
    if grounded_facts:
        # Partial repair: keep the already-grounded (topically relevant) facts and
        # drop only the unprovenanced ones. Replacing the whole set with generic
        # ledger rows would trade relevant grounded context for irrelevant facts.
        repair_status = "ledger_runtime_partial_repair"
        repair_facts = grounded_facts
    else:
        repair_status = "ledger_runtime_repair_applied"
        repair_packet = build_ledger_context_packet(
            question=resolved_question,
            agent_id=resolved_agent_id,
            db_path=db_path,
            limit=limit,
            packet_id_prefix=f"{builder_name}_ledger_runtime_repair",
        )
        repair_facts = _packet_facts(repair_packet)
        if not repair_facts:
            repair_facts = [
                make_ledger_fact(
                    topic="ledger_status",
                    label="Ledger returned no eligible context",
                    value=(
                        "The runtime ledger guard fired, but the business-ops ledger returned "
                        "no eligible facts for this question and agent."
                    ),
                    source_table="ledger_status",
                    source_id="no_eligible_context",
                    db_path=db_path,
                )
            ]
    repair_source_refs = source_refs_from_facts(repair_facts)

    receipt = {
        "schema_version": "ledger_runtime_drift_receipt_v0",
        "builder_name": builder_name,
        "packet_id": packet_id,
        "agent_id": resolved_agent_id,
        "status": repair_status,
        "source_of_truth": LEDGER_SOURCE_OF_TRUTH,
        "original_fact_count": len(fact_list),
        "repair_fact_count": len(repair_facts),
        "original_source_refs": original_source_refs,
        "repair_source_refs": repair_source_refs,
        "drift_log_written": False,
    }
    if drift_log_path is not None:
        receipt = record_ledger_drift_receipt(
            builder_name=builder_name,
            packet_id=packet_id,
            agent_id=resolved_agent_id,
            status=repair_status,
            original_fact_count=len(fact_list),
            repair_fact_count=len(repair_facts),
            original_source_refs=original_source_refs,
            repair_source_refs=repair_source_refs,
            drift_log_path=drift_log_path,
        )
        receipt["drift_log_written"] = True

    machine_proof = dict(packet.get("machine_proof") if isinstance(packet.get("machine_proof"), Mapping) else {})
    machine_proof.update(
        ledger_machine_proof(
            builder_name=builder_name,
            facts=repair_facts,
            db_path=db_path,
        )
    )
    machine_proof.update(
        {
            "ledger_runtime_guard_fired": True,
            "ledger_runtime_repair_status": repair_status,
            "original_facts_have_ledger_provenance": facts_have_ledger_provenance(fact_list),
            "original_fact_count": len(fact_list),
            "repair_fact_count": len(repair_facts),
        }
    )

    repaired = dict(packet)
    repaired["facts"] = repair_facts
    repaired["source_refs"] = repair_source_refs
    repaired["machine_proof"] = machine_proof
    repaired["runtime_ledger_guard"] = {
        "status": repair_status,
        "builder_name": builder_name,
        "source_of_truth": LEDGER_SOURCE_OF_TRUTH,
        "original_fact_count": len(fact_list),
        "repair_fact_count": len(repair_facts),
        "original_fact_ids": [str(fact.get("fact_id") or "") for fact in fact_list if fact.get("fact_id")],
        "dropped_fact_ids": dropped_fact_ids,
        "receipt": receipt,
    }
    return repaired


__all__ = [
    "LEDGER_SOURCE_OF_TRUTH",
    "annotate_facts_with_ledger_provenance",
    "build_ledger_context_facts",
    "build_ledger_context_packet",
    "ensure_packet_ledger_grounded",
    "facts_have_ledger_provenance",
    "ledger_machine_proof",
    "ledger_source_ref",
    "make_ledger_fact",
    "make_ledger_provenance",
    "record_ledger_drift_receipt",
    "resolve_ledger_path",
    "source_refs_from_facts",
]
