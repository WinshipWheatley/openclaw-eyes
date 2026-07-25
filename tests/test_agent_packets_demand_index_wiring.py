"""Every agent packet reaches read-models beyond its hardcoded allowlist.

Class-level: Maestro was the acceptance instance; Cassandra, Guardian and
Hermes carry the same defect (7-9 hardcoded read-models out of ~500).
"""

from __future__ import annotations

import json
from pathlib import Path

import cassandra_context_packet
import guardian_context_packet
import hermes_context_packet
import pytest


AGENTS = (
    pytest.param(
        cassandra_context_packet,
        "_cassandra_read_model_facts",
        "CASSANDRA_READ_MODELS",
        id="cassandra",
    ),
    pytest.param(
        guardian_context_packet,
        "_guardian_read_model_facts",
        "GUARDIAN_READ_MODELS",
        id="guardian",
    ),
    pytest.param(
        hermes_context_packet,
        "_hermes_read_model_facts",
        "HERMES_READ_MODELS",
        id="hermes",
    ),
)


@pytest.mark.parametrize("module,fn_name,allowlist_name", AGENTS)
def test_agent_reaches_read_model_outside_its_allowlist(
    tmp_path: Path, module, fn_name: str, allowlist_name: str
) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    (root / "capital_hilton_agency_status.json").write_text(
        json.dumps({"agency": "Capital Hilton", "status": "active"}), encoding="utf-8"
    )
    assert "capital_hilton_agency_status.json" not in getattr(module, allowlist_name)

    _facts, _refs, proof = getattr(module, fn_name)(
        root, question="what is the capital hilton agency status"
    )

    assert proof.get("demand_selected_read_models") == ["capital_hilton_agency_status"]


@pytest.mark.parametrize("module,fn_name,allowlist_name", AGENTS)
def test_agent_does_not_pull_unrelated_read_models(
    tmp_path: Path, module, fn_name: str, allowlist_name: str
) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    (root / "capital_hilton_agency_status.json").write_text(
        json.dumps({"agency": "Capital Hilton"}), encoding="utf-8"
    )

    _facts, _refs, proof = getattr(module, fn_name)(
        root, question="what is the weather in paris tomorrow"
    )

    assert proof.get("demand_selected_read_models") == []
