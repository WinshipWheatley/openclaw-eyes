import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Adjust sys.path so we can import the script
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evidence_packet_generator import (
    is_safe_path,
    tokenize_topic,
    score_file,
    generate_packet,
)

@pytest.fixture
def mock_index_data():
    return {
        "files": [
            {
                "relative_path": "operator_harness/docs.md",
                "first_heading": "Operator Harness Documentation",
                "headings": ["Setup", "Build"],
                "excerpt_preview": "This explains how to build the operator harness next.",
                "tags": ["harness", "operator"],
                "group": "research/source material"
            },
            {
                "relative_path": "irrelevant/file.md",
                "first_heading": "Irrelevant Topic",
                "headings": [],
                "excerpt_preview": "Nothing to see here.",
                "tags": [],
                "group": "unknowns"
            },
            {
                "relative_path": "operator_harness/stale_notes.md",
                "first_heading": "Old Harness Notes",
                "headings": [],
                "excerpt_preview": "These are stale.",
                "tags": ["harness"],
                "group": "historical handoffs",
                "freshness_class": "stale"
            }
        ]
    }

def test_tokenize_topic():
    tokens = tokenize_topic("What should we build next for Operator Harness?")
    assert "operator" in tokens
    assert "harness" in tokens
    assert "build" in tokens  # 'build' is no longer in STOP_WORDS
    assert "what" not in tokens   # 'what' is in STOP_WORDS

def test_is_safe_path():
    assert is_safe_path("docs/some_file.md") is True
    assert is_safe_path("Right now.md") is True
    assert is_safe_path("/absolute/path") is False
    assert is_safe_path("-some_option.md") is False
    assert is_safe_path("some/../path") is False
    assert is_safe_path("path;rm -rf /") is False
    assert is_safe_path("path`") is False

def test_score_file(mock_index_data):
    file_info = mock_index_data["files"][0]
    score, matched = score_file(file_info, ["operator", "harness", "setup"])
    assert score > 0
    assert "headings" in matched
    assert "path" in matched

@patch("evidence_packet_generator.subprocess.run")
def test_generate_packet(mock_run, tmp_path, mock_index_data):
    # Setup mock SSH response
    mock_res = MagicMock()
    mock_res.stdout = "Mocked File Content"
    mock_res.returncode = 0
    mock_run.return_value = mock_res
    
    # Write mock index
    index_file = tmp_path / "mock_index.json"
    with open(index_file, "w") as f:
        json.dump(mock_index_data, f)
        
    out_dir = tmp_path / "out"
    
    # Run generation
    generate_packet("operator harness", str(index_file), str(out_dir), max_files=1)
    
    # Verify outputs
    json_files = list(out_dir.glob("*.json"))
    md_files = list(out_dir.glob("*.md"))
    
    assert len(json_files) == 1
    assert len(md_files) == 1
    
    with open(json_files[0], "r") as f:
        data = json.load(f)
    
    assert data["selected_count"] == 1
    assert data["files"][0]["source_path"] == "operator_harness/docs.md"
    assert "Mac Watch support material only" in data["banner"]
    
    # Verify SSH calls happened only after selection
    assert mock_run.call_count == 1
    args = mock_run.call_args[0][0]
    assert args[0] == "ssh"
    assert args[1] == "mac"
    assert "cat " in args[2]

@patch("evidence_packet_generator.subprocess.run")
def test_generate_packet_hard_cap(mock_run, tmp_path):
    mock_res = MagicMock()
    mock_res.stdout = "Mocked File Content"
    mock_res.returncode = 0
    mock_run.return_value = mock_res

    # Create an index with 20 relevant files
    files = []
    for i in range(20):
        files.append({
            "relative_path": f"file_{i}.md",
            "first_heading": "Test Heading",
            "excerpt_preview": "test",
        })
    index_data = {"files": files}
    index_file = tmp_path / "mock_index.json"
    with open(index_file, "w") as f:
        json.dump(index_data, f)
        
    out_dir = tmp_path / "out"
    
    # Request max 20, but hard cap is 12
    generate_packet("test", str(index_file), str(out_dir), max_files=20)
    
    json_files = list(out_dir.glob("*.json"))
    with open(json_files[0], "r") as f:
        data = json.load(f)
    
    assert data["selected_count"] == 12
    assert mock_run.call_count == 12

def test_generate_packet_rejects_unsafe_paths(tmp_path):
    index_data = {
        "files": [
            {
                "relative_path": "safe_file.md",
                "first_heading": "test",
            },
            {
                "relative_path": "unsafe;file.md",
                "first_heading": "test",
            },
            {
                "relative_path": "/absolute/test.md",
                "first_heading": "test",
            }
        ]
    }
    index_file = tmp_path / "mock_index.json"
    with open(index_file, "w") as f:
        json.dump(index_data, f)
        
    out_dir = tmp_path / "out"
    
    with patch("evidence_packet_generator.subprocess.run") as mock_run:
        mock_res = MagicMock()
        mock_res.stdout = "Mocked Content"
        mock_run.return_value = mock_res
        
        generate_packet("test", str(index_file), str(out_dir), max_files=10)
        
        json_files = list(out_dir.glob("*.json"))
        with open(json_files[0], "r") as f:
            data = json.load(f)
            
        # Only safe_file.md should be selected
        assert data["selected_count"] == 1
        assert data["files"][0]["source_path"] == "safe_file.md"

def test_score_file_boosts():
    file_info = {
        "relative_path": "packet/active_handoff.md",
        "group": "active packets and rails",
        "authority_guess": "project_authority",
        "freshness_class": "fresh",
        "tags": ["packet"]
    }
    # Topic doesn"t even match keywords, but it should get boosts if tokens match? 
    # Wait, score_file only adds boosts if score > 0 from keywords? No, current implementation adds them always.
    # Actually, current implementation adds them regardless of keyword matches.
    score, matched = score_file(file_info, ["nonexistent"])
    assert score == 15 + 5 + 5 + 20 # active_group + freshness + authority + active_handoff
    assert "active_group_boost" in matched
    assert "freshness_boost" in matched
    assert "authority_boost" in matched
