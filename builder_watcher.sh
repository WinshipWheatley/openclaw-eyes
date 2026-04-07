#!/bin/bash
# Prevent SIGTSTP/SIGTTIN/SIGTTOU from stopping child processes when
# builder_watcher is launched via nohup or from a backgrounded terminal.
trap '' TSTP TTIN TTOU

bootstrap_runner_path() {
  local dir
  for dir in \
    /home/openclaw/.local/bin \
    /home/openclaw/.nvm/versions/node/*/bin \
    /home/openclaw/.vscode-server/extensions/openai.chatgpt-*/bin/linux-x86_64
  do
    [ -d "$dir" ] || continue
    case ":$PATH:" in
      *":$dir:"*) ;;
      *) PATH="$dir:$PATH" ;;
    esac
  done
  export PATH
}

bootstrap_runner_path

POLL_INTERVAL=10
STATUS_FILE="/home/openclaw/polish_loop/status.json"
PROMPT_FILE="/home/openclaw/polish_loop/POLISH_PROMPT.md"
PC_OUTPUT_FILE="/home/openclaw/polish_loop/current/pc_output.md"
CURRENT_TASK_FILE="/home/openclaw/polish_loop/current/task.md"
LEGACY_TASK_FILE="/home/openclaw/polish_loop/task.md"
LOG_FILE="/home/openclaw/builder_watcher.log"
ALERT_FILE="/home/openclaw/polish_loop/current/runner_alert.md"
MAX_LAUNCHES=3
COST_SURFACE="/home/openclaw/cost_truth_surface.py"

if [ -n "${CODING_RUNNER+x}" ]; then
  RUNNER_EXPLICIT=1
  RUNNER_PREFERRED="$CODING_RUNNER"
else
  RUNNER_EXPLICIT=0
  RUNNER_PREFERRED="codex"
fi

# NOTE: Watcher timeout (900s) intentionally exceeds Orchestrator BUILDER_TIMEOUT (600s).
# Orchestrator parks the task at 600s. Watcher's 900s is a last-resort kill for
# cases where Orchestrator itself is unresponsive. Do not align these values.

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

set_runner_alert() {
  local msg="$1"
  {
    echo "RUNNER STARTUP ALERT"
    echo "time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "message: $msg"
  } > "$ALERT_FILE"
}

clear_runner_alert() {
  rm -f "$ALERT_FILE" 2>/dev/null || true
}

guard_pattern_for_runner() {
  local runner="$1"
  if [ "$runner" = "codex" ]; then
    printf 'timeout [0-9]+ codex exec .*--sandbox workspace-write'
  elif [ "$runner" = "gemini" ]; then
    printf 'timeout [0-9]+ gemini .*--prompt'
  elif [ "$runner" = "ollama" ]; then
    printf 'timeout [0-9]+ ollama run'
  else
    printf 'timeout [0-9]+ codex exec .*--sandbox workspace-write'
  fi
}

task_file_for_builder() {
  if [ -f "$CURRENT_TASK_FILE" ]; then
    printf '%s\n' "$CURRENT_TASK_FILE"
  else
    printf '%s\n' "$LEGACY_TASK_FILE"
  fi
}

task_id_for_builder() {
  local task_file
  task_file="$(task_file_for_builder)"
  if [ ! -f "$task_file" ]; then
    printf 'unknown'
    return
  fi

  python3 - <<PY 2>/dev/null || printf 'unknown'
from pathlib import Path

task_file = Path("$task_file")
for line in task_file.read_text().splitlines():
    stripped = line.strip()
    if stripped.startswith("# Task:"):
        print(stripped.split(":", 1)[1].strip()[:80])
        break
else:
    print(task_file.stem[:80])
PY
}

build_fallback_invoke_cmd() {
  local runner="$1"
  local timeout="$2"
  local model="$3"
  local effort="$4"
  local budget="$5"
  local fallback_model="$6"

  if [ "$runner" = "codex" ]; then
    printf 'setsid timeout %s codex exec --sandbox workspace-write - < "%s"' "$timeout" "$PROMPT_FILE"
  elif [ "$runner" = "gemini" ]; then
    printf 'setsid timeout %s gemini --prompt "$(cat %s)" --yolo --output-format text' "$timeout" "$PROMPT_FILE"
  elif [ "$runner" = "ollama" ]; then
    printf 'setsid timeout %s ollama run gemma4:e4b < "%s"' "$timeout" "$PROMPT_FILE"
  else
    printf 'setsid timeout %s ollama run gemma4:e4b < "%s"' "$timeout" "$PROMPT_FILE"
  fi
}

normalize_invoke_cmd() {
  local runner="$1"
  local invoke_cmd="$2"
  local timeout="$3"
  local model="$4"
  local effort="$5"
  local budget="$6"
  local fallback_model="$7"

  if [ "$runner" = "gemini" ]; then
    build_fallback_invoke_cmd "$runner" "$timeout" "$model" "$effort" "$budget" "$fallback_model"
  else
    printf '%s\n' "$invoke_cmd"
  fi
}

fallback_runner_for() {
  local runner="$1"
  local task_type="${2:-standard}"
  # Primary: live registry-based selection — only picks runners that are installed.
  local registry_result
  registry_result=$(python3 /home/openclaw/runner_registry.py --fallback-for "$runner" --task-type "$task_type" 2>/dev/null)
  if [ "$registry_result" = "claude" ] || [ "$registry_result" = "gemini" ]; then
    registry_result=""
  fi
  if [ -n "$registry_result" ] && [ "$registry_result" != "None" ] && [ "$registry_result" != "null" ]; then
    printf '%s' "$registry_result"
    return
  fi
  # Safety fallback: static map used only if registry is unavailable.
  # Claude blocked from autonomous spawning — codex is default builder.
  case "$runner" in
    codex) printf 'ollama' ;;
    gemini) printf 'ollama' ;;
    ollama) printf 'codex' ;;
    *) printf 'ollama' ;;
  esac
}

# Validate pc_output.md after a runner completes.
# Returns "ok" on stdout if valid; otherwise a reason code ("missing",
# "empty", "no_pass_line", "quota_message").
# Exit 0 = valid, exit 1 = invalid.
validate_pc_output_result() {
  python3 /home/openclaw/polish_loop/builder_output_validator.py "$PC_OUTPUT_FILE" 2>/dev/null
  return $?
}

# Prepend "RUNNER: <name>" to pc_output.md for audit traceability.
# If a stale RUNNER: header is already present, replace it with the actual runner.
inject_runner_header() {
  local runner_name="$1"
  [ -f "$PC_OUTPUT_FILE" ] || return 0
  local first_line
  first_line=$(head -1 "$PC_OUTPUT_FILE" 2>/dev/null || echo "")
  local tmp="${PC_OUTPUT_FILE}.tmp"
  case "$(printf '%s' "$first_line" | tr '[:lower:]' '[:upper:]')" in
    RUNNER:*)
      local current_runner
      current_runner="${first_line#*:}"
      current_runner="$(printf '%s' "$current_runner" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
      [ "$current_runner" = "$runner_name" ] && return 0
      { printf 'RUNNER: %s\n' "$runner_name"; tail -n +2 "$PC_OUTPUT_FILE"; } > "$tmp" \
        && mv "$tmp" "$PC_OUTPUT_FILE" \
        || log "WARN: inject_runner_header replace failed for runner=$runner_name"
      ;;
    *)
      { printf 'RUNNER: %s\n' "$runner_name"; cat "$PC_OUTPUT_FILE"; } > "$tmp" \
        && mv "$tmp" "$PC_OUTPUT_FILE" \
        || log "WARN: inject_runner_header prepend failed for runner=$runner_name"
      ;;
  esac
}

any_builder_session_running() {
  # Prevent duplicate launches after watcher restart: detect active timed runner sessions.
  # Match any runner wrapped in setsid timeout (claude, codex, gemini, aider, ollama, etc.)
  pgrep -f 'timeout [0-9]+ (codex|gemini|aider|ollama)' >/dev/null 2>&1
}

launch_runner_once() {
  local runner="$1"

  clear_runner_alert

  # --- Smart profile selection via runner_profiles.py ---
  # runner_profiles.py now uses runner_registry.py internally to pick the
  # best available tool (claude, codex, gemini, aider, ollama, or any
  # plugin runner).  It returns a fully-built invoke_cmd.
  local profile_json
  profile_json=$(cd /home/openclaw && python3 runner_profiles.py 2>/dev/null)
  if [ -z "$profile_json" ]; then
    log "PROFILE: runner_profiles.py failed — falling back to hardcoded defaults"
    profile_json='{"runner":"codex","model":"default","effort":"high","timeout":600,"budget":2.0,"reason":"fallback","invoke_cmd":"setsid timeout 600 codex exec --sandbox workspace-write - < \"/home/openclaw/polish_loop/POLISH_PROMPT.md\"","defer":false}'
  fi

  local p_runner p_model p_effort p_timeout p_budget p_reason p_invoke_cmd p_defer p_tier p_task_id
  p_runner=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('runner','codex'))")
  p_model=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('model','sonnet'))")
  p_effort=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('effort','high'))")
  p_timeout=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('timeout',600))")
  p_budget=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('budget',2.0))")
  p_reason=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reason','unknown'))")
  p_invoke_cmd=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('invoke_cmd',''))")
  p_defer=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('defer',False))")
  p_tier=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tier','standard'))")
  local p_cascade p_cascade_count
  p_cascade=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cascade_decomposed',False))")
  p_cascade_count=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cascade_child_count',0))")

  # Forced runner path (fallback attempts): override profile-selected runner.
  # This ensures fast-failure fallback actually switches tools.
  if [ -n "$runner" ] && [ "$runner" != "$p_runner" ] && [ "$runner" != "$RUNNER_PREFERRED" ]; then
    log "PROFILE: Forced runner override -> $runner (profile had $p_runner)"
    p_runner="$runner"
    p_invoke_cmd=""  # use hardcoded fallback invocation for forced runner
  fi

  # Task deferral — budget says don't run this yet
  if [ "$p_defer" = "True" ]; then
    local defer_reason
    defer_reason=$(echo "$profile_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('defer_reason','budget exhausted'))")
    log "DEFER: Task deferred — $defer_reason"
    if [ "$p_cascade" = "True" ]; then
      # Cascade decomposition completed: write a valid pc_output so orchestrator
      # can advance to Planner review and then on to queued child tasks.
      local pass_num
      pass_num=$(python3 -c "import json; d=json.load(open('$STATUS_FILE')); print(d.get('pass',1))" 2>/dev/null || echo 1)
      {
        echo "PASS: $pass_num"
        echo "STATUS: DONE"
        echo "CHANGES:"
        echo "- Decomposed high-tier task into $p_cascade_count bounded child tasks"
        echo "- Queued child tasks for lower-tier execution (cascade delegation)"
        echo "REASONING:"
        echo "- Budget-edge condition detected for high-tier work"
        echo "- Planning-first cascade chosen to preserve quality while stepping down runner cost"
        echo "ROLLBACK PLAN:"
        echo "- Remove cascade-* child tasks from polish_loop/tasks if decomposition is not desired"
        echo "- Re-run parent task directly with higher-tier runner when budget allows"
        echo "COST:"
        echo "- Spend unavailable: deferred before a runner executed"
        echo "TRUTH:"
        echo "- Verified: cascade decomposition was emitted instead of a live builder run"
        echo "- Estimated: NONE"
        echo "- Unavailable: provider spend, tokens, and headroom for this deferred parent task"
        echo "HEADROOM:"
        echo "- Unknown: deferred before any provider invocation captured headroom"
      } > "$PC_OUTPUT_FILE"
      log "CASCADE: wrote pc_output for decomposed task (children=$p_cascade_count)"
    fi
    # Don't count this as a launch failure. Let orchestrator handle it.
    return 0
  fi

  # Override runner if explicitly requested via CODING_RUNNER
  if [ "$RUNNER_EXPLICIT" -eq 1 ] && [ "$RUNNER_PREFERRED" != "$p_runner" ]; then
    log "PROFILE: Explicit runner override → $RUNNER_PREFERRED (ignoring registry pick: $p_runner)"
    p_runner="$RUNNER_PREFERRED"
    # Fall back to hardcoded command for explicit override
    p_invoke_cmd=""
  fi

  LAST_EFFECTIVE_RUNNER="$p_runner"

  log "PROFILE: runner=$p_runner model=$p_model effort=$p_effort timeout=${p_timeout}s budget=\$${p_budget} tier=$p_tier reason='$p_reason'"

  # Verify the chosen runner binary exists
  if ! command -v "$p_runner" >/dev/null 2>&1; then
    log "ALERT: $p_runner CLI not found on PATH"
    set_runner_alert "$p_runner CLI missing from PATH"
    return 127
  fi

  # Record start time for cost tracking
  local run_start_ts
  run_start_ts=$(date +%s%3N)

  # Execute: use the pre-built invoke_cmd if available, otherwise hardcoded
  local run_exit_code=0
  local run_output_file="/tmp/builder_run_output_$$.json"
  local raw_output_file="/tmp/builder_raw_output_$$.txt"
  rm -f "$raw_output_file"
  local fallback_model="sonnet"
  if [ "$p_model" = "sonnet" ]; then
    fallback_model="haiku"
  fi
  if [ -n "$p_invoke_cmd" ]; then
    p_invoke_cmd="$(normalize_invoke_cmd "$p_runner" "$p_invoke_cmd" "$p_timeout" "$p_model" "$p_effort" "$p_budget" "$fallback_model")"
    log "INVOKE: $p_invoke_cmd"
    # For Claude with JSON output, capture cost data
    if [ "$p_runner" = "claude" ]; then
      local json_cmd
      json_cmd=$(echo "$p_invoke_cmd" | sed 's/--print/--print --output-format json/')
      cd /home/openclaw && eval "$json_cmd" > "$run_output_file" 2>> "$LOG_FILE"
      run_exit_code=$?
    else
      if [ "$p_runner" = "ollama" ]; then
        cd /home/openclaw && eval "$p_invoke_cmd" > "$raw_output_file" 2>> "$LOG_FILE"
      else
        cd /home/openclaw && eval "$p_invoke_cmd" >> "$LOG_FILE" 2>&1
      fi
      run_exit_code=$?
    fi
  else
    p_invoke_cmd="$(build_fallback_invoke_cmd "$p_runner" "$p_timeout" "$p_model" "$p_effort" "$p_budget" "$fallback_model")"
    log "INVOKE: $p_invoke_cmd"
    if [ "$p_runner" = "claude" ]; then
      local json_cmd
      json_cmd=$(echo "$p_invoke_cmd" | sed 's/--print/--print --output-format json/')
      cd /home/openclaw && eval "$json_cmd" > "$run_output_file" 2>> "$LOG_FILE"
      run_exit_code=$?
    else
      if [ "$p_runner" = "ollama" ]; then
        cd /home/openclaw && eval "$p_invoke_cmd" > "$raw_output_file" 2>> "$LOG_FILE"
      else
        cd /home/openclaw && eval "$p_invoke_cmd" >> "$LOG_FILE" 2>&1
      fi
      run_exit_code=$?
    fi
  fi

  local run_end_ts
  run_end_ts=$(date +%s%3N)
  local run_duration_ms=$(( run_end_ts - run_start_ts ))

  # For ollama, stage raw stdout into pc_output only if it looks valid enough
  # to hand to the normal validator. Otherwise leave pc_output absent.
  if [ "$p_runner" = "ollama" ]; then
    rm -f "$PC_OUTPUT_FILE"
    if [ -f "$raw_output_file" ] && [ -s "$raw_output_file" ]; then
      cp "$raw_output_file" "$PC_OUTPUT_FILE"
    fi
  fi

  # Stamp RUNNER immediately after the builder exits so pc_output.md is
  # self-identifying before orchestrator polls it or later augmentation runs.
  inject_runner_header "$p_runner"

  # Record the run in the execution receipt surface, then mirror measured
  # values into budget_tracker so both layers stay aligned.
  local actual_cost="0"
  local input_tokens="0"
  local output_tokens="0"
  local cache_read_tokens="0"
  local receipt_path=""
  if [ -f "$COST_SURFACE" ]; then
    local receipt_meta
    receipt_meta=$(
      RUNNER_NAME="$p_runner" \
      MODEL_REQUESTED="$p_model" \
      TASK_ID="$(task_id_for_builder)" \
      TIER_NAME="$p_tier" \
      EFFORT_LEVEL="$p_effort" \
      BUDGET_CAP="$p_budget" \
      DURATION_MS="$run_duration_ms" \
      EXIT_CODE="$run_exit_code" \
      STARTED_AT="$run_start_ts" \
      ENDED_AT="$run_end_ts" \
      SELECTION_REASON="$p_reason" \
      PROVIDER_JSON_PATH="$run_output_file" \
      python3 - <<'PY' 2>/dev/null
import json
import os
import sys

sys.path.insert(0, "/home/openclaw")

from cost_truth_surface import augment_pc_output, write_receipt

path, receipt = write_receipt(
    task_id=os.environ["TASK_ID"],
    runner=os.environ["RUNNER_NAME"],
    model_requested=os.environ["MODEL_REQUESTED"],
    tier=os.environ["TIER_NAME"],
    effort=os.environ["EFFORT_LEVEL"],
    budget_cap_usd=float(os.environ["BUDGET_CAP"] or 0),
    duration_ms=int(os.environ["DURATION_MS"] or 0),
    exit_code=int(os.environ["EXIT_CODE"] or 0),
    started_at=os.environ["STARTED_AT"],
    ended_at=os.environ["ENDED_AT"],
    selection_reason=os.environ["SELECTION_REASON"],
    provider_json_path=os.environ.get("PROVIDER_JSON_PATH") or None,
)
augment_pc_output(receipt=receipt)
print(json.dumps({
    "receipt_path": str(path),
    "actual_cost": receipt["cost"].get("total_cost_usd") or 0,
    "input_tokens": receipt["tokens"].get("input_tokens") or 0,
    "output_tokens": receipt["tokens"].get("output_tokens") or 0,
    "cache_read_tokens": receipt["tokens"].get("cache_read_tokens") or 0,
}))
PY
    )
    if [ -n "$receipt_meta" ]; then
      actual_cost=$(printf '%s' "$receipt_meta" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('actual_cost', 0))" 2>/dev/null || printf '0')
      input_tokens=$(printf '%s' "$receipt_meta" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('input_tokens', 0))" 2>/dev/null || printf '0')
      output_tokens=$(printf '%s' "$receipt_meta" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('output_tokens', 0))" 2>/dev/null || printf '0')
      cache_read_tokens=$(printf '%s' "$receipt_meta" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('cache_read_tokens', 0))" 2>/dev/null || printf '0')
      receipt_path=$(printf '%s' "$receipt_meta" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('receipt_path', ''))" 2>/dev/null || true)
    fi
  fi

  if [ "$actual_cost" != "0" ] || [ "$input_tokens" != "0" ] || [ -n "$receipt_path" ]; then
    log "COST: \$${actual_cost} for ${p_runner}/${p_model} (${run_duration_ms}ms, exit=${run_exit_code}, receipt=${receipt_path:-none})"
  elif [ -f "$run_output_file" ] && [ -s "$run_output_file" ]; then
    actual_cost=$(python3 -c "
import json, sys
try:
    d = json.load(open('$run_output_file'))
    print(d.get('total_cost_usd', 0))
except: print(0)
" 2>/dev/null)
    log "COST: \$${actual_cost} for ${p_runner}/${p_model} (${run_duration_ms}ms, exit=${run_exit_code})"
  fi

  # Record spend in budget tracker
  local task_completed="false"
  [ "$run_exit_code" -eq 0 ] && task_completed="true"
  python3 -c "
import budget_tracker
budget_tracker.record_spend(
    runner='$p_runner',
    model='$p_model',
    cost_usd=$actual_cost,
    task_id='$(task_id_for_builder)',
    input_tokens=$input_tokens,
    output_tokens=$output_tokens,
    cache_read_tokens=$cache_read_tokens,
    duration_ms=$run_duration_ms,
    completed=$task_completed,
    exit_code=$run_exit_code,
    tier='$p_tier',
)
" 2>/dev/null || log "BUDGET: Failed to record spend (budget_tracker error)"

  # Clean up
  rm -f "$run_output_file" 2>/dev/null

  return $run_exit_code
}

LAST_STATE=""
LAUNCH_COUNT=0
PARKED=0
FALLBACK_ATTEMPTED=0   # reset per pc_turn cycle; prevents double-fallback
LAST_EFFECTIVE_RUNNER=""

log "=== builder_watcher restarted (PID $$) ==="
source /home/openclaw/.chief.env
export PATH="/home/openclaw/.nvm/versions/node/v24.14.0/bin:$PATH"

# PID lock — prevent multiple instances
LOCKFILE="/tmp/builder_watcher.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ABORT: builder_watcher already running (PID lock)" >> "$LOG_FILE"; exit 1; }
echo $$ > "$LOCKFILE"

while true; do
  status=$(python3 -c "import json; d=json.load(open('$STATUS_FILE')); print(d.get('status',''))" 2>/dev/null)
  log "Polled status: '$status'"

  if [ "$status" != "pc_turn" ]; then
    if [ "$LAUNCH_COUNT" -gt 0 ]; then
      log "RESET: State changed to '$status'. Clearing launch counter."
    fi
    LAUNCH_COUNT=0
    PARKED=0
    FALLBACK_ATTEMPTED=0
  fi

  if [ "$status" = "pc_turn" ] && [ "$LAST_STATE" != "pc_turn" ]; then
    launch_runner="$RUNNER_PREFERRED"

    # Guard: skip launch if any Builder session is already running (crash-restart safety).
    if any_builder_session_running; then
      log "SKIP: pc_turn transition detected but Builder session already running — skipping launch"
      LAST_STATE="$status"
      sleep "$POLL_INTERVAL"
      continue
    fi

    # Runner-specific guard remains as a fallback check.
    runner_guard_pattern="$(guard_pattern_for_runner "$launch_runner")"
    if pgrep -f "$runner_guard_pattern" >/dev/null 2>&1; then
      log "SKIP: pc_turn transition detected but $launch_runner session already running — skipping launch"
      LAST_STATE="$status"
      sleep "$POLL_INTERVAL"
      continue
    fi
    log "LAUNCH: Starting Builder (transition from '$LAST_STATE' to 'pc_turn')"
    launch_start_ts=$(date +%s)
    launch_runner_once "$launch_runner"
    exit_code=$?
    launch_elapsed=$(( $(date +%s) - launch_start_ts ))
    effective_runner="${LAST_EFFECTIVE_RUNNER:-$launch_runner}"

    # Fast-failure fallback: only when runner is implicit, non-timeout failure, and <=20s runtime.
    if [ "$RUNNER_EXPLICIT" -eq 0 ] && [ "$exit_code" -ne 0 ] && [ "$exit_code" -ne 124 ] && [ "$launch_elapsed" -le 20 ]; then
      FALLBACK_ATTEMPTED=1
      fallback_runner="$(fallback_runner_for "$effective_runner")"
      fallback_guard_pattern="$(guard_pattern_for_runner "$fallback_runner")"
      if pgrep -f "$fallback_guard_pattern" >/dev/null 2>&1; then
        log "FALLBACK-SKIP: runner=$fallback_runner already running; keeping primary exit=$exit_code"
      else
        log "FALLBACK: runner=$effective_runner failed fast (exit=$exit_code, elapsed=${launch_elapsed}s); trying runner=$fallback_runner once"
        launch_runner="$fallback_runner"
        launch_start_ts=$(date +%s)
        launch_runner_once "$launch_runner"
        exit_code=$?
        launch_elapsed=$(( $(date +%s) - launch_start_ts ))
        effective_runner="${LAST_EFFECTIVE_RUNNER:-$launch_runner}"
        log "FALLBACK: runner=$effective_runner completed (exit=$exit_code, elapsed=${launch_elapsed}s)"
      fi
    else
      log "LAUNCH: runner=$effective_runner completed (exit=$exit_code, elapsed=${launch_elapsed}s)"
    fi

    # Post-run output validation fallback.
    # Fires when pc_output.md is missing, empty, or contains a quota/error message
    # instead of valid builder output — even when exit_code=0.
    # Skipped if: fast-fail already attempted a fallback this cycle, runner was
    # forced via CODING_RUNNER, or the runner timed out (exit=124).
    if [ "$RUNNER_EXPLICIT" -eq 0 ] && [ "$FALLBACK_ATTEMPTED" -eq 0 ] && [ "$exit_code" -ne 124 ]; then
      out_reason="$(validate_pc_output_result)"
      if [ "$out_reason" != "ok" ]; then
        FALLBACK_ATTEMPTED=1
        next_runner="$(fallback_runner_for "$effective_runner")"
        fbguard="$(guard_pattern_for_runner "$next_runner")"
        if pgrep -f "$fbguard" >/dev/null 2>&1; then
          log "OUTPUT-FALLBACK-SKIP: $next_runner already running (output was: $out_reason)"
        else
          log "OUTPUT-FALLBACK: runner=$effective_runner output invalid ($out_reason) — trying runner=$next_runner"
          rm -f "$PC_OUTPUT_FILE" 2>/dev/null || true
          launch_runner="$next_runner"
          launch_runner_once "$launch_runner"
          exit_code=$?
          effective_runner="${LAST_EFFECTIVE_RUNNER:-$launch_runner}"
          log "OUTPUT-FALLBACK: runner=$effective_runner completed (exit=$exit_code)"
        fi
      fi
    fi

    if [ "$exit_code" -eq 124 ]; then
      log "BUILDER: Session TIMED OUT after 900s (exit=124)"
    else
      log "BUILDER: Session ended (exit=$exit_code)"
    fi
    LAUNCH_COUNT=$(( LAUNCH_COUNT + 1 ))
    if [ "$LAUNCH_COUNT" -ge "$MAX_LAUNCHES" ]; then
      log "ERROR: Max launches ($MAX_LAUNCHES) reached for this pc_turn cycle. Parking. Manual intervention required."
      PARKED=1
    fi
  elif [ "$status" = "pc_turn" ] && [ "$LAST_STATE" = "pc_turn" ]; then
    if [ "$PARKED" -eq 0 ]; then
      log "HOLD: Status still pc_turn after Builder exit. Waiting for state change before re-launch."
    fi
  fi

  LAST_STATE="$status"
  sleep "$POLL_INTERVAL"
done
