# Mac-to-PC Import Execution Plan

Status: planning only. No Mac files have been imported.

## Verdict

This PC WSL session cannot access the actual approved Mac source files directly.

Narrow checks performed:

- `git status -sb --untracked-files=all` showed the PC repo clean: `## main...origin/main`.
- `/mnt/c/Users` exists.
- `/mnt/c/Users/Winship/OpenClaw_Watch` exists.
- `/mnt/c/Users/Open Claw/OpenClaw_Watch` does not exist.
- `/mnt/c/Users/openclawssh/OpenClaw_Watch` does not exist.
- `/mnt/c/Users/openclawssh.DESKTOP-HP/OpenClaw_Watch` does not exist.

The only reachable candidate root, `/mnt/c/Users/Winship/OpenClaw_Watch`, did not contain the approved Phase 1 paths:

- `operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md`
- `operator_harness_readiness/visual_brainstorm_packets/operator_harness_north_star_v1/`
- `docs/planning/operator_harness/DOMAIN_AGNOSTIC_OPERATOR_SYSTEMS.md`
- `docs/planning/operator_harness/STUDIO_BORN_OPERATOR_INTELLIGENCE.md`

Conclusion: use a Mac-side sanitized export bundle before any PC import.

## First Safest Import Slice

Import the visual/spatial markdown packet first:

- Source on Mac: `~/OpenClaw_Watch/operator_harness_readiness/visual_brainstorm_packets/operator_harness_north_star_v1/`
- Destination on PC: `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/`
- Allowed material: markdown and plain text only.
- Excluded material: images, screenshots, raw captures, code, binaries, private data, financial/legal/client material, credentials, and any local-only folder.

This slice is the safest because it is foundational doctrine/visual planning, has no implementation code requirement, and can be sanitized by file type before transfer.

## Mac-Side Export Bundle Prompt

Paste this into the Mac-side agent/session that can read `~/OpenClaw_Watch`.

```text
You are on the Mac that has access to ~/OpenClaw_Watch.

Task: create a sanitized docs-only export bundle for the first Mac-to-PC Operator Harness import. Do not modify source files. Do not copy raw screenshots, images, code, secrets, private material, financial/legal/client material, local-only raw captures, app containers, mail, cloud drives, external drives, provider configs, tokens, or keys.

Approved first import slice:
- Source: ~/OpenClaw_Watch/operator_harness_readiness/visual_brainstorm_packets/operator_harness_north_star_v1/
- Destination label for PC: docs/planning/launch_ladder/visual/operator_harness_north_star_v1/
- Include only markdown/text files: *.md, *.txt, *.markdown
- Exclude all images and binaries: *.png, *.jpg, *.jpeg, *.gif, *.webp, *.heic, *.pdf, *.mov, *.mp4, *.zip, *.tar, *.gz, executables, scripts, and any non-text assets.

Optional Phase 1 doctrine files, only if present and clearly non-sensitive:
- ~/OpenClaw_Watch/docs/planning/operator_harness/DOMAIN_AGNOSTIC_OPERATOR_SYSTEMS.md
- ~/OpenClaw_Watch/docs/planning/operator_harness/STUDIO_BORN_OPERATOR_INTELLIGENCE.md

Strict do-not-touch / do-not-import:
- ~/OpenClaw_Watch/operator_harness_readiness/local_capture/ledger_invoice_automation_capture/LOCAL_ONLY_RAW_DO_NOT_UPLOAD/
- law_program/
- .claude/
- Google Contract.md
- cassandra_forensic_audit.md
- secrets/
- vaults/
- legal, tax, ledger, client, private, bank, provider config, token, or key material
- raw screenshots or raw capture logs

Create the export bundle at:
~/OpenClaw_Watch_EXPORTS/operator_harness_docs_only_import_YYYYMMDD_HHMMSS/

Inside the bundle, create this structure:
- visual/operator_harness_north_star_v1/
- operator_harness_research/
- MANIFEST.md

Copy only approved markdown/text files into the matching bundle folders.

After copying, produce MANIFEST.md with:
- export timestamp
- source root
- every included source path
- proposed PC destination for each included file
- every exclusion rule applied
- confirmation that no images, binaries, code, local-only raw capture, secrets, private material, financial/legal/client material, provider configs, tokens, or keys were included

Run these verification commands from the Mac shell and include the output in MANIFEST.md:

find ~/OpenClaw_Watch_EXPORTS/operator_harness_docs_only_import_YYYYMMDD_HHMMSS -type f
find ~/OpenClaw_Watch_EXPORTS/operator_harness_docs_only_import_YYYYMMDD_HHMMSS -type f ! \( -name '*.md' -o -name '*.txt' -o -name '*.markdown' \)

The second command must return no files. Stop and report if it returns anything.

Do not compress the bundle unless explicitly asked. Do not send, upload, or sync it anywhere unless explicitly approved.
```

## Proposed Copy Map After Bundle Exists

Stop for operator approval before running any copy.

If the Mac creates the bundle at `~/OpenClaw_Watch_EXPORTS/operator_harness_docs_only_import_YYYYMMDD_HHMMSS/`, copy only these bundle paths into the PC repo:

| Export bundle path | PC destination |
| --- | --- |
| `visual/operator_harness_north_star_v1/*.md` | `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/` |
| `visual/operator_harness_north_star_v1/*.txt` | `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/` |
| `visual/operator_harness_north_star_v1/*.markdown` | `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/` |
| `operator_harness_research/DOMAIN_AGNOSTIC_OPERATOR_SYSTEMS.md` | `docs/planning/launch_ladder/operator_harness_research/DOMAIN_AGNOSTIC_OPERATOR_SYSTEMS.md` |
| `operator_harness_research/STUDIO_BORN_OPERATOR_INTELLIGENCE.md` | `docs/planning/launch_ladder/operator_harness_research/STUDIO_BORN_OPERATOR_INTELLIGENCE.md` |
| `MANIFEST.md` | `docs/planning/launch_ladder/mac_import_planning/import_manifests/operator_harness_docs_only_import_YYYYMMDD_HHMMSS.md` |

Do not import the doctrine files in the same step if the operator approves only the first visual/spatial slice.

## Explicit Do-Not-Import Exclusions

- Code or tests, including `bank_csv_to_reconciliation_report.py` and its test.
- Raw screenshots and all image/binary media.
- `LOCAL_ONLY_RAW_DO_NOT_UPLOAD/`.
- `local_capture/` raw capture logs and financial workflow captures.
- `law_program/`.
- `.claude/`.
- `Google Contract.md`.
- `cassandra_forensic_audit.md`.
- `secrets/`, `vaults/`, provider configs, tokens, keys, and credentials.
- Legal, tax, ledger, client, bank, financial, or private material.
- Cloud drives, external drives, mail stores, app containers, and broad filesystem scans.

## Validation Commands For Eventual Import

Run after the approved docs-only copy step:

```bash
git status -sb --untracked-files=all
git diff --check
python3 launch_ladder_contract_check.py
python3 -m pytest tests/test_launch_ladder_static_contract.py
```

Do not commit until the operator explicitly approves.
