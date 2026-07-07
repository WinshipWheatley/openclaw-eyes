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
CONTACTS_109_SOURCE_REF = "Operator/to-codex/109-contacts-registry-complete.md"
CLIENT_SLUG_ALIASES = {
    "st-anne": "st-annes",
    "st-anne-s": "st-annes",
    "st-annes": "st-annes",
    "saint-anne": "st-annes",
    "saint-anne-s": "st-annes",
    "saint-annes": "st-annes",
    "live-arts": "live-arts-md",
    "live-arts-md": "live-arts-md",
    "capital-hilton": "capital-hilton",
    "reynolds": "reynolds",
    "reynolds-tavern": "reynolds",
}


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
        role="St. Anne's treasurer and invoice payer",
        aliases=("Glen Mortoro", "Glenn", "Glen", "treasurer", "St. Anne's treasurer", "St. Anne's payer"),
        source_ref=CONTACTS_109_SOURCE_REF,
    ),
    ContactSeed(
        id="draper-carter",
        name="Draper Carter",
        emails=("draper.carter@gmail.com", "draper@liveartsmd.org"),
        connected_clients=("st-annes", "live-arts-md"),
        role="St. Anne's primary contact; forwards invoice/payment details to Glen",
        aliases=("Draper", "Draper Carter", "Draper Live Arts", "Draper St. Anne's", "St. Anne's primary contact"),
        source_ref=CONTACTS_109_SOURCE_REF,
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
        role="Live Arts primary contact",
        aliases=("Dane", "Dane Krich"),
        source_ref=CONTACTS_109_SOURCE_REF,
    ),
    ContactSeed(
        id="megan-rivas",
        name="Megan Rivas",
        emails=(),
        connected_clients=("live-arts-md",),
        role="Live Arts accountant, new around June 2026; email unknown",
        aliases=("Megan", "Megan Rivas", "Live Arts accountant"),
        source_ref=CONTACTS_109_SOURCE_REF,
    ),
    ContactSeed(
        id="lawrence-valcovic",
        name="Lawrence Valcovic",
        emails=("lawrencevalcovic@hilton.com",),
        connected_clients=("capital-hilton",),
        role="Capital Hilton contact; Will",
        aliases=("Will", "Will Valcovic", "Lawrence", "Lawrence Valcovic"),
        source_ref=CONTACTS_109_SOURCE_REF,
    ),
    ContactSeed(
        id="chyna-hardin",
        name="Chyna Hardin",
        emails=("Chyna.Hardin@hilton.com",),
        connected_clients=("capital-hilton",),
        role="Capital Hilton finance contact",
        aliases=("Chyna", "Chyna Hardin"),
        source_ref=CONTACTS_109_SOURCE_REF,
    ),
    ContactSeed(
        id="sam-getachew",
        name="Sam Getachew",
        emails=("Sam.getachew@hilton.com",),
        connected_clients=("capital-hilton",),
        role="Capital Hilton bar manager",
        aliases=("Sam", "Sam Getachew"),
        source_ref=CONTACTS_109_SOURCE_REF,
    ),
    ContactSeed(
        id="annette-sunga",
        name="Annette Sunga",
        emails=(),
        connected_clients=("capital-hilton",),
        role="Capital Hilton AP contact candidate; email unknown; needs_operator_review",
        aliases=("Annette", "Annette Sunga", "Capital Hilton AP"),
        source_ref=CONTACTS_109_SOURCE_REF,
    ),
    ContactSeed(
        id="mike-heuer",
        name="Mike Heuer",
        emails=(),
        connected_clients=("reynolds",),
        role="gig referrer for Reynolds",
        aliases=("Mike", "Mike Heuer", "Reynolds referrer"),
        source_ref=CONTACTS_109_SOURCE_REF,
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _slug_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _clean_text(value).lower()).strip("-")


def _client_slug(value: object) -> str:
    slug = _slug_key(value)
    return CLIENT_SLUG_ALIASES.get(slug, slug)


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


def client_slugs_for_text(text: str, contacts: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> tuple[str, ...]:
    query_key = f" {_contact_match_key(text)} "
    slugs: list[str] = []
    for contact in contacts:
        clients = contact.get("connected_clients") or contact.get("connected_client") or ()
        if isinstance(clients, str):
            clients = (clients,)
        for client in clients:
            slug = _client_slug(client)
            terms = _client_terms(slug)
            if any(term and f" {term} " in query_key for term in terms) and slug not in slugs:
                slugs.append(slug)
    return tuple(slugs)


def answer_contact_question(question: str, *, db_path: str = DEFAULT_CONTACTS_DB_PATH) -> dict[str, Any]:
    registry = ContactsRegistry(db_path, seed=True)
    contacts = registry.list_contacts()
    named = _named_contact_for_question(question, contacts)
    slugs = client_slugs_for_text(question, contacts)
    proof = {
        "question_class": "contacts_whos_who",
        "contacts_registry_read": True,
        "contacts_registry_ref": f"contacts_registry:{db_path}",
        "contacts_registry_client_slugs": list(slugs),
        "contacts_registry_contact_ids": [],
        "contacts_registry_record_found": False,
        "protected_generate_called": False,
        "external_llm_invoked": False,
    }

    if named is not None and _asks_for_email(question) and not named.get("email"):
        proof["contacts_registry_contact_ids"] = [str(named.get("id") or "")]
        proof["contacts_registry_record_found"] = True
        name = str(named.get("name") or "that contact")
        role = str(named.get("role") or "contact")
        return {
            "answered": False,
            "question_class": "contacts_whos_who",
            "answer": f"I do not have a confirmed email for {name}. Registry role: {role}; needs operator review.",
            "machine_proof": proof,
        }

    if named is not None and _asks_for_email(question) and named.get("email"):
        proof["contacts_registry_contact_ids"] = [str(named.get("id") or "")]
        proof["contacts_registry_record_found"] = True
        return {
            "answered": True,
            "question_class": "contacts_whos_who",
            "answer": f"{named['name']}'s registry email is {named['email']}.",
            "machine_proof": proof,
        }

    if slugs:
        selected: list[dict[str, Any]] = []
        for slug in slugs:
            selected.extend(registry.get_contacts_for_client(slug))
        selected = _dedupe_contacts(selected)
        if _asks_for_payment_handler(question):
            selected = _payment_ranked_contacts(selected)
        if selected:
            proof["contacts_registry_contact_ids"] = [str(contact.get("id") or "") for contact in selected]
            proof["contacts_registry_record_found"] = True
            answer = _contacts_answer_for_client(question, slugs[0], selected)
            return {
                "answered": True,
                "question_class": "contacts_whos_who",
                "answer": answer,
                "machine_proof": proof,
            }

    if named is not None:
        proof["contacts_registry_contact_ids"] = [str(named.get("id") or "")]
        proof["contacts_registry_record_found"] = True
        return {
            "answered": True,
            "question_class": "contacts_whos_who",
            "answer": _format_contact_sentence(named),
            "machine_proof": proof,
        }

    return {
        "answered": False,
        "question_class": "contacts_whos_who",
        "answer": "I do not have a matching contact in the contacts registry.",
        "machine_proof": proof,
    }


def _contact_match_key(value: object) -> str:
    text = re.sub(r"['’]s\b", "", _clean_text(value).lower())
    text = text.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _client_terms(slug: str) -> set[str]:
    base = _client_slug(slug)
    aliases = {base, base.replace("-", " "), base.replace("-", "")}
    if base == "st-annes":
        aliases.update({"st anne", "st annes", "st anne s", "saint anne", "saint annes", "saint anne s"})
    elif base == "live-arts-md":
        aliases.update({"live arts", "live arts md", "live arts maryland"})
    elif base == "capital-hilton":
        aliases.update({"capital hilton", "hilton"})
    elif base == "reynolds":
        aliases.update({"reynolds", "reynolds tavern"})
    return {_contact_match_key(alias) for alias in aliases if alias}


def _contact_terms(contact: Mapping[str, Any]) -> set[str]:
    values = [contact.get("id"), contact.get("name"), *(contact.get("aliases") or ())]
    return {_contact_match_key(value) for value in values if _contact_match_key(value)}


def _named_contact_for_question(question: str, contacts: list[dict[str, Any]]) -> dict[str, Any] | None:
    query_key = f" {_contact_match_key(question)} "
    for contact in contacts:
        if any(term and f" {term} " in query_key for term in _contact_terms(contact)):
            return contact
    return None


def _asks_for_email(question: str) -> bool:
    return bool(re.search(r"\b(email|e-mail|address|contact info)\b", str(question or ""), re.IGNORECASE))


def _asks_for_payment_handler(question: str) -> bool:
    return bool(re.search(r"\b(payments?|payer|invoice|treasurer|handles?|who handles)\b", str(question or ""), re.IGNORECASE))


def _payment_ranked_contacts(contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def score(contact: Mapping[str, Any]) -> tuple[int, str]:
        role = str(contact.get("role") or "").lower()
        if "invoice payer" in role or "treasurer" in role:
            return (0, str(contact.get("name") or ""))
        if "forwards" in role or "primary contact" in role:
            return (1, str(contact.get("name") or ""))
        return (2, str(contact.get("name") or ""))

    return sorted(contacts, key=score)


def _contacts_answer_for_client(question: str, slug: str, contacts: list[dict[str, Any]]) -> str:
    if slug == "st-annes" and _asks_for_payment_handler(question):
        primary = contacts[0]
        forwarder = next((contact for contact in contacts[1:] if "forwards" in str(contact.get("role") or "").lower()), None)
        answer = _format_contact_sentence(primary)
        if forwarder is not None:
            answer += f" {forwarder['name']} is the St. Anne's primary contact and forwards details to Glen."
        return answer
    return " ".join(_format_contact_sentence(contact) for contact in contacts)


def _format_contact_sentence(contact: Mapping[str, Any]) -> str:
    name = str(contact.get("name") or contact.get("id") or "Contact")
    role = str(contact.get("role") or "contact")
    clients = contact.get("connected_clients") or contact.get("connected_client") or ()
    if isinstance(clients, str):
        clients = (clients,)
    client_text = ", ".join(str(client) for client in clients) or "no client link"
    return f"{name}: {role}; client: {client_text}."


def _dedupe_contacts(contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for contact in contacts:
        contact_id = str(contact.get("id") or "")
        if contact_id in seen:
            continue
        seen.add(contact_id)
        deduped.append(contact)
    return deduped


__all__ = [
    "CONTACTS_SCHEMA_VERSION",
    "DEFAULT_CONTACTS_DB_PATH",
    "DEFAULT_CONTACT_SEEDS",
    "ContactSeed",
    "ContactsRegistry",
    "answer_contact_question",
    "client_slugs_for_text",
    "get_contact",
    "get_contacts_for_client",
    "seed_default_contacts",
]
