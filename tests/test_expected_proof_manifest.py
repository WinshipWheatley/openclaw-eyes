import os

def test_manifest_file_exists():
    """Verify that the Expected Proof Manifest v0 exists."""
    manifest_path = "docs/operations/OPENCLAW_EXPECTED_PROOF_MANIFEST_V0.md"
    assert os.path.exists(manifest_path), f"{manifest_path} does not exist"

def test_manifest_contains_v0_labels():
    """Verify that the manifest contains the required v0 proof labels."""
    manifest_path = "docs/operations/OPENCLAW_EXPECTED_PROOF_MANIFEST_V0.md"
    with open(manifest_path, "r") as f:
        content = f.read()
    
    expected_labels = [
        "generated_status_check",
        "ledger_inspector_summary",
        "orientation_snapshot_smoke",
        "cassandra_status_wiring_tests",
        "business_ops_ledger_tests"
    ]
    
    for label in expected_labels:
        assert label in content, f"Label {label} not found in manifest"

def test_manifest_contains_sections():
    """Verify that the manifest contains required sections."""
    manifest_path = "docs/operations/OPENCLAW_EXPECTED_PROOF_MANIFEST_V0.md"
    with open(manifest_path, "r") as f:
        content = f.read()
    
    expected_sections = [
        "## Purpose",
        "## v0 Proof Labels",
        "## Manifest Fields Definition",
        "## Important Doctrine",
        "## Non-Goals"
    ]
    
    for section in expected_sections:
        assert section in content, f"Section {section} not found in manifest"
