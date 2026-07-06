#!/usr/bin/env bash
# sync_trusted_tests.sh — ANTI-BRITTLE #1
# One-command sync of a branch's LEGITIMATE test-expectation changes into the trusted-test ref,
# so green_gate's tests/ restore stops blocking approved changes (the "6-attempt drafts scramble").
#
# The gate (green_gate.sh) restores tests/ from OPENCLAW_TRUSTED_TEST_REF to stop branches from
# editing tests to pass. That's correct — but a LEGITIMATE test change (e.g. new approved copy)
# can never pass until the trusted ref is updated. This gives that update a safe, one-command lane
# with a WEAKENING DETECTOR so we never silently loosen the safety net.
#
# Usage:
#   scripts/sync_trusted_tests.sh <branch> [--push] [--force]
#     <branch>   branch whose test changes should sync (e.g. fable/promote-sendready)
#     --push     actually commit + push to the trusted ref (default: dry-run, show what would change)
#     --force    proceed even if the weakening detector flags a file (requires human judgment)
#
set -euo pipefail
BRANCH="${1:?usage: sync_trusted_tests.sh <branch> [--push] [--force]}"
shift || true
PUSH=0; FORCE=0
for a in "$@"; do case "$a" in --push) PUSH=1;; --force) FORCE=1;; esac; done

TRUSTED_REF="${OPENCLAW_TRUSTED_TEST_REF:-origin/codex/morning-test-deflake}"
BASE="${OPENCLAW_SYNC_BASE:-main}"
REMOTE_BRANCH="${TRUSTED_REF#origin/}"

cd "$(git rev-parse --show-toplevel)"
git fetch origin "${REMOTE_BRANCH}" >/dev/null 2>&1 || true

# test files the branch changed vs the base
mapfile -t CHANGED < <(git diff --name-only "${BASE}" "${BRANCH}" -- tests/ 2>/dev/null || true)
if [ "${#CHANGED[@]}" -eq 0 ]; then echo "[sync-trusted] no test files changed by ${BRANCH} vs ${BASE} — nothing to sync"; exit 0; fi

echo "[sync-trusted] branch=${BRANCH} trusted=${TRUSTED_REF} base=${BASE}"
echo "[sync-trusted] ${#CHANGED[@]} test file(s) changed by the branch"

WEAK=0
count_asserts() { git show "$1:$2" 2>/dev/null | grep -cE '^\s*(assert |self\.assert|def test_|with pytest\.raises)' || echo 0; }
for f in "${CHANGED[@]}"; do
  # skip files not tracked in the trusted ref (gate can't restore them anyway)
  if ! git cat-file -e "${TRUSTED_REF}:$f" 2>/dev/null; then echo "  [skip] $f — not tracked in trusted ref (gate uses branch copy)"; continue; fi
  if git diff --quiet "${TRUSTED_REF}" "${BRANCH}" -- "$f" 2>/dev/null; then echo "  [same] $f — already matches trusted ref"; continue; fi
  old=$(count_asserts "${TRUSTED_REF}" "$f"); new=$(count_asserts "${BRANCH}" "$f")
  if [ "$new" -lt "$old" ]; then
    echo "  [WEAKENING?] $f — assertions ${old} -> ${new} (FEWER). Review before syncing."
    WEAK=1
  else
    echo "  [ok] $f — assertions ${old} -> ${new} (additive/stronger)"
  fi
done

if [ "$WEAK" -eq 1 ] && [ "$FORCE" -eq 0 ]; then
  echo "[sync-trusted] BLOCKED: at least one file appears to WEAKEN coverage. Review the diff:"
  echo "  git diff ${TRUSTED_REF} ${BRANCH} -- tests/"
  echo "  Re-run with --force only if the reduction is genuinely correct (e.g. a removed obsolete test)."
  exit 2
fi

if [ "$PUSH" -eq 0 ]; then echo "[sync-trusted] DRY-RUN ok. Re-run with --push to commit + push to ${TRUSTED_REF}."; exit 0; fi

# apply the branch's versions of the (tracked) changed test files onto the trusted ref and push
WT="$(mktemp -d)"; TMPB="fable/sync-trusted-$$"
git worktree add -b "$TMPB" "$WT" "${TRUSTED_REF}" >/dev/null 2>&1
( cd "$WT"
  for f in "${CHANGED[@]}"; do git cat-file -e "${TRUSTED_REF}:$f" 2>/dev/null && git show "${BRANCH}:$f" > "$f"; done
  git add -A tests/
  git commit -q -m "test: sync approved test-expectation changes from ${BRANCH} into trusted ref

Anti-brittle: gives green_gate's trusted-test restore an approved-change lane
so legitimate test updates land without the manual scramble. Weakening-checked.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
  git push origin "HEAD:${REMOTE_BRANCH}" )
git worktree remove --force "$WT" >/dev/null 2>&1; git branch -D "$TMPB" >/dev/null 2>&1
git fetch origin "${REMOTE_BRANCH}" >/dev/null 2>&1
echo "[sync-trusted] ✅ pushed to ${TRUSTED_REF} ($(git rev-parse --short "${TRUSTED_REF}")). Re-gate ${BRANCH} now."
