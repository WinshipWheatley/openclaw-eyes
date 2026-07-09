
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
import cassandra_brain

class MockPIIContext:
    def __init__(self, is_empty=True):
        self.is_empty = is_empty

@pytest.fixture
def mock_state():
    return {
        "human_cues": [],
        "last_interaction_at": "2026-05-10 10:00:00"
    }

def test_ops_status_inquiry_builds_packet_and_routes_through_model():
    """
    Test that 'where are we' builds deterministic packet context, then routes
    through Cassandra's model voice.
    """
    user_text = "where are we"

    with patch("cassandra_brain.external_language_model_call", return_value="Cassandra voice response") as mock_call, \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", side_effect=lambda prompt: (prompt, MockPIIContext())), \
         patch("cassandra_brain._pii_rehydrate_reply", side_effect=lambda r, c: r), \
         patch("cassandra_brain.record_cassandra_packet_event", return_value=123):

        replies = handle(user_text)

        assert replies == ["Cassandra voice response"]
        assert mock_call.called
        prompt = mock_call.call_args.args[0]
        assert "ORIENTATION_PACKET_JSON" in prompt
        assert "cassandra_orientation_status_v1" in prompt
        assert "Answer as Cassandra" in prompt
        assert mock_call.call_args.kwargs["timeout"] == 20
        assert mock_call.call_args.kwargs["metadata"]["data_classification"] == "sanitized_public"


def test_ops_status_inquiry_external_unavailable_falls_back_fast():
    """
    Test that missing/unavailable external model does not fall through to slow
    local generation on the Telegram path.
    """
    user_text = "where are we"

    with patch("cassandra_brain.external_language_model_call", return_value="") as mock_external, \
         patch("cassandra_brain._call") as mock_local_call, \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", side_effect=lambda prompt: (prompt, MockPIIContext())), \
         patch("cassandra_brain._pii_rehydrate_reply", side_effect=lambda r, c: r), \
         patch("cassandra_brain.record_cassandra_packet_event", return_value=123):

        replies = handle(user_text)

        assert mock_external.called
        assert not mock_local_call.called
        assert "OpenClaw Orientation" in replies[0]
        assert "Current documented lane" in replies[0]
        assert "Status: Ready for snapshot wording review." in replies[0]


def test_ops_status_deterministic_fallback_is_operator_facing():
    reply = cassandra_brain._handle_ops_status_inquiry("where are we")

    assert "OpenClaw Orientation" in reply
    assert "Current documented lane" in reply
    assert "Recommended next move" in reply
    assert "Confirmed" in reply
    assert "Not yet confirmed" in reply
    assert "Status: Ready for snapshot wording review." in reply
    assert "latest deterministic surfaces" not in reply
    assert "Active Lane:" not in reply
    assert "This handoff is the train" not in reply
    assert "choose one bounded next lane" not in reply

def test_handle_guards_a_leaked_reply_before_it_reaches_the_operator():
    """Task 144 (CLASS #5): handle() wraps _handle_unguarded so a leak from ANY internal
    branch (here: the ops-status model path) gets substituted with the safe fallback,
    not shipped to the operator."""
    import operator_surface_guard

    with patch(
        "cassandra_brain._answer_ops_status_inquiry",
        return_value=(
            "Here's the readback: livegmailaccessenabled=False (data gap)",
            {"packet_type": "cassandra_orientation_status_v1", "status": "ready"},
        ),
    ), \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", return_value=("safe", MockPIIContext())), \
         patch("cassandra_brain._pii_rehydrate_reply", side_effect=lambda r, c: r), \
         patch("cassandra_brain.record_cassandra_packet_event", return_value=123):

        replies = handle("where are we at")

    assert replies == [operator_surface_guard.SAFE_FALLBACK_REPLY_TEXT]
    assert "livegmailaccessenabled" not in replies[0]


def test_handle_still_returns_safe_replies_unchanged():
    """Sanity check: the guard wrap must not alter or block a genuinely safe reply."""
    with patch(
        "cassandra_brain._answer_ops_status_inquiry",
        return_value=(
            "Cassandra Status: all clear.",
            {"packet_type": "cassandra_orientation_status_v1", "status": "ready"},
        ),
    ), \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", return_value=("safe", MockPIIContext())), \
         patch("cassandra_brain._pii_rehydrate_reply", side_effect=lambda r, c: r), \
         patch("cassandra_brain.record_cassandra_packet_event", return_value=123):

        replies = handle("where are we at")

    assert replies == ["Cassandra Status: all clear."]


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
    Test that fuzzy/natural language queries trigger the model-mediated ops_status path.
    """
    with patch(
        "cassandra_brain._answer_ops_status_inquiry",
        return_value=(
            "Cassandra Status",
            {"packet_type": "cassandra_orientation_status_v1", "status": "ready"},
        ),
    ) as mock_handle, \
         patch("cassandra_brain.save_state"), \
         patch("cassandra_brain.load_state", return_value={"human_cues": []}), \
         patch("cassandra_brain.is_focus_mode", return_value=False), \
         patch("cassandra_brain.is_social_mode", return_value=False), \
         patch("cassandra_brain._pii_tokenize", return_value=("safe", MockPIIContext())), \
         patch("cassandra_brain._pii_rehydrate_reply", side_effect=lambda r, c: r), \
         patch("cassandra_brain.record_cassandra_packet_event", return_value=123):

        replies = handle(query)
        assert mock_handle.called
        assert "Cassandra Status" in replies[0]

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
    with patch("cassandra_brain._answer_ops_status_inquiry") as mock_handle, \
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
