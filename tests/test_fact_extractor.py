
import pytest
import hashlib
from scripts.extract_canonical_facts import extract_markdown_sections

def test_extract_markdown_sections():
    mock_md = """# Project Overview
Some preamble text.

## Section 1
This is the content of section 1.

## Section 2
This is the content of section 2.
"""
    results = extract_markdown_sections(mock_md, "test.md", "commit123")
    
    assert len(results) == 2
    
    # Check section 1
    assert results[0]["source_file"] == "test.md"
    assert results[0]["source_commit"] == "commit123"
    assert results[0]["section_heading"] == "Section 1"
    assert "Project Overview > Section 1" in results[0]["fact_text"]
    assert "This is the content of section 1" in results[0]["fact_text"]
    
    # Check hash
    expected_hash = hashlib.sha256(results[0]["fact_text"].encode("utf-8")).hexdigest()
    assert results[0]["content_hash"] == expected_hash

def test_ignore_empty_sections():
    mock_md = """# Title
## Section 1
Content
## Section 2
"""
    results = extract_markdown_sections(mock_md, "test.md", "commit123")
    assert len(results) == 1
    assert results[0]["section_heading"] == "Section 1"

def test_defaults():
    results = extract_markdown_sections("## H\nBody", "f", "c")
    assert results[0]["sensitivity_class"] == "operational_canonical"
    assert "cassandra" in results[0]["allowed_actors"]
