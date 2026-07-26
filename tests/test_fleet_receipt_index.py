from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import fleet_receipt_index as receipts
from operator_surface_guard import guard_operator_reply


def _descriptor(
    *,
    provider: str = "workflow",
    raw_ref: str = "operator_review_receipt:0123456789abcdef",
    durable: bool = True,
    happened: str = "Cassandra staged the Live Arts invoice handoff for review.",
) -> receipts.ReceiptDescriptor:
    return receipts.build_receipt_descriptor(
        provider=provider,
        raw_ref=raw_ref,
        what_happened=happened,
        status="staged and unclaimed",
        occurred_at="2026-07-11T18:14:00+00:00",
        authority_summary="No send or business-action authority was granted.",
        no_action_facts=(
            "Nothing was sent.",
            "Nothing was posted to the ledger or changed.",
        ),
        durable=durable,
    )


def _register(
    db_path: Path,
    descriptor: receipts.ReceiptDescriptor,
    *,
    surface: str = "telegram",
    bot_identity: str = "maestro",
    chat_id: str = "chat-42",
    source_message_id: str = "in-101",
    delivered_message_id: str = "out-202",
    delivery_succeeded: bool = True,
) -> receipts.RegistrationResult:
    return receipts.register_delivered_receipt(
        descriptor,
        surface=surface,
        bot_identity=bot_identity,
        chat_id=chat_id,
        source_message_id=source_message_id,
        delivered_message_id=delivered_message_id,
        delivery_succeeded=delivery_succeeded,
        delivered_at="2026-07-11T18:14:02+00:00",
        db_path=db_path,
    )


def test_failed_delivery_does_not_create_or_mutate_an_index(tmp_path: Path) -> None:
    db_path = tmp_path / "not-created" / "fleet.sqlite3"

    result = _register(db_path, _descriptor(), delivery_succeeded=False)

    assert result == receipts.RegistrationResult(
        outcome="delivery_not_succeeded",
        registered=False,
        alias="",
    )
    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_failed_text_delivery_does_not_create_or_mutate_an_index(tmp_path: Path) -> None:
    db_path = tmp_path / "not-created" / "fleet.sqlite3"

    result = receipts.register_delivered_text_receipt(
        surface="operator_maestro_chat",
        bot_identity="maestro",
        chat_id="chat-42",
        source_message_id="1665",
        delivered_message_id="9005",
        source_request_id="maestro_telegram_1665_ce0ca2b9fad1",
        delivered_text="Final workflow answer.",
        delivery_succeeded=False,
        db_path=db_path,
    )

    assert result.registered is False
    assert result.outcome == "delivery_not_succeeded"
    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_successful_text_delivery_records_exact_hash_without_raw_text(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    delivered_text = "Final workflow answer."

    result = receipts.register_delivered_text_receipt(
        surface="operator_maestro_chat",
        bot_identity="maestro",
        chat_id="chat-42",
        source_message_id="1665",
        delivered_message_id="9005",
        source_request_id="maestro_telegram_1665_ce0ca2b9fad1",
        delivered_text=delivered_text,
        delivery_succeeded=True,
        delivered_at="2026-07-16T17:42:06+00:00",
        db_path=db_path,
    )

    expected_hash = "sha256:" + hashlib.sha256(delivered_text.encode("utf-8")).hexdigest()
    assert result.registered is True
    assert result.delivered_text_hash == expected_hash
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM fleet_delivered_text_receipts").fetchone()
    assert row is not None
    assert row["source_request_id"] == "maestro_telegram_1665_ce0ca2b9fad1"
    assert row["delivered_text_hash"] == expected_hash
    assert row["delivered_text_length"] == len(delivered_text)
    assert delivered_text not in dict(row).values()


def test_v2_text_delivery_records_full_actor_carrier_tuple_and_safe_mirror(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    mirror_path = tmp_path / "mirror" / "fleet-delivered-v2.jsonl"
    delivered_text = "Luna prepared the bounded answer."
    token_fingerprint = "sha256:" + "a" * 64

    result = receipts.register_delivered_text_receipt_v2(
        effective_service="maestro-listener.service",
        effective_surface="operator_maestro_chat",
        effective_bot_identity="maestro",
        token_owner_label="maestro_bot_token",
        token_fingerprint=token_fingerprint,
        chat_id="chat-42",
        source_message_id="1665",
        delivered_message_id="9005",
        source_request_id="maestro_telegram_1665_ce0ca2b9fad1",
        response_author="luna",
        carrier_identity="maestro",
        transport="telegram",
        delivered_text=delivered_text,
        delivery_succeeded=True,
        delivered_at="2026-07-18T14:20:00+00:00",
        mirror_path=mirror_path,
        db_path=db_path,
    )

    expected_hash = "sha256:" + hashlib.sha256(delivered_text.encode("utf-8")).hexdigest()
    assert result.registered is True
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM fleet_delivered_text_receipts_v2"
        ).fetchone()
    assert row is not None
    assert row["schema_version"] == "fleet_delivered_text_receipt_v2"
    assert row["effective_service"] == "maestro-listener.service"
    assert row["effective_surface"] == "operator_maestro_chat"
    assert row["effective_bot_identity"] == "maestro"
    assert row["token_owner_label"] == "maestro_bot_token"
    assert row["token_fingerprint"] == token_fingerprint
    assert row["response_author"] == "luna"
    assert row["carrier_identity"] == "maestro"
    assert row["delivered_text_hash"] == expected_hash

    mirrored = json.loads(mirror_path.read_text(encoding="utf-8").strip())
    assert mirrored["schema_version"] == "fleet_delivered_text_receipt_v2"
    assert mirrored["delivered_message_id"] == "9005"
    assert mirrored["delivered_text_hash"] == expected_hash
    assert mirrored["chat_binding_hash"].startswith("sha256:")
    assert "chat_id" not in mirrored
    assert delivered_text not in mirror_path.read_text(encoding="utf-8")


def test_failed_v2_text_delivery_leaves_no_sqlite_or_mirror(tmp_path: Path) -> None:
    db_path = tmp_path / "not-created" / "fleet.sqlite3"
    mirror_path = tmp_path / "not-created" / "mirror.jsonl"

    result = receipts.register_delivered_text_receipt_v2(
        effective_service="chief-listener.service",
        effective_surface="chief_listener",
        effective_bot_identity="chief",
        token_owner_label="chief_bot_token",
        token_fingerprint="sha256:" + "b" * 64,
        chat_id="chat-42",
        source_message_id="1665",
        delivered_message_id="9005",
        source_request_id="chief_telegram_1665_ce0ca2b9fad1",
        response_author="chief",
        carrier_identity="chief",
        transport="telegram",
        delivered_text="Not delivered.",
        delivery_succeeded=False,
        mirror_path=mirror_path,
        db_path=db_path,
    )

    assert result.outcome == "delivery_not_succeeded"
    assert result.registered is False
    assert not db_path.exists()
    assert not mirror_path.exists()


def test_only_literal_true_counts_as_delivery_success(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"

    result = _register(  # type: ignore[arg-type]
        db_path,
        _descriptor(),
        delivery_succeeded="true",
    )

    assert result.outcome == "delivery_not_succeeded"
    assert not db_path.exists()


def test_nondurable_pointer_is_neither_advertised_nor_registered(tmp_path: Path) -> None:
    descriptor = _descriptor(
        raw_ref="contract:guided-review-adapter-error",
        durable=False,
    )
    db_path = tmp_path / "fleet.sqlite3"

    assert receipts.human_receipt_hint(descriptor) == ""
    result = _register(db_path, descriptor)

    assert result.outcome == "provider_receipt_not_durable"
    assert result.registered is False
    assert result.alias == ""
    assert not db_path.exists()


def test_durable_flag_must_be_a_real_boolean() -> None:
    with pytest.raises(ValueError, match="durable must be a boolean"):
        receipts.build_receipt_descriptor(  # type: ignore[arg-type]
            provider="workflow",
            raw_ref="workflow:one",
            what_happened="Cassandra staged a handoff.",
            status="staged",
            occurred_at="2026-07-11T18:14:00+00:00",
            authority_summary="No authority was granted.",
            no_action_facts=("Nothing was sent.",),
            durable="false",
        )


@pytest.mark.parametrize(
    ("provider", "backend"),
    [
        ("workflow", "workflow_package_queue"),
        ("typed_contract", "typed_contract_decision"),
        ("origin_output", "origin_bound_output"),
        ("proposal_factory", "proposal_factory_truth"),
    ],
)
def test_closed_provider_set_maps_to_one_owning_backend(
    tmp_path: Path,
    provider: str,
    backend: str,
) -> None:
    descriptor = _descriptor(
        provider=provider,
        raw_ref=f"{provider}:durable-ref-1",
    )
    assert descriptor.owning_backend == backend

    registered = _register(tmp_path / f"{provider}.sqlite3", descriptor)

    assert registered.registered is True
    assert registered.alias.startswith("R-")


def test_unknown_provider_is_rejected_before_any_database_write(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported receipt provider"):
        _descriptor(provider="invented_backend")
    assert list(tmp_path.iterdir()) == []


def test_schema_check_also_rejects_an_unknown_provider(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    registered = _register(db_path, _descriptor())
    assert registered.registered

    with sqlite3.connect(db_path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO fleet_receipt_deliveries (
              delivery_key, alias, provider, owning_backend, raw_ref,
              surface, bot_identity, chat_id, source_message_id,
              delivered_message_id, delivered_at, what_happened, status,
              occurred_at, authority_summary, no_action_facts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "bad-key",
                "R-BADBAD",
                "invented_backend",
                "invented_backend",
                "raw",
                "telegram",
                "maestro",
                "chat",
                "in",
                "out",
                "2026-07-11T18:14:00+00:00",
                "Something happened.",
                "done",
                "2026-07-11T18:14:00+00:00",
                "No authority was granted.",
                "[]",
            ),
        )


def test_alias_collision_retries_without_overwriting_first_delivery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "fleet.sqlite3"

    def forced_alias(delivery_key: str, attempt: int) -> str:
        del delivery_key
        return "R-AAAAAA" if attempt == 0 else "R-BBBBBB"

    monkeypatch.setattr(receipts, "_alias_candidate", forced_alias)
    first = _register(
        db_path,
        _descriptor(raw_ref="workflow:first"),
        delivered_message_id="out-1",
    )
    second = _register(
        db_path,
        _descriptor(raw_ref="workflow:second"),
        delivered_message_id="out-2",
    )

    assert first.alias == "R-AAAAAA"
    assert second.alias == "R-BBBBBB"
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT alias, raw_ref FROM fleet_receipt_deliveries ORDER BY id"
        ).fetchall() == [
            ("R-AAAAAA", "workflow:first"),
            ("R-BBBBBB", "workflow:second"),
        ]


def test_concurrent_registrations_serialize_alias_collisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    # Initialize the schema before exercising the delivery-time race; the
    # contention under test is two successful post-send registrations.
    _register(
        db_path,
        _descriptor(raw_ref="workflow:seed"),
        delivered_message_id="seed-out",
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute("DELETE FROM fleet_receipt_deliveries")

    def forced_alias(delivery_key: str, attempt: int) -> str:
        del delivery_key
        return "R-AAAAAA" if attempt == 0 else "R-BBBBBB"

    monkeypatch.setattr(receipts, "_alias_candidate", forced_alias)
    barrier = threading.Barrier(2)

    def register_one(index: int) -> receipts.RegistrationResult:
        barrier.wait(timeout=2.0)
        return _register(
            db_path,
            _descriptor(raw_ref=f"workflow:concurrent-{index}"),
            source_message_id=f"in-{index}",
            delivered_message_id=f"out-{index}",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register_one, (1, 2)))

    assert {result.alias for result in results} == {"R-AAAAAA", "R-BBBBBB"}
    assert all(result.registered for result in results)
    assert receipts.FleetReceiptIndex(db_path).count() == 2


def test_registration_is_idempotent_and_restart_safe(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    descriptor = _descriptor()
    first_process = receipts.FleetReceiptIndex(db_path)
    first = first_process.register(
        descriptor,
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        source_message_id="in-101",
        delivered_message_id="out-202",
        delivery_succeeded=True,
        delivered_at="2026-07-11T18:14:02+00:00",
    )

    restarted_process = receipts.FleetReceiptIndex(db_path)
    duplicate = restarted_process.register(
        descriptor,
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        source_message_id="in-101",
        delivered_message_id="out-202",
        delivery_succeeded=True,
        delivered_at="2026-07-11T18:15:00+00:00",
    )

    assert first.outcome == "registered"
    assert duplicate.outcome == "already_registered"
    assert duplicate.alias == first.alias
    assert restarted_process.count() == 1


def test_reply_bound_resolution_survives_restart_and_never_renders_raw_refs(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    descriptor = _descriptor()
    registered = _register(db_path, descriptor)

    restarted_process = receipts.FleetReceiptIndex(db_path)
    resolution = restarted_process.resolve(
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        reply_to_message_id="out-202",
    )

    assert resolution.outcome == "found"
    assert resolution.aliases == (registered.alias,)
    assert registered.alias in resolution.text
    assert descriptor.raw_ref not in resolution.text
    assert descriptor.owning_backend not in resolution.text
    assert "Cassandra staged the Live Arts invoice handoff" in resolution.text
    assert "staged and unclaimed" in resolution.text
    assert "No send or business-action authority was granted" in resolution.text
    assert "Nothing was sent" in resolution.text
    assert guard_operator_reply(resolution.text) == resolution.text


def test_explicit_alias_is_case_insensitive_but_never_crosses_a_binding(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    registered = _register(db_path, _descriptor())
    index = receipts.FleetReceiptIndex(db_path)

    same_chat = index.resolve(
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        alias=registered.alias.lower(),
    )
    wrong_chat = index.resolve(
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-99",
        alias=registered.alias,
    )
    wrong_bot = index.resolve(
        surface="telegram",
        bot_identity="chief",
        chat_id="chat-42",
        alias=registered.alias,
    )
    wrong_surface = index.resolve(
        surface="mission_control",
        bot_identity="maestro",
        chat_id="chat-42",
        alias=registered.alias,
    )

    assert same_chat.outcome == "found"
    for denied in (wrong_chat, wrong_bot, wrong_surface):
        assert denied.outcome == "cross_chat_denied"
        assert registered.alias not in denied.text
        assert _descriptor().raw_ref not in denied.text


def test_same_chat_alias_with_the_wrong_reply_target_is_not_called_cross_chat(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    registered = _register(db_path, _descriptor())

    resolution = receipts.FleetReceiptIndex(db_path).resolve(
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        alias=registered.alias,
        reply_to_message_id="a-different-message",
    )

    assert resolution.outcome == "not_found"


def test_reply_message_ids_are_scoped_to_surface_bot_and_chat(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    _register(db_path, _descriptor(), delivered_message_id="shared-telegram-id")

    resolution = receipts.FleetReceiptIndex(db_path).resolve(
        surface="telegram",
        bot_identity="chief",
        chat_id="different-chat",
        reply_to_message_id="shared-telegram-id",
    )

    assert resolution.outcome == "not_found"
    assert "another chat" not in resolution.text.lower()


def test_multiple_candidates_clarify_instead_of_guessing(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    first_descriptor = _descriptor(
        raw_ref="workflow:first",
        happened="Cassandra staged the first invoice handoff.",
    )
    second_descriptor = _descriptor(
        provider="typed_contract",
        raw_ref="contract:second",
        happened="Chief preserved the open billing step.",
    )
    first = _register(
        db_path,
        first_descriptor,
        delivered_message_id="out-1",
    )
    second = _register(
        db_path,
        second_descriptor,
        delivered_message_id="out-2",
    )

    resolution = receipts.FleetReceiptIndex(db_path).resolve(
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
    )

    assert resolution.outcome == "clarify"
    assert set(resolution.aliases) == {first.alias, second.alias}
    assert first.alias in resolution.text
    assert second.alias in resolution.text
    assert "reply to the original message" in resolution.text.lower()
    assert first_descriptor.raw_ref not in resolution.text
    assert second_descriptor.raw_ref not in resolution.text
    assert guard_operator_reply(resolution.text) == resolution.text


def test_multiple_receipts_on_one_delivered_message_also_clarify(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    _register(db_path, _descriptor(raw_ref="workflow:one"))
    _register(
        db_path,
        _descriptor(provider="typed_contract", raw_ref="contract:two"),
    )

    resolution = receipts.FleetReceiptIndex(db_path).resolve(
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        reply_to_message_id="out-202",
    )

    assert resolution.outcome == "clarify"
    assert len(resolution.aliases) == 2


def test_long_chat_history_produces_a_bounded_clarification(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    for index in range(8):
        _register(
            db_path,
            _descriptor(
                raw_ref=f"workflow:bounded-{index}",
                happened=f"Cassandra staged handoff number {index}.",
            ),
            delivered_message_id=f"out-{index}",
        )

    resolution = receipts.FleetReceiptIndex(db_path).resolve(
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
    )

    assert resolution.outcome == "clarify"
    assert len(resolution.aliases) == 5
    assert "More delivered records exist" in resolution.text
    assert guard_operator_reply(resolution.text) == resolution.text


def test_bare_lookup_with_one_same_chat_candidate_returns_it(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    registered = _register(db_path, _descriptor())

    resolution = receipts.resolve_receipt_lookup(
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        db_path=db_path,
    )

    assert resolution.outcome == "found"
    assert resolution.aliases == (registered.alias,)


def test_corrupt_index_is_unavailable_not_a_false_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    db_path.write_bytes(b"this is not sqlite")

    with pytest.raises(receipts.ReceiptIndexUnavailable, match="index unavailable"):
        receipts.resolve_receipt_lookup(
            surface="telegram",
            bot_identity="maestro",
            chat_id="chat-42",
            db_path=db_path,
        )


def test_locked_index_is_unavailable_not_a_false_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    _register(db_path, _descriptor())

    with sqlite3.connect(db_path) as setup:
        setup.execute("PRAGMA journal_mode=DELETE")
    with sqlite3.connect(db_path) as blocker:
        blocker.execute("PRAGMA locking_mode=EXCLUSIVE")
        blocker.execute("BEGIN EXCLUSIVE")
        blocker.execute(
            "UPDATE fleet_receipt_deliveries SET status=status WHERE id=1"
        )
        with pytest.raises(receipts.ReceiptIndexUnavailable, match="index unavailable"):
            receipts.resolve_receipt_lookup(
                surface="telegram",
                bot_identity="maestro",
                chat_id="chat-42",
                db_path=db_path,
            )


def test_human_renderer_fails_closed_when_surface_check_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    _register(db_path, _descriptor())

    import operator_surface_guard

    monkeypatch.setattr(
        operator_surface_guard,
        "check_operator_surface",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("guard offline")),
    )
    with pytest.raises(ValueError, match="could not be validated"):
        receipts.resolve_receipt_lookup(
            surface="telegram",
            bot_identity="maestro",
            chat_id="chat-42",
            db_path=db_path,
        )


@pytest.mark.parametrize(
    ("text", "expected_alias"),
    [
        ("show receipt", ""),
        ("show the receipt", ""),
        ("please show me the receipt", ""),
        ("Show receipt R-7K4Q2M", "R-7K4Q2M"),
        ("what is receipt r-7k4q2m?", "R-7K4Q2M"),
    ],
)
def test_receipt_request_parser_accepts_bounded_human_variants(
    text: str,
    expected_alias: str,
) -> None:
    parsed = receipts.parse_receipt_request(text)
    assert parsed is not None
    assert parsed.alias == expected_alias


@pytest.mark.parametrize(
    "text",
    [
        "how are receipts stored?",
        "show receipt handling code",
        "the receipt says paid",
        "receipt",
        "show the invoice",
    ],
)
def test_receipt_request_parser_does_not_steal_near_misses(text: str) -> None:
    assert receipts.parse_receipt_request(text) is None


def test_request_parser_and_resolver_use_reply_binding(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    registered = _register(db_path, _descriptor())

    resolution = receipts.resolve_receipt_request(
        "show receipt",
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        reply_to_message_id="out-202",
        db_path=db_path,
    )

    assert resolution is not None
    assert resolution.outcome == "found"
    assert resolution.aliases == (registered.alias,)
    assert receipts.resolve_receipt_request(
        "how are receipts stored?",
        surface="telegram",
        bot_identity="maestro",
        chat_id="chat-42",
        db_path=db_path,
    ) is None


def test_human_hint_and_machine_disclosure_keep_raw_ref_on_opposite_sides() -> None:
    descriptor = _descriptor()
    hint = receipts.human_receipt_hint(descriptor)
    disclosure = receipts.machine_receipt_disclosure(descriptor)

    assert hint == "Say “show receipt” for the delivery record."
    assert descriptor.raw_ref not in hint
    assert descriptor.owning_backend not in hint
    assert guard_operator_reply(hint) == hint
    assert disclosure["provider"] == "workflow"
    assert disclosure["owning_backend"] == "workflow_package_queue"
    assert disclosure["raw_ref"] == descriptor.raw_ref
    assert "prompt" not in disclosure


def test_operator_prompt_is_not_a_parameter_column_or_persisted_value(tmp_path: Path) -> None:
    db_path = tmp_path / "fleet.sqlite3"
    raw_operator_prompt = "UNIQUE RAW PROMPT: delete every ledger row 6f0d7d2d"
    _register(db_path, _descriptor())

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(fleet_receipt_deliveries)")
        }
    database_bytes = db_path.read_bytes()

    assert not any("prompt" in column or "request_text" in column for column in columns)
    assert raw_operator_prompt.encode("utf-8") not in database_bytes


def test_public_summary_fields_cannot_embed_the_raw_reference() -> None:
    raw_ref = "operator_review_receipt:0123456789abcdef"
    with pytest.raises(ValueError, match="raw receipt reference"):
        _descriptor(raw_ref=raw_ref, happened=f"I staged {raw_ref} for review.")


def test_public_summary_fields_cannot_embed_the_owning_backend() -> None:
    with pytest.raises(ValueError, match="owning backend"):
        _descriptor(happened="workflow_package_queue staged a handoff for review.")


def test_generated_aliases_are_short_human_safe_and_not_hash_guard_triggers(
    tmp_path: Path,
) -> None:
    registered = _register(tmp_path / "fleet.sqlite3", _descriptor())

    assert re.fullmatch(r"R-[2-9A-HJKMNP-Z]{6,12}", registered.alias)
    assert guard_operator_reply(f"Receipt {registered.alias} is available.") == (
        f"Receipt {registered.alias} is available."
    )
