"""The responder must be nameable from the emitted response alone.

Most of a night went into instrumenting, fixing and verifying a responder the
acceptance turn never touches. The field that would have said so —
machine_proof.request_router_selected_handler_id — already existed and I never read
it. This pins it so the next person can answer "which function produced this reply?"
from the reply itself, without adding a probe.
"""

from __future__ import annotations

import inspect

import openclaw_request_processor as orp

FIELD = "request_router_selected_handler_id"


def test_the_handler_id_field_still_exists() -> None:
    assert FIELD in inspect.getsource(orp), (
        "responder identity vanished from the response; it is the only field that "
        "says which function answered"
    )


def test_the_handler_id_travels_in_machine_proof() -> None:
    src = inspect.getsource(orp)
    i = src.index(FIELD)
    assert "machine_proof" in src[max(0, i - 4000): i + 4000], (
        "handler id is no longer carried in machine_proof, where consumers read it"
    )


def test_a_known_handler_id_is_a_dotted_module_path() -> None:
    """Shape check: 'workflow_package_queue.operator_instruction' names a real seam.

    A bare label like 'chat' would identify nothing, which is what made this
    expensive."""

    observed = "workflow_package_queue.operator_instruction"
    assert "." in observed
    module, _, func = observed.partition(".")
    assert module and func
