#!/usr/bin/env bash
# Shared task-150 boot contract. Keep the ten long-running operator-facing
# services separate from the three autonomy timers because their health checks
# differ: services must be active; timers must be both enabled and active.

# shellcheck disable=SC2034  # This file is sourced by both assertion scripts.
OPENCLAW_BOOT_SERVICES=(
  openclaw-request-response.service
  maestro-listener.service
  cassandra-listener.service
  chief-listener.service
  chief-guardian-listener.service
  niles-listener.service
  hermes-gateway.service
  kokoro-voice.service
  openclaw-gateway.service
  niles-memory-worker.service
)

# Enabled long-running workers/watchers observed on the verified clean boot.
# They do not change the operator-facing "10/10" denominator, but any one of
# them being down blocks a green whole-system assertion.
# shellcheck disable=SC2034
OPENCLAW_BOOT_AUX_SERVICES=(
  cassandra-briefing-scheduler.service
  cassandra-watcher.service
  chief-memory-worker.service
  chief-state-worker.service
  chief-watcher-brain.service
  chief-worker.service
)

# shellcheck disable=SC2034
OPENCLAW_BOOT_TIMERS=(
  openclaw-morning-brief.timer
  openclaw-autonomous-invoice-prep.timer
  openclaw-autonomous-followup-watch.timer
)

# Additional enabled operational timers observed on the verified clean boot.
# shellcheck disable=SC2034
OPENCLAW_BOOT_AUX_TIMERS=(
  guardian-approval-notifier.timer
  openclaw-change-sentinel.timer
  openclaw-drift-control-scan.timer
  openclaw-read-model-auto-refresh.timer
  openclaw-service-keeper.timer
  self-knowledge-crawl.timer
)

# shellcheck disable=SC2034
OPENCLAW_BOOT_REQUIRED_SERVICES=(
  "${OPENCLAW_BOOT_SERVICES[@]}"
  "${OPENCLAW_BOOT_AUX_SERVICES[@]}"
)

# shellcheck disable=SC2034
OPENCLAW_BOOT_REQUIRED_TIMERS=(
  "${OPENCLAW_BOOT_TIMERS[@]}"
  "${OPENCLAW_BOOT_AUX_TIMERS[@]}"
)

# shellcheck disable=SC2034
OPENCLAW_BOOT_ASSERT_UNIT=openclaw-boot-assert.service

# shellcheck disable=SC2034
OPENCLAW_ENABLEMENT_USER_UNITS=(
  "${OPENCLAW_BOOT_REQUIRED_SERVICES[@]}"
  "${OPENCLAW_BOOT_REQUIRED_TIMERS[@]}"
  openclaw-stack.target
  "$OPENCLAW_BOOT_ASSERT_UNIT"
)
