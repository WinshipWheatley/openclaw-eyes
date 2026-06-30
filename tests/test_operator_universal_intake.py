import json
import sqlite3
from pathlib import Path

from ar_gig_to_cash_serialization import from_json
from ar_expected_receivable_record import ExpectedReceivableRecord

from operator_universal_intake import (
    AGENT_LANE_REGISTRY_V0,
    JSON_EXPORT_NAME,
    SUPPORTED_ACTION_TYPES,
    agent_execution_mode_status,
    build_agent_surface_parity_report,
    is_universal_operator_intake_candidate,
    parse_operator_intake_text,
    process_direct_agent_surface_operator_intake,
    process_operator_intake_batch,
    process_mac_composer_operator_intake,
    process_operator_intake,
    split_operator_intake_text,
    try_process_surface_operator_intake,
)
from operator_skill_registry import (
    LOCAL_LOG_SKILL_ACTION_TYPES,
    get_operator_skill,
    operator_skill_reference_data_needs_manifest,
    operator_skill_rows,
)
from watch_desk_feed import build_watch_desk_feed


FIXED_NOW = "2026-06-11T15:00:00+00:00"


def _process(tmp_path: Path, text: str, **kwargs):
    return process_operator_intake(
        raw_text=text,
        surface=kwargs.pop("surface", "local_cli"),
        operator=kwargs.pop("operator", "Winship"),
        received_at_utc=kwargs.pop("received_at_utc", FIXED_NOW),
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
        **kwargs,
    )


def test_all_required_examples_parse_expected_action_lane_and_risk():
    examples = [
        ("Sign this as Winship.", "identity_signature_preference", "chief_identity", "low"),
        ("Start using Clara Reid.", "identity_signature_preference", "chief_identity", "low"),
        ("I did a St. Anne\u2019s gig tonight.", "gig_event_log", "cassandra_business/niles_context", "low"),
        ("I got paid $900 from Live Arts MD.", "income_payment_log", "cassandra_finance", "low"),
        ("I got paid $1250 from St. Anne's.", "income_payment_log", "cassandra_finance", "low"),
        ("I spent $106 on Claude Code Fable 5.", "expense_log", "cassandra_finance", "low"),
    ]

    for text, action_type, lane, risk in examples:
        parsed = parse_operator_intake_text(text, received_at_utc=FIXED_NOW)
        assert parsed["parsed"]["action_type"] == action_type
        assert parsed["parsed"]["lane"] == lane
        assert parsed["risk_tier"] == risk


def test_relative_tonight_normalizes_to_absolute_date():
    parsed = parse_operator_intake_text("I did a St. Anne's gig tonight.", received_at_utc=FIXED_NOW)

    assert parsed["parsed"]["fields"]["event_date"] == "2026-06-11"
    assert parsed["parsed"]["fields"]["date_basis"] == "implied_tonight"


def test_telegram_tonight_uses_operator_local_date_at_utc_rollover(tmp_path):
    result = _process(
        tmp_path,
        "I did a St. Anne's gig tonight.",
        surface="telegram",
        received_at_utc="2026-06-12T00:10:00+00:00",
    )

    fields = result["parsed"]["fields"]
    assert result["received_at_utc"] == "2026-06-12T00:10:00+00:00"
    assert result["operator_local_timezone"] == "America/New_York"
    assert result["operator_local_date"] == "2026-06-11"
    assert result["normalized_event_date"] == "2026-06-11"
    assert fields["operator_local_timezone"] == "America/New_York"
    assert fields["operator_local_date"] == "2026-06-11"
    assert fields["event_date"] == "2026-06-11"
    assert fields["normalized_event_date"] == "2026-06-11"
    assert fields["date_basis"] == "implied_tonight"

    receipt = json.loads(Path(result["receipt_refs"][0].split("#", 1)[0]).read_text(encoding="utf-8"))
    assert receipt["created_at_utc"]
    assert receipt["operator_local_timezone"] == "America/New_York"
    assert receipt["operator_local_date"] == "2026-06-11"
    assert receipt["normalized_event_date"] == "2026-06-11"

    feed = build_watch_desk_feed(read_model_root=tmp_path / "read_models", task_root=tmp_path / "tasks")
    item = next(item for item in feed["feed_items"] if item.get("action_type") == "gig_event_log")
    assert item["plain_line"] == "Logged gig: St. Anne's on 2026-06-11. Missing: payment amount?"
    assert item["operator_local_date"] == "2026-06-11"
    assert item["normalized_event_date"] == "2026-06-11"


def test_today_yesterday_and_tomorrow_use_operator_local_date_at_utc_rollover():
    received = "2026-06-12T00:10:00Z"

    today = parse_operator_intake_text("I did a St. Anne's gig today.", received_at_utc=received)
    yesterday = parse_operator_intake_text("I did a St. Anne's gig yesterday.", received_at_utc=received)
    tomorrow = parse_operator_intake_text("I did a St. Anne's gig tomorrow.", received_at_utc=received)

    assert today["parsed"]["fields"]["event_date"] == "2026-06-11"
    assert today["parsed"]["fields"]["date_basis"] == "implied_today"
    assert yesterday["parsed"]["fields"]["event_date"] == "2026-06-10"
    assert yesterday["parsed"]["fields"]["date_basis"] == "implied_yesterday"
    assert tomorrow["parsed"]["fields"]["event_date"] == "2026-06-12"
    assert tomorrow["parsed"]["fields"]["date_basis"] == "implied_tomorrow"


def test_low_risk_income_writes_receipt_read_model_and_watch_item(tmp_path):
    result = _process(tmp_path, "I got paid $900 from Live Arts MD.")
    read_model_path = tmp_path / "read_models" / JSON_EXPORT_NAME

    assert result["approval_required"] is False
    assert result["received_surface"] == "local_cli"
    assert result["addressed_agent"] == ""
    assert result["inferred_owner_agent"] == "cassandra"
    assert result["inferred_owner_lane"] == "cassandra_ar"
    assert result["route_confidence"] == "high"
    assert result["routed_to_agent"] == "cassandra"
    assert result["execution_mode"] == "live_listener"
    assert result["direct_surface_available"] is True
    assert result["fallback_route_available"] is True
    assert result["spawn_supported"] is False
    assert result["route_back_supported"] is True
    assert result["operator_visible_reply"] == "Logged income: $900 from Live Arts MD. Missing: invoice/project link, payment method."
    assert result["receipts"]
    assert result["receipt_refs"] == [f"{result['receipts'][0]['path']}#receipt"]
    assert Path(result["receipts"][0]["path"]).is_file()
    assert read_model_path.is_file()
    receipt = json.loads(Path(result["receipts"][0]["path"]).read_text(encoding="utf-8"))
    assert receipt["external_calls_performed"] is False
    assert receipt["approval_required"] is False
    assert receipt["parsed_fields"]["invoice_marked_paid"] is False
    assert receipt["inferred_owner_agent"] == "cassandra"
    assert receipt["execution_mode"] == "live_listener"
    assert receipt["direct_surface_available"] is True
    assert receipt["fallback_route_available"] is True
    assert receipt["spawn_supported"] is False
    assert receipt["route_back_supported"] is True
    assert receipt["receipt_refs"] == result["receipt_refs"]
    assert receipt["schema_version"] == "income_payment_log_receipt_v0"
    assert receipt["skill_id"] == "operator_skill:income_payment_log:v0"
    assert receipt["owner_agent"] == "cassandra"
    assert receipt["owner_lane"] == "cassandra_ar"
    assert receipt["source_surface"] == "local_cli"
    assert receipt["created_at_utc"]
    assert receipt["operator_local_timezone"] == "America/New_York"
    assert receipt["operator_local_date"] == "2026-06-11"
    assert receipt["normalized_event_date"] == "2026-06-11"
    assert receipt["invoice_marked_paid"] is False
    assert receipt["cross_link_refs"] == []
    assert receipt["mutation_scope"] == "local_receipt_read_model_only"

    read_model = json.loads(read_model_path.read_text(encoding="utf-8"))
    assert read_model["event_count"] == 1
    assert read_model["operator_skill_schema_version"] == "OPERATOR_SKILL_V0"
    assert len(read_model["operator_skill_rows"]) == 4
    assert read_model["events"][0]["parsed"]["fields"]["amount"] == 900
    assert read_model["events"][0]["operator_local_timezone"] == "America/New_York"
    assert read_model["events"][0]["operator_local_date"] == "2026-06-11"
    assert read_model["events"][0]["normalized_event_date"] == "2026-06-11"
    assert read_model["events"][0]["direct_surface_available"] is True
    assert read_model["events"][0]["fallback_route_available"] is True
    assert read_model["events"][0]["safe_actions_taken"] == ["record_local_income_payment_receipt"]
    assert (tmp_path / "read_models" / "watch_desk_feed.json").exists()

    feed = build_watch_desk_feed(read_model_root=tmp_path / "read_models", task_root=tmp_path / "tasks")
    item = next(item for item in feed["feed_items"] if item["plain_line"].startswith("Logged income"))
    plain_lines = [item["plain_line"] for item in feed["feed_items"]]
    assert "Logged income: $900 from Live Arts MD. Missing: invoice/project link, payment method." in plain_lines
    assert item["source_receipt_ref"] == result["receipt_refs"][0]
    assert item["action_type"] == "income_payment_log"
    assert item["owner_agent"] == "cassandra"
    assert item["owner_lane"] == "cassandra_ar"
    assert item["missing_fields"] == ["invoice/project link", "payment method"]
    assert item["push_class"] == "info"
    assert item["operator_local_date"] == "2026-06-11"
    assert item["normalized_event_date"] == "2026-06-11"


def test_income_payment_can_write_structured_g2c_receivable_without_paid_invoice_mutation(tmp_path):
    g2c_db_path = tmp_path / "g2c.sqlite3"

    result = _process(
        tmp_path,
        "I got paid $900 from Live Arts MD.",
        g2c_db_path=g2c_db_path,
    )

    assert result["parsed"]["fields"]["invoice_marked_paid"] is False
    assert result["authority_boundary"]["invoice_marked_paid"] is False
    assert result["g2c_normalization"]["status"] == "written"
    assert result["g2c_normalization"]["counterparty_ref"] == "live_arts_md"
    assert result["g2c_normalization"]["amount_minor_units"] == 90000
    assert result["g2c_normalization"]["lifecycle_state"] == "satisfied"
    assert result["g2c_normalization"]["due_date_iso"] == "2026-06-11"

    with sqlite3.connect(g2c_db_path) as conn:
        rows = conn.execute("SELECT canonical_json FROM expected_receivable_records").fetchall()
        links = conn.execute(
            """
            SELECT intake_id, record_type, counterparty_ref, amount_minor_units,
                   due_date_iso, lifecycle_state, provenance_json
            FROM operator_intake_g2c_links
            WHERE record_type = 'ExpectedReceivableRecord'
            """
        ).fetchall()

    assert len(rows) == 1
    receivable = from_json(rows[0][0])
    assert isinstance(receivable, ExpectedReceivableRecord)
    assert receivable.counterparty_ref == "live_arts_md"
    assert receivable.expected_minor_units == 90000
    assert receivable.currency_iso == "USD"
    assert receivable.due_date_iso == "2026-06-11"
    assert receivable.lifecycle_state == "satisfied"
    assert receivable.source_ref == f"operator_intake:{result['intake_id']}"
    assert receivable.resolution_ref == f"operator_intake:{result['intake_id']}:local_income_payment"

    assert len(links) == 1
    assert links[0][0] == result["intake_id"]
    assert links[0][2] == "live_arts_md"
    assert links[0][3] == 90000
    assert links[0][4] == "2026-06-11"
    assert links[0][5] == "satisfied"
    provenance = json.loads(links[0][6])
    assert provenance["source"] == "operator_universal_intake"
    assert provenance["raw_text_hash"].startswith("sha256:")
    assert provenance["receipt_ref"] == result["receipt_refs"][0]


def test_st_annes_gig_and_payment_preserve_g2c_provenance(tmp_path):
    g2c_db_path = tmp_path / "g2c.sqlite3"
    gig = _process(tmp_path, "I did a St. Anne's gig tonight.", g2c_db_path=g2c_db_path)
    payment = _process(
        tmp_path,
        "I got paid $1250 from St. Anne's.",
        session_context={"recent_gigs": [gig]},
        g2c_db_path=g2c_db_path,
    )

    with sqlite3.connect(g2c_db_path) as conn:
        gig_links = conn.execute(
            """
            SELECT record_id, provenance_json FROM operator_intake_g2c_links
            WHERE intake_id = ? AND record_type = 'GigRecord'
            """,
            (gig["intake_id"],),
        ).fetchall()
        receivable_links = conn.execute(
            """
            SELECT source_ref, provenance_json FROM operator_intake_g2c_links
            WHERE intake_id = ? AND record_type = 'ExpectedReceivableRecord'
            """,
            (payment["intake_id"],),
        ).fetchall()
        receivable_rows = conn.execute("SELECT canonical_json FROM expected_receivable_records").fetchall()

    assert len(gig_links) == 1
    gig_id = gig_links[0][0]
    assert gig_id.startswith("gig:operator_intake:")
    assert len(receivable_links) == 1
    assert receivable_links[0][0] == f"gig:{gig_id}"
    provenance = json.loads(receivable_links[0][1])
    assert provenance["associated_gig_intake_id"] == gig["intake_id"]
    assert provenance["associated_g2c_gig_id"] == gig_id

    receivable = from_json(receivable_rows[-1][0])
    assert receivable.counterparty_ref == "st_annes"
    assert receivable.expected_minor_units == 125000
    assert receivable.lifecycle_state == "satisfied"
    assert receivable.source_ref == f"gig:{gig_id}"


def test_ambiguous_sign_this_asks_for_referent_and_does_not_mutate(tmp_path):
    result = _process(tmp_path, "Sign this as Winship.")

    assert result["parsed"]["action_type"] == "identity_signature_preference"
    assert result["needs_clarification"] == ["referent:this"]
    assert result["safe_actions_taken"] == []
    assert result["receipts"] == []
    assert result["watch_desk_items"] == []
    assert result["approval_required"] is False
    assert not (tmp_path / "read_models" / JSON_EXPORT_NAME).exists()


def test_st_annes_payment_associates_with_recent_gig_context(tmp_path):
    gig = _process(tmp_path, "I did a St. Anne's gig tonight.")
    payment = _process(
        tmp_path,
        "I got paid $1250 from St. Anne's.",
        session_context={"recent_gigs": [gig]},
    )

    fields = payment["parsed"]["fields"]
    assert fields["payer"] == "St. Anne's"
    assert fields["amount"] == 1250
    assert fields["associated_gig_intake_id"] == gig["intake_id"]
    assert fields["associated_gig_date"] == "2026-06-11"


def test_expense_log_labels_category_without_tax_advice(tmp_path):
    result = _process(tmp_path, "I spent $106 on Claude Code Fable 5.")

    fields = result["parsed"]["fields"]
    assert fields["amount"] == 106
    assert fields["vendor"] == "Claude Code"
    assert fields["purchase_label"] == "Claude Code Fable 5"
    assert fields["category_label"] == "AI tools/software"
    assert fields["tax_advice_given"] is False
    assert "tax advice" not in result["normalized_summary"].lower()


def test_expense_log_links_to_recent_gig_when_venue_context_is_present(tmp_path):
    gig = _process(tmp_path, "I did a St. Anne's gig tonight.")
    expense = _process(
        tmp_path,
        "I spent $20 on St. Anne's parking.",
        session_context={"recent_gigs": [gig]},
    )

    fields = expense["parsed"]["fields"]
    assert fields["associated_gig_intake_id"] == gig["intake_id"]
    assert fields["associated_gig_date"] == "2026-06-11"
    assert gig["intake_id"] in expense["cross_link_refs"]
    receipt = json.loads(Path(expense["receipt_refs"][0].split("#", 1)[0]).read_text(encoding="utf-8"))
    assert gig["intake_id"] in receipt["cross_link_refs"]
    assert receipt["tax_advice_given"] is False


def test_operator_skill_registry_has_four_local_rows_and_unknown_is_blocked():
    rows = operator_skill_rows()
    by_action = {row["action_type"]: row for row in rows}

    assert tuple(by_action) == LOCAL_LOG_SKILL_ACTION_TYPES
    assert set(by_action) == {
        "income_payment_log",
        "expense_log",
        "gig_event_log",
        "identity_signature_preference",
    }
    for row in rows:
        assert row["schema_version"] == "OPERATOR_SKILL_V0"
        assert row["external"] is False
        assert row["approval_action"] is None
        assert row["must_not"]
        assert row["receipt_schema"] == f"{row['action_type']}_receipt_v0"
        assert row["push_class"] == "info"

    unknown = get_operator_skill("unknown_future_action")
    assert unknown["risk_tier"] == "high"
    assert unknown["external"] is True
    assert unknown["blocked"] is True
    assert "default unknown action to low risk" in unknown["must_not"]


def test_operator_skill_reference_data_manifest_is_placeholder_only():
    manifest = operator_skill_reference_data_needs_manifest()

    assert manifest["schema_version"] == "operator_skill_reference_data_needs_v0"
    assert manifest["private_data_ingested"] is False
    assert manifest["secrets_requested"] is False
    assert manifest["raw_bank_tax_legal_docs_ingested"] is False
    assert manifest["private_music_media_session_files_ingested"] is False
    assert "rate card" in manifest["missing_reference_data"]
    assert "tax category labels" in manifest["missing_reference_data"]


def test_income_missing_amount_clarifies_without_receipt_or_paid_claim(tmp_path):
    result = _process(tmp_path, "I got paid for the Hilton gig.")

    assert result["parsed"]["action_type"] == "income_payment_log"
    assert result["needs_clarification"] == ["amount"]
    assert result["parsed"]["fields"]["amount"] is None
    assert result["parsed"]["fields"]["invoice_marked_paid"] is False
    assert result["safe_actions_taken"] == []
    assert result["receipts"] == []
    assert result["watch_desk_items"] == []
    assert not (tmp_path / "read_models" / JSON_EXPORT_NAME).exists()


def test_unknown_low_confidence_input_only_requests_clarification(tmp_path):
    result = _process(tmp_path, "Handle that confusing thing.")

    assert result["parsed"]["action_type"] == "operator_clarification_event"
    assert result["parsed"]["confidence"] < 0.5
    assert result["needs_clarification"] == ["action_type"]
    assert result["safe_actions_taken"] == []
    assert result["receipts"] == []
    assert result["watch_desk_items"] == []


def test_remote_surfaces_store_hash_ref_not_raw_text(tmp_path):
    result = _process(tmp_path, "I got paid $900 from Live Arts MD.", surface="telegram")

    assert "raw_text" not in result
    assert result["raw_text_ref"].startswith("sha256:")
    assert result["raw_text_stored"] is False


def test_no_external_or_approval_side_effects_for_supported_local_events(tmp_path):
    for text in [
        "Start using Clara Reid.",
        "I did a St. Anne's gig tonight.",
        "I got paid $900 from Live Arts MD.",
        "I spent $106 on Claude Code Fable 5.",
    ]:
        result = _process(tmp_path, text)
        assert result["approval_required"] is False
        assert result["authority_boundary"]["external_calls_performed"] is False
        assert result["authority_boundary"]["approval_request_created"] is False
        assert result["authority_boundary"]["gmail_or_broker_called"] is False
        assert result["authority_boundary"]["coupa_bank_external_ledger_mutated"] is False
        assert result["authority_boundary"]["invoice_marked_paid"] is False

    assert set(SUPPORTED_ACTION_TYPES) == {
        "income_payment_log",
        "expense_log",
        "gig_event_log",
        "identity_signature_preference",
        "agent_lane_request",
        "approval_gated_action_request",
        "operator_clarification_event",
    }


def test_agent_lane_registry_v0_contains_required_daytime_lanes():
    assert set(AGENT_LANE_REGISTRY_V0) == {"cassandra", "niles", "chief", "hermes", "guardian", "watch desk"}
    assert AGENT_LANE_REGISTRY_V0["cassandra"]["watch_lane"] == "cassandra_ar"
    assert AGENT_LANE_REGISTRY_V0["niles"]["watch_lane"] == "niles_creative"
    assert AGENT_LANE_REGISTRY_V0["chief"]["watch_lane"] == "chief_runtime"
    assert AGENT_LANE_REGISTRY_V0["hermes"]["watch_lane"] == "hermes"
    assert AGENT_LANE_REGISTRY_V0["guardian"]["watch_lane"] == "guardian_approval"
    assert "send email without Guardian approval" in AGENT_LANE_REGISTRY_V0["cassandra"]["must_not"]


def test_agent_execution_mode_registry_classifies_live_spawned_sidecar_logical_and_guardian():
    cassandra = agent_execution_mode_status("cassandra")
    niles = agent_execution_mode_status("niles")
    chief = agent_execution_mode_status("chief")
    hermes = agent_execution_mode_status("hermes")
    guardian = agent_execution_mode_status("guardian")
    watch_desk = agent_execution_mode_status("watch desk")
    mac_composer = agent_execution_mode_status("mac_composer")

    assert cassandra["execution_mode"] == "live_listener"
    assert cassandra["direct_surface_available"] is True
    assert cassandra["current_status"] == "wired"
    assert niles["execution_mode"] == "spawned_worker"
    assert niles["direct_surface_available"] is False
    assert niles["spawn_supported"] is True
    assert chief["execution_mode"] == "hardcoded_route"
    assert hermes["execution_mode"] == "sidecar_adapter"
    assert guardian["execution_mode"] == "human_approval"
    assert guardian["spawn_supported"] is False
    assert watch_desk["execution_mode"] == "logical_only"
    assert watch_desk["current_status"] == "not_wired"
    assert mac_composer["execution_mode"] == "hardcoded_route"
    assert mac_composer["current_status"] == "partial"

    report = build_agent_surface_parity_report()
    assert report["live_surfaces_found"] == ["cassandra"]
    assert report["direct_surfaces_wired"]["niles"] is False
    assert report["fallback_routes_available"]["hermes"] is True
    assert report["execution_modes"]["watch desk"] == "logical_only"


def test_agent_addressed_messages_route_to_expected_lanes_without_external_calls(tmp_path):
    examples = [
        (
            "Niles, prep my live set notes.",
            "niles_creative",
            "niles",
            "spawned_worker",
            "That's a Niles creative prep request. I staged it for Niles.",
        ),
        (
            "Chief, what broke?",
            "chief_runtime",
            "chief",
            "hardcoded_route",
            "That's a Chief/system review request. I routed it to Chief.",
        ),
        (
            "Hermes, check the bridge.",
            "hermes",
            "hermes",
            "sidecar_adapter",
            "That's a Hermes adapter/protocol check. I staged it for Hermes.",
        ),
        (
            "Cassandra, log client context.",
            "cassandra_ar",
            "cassandra",
            "live_listener",
            "Cassandra request staged: log client context. No email action taken.",
        ),
    ]

    for text, lane, owner_agent, execution_mode, reply in examples:
        routed = try_process_surface_operator_intake(
            text,
            surface="telegram",
            received_at_utc=FIXED_NOW,
            read_model_root=tmp_path / "read_models",
            receipt_root=tmp_path / "receipts",
        )
        assert routed is not None
        assert routed["action_type"] == "agent_lane_request"
        assert routed["lane"] == lane
        assert routed["inferred_owner_agent"] == owner_agent
        assert routed["routed_from_agent"] == "cassandra"
        assert routed["routed_to_agent"] == owner_agent
        assert routed["execution_mode"] == execution_mode
        assert routed["reply_text"] == reply
        assert routed["approval_required"] is False
        assert routed["external_calls_performed"] is False
        assert routed["event"]["authority_boundary"]["approval_request_created"] is False
        assert routed["event"]["authority_boundary"]["gmail_or_broker_called"] is False


def test_direct_intended_niles_request_routes_with_spawned_mode_but_no_fake_live_surface(tmp_path):
    routed = process_direct_agent_surface_operator_intake(
        "prep my live set notes.",
        agent_id="niles",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed["handled"] is True
    assert routed["direct_surface_available"] is False
    assert routed["surface_status"] == "FALLBACK_ONLY"
    assert routed["routing_status"] == "ROUTED_VIA_FALLBACK"
    assert routed["inferred_owner_agent"] == "niles"
    assert routed["routed_from_agent"] == "niles"
    assert routed["routed_to_agent"] == "niles"
    assert routed["execution_mode"] == "spawned_worker"
    assert routed["event"]["addressed_agent"] == ""
    assert routed["event"]["direct_surface_available"] is False
    assert routed["event"]["fallback_route_available"] is True
    assert routed["event"]["spawn_supported"] is True
    assert routed["event"]["route_back_supported"] is True
    assert routed["event"]["parsed"]["fields"]["daw_action_taken"] is False
    assert routed["event"]["authority_boundary"]["daw_or_media_session_mutated"] is False


def test_wrong_agent_chief_finance_request_patches_to_cassandra_receipt(tmp_path):
    routed = process_direct_agent_surface_operator_intake(
        "I got paid $900 from Live Arts MD.",
        agent_id="chief",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed["handled"] is True
    assert routed["routing_status"] == "PATCHED_TO_OWNER"
    assert routed["wrong_agent_recovery"] is True
    assert routed["routed_from_agent"] == "chief"
    assert routed["routed_to_agent"] == "cassandra"
    assert routed["inferred_owner_agent"] == "cassandra"
    assert routed["reply_text"] == "That's a Cassandra finance item. I logged it there."
    assert routed["receipt_refs"]
    receipt = json.loads(Path(routed["receipt_refs"][0].split("#", 1)[0]).read_text(encoding="utf-8"))
    assert receipt["received_surface"] == "chief_direct"
    assert receipt["routed_from_agent"] == "chief"
    assert receipt["routed_to_agent"] == "cassandra"
    assert receipt["approval_required"] is False


def test_wrong_agent_cassandra_creative_request_patches_to_niles_without_daw_mutation(tmp_path):
    routed = try_process_surface_operator_intake(
        "Niles, prep my live set notes.",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed is not None
    assert routed["routed_from_agent"] == "cassandra"
    assert routed["routed_to_agent"] == "niles"
    assert routed["inferred_owner_agent"] == "niles"
    assert routed["execution_mode"] == "spawned_worker"
    assert routed["reply_text"] == "That's a Niles creative prep request. I staged it for Niles."
    assert routed["event"]["parsed"]["fields"]["daw_action_taken"] is False
    assert routed["event"]["authority_boundary"]["daw_or_media_session_mutated"] is False


def test_wrong_agent_niles_outbound_followup_patches_to_cassandra_and_requires_guardian(tmp_path):
    routed = process_direct_agent_surface_operator_intake(
        "Follow up with Annette about the invoice.",
        agent_id="niles",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed["handled"] is True
    assert routed["action_type"] == "approval_gated_action_request"
    assert routed["risk_tier"] == "high"
    assert routed["routing_status"] == "PATCHED_TO_OWNER"
    assert routed["routed_from_agent"] == "niles"
    assert routed["routed_to_agent"] == "cassandra"
    assert routed["approval_required"] is True
    assert "Guardian approval is required" in routed["reply_text"]
    assert routed["event"]["parsed"]["fields"]["email_sent"] is False
    assert routed["event"]["parsed"]["fields"]["gmail_draft_created"] is False
    assert routed["event"]["authority_boundary"]["approval_request_created"] is False


def test_wrong_agent_hermes_build_status_patches_to_chief(tmp_path):
    routed = process_direct_agent_surface_operator_intake(
        "What broke in the build?",
        agent_id="hermes",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed["handled"] is True
    assert routed["routing_status"] == "PATCHED_TO_OWNER"
    assert routed["routed_from_agent"] == "hermes"
    assert routed["routed_to_agent"] == "chief"
    assert routed["execution_mode"] == "hardcoded_route"
    assert routed["reply_text"] == "That's a Chief/system review request. I routed it to Chief."


def test_ambiguous_direct_request_creates_clarification_proof_without_execution(tmp_path):
    routed = process_direct_agent_surface_operator_intake(
        "Can you handle that thing?",
        agent_id="chief",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed["handled"] is False
    assert routed["routing_status"] == "CLARIFICATION_REQUIRED"
    assert routed["route_confidence"] == "low"
    assert routed["action_type"] == "operator_clarification_event"
    assert routed["approval_required"] is False
    assert routed["external_calls_performed"] is False
    assert routed["event"]["safe_actions_taken"] == []
    assert routed["event"]["stop_condition"] == "clarification_proof_written"
    assert routed["receipt_refs"]
    assert routed["watch_desk_refs"]
    assert "one detail" in routed["reply_text"]
    read_model_path = tmp_path / "read_models" / JSON_EXPORT_NAME
    assert read_model_path.exists()
    read_model = json.loads(read_model_path.read_text(encoding="utf-8"))
    assert read_model["events"][0]["parsed"]["action_type"] == "operator_clarification_event"
    assert read_model["events"][0]["approval_required"] is False
    receipt = json.loads(Path(routed["receipt_refs"][0].split("#", 1)[0]).read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "operator_clarification_event_receipt_v0"
    assert receipt["safe_actions_taken"] == []
    assert receipt["external_calls_performed"] is False
    assert receipt["approval_required"] is False


def test_telegram_ambiguous_handoff_request_persists_clarification_proof(tmp_path):
    routed = try_process_surface_operator_intake(
        "Can you handle that thing?",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed is not None
    assert routed["handled"] is False
    assert routed["route_confidence"] == "low"
    assert routed["event"]["parsed"]["action_type"] == "operator_clarification_event"
    assert routed["event"]["safe_actions_taken"] == []
    assert routed["receipt_refs"]
    assert routed["watch_desk_refs"]
    assert routed["approval_required"] is False
    assert routed["external_calls_performed"] is False
    assert "one detail" in routed["reply_text"]
    assert (tmp_path / "read_models" / JSON_EXPORT_NAME).exists()
    assert (tmp_path / "read_models" / "watch_desk_feed.json").exists()

    repeated = try_process_surface_operator_intake(
        "Can you handle that thing?",
        surface="telegram",
        received_at_utc="2026-06-11T23:10:00+00:00",
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )
    assert repeated is not None
    assert repeated["receipt_refs"] == routed["receipt_refs"]
    read_model = json.loads((tmp_path / "read_models" / JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    assert read_model["event_count"] == 1


def test_high_risk_send_request_logs_guardian_gated_receipt_without_approval_or_email(tmp_path):
    routed = try_process_surface_operator_intake(
        "Send this to Annette.",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed is not None
    assert routed["action_type"] == "approval_gated_action_request"
    assert routed["risk_tier"] == "high"
    assert routed["inferred_owner_agent"] == "cassandra"
    assert routed["routed_from_agent"] == "cassandra"
    assert routed["routed_to_agent"] == "cassandra"
    assert routed["approval_required"] is True
    assert routed["external_calls_performed"] is False
    assert routed["receipt_refs"]
    receipt = json.loads(Path(routed["receipt_refs"][0].split("#", 1)[0]).read_text(encoding="utf-8"))
    assert receipt["approval_required"] is True
    assert receipt["authority_boundary"]["approval_request_created"] is False
    assert receipt["parsed_fields"]["email_sent"] is False
    assert receipt["parsed_fields"]["gmail_draft_created"] is False


def test_sidecar_adapter_and_logical_only_routes_are_explicit(tmp_path):
    hermes = try_process_surface_operator_intake(
        "Hermes, check the bridge.",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )
    watch = try_process_surface_operator_intake(
        "Watch Desk, show what needs me.",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert hermes is not None
    assert hermes["inferred_owner_agent"] == "hermes"
    assert hermes["execution_mode"] == "sidecar_adapter"
    assert hermes["agent_execution"]["direct_surface_available"] is False
    assert watch is not None
    assert watch["inferred_owner_agent"] == "watch desk"
    assert watch["execution_mode"] == "logical_only"
    assert "executor is not wired" in watch["reply_text"]


def test_unknown_agent_asks_clarification_without_receipt_or_read_model(tmp_path):
    routed = try_process_surface_operator_intake(
        "Zephyr, check the thing.",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed is not None
    assert routed["handled"] is True
    assert routed["event"]["needs_clarification"] == ["known_agent_lane"]
    assert routed["receipt_refs"] == []
    assert routed["watch_desk_refs"] == []
    assert "don't know an active lane" in routed["reply_text"]
    assert not (tmp_path / "read_models" / JSON_EXPORT_NAME).exists()


def test_low_signal_comma_prefix_is_not_unknown_agent_and_can_still_parse_income(tmp_path):
    routed = try_process_surface_operator_intake(
        "ok, i got payd $900 frm Live Arts MD",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed is not None
    assert routed["action_type"] == "income_payment_log"
    assert routed["addressed_agent"] == ""
    assert routed["event"]["parsed"]["fields"]["amount"] == 900
    assert routed["event"]["parsed"]["fields"]["payer"] == "Live Arts MD"
    assert routed["event"]["parsed"]["fields"]["invoice_marked_paid"] is False


def test_typo_heavy_agent_lane_requests_resolve_to_existing_lanes(tmp_path):
    niles = try_process_surface_operator_intake(
        "Niels, prep the albm progression",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )
    chief = try_process_surface_operator_intake(
        "wat brok",
        surface="telegram",
        received_at_utc="2026-06-11T15:01:00+00:00",
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert niles is not None
    assert niles["action_type"] == "agent_lane_request"
    assert niles["inferred_owner_agent"] == "niles"
    assert niles["event"]["parsed"]["fields"]["daw_action_taken"] is False
    assert chief is not None
    assert chief["action_type"] == "agent_lane_request"
    assert chief["inferred_owner_agent"] == "chief"
    assert chief["event"]["parsed"]["fields"]["request_label"] == "what broke"


def test_multi_intent_message_splits_and_writes_stable_child_receipts(tmp_path):
    text = "I did a St. Anne's gig tonight, got paid $1250 from St. Anne's, and spent $106 on Claude Code Fable 5."

    assert split_operator_intake_text(text) == [
        "I did a St. Anne's gig tonight",
        "got paid $1250 from St. Anne's",
        "spent $106 on Claude Code Fable 5",
    ]

    events = process_operator_intake_batch(
        raw_text=text,
        surface="local_cli",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert [event["parsed"]["action_type"] for event in events] == [
        "gig_event_log",
        "income_payment_log",
        "expense_log",
    ]
    assert all(event["receipts"] for event in events)
    payment_fields = events[1]["parsed"]["fields"]
    assert payment_fields["associated_gig_intake_id"] == events[0]["intake_id"]
    assert payment_fields["associated_gig_date"] == "2026-06-11"
    assert events[1]["parsed"]["fields"]["invoice_marked_paid"] is False
    assert events[2]["parsed"]["fields"]["tax_advice_given"] is False
    assert events[0]["batch_group_id"].startswith("operator_intake_group:")
    assert events[0]["cross_link_refs"]
    assert events[1]["intake_id"] in events[0]["cross_link_refs"]
    assert events[0]["intake_id"] in events[1]["cross_link_refs"]
    receipt = json.loads(Path(events[1]["receipt_refs"][0].split("#", 1)[0]).read_text(encoding="utf-8"))
    assert events[0]["intake_id"] in receipt["cross_link_refs"]

    read_model = json.loads((tmp_path / "read_models" / JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    assert read_model["event_count"] == 3
    feed = build_watch_desk_feed(read_model_root=tmp_path / "read_models", task_root=tmp_path / "tasks")
    plain_lines = [item["plain_line"] for item in feed["feed_items"]]
    assert "Logged gig: St. Anne's on 2026-06-11. Missing: payment amount?" in plain_lines
    assert "Logged income: $1250 from St. Anne's. Missing: invoice/project link, payment method." in plain_lines
    assert "Logged expense: $106 Claude Code Fable 5 as AI tools/software." in plain_lines


def test_repeated_same_local_skill_intake_reuses_receipt_and_does_not_spam_watch_desk(tmp_path):
    first = _process(tmp_path, "I got paid $900 from Live Arts MD.")
    second = process_operator_intake(
        raw_text="I got paid $900 from Live Arts MD.",
        surface="local_cli",
        operator="Winship",
        received_at_utc="2026-06-11T23:59:00+00:00",
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert second["duplicate_detected"] is True
    assert second["duplicate_of_intake_id"] == first["intake_id"]
    assert second["receipt_refs"] == first["receipt_refs"]
    assert second["safe_actions_taken"] == ["reuse_existing_local_receipt_ref"]
    read_model = json.loads((tmp_path / "read_models" / JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    assert read_model["event_count"] == 1
    feed = build_watch_desk_feed(read_model_root=tmp_path / "read_models", task_root=tmp_path / "tasks")
    income_items = [item for item in feed["feed_items"] if item.get("action_type") == "income_payment_log"]
    assert len(income_items) == 1


def test_surface_response_for_multi_intent_exposes_mac_contract_refs(tmp_path):
    routed = try_process_surface_operator_intake(
        "I did a St. Anne's gig tonight, got paid $1250 from St. Anne's, and spent $106 on Claude Code Fable 5.",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed is not None
    assert routed["action_type"] == "multi_intent"
    assert routed["action_types"] == ["gig_event_log", "income_payment_log", "expense_log"]
    assert len(routed["intake_event_refs"]) == 3
    assert len(routed["receipt_refs"]) == 3
    assert len(routed["watch_desk_refs"]) == 3
    assert "Logged gig: St. Anne's on 2026-06-11." in routed["reply_text"]
    assert routed["safety_flags"]["external_calls_performed"] is False


def test_telegram_style_phrases_route_to_universal_intake(tmp_path):
    examples = [
        ("I got paid $900 from Live Arts MD.", "income_payment_log", "Logged income: $900 from Live Arts MD."),
        ("I spent $106 on Claude Code Fable 5.", "expense_log", "Logged expense: $106 Claude Code Fable 5"),
        ("I did a St. Anne's gig tonight.", "gig_event_log", "Logged gig: St. Anne's on 2026-06-11."),
    ]

    for text, action_type, reply_part in examples:
        routed = try_process_surface_operator_intake(
            text,
            surface="telegram",
            received_at_utc=FIXED_NOW,
            read_model_root=tmp_path / "read_models",
            receipt_root=tmp_path / "receipts",
        )
        assert routed is not None
        assert routed["handled"] is True
        assert routed["action_type"] == action_type
        assert reply_part in routed["reply"]
        assert routed["approval_required"] is False
        assert routed["external_calls_performed"] is False
        assert routed["reply_text"] == routed["reply"]


def test_telegram_sign_this_routes_to_clarification_not_mutation(tmp_path):
    routed = try_process_surface_operator_intake(
        "Sign this as Winship.",
        surface="telegram",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert routed is not None
    event = routed["event"]
    assert event["needs_clarification"] == ["referent:this"]
    assert event["safe_actions_taken"] == []
    assert event["receipts"] == []
    assert "Need the target item" in routed["reply"]
    assert not (tmp_path / "read_models" / JSON_EXPORT_NAME).exists()


def test_route_exclusions_do_not_intercept_approval_reminder_or_generic_chat():
    exact_send_approval = (
        "Approve exact send request exact_send_authority_request:abc123 for "
        "Annette.Sunga@hilton.com."
    )
    guardian_text = "Guardian approval request operator_action_approval_request:34EF3C91 approved."
    draft_approval = (
        "Cassandra, the Annette follow-up draft is approved with this exact text:\n\n"
        "Subject: Follow-up on Winship invoice\n\n"
        "Hi Annette,\n\nPlease follow up.\n\nPrepare the send authority request."
    )

    assert is_universal_operator_intake_candidate(exact_send_approval) is False
    assert is_universal_operator_intake_candidate(guardian_text) is False
    assert is_universal_operator_intake_candidate(draft_approval) is False
    assert is_universal_operator_intake_candidate("Remind me tomorrow to check the invoice.") is False
    assert is_universal_operator_intake_candidate("What's the state of Cassandra today?") is False


def test_mac_composer_callable_contract_routes_fixture_text(tmp_path):
    response = process_mac_composer_operator_intake(
        "Start using Clara Reid.",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert response["schema_version"] == "operator_intake_surface_response_v0"
    assert response["handled"] is True
    assert response["surface"] == "mac_composer"
    assert response["action_type"] == "identity_signature_preference"
    assert response["reply"] == "Staged identity preference: use Clara Reid locally."
    assert response["reply_text"] == response["reply"]
    assert response["intake_event_refs"]
    assert response["receipt_refs"]
    assert response["watch_desk_refs"]
    assert response["approval_required"] is False
    assert response["external_calls_performed"] is False


def test_mac_composer_callable_contract_handles_niles_creative_prep(tmp_path):
    response = process_mac_composer_operator_intake(
        "Niles, prep my live set notes.",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert response["schema_version"] == "operator_intake_surface_response_v0"
    assert response["handled"] is True
    assert response["surface"] == "mac_composer"
    assert response["lane"] == "niles_creative"
    assert response["action_type"] == "agent_lane_request"
    assert response["inferred_owner_agent"] == "niles"
    assert response["routed_from_agent"] == "mac_composer"
    assert response["routed_to_agent"] == "niles"
    assert response["execution_mode"] == "spawned_worker"
    assert response["reply_text"] == "That's a Niles creative prep request. I staged it for Niles."
    assert response["event"]["authority_boundary"]["daw_or_media_session_mutated"] is False
    assert response["event"]["raw_text_stored"] is False


def test_mac_composer_callable_contract_routes_finance_to_cassandra(tmp_path):
    response = process_mac_composer_operator_intake(
        "I got paid $900 from Live Arts MD.",
        received_at_utc=FIXED_NOW,
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
    )

    assert response["schema_version"] == "operator_intake_surface_response_v0"
    assert response["handled"] is True
    assert response["surface"] == "mac_composer"
    assert response["action_type"] == "income_payment_log"
    assert response["inferred_owner_agent"] == "cassandra"
    assert response["routed_from_agent"] == "mac_composer"
    assert response["routed_to_agent"] == "cassandra"
    assert response["execution_mode"] == "live_listener"
    assert response["approval_required"] is False
    assert response["event"]["parsed"]["fields"]["invoice_marked_paid"] is False
    assert response["event"]["authority_boundary"]["external_calls_performed"] is False
    assert response["receipt_refs"]


def test_cassandra_handler_routes_operator_telegram_text_to_universal_intake(monkeypatch, tmp_path):
    import cassandra_brain

    logged = {}
    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda query, packet: "event:test")
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None)
    monkeypatch.setattr(cassandra_brain, "answer_date_awareness_query", lambda query: None)
    monkeypatch.setattr(cassandra_brain, "_handle_operator_objective", lambda *args, **kwargs: None)

    def fail_call(*args, **kwargs):
        raise AssertionError("universal intake route should not call a model")

    def capture_log(user_text, replies, route="llm", metadata=None):
        logged["route"] = route
        logged["replies"] = replies
        logged["metadata"] = metadata or {}

    monkeypatch.setattr(cassandra_brain, "_call", fail_call)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", capture_log)

    replies = cassandra_brain.handle(
        "I got paid $900 from Live Arts MD.",
        session={
            "skip_followup_check": True,
            "source_user_label": "operator",
            "received_at_utc": FIXED_NOW,
            "operator_intake_read_model_root": tmp_path / "read_models",
            "operator_intake_receipt_root": tmp_path / "receipts",
        },
    )

    assert replies == ["Logged income: $900 from Live Arts MD. Missing: invoice/project link, payment method."]
    assert logged["route"] == "universal_operator_intake"
    assert logged["metadata"]["action_type"] == "income_payment_log"
    assert logged["metadata"]["approval_required"] is False
    assert logged["metadata"]["external_calls_performed"] is False
    assert logged["metadata"]["route_confidence"] == "high"
    assert logged["metadata"]["inferred_owner_agent"] == "cassandra"
    assert logged["metadata"]["routed_to_agent"] == "cassandra"
    assert logged["metadata"]["receipt_refs"]
    receipt = json.loads(Path(logged["metadata"]["receipt_refs"][0].split("#", 1)[0]).read_text(encoding="utf-8"))
    assert logged["metadata"]["approval_required"] == receipt["approval_required"]
    assert logged["metadata"]["watch_desk_refs"]


def test_cassandra_handler_logs_high_risk_universal_intake_approval_truth(monkeypatch, tmp_path):
    import cassandra_brain

    logged_rows = []
    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda query, packet: "event:test")
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None)
    monkeypatch.setattr(cassandra_brain, "answer_date_awareness_query", lambda query: None)
    monkeypatch.setattr(cassandra_brain, "_handle_operator_objective", lambda *args, **kwargs: None)

    def fail_call(*args, **kwargs):
        raise AssertionError("approval-gated universal intake route should not call a model")

    def capture_log(user_text, replies, route="llm", metadata=None):
        logged_rows.append({"route": route, "replies": replies, "metadata": metadata or {}})

    monkeypatch.setattr(cassandra_brain, "_call", fail_call)
    monkeypatch.setattr(cassandra_brain, "_log_conversation", capture_log)

    for text in ("Send this to Annette.", "Follow up with Annette about the invoice."):
        replies = cassandra_brain.handle(
            text,
            session={
                "skip_followup_check": True,
                "source_user_label": "operator",
                "received_at_utc": FIXED_NOW,
                "operator_intake_read_model_root": tmp_path / "read_models",
                "operator_intake_receipt_root": tmp_path / "receipts",
            },
        )

        assert replies == [
            "That's a Cassandra outbound action. I logged it for Cassandra; "
            "Guardian approval is required before execution."
        ]

    assert len(logged_rows) == 2
    for logged in logged_rows:
        assert logged["route"] == "universal_operator_intake"
        assert logged["metadata"]["action_type"] == "approval_gated_action_request"
        assert logged["metadata"]["risk_tier"] == "high"
        assert logged["metadata"]["approval_required"] is True
        assert logged["metadata"]["external_calls_performed"] is False
        assert logged["metadata"]["route_confidence"] == "high"
        assert logged["metadata"]["inferred_owner_agent"] == "cassandra"
        assert logged["metadata"]["routed_to_agent"] == "cassandra"
        assert logged["metadata"]["receipt_refs"]
        receipt = json.loads(Path(logged["metadata"]["receipt_refs"][0].split("#", 1)[0]).read_text(encoding="utf-8"))
        assert receipt["approval_required"] is True
        assert receipt["authority_boundary"]["approval_request_created"] is False
        assert logged["metadata"]["approval_required"] == receipt["approval_required"]
        assert logged["metadata"]["watch_desk_refs"]


def test_cassandra_handler_does_not_route_designated_contact_to_operator_intake(monkeypatch, tmp_path):
    import cassandra_brain

    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda query, packet: "event:test")
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None)
    monkeypatch.setattr(cassandra_brain, "answer_date_awareness_query", lambda query: None)
    monkeypatch.setattr(cassandra_brain, "_handle_operator_objective", lambda *args, **kwargs: None)
    monkeypatch.setattr(cassandra_brain, "_detect_financial_intent", lambda query: None)
    monkeypatch.setattr(cassandra_brain, "_detect_future_action_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_detect_calendar_delete_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_detect_calendar_create_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_detect_outreach_email_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_detect_send_email_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_detect_invoice_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_detect_file_verify_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_detect_payment_verify_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "detect_finance_status_intent", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_call", lambda *args, **kwargs: "normal Cassandra path")
    monkeypatch.setattr(cassandra_brain, "_pii_tokenize", lambda prompt: (prompt, None))
    monkeypatch.setattr(cassandra_brain, "_pii_rehydrate_reply", lambda reply, ctx: reply)
    monkeypatch.setattr(cassandra_brain, "_cassandra_context_clean", lambda *args, **kwargs: False)
    monkeypatch.setattr(cassandra_brain, "registry_context_for_query", lambda query: None)
    monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda query, **kwargs: "")
    monkeypatch.setattr(cassandra_brain, "_fetch_gmail_context", lambda query, **kwargs: "")
    monkeypatch.setattr(cassandra_brain, "_fetch_contacts_context", lambda query, **kwargs: "")
    monkeypatch.setattr(cassandra_brain, "_fetch_payment_verify_context", lambda query, **kwargs: "")
    monkeypatch.setattr(cassandra_brain, "format_finance_context", lambda query: "")
    monkeypatch.setattr(cassandra_brain, "_format_reality_context", lambda query: "")
    monkeypatch.setattr(cassandra_brain, "_format_session_fact_override_context", lambda query, state: "")
    monkeypatch.setattr(cassandra_brain, "_should_use_deep", lambda query: False)
    monkeypatch.setattr(cassandra_brain, "_use_small_cassandra_reply_model", lambda query: True)
    monkeypatch.setattr(cassandra_brain, "gate_reply", lambda reply, query, **kwargs: reply)
    monkeypatch.setattr(cassandra_brain, "tts_clean", lambda reply: reply)
    monkeypatch.setattr(cassandra_brain, "build_context_snapshot", lambda state: "")
    monkeypatch.setattr(cassandra_brain, "is_focus_mode", lambda: False)
    monkeypatch.setattr(cassandra_brain, "is_social_mode", lambda: False)

    replies = cassandra_brain.handle(
        "I got paid $900 from Live Arts MD.",
        session={
            "skip_followup_check": True,
            "source_user_label": "designated_contact",
            "operator_intake_read_model_root": tmp_path / "read_models",
            "operator_intake_receipt_root": tmp_path / "receipts",
        },
    )

    assert replies == ["normal Cassandra path"]
    assert not (tmp_path / "read_models" / JSON_EXPORT_NAME).exists()
