import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_voice_response_layer import TerminologyAdapter


def test_maestro_internal_brief_layer():
    adapter = TerminologyAdapter()

    result = adapter.context_layer("BLOCKED_PENDING_APPROVAL", role="maestro")

    assert result == "Ready and protected at your approval gate"


def test_clara_client_facing_layer():
    adapter = TerminologyAdapter()

    result = adapter.context_layer("BLOCKED_PENDING_APPROVAL", role="clara")

    assert result == "Everything is prepared. Once approved, we'll proceed."


def test_unknown_term_falls_back_to_original():
    adapter = TerminologyAdapter()

    result = adapter.context_layer("some_unknown_machine_token", role="maestro")

    assert result == "some_unknown_machine_token"


def test_unknown_role_falls_back_to_original():
    adapter = TerminologyAdapter()

    result = adapter.context_layer("BLOCKED_PENDING_APPROVAL", role="steel")

    assert result == "BLOCKED_PENDING_APPROVAL"


def test_send_hold_maestro_preserves_boundary_meaning():
    adapter = TerminologyAdapter()

    result = adapter.context_layer("SEND_HOLD", role="maestro")

    assert "send" in result.lower() or "locked" in result.lower()
    assert "approval" in result.lower()


def test_clara_never_hides_approval_gate():
    adapter = TerminologyAdapter()

    result = adapter.context_layer("BLOCKED_PENDING_APPROVAL", role="clara")

    assert "approved" in result.lower() or "approval" in result.lower()


def test_dual_label_payment_preserves_fidelity():
    adapter = TerminologyAdapter()

    maestro = adapter.context_layer("PAYMENT_PENDING", role="maestro")
    clara = adapter.context_layer("PAYMENT_PENDING", role="clara")

    assert "payment" in maestro.lower() or "scheduled" in maestro.lower()
    assert "payment" in clara.lower() or "confirmed" in clara.lower()
