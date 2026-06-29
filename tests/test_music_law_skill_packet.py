from __future__ import annotations

from pathlib import Path
import json

import chief_llm
from maestro_context_packet import build_maestro_context_packet
from maestro_cassandra_responder import answer_frontdoor_chat
from operator_truth_store import upsert_operator_truth
from protected_generate import protected_generate_with_receipt
from skill_loader import load_skills


QUESTION = "How do publishing splits work on a 50/50 co-write with a topliner?"
LAWYER_FLAG = "This is general information, not legal advice. Consult an entertainment lawyer before taking action."


def _seed_skill_catalog(catalog_path: Path) -> None:
    load_skills(
        "skills/music-law-advisory",
        include_patterns=("SKILL.md",),
        catalog_path=catalog_path,
        persist_catalog=True,
        strict_mode=True,
    )


def _seed_minimal_read_models(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "agent_presence.json").write_text(
        json.dumps({"agents": [{"agent_id": "chief", "display_name": "Chief", "actual_state": "online"}]}),
        encoding="utf-8",
    )
    (root / "chief_status_rail.json").write_text(
        json.dumps({"chief_current_status": "online", "chief_current_proven_role": {"role_summary": "Chief routes advisory answers."}}),
        encoding="utf-8",
    )


def test_music_law_skill_attaches_simple_tier_to_maestro_packet(tmp_path: Path, monkeypatch) -> None:
    catalog_path = tmp_path / "system_catalog.sqlite3"
    _seed_skill_catalog(catalog_path)
    monkeypatch.setenv("OPENCLAW_SYSTEM_CATALOG", catalog_path.as_posix())
    selector_kwargs = {}

    def fake_select_frontdoor_model(**kwargs):
        selector_kwargs.update(kwargs)
        return "qwen3:8b-q4_K_M", "frontdoor_largest_fitting"

    monkeypatch.setattr(
        chief_llm,
        "select_frontdoor_model",
        fake_select_frontdoor_model,
    )

    packet = build_maestro_context_packet(
        question=QUESTION,
        source_surface="operator_maestro_chat",
        read_model_root=tmp_path / "read_models",
        operator_truth_store_path=tmp_path / "truth.json",
        require_real_truth=False,
    )

    assert packet["skills"][0]["skill_id"] == "music_law_advisory"
    assert packet["skills"][0]["owner_agent"] == "chief"
    assert packet["skills"][0]["selected_tier"] == "simple"
    assert packet["skills"][0]["authority"] == "advisory_only"
    assert "chief_musiclaw_brain" in packet["skills"][0]["tools"]
    assert packet["skill_receipts"][0]["applied"] is True
    assert packet["skill_receipts"][0]["model_selected"] == "qwen3:8b-q4_K_M"
    assert packet["skill_receipts"][0]["selected_tier"] == "simple"
    assert selector_kwargs["max_gb"] == 6.0
    assert any(
        fact.get("topic") == "music_law_advisory" and "Default split when no agreement exists" in fact.get("value", "")
        for fact in packet["facts"]
    )
    assert LAWYER_FLAG in packet["packet_text"]
    assert "Music Law Advisory" in packet["packet_text"]
    assert packet["bounds"]["outbound_send_allowed"] is False


def test_protected_generate_receipt_records_applied_skill(tmp_path: Path) -> None:
    packet = {
        "schema_version": "maestro_context_packet_v0",
        "packet_id": "maestro_context_packet:test-skill",
        "source_surface": "operator_maestro_chat",
        "facts": [],
        "skills": [
            {
                "skill_id": "music_law_advisory",
                "owner_agent": "chief",
                "selected_tier": "simple",
                "authority": "advisory_only",
            }
        ],
        "skill_receipts": [
            {
                "skill_id": "music_law_advisory",
                "applied": True,
                "selected_tier": "simple",
                "authority": "advisory_only",
            }
        ],
    }

    outcome = protected_generate_with_receipt(
        QUESTION,
        context_packet=packet,
        generator_fn=lambda *_args, **_kwargs: {"text": f"Splits are negotiated. {LAWYER_FLAG}", "done_reason": "stop"},
        audit_log_path=tmp_path / "protected_generate_audit.jsonl",
        allow_live_model=False,
        front_door_profile=True,
        model_selected="qwen3:8b-q4_K_M",
    )

    assert outcome.receipt["skills_applied"] == ["music_law_advisory"]
    assert outcome.receipt["skill_receipts"][0]["skill_id"] == "music_law_advisory"
    assert outcome.receipt["skill_receipts"][0]["selected_tier"] == "simple"
    assert LAWYER_FLAG in outcome.text


def test_music_law_frontdoor_reuses_existing_safety_wrapper(tmp_path: Path, monkeypatch) -> None:
    catalog_path = tmp_path / "system_catalog.sqlite3"
    read_model_root = tmp_path / "read_models"
    truth_path = tmp_path / "truth.json"
    _seed_skill_catalog(catalog_path)
    _seed_minimal_read_models(read_model_root)
    upsert_operator_truth(
        "capital_hilton",
        "Probe invoice status is paid with $0 outstanding.",
        source_surface="test_music_law_skill_packet",
        path=truth_path,
    )
    monkeypatch.setattr(
        chief_llm,
        "select_frontdoor_model",
        lambda **_: ("qwen3:8b-q4_K_M", "frontdoor_largest_fitting"),
    )

    def fake_protected_generate(prompt, *, context_packet=None, **_kwargs):
        return {
            "text": "For a two-writer composition, the split is often equal if there is no signed split sheet.",
            "receipt": {
                "status": "ANSWER_READY",
                "decision": "INJECTED_PROTECTED_GENERATE",
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "skills_applied": ["music_law_advisory"],
                "skill_receipts": list(context_packet.get("skill_receipts", [])),
            },
        }

    result = answer_frontdoor_chat(
        QUESTION,
        session={
            "system_catalog_path": catalog_path.as_posix(),
            "read_model_root": read_model_root.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
        },
        protected_generate_fn=fake_protected_generate,
    )

    assert result.status == "ANSWER_READY"
    assert "This is general information, not legal advice." in result.plain_summary
    assert "Consult an entertainment lawyer before taking action." in result.plain_summary
    assert result.machine_proof["skills_applied"] == ["music_law_advisory"]
    assert result.machine_proof["skill_receipts"][0]["skill_id"] == "music_law_advisory"
