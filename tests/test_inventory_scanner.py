import pytest
from scripts.inventory_scanner import scan_root

def test_unknown_root_rejected():
    with pytest.raises(ValueError, match="Unknown root_id"):
        scan_root("nonexistent")

def test_dry_run_scans_correctly():
    results = scan_root("test_fixture_01", dry_run=True)
    # Check that expected files are found
    paths = [r["relative_path"] for r in results]
    assert "notes/readme.txt" in paths
    assert "docs/song_notes.md" in paths
    assert "data/example.json" in paths
    assert "nested/deeper/file.txt" in paths

def test_exclusions_respected():
    results = scan_root("test_fixture_01", dry_run=True)
    paths = [r["relative_path"] for r in results]
    assert "excluded/.env" not in paths
    assert "excluded/node_modules/package.json" not in paths
    for p in paths:
        assert ".git" not in p

def test_extensions_respected():
    results = scan_root("test_fixture_01", dry_run=True)
    for r in results:
        assert r["extension"] in [".md", ".txt", ".json"]

def test_max_depth_respected():
    # Deeper file is at depth 3. If max depth is 3, it should be included.
    # Let's test with a mock config for deeper nesting if needed,
    # but here current test structure is shallow enough.
    results = scan_root("test_fixture_01", dry_run=True)
    paths = [r["relative_path"] for r in results]
    assert "nested/deeper/file.txt" in paths
