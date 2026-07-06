"""Durable canonical business contacts registry.

This module is a local SQLite read/seed layer for known business contacts. It
does not read Gmail, create drafts, send email, post ledgers, move money, or
mutate any production business workflow.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CONTACTS_DB_PATH = "/home/openclaw/state/contacts/contacts.sqlite3"
CONTACTS_SCHEMA_VERSION = 1
DEFAULT_SOURCE_REF = "Operator/to-codex/43-durable-contacts-registry.md"


@dataclass(frozen=True)
class ContactSeed:
    id: str
    name: str
    emails: tuple[str, ...]
    connected_clients: tuple[str, ...]
    role: str
    aliases: tuple[str, ...] = ()
    source_ref: str = DEFAULT_SOURCE_REF


DEFAULT_CONTACT_SEEDS: tuple[ContactSeed, ...] = (
    ContactSeed(
        id="glenn-mortoro",
        name="Glenn Mortoro",
        emails=("treasurer@stannes-annapolis.org", "glennmortoro@gmail.com"),
        connected_clients=("st-annes",),
        role="treasurer/forward-to",
        aliases=("Glen Mortoro", "Glenn", "Glen", "treasurer", "St. Anne's treasurer"),
    ),
    ContactSeed(
        id="draper-carter",
        name="Draper Carter",
        emails=("draper.carter@gmail.com", "draper@liveartsmd.org"),
        connected_clients=("st-annes", "live-arts-md"),
        role="intermediary",
        aliases=("Draper", "Draper Carter", "Draper Live Arts", "Draper St. Anne's"),
    ),
    ContactSeed(
        id="ernie-green",
        name="Ernie Green",
        emails=(),
        connected_clients=("st-annes", "live-arts-md"),
        role="dual-client contact",
        aliases=("Ernie", "Ernie Green", "Earnie", "Earnie Green"),
    ),
    ContactSeed(
        id="nancy-pollack",
        name="Nancy Pollack",
        emails=("npollack@stannes-annapolis.org",),
        connected_clients=("st-annes",),
        role="St. Anne's contact",
        aliases=("Nancy", "Nancy Pollack"),
    ),
    ContactSeed(
        id="dane-krich",
        name="Dane Krich",
        emails=("dane@liveartsmd.org", "execdir@cysomusic.org"),
        connected_clients=("live-arts-md",),
        role="GM",
        aliases=("Dane", "Dane Krich"),
    ),
    ContactSeed(
        id="megan-rivas",
        name="Megan Rivas",
        emails=("megan@mandmstrategic.com",),
        connected_clients=("live-arts-md",),
        role="accountant",
        aliases=("Megan", "Megan Rivas"),
    ),
    ContactSeed(
        id="lawrence-valcovic",
        name="Lawrence Valcovic",
        emails=("lawrencevalcovic@hilton.com",),
        connected_clients=("capital-hilton",),
        role="F&B",
        aliases=("Will", "Will Valcovic", "Lawrence", "Lawrence Valcovic"),
    ),
    ContactSeed(
        id="chyna-hardin",
        name="Chyna Hardin",
        emails=("Chyna.Hardin@hilton.com",),
        connected_clients=("capital-hilton",),
        role="finance",
        aliases=("Chyna", "Chyna Hardin"),
    ),
    ContactSeed(
        id="sam-getachew",
        name="Sam Getachew",
        emails=("Sam.getachew@hilton.com",),
        connected_clients=("capital-hilton",),
        role="bar-mgr",
        aliases=("Sam", "Sam Getachew"),
    ),
    ContactSeed(
        id="annette-sunga",
        name="Annette Sunga",
        emails=("annette.Sunga@hilton.com",),
        connected_clients=("capital-hilton",),
        role="AP-lead",
        aliases=("Annette", "Annette Sunga"),
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _slug_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _clean_text(value).lower()).strip("-")


def _client_slug(value: object) -> str:
    return _slug_key(value)


def _alias_key(value: object) -> str:
    return _slug_key(value)


def _stable_aliases_json(aliases: tuple[str, ...]) -> str:
    return json.dumps(tuple(aliases), ensure_ascii=True, separators=(",", ":"))


class ContactsRegistry:
    """SQLite-backed canonical contacts registry."""

    def __init__(
        self,
        db_path: str = DEFAULT_CONTACTS_DB_PATH,
        *,
        seed: bool = True,
        seed_records: tuple[ContactSeed, ...] = DEFAULT_CONTACT_SEEDS,
    ) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()
        if seed:
            self.seed_contacts(seed_records)

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version     INTEGER PRIMARY KEY,
                    applied_utc TEXT NOT NULL,
                    description TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO schema_migrations (version, applied_utc, description)
                VALUES (?, ?, ?)
                """,
                (
                    CONTACTS_SCHEMA_VERSION,
                    _utc_now_iso(),
                    "contacts registry schema: contacts, emails, aliases, client links",
                ),
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    id                 TEXT PRIMARY KEY,
                    name               TEXT NOT NULL,
                    primary_email      TEXT NULL,
                    role               TEXT NOT NULL,
                    aliases_json       TEXT NOT NULL,
                    source_ref         TEXT NOT NULL,
                    seed_version       INTEGER NOT NULL,
                    updated_at_utc_iso TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contact_emails (
                    contact_id TEXT NOT NULL,
                    email      TEXT NOT NULL,
                    email_key  TEXT NOT NULL,
                    position   INTEGER NOT NULL,
                    PRIMARY KEY (contact_id, email_key),
                    FOREIGN KEY (contact_id) REFERENCES contacts (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_contact_emails_email_key ON contact_emails (email_key)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contact_aliases (
                    contact_id TEXT NOT NULL,
                    alias      TEXT NOT NULL,
                    alias_key  TEXT NOT NULL,
                    position   INTEGER NOT NULL,
                    PRIMARY KEY (contact_id, alias_key),
                    FOREIGN KEY (contact_id) REFERENCES contacts (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_contact_aliases_alias_key ON contact_aliases (alias_key)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contact_client_links (
                    contact_id  TEXT NOT NULL,
                    client_slug TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    PRIMARY KEY (contact_id, client_slug),
                    FOREIGN KEY (contact_id) REFERENCES contacts (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_contact_client_links_client ON contact_client_links (client_slug)"
            )
        finally:
            conn.close()

    def seed_contacts(self, seeds: tuple[ContactSeed, ...] = DEFAULT_CONTACT_SEEDS) -> None:
        conn = self._connect()
        try:
            for seed in seeds:
                contact_id = _slug_key(seed.id)
                name = _clean_text(seed.name)
                if not contact_id or not name:
                    raise ValueError("contact seed id and name are required")
                emails = tuple(_clean_text(email) for email in seed.emails if _clean_text(email))
                clients = tuple(dict.fromkeys(_client_slug(client) for client in seed.connected_clients if _client_slug(client)))
                aliases = tuple(dict.fromkeys(_clean_text(alias) for alias in seed.aliases if _clean_text(alias)))
                primary_email = emails[0] if emails else None

                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO contacts
                            (id, name, primary_email, role, aliases_json, source_ref, seed_version, updated_at_utc_iso)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            contact_id,
                            name,
                            primary_email,
                            _clean_text(seed.role),
                            _stable_aliases_json(aliases),
                            _clean_text(seed.source_ref),
                            CONTACTS_SCHEMA_VERSION,
                            _utc_now_iso(),
                        ),
                    )
                    conn.execute("DELETE FROM contact_emails WHERE contact_id = ?", (contact_id,))
                    conn.execute("DELETE FROM contact_aliases WHERE contact_id = ?", (contact_id,))
                    conn.execute("DELETE FROM contact_client_links WHERE contact_id = ?", (contact_id,))
                    for position, email in enumerate(emails):
                        conn.execute(
                            """
                            INSERT INTO contact_emails (contact_id, email, email_key, position)
                            VALUES (?, ?, ?, ?)
                            """,
                            (contact_id, email, email.lower(), position),
                        )
                    lookup_aliases = (contact_id, name, *aliases)
                    for position, alias in enumerate(dict.fromkeys(lookup_aliases)):
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO contact_aliases (contact_id, alias, alias_key, position)
                            VALUES (?, ?, ?, ?)
                            """,
                            (contact_id, alias, _alias_key(alias), position),
                        )
                    for client_slug in clients:
                        conn.execute(
                            """
                            INSERT INTO contact_client_links (contact_id, client_slug, role)
                            VALUES (?, ?, ?)
                            """,
                            (contact_id, client_slug, _clean_text(seed.role)),
                        )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
        finally:
            conn.close()

    def get_contact(self, query: str) -> dict[str, Any] | None:
        text = _clean_text(query)
        if not text:
            return None
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM contacts WHERE id = ?", (_slug_key(text),)).fetchone()
            if row is None:
                alias = conn.execute(
                    """
                    SELECT contact_id
                    FROM contact_aliases
                    WHERE alias_key = ?
                    ORDER BY position ASC, contact_id ASC
                    LIMIT 1
                    """,
                    (_alias_key(text),),
                ).fetchone()
                if alias is not None:
                    row = conn.execute("SELECT * FROM contacts WHERE id = ?", (alias["contact_id"],)).fetchone()
            if row is None and "@" in text:
                email = conn.execute(
                    """
                    SELECT contact_id
                    FROM contact_emails
                    WHERE email_key = ?
                    ORDER BY position ASC, contact_id ASC
                    LIMIT 1
                    """,
                    (text.lower(),),
                ).fetchone()
                if email is not None:
                    row = conn.execute("SELECT * FROM contacts WHERE id = ?", (email["contact_id"],)).fetchone()
            return self._public_row(conn, row) if row else None
        finally:
            conn.close()

    def get_contacts_for_client(self, client_slug: str) -> list[dict[str, Any]]:
        slug = _client_slug(client_slug)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT contacts.*
                FROM contacts
                JOIN contact_client_links ON contact_client_links.contact_id = contacts.id
                WHERE contact_client_links.client_slug = ?
                ORDER BY contacts.name ASC, contacts.id ASC
                """,
                (slug,),
            ).fetchall()
            return [self._public_row(conn, row) for row in rows]
        finally:
            conn.close()

    def list_contacts(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM contacts ORDER BY name ASC, id ASC").fetchall()
            return [self._public_row(conn, row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _public_row(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        emails = tuple(
            item["email"]
            for item in conn.execute(
                """
                SELECT email
                FROM contact_emails
                WHERE contact_id = ?
                ORDER BY position ASC, email ASC
                """,
                (row["id"],),
            ).fetchall()
        )
        clients = tuple(
            item["client_slug"]
            for item in conn.execute(
                """
                SELECT client_slug
                FROM contact_client_links
                WHERE contact_id = ?
                ORDER BY client_slug ASC
                """,
                (row["id"],),
            ).fetchall()
        )
        aliases = tuple(json.loads(row["aliases_json"]))
        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["primary_email"],
            "emails": emails,
            "connected_client": clients,
            "connected_clients": clients,
            "role": row["role"],
            "aliases": aliases,
            "source_ref": row["source_ref"],
            "schema_version": row["seed_version"],
        }


def seed_default_contacts(db_path: str = DEFAULT_CONTACTS_DB_PATH) -> ContactsRegistry:
    return ContactsRegistry(db_path, seed=True)


def get_contact(query: str, *, db_path: str = DEFAULT_CONTACTS_DB_PATH) -> dict[str, Any] | None:
    return ContactsRegistry(db_path, seed=False).get_contact(query)


def get_contacts_for_client(
    client_slug: str,
    *,
    db_path: str = DEFAULT_CONTACTS_DB_PATH,
) -> list[dict[str, Any]]:
    return ContactsRegistry(db_path, seed=False).get_contacts_for_client(client_slug)


__all__ = [
    "CONTACTS_SCHEMA_VERSION",
    "DEFAULT_CONTACTS_DB_PATH",
    "DEFAULT_CONTACT_SEEDS",
    "ContactSeed",
    "ContactsRegistry",
    "get_contact",
    "get_contacts_for_client",
    "seed_default_contacts",
]
