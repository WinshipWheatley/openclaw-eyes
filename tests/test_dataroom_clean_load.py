import json
import sqlite3
from pathlib import Path

import pytest

from business_ops_ledger import init_business_ops_ledger
from dataroom_clean_load import (
    DEFAULT_CONFIRMED_REFERENCE_PATH,
    TARGET_TABLE,
    build_load_plan,
    parse_confirmed_reference,
    render_load_plan_markdown,
)


SOURCE_PATH = DEFAULT_CONFIRMED_REFERENCE_PATH


def _write_by_key(plan):
    return {write.key: write for write in plan.planned_writes}


def test_parse_staged_confirmed_reference_maps_all_planned_business_facts():
    plan = build_load_plan(SOURCE_PATH, source_commit="test-source")
    writes = _write_by_key(plan)

    assert plan.dry_run_only is True
    assert len(plan.planned_writes) == 40
    assert writes["business_config.services.live_music_performance"].value.startswith(
        "Live music performance"
    )
    assert writes[
        "business_config.rate_card.corporate_dc_baltimore_annapolis"
    ].canonical_fields["fact_text"] == "Corporate (DC / Baltimore / Annapolis): from $2,000"
    assert (
        writes[
            "business_config.clients_payers_contacts.capital_hilton_dc"
        ].target_table
        == TARGET_TABLE
    )
    assert "Coupa" in writes[
        "business_config.clients_payers_contacts.capital_hilton_dc"
    ].value
    assert writes[
        "business_config.payment_methods_remit_by_trust_tier.trust_gated_hidden_by_default"
    ].canonical_fields["sensitivity_class"] == "operational_canonical"
    assert writes["business_config.personas.cassandra"].value.startswith(
        "Cassandra = internal"
    )
    assert writes[
        "business_config.open_items_actions.time_sensitive_live_arts_md_payment_chase"
    ].value.startswith("TIME-SENSITIVE - Live Arts MD! payment chase")


def test_planned_rows_are_idempotent_for_same_source_and_revision():
    first = build_load_plan(SOURCE_PATH, source_commit="test-source")
    second = build_load_plan(SOURCE_PATH, source_commit="test-source")

    first_rows = [write.canonical_fields for write in first.planned_writes]
    second_rows = [write.canonical_fields for write in second.planned_writes]
    assert first_rows == second_rows
    assert len({write.fact_id for write in first.planned_writes}) == len(first.planned_writes)


def test_build_plan_checks_conflicts_without_writing(tmp_path):
    plan = build_load_plan(SOURCE_PATH, source_commit="test-source")
    selected = _write_by_key(plan)["business_config.services.live_music_performance"]
    db_path = tmp_path / "ledger.sqlite"
    init_business_ops_ledger(str(db_path))

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO canonical_facts (
            fact_id, source_file, section_heading, source_commit, content_hash,
            fact_text, sensitivity_class, allowed_actors, doc_category,
            temporal_or_doctrine, source_description, truth_source_id,
            truth_status, verification_required, verification_evidence_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            selected.fact_id,
            "old.md",
            "Services",
            "old",
            "different-hash",
            "Different service text",
            "public_canonical",
            json.dumps(["cassandra"]),
            "business_config",
            "declared_reference",
            "old source",
            "old_source",
            "declared",
            1,
            None,
        ),
    )
    conn.commit()
    before_count = conn.execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]
    conn.close()

    checked = build_load_plan(SOURCE_PATH, db_path=db_path, source_commit="test-source")

    conn = sqlite3.connect(db_path)
    after_count = conn.execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]
    conn.close()

    assert before_count == after_count == 1
    assert checked.db_check_status == "checked"
    assert len(checked.conflicts) == 1
    assert checked.conflicts[0].fact_id == selected.fact_id


def test_gaps_and_markdown_call_out_open_or_ambiguous_items():
    plan = build_load_plan(SOURCE_PATH, source_commit="test-source")
    gap_keys = {gap.key for gap in plan.gaps}

    assert "business_config.rate_card.tech_work" in gap_keys
    assert "business_config.payment_terms.reynolds" in gap_keys
    assert "business_config.open_items_actions.live_arts_accountant_name" in gap_keys

    markdown = render_load_plan_markdown(plan)
    assert "# Data Room Clean Load Dry Run Plan" in markdown
    assert "## Exact canonical_facts Rows" in markdown
    assert "## Gaps And Ambiguities" in markdown
    assert "This plan does not write the live ledger." in markdown


def test_parser_normalizes_markdown_to_ascii_values():
    items = parse_confirmed_reference(
        """
## Example — Section
- **Client** — pays via **Coupa** → review.
"""
    )

    assert items[0].section_heading == "Example - Section"
    assert items[0].value == "Client - pays via Coupa -> review."
    assert items[0].key == "business_config.example_section.client"
