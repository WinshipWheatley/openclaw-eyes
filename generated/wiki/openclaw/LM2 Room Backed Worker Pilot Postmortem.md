# LM2 Room Backed Worker Pilot Postmortem

Status: `LM2_ROOM_BACKED_WORKER_PILOT_POSTMORTEM_READY`

This postmortem reads saved artifacts only. It does not invoke LM2, connect Ollama, send prompts or proof bundles, spawn workers, or perform business actions.

## What Failed

- The local Ollama CLI attempt returned output that was not valid JSON for the strict response schema.
- Failure class: `non_json_model_output / structured_output_boundary_failure`
- Adapter parse status: `PARSE_ERROR`

## Safety Findings

- Forbidden fields sent: `false`
- Protected action attempted: `false`
- Fallback published correctly: `true`
- Receipts complete: `true`
- Approval used exactly once: `true`

## Conclusion

- Failure class: non_json_model_output / structured_output_boundary_failure.
- Safety wrapper passed.
- Room-backed package passed.
- Fallback passed.
- Next attempt must not rely on plain text prompting alone.

## Structured Output Plan

- Current method: `ollama_cli_run_via_subprocess`
- Next method: `ollama_local_http_api_with_format_json_schema`
- Next attempt must use Ollama API `format` with the exact response JSON schema before another one-attempt approval is used.
- Verifier and fallback remain mandatory.
- Truth and authority checks must not be loosened.
