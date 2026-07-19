from __future__ import annotations

from price_truth_temporal import load_price_truth_facts, resolve_temporal_truth


SIGNATURE = {
    "job_type": "solo_performance",
    "duration_minutes": 180,
    "personnel": ["operator"],
    "scope": ["performance"],
    "location": "annapolis_md",
    "production": "venue_provided",
    "client_event_class": "restaurant",
}


def _fact(ref: str, **changes):
    value = {
        "fact_ref": ref,
        "subject_ref": "solo_acoustic",
        "metric_ref": "price_minor_units",
        "value_known": True,
        "typed_value": {"minor_units": 25000, "currency": "USD"},
        "time_domain": "HISTORICAL_OBSERVED",
        "valid_from": "2026-06-27",
        "valid_until": "2026-06-27",
        "observed_at": "2026-06-27T23:00:00+00:00",
        "evidence_as_of": "2026-06-27T23:00:00+00:00",
        "freshness_policy": "HISTORICAL_IMMUTABLE",
        "freshness_status": "CURRENT_HASH",
        "authority_status": "OBSERVED",
        "operator_authority_ref": "",
        "regime_ref": "solo_pre_org",
        "transition_event_ref": "",
        "transition_status": "",
        "transition_requires_operator": False,
        "comparison_signature": dict(SIGNATURE),
        "source_refs": ["g2c:reynolds:2026-06-27"],
        "source_hashes": ["sha256:" + "a" * 64],
    }
    value.update(changes)
    return value


def test_c1_never_promotes_historical_price_when_current_value_is_unknown() -> None:
    facts = [
        _fact("history:reynolds"),
        _fact(
            "current:solo-custom",
            value_known=False,
            typed_value=None,
            time_domain="CURRENT_PROVISIONAL",
            valid_from="2026-07-18",
            valid_until=None,
            authority_status="PROVISIONAL",
            source_refs=["operator:price-truth-agreement-v1"],
        ),
    ]

    answer = resolve_temporal_truth("C1", facts, subject_ref="solo_acoustic", as_of="2026-07-19")

    assert answer["direct_answer"]["value_known"] is False
    assert answer["direct_answer"]["posture"] == "CURRENT_PROVISIONAL"
    assert answer["historical_context"][0]["typed_value"]["minor_units"] == 25000
    assert answer["trace"]["selected_fact_refs"] == ["current:solo-custom", "history:reynolds"]
    assert answer["machine_proof"]["historical_promoted_to_current"] is False


def test_c2_blocks_growth_claim_when_any_signature_dimension_differs_or_is_missing() -> None:
    current = _fact(
        "current:solo",
        typed_value={"minor_units": 50000, "currency": "USD"},
        time_domain="CURRENT_DECLARED",
        valid_from="2026-07-18",
        valid_until=None,
        authority_status="DECLARED",
        operator_authority_ref="operator:terminal:price",
    )
    history = _fact("history:short", comparison_signature={**SIGNATURE, "duration_minutes": 60})

    answer = resolve_temporal_truth("C2", [current, history], subject_ref="solo_acoustic", as_of="2026-07-19")

    assert answer["comparison"]["comparable"] is False
    assert "duration_minutes" in answer["comparison"]["mismatched_dimensions"]
    assert answer["comparison"]["growth_claim_allowed"] is False
    assert answer["trace"]["rejected_facts"][0]["reason"] == "comparison_signature_mismatch"


def test_c3_keeps_semantic_time_evidence_freshness_and_authority_independent() -> None:
    answer = resolve_temporal_truth(
        "C3",
        [_fact("history:fresh-hash")],
        subject_ref="solo_acoustic",
        as_of="2026-07-19",
    )

    row = answer["axis_report"][0]
    assert row["semantic_time"] == "HISTORICAL_OBSERVED"
    assert row["evidence_freshness"] == "CURRENT_HASH"
    assert row["authority_state"] == "OBSERVED"
    assert row["current_rate_claim_allowed"] is False


def test_c4_observation_never_activates_future_regime_without_operator_gate() -> None:
    future = _fact(
        "future:org-band",
        subject_ref="band_event",
        typed_value={"minor_units": 2000000, "currency": "USD"},
        time_domain="FUTURE_TRIGGER",
        valid_from="2026-08-01",
        valid_until=None,
        authority_status="TRANSITION_PENDING",
        regime_ref="organization_online",
        transition_event_ref="event:organization-online",
        transition_status="OBSERVED_PENDING_OPERATOR",
        transition_requires_operator=True,
    )

    pending = resolve_temporal_truth("C4", [future], subject_ref="band_event", as_of="2026-08-02")
    activated = resolve_temporal_truth(
        "C4",
        [{**future, "authority_status": "OPERATOR_ACTIVATED", "operator_authority_ref": "operator:terminal:activate", "transition_status": "OPERATOR_ACTIVATED"}],
        subject_ref="band_event",
        as_of="2026-08-02",
    )

    assert pending["transition"]["activated"] is False
    assert pending["direct_answer"]["value_known"] is False
    assert activated["transition"]["activated"] is True
    assert activated["direct_answer"]["typed_value"]["minor_units"] == 2000000


def test_lamd_fixture_keeps_june_paid_history_separate_from_july_open_truth() -> None:
    june = _fact(
        "lamd:2026-06:paid",
        subject_ref="live_arts_md_speaker_rental_receivable",
        metric_ref="receivable_minor_units",
        time_domain="HISTORICAL_OBSERVED",
        typed_value={"minor_units": 10000, "currency": "USD", "payment_status": "paid"},
        valid_from="2026-06-16",
        valid_until="2026-06-30",
        source_refs=["operator-graded:june-settlement"],
    )
    july = _fact(
        "lamd:2026-07:open",
        subject_ref="live_arts_md_speaker_rental_receivable",
        metric_ref="receivable_minor_units",
        time_domain="CURRENT_DECLARED",
        typed_value={"minor_units": 10000, "currency": "USD", "payment_status": "open"},
        valid_from="2026-07-18",
        valid_until=None,
        authority_status="DECLARED",
        operator_authority_ref="operator:terminal:lamd-post",
        source_refs=["g2c:invoice:2026-1004", "gmail:19f75b64a21e0e91"],
    )

    answer = resolve_temporal_truth(
        "C2",
        [june, july],
        subject_ref="live_arts_md_speaker_rental_receivable",
        as_of="2026-07-19",
    )

    assert answer["direct_answer"]["typed_value"]["payment_status"] == "open"
    assert answer["historical_context"][0]["typed_value"]["payment_status"] == "paid"
    assert answer["machine_proof"]["historical_promoted_to_current"] is False
    assert answer["machine_proof"]["time_domains_blended"] is False


def test_typed_seed_rows_are_v12_bound_and_history_is_not_current_policy() -> None:
    payload = load_price_truth_facts()
    facts = payload["facts"]
    reynolds = next(fact for fact in facts if "reynolds_tavern" in fact.fact_ref)
    current = next(
        fact
        for fact in facts
        if fact.subject_ref == "solo_acoustic"
        and fact.time_domain == "CURRENT_PROVISIONAL"
    )

    assert payload["doctrine_ref"] == "gig_business_doctrine:v1.2"
    assert payload["status"] == "candidate_not_accepted_truth"
    assert reynolds.time_domain == "HISTORICAL_OBSERVED"
    assert current.value_known is False
    assert payload["source_sha256"].startswith("sha256:")
