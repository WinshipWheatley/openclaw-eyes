# Operator Artifact Links

Workers sometimes create useful reports in WSL paths or tool-private cache
folders that are not directly openable from the operator UI. Operator-facing
artifact reports must include openable paths, not only `file://` links.

## Required Link Set

For every operator-facing artifact, include:

- Source WSL path.
- Source Windows path when the artifact is on a mounted Windows drive or can be
  translated from WSL.
- Operator copy path when the source lives in a buried cache folder.
- Operator copy Windows path when applicable.
- Bridge or share path when one exists.
- Clear opening instructions.

## Operator Report Location

Prefer durable operator report copies under:

`/mnt/e/OpenClaw_Operator_Reports/<task_id>/`

If `/mnt/e` is unavailable, use:

`/tmp/openclaw-mission-control/operator_reports/<task_id>/`

`/tmp` artifacts may disappear after reboot, so any operator-facing note that
uses the fallback path must say that the path is temporary.

## Safety Rules

- Do not give only `file://` links.
- Always include both the original source path and the operator copy path.
- Copy operator reports; do not move originals.
- Never copy secrets, tokens, credentials, raw private documents, or other
  credential-bearing material into operator report folders.
- Do not export raw private finance, bank, tax, medical, or client source
  material unless the task explicitly authorizes that export.
- For durable artifacts, include the durable source path and the durable
  operator copy path.

## Helper

Use the local helper for report exports:

```bash
.venv/bin/python scripts/operator_artifact_link_normalizer.py \
  /path/to/report.md \
  --task-id example_task \
  --description "Short operator-facing description."
```

The helper writes:

- `artifact_manifest.json`
- `OPEN_ME.md`
- an operator copy of the report when the source file is safe to export

The original artifact remains in place.
