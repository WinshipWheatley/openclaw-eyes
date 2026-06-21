from __future__ import annotations

import json
from pathlib import Path


def test_memory_boundary_audit_flags_global_sensitive_and_inference_findings(tmp_path: Path) -> None:
    from scripts import audit_agent_memory_boundaries as audit

    public = tmp_path / "generated" / "read_models"
    public.mkdir(parents=True)
    (public / "operator_profile.json").write_text(
        json.dumps(
            {
                "email": "winship@example.com",
                "note": "Inferred hypothesis: likely has a private personality type preference.",
                "project": "Capital Hilton invoice continuity.",
            }
        ),
        encoding="utf-8",
    )
    secret = tmp_path / ".chief.env"
    secret.write_text("SECRET_TOKEN=1234567890", encoding="utf-8")

    payload = audit.build_audit(root=tmp_path, scan_roots=("generated/read_models", "."))

    assert payload["status"] == "READY"
    assert payload["machine_proof"]["read_only"] is True
    assert payload["machine_proof"]["secret_paths_skipped"] is True
    assert payload["risky_global_memory_count"] >= 2
    risky_categories = {row["category"] for row in payload["risky_global_memory"]}
    assert {"F", "G"}.issubset(risky_categories)
    samples = " ".join(row["redacted_sample"] for row in payload["risky_global_memory"])
    assert "winship@example.com" not in samples
    assert "SECRET_TOKEN" not in samples
    assert "[EMAIL]" in samples


def test_memory_boundary_audit_writes_json_and_markdown_outputs(tmp_path: Path) -> None:
    from scripts import audit_agent_memory_boundaries as audit

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "memory.md").write_text("Client relationship detail and service preference.", encoding="utf-8")
    payload = audit.build_audit(root=tmp_path, scan_roots=("docs",))
    json_output = tmp_path / "generated" / "read_models" / "agent_memory_boundary_audit.json"
    markdown_output = tmp_path / "artifacts" / "039_memory_boundary_audit.md"

    audit.write_outputs(payload, json_output=json_output, markdown_output=markdown_output)

    parsed = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert parsed["read_model_id"] == "agent_memory_boundary_audit"
    assert "Phase III Memory Boundary Audit" in markdown
    assert "Category C" in markdown
    assert "Audit only" in markdown
