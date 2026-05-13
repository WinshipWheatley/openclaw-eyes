import json

import pytest

from scripts.build_source_inventory import BlockedExample, build_inventory
from scripts.promote_accepted_context import (
    PROMOTION_MANIFEST_VERSION,
    build_promotion_manifest,
    format_operator_promotion,
    main,
)


def _inventory(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "allowed.md").write_text("# Allowed\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "allowed.py").write_text('"""Allowed."""\n', encoding="utf-8")
    return build_inventory(
        root=tmp_path,
        allowlist=("docs/allowed.md", "scripts/allowed.py"),
        blocked_examples=(
            BlockedExample(
                ".chief.env",
                "secret_or_credential",
                "credential file is outside source inventory scope",
            ),
        ),
    )


def test_allowlisted_source_can_become_promotion_candidate(tmp_path):
    inventory = _inventory(tmp_path)

    manifest = build_promotion_manifest(
        inventory,
        requested_paths=("docs/allowed.md",),
        reason_for_promotion="needed for deterministic operator context",
    )

    assert manifest["manifest_version"] == PROMOTION_MANIFEST_VERSION
    assert manifest["summary"]["promoted_records"] == 1
    assert manifest["summary"]["refused_records"] == 0
    record = manifest["records"][0]
    assert record["path"] == "docs/allowed.md"
    assert record["promotion_state"] == "accepted_context_candidate"
    assert record["accepted_context_candidate"] is True
    assert record["eligible_for_extraction"] is True
    assert record["reason_for_promotion"] == "needed for deterministic operator context"


def test_blocked_source_cannot_be_promoted(tmp_path):
    inventory = _inventory(tmp_path)

    manifest = build_promotion_manifest(
        inventory,
        requested_paths=(".chief.env", "not-listed.md"),
        reason_for_promotion="attempt should fail closed",
    )

    assert manifest["summary"]["promoted_records"] == 0
    assert manifest["summary"]["refused_records"] == 2
    refusals = {item["path"]: item for item in manifest["refusals"]}
    assert refusals[".chief.env"]["eligible_for_extraction"] is False
    assert refusals[".chief.env"]["accepted_context_candidate"] is False
    assert "source_record_not_promotable" in refusals[".chief.env"]["reason_refused"]
    assert refusals["not-listed.md"]["reason_refused"] == "path_not_in_source_inventory_allowlist"


def test_promotion_does_not_ingest_bodies(tmp_path):
    manifest = build_promotion_manifest(
        _inventory(tmp_path),
        requested_paths=("scripts/allowed.py",),
        reason_for_promotion="metadata promotion only",
    )

    assert manifest["scope"]["body_ingested"] is False
    assert manifest["scope"]["source_body_read"] is False
    assert manifest["summary"]["body_ingested"] is False
    assert {record["body_ingested"] for record in manifest["records"]} == {False}
    assert {record["source_body_read"] for record in manifest["records"]} == {False}


def test_reason_for_promotion_is_required(tmp_path):
    with pytest.raises(ValueError, match="reason_for_promotion is required"):
        build_promotion_manifest(
            _inventory(tmp_path),
            requested_paths=("docs/allowed.md",),
            reason_for_promotion=" ",
        )


def test_runtime_authority_remains_false(tmp_path):
    manifest = build_promotion_manifest(
        _inventory(tmp_path),
        requested_paths=("docs/allowed.md", "scripts/allowed.py"),
        reason_for_promotion="non-runtime context substrate",
    )

    assert manifest["scope"]["runtime_authority"] is False
    assert manifest["scope"]["runtime_activation"] is False
    for record in manifest["records"]:
        assert record["runtime_authority"] is False
        assert record["authority_label"] != "runtime_authority"


def test_operator_output_uses_cockpit_grammar(tmp_path):
    manifest = build_promotion_manifest(
        _inventory(tmp_path),
        requested_paths=("docs/allowed.md", ".chief.env"),
        reason_for_promotion="operator cockpit read model",
    )
    output = format_operator_promotion(manifest)

    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert output.index("Evidence:") < output.index("Boundary:")
    assert output.index("Boundary:") < output.index("Blocked:")
    assert output.index("Blocked:") < output.index("Next safe move:")
    assert "metadata-only" in output
    assert "`body_ingested=false`" in output
    assert "`runtime_authority=false`" in output
    assert "No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated." in output
    assert '"records"' not in output
    assert "[PROMOTION]" not in output


def test_cli_json_output_is_machine_readable(capsys):
    exit_code = main(
        [
            "--format",
            "json",
            "--path",
            "scripts/generate_operator_status.py",
            "--reason",
            "needed for status context substrate",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["manifest_version"] == PROMOTION_MANIFEST_VERSION
    assert payload["summary"]["promoted_records"] == 1
    assert payload["scope"]["source_body_read"] is False
