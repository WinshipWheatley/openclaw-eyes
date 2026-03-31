#!/usr/bin/env bash
# run_polish_pass.sh
# Runs one autonomous PC Claude polish pass.
# Exits silently if it is not pc_turn.

set -euo pipefail
export PATH="/home/openclaw/.local/bin:$PATH"

LOOP_DIR="/home/openclaw/polish_loop"
STATUS_FILE="$LOOP_DIR/status.json"
OUTPUT_FILE="$LOOP_DIR/current/pc_output.md"
PROMPT_FILE="$LOOP_DIR/POLISH_PROMPT.md"
REVIEW_FILE="$LOOP_DIR/current/mac_review.md"
LOG_FILE="/mnt/c/OpenClaw/logs/polish_loop.log"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

# Read current state
STATUS=$(python3 -c "import json; print(json.load(open('$STATUS_FILE'))['status'])")
PASS_NUM=$(python3 -c "import json; print(json.load(open('$STATUS_FILE'))['pass'])")
TASK_NAME=$(python3 -c "import json; print(json.load(open('$STATUS_FILE')).get('task_name',''))")

if [ "$STATUS" != "pc_turn" ]; then
    echo "$(ts) [polish] Not pc_turn (status: $STATUS) — skipping." | tee -a "$LOG_FILE"
    exit 0
fi

ELEVATED=$(python3 -c "import json; print(json.load(open('$STATUS_FILE')).get('elevated_approved', False))")

echo "$(ts) [polish] pc_turn confirmed — pass ${PASS_NUM}, task: ${TASK_NAME}" | tee -a "$LOG_FILE"

# Build prompt — inject pass context and mac_review at the top so it can't be missed
if [ "$PASS_NUM" -gt 1 ] && [ -f "$REVIEW_FILE" ]; then
    PROMPT="$(cat << HEREDOC
=== MAC CLAUDE REVIEW — READ AND ACT ON THIS BEFORE ANYTHING ELSE ===
This is pass ${PASS_NUM} of task: ${TASK_NAME}

$(cat "$REVIEW_FILE")

=== END MAC CLAUDE REVIEW ===

Your job this pass: address every item listed under ISSUES TO FIX above.
Do NOT re-implement items listed under APPROVED ITEMS.
Write PASS: ${PASS_NUM} in your pc_output.md.

Output quality gate (required):
- Include `STATUS: DONE` (or `STATUS: BLOCKED` only if truly blocked).
- Include section headers exactly: `CHANGES:`, `REASONING:`, and `ROLLBACK PLAN:`.
- Keep each section concrete and specific to files changed this pass.

$(cat "$PROMPT_FILE")
HEREDOC
)"
else
    PROMPT="$(cat << HEREDOC
This is pass 1 of task: ${TASK_NAME}

Output quality gate (required):
- Include `STATUS: DONE` (or `STATUS: BLOCKED` only if truly blocked).
- Include section headers exactly: `CHANGES:`, `REASONING:`, and `ROLLBACK PLAN:`.
- Keep each section concrete and specific to files changed this pass.

$(cat "$PROMPT_FILE")
HEREDOC
)"
fi

# Run Claude with full tool access, non-interactively
if [ "$ELEVATED" = "True" ]; then
    echo "$PROMPT" | claude --model sonnet --dangerously-skip-permissions --print 2>&1 | tee -a "$LOG_FILE"
else
    echo "$PROMPT" | claude --model sonnet --print 2>&1 | tee -a "$LOG_FILE"
fi

echo "$(ts) [polish] Pass complete. Output at $OUTPUT_FILE" | tee -a "$LOG_FILE"
