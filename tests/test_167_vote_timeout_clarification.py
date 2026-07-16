from __future__ import annotations

import time

import pytest

import typed_contract_decision as contract
import vote_timeout_clarification as clarification_policy
from vote_timeout_clarification import (
    ExplicitDigestIntent,
    VoteTimeoutDisposition,
    WARM_TIMEOUT_CLARIFICATION,
    classify_explicit_digest_intent,
    classify_vote_timeout_disposition,
    enforce_vote_timeout_output,
    is_outside_session_vote_failure,
    is_recoverable_outside_session_vote_timeout,
    warm_clarification_for_vote_timeout,
)


AMBIGUOUS_REQUEST = "Could you unpack that broader situation?"
EXPECTED_MODEL_TIMEOUT_CLARIFICATION = (
    "The language model timed out before it could classify that request. "
    "The GPU may be busy. I left your request untouched; please try again in a moment."
)
EXPECTED_MODEL_FAILURE_CLARIFICATION = (
    "The language model didn't return a usable routing decision. I left your "
    "request untouched; please try again in a moment."
)


def test_vote_failure_clarifications_are_exact_and_do_not_overclaim() -> None:
    assert clarification_policy.MODEL_TIMEOUT_CLARIFICATION == (
        EXPECTED_MODEL_TIMEOUT_CLARIFICATION
    )
    assert clarification_policy.MODEL_FAILURE_CLARIFICATION == (
        EXPECTED_MODEL_FAILURE_CLARIFICATION
    )
    assert WARM_TIMEOUT_CLARIFICATION == EXPECTED_MODEL_TIMEOUT_CLARIFICATION
    assert "timeout" not in EXPECTED_MODEL_FAILURE_CLARIFICATION.lower()
    for unsupported_claim in ("rewarm", "re-warm", "switch", "watchdog"):
        assert unsupported_claim not in EXPECTED_MODEL_TIMEOUT_CLARIFICATION.lower()


def _context(*, active: bool = False) -> contract.ContractContext:
    return contract.ContractContext(
        agent="maestro",
        surface="operator_maestro_chat",
        active_session=active,
        session_kind="guided_review" if active else "",
        session_field="q1" if active else "",
        session_snapshot=(
            {"status": "active", "active_workflow": "guided_review", "current_question_id": "q1"}
            if active
            else {}
        ),
    )


@pytest.mark.parametrize(
    ("vote_status", "expected_kind", "expected_clarification"),
    (
        ("error:TimeoutError", "timeout", EXPECTED_MODEL_TIMEOUT_CLARIFICATION),
        ("error:GPU TIMEOUT", "timeout", EXPECTED_MODEL_TIMEOUT_CLARIFICATION),
        ("deadline_exceeded", "timeout", EXPECTED_MODEL_TIMEOUT_CLARIFICATION),
        ("empty", "model_failure", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("invalid", "model_failure", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("below_threshold", "model_failure", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("session_label_without_session", "model_failure", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("timeout_or_invalid", "model_failure", EXPECTED_MODEL_FAILURE_CLARIFICATION),
        ("error:RuntimeError", "model_failure", EXPECTED_MODEL_FAILURE_CLARIFICATION),
    ),
)
def test_outside_session_vote_failure_keeps_exact_pass_through_receipt(
    vote_status: str,
    expected_kind: str,
    expected_clarification: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *_args, **_kwargs: (None, vote_status),
    )

    decision = contract.decide_contract(
        AMBIGUOUS_REQUEST,
        context=_context(),
        semantic_vote_enabled=True,
    )

    receipt = decision.receipt.to_dict()
    assert decision.label is contract.ContractLabel.UNRESOLVED
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert decision.handled is False
    assert receipt["source"] == "semantic_vote"
    assert receipt["label"] == "unresolved"
    assert receipt["action"] == "pass_through"
    assert receipt["reason"] == "uncertain_outside_session_fail_open"
    assert receipt["semantic_vote_status"] == vote_status
    assert is_outside_session_vote_failure(decision) is True
    assert clarification_policy.classify_vote_failure_kind(decision).value == expected_kind
    assert is_recoverable_outside_session_vote_timeout(decision) is (
        expected_kind == "timeout"
    )
    assert (
        classify_vote_timeout_disposition(AMBIGUOUS_REQUEST, decision)
        is VoteTimeoutDisposition.CLARIFY
    )
    assert (
        warm_clarification_for_vote_timeout(AMBIGUOUS_REQUEST, decision)
        == expected_clarification
    )


@pytest.mark.parametrize(
    ("raw_vote", "expected_status"),
    (("", "empty"), ("   \n", "empty"), ("not-json", "invalid"), ("{}", "invalid")),
)
def test_semantic_vote_distinguishes_empty_from_invalid(
    raw_vote: str,
    expected_status: str,
) -> None:
    parsed, status = contract._call_semantic_vote(
        AMBIGUOUS_REQUEST,
        _context(),
        adaptive_call_fn=lambda *_args, **_kwargs: raw_vote,
        timeout_seconds=0.2,
    )

    assert parsed is None
    assert status == expected_status


def test_semantic_vote_reports_timeout_error_separately() -> None:
    def raises_timeout(*_args, **_kwargs):
        raise TimeoutError("provider timed out")

    parsed, status = contract._call_semantic_vote(
        AMBIGUOUS_REQUEST,
        _context(),
        adaptive_call_fn=raises_timeout,
        timeout_seconds=0.2,
    )

    assert parsed is None
    assert status == "error:TimeoutError"


def test_semantic_vote_requests_and_classifies_caught_provider_timeout_metadata() -> None:
    seen = {}

    def caught_provider_timeout(*_args, **kwargs):
        seen.update(kwargs)
        return {
            "text": "",
            "response": "",
            "status": "exception",
            "done_reason": "timeout",
            "exception_type": "TimeoutError",
            "exception": "provider timed out",
        }

    parsed, status = contract._call_semantic_vote(
        AMBIGUOUS_REQUEST,
        _context(),
        adaptive_call_fn=caught_provider_timeout,
        timeout_seconds=0.2,
    )

    assert seen["return_metadata"] is True
    assert parsed is None
    assert status == "error:TimeoutError"


def test_semantic_vote_classifies_caught_provider_exception_metadata() -> None:
    def caught_provider_exception(*_args, **_kwargs):
        return {
            "text": "",
            "response": "",
            "status": "exception",
            "done_reason": "unreachable",
            "exception_type": "ConnectionError",
            "exception": "connection refused",
        }

    parsed, status = contract._call_semantic_vote(
        AMBIGUOUS_REQUEST,
        _context(),
        adaptive_call_fn=caught_provider_exception,
        timeout_seconds=0.2,
    )

    assert parsed is None
    assert status == "error:ConnectionError"


def test_semantic_vote_timeout_metadata_cannot_lose_timeout_to_exception_type() -> None:
    def timeout_with_generic_exception(*_args, **_kwargs):
        return {
            "text": "",
            "status": "exception",
            "done_reason": "timeout",
            "exception_type": "URLError",
        }

    parsed, status = contract._call_semantic_vote(
        AMBIGUOUS_REQUEST,
        _context(),
        adaptive_call_fn=timeout_with_generic_exception,
        timeout_seconds=0.2,
    )

    assert parsed is None
    assert status == "error:TimeoutError"


def test_default_semantic_vote_runs_in_killable_spawned_process(monkeypatch) -> None:
    captured = {}

    class FakeQueue:
        def __init__(self):
            self.value = None

        def get(self, timeout):
            captured["get_timeout"] = timeout
            return self.value

        def close(self):
            captured["queue_closed"] = True

        def join_thread(self):
            captured["queue_joined"] = True

    queue_instance = FakeQueue()

    class FakeProcess:
        def __init__(self, *, target, args, daemon, name):
            captured.update(target=target, args=args, daemon=daemon, name=name)
            self.exitcode = None

        def start(self):
            call_kwargs = captured["args"][1]
            captured["call_kwargs"] = call_kwargs
            queue_instance.value = (
                "result",
                {
                    "text": '{"label":"status","confidence":0.94,"session_relevant":false}',
                    "status": "success",
                },
            )
            self.exitcode = 0

        def join(self, timeout=None):
            captured.setdefault("join_timeouts", []).append(timeout)

        def is_alive(self):
            return False

        def terminate(self):
            raise AssertionError("completed worker must not be terminated")

        def kill(self):
            raise AssertionError("completed worker must not be killed")

    class FakeContext:
        def Queue(self, maxsize):
            captured["queue_maxsize"] = maxsize
            return queue_instance

        def Process(self, **kwargs):
            return FakeProcess(**kwargs)

    monkeypatch.setattr(
        contract.multiprocessing,
        "get_context",
        lambda method: captured.setdefault("start_method", method) and FakeContext(),
    )

    parsed, status = contract._call_semantic_vote(
        AMBIGUOUS_REQUEST,
        _context(),
        adaptive_call_fn=None,
        timeout_seconds=0.2,
    )

    assert parsed == (contract.ContractLabel.STATUS, 0.94, False)
    assert status == "accepted"
    assert captured["start_method"] == "spawn"
    assert captured["daemon"] is True
    assert captured["call_kwargs"]["model"] == "qwen3:8b-q4_K_M"
    assert captured["call_kwargs"]["options"]["num_batch"] == 128
    assert captured["call_kwargs"]["options"]["num_ctx"] == 2048
    assert captured["call_kwargs"]["options"]["num_gpu"] == 999
    assert captured["queue_closed"] is True


def test_default_semantic_vote_deadline_terminates_spawned_process(monkeypatch) -> None:
    state = {"alive": False, "terminated": False, "closed": False}

    class TimeoutQueue:
        def get(self, timeout):
            raise contract.queue.Empty

        def close(self):
            state["closed"] = True

        def join_thread(self):
            pass

    class HangingProcess:
        exitcode = None

        def start(self):
            state["alive"] = True

        def join(self, timeout=None):
            pass

        def is_alive(self):
            return state["alive"]

        def terminate(self):
            state["terminated"] = True
            state["alive"] = False
            self.exitcode = -15

        def kill(self):
            raise AssertionError("terminate should end the fake worker")

    class TimeoutContext:
        def Queue(self, maxsize):
            return TimeoutQueue()

        def Process(self, **_kwargs):
            return HangingProcess()

    monkeypatch.setattr(
        contract.multiprocessing,
        "get_context",
        lambda _method: TimeoutContext(),
    )

    parsed, status = contract._call_semantic_vote(
        AMBIGUOUS_REQUEST,
        _context(),
        adaptive_call_fn=None,
        timeout_seconds=0.02,
    )

    assert parsed is None
    assert status == "deadline_exceeded"
    assert state == {"alive": False, "terminated": True, "closed": True}


def test_semantic_vote_reports_deadline_exceeded_separately() -> None:
    def overruns_wall(*_args, **_kwargs):
        time.sleep(0.15)
        return ""

    parsed, status = contract._call_semantic_vote(
        AMBIGUOUS_REQUEST,
        _context(),
        adaptive_call_fn=overruns_wall,
        timeout_seconds=0.02,
    )

    assert parsed is None
    assert status == "deadline_exceeded"


def test_only_true_low_coherence_keeps_the_warm_rephrase_line() -> None:
    decision = contract.decide_contract(
        'What do you make of "blorp fizzle invoice quantum"?',
        context=_context(),
        semantic_vote_enabled=False,
    )

    assert decision.label is contract.ContractLabel.LOW_COHERENCE
    assert decision.reply == contract.LOW_COHERENCE_CLARIFICATION
    assert decision.reply == "I didn't catch what you need — say it any way you like."
    assert clarification_policy.classify_vote_failure_kind(decision).value == "none"
    assert warm_clarification_for_vote_timeout(AMBIGUOUS_REQUEST, decision) is None


@pytest.mark.parametrize(
    "vote_status",
    ("error:TimeoutError", "deadline_exceeded", "invalid", "empty"),
)
def test_active_session_vote_failure_preserves_and_never_clarifies(
    vote_status: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(contract.CONTRACT_RECEIPT_DB_ENV, str(tmp_path / "contract.sqlite3"))
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *_args, **_kwargs: (None, vote_status),
    )
    context = _context(active=True)
    before = dict(context.session_snapshot)

    decision = contract.decide_contract(
        AMBIGUOUS_REQUEST,
        context=context,
        semantic_vote_enabled=True,
    )

    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.reason == "uncertain_active_session_preserved"
    assert decision.receipt.semantic_vote_status == vote_status
    assert is_outside_session_vote_failure(decision) is False
    assert (
        classify_vote_timeout_disposition(AMBIGUOUS_REQUEST, decision)
        is VoteTimeoutDisposition.NONE
    )
    assert warm_clarification_for_vote_timeout(AMBIGUOUS_REQUEST, decision) is None
    assert dict(context.session_snapshot) == before


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("what's on my plate tonight, and what actually needs me?", ExplicitDigestIntent.PLATE),
        ("What is on my plate?", ExplicitDigestIntent.PLATE),
        ("show me what's on my plate today", ExplicitDigestIntent.PLATE),
        ("what actually needs me today?", ExplicitDigestIntent.PLATE),
        ("what's on my plate this morning?", ExplicitDigestIntent.PLATE),
        ("what needs my attention today?", ExplicitDigestIntent.PLATE),
        ("what all is on my plate today?", ExplicitDigestIntent.PLATE),
        ("could you tell me what needs my attention today?", ExplicitDigestIntent.PLATE),
        ("would you tell me what actually needs me tonight?", ExplicitDigestIntent.PLATE),
        ("can you show me what needs my attention?", ExplicitDigestIntent.PLATE),
        ("what's on my plate for today?", ExplicitDigestIntent.PLATE),
        ("catch me up", ExplicitDigestIntent.DIGEST),
        ("can you catch me up?", ExplicitDigestIntent.DIGEST),
        ("could you please catch me up?", ExplicitDigestIntent.DIGEST),
        ("fill me in on where things stand", ExplicitDigestIntent.DIGEST),
        ("brief me on the current fleet", ExplicitDigestIntent.DIGEST),
        ("give me the current overview", ExplicitDigestIntent.DIGEST),
        ("give me a quick rundown of everything", ExplicitDigestIntent.DIGEST),
        ("could you give me a quick rundown?", ExplicitDigestIntent.DIGEST),
        ("can I get a quick rundown?", ExplicitDigestIntent.DIGEST),
        ("may I have the rundown?", ExplicitDigestIntent.DIGEST),
        ("I'd like a quick overview", ExplicitDigestIntent.DIGEST),
        ("give me my morning brief right now", ExplicitDigestIntent.DIGEST),
        ("summarize everything", ExplicitDigestIntent.DIGEST),
        ("recap where things stand", ExplicitDigestIntent.DIGEST),
        ("what's new?", ExplicitDigestIntent.DIGEST),
        ("the latest", ExplicitDigestIntent.DIGEST),
        ("overview", ExplicitDigestIntent.DIGEST),
        ("overview please", ExplicitDigestIntent.DIGEST),
    ),
)
def test_explicit_plate_and_digest_classifier_positive(
    text: str,
    expected: ExplicitDigestIntent,
) -> None:
    assert classify_explicit_digest_intent(text) is expected


@pytest.mark.parametrize(
    "text",
    (
        "what do you mean?",
        AMBIGUOUS_REQUEST,
        "update the St Anne's invoice",
        "what's the status of the Capital Hilton invoice?",
        "the overview wording is wrong",
        "summarize this email from Dane",
        "summarize the Capital Hilton invoice",
        "recap the email from Dane",
        "show me the digest authentication implementation",
        "I put the mix review on my plate",
        "the daily digest did not arrive",
        "I like the daily digest",
        "I like the rundown",
        "I like a quick overview",
        "update",
        "summary",
        "status",
        "status update",
        "could you tell me what needs my attention and send the invoice?",
        "show me what actually needs me, then update the ledger",
    ),
)
def test_explicit_plate_and_digest_classifier_rejects_mentions_and_domain_asks(
    text: str,
) -> None:
    assert classify_explicit_digest_intent(text) is ExplicitDigestIntent.NONE


def _timeout_receipt() -> dict[str, object]:
    return {
        "source": "semantic_vote",
        "label": "unresolved",
        "action": "pass_through",
        "reason": "uncertain_outside_session_fail_open",
        "semantic_vote_status": "deadline_exceeded",
        "model_called": True,
    }


def test_explicit_digest_exception_requires_deterministic_renderer_availability() -> None:
    text = "what's on my plate tonight, and what actually needs me?"
    receipt = _timeout_receipt()

    assert (
        classify_vote_timeout_disposition(text, receipt)
        is VoteTimeoutDisposition.CLARIFY
    )
    assert (
        classify_vote_timeout_disposition(
            text,
            receipt,
            deterministic_digest_available=True,
        )
        is VoteTimeoutDisposition.DETERMINISTIC_DIGEST
    )


def test_post_launder_assertion_restores_exact_warm_line() -> None:
    laundered_digest = (
        "Live Arts owes $1,095, St Anne's needs follow-up, and three unrelated items need review."
    )

    assert enforce_vote_timeout_output(
        AMBIGUOUS_REQUEST,
        laundered_digest,
        _timeout_receipt(),
    ) == WARM_TIMEOUT_CLARIFICATION


def test_post_launder_assertion_preserves_allowed_deterministic_digest() -> None:
    text = "give me the full digest"
    deterministic_digest = "Two grounded items need review."

    assert enforce_vote_timeout_output(
        text,
        deterministic_digest,
        _timeout_receipt(),
        deterministic_digest_available=True,
    ) == deterministic_digest


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source", "fallback"),
        ("label", "status"),
        ("action", "direct_answer"),
        ("reason", "optional_vote_disabled"),
        ("semantic_vote_status", "accepted_unresolved"),
    ),
)
def test_near_miss_receipts_never_trigger_clarification(field: str, value: str) -> None:
    receipt = _timeout_receipt()
    receipt[field] = value

    assert is_outside_session_vote_failure(receipt) is False
    assert warm_clarification_for_vote_timeout(AMBIGUOUS_REQUEST, receipt) is None
