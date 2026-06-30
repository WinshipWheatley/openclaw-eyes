"""Front-door local-model profile bridge tests (spec 20260625-FDMODEL-v2).

SYNTHETIC ONLY — no real model call. The ollama HTTP layer is mocked (urlopen) and
the protected_generate model is exercised through an injected generator. Covers all
spec test cases plus the binding DEFAULT-OFF byte-identity proofs.
"""

from __future__ import annotations

import json
import socket
from contextlib import contextmanager

import pytest

import chief_llm
from frontdoor_prompt import build_frontdoor_prompt
from protected_generate import protected_generate_with_receipt


# ── ollama_call payload mocking ───────────────────────────────────────────────


class _FakeResp:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@contextmanager
def _capture_ollama_payload(monkeypatch, response_text="hello", raise_exc=None, response_body=None):
    """Patch urlopen used by ollama_call; capture the POST payload bytes."""
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["payload_bytes"] = req.data
        captured["timeout"] = timeout
        if raise_exc is not None:
            raise raise_exc
        return _FakeResp(response_body or {"response": response_text})

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", fake_urlopen)
    yield captured


# Test 1: default (no think/num_predict) → payload byte-identical to legacy.
def test_ollama_call_default_payload_byte_identical(monkeypatch):
    with _capture_ollama_payload(monkeypatch) as cap:
        out = chief_llm.ollama_call("hi", model="qwen3.5:4b", attempts=1)
    assert out == "hello"
    expected = json.dumps({"model": "qwen3.5:4b", "prompt": "hi", "stream": False}).encode("utf-8")
    assert cap["payload_bytes"] == expected
    # And explicitly: the decoded dict has exactly the three legacy keys.
    decoded = json.loads(cap["payload_bytes"].decode("utf-8"))
    assert set(decoded.keys()) == {"model", "prompt", "stream"}


# Test 2: think=False → payload has "think": false.
def test_ollama_call_think_false_adds_think(monkeypatch):
    with _capture_ollama_payload(monkeypatch) as cap:
        chief_llm.ollama_call("hi", model="qwen3.5:4b", attempts=1, think=False)
    decoded = json.loads(cap["payload_bytes"].decode("utf-8"))
    assert decoded["think"] is False


# Test 3: num_predict=200 → payload has options.num_predict=200 (merge not clobber).
def test_ollama_call_num_predict_adds_options(monkeypatch):
    with _capture_ollama_payload(monkeypatch) as cap:
        chief_llm.ollama_call("hi", model="qwen3.5:4b", attempts=1, num_predict=200)
    decoded = json.loads(cap["payload_bytes"].decode("utf-8"))
    assert decoded["options"]["num_predict"] == 200


def test_ollama_call_num_predict_merges_existing_options(monkeypatch):
    with _capture_ollama_payload(monkeypatch) as cap:
        chief_llm.ollama_call(
            "hi", model="qwen3.5:4b", attempts=1,
            num_predict=200, options={"temperature": 0.1},
        )
    decoded = json.loads(cap["payload_bytes"].decode("utf-8"))
    assert decoded["options"] == {"temperature": 0.1, "num_predict": 200}


# Test 4: both present together.
def test_ollama_call_think_and_num_predict_together(monkeypatch):
    with _capture_ollama_payload(monkeypatch) as cap:
        chief_llm.ollama_call("hi", model="qwen3.5:4b", attempts=1, think=False, num_predict=160)
    decoded = json.loads(cap["payload_bytes"].decode("utf-8"))
    assert decoded["think"] is False
    assert decoded["options"]["num_predict"] == 160
    assert decoded["model"] == "qwen3.5:4b"
    assert decoded["prompt"] == "hi"
    assert decoded["stream"] is False


# Test 5: mocked urlopen timeout → ollama_call returns "".
def test_ollama_call_timeout_returns_empty(monkeypatch):
    with _capture_ollama_payload(monkeypatch, raise_exc=socket.timeout("timed out")):
        out = chief_llm.ollama_call("hi", model="qwen3.5:4b", attempts=1)
    assert out == ""


def test_ollama_call_return_metadata_preserves_done_reason(monkeypatch):
    body = {
        "response": "hello",
        "done_reason": "length",
        "eval_count": 12,
        "total_duration": 123456,
    }
    with _capture_ollama_payload(monkeypatch, response_body=body) as cap:
        out = chief_llm.ollama_call(
            "hi",
            model="qwen3.5:4b",
            attempts=1,
            return_metadata=True,
        )
    assert out["text"] == "hello"
    assert out["done_reason"] == "length"
    assert out["response_metadata"]["eval_count"] == 12
    decoded = json.loads(cap["payload_bytes"].decode("utf-8"))
    assert decoded == {"model": "qwen3.5:4b", "prompt": "hi", "stream": False}


# ── select_frontdoor_model: sizing / ladder ──────────────────────────────────

_SIZES = {
    "qwen3.5:4b": 3.0,
    "qwen3:8b-q4_K_M": 5.5,
    "qwen3.5:9b": 6.5,
    "gemma4:26b": 18.0,
    "gemma4:31b": 22.0,
}


# Test 6: oversized gemma rejected even if "installed"; largest-fitting allowlist chosen.
def test_select_frontdoor_largest_fitting_excludes_gemma(monkeypatch):
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    installed = {"qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b", "gemma4:26b", "gemma4:31b"}
    model, reason = chief_llm.select_frontdoor_model(
        installed=installed, sizes=_SIZES, available_ram_gb=16.0
    )
    # ram budget = 16-4=12, max=12 → all qwen fit (<=6.5); largest fitting = 9b.
    assert model == "qwen3.5:9b"
    assert reason == "frontdoor_largest_fitting"
    assert model not in {"gemma4:26b", "gemma4:31b"}


def test_select_frontdoor_env_override_hard_filters_gemma(monkeypatch):
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", "gemma4:31b,qwen3.5:4b,gemma4:26b")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", "40")
    installed = {"qwen3.5:4b", "gemma4:26b", "gemma4:31b"}
    model, reason = chief_llm.select_frontdoor_model(
        installed=installed, sizes=_SIZES, available_ram_gb=64.0
    )
    assert chief_llm.FRONTDOOR_MODEL_ALLOWLIST() == ("qwen3.5:4b",)
    assert model == "qwen3.5:4b"
    assert reason == "frontdoor_largest_fitting"


def test_select_frontdoor_env_override_only_gemma_no_fitting_model(monkeypatch):
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", "gemma4:31b,gemma4:26b")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", "40")
    model, reason = chief_llm.select_frontdoor_model(
        installed={"gemma4:26b", "gemma4:31b"}, sizes=_SIZES, available_ram_gb=64.0
    )
    assert chief_llm.FRONTDOOR_MODEL_ALLOWLIST() == ()
    assert model is None
    assert reason == "no_fitting_model"


# Test 8 (ladder): when the larger allowlist model misses budget, a smaller one is chosen.
def test_select_frontdoor_falls_to_smaller_when_budget_tight(monkeypatch):
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    installed = {"qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b"}
    # available_ram=10 → budget = min(10-4, 12) = 6 → 9b(6.5) excluded, 8b(5.5) largest fitting.
    model, reason = chief_llm.select_frontdoor_model(
        installed=installed, sizes=_SIZES, available_ram_gb=10.0
    )
    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_largest_fitting"


def test_select_frontdoor_smallest_when_only_it_fits(monkeypatch):
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    installed = {"qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b"}
    # available_ram=8 → budget = min(8-4, 12) = 4 → only 4b(3.0) fits.
    model, reason = chief_llm.select_frontdoor_model(
        installed=installed, sizes=_SIZES, available_ram_gb=8.0
    )
    assert model == "qwen3.5:4b"
    assert reason == "frontdoor_largest_fitting"


def test_select_frontdoor_steps_down_when_free_vram_is_tight(monkeypatch):
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    installed = {"qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b"}
    model, reason = chief_llm.select_frontdoor_model(
        installed=installed,
        sizes=_SIZES,
        available_ram_gb=16.0,
        available_vram_gb=4.282,
        max_gb=6.0,
    )
    assert model == "qwen3.5:4b"
    assert reason == "frontdoor_step_down_vram_contention"


def test_select_frontdoor_uses_smallest_card_fit_when_vram_exhausted(monkeypatch):
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    installed = {"qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b"}
    model, reason = chief_llm.select_frontdoor_model(
        installed=installed,
        sizes=_SIZES,
        available_ram_gb=16.0,
        available_vram_gb=0.547,
        max_gb=6.0,
    )
    assert model == "qwen3.5:4b"
    assert reason == "frontdoor_step_down_vram_contention_ram_spill"


# Test 7: nothing fits → (None, "no_fitting_model").
def test_select_frontdoor_no_fitting_model(monkeypatch):
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    installed = {"qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b"}
    # available_ram=6 → budget = min(6-4, 12) = 2 → nothing fits (smallest is 3.0).
    model, reason = chief_llm.select_frontdoor_model(
        installed=installed, sizes=_SIZES, available_ram_gb=6.0
    )
    assert model is None
    assert reason == "no_fitting_model"


def test_select_frontdoor_empty_installed_means_unenumerated(monkeypatch):
    # Convention (mirrors _ollama_installed_models / resolve_local_model): an empty
    # installed-set means "couldn't enumerate", so the installed filter is skipped and
    # selection proceeds on the size budget alone — it must NOT be read as "nothing
    # installed". Largest fitting within the 12GB max is the 9b.
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    model, reason = chief_llm.select_frontdoor_model(
        installed=set(), sizes=_SIZES, available_ram_gb=64.0
    )
    assert model == "qwen3.5:9b"
    assert reason == "frontdoor_largest_fitting"
    assert model not in {"gemma4:26b", "gemma4:31b"}  # still excluded by 12GB max


def test_resolve_local_model_frontdoor_profile(monkeypatch):
    monkeypatch.setattr(chief_llm, "select_frontdoor_model", lambda **_: ("qwen3:8b-q4_K_M", "frontdoor_largest_fitting"))
    model, reason = chief_llm.resolve_local_model("hi", profile="frontdoor")
    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_largest_fitting"
    # task_class alias too
    model2, _ = chief_llm.resolve_local_model("hi", task_class="frontdoor_reply")
    assert model2 == "qwen3:8b-q4_K_M"


def test_resolve_local_model_chief_user_reply_untouched(monkeypatch):
    # chief_user_reply must NOT be repointed to the frontdoor ladder.
    monkeypatch.setattr(chief_llm, "_ollama_installed_models", lambda *a, **k: {"qwen3:8b-q4_K_M", "qwen3:4b"})
    model, lane = chief_llm.resolve_local_model("hi", task_class="chief_user_reply")
    assert model == "qwen3:8b-q4_K_M"
    assert lane == "strong"


def test_ollama_model_sizes_graceful_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("no ollama")
    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", boom)
    chief_llm._MODEL_SIZE_CACHE = None
    assert chief_llm._ollama_model_sizes(force_refresh=True) == {}


def test_ollama_model_sizes_parses_tags(monkeypatch):
    body = {"models": [{"name": "qwen3.5:4b", "size": 3_000_000_000},
                       {"name": "gemma4:26b", "size": 18_000_000_000}]}
    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", lambda *a, **k: _FakeResp(body))
    chief_llm._MODEL_SIZE_CACHE = None
    sizes = chief_llm._ollama_model_sizes(force_refresh=True)
    assert sizes["qwen3.5:4b"] == pytest.approx(3.0)
    assert sizes["gemma4:26b"] == pytest.approx(18.0)


# ── build_frontdoor_prompt: budgeting ─────────────────────────────────────────

def _packet(facts):
    return {"facts": facts}


# Test 9: packet under budget → all facts kept, Layer A present.
def test_build_frontdoor_prompt_under_budget_keeps_all():
    facts = [
        {"fact_id": "f1", "topic": "finance", "label": "Capital Hilton", "value": "owes 400"},
        {"fact_id": "f2", "topic": "calendar_day", "label": "Friday", "value": "gig at 8pm"},
    ]
    prompt, manifest = build_frontdoor_prompt(_packet(facts), "what does capital hilton owe", max_chars=2200)
    assert manifest["context_facts_kept"] == 2
    assert manifest["context_facts_dropped"] == 0
    assert manifest["over_budget"] is False
    # Layer A persona preamble always present.
    assert "You are Maestro" in prompt
    assert "Capital Hilton" in prompt
    assert manifest["prompt_chars"] <= 2200 + manifest["layer_a_chars"]


# Test 10 + 11: over budget → narrowed ≤ max_chars; fact_selection retained;
# Layer A reserve always present; manifest records kept/dropped; OUTPUT not truncated.
def test_build_frontdoor_prompt_over_budget_narrows_and_keeps_selection():
    big = "x" * 400
    facts = [
        {"fact_id": "sel1", "topic": "finance", "label": "Selected", "value": big,
         "source_ref": "generated/read_models/openclaw_finance.json"},
        {"fact_id": "p1", "topic": "system_posture", "label": "Fleet", "value": "all agents online " + big},
        {"fact_id": "p2", "topic": "agent_presence", "label": "Sync", "value": "sync health green " + big},
        {"fact_id": "g1", "topic": "calendar_day", "label": "Friday", "value": "gig at 8pm " + big},
    ]
    # Force narrowing while leaving room for the selected fact. The Layer-A grounded
    # preamble is ~471 chars; this budget keeps the interpreter-selected fact (highest
    # priority) and drops the lower-priority posture facts — which is what this test asserts.
    max_chars = 1000
    prompt, manifest = build_frontdoor_prompt(
        _packet(facts), "what does the finance read model say",
        max_chars=max_chars, fact_selection=["openclaw_finance.json"],
    )
    # Layer A reserve always present even when B is squeezed.
    assert "You are Maestro" in prompt
    # Context budget respected.
    assert manifest["prompt_context_chars"] <= max_chars
    # The interpreter-selected fact is retained (highest priority).
    assert "sel1" in manifest["kept_fact_ids"]
    # System-posture facts dropped first → at least one posture fact dropped.
    assert manifest["context_facts_dropped"] >= 1
    assert ("p1" in manifest["dropped_fact_ids"]) or ("p2" in manifest["dropped_fact_ids"])
    assert manifest["over_budget"] is True
    # OUTPUT is never the thing truncated — the prompt is context-only; the operator
    # message is appended verbatim and intact.
    assert "what does the finance read model say" in prompt


def test_build_frontdoor_prompt_layer_a_always_present_when_no_facts():
    prompt, manifest = build_frontdoor_prompt(_packet([]), "hello", max_chars=2200)
    assert "You are Maestro" in prompt
    assert manifest["context_facts_kept"] == 0


def test_build_frontdoor_prompt_empty_facts_do_not_set_over_budget():
    """over_budget reflects BUDGET narrowing only — empty/blank facts that get
    dropped for traceability must NOT flip over_budget (regression for the
    budget_narrowing_occurred fix). Everything fits; no budget pressure."""
    facts = [
        {"fact_id": "real1", "topic": "finance", "label": "Owed", "value": "St Anne's owes $400."},
        {"fact_id": "empty1", "topic": "calendar_day", "label": "", "value": ""},  # blank → dropped
    ]
    prompt, manifest = build_frontdoor_prompt(_packet(facts), "what is owed", max_chars=2200)
    assert "real1" in manifest["kept_fact_ids"]
    assert "empty1" in manifest["dropped_fact_ids"]  # dropped for traceability
    assert manifest["over_budget"] is False  # NOT budget pressure — just an empty fact


@pytest.mark.parametrize(
    ("agent", "question", "fact"),
    [
        (
            "cassandra",
            "what gigs do I have coming up?",
            {
                "fact_id": "gig_reynolds",
                "topic": "niles_reynolds_gig",
                "label": "Reynolds Tavern gig",
                "value": "Reynolds Tavern is scheduled for 2026-06-27 at 19:00 for $250.",
                "source_ref": "generated/read_models/niles_reynolds_gig.json",
            },
        ),
        (
            "maestro",
            "what invoices are open?",
            {
                "fact_id": "invoice_capital_hilton",
                "topic": "invoice_status",
                "label": "Capital Hilton invoice",
                "value": "Capital Hilton has an open Coupa invoice awaiting payment.",
                "source_ref": "generated/read_models/openclaw_finance.json",
            },
        ),
        (
            "guardian",
            "what approvals are required before I send this?",
            {
                "fact_id": "approval_send_hold",
                "topic": "approval_gate",
                "label": "SEND_HOLD approval",
                "value": "Guardian approval is required before any protected send action.",
                "source_ref": "generated/read_models/approval_gate.json",
            },
        ),
    ],
)
def test_build_frontdoor_prompt_keeps_question_domain_fact_for_agent(agent, question, fact):
    prompt, manifest = build_frontdoor_prompt(
        _packet([fact]),
        question,
        max_chars=2200,
        agent=agent,
    )
    assert fact["fact_id"] in manifest["kept_fact_ids"]
    assert fact["fact_id"] not in manifest["dropped_fact_ids"]
    assert str(fact["label"]) in prompt


# ── protected_generate_with_receipt: classification + telemetry ───────────────

_PACKET = {
    "facts": [
        {"topic": "identity", "label": "operator", "value": "Winship is the human operator."}
    ]
}

_FRONTDOOR_PACKET = {
    "schema_version": "maestro_context_packet_v0",
    "packet_id": "maestro_context_packet:test",
    "source_surface": "operator_maestro_chat",
    "facts": [
        {
            "fact_id": "identity:operator",
            "topic": "identity",
            "label": "operator",
            "value": "Winship is the human operator.",
            "source_ref": "generated/read_models/operator_truth.json",
        }
    ],
}

_TELEMETRY_KEYS = {
    "front_door_profile_used", "model_selected", "prompt_chars", "model_elapsed_ms",
    "model_timeout_s", "model_num_predict", "model_think", "done_reason",
    "model_fallback_reason", "response_truncated", "context_facts_kept",
    "context_facts_dropped", "prompt_context_chars", "model_call_attempted",
    "model_output_delivered", "delivered_response_source", "model_response_metadata",
    "model_selection_reason",
}


def _gen_returning(text, done_reason=None):
    def gen(system_prompt, **_kwargs):
        if done_reason is None:
            return text
        return {"text": text, "done_reason": done_reason}
    return gen


# Test 12: done_reason=stop complete → model_ok + all telemetry fields present.
def test_pgwr_frontdoor_stop_complete_model_ok(tmp_path):
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning("Winship is the operator.", done_reason="stop"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        interactive_timeout_s=30.0,
        num_predict=160,
        model_selected="qwen3:8b-q4_K_M",
        model_think=False,
        prompt_chars=512,
        context_facts_kept=1,
        context_facts_dropped=0,
    )
    r = outcome.receipt
    assert r["model_fallback_reason"] == "model_ok"
    assert r["response_truncated"] is False
    assert r["front_door_profile_used"] is True
    assert r["model_selected"] == "qwen3:8b-q4_K_M"
    assert r["model_num_predict"] == 160
    assert r["model_timeout_s"] == 30.0
    assert r["model_think"] is False
    assert r["done_reason"] == "stop"
    assert r["prompt_chars"] == 512
    assert r["context_facts_kept"] == 1
    assert r["model_elapsed_ms"] is not None
    assert r["model_call_attempted"] is True
    assert r["model_output_delivered"] is True
    assert r["delivered_response_source"] == "model"
    assert _TELEMETRY_KEYS.issubset(r.keys())
    assert "Winship is the operator." in outcome.text


# Test 13: done_reason=length but complete+validated utterance → model_ok, not truncated.
def test_pgwr_frontdoor_length_but_complete_is_model_ok(tmp_path, monkeypatch):
    import protected_generate as pg

    monkeypatch.setattr(pg, "_stage1_validate", lambda _text: (True, True, ()))
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning("Winship is the human operator here.", done_reason="length"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
    )
    r = outcome.receipt
    assert r["model_fallback_reason"] == "model_ok"
    assert r["response_truncated"] is False
    assert "Winship is the human operator here." in outcome.text


def test_pgwr_frontdoor_length_validator_unavailable_fails_closed(tmp_path, monkeypatch):
    import protected_generate as pg

    monkeypatch.setattr(pg, "_stage1_validate", lambda _text: (True, False, ()))
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning("Winship is the human operator here.", done_reason="length"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
    )
    r = outcome.receipt
    assert r["model_fallback_reason"] == "truncated"
    assert r["response_truncated"] is True
    assert r["validation_unavailable"] is True
    assert r["model_call_attempted"] is True
    assert r["model_output_delivered"] is False
    assert r["delivered_response_source"] == "grounded_fallback"


# Test 14: done_reason=length dangling/invalid → truncated, grounded fallback.
def test_pgwr_frontdoor_length_dangling_is_truncated(tmp_path):
    dangling = "Winship is the operator and he is currently working on the"
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning(dangling, done_reason="length"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
    )
    r = outcome.receipt
    assert r["model_fallback_reason"] == "truncated"
    assert r["response_truncated"] is True
    # Truncated text is NEVER delivered — answer comes from the grounded fallback.
    assert outcome.text != dangling
    assert "working on the" not in outcome.text
    # RECEIPT INTEGRITY: because the model output was DISCARDED, the receipt must NOT
    # claim a model answer was used, even though generator_fn was wired (regression for
    # the generator_fn_used fix). The delivered text is the grounded fallback.
    assert r["model_call_performed"] is False
    assert r["deterministic_fallback_used"] is True
    assert r["decision"] == "ALLOW_GROUNDED_FALLBACK"
    assert r["local_model_invoked"] is False
    assert r["model_call_attempted"] is True
    assert r["model_output_delivered"] is False
    assert r["delivered_response_source"] == "grounded_fallback"


# Test 15: timeout → timeout, fallback.
def test_pgwr_frontdoor_timeout(tmp_path):
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning("", done_reason="timeout"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        interactive_timeout_s=25.0,
    )
    r = outcome.receipt
    assert r["model_fallback_reason"] == "timeout"
    assert r["response_truncated"] is False
    assert r["model_call_attempted"] is True
    assert r["model_output_delivered"] is False
    assert r["delivered_response_source"] == "grounded_fallback"
    assert outcome.status == "ANSWER_READY"


# Test 16a: empty output → empty_output.
def test_pgwr_frontdoor_empty_output(tmp_path):
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning("", done_reason="stop"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
    )
    assert outcome.receipt["model_fallback_reason"] == "empty_output"


# Test 16b: unreachable → unreachable (no generator, live model on, ollama probe fails).
def test_pgwr_frontdoor_unreachable(tmp_path, monkeypatch):
    import protected_generate as pg

    monkeypatch.setattr(pg, "_live_model_allowed", lambda *a, **k: True)
    # Force the no-external-model + ollama-unreachable short-circuit.
    import chief_llm as cl
    monkeypatch.setattr(cl, "_configured_openrouter_model", lambda: "", raising=False)
    monkeypatch.setattr(cl, "ollama_is_unreachable", lambda **k: True, raising=False)
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=None,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=True,
        front_door_profile=True,
        interactive_timeout_s=25.0,
    )
    assert outcome.receipt["model_fallback_reason"] == "unreachable"


# Test 16c: test-mode / live model not allowed + no generator → never_invoked.
def test_pgwr_frontdoor_never_invoked(tmp_path):
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=None,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,  # test-mode equivalent
        front_door_profile=True,
    )
    assert outcome.receipt["model_fallback_reason"] == "never_invoked"
    assert outcome.receipt["model_call_attempted"] is False
    assert outcome.receipt["model_output_delivered"] is False


# Test 16d: no-fitting-model → no_fitting_model (caller threads done_reason + model_selected None).
def test_pgwr_frontdoor_no_fitting_model(tmp_path):
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=None,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        model_selected=None,
        done_reason="no_fitting_model",
    )
    assert outcome.receipt["model_fallback_reason"] == "no_fitting_model"
    assert outcome.receipt["model_call_attempted"] is False
    assert outcome.receipt["model_output_delivered"] is False


# Test 16e: validator-reject → validation_failed.
def test_pgwr_frontdoor_validation_failed(tmp_path):
    # A machine-contract leak (raw JSON structure) trips the Stage-1 validator.
    leak = '{"receipt_id": "abc", "status": "ANSWER_READY"}'
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning(leak, done_reason="stop"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
    )
    r = outcome.receipt
    assert r["model_fallback_reason"] == "validation_failed"
    # The leaking text is never delivered.
    assert outcome.text != leak
    assert r["model_call_attempted"] is True
    assert r["model_output_delivered"] is False


def test_pgwr_real_frontdoor_packet_flag_off_uses_legacy_path(tmp_path, monkeypatch):
    calls: dict = {}
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_PROFILE", raising=False)

    def gen(prompt, **kwargs):
        calls["prompt"] = prompt
        calls["kwargs"] = kwargs
        return "Legacy path answer."

    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_FRONTDOOR_PACKET,
        generator_fn=gen,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
    )
    assert "Big picture, then middle, then small." in calls["prompt"]
    assert "DETERMINISTIC PACKET:" in calls["prompt"]
    assert "front_door_profile_used" not in outcome.receipt
    assert _TELEMETRY_KEYS.isdisjoint(set(outcome.receipt.keys()))
    assert outcome.receipt["route"] == "injected_generator"
    assert outcome.receipt["model_call_performed"] is True
    assert "Legacy path answer." in outcome.text


def test_pgwr_real_frontdoor_packet_flag_on_auto_uses_profile_local_path(tmp_path, monkeypatch):
    import protected_generate as pg

    calls: dict = {}
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_PROFILE", "1")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_REPLY_TIMEOUT", "25")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_NUM_PREDICT", "180")
    monkeypatch.setattr(pg, "_live_model_allowed", lambda *a, **k: True)
    monkeypatch.setattr(chief_llm, "_configured_openrouter_model", lambda: "", raising=False)
    monkeypatch.setattr(chief_llm, "ollama_is_unreachable", lambda **_k: False, raising=False)
    monkeypatch.setattr(
        chief_llm,
        "select_frontdoor_model",
        lambda **_k: ("qwen3.5:4b", "frontdoor_largest_fitting"),
        raising=False,
    )

    def fake_ollama(prompt, **kwargs):
        calls["prompt"] = prompt
        calls["kwargs"] = kwargs
        return {
            "text": "Winship is the human operator.",
            "done_reason": "stop",
            "elapsed_ms": 42,
            "response_metadata": {"eval_count": 9, "total_duration": 123},
        }

    monkeypatch.setattr(chief_llm, "ollama_call", fake_ollama)
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_FRONTDOOR_PACKET,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=True,
    )
    r = outcome.receipt
    assert "You are Maestro" in calls["prompt"]
    # Grounded factual path (renamed label as of 836bb4d1: "OPERATOR QUESTION:" ->
    # "OPERATOR JUST SAID:"); the deterministic packet must still be present so a factual
    # question is answered from grounding, not routed to the conversational lane.
    assert "OPERATOR JUST SAID:" in calls["prompt"]
    assert "DETERMINISTIC PACKET" in calls["prompt"]
    assert calls["kwargs"]["model"] == "qwen3.5:4b"
    assert calls["kwargs"]["task_class"] == "frontdoor_reply"
    assert calls["kwargs"]["think"] is False
    assert calls["kwargs"]["num_predict"] == 180
    assert calls["kwargs"]["timeout"] == 25.0
    assert calls["kwargs"]["attempts"] == 1
    assert calls["kwargs"]["return_metadata"] is True
    assert r["front_door_profile_used"] is True
    assert r["model_selected"] == "qwen3.5:4b"
    assert r["model_timeout_s"] == 25.0
    assert r["model_num_predict"] == 180
    assert r["model_think"] is False
    assert r["done_reason"] == "stop"
    assert r["model_elapsed_ms"] == 42
    assert r["model_response_metadata"]["eval_count"] == 9
    assert r["model_fallback_reason"] == "model_ok"
    assert r["model_call_attempted"] is True
    assert r["model_output_delivered"] is True
    assert r["delivered_response_source"] == "model"
    assert r["context_facts_kept"] == 1
    assert "Winship is the human operator." in outcome.text


def test_pgwr_frontdoor_low_vram_steps_down_and_delivers_model(tmp_path, monkeypatch):
    import protected_generate as pg
    import frontdoor_resource_probe as frp
    from frontdoor_resource_probe import FrontdoorResourceSnapshot

    calls: dict = {}
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_PROFILE", "1")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_REPLY_TIMEOUT", "25")
    monkeypatch.setattr(pg, "_live_model_allowed", lambda *a, **k: True)
    monkeypatch.setattr(chief_llm, "_configured_openrouter_model", lambda: "", raising=False)
    monkeypatch.setattr(chief_llm, "ollama_is_unreachable", lambda **_k: False, raising=False)
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda *a, **k: {"qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b"},
        raising=False,
    )
    monkeypatch.setattr(chief_llm, "_ollama_model_sizes", lambda *a, **k: dict(_SIZES), raising=False)
    monkeypatch.setattr(
        frp,
        "probe_frontdoor_resources",
        lambda: FrontdoorResourceSnapshot(
            available_vram_gb=4.282,
            total_vram_gb=6.0,
            available_ram_gb=16.0,
            resident_models=[{"name": "resident-model", "size_vram_gb": 1.7}],
            probe_errors=[],
        ),
    )

    def fake_ollama(prompt, **kwargs):
        calls["prompt"] = prompt
        calls["kwargs"] = kwargs
        return {
            "text": "Winship is the human operator.",
            "done_reason": "stop",
            "elapsed_ms": 42,
            "response_metadata": {"eval_count": 9},
        }

    monkeypatch.setattr(chief_llm, "ollama_call", fake_ollama)
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_FRONTDOOR_PACKET,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=True,
    )
    assert calls["kwargs"]["model"] == "qwen3.5:4b"
    assert outcome.text == "Winship is the human operator."
    assert outcome.receipt["delivered_response_source"] == "model"
    assert outcome.receipt["model_fallback_reason"] == "model_ok"
    assert outcome.receipt["model_selected"] == "qwen3.5:4b"
    assert outcome.receipt["model_selection_reason"] == "frontdoor_step_down_vram_contention"


def test_pgwr_explicit_frontdoor_true_works_with_flag_off(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_PROFILE", raising=False)

    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_FRONTDOOR_PACKET,
        generator_fn=_gen_returning("Winship is the operator.", done_reason="stop"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
    )
    assert outcome.receipt["front_door_profile_used"] is True
    assert outcome.receipt["model_fallback_reason"] == "model_ok"
    assert outcome.receipt["model_output_delivered"] is True


def test_pgwr_explicit_frontdoor_false_overrides_flag_on(tmp_path, monkeypatch):
    calls: dict = {}
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_PROFILE", "1")

    def gen(prompt, **kwargs):
        calls["prompt"] = prompt
        calls["kwargs"] = kwargs
        return "Forced legacy answer."

    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_FRONTDOOR_PACKET,
        generator_fn=gen,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=False,
    )
    assert "Big picture, then middle, then small." in calls["prompt"]
    assert "front_door_profile_used" not in outcome.receipt
    assert _TELEMETRY_KEYS.isdisjoint(set(outcome.receipt.keys()))
    assert "Forced legacy answer." in outcome.text


# Test 17: flag-off / front_door_profile=False / params absent → receipts BYTE-IDENTICAL.
def test_pgwr_flag_off_no_new_telemetry_keys(tmp_path):
    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning("Winship is the operator.", done_reason="stop"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
    )
    keys = set(outcome.receipt.keys())
    # NONE of the front-door telemetry keys appear when the profile is off.
    assert _TELEMETRY_KEYS.isdisjoint(keys), f"unexpected telemetry keys: {_TELEMETRY_KEYS & keys}"
    assert "validation_unavailable" not in keys
    assert "validation_reasons" not in keys


def test_pgwr_flag_off_receipt_matches_baseline_schema(tmp_path):
    """The OFF receipt key-set must equal the legacy injected-generator key-set."""
    legacy_off = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        generator_fn=_gen_returning("Winship is the operator."),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
    )
    baseline_keys = {
        "schema_version", "receipt_id", "generated_at", "pii_tier", "packet_id",
        "agent", "prompt_hash", "packet_hash", "send_hold_active", "outbound_action_allowed",
        "money_movement_allowed", "ledger_mutation_allowed", "raw_values_written_to_audit",
        "status", "decision", "tokenization_applied", "token_count", "raw_values_included",
        "model_call_performed", "external_llm_invoked", "local_model_invoked", "route",
        "external_policy_safe", "external_policy_reason", "external_model_configured",
        "external_timeout_seconds", "local_timeout_seconds", "local_model_attempts",
        "ollama_probe_timeout_seconds", "ollama_unreachable_shortcircuit",
        "deterministic_fallback_used", "safe_prompt_hash", "audit_ref",
    }
    assert set(legacy_off.receipt.keys()) == baseline_keys


# ── front-door: strip the echoed agent speaker-label prefix ───────────────────
def test_pgwr_frontdoor_strips_echoed_agent_speaker_prefix(tmp_path):
    # The small local model sometimes echoes the prompt's trailing "Maestro:" speaker cue
    # at the very start of its reply. The delivered answer must not carry that label.
    outcome = protected_generate_with_receipt(
        "hey hows it going",
        context_packet=_FRONTDOOR_PACKET,
        generator_fn=_gen_returning("Maestro: hey, all good here — what's up?", done_reason="stop"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
    )
    assert outcome.receipt["model_fallback_reason"] == "model_ok"
    assert outcome.text == "hey, all good here — what's up?"
    assert not outcome.text.lower().startswith("maestro:")


def test_pgwr_frontdoor_strips_prefix_per_agent(tmp_path):
    # Agent-aware: a non-Maestro agent's own label is the one stripped.
    outcome = protected_generate_with_receipt(
        "yo",
        context_packet=_FRONTDOOR_PACKET,
        generator_fn=_gen_returning("Niles: right then, all sorted.", done_reason="stop"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        agent="niles",
    )
    assert outcome.text == "right then, all sorted."


def test_pgwr_frontdoor_keeps_non_leading_label_intact(tmp_path):
    # Only a LEADING own-name label is stripped; a mid-sentence mention is untouched.
    body = "All good — and yeah, Maestro: is just my name."
    outcome = protected_generate_with_receipt(
        "hey hows it going",
        context_packet=_FRONTDOOR_PACKET,
        generator_fn=_gen_returning(body, done_reason="stop"),
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=False,
        front_door_profile=True,
    )
    assert outcome.text == body
