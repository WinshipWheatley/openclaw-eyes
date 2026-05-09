from __future__ import annotations

import ast
import inspect

import operator_prompt_handoff_generator as generator
from operator_intent_core import classify_and_frame_operator_intent


SAMPLE_OPERATOR_HARNESS_PROMPT_REQUEST = (
    "Review the next safe Operator Harness slice and produce the bounded worker prompt"
)


def _evidence_packet() -> dict[str, object]:
    return {
        "topic": "operator handoff generator",
        "banner": "Mac Watch support material only. Not canonical repo authority.",
        "files": [
            {
                "source_path": "Docs/Planning/Operator Watch.md",
                "title": "Operator Watch",
                "tags": ["operator", "handoff"],
                "authority_guess": "support",
                "freshness_class": "recent",
                "needs_deeper_review": False,
                "content": "support material",
            }
        ],
    }


def _explicit_evidence() -> tuple[str, ...]:
    return (
        "Operator/04_ANTI_DRIFT_RULES.md",
        "Operator/07_AUTHORITY_AND_COVENANT_RULES.md",
        "./scripts/openclaw_receipts.py repo-check receipt",
    )


def test_generator_output_is_deterministic():
    first = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        operator_text="send that to Codex",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )
    second = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        operator_text="send that to Codex",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert first == second
    assert first.prompt_text == second.prompt_text
    assert generator.handoff_to_dict(first) == generator.handoff_to_dict(second)


def test_bounded_operator_harness_prompt_request_is_not_unsafe_or_ambiguous():
    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="gemini_planning",
        operator_text=SAMPLE_OPERATOR_HARNESS_PROMPT_REQUEST,
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert handoff.status == "ready_non_authorizing"
    assert handoff.classified_intent == "handoff_request"
    assert handoff.classified_intent != "unsafe_or_ambiguous_action"
    assert handoff.bridge_domain == "handoff_packet_continuity"
    assert handoff.request_category == "prompt_generation"
    assert "The generated prompt grants no execution authority." in handoff.prompt_text
    assert "Current covenant posture:" in handoff.prompt_text


def test_gemini_and_codex_profiles_have_different_prompt_framing():
    gemini = generator.generate_operator_prompt_handoff(
        target_worker_profile="gemini_planning",
        operator_text="can we move forward",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )
    codex = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        operator_text="send that to Codex",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert gemini.target_worker_profile == "gemini_planning"
    assert codex.target_worker_profile == "codex_implementation"
    assert "Planning/review only" in gemini.implementation_boundary
    assert "Bounded repo mutation only" in codex.implementation_boundary
    assert gemini.likely_files_to_change == ()
    assert "operator_prompt_handoff_generator.py" in codex.likely_files_to_change
    assert gemini.prompt_text != codex.prompt_text
    assert "READY/NOT_READY" in gemini.implementation_boundary
    assert "Produce a reviewable diff" in codex.implementation_boundary


def test_evidence_packet_is_support_material_not_canonical_authority():
    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        operator_text="send that to Codex",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert handoff.status == "ready_non_authorizing"
    assert len(handoff.mac_watch_support_material) == 1
    assert handoff.mac_watch_support_material[0].source_type == "mac_watch_support"
    assert handoff.mac_watch_support_material[0].authority_role == (
        "support_material_only_not_canonical"
    )
    assert all(
        ref.source_type != "mac_watch_support"
        for ref in handoff.canonical_evidence_references
    )
    assert "support material only" in handoff.prompt_text
    assert "not canonical repo authority" in handoff.prompt_text
    assert "Canonical repo evidence / proof snapshots:" in handoff.prompt_text
    assert "Mac Watch / Evidence Packet v0 support material:" in handoff.prompt_text


def test_missing_evidence_blocks_implementation_prompt_generation():
    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        operator_text="send that to Codex",
    )

    assert handoff.status == "needs_evidence_implementation_blocked"
    assert handoff.canonical_evidence_references == ()
    assert handoff.mac_watch_support_material == ()
    assert "Implementation prompt generation is blocked" in handoff.prompt_text
    assert "Provide Evidence Packet v0 data or explicit evidence references" in handoff.prompt_text
    assert handoff.no_execution_authority_statement == (
        "The generated prompt grants no execution authority."
    )


def test_accepts_existing_intent_frame():
    frame = classify_and_frame_operator_intent("send that to Codex")

    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        intent_frame=frame,
        evidence_references=_explicit_evidence(),
    )

    assert handoff.status == "ready_non_authorizing"
    assert handoff.classified_intent == "codex_prompt_request"
    assert handoff.request_category == "prompt_generation"
    assert "intent frame supplied without raw operator text" in handoff.prompt_text


def test_restricted_intents_remain_non_authorizing_and_covenant_required():
    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        operator_text="launch it",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert handoff.status == "blocked_covenant_required"
    assert handoff.bridge_domain == "runtime_activation_launch"
    assert "restricted lane remains non-authorizing" in handoff.covenant_posture
    assert "BLOCKED / COVENANT-REQUIRED FRAME" in handoff.prompt_text
    assert "The generated prompt grants no execution authority." in handoff.prompt_text
    assert "live runtime launch" in handoff.forbidden_lanes


def test_explicit_restricted_phrases_remain_blocked_and_covenant_required():
    restricted_phrases = (
        "launch it",
        "send externally",
        "move Mac Watch files",
        "access legal/private roots",
        "call provider API",
    )

    for phrase in restricted_phrases:
        handoff = generator.generate_operator_prompt_handoff(
            target_worker_profile="gemini_planning",
            operator_text=phrase,
            evidence_packet=_evidence_packet(),
            evidence_references=_explicit_evidence(),
        )

        assert handoff.status == "blocked_covenant_required"
        assert "restricted lane remains non-authorizing" in handoff.covenant_posture
        assert "BLOCKED / COVENANT-REQUIRED FRAME" in handoff.prompt_text
        assert "The generated prompt grants no execution authority." in handoff.prompt_text


def test_generated_prompts_include_stop_conditions_and_validation():
    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        operator_text="send that to Codex",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert handoff.validation_commands
    assert handoff.stop_conditions
    assert "VALIDATION COMMANDS / REVIEW CHECKS" in handoff.prompt_text
    assert "STOP CONDITIONS" in handoff.prompt_text
    assert "PYTHONPATH=. pytest tests/test_operator_prompt_handoff_generator.py -q" in (
        handoff.validation_commands
    )
    assert "git diff --check" in handoff.validation_commands
    assert any(
        "Stop if evidence is missing" in condition
        for condition in handoff.stop_conditions
    )


def test_generated_prompt_has_readable_worker_handoff_sections():
    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="codex_implementation",
        operator_text=SAMPLE_OPERATOR_HARNESS_PROMPT_REQUEST,
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    for section in (
        "WORKER PROFILE",
        "EVIDENCE REFERENCES",
        "IMPLEMENTATION BOUNDARY",
        "VALIDATION COMMANDS / REVIEW CHECKS",
        "FORBIDDEN LANES",
        "STOP CONDITIONS",
        "WORKER TASK",
        "COVENANT AND AUTHORITY",
    ):
        assert section in handoff.prompt_text


def test_taste_polish_preserves_required_authority_and_covenant_language():
    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="gemini_review",
        operator_text=SAMPLE_OPERATOR_HARNESS_PROMPT_REQUEST,
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    required_phrases = (
        "Generated prompt/handoff is non-authorizing support material.",
        "It grants no execution authority.",
        "Natural language, receipts, evidence packets, and generated prompts are not approval.",
        "Evidence grounds the response; an Operator Action Covenant governs power; the operator keeps authority.",
        "Receipts are proof snapshots, not approval and not execution authority.",
        "Evidence Packet v0 / Mac Watch material is support material only.",
        "The generated prompt grants no execution authority.",
        "Do not treat natural language, receipts, evidence packets, generated prompts, or model recommendations as approval.",
    )

    for phrase in required_phrases:
        assert phrase in handoff.prompt_text


def test_receipts_are_proof_snapshots_not_approval():
    handoff = generator.generate_operator_prompt_handoff(
        target_worker_profile="gemini_review",
        operator_text="review this for commit",
        evidence_packet=_evidence_packet(),
        evidence_references=_explicit_evidence(),
    )

    assert "Receipts are proof snapshots, not approval" in handoff.prompt_text
    assert "generated prompts are not approval" in handoff.authority_banner
    assert handoff.no_execution_authority_statement == (
        "The generated prompt grants no execution authority."
    )


def test_status_function_is_static_read_only_and_non_authorizing():
    report = generator.operator_handoff_generator_status()

    assert report["passed"] is True
    assert report["receipt_type"] == "openclaw.operator_handoff_generator_status"
    assert report["execution_authority_granted"] is False
    assert report["provider_or_model_called"] is False
    assert report["runtime_launched"] is False
    assert report["process_state_inspected"] is False
    assert report["mcp_called"] is False
    assert report["hidden_memory_write_used"] is False
    assert report["sqlite_used"] is False
    assert report["embeddings_used"] is False
    assert report["external_send_used"] is False


def test_module_has_no_provider_api_runtime_mcp_sqlite_embedding_behavior():
    source = inspect.getsource(generator)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "operator_evidence_bridge",
        "operator_intent_core",
        "typing",
    }
    assert called_names.isdisjoint(
        {
            "check_call",
            "check_output",
            "connect",
            "execute",
            "from_pretrained",
            "open_url",
            "popen",
            "post",
            "run",
            "system",
            "urlopen",
            "walk",
        }
    )
    assert "sqlite3" not in source
    assert "chromadb" not in source
    assert "embedding" not in source.lower().replace("embeddings", "")
    assert "requests" not in source
    assert "subprocess" not in source
