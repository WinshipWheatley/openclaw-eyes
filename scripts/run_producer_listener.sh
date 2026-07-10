#!/bin/bash
# Launcher for Producer listener agent
# Canonical bot identity lives in .chief.env; legacy producer.env remains optional.
# Usage: ./scripts/run_producer_listener.sh

set -e

REPO_ROOT="${OPENCLAW_NILES_REPO_ROOT:-/home/openclaw}"
cd "${REPO_ROOT}"

# Load canonical shared configuration without printing values.
set -a
if [ -f ".chief.env" ]; then
    source .chief.env
fi

# Preserve old installations explicitly and loudly while they migrate.
if [ -f "secrets/producer.env" ]; then
    source secrets/producer.env
fi
set +a
if [ -z "${NILES_BOT_TOKEN:-}" ] && [ -n "${PRODUCER_BOT_TOKEN:-}" ]; then
    echo "[niles_listener] LOUD WARNING: PRODUCER_BOT_TOKEN is legacy; configure NILES_BOT_TOKEN." >&2
    export NILES_BOT_TOKEN="${PRODUCER_BOT_TOKEN}"
fi
if [ -z "${TELEGRAM_AUTHORIZED_USER_ID:-}" ] && [ -n "${PRODUCER_AUTHORIZED_USER_ID:-}" ]; then
    echo "[niles_listener] LOUD WARNING: PRODUCER_AUTHORIZED_USER_ID is legacy; configure TELEGRAM_AUTHORIZED_USER_ID." >&2
    export TELEGRAM_AUTHORIZED_USER_ID="${PRODUCER_AUTHORIZED_USER_ID}"
fi

export PRODUCER_VOICE_ENABLED="${PRODUCER_VOICE_ENABLED:-0}"
export PRODUCER_PERSONA="${PRODUCER_PERSONA:-niles}"

# Verify role identity + shared operator identity without printing values.
REQUIRED_VARS=("NILES_BOT_TOKEN" "NILES_EXPECTED_BOT_USERNAME" "TELEGRAM_AUTHORIZED_USER_ID")

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Required environment variable $var is not set in canonical or legacy Niles configuration"
        exit 1
    fi
done

# Run the producer listener
# Use the chief_env venv (has python-telegram-bot); system python3 lacks it.
NILES_LISTENER_PYTHON="${OPENCLAW_NILES_LISTENER_PYTHON:-/home/openclaw/chief_env/bin/python}"
exec "${NILES_LISTENER_PYTHON}" -u producer_listener.py
