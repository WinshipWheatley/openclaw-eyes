import json

from scripts.build_source_inventory import (
    AUTHORITY_LABELS,
    DEFAULT_ALLOWLIST,
    DEFAULT_BLOCKED_EXAMPLES,
    INGESTION_STATES,
    build_inventory,
    format_operator_inventory,
    main,
)


REQUIRED_RECORD_FIELDS = {
    "path",
    "file_type",
    "extension",
    "size_bytes",
    "modified_time",
    "git_tracked",
    "committed_status",
    "source_class",
    "sensitivity_label",
    "authority_label",
    "ingestion_state",
    "reason_included",
    "allowed_for_agent_context",
    "body_ingested",
    "blocked_reason",
}


def _inventory():
    return build_inventory()


def test_allowlisted_files_are_included():
    inventory = _inventory()
    paths = {record["path"] for record in inventory["records"]}

    assert "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md" in paths
    assert "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md" in paths
    assert "docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md" in paths
    assert "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_VALIDATION_CONTRACT_V0.md" in paths
    for allowlisted_path in DEFAULT_ALLOWLIST:
        if not allowlisted_path.endswith("/"):
            assert allowlisted_path in paths


def test_non_allowlisted_paths_are_excluded():
    inventory = _inventory()
    paths = {record["path"] for record in inventory["records"]}

    assert "README.md" not in paths
    assert ".gitignore" not in paths
    assert "business_ops_ledger.py" not in paths


def test_no_go_examples_are_blocked_without_context_access():
    inventory = _inventory()
    records_by_path = {record["path"]: record for record in inventory["records"]}

    for example in DEFAULT_BLOCKED_EXAMPLES:
        record = records_by_path[example.path]
        assert record["ingestion_state"] == "blocked"
        assert record["allowed_for_agent_context"] is False
        assert record["body_ingested"] is False
        assert record["size_bytes"] is None
        assert record["git_tracked"] is None
        assert record["committed_status"] == "not_checked_no_go_boundary"
        assert record["blocked_reason"] == example.blocked_reason


def test_inventory_records_include_required_metadata_fields_and_labels():
    inventory = _inventory()

    for record in inventory["records"]:
        assert REQUIRED_RECORD_FIELDS <= set(record)
        assert record["ingestion_state"] in INGESTION_STATES
        assert record["authority_label"] in AUTHORITY_LABELS
        assert record["sensitivity_label"]
        assert record["reason_included"]


def test_inventory_is_metadata_only_and_no_body_is_ingested():
    inventory = _inventory()

    assert inventory["scope"]["body_ingested"] is False
    assert inventory["scope"]["sqlite_touched"] is False
    assert inventory["scope"]["whole_repo_scan"] is False
    assert inventory["scope"]["hard_drive_scan"] is False
    assert inventory["summary"]["body_ingested"] is False
    assert {record["body_ingested"] for record in inventory["records"]} == {False}


def test_operator_read_model_uses_required_grammar_and_is_not_raw_logs():
    output = format_operator_inventory(_inventory())

    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert output.index("Evidence:") < output.index("Boundary:")
    assert output.index("Boundary:") < output.index("Blocked:")
    assert output.index("Blocked:") < output.index("Next safe move:")
    assert "[SOURCE_INVENTORY]" not in output
    assert '"records"' not in output
    assert "metadata-only" in output
    assert "allowlist-only" in output


def test_inventory_does_not_imply_runtime_authority_or_activation():
    inventory = _inventory()
    output = format_operator_inventory(inventory).lower()

    assert inventory["scope"]["runtime_activation"] is False
    assert inventory["scope"]["agent_activation"] is False
    assert inventory["scope"]["broker_connection"] is False
    assert inventory["scope"]["customer_deployment"] is False
    assert "authority labels describe documentation/receipt/validation posture only" in output
    assert "do not grant runtime authority" in output
    for forbidden_claim in [
        "runtime ready",
        "runtime-ready",
        "modules active",
        "agent wired",
        "broker connected",
        "customer deployment active",
    ]:
        assert forbidden_claim not in output


def test_json_output_is_machine_readable_and_stable_enough_for_agents(capsys):
    exit_code = main(["--format", "json"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["inventory_version"] == "bounded_source_inventory_v0"
    assert payload["mode"] == "explicit_allowlist_metadata_only"
    assert isinstance(payload["records"], list)
    assert payload["records"]
    assert "generated_at" not in payload
    assert payload["records"][0]["path"]
    assert payload["records"][0]["body_ingested"] is False


def test_custom_allowlist_does_not_include_default_or_unlisted_paths(tmp_path):
    root = tmp_path
    (root / "allowed").mkdir()
    (root / "allowed" / "one.md").write_text("# One\n")
    (root / "not_allowed.md").write_text("# Not allowed\n")

    inventory = build_inventory(
        root=root,
        allowlist=("allowed/",),
        blocked_examples=(),
        include_blocked_examples=False,
    )
    paths = {record["path"] for record in inventory["records"]}

    assert paths == {"allowed/one.md"}
    record = inventory["records"][0]
    assert record["ingestion_state"] == "metadata_only"
    assert record["body_ingested"] is False


def test_explicit_no_go_allowlist_path_is_not_enumerated(tmp_path):
    root = tmp_path
    (root / "Legal").mkdir()
    (root / "Legal" / "case.md").write_text("# Synthetic no-go fixture\n")
    (root / "allowed.md").write_text("# Allowed\n")

    inventory = build_inventory(
        root=root,
        allowlist=("Legal/", "C:/Users/Winship/AppData/", "allowed.md"),
        blocked_examples=(),
        include_blocked_examples=False,
    )
    paths = {record["path"] for record in inventory["records"]}

    assert paths == {"allowed.md"}
