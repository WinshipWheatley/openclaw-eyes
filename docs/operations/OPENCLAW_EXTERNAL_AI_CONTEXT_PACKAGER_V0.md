# OpenClaw External AI Context Packager v0

## Purpose

External AI Context Packager v0 builds focused, upload-ready source packs for
ChatGPT Projects, Claude Projects, Codex sessions, Gemini sessions, generic ZIP
exports, and future local agents.

It exists to remove manual file hunting. It does not upload files or automate a
browser.

## Canonical Posture

- PC/WSL `/home/openclaw` remains the canonical backend repo and evidence-processing authority.
- Context packs are generated export artifacts under `generated/context_packs/`.
- Context packs are evidence/context surfaces, not truth promotion.
- Generated read-models remain the primary source basis for pack contents.

## Commands

Build the demo/current Mission Control pack:

```bash
python3 scripts/build_external_ai_context_pack.py --profile chatgpt_project --world build --focus mission_control_current --format operator
```

Query packs:

```bash
python3 scripts/query_external_ai_context_packs.py --report summary --format operator
python3 scripts/query_external_ai_context_packs.py --pack-id mission_control_current --format operator
```

Export read-model:

```bash
python3 scripts/export_external_ai_context_pack_read_model.py --format operator
```

## Output

Default pack path:

```text
generated/context_packs/mission_control_current/
```

Expected files:

- `00_START_HERE.md`
- `MANIFEST.json`
- `CURRENT_STATE.md`
- `NEXT_ACTIONS.md`
- `EVIDENCE_INDEX.md`
- `READ_MODEL_INDEX.md`
- `SAFETY_BOUNDARIES.md`
- `UPLOAD_INSTRUCTIONS.md`
- `selected_read_models/`
- `OpenClaw_ContextPack_mission_control_current.zip`

Generated read-model:

- `generated/read_models/external_ai_context_packs.json`
- `generated/read_models/external_ai_context_packs_OPERATOR.md`

## Selection Policy

The packager uses the shared generated read-model discovery helper.

Included:

- Safe top-level files under `generated/read_models/`.
- Human/operator `.md` and `.txt` read-model companions.
- Selected machine-state JSON files for current posture.

Excluded:

- Manifests.
- SQLite databases.
- Temp files.
- Hidden files.
- No-go/private/sensitive path hints.
- Non-selected raw JSON read-models.

## Target Profiles

Supported profiles:

- `chatgpt_project`
- `claude_project`
- `codex_session`
- `gemini_session`
- `local_agent`
- `generic_zip`

For `chatgpt_project`, the policy is advisory:

- Target roughly 40 source files.
- Upload in batches around 10 files.
- Prefer focused individual files over one giant ZIP.
- Start with `00_START_HERE.md`, `MANIFEST.json`, `CURRENT_STATE.md`, and `SAFETY_BOUNDARIES.md`.

## Boundaries

- No external upload.
- No browser automation.
- No network/API calls.
- No secret/private/legal/tax/CPA/client raw content.
- No no-go raw reads.
- No file moves, deletes, renames, or reorg.
- No runtime, tool, model, or agent activation.
- No action auto-execution.

