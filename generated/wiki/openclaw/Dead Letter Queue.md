# Dead Letter Queue

Status: DEAD_LETTER_QUEUE_READY

No retries are executed by this queue. It records compact recovery metadata for failed, blocked, stale, or malformed package requests.

## Failure Kinds
- malformed_request (needs_operator): Ask Mission Control to resend a valid package request.
- missing_required_field (retry): Create a corrected request with the missing field included.
- unsafe_authority_requested (needs_operator): Keep it blocked and ask Guardian for an approval path.
- unknown_workflow_ref (investigate): Map the workflow or route it to system_question_answer for explanation.
- stale_response (investigate): Regenerate a compact status response from current local read models.
- missing_bridge_file (retry): Republish the specific read model to bridge after validation.
- service_not_current (investigate): Validate first, then restart only if request-response code changed.
- permission_required (needs_operator): Ask for the narrow filesystem permission needed for the target path.
- provider_gate_required (needs_operator): Leave provider work pending until the operator opens the protected lane.

Raw request bodies are not dumped; proof refs stay collapsed.
