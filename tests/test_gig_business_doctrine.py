from __future__ import annotations

import sqlite3
from pathlib import Path


DOCTRINE_PATH = Path("docs/doctrine/GIG_BUSINESS_DOCTRINE.md")


def test_canonical_contract_registers_v12_as_never_stale_only_source() -> None:
    from gig_business_doctrine import load_gig_business_doctrine

    contract = load_gig_business_doctrine()

    assert contract["schema_version"] == "gig_business_doctrine_contract_v1_2"
    assert contract["doctrine_ref"] == "gig_business_doctrine:v1.2"
    assert contract["canonical_path"] == str(DOCTRINE_PATH)
    assert contract["freshness"]["class"] == "NEVER_STALE"
    assert contract["freshness"]["stale_on_age"] is False
    assert contract["freshness"]["drift_on_hash_change"] is True
    assert contract["pricing_logistics_source_policy"] == "ONLY"
    assert contract["source_sha256"].startswith("sha256:")
    assert {section["section_id"] for section in contract["sections"]} == {
        "artistic_identity",
        "pricing_buckets",
        "label_identity",
        "client_fit_conflict",
        "safety",
        "email_outreach",
        "clara_intake_trust",
        "trust_breaking_point",
    }


def test_freshness_tracks_age_but_only_missing_or_hash_drift_is_stale() -> None:
    from gig_business_doctrine import build_freshness_registration

    registration = build_freshness_registration()

    assert registration["freshness_class"] == "NEVER_STALE"
    assert registration["status"] == "CURRENT"
    assert registration["age_seconds"] >= 0
    assert registration["max_age_seconds"] is None
    assert registration["stale_on_age"] is False
    assert registration["source_sha256"].startswith("sha256:")


def test_delivery_is_bounded_by_question_and_consumer() -> None:
    from gig_business_doctrine import build_doctrine_delivery

    unrelated = build_doctrine_delivery(
        agent_id="cassandra",
        question_class="frontdoor_freeform",
        question="summarize the service roster",
    )
    generic_client_note = build_doctrine_delivery(
        agent_id="cassandra",
        question_class="frontdoor_freeform",
        question="draft a client note about the attached invoice",
    )
    pricing = build_doctrine_delivery(
        agent_id="cassandra",
        question_class="gig_pricing",
        question="price a five-piece wedding band",
    )
    guardian = build_doctrine_delivery(
        agent_id="guardian",
        question_class="email_watch",
        question="review a client follow-up",
    )

    assert unrelated["status"] == "NOT_RELEVANT"
    assert unrelated["sections"] == []
    assert generic_client_note["status"] == "NOT_RELEVANT"
    assert generic_client_note["sections"] == []
    assert pricing["status"] == "READY"
    assert {section["section_id"] for section in pricing["sections"]} == {
        "pricing_buckets"
    }
    assert "Band gig target: $20,000" in pricing["packet_text"]
    guardian_ids = {section["section_id"] for section in guardian["sections"]}
    assert guardian_ids == {"email_outreach", "trust_breaking_point"}
    assert "artistic_identity" not in guardian_ids
    assert guardian["receipt"]["source_sha256"].startswith("sha256:")
    assert guardian["receipt"]["pricing_logistics_source_policy"] == "ONLY"


def test_temp_ledger_ingest_uses_single_door_and_records_provenance(tmp_path: Path) -> None:
    from gig_business_doctrine import ingest_doctrine_into_ledger

    db_path = tmp_path / "doctrine.sqlite"
    receipt = ingest_doctrine_into_ledger(db_path=db_path)

    assert receipt["status"] == "INGESTED"
    assert receipt["production_ledger_post"] is False
    assert receipt["source_file"] == str(DOCTRINE_PATH)
    assert receipt["source_sha256"].startswith("sha256:")
    assert receipt["freshness_class"] == "NEVER_STALE"
    assert receipt["total"] == 8
    assert receipt["inserted"] == 8

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT fact_id, source_file, source_commit, doc_category, "
            "temporal_or_doctrine FROM canonical_facts ORDER BY fact_id"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 8
    assert {row[1] for row in rows} == {str(DOCTRINE_PATH)}
    assert all(str(row[2]).startswith("sha256:") for row in rows)
    assert {row[3] for row in rows} == {"gig_business_doctrine"}
    assert {row[4] for row in rows} == {"doctrine_never_stale"}


def test_relevant_delivery_fails_closed_when_canonical_doctrine_is_missing(
    tmp_path: Path,
) -> None:
    from gig_business_doctrine import build_doctrine_delivery

    delivery = build_doctrine_delivery(
        agent_id="cassandra",
        question_class="gig_pricing",
        question="price the wedding band",
        path=tmp_path / "missing.md",
    )

    assert delivery["status"] == "STALE_MISSING"
    assert delivery["sections"] == []
    assert delivery["pricing_logistics_source_policy"] == "ONLY"
    assert "DO NOT PROVIDE OR ACT ON PRICING/LOGISTICS" in delivery["packet_text"]
