from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_outreach
import cassandra_sender
import first_class_operator_envelope as operator_authority
import maestro_cassandra_responder as maestro
import openclaw_request_processor as processor
import operator_truth_store
import operator_controller_event_router as router


FIXED_NOW = "2026-06-05T12:00:00+00:00"
NEGATION_LINE = (
    "No email, Gmail, browser, Coupa, submit, ledger, workbook, PDF, paid, push, "
    "external LLM, local model runtime, or business execution occurred."
)


def _seed_read_models(tmp_path: Path) -> Path:
    read_model_root = tmp_path / "read_models"
    read_model_root.mkdir(parents=True, exist_ok=True)
    required = [
        "operator_controller_protocol.json",
        "first_class_operator_envelope_status.json",
        "dynamic_card_packet_latest.json",
        "dynamic_card_lifecycle_policy.json",
        "evidence_intake_status.json",
        "operator_action_payloads.json",
        "objective_advancement_protocol.json",
        "system_question_answer_contract.json",
        "workroom_review_decision_status.json",
        "workroom_review_packet_index.json",
        "workroom_review_decision_contract.json",
        "package_event_index.json",
    ]
    for filename in required:
        shutil.copy2(ROOT / "generated/read_models" / filename, read_model_root / filename)
    return read_model_root


def _verified_chat_request(text: str, *, world: str = "general", thread: str = "frontdoor") -> dict:
    request = {
        "request_id": "controller_event_test_maestro_chat",
        "request_type": router.REQUEST_TYPE,
        "schema_version": "operator_controller_event_request_v0",
        "controller_event_type": "chat_goal",
        "controller_action_type": "chat_goal",
        "current_world_ref": world,
        "current_thread_ref": thread,
        "active_entity_ref": thread,
        "operator_text": text,
        "source_surface": "mission_control",
        "authority_requested": [],
        "authority_boundary": dict(router.AUTHORITY_BOUNDARY),
        "system_knowledge_repo_root": "/tmp/allowed",
        "unapproved_session_key": "do-not-forward",
    }
    return operator_authority.attach_verified_authority_envelope(
        request,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref="session:test:maestro",
        source_surface="chat",
        current_world_ref=world,
        current_thread_ref=thread,
        active_entity_ref=thread,
        controller_action_type="chat_goal",
        authority_requested=[],
        proof_refs=["controller_surface:mission_control", "test:first_class_operator_envelope"],
        created_at=FIXED_NOW,
    )


def _maestro_operator_instruction_request(text: str, *, request_id: str = "general_operator_instruction_test") -> dict:
    request = {
        "active_surface_ref": "operator_maestro_chat",
        "authority_boundary": dict(processor.AUTHORITY_BOUNDARY),
        "created_at": FIXED_NOW,
        "current_world_ref": "general",
        "idempotency_key": f"mission_control_operator_instruction:general:no_thread:{request_id}",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "mac_wrote_request_only": True,
        "operator_message": text,
        "origin_surface": "mission_control_mac",
        "request_id": request_id,
        "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "schema_version": "operator_instruction_writer_v0",
        "source_channel": "mission_control_chat",
        "source_request_id": request_id,
        "source_surface": "mission_control",
        "source_text": text,
        "thread_title": "Maestro",
        "world": "general",
        "world_ref": "general",
    }
    request["payload_hash"] = processor._content_hash(request)
    return request


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_truthful_status_read_models(tmp_path: Path) -> Path:
    read_model_root = tmp_path / "truthful_status_read_models"
    _write_json(
        read_model_root / "openclaw_capability_index.json",
        {
            "schema_version": "openclaw_capability_index_v0",
            "read_model_id": "openclaw_capability_index",
            "generic_capabilities": [
                {
                    "capability_id": "request_processing",
                    "capability_name": "Bounded request processor",
                    "capability_status": "LIVE_IMPLEMENTED",
                    "lifecycle_status": "LIVE_IMPLEMENTED",
                },
                {
                    "capability_id": "status_readback",
                    "capability_name": "Unified status readback",
                    "capability_status": "IMPLEMENTED_NON_EXECUTING",
                    "lifecycle_status": "VALIDATED_NON_EXECUTING",
                },
                {
                    "capability_id": "protected_secret_intake",
                    "capability_name": "Protected secret intake contract",
                    "capability_status": "CONTRACT_ONLY",
                    "lifecycle_status": "KNOWN_GENERIC",
                },
            ],
        },
    )
    _write_json(
        read_model_root / "agent_presence.json",
        {
            "schema_version": "agent_presence_read_model_v0",
            "agents": [
                {"agent_id": "chief", "display_name": "Chief", "actual_state": "online"},
                {"agent_id": "cassandra", "display_name": "Cassandra", "actual_state": "online"},
                {"agent_id": "niles", "display_name": "Niles", "actual_state": "offline"},
            ],
        },
    )
    _write_json(
        read_model_root / "chief_status_rail.json",
        {
            "schema_version": "chief_status_rail_v0",
            "chief_current_status": "safe_status_read_model_only",
            "chief_current_proven_role": {
                "role_summary": "Chief is proven for visibility and planning, not runtime execution.",
            },
        },
    )
    return read_model_root


def _route(tmp_path: Path, request: dict) -> dict:
    read_model_root = _seed_read_models(tmp_path)
    return router.route_controller_event(
        request,
        source_request_filename=f"{request.get('request_id', 'request')}.json",
        read_model_root=read_model_root,
        export_root=read_model_root,
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Controller Event Router.md",
        workroom_wiki_path=tmp_path / "wiki" / "Workroom Review Decision Consumer.md",
        sqlite_path=tmp_path / "operator_controller_event_router.sqlite",
        evidence_sqlite_path=tmp_path / "evidence_intake.sqlite",
        artifact_lineage_sqlite_path=tmp_path / "artifact_lineage_registry.sqlite",
        generated_at=FIXED_NOW,
    )


def test_responder_target_selected_for_chat_and_live_call_stays_false():
    targets = processor.build_responder_targets("CHAT")
    maestro_target = next(target for target in targets if target.target_type == "MAESTRO_CASSANDRA_RESPONDER")
    future_target = next(target for target in targets if target.target_type == "CASSANDRA_FUTURE")

    assert maestro_target.adapter_available is True
    assert maestro_target.selected is True
    assert maestro_target.live_call_allowed is False
    assert maestro_target.blocked_reason is None
    assert future_target.adapter_available is False
    assert future_target.selected is False
    assert future_target.live_call_allowed is False


def test_adapter_maps_handle_result_and_filters_session():
    calls = []

    def fake_handle(text: str, session: dict | None = None) -> list[str]:
        calls.append((text, session))
        return [
            "Today is Tuesday, June 16, 2026.",
            "This second line should stay in the plain summary for disclosure.",
        ]

    result = maestro.answer_frontdoor_chat(
        "what is in orbit",
        session={
            "system_knowledge_repo_root": "/home/openclaw",
            "raw_body": "must not forward",
            "system_knowledge_atlas_path": "",
        },
        handle_fn=fake_handle,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "system_knowledge"
    assert result.allowed_to_call_handle is True
    assert result.mac_render_hint == "COMPACT_WITH_DISCLOSURE"
    assert len(result.one_line_answer.split()) <= 30
    assert "second line" in result.plain_summary
    assert calls == [("what is in orbit", {"system_knowledge_repo_root": "/home/openclaw"})]
    assert result.machine_proof["gmail_metadata_read_performed"] is False
    assert result.machine_proof["email_send_performed"] is False
    assert result.machine_proof["text_response_only"] is True


def test_session_from_request_drops_vault_paths_and_accepts_allowlisted_aliases():
    session = maestro.session_from_request(
        {
            "system_knowledge_atlas_path": "/mnt/c/OpenClawLegalPrivate/x.json",
            "system_knowledge_ledger_path": "/home/openclaw/generated/system_knowledge/openclaw.sqlite",
            "context": {
                "repo_root": "/mnt/e/openclaw/orchestration",
                "ledger_path": "/mnt/c/FinancePrivate/ledger.sqlite",
            },
            "current_context": {
                "atlas_path": "/home/openclaw/generated/read_models/openclaw_system_knowledge_registry.json",
            },
        }
    )

    assert session == {
        "system_knowledge_repo_root": "/mnt/e/openclaw/orchestration",
        "system_knowledge_ledger_path": "/home/openclaw/generated/system_knowledge/openclaw.sqlite",
        "system_knowledge_atlas_path": "/home/openclaw/generated/read_models/openclaw_system_knowledge_registry.json",
    }


def test_session_from_request_rejects_dotdot_and_symlink_escape(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    outside_file = outside / "vault.json"
    outside_file.write_text("private", encoding="utf-8")
    monkeypatch.setattr(maestro, "PATH_PREFIX_ALLOWLIST", (allowed.resolve(),))

    traversal = allowed / ".." / "outside" / "vault.json"
    assert maestro.session_from_request({"system_knowledge_atlas_path": str(traversal)}) == {}

    symlink = allowed / "vault-link.json"
    try:
        symlink.symlink_to(outside_file)
    except OSError:
        return
    assert maestro.session_from_request({"system_knowledge_atlas_path": str(symlink)}) == {}

    allowed_file = allowed / "atlas.json"
    assert maestro.session_from_request({"system_knowledge_atlas_path": str(allowed_file)}) == {
        "system_knowledge_atlas_path": str(allowed_file)
    }


def test_filtered_session_does_not_forward_direct_vault_paths_to_handle():
    calls = []

    def fake_handle(text: str, session: dict | None = None) -> list[str]:
        calls.append(session)
        return ["OpenClaw knows its safe shape."]

    result = maestro.answer_frontdoor_chat(
        "what does OpenClaw know?",
        session={"system_knowledge_atlas_path": "/home/openclaw/.chief.env"},
        handle_fn=fake_handle,
    )

    assert result.status == "ANSWER_READY"
    assert calls == [{}]


def test_adapter_distills_one_line_without_losing_plain_summary():
    long_line = " ".join(f"word{i}" for i in range(45))

    result = maestro.answer_frontdoor_chat(
        "what is in orbit",
        handle_fn=lambda _text, _session=None: [long_line, "Full detail remains here."],
    )

    assert len(result.one_line_answer.split()) <= 30
    assert result.one_line_answer.endswith("...")
    assert long_line in result.plain_summary
    assert "Full detail remains here." in result.plain_summary


def test_date_query_answered_deterministically_without_handle():
    import re as _re
    calls = []

    def spy_handle(text, session=None):
        calls.append(text)
        return ["SHOULD NOT BE USED"]

    for q in ("what is todays date?", "what's today's date", "what day is it"):
        result = maestro.answer_frontdoor_chat(q, handle_fn=spy_handle)
        assert result.status == "ANSWER_READY"
        assert result.intent_class == "date_awareness"
        assert result.allowed_to_call_handle is False
        assert _re.match(r"Today is \d{4}-\d{2}-\d{2} \(\w+\)\.$", result.one_line_answer), result.one_line_answer
        assert result.machine_proof["cassandra_handle_called"] is False
    assert calls == []


def test_status_capability_query_answers_from_read_models_without_handle(tmp_path):
    read_model_root = _seed_truthful_status_read_models(tmp_path)

    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("status/capability readback must not call cassandra_brain.handle")

    result = maestro.answer_frontdoor_chat(
        "Hermes, what's going on? What can you do now?",
        session={
            "read_model_root": read_model_root.as_posix(),
            "system_knowledge_repo_root": "/home/openclaw",
        },
        handle_fn=forbidden_handle,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "status_capability_readback"
    assert result.allowed_to_call_handle is False
    assert "2 agents are online" in result.plain_summary
    assert "Bounded request processor" in result.plain_summary
    assert "Unified status readback" in result.plain_summary
    assert "I cannot claim email send" in result.plain_summary
    assert result.session_forwarded == {"system_knowledge_repo_root": "/home/openclaw"}
    assert result.machine_proof["cassandra_handle_called"] is False
    assert result.machine_proof["capability_index_used"] is True
    assert result.machine_proof["agent_presence_used"] is True
    assert result.machine_proof["chief_status_rail_used"] is True
    assert result.machine_proof["live_implemented_capability_ids"] == ("request_processing",)
    assert result.machine_proof["blocked_or_future_capability_ids_not_claimed"] == (
        "protected_secret_intake",
    )


def test_hermes_capability_prompt_is_truthful_not_canned_and_no_send(tmp_path):
    read_model_root = _seed_truthful_status_read_models(tmp_path)

    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("Hermes first-touch prompts must not call cassandra_brain.handle")

    result = maestro.answer_frontdoor_chat(
        "Hermes, what's your job?",
        session={
            "read_model_root": read_model_root.as_posix(),
            "system_knowledge_repo_root": "/home/openclaw",
        },
        handle_fn=forbidden_handle,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "hermes_truthful_advisory"
    assert result.allowed_to_call_handle is False
    assert "advisory boundary reviewer" in result.plain_summary
    assert "SEND_HOLD remains in force" in result.plain_summary
    assert "Non-canonical advisory output" not in result.plain_summary
    assert result.machine_proof["cassandra_handle_called"] is False
    assert result.machine_proof["agent_dispatch_performed"] is False
    assert result.machine_proof["email_send_performed"] is False
    assert result.machine_proof["send_hold_boundary_visible"] is True


def test_hermes_route_prompt_denies_without_guessing_skill_or_dispatching():
    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("Hermes route prompts must not call cassandra_brain.handle")

    result = maestro.answer_frontdoor_chat(
        "Hermes, route this to Cassandra",
        handle_fn=forbidden_handle,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "hermes_truthful_advisory"
    assert "cannot route this to cassandra" in result.plain_summary.lower()
    assert "no agent handoff ran" in result.plain_summary.lower()
    assert "no route receipt was written" in result.plain_summary.lower()
    assert "cassandra_email_triage" not in result.plain_summary
    assert result.machine_proof["hermes_reply_mode"] == "route_request"
    assert result.machine_proof["requested_route_target"] == "cassandra"
    assert result.machine_proof["hermes_skill_guess_performed"] is False
    assert result.machine_proof["hermes_route_receipt_written"] is False
    assert result.machine_proof["agent_dispatch_performed"] is False


def test_hermes_non_agent_money_route_denies_money_before_route():
    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("Hermes money route prompts must not call cassandra_brain.handle")

    result = maestro.answer_frontdoor_chat(
        "Hermes, forward this to accounting and pay the vendor",
        handle_fn=forbidden_handle,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "hermes_truthful_advisory"
    lowered = result.plain_summary.lower()
    assert "cannot send messages" in lowered
    assert "move money" in lowered
    assert "denied for live action" in lowered
    assert "cannot route this to accounting" not in lowered
    assert result.machine_proof["hermes_reply_mode"] == "send_money_denial"
    assert result.machine_proof["requested_route_target"] == "accounting"
    assert result.machine_proof["requested_route_target_is_canonical_agent"] is False
    assert result.machine_proof["agent_dispatch_performed"] is False
    assert result.machine_proof["email_send_performed"] is False


def test_hermes_inventory_distinguishes_real_bridges_from_local_helpers():
    result = maestro.answer_frontdoor_chat("Hermes, what can you route to?")

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "hermes_truthful_advisory"
    assert "Real agent bridges available to Hermes here: none proven." in result.plain_summary
    assert "Local helper tools and read-model sidecars" in result.plain_summary
    assert "not dispatch routes" in result.plain_summary
    assert result.machine_proof["hermes_reply_mode"] == "route_inventory"
    assert result.machine_proof["hermes_real_agent_bridge_available"] is False
    assert result.machine_proof["hermes_local_helpers_are_not_agent_bridges"] is True


def test_internal_worker_state_leaks_are_suppressed_from_user_reply():
    result = maestro.answer_frontdoor_chat(
        "what is in orbit",
        handle_fn=lambda _text, _session=None: [
            "Interrupting current task (iteration 1/90) OpenClaw knows its registry shape.",
            "Full detail remains here.",
        ],
    )

    public_text = result.one_line_answer + "\n" + result.plain_summary
    assert result.status == "ANSWER_READY"
    assert "Interrupting current task" not in public_text
    assert "iteration 1/90" not in public_text
    assert "OpenClaw knows its registry shape." in result.plain_summary
    assert "Full detail remains here." in result.plain_summary


def test_status_capability_missing_index_fails_closed_without_fake_claim(tmp_path):
    read_model_root = tmp_path / "empty_read_models"
    read_model_root.mkdir()

    result = maestro.answer_frontdoor_chat(
        "what can you do?",
        session={"read_model_root": read_model_root.as_posix()},
        handle_fn=lambda _text, _session=None: ["SHOULD NOT RUN"],
    )

    assert result.status == "ANSWER_READY"
    assert result.allowed_to_call_handle is False
    assert "cannot truthfully list capabilities" in result.plain_summary
    assert result.machine_proof["capability_index_used"] is False
    assert result.machine_proof["live_implemented_capability_count"] == 0


def test_operator_truth_query_intent_routes_deterministic(monkeypatch, tmp_path):
    store_path = tmp_path / "operator_truth_store.json"
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", str(store_path))
    operator_truth_store.upsert_operator_truth(
        "capital_hilton",
        "Capital Hilton invoice was submitted and payment received for $2000.",
        source_surface="test",
        path=store_path,
    )

    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("cassandra_brain.handle must not run for operator truth query")

    def forbidden_protected_generate(*_args, **_kwargs):
        raise AssertionError("protected_generate must not run for operator truth query")

    started = time.perf_counter()
    result = maestro.answer_frontdoor_chat(
        "Did you store Capital Hilton?",
        handle_fn=forbidden_handle,
        protected_generate_fn=forbidden_protected_generate,
    )
    elapsed = time.perf_counter() - started

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "operator_truth_query"
    assert elapsed < 0.1
    assert result.allowed_to_call_handle is False
    assert "Capital Hilton invoice was submitted" in result.plain_summary
    assert result.machine_proof["operator_truth_query_performed"] is True
    assert result.machine_proof["operator_truth_store_read"] is True
    assert result.machine_proof["operator_truth_record_found"] is True
    assert result.machine_proof["operator_truth_entity_key"] == "capital_hilton"
    assert result.machine_proof["cassandra_handle_called"] is False
    assert result.machine_proof["protected_generate_called"] is False
    assert result.machine_proof["external_llm_invoked"] is False

def test_people_reference_query_routes_truth_before_llm(monkeypatch, tmp_path):
    store_path = tmp_path / "operator_truth_store.json"
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", str(store_path))
    operator_truth_store.upsert_operator_truth(
        "capital_hilton",
        "Will Valcovic is the Capital Hilton contact for Coupa and payment follow-up.",
        source_surface="test",
        path=store_path,
    )

    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("cassandra_brain.handle must not run for people reference query")

    def forbidden_protected_generate(*_args, **_kwargs):
        raise AssertionError("protected_generate must not run when operator truth matches")

    result = maestro.answer_frontdoor_chat(
        "who is will valcovic?",
        handle_fn=forbidden_handle,
        protected_generate_fn=forbidden_protected_generate,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "people_reference_query"
    assert result.allowed_to_call_handle is False
    assert "Will Valcovic is the Capital Hilton contact" in result.plain_summary
    assert result.machine_proof["people_reference_query_performed"] is True
    assert result.machine_proof["operator_truth_store_read"] is True
    assert result.machine_proof["operator_truth_record_found"] is True
    assert result.machine_proof["operator_truth_entity_key"] == "capital_hilton"
    assert result.machine_proof["cassandra_handle_called"] is False
    assert result.machine_proof["protected_generate_called"] is False
    assert result.machine_proof["external_llm_invoked"] is False



def test_operator_truth_query_recorded_about_phrase_is_zero_llm(monkeypatch, tmp_path):
    store_path = tmp_path / "operator_truth_store.json"
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", str(store_path))
    operator_truth_store.upsert_operator_truth(
        "capital_hilton",
        "Capital Hilton invoice was submitted and payment received for $2000.",
        source_surface="test",
        path=store_path,
    )

    result = maestro.answer_frontdoor_chat(
        "What have you recorded about Capital Hilton?",
        handle_fn=lambda _text, _session=None: (_ for _ in ()).throw(
            AssertionError("cassandra_brain.handle must not run for operator truth query")
        ),
        protected_generate_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("protected_generate must not run for operator truth query")
        ),
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "operator_truth_query"
    assert "Capital Hilton invoice was submitted" in result.plain_summary
    assert result.machine_proof["protected_generate_called"] is False
    assert result.machine_proof["external_llm_invoked"] is False


def test_operator_truth_query_no_match_still_short_circuits_models(monkeypatch, tmp_path):
    store_path = tmp_path / "operator_truth_store.json"
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", str(store_path))

    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("cassandra_brain.handle must not run for operator truth query")

    def forbidden_protected_generate(*_args, **_kwargs):
        raise AssertionError("protected_generate must not run for operator truth query")

    result = maestro.answer_frontdoor_chat(
        "Did you store Live Arts MD as truth?",
        handle_fn=forbidden_handle,
        protected_generate_fn=forbidden_protected_generate,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "operator_truth_query"
    assert result.allowed_to_call_handle is False
    assert "do not have a matching operator-truth record" in result.plain_summary
    assert result.machine_proof["operator_truth_record_found"] is False
    assert result.machine_proof["cassandra_handle_called"] is False
    assert result.machine_proof["protected_generate_called"] is False
    assert result.machine_proof["external_llm_invoked"] is False



def test_send_reply_intent_never_reaches_handle_or_send_spies(monkeypatch):
    calls: list[str] = []

    def spy(*_args, **_kwargs):
        calls.append("called")

    monkeypatch.setattr(cassandra_sender, "send_message", spy)
    monkeypatch.setattr(cassandra_sender, "send_document", spy)
    monkeypatch.setattr(cassandra_sender, "send_voice_note", spy)
    monkeypatch.setattr(cassandra_outreach, "create_gmail_draft", spy)
    monkeypatch.setattr(cassandra_outreach, "run_outreach", spy)
    monkeypatch.setattr(cassandra_outreach, "send_known_contact_watch_notification", spy)

    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("cassandra_brain.handle must not be called for send/reply intent")

    result = maestro.answer_frontdoor_chat(
        "reply to Glenn subject: yes body: I can do it",
        handle_fn=forbidden_handle,
    )

    assert result.status == "ROUTE_TO_STAGING"
    assert result.allowed_to_call_handle is False
    assert result.intent_class == "send_reply_email_action"
    assert result.machine_proof["cassandra_handle_called"] is False
    assert calls == []


def test_inbox_queries_take_option_b_and_do_not_reach_handle():
    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("inbox metadata queries must not call handle on blanket-negation route")

    result = maestro.answer_frontdoor_chat(
        "list my 5 newest unread inbox emails with sender and subject only",
        handle_fn=forbidden_handle,
    )

    assert result.status == "ROUTE_TO_STAGING"
    assert result.intent_class == "inbox_gmail_metadata"
    assert result.route_to_staging_reason == "gmail_metadata_queries_use_existing_staging_path_for_truthful_proof"
    assert result.machine_proof["gmail_metadata_queries_route_to_staging"] is True
    assert result.machine_proof["gmail_metadata_read_performed"] is False


def test_router_answer_path_uses_maestro_receipt_and_no_authority_proof(monkeypatch, tmp_path):
    monkeypatch.setattr(
        maestro,
        "answer_frontdoor_chat",
        lambda text, *, session=None: maestro.MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="date_awareness",
            allowed_to_call_handle=False,
            one_line_answer="Today is Tuesday.",
            plain_summary="Today is Tuesday, June 16, 2026.",
            session_forwarded=maestro.filtered_session(session),
            machine_proof={
                "intent_gate_before_handle": True,
                "cassandra_handle_called": False,
                "email_send_performed": False,
                "gmail_metadata_read_performed": False,
                "telegram_send_triggered": False,
                "text_response_only": True,
            },
        ),
    )

    receipt = _route(tmp_path, _verified_chat_request("what's today's date?"))

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "maestro_cassandra_responder.datetime_deterministic"
    assert receipt["route_status"] == "TEXT_RESPONSE_READY"
    assert receipt["route_result"]["allowed_to_call_handle"] is False
    assert receipt["one_line_answer"] == "Today is Tuesday."
    assert receipt["plain_summary"] == "Today is Tuesday, June 16, 2026."
    assert receipt["mac_render_hint"] == "COMPACT_WITH_DISCLOSURE"
    assert receipt["machine_proof"]["maestro_cassandra_responder_performed"] is True
    assert receipt["machine_proof"]["cassandra_handle_called"] is False
    assert receipt["machine_proof"]["external_llm_invoked"] is False
    assert receipt["machine_proof"]["gmail_access_performed"] is False
    assert receipt["machine_proof"]["email_send_performed"] is False
    assert receipt["dynamic_card_response"]["actions"] == []
    assert receipt["dynamic_card_response"]["authority_boundary"] == dict(router.AUTHORITY_BOUNDARY)
    assert "maestro_cassandra_responder:date_awareness" in receipt["proof_refs"]


def test_router_fallback_still_handles_action_intent_without_adapter_handle(monkeypatch, tmp_path):
    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("handle must not run for action intent")

    monkeypatch.setattr(maestro, "_default_handle", forbidden_handle)

    receipt = _route(
        tmp_path,
        _verified_chat_request(
            "send email to Glenn subject: hi body: hello",
            world="finance",
            thread="capital_hilton",
        ),
    )

    assert receipt["backend_route"] == "operator_conversation_router.route_conversation_text"
    assert receipt["route_status"] in {
        "STAGE_PLAN_TEXT_RESPONSE",
        "PROTECTED_ACTION_BLOCKED_TEXT_RESPONSE",
        "CAPABILITY_GAP_AUTHORITY_REQUEST_READY",
        "TEXT_RESPONSE_READY",
    }
    for action in receipt["dynamic_card_response"]["actions"]:
        assert action["business_action"] is False
        assert action["authority_boundary"] == dict(router.AUTHORITY_BOUNDARY)
    assert receipt["machine_proof"].get("cassandra_handle_called", False) is False


def test_processor_answer_path_keeps_existing_controller_event_envelope(monkeypatch, tmp_path):
    monkeypatch.setattr(
        maestro,
        "answer_frontdoor_chat",
        lambda text, *, session=None: maestro.MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="system_knowledge",
            allowed_to_call_handle=True,
            one_line_answer="OpenClaw knows its registry shape.",
            plain_summary="OpenClaw knows its registry shape from the local system knowledge registry.",
            session_forwarded=maestro.filtered_session(session),
            machine_proof={
                "intent_gate_before_handle": True,
                "cassandra_handle_called": True,
                "email_send_performed": False,
                "gmail_metadata_read_performed": False,
                "telegram_send_triggered": False,
                "text_response_only": True,
            },
        ),
    )
    read_model_root = _seed_read_models(tmp_path)
    request_path = tmp_path / "mission_control_controller_event_request_maestro_chat.json"
    request_path.write_text(json.dumps(_verified_chat_request("what does OpenClaw know from the system knowledge registry?")), encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=read_model_root,
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    layered = response.detail_disclosure["layered_response_fields"]

    assert response.request_type == "OPERATOR_CONTROLLER_EVENT_REQUEST"
    assert response.internal_status == "RESPONSE_READY"
    assert response.card_mirror_refs == ()
    assert response.context_package_refs == ()
    assert response.detail_disclosure["layered_response_fields"]["no_external_authority_granted"] is True
    assert NEGATION_LINE in response.what_happened
    assert layered["one_line_answer"] == "OpenClaw knows its registry shape."
    assert layered["plain_summary"] == "OpenClaw knows its registry shape from the local system knowledge registry."
    assert layered["mac_render_hint"] == "COMPACT_WITH_DISCLOSURE"
    assert response.worker_route_refs == (
        {
            "selected_worker_target": "PC_CODEX",
            "selected_machine": "PC_WSL",
            "routing_status": "PROCESSING_ON_PC",
            "selected_rail": "operator_controller_event_router",
            "controller_event_type": "chat_goal",
            "route_status": "TEXT_RESPONSE_READY",
            "backend_route": "maestro_cassandra_responder.cassandra_brain.handle",
        },
    )


def test_processor_routes_general_maestro_frontdoor_request_to_responder(monkeypatch, tmp_path):
    calls = []

    def fake_answer(text: str, *, session=None):
        calls.append((text, session))
        return maestro.MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="date_awareness",
            allowed_to_call_handle=False,
            one_line_answer="Today is 2026-06-16 (Tuesday).",
            plain_summary="Today is 2026-06-16 (Tuesday).",
            session_forwarded=maestro.filtered_session(session),
            machine_proof={
                "intent_gate_before_handle": True,
                "cassandra_handle_called": False,
                "email_send_performed": False,
                "gmail_metadata_read_performed": False,
                "telegram_send_triggered": False,
                "text_response_only": True,
            },
        )

    monkeypatch.setattr(maestro, "answer_frontdoor_chat", fake_answer)
    read_model_root = _seed_read_models(tmp_path)
    request_path = tmp_path / "mission_control_operator_instruction_request_general_operator_instruction_20260616T171609Z.json"
    request_path.write_text(
        json.dumps(_maestro_operator_instruction_request("what's today's date"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=read_model_root,
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )

    assert response.request_type == "CHAT"
    assert response.internal_status == "RESPONSE_READY"
    assert response.operator_headline == "Today is 2026-06-16 (Tuesday)."
    assert response.operator_message == "Today is 2026-06-16 (Tuesday)."
    assert "Workflow package staged" not in response.operator_headline + response.operator_message
    assert response.detail_disclosure["maestro_frontdoor_routing"]["workflow_package_staged"] is False
    assert response.detail_disclosure["maestro_cassandra_responder"]["allowed_to_call_handle"] is False
    assert response.detail_disclosure["external_llm_invoked"] is False
    assert response.detail_disclosure["workflow_package_staged"] is False
    assert response.visible_cards[0]["actions"] == []
    assert "maestro_cassandra_responder:date_awareness" in response.visible_cards[0]["proof"]["proof_refs"]
    assert response.worker_route_refs == (
        {
            "selected_worker_target": "PC_CODEX",
            "selected_machine": "PC_WSL",
            "routing_status": "PROCESSING_ON_PC",
            "selected_rail": "MAESTRO_CASSANDRA_RESPONDER",
            "controller_event_type": "chat_goal",
            "route_status": "TEXT_RESPONSE_READY",
            "backend_route": "maestro_cassandra_responder.datetime_deterministic",
        },
    )
    assert calls == [("what's today's date", {})]


def test_processor_routes_general_status_query_to_truthful_responder(tmp_path):
    read_model_root = _seed_read_models(tmp_path)
    request_path = tmp_path / "mission_control_operator_instruction_request_general_operator_instruction_status.json"
    request_path.write_text(
        json.dumps(
            _maestro_operator_instruction_request(
                "what's going on? what can you do now?",
                request_id="general_operator_instruction_status_test",
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=read_model_root,
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    responder = response.detail_disclosure["maestro_cassandra_responder"]

    assert response.request_type == "CHAT"
    assert response.internal_status == "RESPONSE_READY"
    assert "Workflow package staged" not in response.operator_headline + response.operator_message
    assert responder["intent_class"] == "status_capability_readback"
    assert responder["allowed_to_call_handle"] is False
    assert responder["machine_proof"]["cassandra_handle_called"] is False
    assert responder["machine_proof"]["capability_index_used"] is True
    assert response.worker_route_refs[0]["backend_route"] == (
        "maestro_cassandra_responder.truthful_status_capability_readback"
    )


def test_processor_routes_hermes_route_prompt_to_truthful_denial(tmp_path):
    read_model_root = _seed_read_models(tmp_path)
    request_path = tmp_path / "mission_control_operator_instruction_request_general_operator_instruction_hermes_route.json"
    request_path.write_text(
        json.dumps(
            _maestro_operator_instruction_request(
                "Hermes, route this to Cassandra",
                request_id="general_operator_instruction_hermes_route_test",
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=read_model_root,
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    responder = response.detail_disclosure["maestro_cassandra_responder"]
    public_text = response.operator_headline + "\n" + response.operator_message

    assert response.request_type == "CHAT"
    assert response.internal_status == "RESPONSE_READY"
    assert "cannot route this to cassandra" in public_text.lower()
    assert "cassandra_email_triage" not in public_text
    assert "SEND_HOLD remains in force" in public_text
    assert responder["intent_class"] == "hermes_truthful_advisory"
    assert responder["allowed_to_call_handle"] is False
    assert responder["machine_proof"]["hermes_skill_guess_performed"] is False
    assert responder["machine_proof"]["agent_dispatch_performed"] is False
    assert responder["machine_proof"]["email_send_performed"] is False
    assert response.detail_disclosure["workflow_package_staged"] is False
    assert response.worker_route_refs[0]["backend_route"] == maestro.HERMES_TRUTHFUL_BACKEND_ROUTE


def test_processor_keeps_general_maestro_action_request_on_staging(monkeypatch, tmp_path):
    def forbidden_handle(_text: str, _session: dict | None = None) -> list[str]:
        raise AssertionError("cassandra_brain.handle must not be called for action intent")

    monkeypatch.setattr(maestro, "_default_handle", forbidden_handle)
    read_model_root = _seed_read_models(tmp_path)
    request_path = tmp_path / "mission_control_operator_instruction_request_general_operator_instruction_send.json"
    request_path.write_text(
        json.dumps(
            _maestro_operator_instruction_request(
                "send email to Glenn subject: hi body: hello",
                request_id="general_operator_instruction_send_test",
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=read_model_root,
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )

    assert response.request_type == "WORKFLOW_PACKAGE_REQUEST"
    assert response.internal_status == "RESPONSE_READY"
    assert response.operator_headline == "Workflow package staged"
    assert "Workflow Package Queue" in response.why_it_happened
    assert response.detail_disclosure.get("maestro_frontdoor_routing") is None


def test_adapter_structural_imports_only_cassandra_handle_from_forbidden_family():
    tree = ast.parse((ROOT / "maestro_cassandra_responder.py").read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    imported_names: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.append(node.module or "")
            imported_names.extend((node.module or "", alias.name) for alias in node.names)

    assert ("cassandra_brain", "handle") in imported_names
    forbidden_modules = {
        "cassandra_listener",
        "cassandra_whisper_relay",
        "cassandra_outreach",
        "cassandra_sender",
    }
    assert forbidden_modules.isdisjoint(set(imported_modules))


def test_gitignore_allows_pc_maestro_listener_source():
    result = subprocess.run(
        ["git", "check-ignore", "maestro_listener.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
