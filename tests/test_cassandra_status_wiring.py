
import os
import json
import importlib.util
import sys
import types
import pytest
from unittest.mock import MagicMock, patch


def _stub_if_missing(module_name, **attrs):
    if importlib.util.find_spec(module_name) is not None:
        return
    module = types.ModuleType(module_name)
    for name, value in attrs.items():
        setattr(module, name, value)
    sys.modules[module_name] = module


_stub_if_missing("cassandra_email_config", get_review_inbox=lambda: "review@example.com")
_stub_if_missing(
    "finance_state",
    build_finance_snapshot=lambda *args, **kwargs: {},
    detect_finance_status_intent=lambda *args, **kwargs: False,
    find_finance_account=lambda *args, **kwargs: None,
    finance_entity_terms=lambda *args, **kwargs: (),
    format_finance_context=lambda *args, **kwargs: "",
    get_finance_payment_answer=lambda *args, **kwargs: None,
    get_finance_status_answer=lambda *args, **kwargs: None,
    load_finance_state=lambda *args, **kwargs: {},
)
_stub_if_missing(
    "capability_registry",
    get_actor=lambda *args, **kwargs: None,
    registry_context_for_query=lambda *args, **kwargs: None,
)
_stub_if_missing("cassandra_custom_tools", handle_operator_objective=lambda *args, **kwargs: None)
_stub_if_missing("operator_universal_intake", try_process_surface_operator_intake=lambda *args, **kwargs: None)
_stub_if_missing("cassandra_guided_review", process_guided_review_message=lambda *args, **kwargs: None)
_stub_if_missing("operator_context_switchboard", process_operator_context_switchboard_message=lambda *args, **kwargs: None)
_stub_if_missing(
    "cassandra_pii_hooks",
    tokenize_prompt=lambda prompt: (prompt, MockPIIContext()) if "MockPIIContext" in globals() else (prompt, None),
    rehydrate_reply=lambda reply, _ctx: reply,
    detokenize_for_dashboard=lambda text, *_args, **_kwargs: text,
)
from cassandra_brain import handle

class MockPIIContext:
    def __init__(self, is_empty=True):
        self.is_empty = is_empty

@pytest.fixture
def mock_state():
    return {
        "human_cues": [],
        "last_interaction_at": "2026-05-10 10:00:00"
    }

def test_ops_status_inquiry_triggers_deterministic_path():
    """
    Test that 'where are we' triggers the ops_status deterministic path.
    LLM should NOT be called.
    """
    user_text = "where are we"

    with patch("cassandra_brain._call", return_value="LLM response") as mock_call, \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", return_value=("safe prompt", MockPIIContext())), \
         patch("cassandra_brain._pii_rehydrate_reply", side_effect=lambda r, c: r), \
         patch("cassandra_brain.record_cassandra_packet_event", return_value=123):

        replies = handle(user_text)

        # LLM should NOT be called
        assert not mock_call.called
        assert "OpenClaw Orientation Status" in replies[0]

def test_ops_status_missing_surfaces():
    """
    Test behavior when status files are missing.
    """
    user_text = "where are we"

    with patch("pathlib.Path.exists", return_value=False), \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False):

        replies = handle(user_text)

        assert "Orientation status surfaces are missing" in replies[0]
        assert "scripts/generate_operator_status.py --check" in replies[0]
        assert "--write" in replies[0]


def test_system_knowledge_registry_query_triggers_deterministic_read_only_path(tmp_path):
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(
        json.dumps({"summary": {"root_count": 1, "directory_count": 2}, "directories": []}),
        encoding="utf-8",
    )

    with patch("cassandra_brain._call", return_value="LLM response") as mock_call, \
         patch("cassandra_brain.record_cassandra_packet_event", return_value="evt_should_not_write") as mock_record, \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain._log_conversation") as mock_log:

        replies = handle(
            "what's the system's shape / what does it know / not know / in orbit?",
            {
                "system_knowledge_repo_root": str(tmp_path),
                "system_knowledge_atlas_path": str(atlas_path),
            },
        )

    assert not mock_call.called
    assert not mock_record.called
    assert "OpenClaw System Knowledge" in replies[0]
    assert "Shape:" in replies[0]
    assert "Knows:" in replies[0]
    assert "Does not know:" in replies[0]
    assert "In orbit:" in replies[0]
    assert "no model call" in replies[0]
    assert mock_log.call_args.kwargs["route"] == "system_knowledge_registry_query"
    assert mock_log.call_args.kwargs["metadata"]["model_called"] is False

@pytest.mark.parametrize("query", [
    "what's up?",
    "where are we at?",
    "how are things looking?",
    "give me the lay of the land",
    "catch me up",
    "what's the move?",
    "what should I know?",
    "where do things stand?",
    "what's going on with OpenClaw?",
    "remind me what's current",
    "what did we just finish and what's next?",
    "I'm coming back in cold, orient me",
    "Hey Cassandra, I'm coming back in cold after a few hours away. Can you orient me and tell me what the move is?",
    "I'm lost, orient me",
    "what did we finish and what should I do next",
    "been gone a while, where are we",
    "what should I know before I keep going",
    "Hey Cassandra, I've been away from my desk for a bit and I'm losing the thread of what we were doing with the ledger and the snapshot. Could you catch me up and give me the orientation status so I know where to pick up?",
])
def test_fuzzy_status_intents_positive(query):
    """
    Test that fuzzy/natural language queries trigger the ops_status deterministic path.
    """
    with patch("cassandra_brain._handle_ops_status_inquiry", return_value="Deterministic Status") as mock_handle, \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", return_value=("safe", MockPIIContext())), \
         patch("cassandra_brain._pii_rehydrate_reply", side_effect=lambda r, c: r), \
         patch("cassandra_brain.record_cassandra_packet_event", return_value=123):

        replies = handle(query)
        assert mock_handle.called
        assert "Deterministic Status" in replies[0]

@pytest.mark.parametrize("query", [
    "what's up with the weather?",
    "what's the status of my invoice?",
    "catch me up on this email",
    "what's the move for dinner?",
    "is the payment status clear?",
    "gmail status update",
    "remind me to buy milk",
    "what's for lunch?",
    "Hey, what's up?", # Social/General greeting without OpenClaw context
    "How's it going today?",
])
def test_fuzzy_status_intents_negative(query, mock_state):
    """
    Test that queries that SHOULD NOT be ops_status do not trigger it.
    """
    with patch("cassandra_brain._handle_ops_status_inquiry") as mock_handle, \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value=mock_state), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", return_value=("safe", MockPIIContext())), \
         patch("cassandra_brain._pii_rehydrate_reply", side_effect=lambda r, c: r), \
         patch("cassandra_brain._call", return_value="LLM Response"), \
         patch("cassandra_brain.record_cassandra_packet_event", return_value=123):

        handle(query)
        assert not mock_handle.called
