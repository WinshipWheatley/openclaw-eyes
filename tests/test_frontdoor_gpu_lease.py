"""Front-door interactive GPU lease wiring (P5 resource orchestration).

The interactive front door must hold an "interactive" GPU lease while the local
model call runs — that is what lets builders defer/preempt instead of loading a
second model into the 6GB card mid-reply. The lease is ADVISORY for answering:
arbiter failure or denial must never block an operator answer (the arbiter is a
performance control, not a safety control).
"""

from pathlib import Path

import chief_llm
import protected_generate as pg
from polish_loop.gpu_arbiter import GPUArbiter

_PACKET = {
    "schema_version": "maestro_context_packet_v0",
    "packet_id": "maestro_context_packet:lease",
    "facts": [],
    "source_refs": [],
}


def _wire_live_frontdoor(monkeypatch, lease_db) -> dict:
    seen: dict = {}
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_PROFILE", "1")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_REPLY_TIMEOUT", "25")
    monkeypatch.setenv("OPENCLAW_GPU_LEASE_DB", str(lease_db))
    monkeypatch.setattr(pg, "_live_model_allowed", lambda *a, **k: True)
    monkeypatch.setattr(chief_llm, "ollama_is_unreachable", lambda **_k: False, raising=False)
    monkeypatch.setattr(
        chief_llm,
        "select_frontdoor_model",
        lambda **_k: ("qwen3.5:4b", "frontdoor_largest_fitting"),
        raising=False,
    )

    def fake_ollama(prompt, **kwargs):
        try:
            seen["lease_at_call"] = GPUArbiter(lease_db).current()
        except Exception:
            seen["lease_at_call"] = None
        return {
            "text": "Winship is the human operator.",
            "done_reason": "stop",
            "elapsed_ms": 5,
            "response_metadata": {},
        }

    monkeypatch.setattr(chief_llm, "ollama_call", fake_ollama)
    return seen


def test_frontdoor_acquires_and_releases_interactive_lease(tmp_path: Path, monkeypatch):
    lease_db = tmp_path / "gpu_leases.sqlite"
    seen = _wire_live_frontdoor(monkeypatch, lease_db)

    outcome = pg.protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=True,
        front_door_profile=True,
        agent="maestro",
    )

    assert seen["lease_at_call"] is not None
    assert seen["lease_at_call"]["holder_type"] == "interactive"
    assert seen["lease_at_call"]["holder_id"] == "frontdoor:maestro"
    assert GPUArbiter(lease_db).current() is None
    lease_receipt = outcome.receipt["gpu_lease"]
    assert lease_receipt["status"].startswith("acquired")
    assert lease_receipt["released"] is True
    assert outcome.receipt["model_fallback_reason"] == "model_ok"


def test_frontdoor_preempts_build_lease(tmp_path: Path, monkeypatch):
    lease_db = tmp_path / "gpu_leases.sqlite"
    build_lease = GPUArbiter(lease_db).acquire("build", "polish_loop:unit42")
    assert build_lease["status"] == "acquired"
    seen = _wire_live_frontdoor(monkeypatch, lease_db)

    outcome = pg.protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=True,
        front_door_profile=True,
        agent="maestro",
    )

    assert outcome.receipt["gpu_lease"]["status"] == "acquired_preempted_build"
    assert outcome.receipt["model_fallback_reason"] == "model_ok"
    assert GPUArbiter(lease_db).current() is None


def test_frontdoor_answers_when_arbiter_unavailable(tmp_path: Path, monkeypatch):
    lease_db = tmp_path / "not_a_db_dir"
    lease_db.mkdir()
    _wire_live_frontdoor(monkeypatch, lease_db)

    outcome = pg.protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=True,
        front_door_profile=True,
        agent="maestro",
    )

    assert outcome.receipt["gpu_lease"]["status"] == "arbiter_error"
    # The answer path must be unaffected by an arbiter failure.
    assert outcome.receipt["model_fallback_reason"] == "model_ok"
    assert outcome.receipt["model_output_delivered"] is True


def test_frontdoor_lease_disabled_in_test_mode_without_explicit_db(tmp_path: Path, monkeypatch):
    """Suite runs (OPENCLAW_TEST_MODE=1) must never write the fleet-shared lease
    path — regression for cross-test leakage caught by
    test_lease_and_lifecycle_dbs_default_under_loop_dir_not_real_home."""
    seen = _wire_live_frontdoor(monkeypatch, tmp_path / "unused.sqlite")
    monkeypatch.delenv("OPENCLAW_GPU_LEASE_DB", raising=False)
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

    outcome = pg.protected_generate_with_receipt(
        "Who is the operator?",
        context_packet=_PACKET,
        audit_log_path=tmp_path / "a.jsonl",
        allow_live_model=True,
        front_door_profile=True,
        agent="maestro",
    )

    assert outcome.receipt["gpu_lease"]["status"] == "disabled_test_mode"
    assert outcome.receipt["model_fallback_reason"] == "model_ok"
    assert not Path("/home/openclaw/.openclaw/polish_loop/gpu_leases.sqlite").exists()
