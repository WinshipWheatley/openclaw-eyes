import hashlib
import json
from pathlib import Path

import openclaw_reference_data_hydrator as hydrator


FIXED_NOW = "2026-06-11T18:00:00Z"


def _write_confirmed(path: Path, records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"records": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_record(record_id: str, category: str, **fields):
    record = {
        "record_id": record_id,
        "category": category,
        "authoritative": True,
        "review_status": "confirmed_by_winship",
        "safe_usage_scope": "runtime_reference_label_only",
        "source_artifact_ref": "guided_review_sessions.json#data_room_reference_review",
        "confidence": "confirmed",
        "allowed_uses": ["read_model_context"],
        "must_not": ["do not invent missing details"],
    }
    record.update(fields)
    return record


def _confirmed_records():
    return [
        _base_record(
            "rate_001",
            "rate_card",
            service="Music direction",
            default_rate="confirmed per contract",
            rate_type="project",
            quote_ready=True,
            planning_estimate=True,
        ),
        _base_record(
            "client_001",
            "client_roster",
            canonical_name="Capital Hilton",
            aliases=["Capital Hilton DC"],
            terms="net terms if confirmed by invoice",
            portal_or_coupa="Coupa label only",
            usual_services=["events"],
            trust_tier="known_client",
        ),
        _base_record(
            "venue_001",
            "venue_roster",
            venue="Capital Hilton",
            payer_or_client="Capital Hilton",
            typical_service="events",
            venue_status="confirmed venue",
        ),
        _base_record(
            "expense_001",
            "expense_categories",
            category_label="AI tools/software",
            examples=["Claude Code"],
            tax_tag_label_only="software_tools",
            cpa_review_recommended=True,
        ),
        _base_record(
            "persona_001",
            "persona_policy",
            identity="Winship",
            public_facing=True,
            allowed_contexts=["artist signature"],
            prohibited_contexts=["legal identity", "tax identity", "billing identity"],
            signature_rules="Use Winship only where confirmed.",
        ),
        _base_record(
            "business_001",
            "business_identity",
            business_name="OpenClaw Studio",
            invoice_from_name="OpenClaw Studio",
            invoice_terms="as stated on invoice",
            invoice_numbering_policy="preserve source numbering",
        ),
        _base_record(
            "payment_privacy_001",
            "payment_privacy_policy",
            zelle_policy="Use confirmed public label only.",
            direct_deposit_policy="Do not store raw account or routing values.",
            address_policy="Do not expose home address unless trust policy confirms.",
            phone_policy="Do not expose phone unless trust policy confirms.",
            trust_tiers=["known_client"],
        ),
        _base_record(
            "contact_001",
            "contact_requirements",
            account_client="Capital Hilton",
            needed_contacts=["billing contact"],
            known_contacts=["confirmed billing desk label"],
            missing_fields=["direct email"],
        ),
    ]


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _hashes(root: Path):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.glob("openclaw_reference_*.json"))
    }


def test_confirmed_input_hydrates_expected_read_models(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    _write_confirmed(input_path, _confirmed_records())

    result = hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    assert result["status"] == hydrator.STATUS_READY
    expected_files = set(hydrator.OUTPUT_FILES.values()) | {hydrator.MANIFEST_FILE}
    assert expected_files == {path.name for path in output_root.glob("openclaw_reference_*.json")}
    assert result["validation"]["hydrated_record_count"] == 8
    assert all(count == 1 for count in result["validation"]["hydrated_counts_by_category"].values())

    rate_card = _json(output_root / "openclaw_reference_rate_card.json")
    first = rate_card["records"][0]
    assert first["source_record_id"] == "rate_001"
    assert first["review_status"] == "hydrated_from_confirmed_reference"
    assert first["authoritative"] is True
    assert first["runtime_mutation_performed"] is False
    assert first["external_calls_performed"] is False
    assert "do not invent rates" in first["must_not"]


def test_provisional_input_is_skipped(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    record = _base_record("sleepy_001", "client_roster", canonical_name="Sleepy Client")
    record["provisional_marker"] = "*"
    _write_confirmed(input_path, [record])

    result = hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    assert result["status"] == hydrator.STATUS_BLOCKED
    assert result["validation"]["skipped_counts_by_reason"] == {"provisional_marker": 1}
    assert not (output_root / "openclaw_reference_client_roster.json").exists()


def test_do_not_import_input_is_skipped(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    _write_confirmed(input_path, [_base_record("blocked_001", "do_not_import", name="Raw private source")])

    result = hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    assert result["status"] == hydrator.STATUS_BLOCKED
    assert result["validation"]["skipped_counts_by_reason"] == {"do_not_import": 1}


def test_missing_confirmed_input_returns_blocked_status(tmp_path):
    output_root = tmp_path / "read_models"
    result = hydrator.run_hydration_once(
        primary_path=tmp_path / "primary_missing.json",
        fallback_path=tmp_path / "fallback_missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    assert result["status"] == hydrator.STATUS_BLOCKED_NO_CONFIRMED_DATA
    assert result["validation"]["skipped_counts_by_reason"] == {"missing_confirmed_input": 1}
    assert _json(output_root / hydrator.MANIFEST_FILE)["status"] == hydrator.STATUS_BLOCKED_NO_CONFIRMED_DATA
    assert not (output_root / "openclaw_reference_rate_card.json").exists()


def test_raw_sensitive_patterns_are_rejected(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    _write_confirmed(
        input_path,
        [
            _base_record(
                "sensitive_payment_001",
                "payment_privacy_policy",
                direct_deposit_policy="routing number 123456789 account number 123456789012",
            )
        ],
    )

    result = hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    assert result["status"] == hydrator.STATUS_BLOCKED
    assert result["validation"]["skipped_counts_by_reason"] == {"sensitive_raw_pattern": 1}
    assert not (output_root / "openclaw_reference_payment_privacy_policy.json").exists()


def test_expense_category_keeps_tax_label_without_tax_advice(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    _write_confirmed(input_path, [_confirmed_records()[3]])

    hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    record = _json(output_root / "openclaw_reference_expense_categories.json")["records"][0]
    assert record["tax_tag_label_only"] == "software_tools"
    assert record["tax_advice_given"] is False
    assert "no tax advice" in record["must_not"]


def test_payment_privacy_never_stores_raw_account_or_routing_values(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    _write_confirmed(input_path, [_confirmed_records()[6]])

    hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    record = _json(output_root / "openclaw_reference_payment_privacy_policy.json")["records"][0]
    assert record["raw_account_routing_imported"] is False
    serialized = json.dumps(record, sort_keys=True)
    assert "123456789" not in serialized
    assert "123456789012" not in serialized


def test_persona_policy_preserves_prohibited_contexts(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    _write_confirmed(input_path, [_confirmed_records()[4]])

    hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    record = _json(output_root / "openclaw_reference_persona_policy.json")["records"][0]
    assert record["prohibited_contexts"] == ["legal identity", "tax identity", "billing identity"]
    assert "do not use persona for legal/tax/billing identity unless confirmed" in record["must_not"]


def test_idempotent_rerun_produces_same_hashes(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    _write_confirmed(input_path, _confirmed_records())

    first = hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )
    first_hashes = _hashes(output_root)
    second = hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )
    second_hashes = _hashes(output_root)

    assert first["status"] == second["status"] == hydrator.STATUS_READY
    assert first_hashes == second_hashes


def test_hydration_manifest_lists_counts_and_skipped_reasons(tmp_path):
    input_path = tmp_path / "confirmed.json"
    output_root = tmp_path / "read_models"
    skipped = _base_record("needs_source_001", "client_roster", canonical_name="Needs Source")
    skipped["review_status"] = "needs_source"
    _write_confirmed(input_path, [_confirmed_records()[0], skipped])

    hydrator.run_hydration_once(
        primary_path=input_path,
        fallback_path=tmp_path / "missing.json",
        read_model_root=output_root,
        hydrated_at_utc=FIXED_NOW,
    )

    manifest = _json(output_root / hydrator.MANIFEST_FILE)
    assert manifest["status"] == hydrator.STATUS_READY
    assert manifest["source_record_count"] == 2
    assert manifest["hydrated_counts_by_category"] == {"rate_card": 1}
    assert manifest["skipped_counts_by_reason"] == {"provisional_review_status": 1}
    assert manifest["runtime_mutation_performed"] is False
    assert manifest["external_calls_performed"] is False
