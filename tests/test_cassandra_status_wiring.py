
import os
import pytest
from unittest.mock import patch
from cassandra_brain import handle

def test_ops_status_inquiry_triggers_deterministic_path():
    """
    Test that 'where are we' triggers the ops_status deterministic path.
    LLM should NOT be called.
    """
    user_text = "where are we"
    
    with patch("cassandra_brain._call", return_value="LLM response") as mock_call, \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", return_value=("safe prompt", {})), \
         patch("cassandra_brain._pii_rehydrate_reply", return_value="LLM response"):
         
        replies = handle(user_text)
        
        # LLM should NOT be called
        assert not mock_call.called
        assert "OpenClaw Orientation Status" in replies[0]
        assert "Active Lane" in replies[0]
        assert "Next Safe Move" in replies[0]
        assert "Confirmed Facts" in replies[0]
        assert "NOTE: No live runtime health" in replies[0]

def test_ops_status_missing_surfaces():
    """
    Test behavior when status files are missing.
    """
    user_text = "where are we"
    
    with patch("pathlib.Path.exists", return_value=False), \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False):
         
        replies = handle(user_text)
        
        assert "Orientation status surfaces are missing" in replies[0]
        assert "scripts/generate_operator_status.py --write" in replies[0]
