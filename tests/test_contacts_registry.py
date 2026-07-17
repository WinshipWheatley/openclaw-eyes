import sqlite3
from pathlib import Path

from contacts_registry import (
    CONTACTS_SCHEMA_VERSION,
    ContactsRegistry,
    answer_contact_question,
    get_contact,
    get_contacts_for_client,
    seed_default_contacts,
)


def test_default_seed_loads_fuller_roster_into_sqlite_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "contacts.sqlite3"
    registry = ContactsRegistry(str(db_path))

    contacts = registry.list_contacts()
    contact_ids = {contact["id"] for contact in contacts}

    assert {
        "glenn-mortoro",
        "draper-carter",
        "ernie-green",
        "nancy-pollack",
        "dane-krich",
        "megan-rivas",
        "lawrence-valcovic",
        "chyna-hardin",
        "sam-getachew",
        "annette-sunga",
        "mike-heuer",
    } <= contact_ids

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        version = conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchone()[0]
        live_links = conn.execute(
            """
            SELECT contact_id
            FROM contact_client_links
            WHERE client_slug = 'live-arts-md'
            ORDER BY contact_id
            """
        ).fetchall()

    assert CONTACTS_SCHEMA_VERSION == 1
    assert {"contacts", "contact_aliases", "contact_emails", "contact_client_links"} <= tables
    assert version == 1
    assert [row[0] for row in live_links] == [
        "dane-krich",
        "draper-carter",
        "ernie-green",
        "live-arts-md-accountant",
        "megan-rivas",
    ]


def test_lookup_by_id_name_alias_and_business_email(tmp_path: Path) -> None:
    registry = ContactsRegistry(str(tmp_path / "contacts.sqlite3"))

    by_id = registry.get_contact("draper-carter")
    by_name = registry.get_contact("Draper Carter")
    by_alias = registry.get_contact("Draper")
    by_email = registry.get_contact("draper@liveartsmd.org")

    assert by_id == by_name == by_alias == by_email
    assert by_id["id"] == "draper-carter"
    assert by_id["name"] == "Draper Carter"
    assert by_id["email"] == "draper.carter@gmail.com"
    assert by_id["emails"] == ("draper.carter@gmail.com", "draper@liveartsmd.org")
    assert by_id["connected_client"] == ("live-arts-md", "st-annes")
    assert by_id["role"] == "St. Anne's primary contact; forwards invoice/payment details to Glen"


def test_lookup_by_secondary_seed_emails(tmp_path: Path) -> None:
    registry = ContactsRegistry(str(tmp_path / "contacts.sqlite3"))

    glenn = registry.get_contact("glennmortoro@gmail.com")
    dane = registry.get_contact("execdir@cysomusic.org")

    assert glenn["id"] == "glenn-mortoro"
    assert glenn["emails"] == ("treasurer@stannes-annapolis.org", "glennmortoro@gmail.com")
    assert dane["id"] == "dane-krich"
    assert dane["emails"] == ("dane@liveartsmd.org", "execdir@cysomusic.org")


def test_get_contacts_for_client_live_arts_returns_human_business_contacts(tmp_path: Path) -> None:
    registry = ContactsRegistry(str(tmp_path / "contacts.sqlite3"))

    contacts = registry.get_contacts_for_client("live-arts-md")
    names = [contact["name"] for contact in contacts]

    assert names == ["Dane Krich", "Draper Carter", "Ernie Green", "Live Arts MD Accountant", "Megan Rivas"]
    assert {contact["id"] for contact in contacts} == {
        "dane-krich",
        "draper-carter",
        "ernie-green",
        "live-arts-md-accountant",
        "megan-rivas",
    }
    assert all("agent" not in alias.lower() for contact in contacts for alias in contact["aliases"])


def test_null_email_placeholder_contact_is_seeded_not_dropped(tmp_path: Path) -> None:
    registry = ContactsRegistry(str(tmp_path / "contacts.sqlite3"))

    ernie = registry.get_contact("ernie-green")

    assert ernie["name"] == "Ernie Green"
    assert ernie["email"] is None
    assert ernie["emails"] == ()
    assert ernie["connected_client"] == ("live-arts-md", "st-annes")


def test_annette_stays_email_unknown_and_nancy_email_is_seeded(tmp_path: Path) -> None:
    registry = ContactsRegistry(str(tmp_path / "contacts.sqlite3"))

    annette = registry.get_contact("Annette")
    nancy = registry.get_contact("Nancy Pollack")

    assert annette["email"] is None
    assert annette["emails"] == ()
    assert annette["connected_client"] == ("capital-hilton",)
    assert "email unknown" in annette["role"].lower()
    assert "needs_operator_review" in annette["role"]
    assert nancy["email"] == "npollack@stannes-annapolis.org"
    assert nancy["connected_client"] == ("st-annes",)


def test_live_arts_accountant_and_reynolds_referrer_have_roles_without_invented_email(tmp_path: Path) -> None:
    registry = ContactsRegistry(str(tmp_path / "contacts.sqlite3"))

    megan = registry.get_contact("Megan Rivas")
    mike = registry.get_contact("Mike Heuer")

    assert megan["name"] == "Megan Rivas"
    assert "accountant" in megan["role"].lower()
    assert "June 2026" in megan["role"]
    assert megan["email"] is None
    assert mike["name"] == "Mike Heuer"
    assert "gig referrer" in mike["role"].lower()
    assert "reynolds" in mike["connected_client"]


def test_contact_question_answers_st_annes_payment_handler_from_registry(tmp_path: Path) -> None:
    db_path = str(tmp_path / "contacts.sqlite3")
    ContactsRegistry(db_path)

    result = answer_contact_question("who handles St Anne's payments?", db_path=db_path)

    assert result["answered"] is True
    assert result["question_class"] == "contacts_whos_who"
    answer = result["answer"]
    assert "Glenn Mortoro" in answer
    assert "invoice payer" in answer
    assert "Draper Carter" in answer
    assert "forwards" in answer.lower()
    assert result["machine_proof"]["contacts_registry_record_found"] is True


def test_contact_question_prefers_named_client_role_match(tmp_path: Path) -> None:
    db_path = str(tmp_path / "contacts.sqlite3")
    ContactsRegistry(db_path)

    result = answer_contact_question("who is the accountant at Live Arts?", db_path=db_path)

    assert result["answered"] is True
    answer = result["answer"]
    assert "Live Arts MD Accountant" in answer
    assert "Accountant@liveartsmd.org" in answer
    assert "accountant" in answer.lower()
    assert "Dane Krich" not in answer
    assert "Draper Carter" not in answer
    assert "Glenn Mortoro" not in answer


def test_operator_confirmed_live_arts_accountant_mailbox_is_seeded(tmp_path: Path) -> None:
    db_path = str(tmp_path / "contacts.sqlite3")
    registry = ContactsRegistry(db_path)

    accountant = registry.get_contact("Accountant@liveartsmd.org")

    assert accountant is not None
    assert accountant["name"] == "Live Arts MD Accountant"
    assert accountant["email"] == "Accountant@liveartsmd.org"
    assert accountant["role"] == "Live Arts invoice accountant"
    assert accountant["connected_clients"] == ("live-arts-md",)


def test_contact_question_named_role_gap_offers_only_named_client_contacts(tmp_path: Path) -> None:
    db_path = str(tmp_path / "contacts.sqlite3")
    ContactsRegistry(db_path)

    result = answer_contact_question("who is the treasurer at Live Arts?", db_path=db_path)

    assert result["answered"] is False
    answer = result["answer"]
    assert "do not have a confirmed treasurer contact for live-arts-md" in answer.lower()
    assert "Known Live Arts MD contacts:" in answer
    assert "Dane Krich" in answer
    assert "Megan Rivas" in answer
    assert "Glenn Mortoro" not in answer
    assert "Nancy Pollack" not in answer


def test_contact_question_for_annette_email_is_honest_gap(tmp_path: Path) -> None:
    db_path = str(tmp_path / "contacts.sqlite3")
    ContactsRegistry(db_path)

    result = answer_contact_question("what is Annette's email?", db_path=db_path)

    assert result["answered"] is False
    assert "I do not have a confirmed email for Annette Sunga" in result["answer"]
    assert "needs operator review" in result["answer"].lower()
    assert "Annette.Sunga@hilton.com" not in result["answer"]


def test_module_level_resolvers_read_seeded_sqlite_store(tmp_path: Path) -> None:
    db_path = str(tmp_path / "contacts.sqlite3")

    seed_default_contacts(db_path)

    assert get_contact("glenn", db_path=db_path)["email"] == "treasurer@stannes-annapolis.org"
    st_annes_names = [contact["name"] for contact in get_contacts_for_client("st_annes", db_path=db_path)]
    assert st_annes_names == ["Draper Carter", "Ernie Green", "Glenn Mortoro", "Nancy Pollack"]
