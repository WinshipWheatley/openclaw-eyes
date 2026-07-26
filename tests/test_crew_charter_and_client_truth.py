"""The crew doctrine, enforced rather than described.

Three claims are under test, one per seam:

* every agent is told its post and orders on every packet (crew_charter)
* an internal excuse cannot reach a client (client_copy_guard, at the send seam)
* the client's words reach Chief unsoftened (client_repair_escalation)
"""

from __future__ import annotations

import json
from pathlib import Path

import client_copy_guard as guard
import client_repair_escalation as escalation
import crew_charter


# --------------------------------------------------------------------------
# The charter: every agent knows which chair it is in
# --------------------------------------------------------------------------


def test_every_officer_on_the_roster_gets_a_post_and_orders() -> None:
    roster = crew_charter.load_roster()
    assert roster, "roster read-model must be readable"

    for officer in roster["crew"]:
        delivery = crew_charter.build_charter_delivery(agent_id=officer["agent_id"])
        assert delivery["status"] == crew_charter.STATUS_READY
        assert delivery["post"], f"{officer['agent_id']} has no post"
        assert delivery["standing_orders"], f"{officer['agent_id']} has no orders"
        assert delivery["escalation"]["path"]


def test_cassandra_is_told_the_client_boundary_is_hers() -> None:
    delivery = crew_charter.build_charter_delivery(agent_id="cassandra")

    assert "client boundary" in delivery["post"].lower()
    assert "cassandra" in delivery["packet_text"].lower()


def test_chief_is_told_he_runs_the_ship() -> None:
    delivery = crew_charter.build_charter_delivery(agent_id="chief")

    assert "runs the ship" in delivery["post"].lower()


def test_an_order_naming_an_officer_is_delivered_to_them_first() -> None:
    """A truncated packet must keep the order most specifically about the reader."""

    orders = crew_charter.build_charter_delivery(agent_id="cassandra")["standing_orders"]

    assert "cassandra" in orders[0].lower()


def test_the_charter_stays_small_enough_to_ride_in_every_packet(tmp_path: Path) -> None:
    for agent in ("maestro", "chief", "cassandra", "niles", "guardian", "hermes"):
        text = crew_charter.build_charter_delivery(agent_id=agent)["packet_text"]
        assert len(text) <= crew_charter.CHARTER_TEXT_CHARS


def test_a_missing_roster_says_so_instead_of_pretending_there_are_no_orders(
    tmp_path: Path,
) -> None:
    """Silence would read as "no orders". The floors have to survive the outage."""

    delivery = crew_charter.build_charter_delivery(
        agent_id="cassandra", path=tmp_path / "gone.json"
    )

    assert delivery["status"] == crew_charter.STATUS_UNAVAILABLE
    assert "UNAVAILABLE" in delivery["packet_text"]
    assert "never route around a gate" in delivery["packet_text"]


def test_the_charter_reaches_the_agent_through_the_packet_engine() -> None:
    import packet_engine

    packet = packet_engine.build_agent_packet(
        agent="cassandra",
        question="what is outstanding for live arts md",
        legacy_builder=lambda **_: {"facts": [], "packet_text": "", "source_refs": ()},
    )

    assert packet["machine_proof"]["crew_charter_status"] == crew_charter.STATUS_READY
    assert "crew_charter" in packet["machine_proof"]["packet_engine_sections"]
    assert "client boundary" in packet["packet_text"].lower()
    assert any(row.get("topic") == "crew_charter" for row in packet["facts"])


def test_standing_orders_are_not_mistaken_for_knowing_the_subject() -> None:
    """The charter says "never route around a gate". That must not make a packet
    look like it knows how TH-U routes into Logic Pro.

    Identity is not coverage — the same rule persona and doctrine already live
    under. One predicate decides it for every seam, so a future section cannot
    re-open the anti-confabulation gate by being added in only one place.
    """

    import packet_engine

    for topic in ("persona_core", "gig_business_doctrine", "crew_charter"):
        assert packet_engine.is_identity_fact({"topic": topic, "fact_id": f"{topic}:x"})
    assert not packet_engine.is_identity_fact({"topic": "invoice", "fact_id": "invoice:1"})


def test_the_coverage_gate_still_catches_an_uncovered_target() -> None:
    """End-to-end: a packet carrying only identity still reports the gap."""

    import agent_spawn

    packet = {
        "facts": [
            crew_charter.charter_fact(crew_charter.build_charter_delivery(agent_id="niles"))
        ]
    }
    gap = agent_spawn._coverage_gap(
        packet, target="explain what TH-U is and how it routes into Logic Pro X", question=""
    )

    assert gap.startswith("packet_does_not_cover_target")


def test_doer_narrowing_never_strips_the_charter() -> None:
    """An assignment narrows breadth. It must not narrow away the orders."""

    import packet_engine

    packet = packet_engine.build_agent_packet(
        agent="cassandra",
        question="draft the invoice email",
        consumer_kind="spawned",
        target="live_arts_md",
        legacy_builder=lambda **_: {
            "facts": [
                {"topic": "unrelated", "label": "weather", "value": "clear"},
                {"topic": "invoice", "label": "amount", "value": "$100"},
            ],
            "packet_text": "",
            "source_refs": (),
        },
    )

    assert any(row.get("topic") == "crew_charter" for row in packet["facts"])


# --------------------------------------------------------------------------
# The copy guard: the excuse cannot get out
# --------------------------------------------------------------------------


def test_the_operators_own_sentence_is_blocked_verbatim() -> None:
    verdict = guard.review_client_copy(
        body="Sorry for the wait — our AI is a bit hoinky and we're working it out.",
        recipient="client@example.com",
    )

    assert verdict["blocked"]
    assert verdict["remedy"]


def test_apparatus_alone_is_not_an_excuse() -> None:
    """A client may hear about our system; just not as the reason it is late."""

    assert guard.is_client_safe(
        "Your invoice is in our system and payment is due on the 16th."
    )


def test_working_on_it_about_the_actual_work_is_fine() -> None:
    """The gate is precision, not friction. Real work talk must pass."""

    assert guard.is_client_safe(
        "We're working on the final mix and will have it to you Thursday."
    )


def test_blaming_the_software_is_caught_however_it_is_worded() -> None:
    for excuse in (
        "The automation misfired on our end.",
        "Our platform has been glitchy this week.",
        "The integration errored, so the invoice never went out.",
        "Our new system is still learning your account.",
        "Please bear with us while we sort this.",
        "Apologies for the technical difficulties.",
    ):
        assert not guard.is_client_safe(excuse), f"not caught: {excuse}"


def test_internal_vocabulary_never_faces_a_client() -> None:
    """The client knows Clara Reid. Cassandra is an internal name."""

    verdict = guard.review_client_copy(body="Cassandra will send the packet over shortly.")

    kinds = {row["kind"] for row in verdict["violations"]}
    assert "leak" in kinds
    assert verdict["blocked"]


def test_a_clean_client_email_passes_untouched() -> None:
    verdict = guard.review_client_copy(
        subject="Invoice 2026-1004 — Live Arts MD",
        body=(
            "Hi Megan,\n\nAttached is the monthly speaker rental invoice for $100, "
            "due on receipt. Thanks as always.\n\nClara Reid"
        ),
        recipient="megan@example.com",
    )

    assert not verdict["blocked"]
    assert verdict["violations"] == []


def _reach_the_guard(monkeypatch, executor, tmp_path):
    """Walk an approved, unheld packet right up to the guard.

    Every earlier stop (surface, stale hash, SEND_HOLD, approval) is satisfied,
    so whatever happens next is the copy guard's doing and nothing else's.
    """

    import chief_compose

    monkeypatch.setattr(
        chief_compose,
        "get_packet_approval_state",
        lambda packet_id, **_: {
            "surface": "email_send",
            "stale": False,
            "execution_allowed": True,
            "packet_id": packet_id,
        },
    )
    monkeypatch.setattr(
        executor,
        "ensure_send_hold_sentinel",
        lambda *a, **k: type("S", (), {"send_hold_active": False})(),
    )
    monkeypatch.setattr(executor, "_email_receipt", _recording_receipt)
    monkeypatch.setattr(
        executor, "_file_blocked_copy_repair", lambda payload, review: {"filed": True}
    )


def _recording_receipt(**kwargs):
    from compose_contract import ExecutionReceipt

    return ExecutionReceipt(
        packet_id=kwargs.get("packet_id", ""),
        surface="email_send",
        ok=bool(kwargs.get("ok")),
        detail=str(kwargs.get("detail") or ""),
        meta=dict(kwargs.get("meta") or {}),
    )


def test_the_send_seam_blocks_the_excuse_and_never_calls_the_provider(
    monkeypatch, tmp_path
) -> None:
    """The claim is structural: the words do not leave the building.

    Not "the review says blocked" — the provider is never invoked.
    """

    import email_send_executor as executor

    _reach_the_guard(monkeypatch, executor, tmp_path)
    called: list[dict] = []

    receipt = executor.execute_email_send_packet(
        packet_id="pkt-1",
        outbound_payload={
            "to": "megan@example.com",
            "subject": "Invoice",
            "body": "Sorry — our system is being hoinky and we're working it out.",
        },
        email_sender=lambda **kwargs: called.append(kwargs) or {"ok": True},
    )

    assert called == [], "the provider was called with an excuse in the body"
    assert not receipt.ok
    assert receipt.meta["client_copy_review"]["blocked"]
    assert receipt.meta["external_send_performed"] is False


def test_the_same_seam_lets_clean_copy_through(monkeypatch, tmp_path) -> None:
    """The guard must not be friction: a clean invoice still sends."""

    import email_send_executor as executor

    _reach_the_guard(monkeypatch, executor, tmp_path)
    called: list[dict] = []

    executor.execute_email_send_packet(
        packet_id="pkt-2",
        outbound_payload={
            "to": "megan@example.com",
            "subject": "Invoice 2026-1004 — Live Arts MD",
            "body": "Hi Megan,\n\nAttached is the $100 monthly rental invoice, due on receipt.\n\nClara Reid",
        },
        email_sender=lambda **kwargs: called.append(kwargs) or {"ok": True, "id": "x"},
    )

    assert len(called) == 1, "clean client copy must still reach the provider"


def test_mail_to_the_operator_is_not_client_copy() -> None:
    """Test-mode loopback is internal. The exemption is recorded, not silent."""

    import email_send_executor as executor

    review = executor._review_client_copy(
        {"to": "winshiplive@gmail.com", "subject": "x", "body": "the AI is hoinky"}
    )

    assert not review["blocked"]
    assert review["exempt_reason"] == "operator_loopback_is_not_client_copy"


def test_a_broken_guard_blocks_rather_than_waves_the_mail_through(monkeypatch) -> None:
    """Fail closed: a guard that cannot run is not permission to send."""

    import builtins

    import email_send_executor as executor

    real_import = builtins.__import__

    def _boom(name, *args, **kwargs):
        if name == "client_copy_guard":
            raise RuntimeError("guard exploded")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _boom)
    review = executor._review_client_copy({"to": "c@example.com", "subject": "", "body": "hello"})

    assert review["blocked"]
    assert "guard exploded" in review["detail"]


# --------------------------------------------------------------------------
# The escalation: Chief hears the client, unsoftened
# --------------------------------------------------------------------------


def test_a_repair_item_carries_the_clients_own_words(tmp_path: Path) -> None:
    queue = tmp_path / "queue.jsonl"
    message = "This is the third time. I'm done hearing about your software."

    result = escalation.escalate_client_dissatisfaction(
        client_ref="live_arts_md",
        client_message=message,
        client_verbatim="I'm done hearing about your software",
        what_broke="Invoice send failed silently three months running.",
        queue_path=queue,
    )

    assert result["status"] == escalation.STATUS_FILED
    assert result["item"]["owner"] == "chief"
    assert result["item"]["reporter"] == "cassandra"
    assert result["item"]["client_verbatim"] == "I'm done hearing about your software"


def test_a_paraphrase_cannot_be_filed_as_the_clients_words(tmp_path: Path) -> None:
    """The softening is the failure. So it is rejected, not merely discouraged."""

    queue = tmp_path / "queue.jsonl"

    result = escalation.escalate_client_dissatisfaction(
        client_ref="live_arts_md",
        client_message="This is the third time. I'm done hearing about your software.",
        client_verbatim="Client would appreciate an update at your convenience.",
        what_broke="Invoice send failed.",
        queue_path=queue,
    )

    assert result["status"] == escalation.STATUS_REJECTED_PARAPHRASE
    assert not result["filed"]
    assert not queue.exists()
    assert result["remedy"]


def test_curly_quotes_and_wrapping_do_not_count_as_paraphrase() -> None:
    """Precision, not pedantry — a real quote must survive a copy-paste."""

    assert escalation.is_verbatim(
        "I'm done hearing about your software",
        "This is the third time.\n  I’m done   hearing about your software.",
    )


def test_spent_patience_is_rated_higher_than_a_late_invoice() -> None:
    assert escalation.assess_severity("This is the third time, it's unacceptable.") == "trust_damage"
    assert escalation.assess_severity("The invoice looks delayed?") == "elevated"
    assert escalation.assess_severity("Got it, thanks.") == "routine"


def test_a_blocked_draft_files_its_own_repair_item(tmp_path: Path) -> None:
    """A block that stops there is a wall. This makes it a self-heal."""

    queue = tmp_path / "queue.jsonl"
    body = "Sorry — our system is being hoinky and we're working it out."
    review = guard.review_client_copy(body=body, recipient="megan@example.com")

    result = escalation.escalate_blocked_copy(
        client_ref="megan@example.com", review=review, draft_body=body, queue_path=queue
    )

    assert result["status"] == escalation.STATUS_FILED
    assert result["item"]["surface"] == "blocked_client_copy"
    assert result["item"]["owner"] == "chief"


def test_chiefs_board_shows_trust_damage_first(tmp_path: Path) -> None:
    queue = tmp_path / "queue.jsonl"
    for verbatim, message in (
        ("the invoice looks delayed", "the invoice looks delayed"),
        ("this is the third time", "this is the third time"),
    ):
        escalation.escalate_client_dissatisfaction(
            client_ref="c",
            client_message=message,
            client_verbatim=verbatim,
            what_broke="x",
            queue_path=queue,
        )

    model = escalation.build_read_model(queue)

    assert model["items"][0]["severity"] == "trust_damage"
    assert model["trust_damage_count"] == 1
    assert model["never"] == "client -> captain-as-developer"


def test_a_rehearsal_never_counts_as_a_client_complaint(tmp_path: Path) -> None:
    """A board that counts drills as real complaints lies about the trust at stake."""

    queue = tmp_path / "queue.jsonl"
    escalation.escalate_client_dissatisfaction(
        client_ref="c", client_message="this is the third time", client_verbatim="third time",
        what_broke="x", queue_path=queue, test_mode=True,
    )
    escalation.escalate_client_dissatisfaction(
        client_ref="c", client_message="the invoice looks delayed",
        client_verbatim="looks delayed", what_broke="y", queue_path=queue,
    )

    model = escalation.build_read_model(queue)

    assert model["open_count"] == 1
    assert model["trust_damage_count"] == 0, "a drill must not inflate trust damage"
    assert model["rehearsal_count"] == 1, "and must not be silently dropped either"
    assert len(escalation.load_queue(queue)) == 2, "the queue keeps both for audit"


def test_the_harness_picks_the_quote_not_the_agent(tmp_path: Path) -> None:
    """Asked to summarise, a model reaches for the politest line. So it is not asked."""

    message = (
        "Hi, hope you're well. Thanks for sending that over. "
        "This is the third time the invoice has been late and it's unacceptable. "
        "Let me know when you can."
    )

    verdict = escalation.detect_dissatisfaction(message)

    assert verdict["escalate"]
    assert verdict["severity"] == "trust_damage"
    assert "unacceptable" in verdict["verbatim"]
    assert "hope you're well" not in verdict["verbatim"]


def test_a_happy_client_does_not_get_escalated(tmp_path: Path) -> None:
    """The gate is precision. A thank-you must not open a repair ticket."""

    queue = tmp_path / "queue.jsonl"
    result = escalation.escalate_from_message(
        client_ref="c",
        client_message="Got it, thanks so much — looks great.",
        what_broke="n/a",
        queue_path=queue,
    )

    assert result["status"] == "NO_ESCALATION_NEEDED"
    assert not queue.exists()


def test_filing_from_a_raw_message_quotes_it_verbatim(tmp_path: Path) -> None:
    queue = tmp_path / "queue.jsonl"
    message = "I'm still waiting on this. Every time I have to chase you."

    result = escalation.escalate_from_message(
        client_ref="live_arts_md",
        client_message=message,
        what_broke="LAMD auto-send did not fire on the 16th.",
        queue_path=queue,
    )

    assert result["status"] == escalation.STATUS_FILED
    assert escalation.is_verbatim(result["item"]["client_verbatim"], message)
    assert result["item"]["severity"] == "trust_damage"

