"""SQLite-backed store for RecurrenceRuleRecord -- append-only, versioned, supersedes-chain.

Task 136a. Consumers (derivation, packets, registries) read ONLY latest-unsuperseded per
(client_ref, event_type) -- a superseded version remains in history (provenance) but
influences nothing. This module never sends, pays, posts, or mutates anything outside its
own table.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from recurrence_rule_record import RecurrenceRuleRecord

DEFAULT_DB_PATH = Path("/home/openclaw/state/recurrence_rules/recurrence_rules.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recurrence_rule_versions (
    rule_version_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    client_ref TEXT NOT NULL,
    event_type TEXT NOT NULL,
    schedule_kind TEXT NOT NULL,
    schedule_day INTEGER NOT NULL,
    stated_as_of TEXT NOT NULL,
    provenance_raw TEXT NOT NULL,
    truth_status TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    supersedes_rule_version_id TEXT,
    terminated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    row_seq INTEGER
);
CREATE INDEX IF NOT EXISTS idx_recurrence_rule_client_event
    ON recurrence_rule_versions(client_ref, event_type);
"""


def _row_to_record(row: sqlite3.Row) -> RecurrenceRuleRecord:
    return RecurrenceRuleRecord(
        rule_id=row["rule_id"],
        rule_version_id=row["rule_version_id"],
        client_ref=row["client_ref"],
        event_type=row["event_type"],
        schedule_kind=row["schedule_kind"],
        schedule_day=row["schedule_day"],
        stated_as_of=row["stated_as_of"],
        provenance_raw=row["provenance_raw"],
        truth_status=row["truth_status"],
        source_ref=row["source_ref"],
        supersedes_rule_version_id=row["supersedes_rule_version_id"],
        terminated=bool(row["terminated"]),
    )


class RecurrenceRuleStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def __enter__(self) -> "RecurrenceRuleStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def append(self, record: RecurrenceRuleRecord) -> None:
        next_seq = (
            self._conn.execute("SELECT COALESCE(MAX(row_seq), 0) + 1 FROM recurrence_rule_versions").fetchone()[0]
        )
        self._conn.execute(
            """INSERT INTO recurrence_rule_versions
               (rule_version_id, rule_id, client_ref, event_type, schedule_kind, schedule_day,
                stated_as_of, provenance_raw, truth_status, source_ref,
                supersedes_rule_version_id, terminated, row_seq)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.rule_version_id,
                record.rule_id,
                record.client_ref,
                record.event_type,
                record.schedule_kind,
                record.schedule_day,
                record.stated_as_of,
                record.provenance_raw,
                record.truth_status,
                record.source_ref,
                record.supersedes_rule_version_id,
                int(record.terminated),
                next_seq,
            ),
        )
        self._conn.commit()

    def latest_unsuperseded_for_client(
        self, client_ref: str, event_type: str
    ) -> RecurrenceRuleRecord | None:
        """The active rule for (client_ref, event_type): the version no OTHER version's
        supersedes_rule_version_id points at. None if never stated, or if the latest version
        is a termination."""
        rows = self._conn.execute(
            "SELECT * FROM recurrence_rule_versions WHERE client_ref = ? AND event_type = ? "
            "ORDER BY row_seq ASC",
            (client_ref, event_type),
        ).fetchall()
        if not rows:
            return None
        superseded_ids = {row["supersedes_rule_version_id"] for row in rows if row["supersedes_rule_version_id"]}
        latest = None
        for row in rows:
            if row["rule_version_id"] not in superseded_ids:
                latest = row
        if latest is None:
            return None
        record = _row_to_record(latest)
        if record.terminated:
            return None
        return record

    def all_versions_for_client(self, client_ref: str) -> list[RecurrenceRuleRecord]:
        rows = self._conn.execute(
            "SELECT * FROM recurrence_rule_versions WHERE client_ref = ? ORDER BY row_seq ASC",
            (client_ref,),
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def all_client_refs(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT client_ref FROM recurrence_rule_versions ORDER BY client_ref ASC"
        ).fetchall()
        return [str(row["client_ref"]) for row in rows]

    def active_rules(self, *, event_type: str | None = None) -> list[RecurrenceRuleRecord]:
        """Every client's latest-unsuperseded, non-terminated rule -- optionally filtered to
        one event_type. Used by derivation: no rule = no derivation, never guess schedules."""
        active: list[RecurrenceRuleRecord] = []
        for client_ref in self.all_client_refs():
            for candidate_event_type in (
                (event_type,) if event_type is not None else sorted({"invoice_send"})
            ):
                record = self.latest_unsuperseded_for_client(client_ref, candidate_event_type)
                if record is not None:
                    active.append(record)
        return active
