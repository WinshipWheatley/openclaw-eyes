"""Maestro packet reaches read-models beyond the hardcoded allowlist.

Before this wiring, `KNOWN_READ_MODELS` was a hardcoded 23 out of ~500, so the
other read-models were structurally invisible to the packet no matter how
relevant they were to the operator's question.
"""

from __future__ import annotations

import json
from pathlib import Path

import maestro_context_packet as packet


def _write(root: Path, name: str, payload: dict) -> None:
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


def test_question_relevant_read_model_outside_the_allowlist_is_reachable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    # NOT in KNOWN_READ_MODELS
    _write(
        root,
        "capital_hilton_agency_status.json",
        {"agency": "Capital Hilton", "status": "active"},
    )
    assert "capital_hilton_agency_status.json" not in packet.KNOWN_READ_MODELS

    _facts, refs, _proof = packet._read_model_facts(
        root, question="what is the capital hilton agency status"
    )

    assert "generated/read_models/capital_hilton_agency_status.json" in refs


def test_relative_root_still_resolves_like_production(tmp_path: Path, monkeypatch) -> None:
    """Production passes a repo-relative root; selection must still work."""

    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    _write(
        root,
        "capital_hilton_agency_status.json",
        {"agency": "Capital Hilton", "status": "active"},
    )
    monkeypatch.chdir(tmp_path)

    _facts, refs, proof = packet._read_model_facts(
        Path("generated/read_models"),
        question="what is the capital hilton agency status",
    )

    assert proof.get("demand_selected_read_models") == ["capital_hilton_agency_status"]
    assert "generated/read_models/capital_hilton_agency_status.json" in refs


def test_selection_failure_is_reported_not_disguised_as_no_match(
    tmp_path: Path,
) -> None:
    """A broken root must NOT look like an honest 'nothing matched'."""

    _facts, _refs, proof = packet._demand_selected_read_model_facts(
        tmp_path / "does_not_exist",
        question="capital hilton invoice",
        already_loaded=set(),
    )

    assert proof.get("demand_selection_error")


def test_unrelated_question_does_not_pull_extra_read_models(tmp_path: Path) -> None:
    root = tmp_path / "read_models"
    root.mkdir()
    _write(
        root,
        "capital_hilton_agency_status.json",
        {"agency": "Capital Hilton", "status": "active"},
    )

    _facts, refs, _proof = packet._read_model_facts(
        root, question="what is the weather in paris tomorrow"
    )

    assert "generated/read_models/capital_hilton_agency_status.json" not in refs
