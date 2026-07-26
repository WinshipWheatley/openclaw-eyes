import asyncio
import ast
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import maestro_listener


FIXED_NOW = "2026-06-19T15:18:00+00:00"
REPO_ROOT = Path(__file__).resolve().parents[1]
DRIFT_AWARE_ANSWER = (
    "The St. Anne's invoice dry-run passed and nothing was sent. "
    "The June workbook has 7 services totaling $875, while the work-log mirror has 0 confirmed."
)
LOCATOR_ANSWER = (
    "I found one canonical St. Anne's June invoice PDF across 2 verified copies. "
    "It comes from invoice.xlsx sheet June 2026, invoice 3, totals $875, is draft, and was never sent."
)


@pytest.fixture(autouse=True)
def _claimed_update(monkeypatch):
    monkeypatch.setattr(maestro_listener, "claim_listener_update", lambda *args, **kwargs: True)
    monkeypatch.setenv("OPENCLAW_AGENT_VOICE_NOTES", "0")


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeChat:
    def __init__(self, chat_id: int):
        self.id = chat_id


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class FakeUpdate:
    def __init__(self, *, text: str, user_id: int, chat_id: int | None = None, update_id: int = 789):
        self.message = FakeMessage(text)
        self.effective_user = FakeUser(user_id)
        self.effective_chat = FakeChat(user_id if chat_id is None else chat_id)
        self.update_id = update_id


class FakeBot:
    def __init__(self):
        self.actions: list[tuple[int, str]] = []
        self.photos: list[dict] = []

    async def send_chat_action(self, *, chat_id: int, action: str) -> None:
        self.actions.append((chat_id, action))

    async def send_photo(self, **kwargs):
        payload = dict(kwargs)
        payload["photo"] = payload["photo"].read()
        self.photos.append(payload)
        return SimpleNamespace(message_id=9101)


class FakeContext:
    def __init__(self):
        self.bot = FakeBot()


def test_maestro_listener_service_defaults_to_reply_only_egress():
    service = (REPO_ROOT / "systemd/user/maestro-listener.service.in").read_text(encoding="utf-8")

    assert "Environment=OPENCLAW_MAESTRO_REPLY_ONLY=1" in service
    assert (
        "source @REPO_ROOT@/.chief.env && export OPENCLAW_MAESTRO_REPLY_ONLY=1 && exec"
        in service
    )


def test_env_file_loads_maestro_token_without_printing(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("MAESTRO_BOT_TOKEN", raising=False)
    env_path = tmp_path / ".chief.env"
    env_path.write_text("MAESTRO_BOT_TOKEN='fake-maestro-token'\nTELEGRAM_AUTHORIZED_USER_ID=123\n", encoding="utf-8")

    assert maestro_listener.env_value("MAESTRO_BOT_TOKEN", env_path=env_path) == "fake-maestro-token"

    captured = capsys.readouterr()
    assert "fake-maestro-token" not in captured.out
    assert "fake-maestro-token" not in captured.err


def test_bridge_request_has_unique_id_and_full_false_authority_boundary(tmp_path):
    first = maestro_listener.build_operator_maestro_chat_request(
        "what day is it",
        message_id="42",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    second = maestro_listener.build_operator_maestro_chat_request(
        "what day is it",
        message_id="43",
        chat_id=456,
        created_at=FIXED_NOW,
    )

    assert first["request_id"] != second["request_id"]
    assert first["active_surface_ref"] == "operator_maestro_chat"
    assert first["kind"] == "OPERATOR_INSTRUCTION_PACKAGE_REQUEST"
    assert first["request_type"] == "WORKFLOW_PACKAGE_REQUEST_V0"
    assert first["source_surface"] == "mission_control"
    assert first["source_channel"] == "maestro_listener"
    assert first["speaker"] == "Winship"
    assert first["lane"] == "telegram_pc_maestro_listener"
    assert first["relay_origin"] is None
    assert first["actor"] == "operator_winship"
    assert first["message_provenance"] == {
        "speaker": "Winship",
        "lane": "telegram_pc_maestro_listener",
        "relay_origin": None,
        "actor": "operator_winship",
        "surface_ref": "operator_maestro_chat",
        "message_role": "operator_prompt",
    }
    assert first["expected_response_provenance"]["speaker"] == "Maestro"
    assert first["expected_response_provenance"]["actor"] == "maestro"
    assert first["expected_response_provenance"]["processing_receipt_user_visible"] is False
    assert first["correlation"]["request_id"] == first["request_id"]
    assert first["correlation"]["telegram_message_id"] == "42"
    assert first["source_text"] == "what day is it"
    assert first["operator_message"] == "what day is it"
    assert first["payload_hash"]
    assert first["authority_boundary"]
    assert all(value is False for value in first["authority_boundary"].values())
    assert "live_email_send_allowed" in first["authority_boundary"]
    assert "email_send_allowed" in first["authority_boundary"]
    assert "runtime_dispatch_allowed" in first["authority_boundary"]


def test_replay_request_uses_test_actor_and_suppresses_live_delivery():
    request = maestro_listener.build_maestro_chat_replay_request(
        "show the recommended invoice",
        message_id="replay-1711",
        created_at=FIXED_NOW,
    )

    assert request["actor"] == "pc_codex_desktop_replay"
    assert request["speaker"] == "PC Codex Desktop replay"
    assert request["message_provenance"]["actor"] == "pc_codex_desktop_replay"
    assert request["message_provenance"]["message_role"] == "synthetic_replay_prompt"
    assert request["replay_mode"] == "bounded_synthetic"
    assert request["test_actor"] is True
    assert request["delivery_suppressed"] is True
    assert request["correlation"]["telegram_chat_ref"] == "suppressed"
    assert request["telegram_chat_ref"] == "suppressed"
    assert request["no_external_action"] is True
    assert all(value is False for value in request["authority_boundary"].values())
    assert request["payload_hash"] == maestro_listener._content_hash(request)


def test_listener_bridge_request_routes_through_pc_processor_for_date_answer(tmp_path):
    import openclaw_request_processor as processor

    request = maestro_listener.build_operator_maestro_chat_request(
        "what day is it",
        message_id="processor-smoke",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_listener_processor_smoke.json"
    request_path.write_text(maestro_listener.stable_json(request), encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )

    assert response.internal_status == "RESPONSE_READY"
    assert response.request_type == "CHAT"
    assert response.operator_message == f"Today is {date.today().isoformat()} ({date.today().strftime('%A')})."
    assert response.detail_disclosure["message_provenance"]["speaker"] == "Maestro"
    assert response.detail_disclosure["message_provenance"]["actor"] == "maestro"
    assert response.detail_disclosure["message_provenance"]["relay_origin"] is None
    assert response.detail_disclosure["request_message_provenance"]["speaker"] == "Winship"
    assert response.detail_disclosure["correlation"]["source_request_id"] == request["request_id"]
    assert response.detail_disclosure["maestro_frontdoor_routing"]["workflow_package_staged"] is False
    assert response.detail_disclosure["workflow_package_staged"] is False
    assert response.detail_disclosure["email_send_performed"] is False


def test_listener_bridge_request_delivers_capability_readback_not_generic_intro(tmp_path, monkeypatch):
    import maestro_cassandra_responder as maestro
    import openclaw_request_processor as processor

    # Freshness is part of the production status contract.  Keep this bridge
    # test deterministic with an explicitly dated source set instead of
    # depending on whichever ignored read models happen to exist in the
    # developer checkout.
    source_root = tmp_path / "status_sources"
    source_root.mkdir()
    generated_at = f"{date.today().isoformat()}T12:00:00+00:00"
    (source_root / "openclaw_capability_index.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "generic_capabilities": [
                    {
                        "capability_id": "request_processing",
                        "capability_name": "Bounded request processor",
                        "capability_status": "LIVE_IMPLEMENTED",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (source_root / "agent_presence.json").write_text(
        json.dumps({"generated_at": generated_at, "agents": []}),
        encoding="utf-8",
    )
    (source_root / "chief_status_rail.json").write_text(
        json.dumps({"generated_at": generated_at, "chief_current_status": "read_model_only"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(maestro, "DEFAULT_READ_MODEL_ROOT", source_root)

    request = maestro_listener.build_operator_maestro_chat_request(
        "what can you help me with?",
        message_id="capability-smoke",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_listener_capability_smoke.json"
    request_path.write_text(maestro_listener.stable_json(request), encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    payload, _ = processor.build_payloads(response, generated_at=FIXED_NOW)
    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert response.internal_status == "RESPONSE_READY"
    assert response.request_type == "CHAT"
    assert "Here is the truthful readback from current generated state." in response.operator_message
    assert "Proven live-implemented rails:" in response.operator_message
    assert "Proven live-implemented rails:" in reply
    assert "Recorded, no action ran" not in reply
    assert reply != "Here is the truthful readback from current generated state."
    # 174 EVOLUTION: the visible "[Maestro-native reply - ref ...]" tag was the
    # upstream root of the MT1-MT6 footer regressions (bracket-led fragment =
    # machine contract to the surface guard). Receipt refs live ONLY in the
    # receipt channel now — the visible reply must NOT carry the tag.
    assert "Maestro-native reply - ref" not in reply


def test_listener_capital_hilton_status_probe_reaches_brain_not_system_question(monkeypatch, tmp_path):
    import maestro_context_packet
    import openclaw_request_processor as processor
    import protected_generate

    packet_calls: list[dict] = []
    protected_calls: list[str] = []

    def fake_packet(*, question, session=None, source_surface="operator_maestro_chat", require_real_truth=True, **_kwargs):
        packet_calls.append(
            {
                "question": question,
                "source_surface": source_surface,
                "require_real_truth": require_real_truth,
            }
        )
        return {
            "packet_id": "maestro_context_packet:test:capital_hilton_status",
            "source_refs": ["generated/read_models/capital_hilton_invoice_operator_run_status.json"],
            "facts": [
                {
                    "label": "Capital Hilton status",
                    "value": "$2000 received through Coupa; July 1 check expected.",
                    "source_ref": "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                }
            ],
            "privacy": {"tiers_present": ["LIGHT"]},
            "packet_text": "Capital Hilton status: $2000 received through Coupa; July 1 check expected.",
        }

    def fake_protected(question, *, context_packet, **_kwargs):
        protected_calls.append(question)
        return {
            "text": "Capital Hilton packet answer: $2000 received through Coupa; July 1 check expected. SEND_HOLD remains active.",
            "receipt": {
                "receipt_id": "receipt:test:capital_hilton_status",
                "decision": "INJECTED_PROTECTED_GENERATE",
                "model_call_performed": False,
                "external_llm_invoked": False,
                "local_model_invoked": False,
            },
        }

    monkeypatch.setattr(maestro_context_packet, "build_maestro_context_packet", fake_packet)
    monkeypatch.setattr(protected_generate, "protected_generate_with_receipt", fake_protected)

    request = maestro_listener.build_operator_maestro_chat_request(
        "what's Winship's day / Capital Hilton status?",
        message_id="238",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_telegram_238.json"
    request_path.write_text(maestro_listener.stable_json(request), encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    detail = response.detail_disclosure

    assert response.internal_status == "RESPONSE_READY"
    assert response.request_type == "CHAT"
    assert "Capital Hilton packet answer" in response.operator_message
    assert "I do not have a deterministic local answer" not in response.operator_message
    assert detail["workflow_package_staged"] is False
    assert detail["maestro_frontdoor_routing"]["workflow_package_staged"] is False
    assert detail["maestro_cassandra_responder"]["intent_class"] == "maestro_brain_freeform"
    assert detail["maestro_cassandra_responder"]["machine_proof"]["protected_generate_called"] is True
    assert detail["maestro_cassandra_responder"]["machine_proof"]["maestro_context_packet_used"] is True
    assert "system_question_answer" not in json.dumps(detail, sort_keys=True)
    assert packet_calls == [
        {
            "question": "what's Winship's day / Capital Hilton status?",
            "source_surface": "operator_maestro_chat",
            "require_real_truth": True,
        }
    ]
    assert protected_calls == ["what's Winship's day / Capital Hilton status?"]


def test_authorized_date_question_replies_from_bridge_and_sends_typing(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    written: list[dict] = []

    def fake_write(request: dict, *, inbox: Path = maestro_listener.DEFAULT_REQUEST_INBOX) -> Path:
        written.append(request)
        return tmp_path / f"{request['request_id']}.json"

    async def fake_poll(*args, **kwargs):
        await asyncio.sleep(0)
        return {"one_line_answer": f"Today is {date.today().isoformat()}."}

    records: list[dict] = []
    monkeypatch.setattr(maestro_listener, "write_bridge_request", fake_write)
    monkeypatch.setattr(maestro_listener, "poll_bridge_response", fake_poll)
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: records.append(kwargs))

    update = FakeUpdate(text="what day is it", user_id=123, update_id=42)
    context = FakeContext()
    asyncio.run(maestro_listener.handle_message(update, context))

    assert written
    assert written[0]["request_id"].startswith("maestro_telegram_42_")
    assert written[0]["protected_text_hash"].startswith("sha256:")
    assert written[0]["source_text_ref"] == "protected_text_hash:" + written[0]["protected_text_hash"]
    assert update.message.replies == [f"Today is {date.today().isoformat()}."]
    assert context.bot.actions == [(123, "typing")]
    assert records[0]["operator_message"] is True


def test_reply_only_egress_keeps_typing_and_voice_without_filler_ack(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setenv("OPENCLAW_MAESTRO_REPLY_ONLY", "1")
    writes: list[dict] = []
    voice_calls: list[tuple[str, int]] = []

    monkeypatch.setattr(
        maestro_listener,
        "write_bridge_request",
        lambda request, **kwargs: writes.append(request) or tmp_path / "request.json",
    )

    async def fake_poll(*args, **kwargs):
        await asyncio.sleep(0)
        return {"one_line_answer": "Bound answer."}

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", fake_poll)
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: None)
    monkeypatch.setattr(
        maestro_listener,
        "_fire_maestro_voice",
        lambda text, chat_id, **_kwargs: voice_calls.append((text, chat_id)),
    )

    update = FakeUpdate(text="status?", user_id=123, update_id=43)
    context = FakeContext()
    asyncio.run(maestro_listener.handle_message(update, context))

    assert writes
    assert update.message.replies == ["Bound answer."]
    assert context.bot.actions == [(123, "typing")]
    assert voice_calls == [("Bound answer.", 123)]


def test_telegram_photo_disposition_delivers_verified_image_and_records_hashes(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setenv("OPENCLAW_MAESTRO_REPLY_ONLY", "1")
    image_path = tmp_path / "candidate.png"
    image_path.write_bytes(b"verified candidate image")
    image_sha = __import__("hashlib").sha256(image_path.read_bytes()).hexdigest()
    receipt_path = tmp_path / "artifact-deliveries.jsonl"
    monkeypatch.setenv("OPENCLAW_ARTIFACT_DELIVERY_RECEIPT_PATH", str(receipt_path))
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: None)
    monkeypatch.setattr(
        maestro_listener,
        "write_bridge_request",
        lambda request, **kwargs: tmp_path / "request.json",
    )
    monkeypatch.setattr(
        maestro_listener,
        "build_operator_maestro_chat_request",
        lambda *_args, **_kwargs: {"request_id": "f0-photo-canary"},
    )
    monkeypatch.setattr(maestro_listener, "_fire_maestro_voice", lambda *_args, **_kwargs: None)
    delivered_text_receipts: list[dict] = []
    monkeypatch.setattr(
        maestro_listener,
        "register_delivered_text_receipt",
        lambda **kwargs: delivered_text_receipts.append(kwargs),
    )

    async def fake_poll(*args, **kwargs):
        return {
            "source_request_id": "f0-photo-canary",
            "response_author": "MAESTRO",
            "operator_message": "Here is the verified candidate preview. This is not final.",
            "proof_artifacts": [
                {
                    "artifact_id": "lamd-candidate-b",
                    "bridge_path": str(tmp_path / "candidate.pdf"),
                    "sha256": "sha256:" + "a" * 64,
                    "rendered_image_path": image_path.as_posix(),
                    "rendered_image_sha256": "sha256:" + image_sha,
                }
            ],
            "detail_disclosure": {
                "operator_response_disposition": {
                    "active_surface": "telegram",
                    "delivery_mode": "telegram_photo",
                    "artifact_variant": "candidate",
                    "addressed_agent": "maestro",
                }
            },
        }

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", fake_poll)
    update = FakeUpdate(text="show the recommended invoice", user_id=123, update_id=1711)
    update.message.message_id = 1711
    context = FakeContext()

    asyncio.run(maestro_listener.handle_message(update, context))

    assert update.message.replies == []
    assert context.bot.actions == [(123, "typing")]
    assert len(context.bot.photos) == 1
    assert context.bot.photos[0]["photo"] == image_path.read_bytes()
    assert "QuickLook" not in context.bot.photos[0]["caption"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8").strip())
    assert receipt["source_request_id"] == "f0-photo-canary"
    assert receipt["selected_artifact_sha256"] == "a" * 64
    assert receipt["rendered_image_sha256"] == image_sha
    assert receipt["delivered_message_id"] == "9101"
    assert receipt["delivery_succeeded"] is True
    assert delivered_text_receipts[0]["delivered_text"] == context.bot.photos[0]["caption"]


def test_telegram_photo_delivery_refuses_suppressed_replay_payload(tmp_path):
    payload = {
        "proof_artifacts": [
            {
                "artifact_id": "lamd-candidate-b",
                "bridge_path": str(tmp_path / "candidate.pdf"),
                "sha256": "sha256:" + "a" * 64,
            }
        ],
        "detail_disclosure": {
            "operator_response_disposition": {
                "active_surface": "telegram",
                "delivery_mode": "telegram_photo",
                "artifact_variant": "candidate",
                "addressed_agent": "maestro",
                "delivery_suppressed": True,
            }
        },
    }
    bot = FakeBot()

    with pytest.raises(RuntimeError, match="telegram_artifact_delivery_suppressed"):
        asyncio.run(
            maestro_listener._deliver_telegram_artifact(
                bot=bot,
                chat_id=123,
                caption="test replay",
                payload=payload,
                source_request_id="replay-1711",
                source_message_id="replay-1711",
            )
        )

    assert bot.photos == []


def test_unauthorized_user_does_not_enter_governed_business_intake_or_reply(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    records: list[dict] = []
    writes: list[dict] = []
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: records.append(kwargs))
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda request, **kwargs: writes.append(request))

    update = FakeUpdate(text="hello maestro", user_id=999)
    asyncio.run(maestro_listener.handle_message(update, FakeContext()))

    assert update.message.replies == []
    assert writes == []
    assert records == []


def test_authorized_user_in_non_private_chat_does_not_claim_or_reply(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    claims: list[str] = []
    writes: list[dict] = []
    monkeypatch.setattr(
        maestro_listener,
        "claim_listener_update",
        lambda *args, **kwargs: claims.append("claim") or True,
    )
    monkeypatch.setattr(
        maestro_listener,
        "write_bridge_request",
        lambda request, **kwargs: writes.append(request),
    )

    async def fake_poll(*args, **kwargs):
        return {"one_line_answer": "should not be delivered"}

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", fake_poll)

    update = FakeUpdate(text="status?", user_id=123, chat_id=-100456)
    context = FakeContext()
    asyncio.run(maestro_listener.handle_message(update, context))

    assert claims == []
    assert writes == []
    assert context.bot.actions == []
    assert update.message.replies == []


def test_first_touch_refusal_precedes_governed_intake_and_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setenv(
        "OPENCLAW_REFUSAL_RECEIPT_PATH",
        str(tmp_path / "refusal-receipts.jsonl"),
    )

    def _must_not_reach(*_args, **_kwargs):
        raise AssertionError("governed intake or bridge write ran before refusal")

    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", _must_not_reach)
    monkeypatch.setattr(maestro_listener, "write_bridge_request", _must_not_reach)
    monkeypatch.setattr(maestro_listener, "_fire_maestro_voice", _must_not_reach)

    update = FakeUpdate(
        text="clear out all the old logs and branches, do it now",
        user_id=123,
        update_id=162,
    )
    context = FakeContext()
    asyncio.run(maestro_listener.handle_message(update, context))

    assert len(update.message.replies) == 1
    assert "Nothing was deleted" in update.message.replies[0]
    assert context.bot.actions == []
    assert (tmp_path / "refusal-receipts.jsonl").is_file()


def test_workflow_staging_bridge_response_is_explicit_and_model_call_agnostic(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: None)
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda request, **kwargs: Path("/tmp/request.json"))

    async def fake_poll(*args, **kwargs):
        await asyncio.sleep(0)
        return {
            "internal_status": "RESPONSE_READY",
            "request_type": "WORKFLOW_PACKAGE_REQUEST",
            "operator_headline": "Workflow package staged",
            "operator_message": "OpenClaw staged a package instead of answering directly.",
        }

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", fake_poll)

    update = FakeUpdate(text="send an email", user_id=123)
    asyncio.run(maestro_listener.handle_message(update, FakeContext()))

    assert len(update.message.replies) == 1
    reply = update.message.replies[0].lower()
    assert "staged a workflow package instead of producing a final answer" in reply
    assert "can't verify from this payload whether a model ran" in reply
    assert "no send, workflow, model, tool" not in reply
    assert "capability readback is live after reconcile" not in reply


@pytest.mark.parametrize("answer", [DRIFT_AWARE_ANSWER, LOCATOR_ANSWER])
def test_final_workflow_answers_are_not_classified_as_staging_text(answer):
    payload = {
        "internal_status": "RESPONSE_READY",
        "request_type": "WORKFLOW_PACKAGE_REQUEST",
        "operator_headline": "Workflow package staged",
        "one_line_answer": answer,
        "operator_message": answer,
        "terminal": True,
    }

    assert maestro_listener._looks_like_interim_or_staging_text(answer) is False
    assert maestro_listener.reply_text_from_bridge_response(payload) == answer


def test_exact_1665_workflow_answer_reaches_private_reply_once_with_delivery_receipt(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setenv("OPENCLAW_MAESTRO_REPLY_ONLY", "1")
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **_kwargs: None)
    monkeypatch.setattr(
        maestro_listener,
        "build_operator_maestro_chat_request",
        lambda *_args, **_kwargs: {"request_id": "maestro_telegram_1665_ce0ca2b9fad1"},
    )
    monkeypatch.setattr(
        maestro_listener,
        "write_bridge_request",
        lambda *_args, **_kwargs: tmp_path / "request.json",
    )

    async def fake_poll(*_args, **_kwargs):
        return {
            "source_request_id": "maestro_telegram_1665_ce0ca2b9fad1",
            "internal_status": "RESPONSE_READY",
            "request_type": "WORKFLOW_PACKAGE_REQUEST",
            "operator_headline": "St. Anne's invoice sources need reconciliation",
            "one_line_answer": DRIFT_AWARE_ANSWER,
            "operator_message": DRIFT_AWARE_ANSWER,
            "terminal": True,
        }

    delivery_calls: list[dict] = []
    v2_delivery_calls: list[dict] = []
    monkeypatch.setattr(maestro_listener, "poll_bridge_response", fake_poll)
    monkeypatch.setattr(
        maestro_listener,
        "register_delivered_text_receipt",
        lambda **kwargs: delivery_calls.append(kwargs),
    )
    monkeypatch.setattr(
        maestro_listener,
        "register_operator_text_delivery_v2",
        lambda **kwargs: v2_delivery_calls.append(kwargs),
    )
    monkeypatch.setattr(maestro_listener, "maestro_bot_token", lambda: "test-token")

    class DeliveryMessage(FakeMessage):
        def __init__(self, text: str):
            super().__init__(text)
            self.message_id = 1665

        async def reply_text(self, text: str):
            self.replies.append(text)
            return SimpleNamespace(message_id=9005)

    update = FakeUpdate(text="What's going on with the St Annes invoice test?", user_id=123)
    update.message = DeliveryMessage(update.message.text)

    asyncio.run(maestro_listener.handle_message(update, FakeContext()))

    assert update.message.replies == [DRIFT_AWARE_ANSWER]
    assert len(delivery_calls) == 1
    assert delivery_calls[0]["delivered_text"] == DRIFT_AWARE_ANSWER
    assert delivery_calls[0]["source_request_id"] == "maestro_telegram_1665_ce0ca2b9fad1"
    assert delivery_calls[0]["delivery_succeeded"] is True
    assert len(v2_delivery_calls) == 1
    assert v2_delivery_calls[0]["response_author"] == "maestro"
    assert v2_delivery_calls[0]["carrier_identity"] == "maestro"


def test_guardian_denial_keeps_guardian_truth_instead_of_lying_no_model_floor():
    payload = {
        "source_request_id": "maestro_telegram_guardian_hold",
        "internal_status": "BLOCKED_WITH_REASON",
        "request_type": "CHAT",
        "blocked_reason": "guardian_output_denied",
        "operator_headline": "Guardian held this reply",
        "operator_message": (
            "Guardian held this reply before publication. Nothing was sent, changed, or executed. "
            "Ask me to retry or show the gate reason."
        ),
    }

    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert "Guardian held this reply before publication" in reply
    assert "Nothing was sent, changed, or executed" in reply
    assert "no send, workflow, model, tool" not in reply.lower()


def test_timeout_bridge_response_names_timeout_without_inventing_model_call_facts():
    payload = {
        "source_request_id": "maestro_telegram_timeout",
        "internal_status": "MODEL_TIMEOUT",
        "request_type": "CHAT",
        "blocked_reason": "deadline_exceeded",
        "operator_message": "The bounded answer attempt timed out before a final response was ready.",
    }

    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert "timed out" in reply.lower()
    assert "no send, workflow, model, tool" not in reply.lower()


def test_missing_scoped_response_does_not_claim_that_no_model_ran():
    reply = maestro_listener.reply_text_from_bridge_response(None)

    assert "did not receive a final response" in reply.lower()
    assert "can't verify whether a model ran" in reply.lower()
    assert "no send, workflow, model, tool" not in reply.lower()


def test_reply_prefers_full_final_operator_message_over_generic_one_line():
    payload = {
        "source_request_id": "maestro_telegram_42_abcdef123456",
        "internal_status": "RESPONSE_READY",
        "request_type": "CHAT",
        "one_line_answer": "Here is the truthful readback from current generated state.",
        "operator_message": (
            "Here is the truthful readback from current generated state.\n\n"
            "- Agent roster: Cassandra and Chief are online.\n"
            "- Proven live-implemented rails: Bounded request processor.\n"
            "- I cannot claim send, browser, deploy, or workflow execution from this front door."
        ),
    }

    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert "- Agent roster: Cassandra and Chief are online." in reply
    assert "Proven live-implemented rails" in reply
    assert reply != "Here is the truthful readback from current generated state."
    # 174 EVOLUTION: no visible machine ref tag — receipt channel only.
    assert "Maestro-native reply - ref" not in reply


def test_reply_suppresses_processing_heartbeat_as_final_answer():
    payload = {
        "source_request_id": "maestro_telegram_42_abcdef123456",
        "terminal": False,
        "processing_heartbeat_id": "processing_heartbeat_maestro_telegram_42_abcdef123456",
        "operator_message": "OpenClaw picked this up and is checking the local rails.",
    }

    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert "OpenClaw picked this up" not in reply
    assert "Recorded, no action ran" in reply
    # 174 EVOLUTION: no visible machine ref tag — receipt channel only.
    assert "Maestro-native reply - ref" not in reply


def test_reply_sanitizes_stale_carryover_before_delivery():
    payload = {
        "source_request_id": "maestro_telegram_42_abcdef123456",
        "internal_status": "RESPONSE_READY",
        "request_type": "CHAT",
        "operator_message": (
            "The previous response was truncated. Continue? (61/61)\n"
            "Still working... waiting for stream response\n"
            "Fresh Maestro answer."
        ),
    }

    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert "Fresh Maestro answer." in reply
    assert "Still working" not in reply
    assert "previous response was truncated" not in reply.lower()
    # 174 EVOLUTION: no visible machine ref tag — receipt channel only.
    assert "Maestro-native reply - ref" not in reply


def test_listener_has_no_outbound_send_imports_and_send_hold_boundary_false():
    source = Path(maestro_listener.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    forbidden_imports = {
        "cassandra_sender",
        "gated_email_send_adapter",
        "gmail_access_broker",
        "google_access_broker",
        "coupa_supplier_portal_package_compiler",
    }
    assert imported_modules.isdisjoint(forbidden_imports)
    assert all(value is False for value in maestro_listener.AUTHORITY_BOUNDARY.values())
    assert maestro_listener.AUTHORITY_BOUNDARY["live_email_send_allowed"] is False
    assert maestro_listener.AUTHORITY_BOUNDARY["email_send_allowed"] is False
    assert maestro_listener.AUTHORITY_BOUNDARY["external_action_allowed"] is False
