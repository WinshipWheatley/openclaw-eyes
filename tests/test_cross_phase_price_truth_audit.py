from __future__ import annotations

import json
from pathlib import Path


def test_cross_phase_audit_maps_agents_and_flags_incomplete_price_surfaces(tmp_path: Path) -> None:
    from scripts import build_cross_phase_responsibility_map as audit

    generated = tmp_path / "generated" / "finance_packets"
    generated.mkdir(parents=True)
    (generated / "quote.md").write_text(
        "Quote total: $4,800. Sorry, this is just an estimate. Scope TBD. Needs confirmation.",
        encoding="utf-8",
    )

    payload = audit.build_audit(root=tmp_path, scan_roots=("generated",))

    assert payload["status"] == "READY"
    assert payload["machine_proof"]["read_only"] is True
    assert payload["price_surface_count"] == 1
    assert payload["defensive_surface_count"] == 1
    assert payload["unclear_surface_count"] == 1
    assert payload["incomplete_surface_count"] == 1
    owners = {row["primary_owner"] for row in payload["responsibility_matrix"]}
    assert {"chief", "guardian", "hermes", "niles", "maestro", "clara"}.issubset(owners)
    surface = payload["price_surfaces"][0]
    assert "$4,800" in surface["amount_mentions"]
    assert "labor" in surface["missing_dimensions"]
    assert "cost" in surface["missing_dimensions"]
    assert "approval" in surface["missing_dimensions"]


def test_cross_phase_audit_writes_markdown_report(tmp_path: Path) -> None:
    from scripts import build_cross_phase_responsibility_map as audit

    finance = tmp_path / "finance"
    finance.mkdir()
    (finance / "rate_card.json").write_text(
        json.dumps({"rate": "$125/hr", "labor": "2 hours", "scope": "sound support", "approval": "operator review"}),
        encoding="utf-8",
    )
    payload = audit.build_audit(root=tmp_path, scan_roots=("finance",))
    json_output = tmp_path / "generated" / "read_models" / "cross_phase_price_truth_audit.json"
    markdown_output = tmp_path / "artifacts" / "040_price_truth_and_cross_phase_audit.md"

    audit.write_outputs(payload, json_output=json_output, markdown_output=markdown_output)

    parsed = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert parsed["read_model_id"] == "cross_phase_price_truth_audit"
    assert "Cross-Phase Responsibility Matrix" in markdown
    assert "Missing Price Dimensions" in markdown
    assert "Price should signal earned reality" in markdown
