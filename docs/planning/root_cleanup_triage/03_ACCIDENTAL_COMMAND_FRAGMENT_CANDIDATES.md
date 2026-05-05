# Accidental Command-Fragment Candidates

Status: candidate list only. Command-fragment-looking means later review, not cleanup now.

## Candidate Paths

- `chmod`
- `chmod 700 4home`
- `mkdir -p 49dirname`
- `set -euo pipefail`
- `printf`
- `printf paste`
- `umask`
- `4secret-file0`
- `secret-file=4home`
- `hidden0`
- `5s\n`
- `4home`
- `700`
- `31`
- `077`
- `77`
- `9input`

## Why These Are Suspicious

These names look like shell command fragments, test artifacts, accidental pasted commands, or placeholder paths. Some also include secret-ish words. That makes them confusing and potentially noisy, but it does not make them safe to remove.

## Required Future Review Before Any Cleanup

Before any move, delete, archive, or rename proposal, a later metadata-only packet must capture:

1. Path exactly as found.
2. Type: file, directory, symlink, or other.
3. Size.
4. Modified time.
5. Git tracked, ignored, or untracked status.
6. Whether the path name is sensitive-looking.
7. Known references from authority docs or code search, without opening sensitive contents.
8. Proposed action.
9. Rollback plan.
10. Explicit operator approval.

## Stop Rule

If a path is secret-ish by name, referenced by runtime docs, unclear in ownership, or impossible to classify by metadata only, leave it in place and classify it as `unknown-human-review` or `sensitive/do-not-touch`.