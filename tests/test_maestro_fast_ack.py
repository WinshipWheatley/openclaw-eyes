from __future__ import annotations


def test_fast_ack_requires_a_bound_bridge_request_receipt() -> None:
    import action_promise_integrity
    import maestro_listener

    unbound = maestro_listener._bound_fast_ack_text(
        message="let me see the exported pdf proof",
        action_receipt_refs=(),
    )
    bound = maestro_listener._bound_fast_ack_text(
        message="let me see the exported pdf proof",
        action_receipt_refs=("bridge_request:req_1690",),
    )

    assert action_promise_integrity.contains_action_promise(unbound.visible_text) is False
    assert unbound.receipt.substituted is True
    assert bound.receipt.action_binding_present is True
    assert bound.receipt.substituted is False

    final_text = maestro_listener._final_operator_reply(
        bound.visible_text,
        source_request="let me see the exported pdf proof",
        action_receipt_refs=bound.receipt.action_receipt_refs,
    )
    assert final_text == bound.visible_text


def test_fast_ack_configuration_is_enabled_delayed_and_varied() -> None:
    import maestro_listener

    assert maestro_listener._fast_ack_enabled({}) is True
    assert maestro_listener._fast_ack_enabled({"OPENCLAW_FAST_ACK": "0"}) is False
    assert maestro_listener._fast_ack_delay({}) == 3.0
    assert maestro_listener._fast_ack_delay({"OPENCLAW_FAST_ACK_DELAY": "1.25"}) == 1.25
    assert maestro_listener._fast_ack_text(message="one")
    assert maestro_listener._fast_ack_text(message="two")
