#!/usr/bin/env bash
# with_prod_env.sh — ANTI-BRITTLE #5
# Run any command with the REAL production service environment, so probes/tests reflect the
# LIVE config (not a stripped default that gives false alarms — e.g. the "6s timeout / all-agents-
# are-Maestro" phantom that nearly caused a config change to a working system).
#
# It reads Environment= directives straight from the deployed systemd unit (single source of truth,
# stays in sync automatically), then execs the command.
#
# Usage:
#   scripts/with_prod_env.sh <command...>
#   scripts/with_prod_env.sh /home/openclaw/chief_env/bin/python -c "import ...; probe()"
#
# Env override: OPENCLAW_PROD_ENV_UNIT (default: openclaw-request-response.service — the PROCESSOR
# that runs the brain; per the maestro service split, processing flags live there).
set -euo pipefail
UNIT="${OPENCLAW_PROD_ENV_UNIT:-openclaw-request-response.service}"

# pull Environment="K=V" directives from the live unit (both [Service] Environment and drop-ins)
while IFS= read -r line; do
  # systemctl cat emits: Environment="K=V"  (possibly multiple K=V per line)
  kv="${line#*Environment=}"; kv="${kv%\"}"; kv="${kv#\"}"
  # split on spaces only outside quotes is overkill here — our units use one K=V per Environment=
  export "${kv?}" 2>/dev/null || true
done < <(systemctl --user cat "$UNIT" 2>/dev/null | grep -E '^\s*Environment=' || true)

# sensible fallbacks matching the live processor if the unit didn't declare them
export OPENCLAW_FRONTDOOR_MODEL_PROFILE="${OPENCLAW_FRONTDOOR_MODEL_PROFILE:-1}"
export OPENCLAW_PACKET_SOURCE="${OPENCLAW_PACKET_SOURCE:-sqlite}"

if [ "$#" -eq 0 ]; then
  echo "[with-prod-env] loaded from ${UNIT}:"
  echo "  OPENCLAW_FRONTDOOR_MODEL_PROFILE=${OPENCLAW_FRONTDOOR_MODEL_PROFILE:-}"
  echo "  OPENCLAW_PACKET_SOURCE=${OPENCLAW_PACKET_SOURCE:-}"
  echo "  OPENCLAW_FRONTDOOR_REPLY_TIMEOUT=${OPENCLAW_FRONTDOOR_REPLY_TIMEOUT:-}"
  echo "  OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT=${OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT:-}"
  echo "  (pass a command to run under this env)"
  exit 0
fi
exec "$@"
