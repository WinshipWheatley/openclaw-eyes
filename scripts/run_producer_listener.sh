#!/bin/bash
# Launcher for Producer listener agent
# Humans must manually create secrets/producer.env
# Usage: ./scripts/run_producer_listener.sh

set -e

cd /home/openclaw

# Load environment if secret file exists
if [ -f "secrets/producer.env" ]; then
    source secrets/producer.env
else
    echo "Error: secrets/producer.env not found. Please create it first."
    exit 1
fi

# Verify required vars are set (without printing values)
REQUIRED_VARS=("PRODUCER_BOT_TOKEN" "PRODUCER_AUTHORIZED_USER_ID" "PRODUCER_VOICE_ENABLED" "PRODUCER_PERSONA")

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Required environment variable $var is not set in secrets/producer.env"
        exit 1
    fi
done

# Run the producer listener
# Ensure chief_env is active via existing env setup if required
python3 producer_listener.py
