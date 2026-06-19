import reynolds_gig_setup_status as reynolds_status


def test_reynolds_gig_setup_status_is_read_only_eight_lane_status():
    payload = reynolds_status.build_reynolds_gig_setup_status(
        generated_at="2026-06-19T00:00:00+00:00"
    )

    assert payload["schema_version"] == reynolds_status.SCHEMA_VERSION
    assert payload["machine_proof"]["eight_lanes_present"] is True
    assert payload["machine_proof"]["external_send_false"] is True
    assert payload["machine_proof"]["ledger_mutation_false"] is True
    assert payload["machine_proof"]["reply_watch_not_overclaimed"] is True
    assert payload["authority_flags"]["external_send_performed"] is False
    assert payload["authority_flags"]["calendar_mutation_performed"] is False
    assert payload["authority_flags"]["contact_mutation_performed"] is False
    assert payload["authority_flags"]["invoice_send_performed"] is False
    assert payload["authority_flags"]["money_movement_performed"] is False


def test_reynolds_gig_setup_answer_does_not_overclaim_actions():
    answer = reynolds_status.format_reynolds_gig_setup_answer(
        "Are we all set for Reynolds Tavern, and what is left to set up?"
    )

    assert answer is not None
    assert "not all-set yet" in answer
    assert "No Coupa is needed" in answer
    assert "Nothing has been sent" in answer
    assert "calendar/contact mutated" in answer
    assert "money-moved" in answer


def test_cassandra_brain_imports_reynolds_gig_setup_status_route():
    import cassandra_brain

    assert cassandra_brain.is_reynolds_gig_setup_query(
        "Where are we with Reynolds setup?"
    )
    assert cassandra_brain.format_reynolds_gig_setup_answer(
        "Where are we with Reynolds setup?"
    )
