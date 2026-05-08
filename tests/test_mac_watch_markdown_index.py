import pytest
import time
from scripts.mac_watch_markdown_index import classify_file

def test_classify_top_level():
    info = {"relative_path": "Right now.md"}
    res = classify_file(info)
    assert res["is_top_level_loose"] is True
    assert res["group"] == "generated watch surfaces"

def test_classify_unknown_top_level():
    info = {"relative_path": "Something.md", "excerpt_preview": "normal"}
    res = classify_file(info)
    assert res["group"] == "top-level loose files"
    assert res["needs_deeper_review"] is True

def test_classify_legal():
    info = {"relative_path": "legal/Contract.md"}
    res = classify_file(info)
    assert res["group"] == "legal product docs"
    assert res["authority_guess"] == "legal_reference"

def test_classify_research():
    info = {"relative_path": "research/AI_Notes.md", "excerpt_preview": "TODO: fix this"}
    res = classify_file(info)
    assert res["group"] == "research/source material"
    assert "has_todos" in res["tags"]

def test_freshness():
    now = time.time()
    info = {"relative_path": "a/b.md", "modified_time": now - 3600} # 1 hour ago
    res = classify_file(info)
    assert res["freshness_class"] == "fresh"
    
    info_stale = {"relative_path": "a/b.md", "modified_time": now - 86400 * 10}
    res_stale = classify_file(info_stale)
    assert res_stale["freshness_class"] == "stale"
