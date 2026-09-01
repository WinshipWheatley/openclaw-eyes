#!/usr/bin/env bash
# home_fabric_check.sh - read-only health check for the OpenClaw home fabric (PC/WSL <-> Mac).
#
# Usage:
#   bash scripts/home_fabric_check.sh            # one line per check, exit 0
#   bash scripts/home_fabric_check.sh --strict   # exit 1 when any check FAILs
#   bash scripts/home_fabric_check.sh --help
#
# Checks: WSL address, Windows portproxy for the Mac -> PC:2222 -> WSL:22 route, WSL sshd,
# Tailscale (WSL and Windows), Mac reachability (mDNS + ssh alias), E-drive shuttle markers,
# Ollama, core systemd user units, and services bound to all interfaces.
# Never mutates state: no portproxy edits, no service restarts, no Tailscale changes, no writes.
set -uo pipefail

STRICT=0
case "${1:-}" in
  --strict) STRICT=1 ;;
  -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  "") ;;
  *) echo "unknown option: $1" >&2; exit 2 ;;
esac

MAC_SSH_HOST="${OPENCLAW_MAC_SSH_HOST:-mac}"
MAC_MDNS_HOST="${OPENCLAW_MAC_MDNS_HOST:-Hs-MBP-2.local}"
SSH_LISTEN_PORT="${OPENCLAW_WSL_SSH_LISTEN_PORT:-2222}"
SHUTTLE_ROOT="${OPENCLAW_SHUTTLE_ROOT:-/mnt/e/openclaw}"
OLLAMA_URL="${OPENCLAW_OLLAMA_URL:-http://127.0.0.1:11434}"
CORE_UNITS="${OPENCLAW_CORE_UNITS:-chief-listener.service cassandra-listener.service chief-guardian-listener.service openclaw-sleep-resilience.service}"
STALE_AFTER_SECONDS="${OPENCLAW_FABRIC_STALE_SECONDS:-900}"

FAILS=0
WARNS=0
ok()   { printf '[OK]   %-28s %s\n' "$1" "$2"; }
warn() { printf '[WARN] %-28s %s\n' "$1" "$2"; WARNS=$((WARNS + 1)); }
fail() { printf '[FAIL] %-28s %s\n' "$1" "$2"; FAILS=$((FAILS + 1)); }
skip() { printf '[SKIP] %-28s %s\n' "$1" "$2"; }
have() { command -v "$1" >/dev/null 2>&1; }

# --- node identity -------------------------------------------------------------
IS_WSL=0
grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=1
ok "node" "$(hostname) user=$(id -un) wsl=$IS_WSL"

# --- WSL address + Windows host --------------------------------------------------
WSL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -n "$WSL_IP" ]; then ok "wsl_ipv4" "$WSL_IP"; else warn "wsl_ipv4" "no IPv4 address found"; fi
WIN_GW="$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')"
if [ -n "$WIN_GW" ]; then ok "windows_host_via_wsl" "$WIN_GW (default gateway)"; else skip "windows_host_via_wsl" "no default route"; fi

# --- Windows portproxy: Mac -> PC:2222 -> WSL:22 ---------------------------------
if [ "$IS_WSL" = 1 ] && have netsh.exe; then
  PROXY_LINE="$(netsh.exe interface portproxy show v4tov4 2>/dev/null | tr -d '\r' | awk -v p="$SSH_LISTEN_PORT" '$2 == p {print; exit}')"
  if [ -z "$PROXY_LINE" ]; then
    fail "portproxy_$SSH_LISTEN_PORT" "no v4tov4 mapping for listen port $SSH_LISTEN_PORT (Mac 'ssh openclaw' route is down)"
  else
    TARGET_IP="$(printf '%s' "$PROXY_LINE" | awk '{print $3}')"
    if [ "$TARGET_IP" = "$WSL_IP" ]; then
      ok "portproxy_$SSH_LISTEN_PORT" "0.0.0.0:$SSH_LISTEN_PORT -> $TARGET_IP:22 (matches WSL IP)"
    else
      fail "portproxy_$SSH_LISTEN_PORT" "targets $TARGET_IP but WSL IP is $WSL_IP (stale after reboot; run scripts/windows_wsl_portproxy_resync.ps1 on Windows)"
    fi
  fi
else
  skip "portproxy_$SSH_LISTEN_PORT" "not WSL or netsh.exe not on PATH"
fi

# --- sshd inside WSL ----------------------------------------------------------------
if have ss; then
  if ss -ltn 2>/dev/null | awk 'NR > 1 {print $4}' | grep -qE '(^|:)22$'; then
    ok "wsl_sshd" "listening on :22"
  else
    fail "wsl_sshd" "nothing listening on :22 (check: systemctl status ssh)"
  fi
else
  skip "wsl_sshd" "ss not available"
fi

# --- Tailscale -----------------------------------------------------------------------
if have tailscale; then
  TS_IP="$(tailscale ip -4 2>/dev/null | head -1)"
  if [ -n "$TS_IP" ]; then ok "tailscale_wsl" "$TS_IP"; else warn "tailscale_wsl" "installed but no IPv4 (not up / not logged in)"; fi
else
  skip "tailscale_wsl" "tailscale not installed in WSL"
fi
if have tailscale.exe; then
  TSW_IP="$(tailscale.exe ip -4 2>/dev/null | tr -d '\r' | head -1)"
  if [ -n "$TSW_IP" ]; then ok "tailscale_windows" "$TSW_IP"; else warn "tailscale_windows" "installed but no IPv4"; fi
else
  skip "tailscale_windows" "tailscale.exe not on PATH"
fi

# --- Mac reachability ------------------------------------------------------------------
if have getent; then
  if getent hosts "$MAC_MDNS_HOST" >/dev/null 2>&1; then
    ok "mac_mdns" "$MAC_MDNS_HOST resolves"
  else
    warn "mac_mdns" "$MAC_MDNS_HOST does not resolve from WSL (mDNS is unreliable here; prefer Tailscale MagicDNS)"
  fi
fi
if have ssh; then
  if MAC_HOST="$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$MAC_SSH_HOST" hostname 2>/dev/null)"; then
    ok "mac_ssh" "ssh $MAC_SSH_HOST -> $MAC_HOST"
  else
    fail "mac_ssh" "ssh $MAC_SSH_HOST failed (alias, key, or Mac asleep); PC -> Mac mirrors are down"
  fi
fi

# --- E-drive shuttle --------------------------------------------------------------------
if [ -d "$SHUTTLE_ROOT" ]; then
  ok "shuttle_mount" "$SHUTTLE_ROOT present"
  NOW="$(date +%s)"
  for marker in shuttle/from_mac/read_model_sync_agent_status.json shuttle/from_mac/read_model_sync_completed.json; do
    label="shuttle_$(basename "$marker" .json)"
    file="$SHUTTLE_ROOT/$marker"
    if [ -f "$file" ]; then
      age=$(( NOW - $(stat -c %Y "$file") ))
      if [ "$age" -le "$STALE_AFTER_SECONDS" ]; then
        ok "$label" "${age}s old"
      else
        warn "$label" "${age}s old (> ${STALE_AFTER_SECONDS}s: Mac agent idle or /Volumes/openclaw_e unmounted)"
      fi
    else
      warn "$label" "missing"
    fi
  done
else
  fail "shuttle_mount" "$SHUTTLE_ROOT missing (E: drive not mounted in WSL)"
fi

# --- Ollama ----------------------------------------------------------------------------------
if have curl; then
  if MODELS="$(curl -s -m 3 "$OLLAMA_URL/api/tags" 2>/dev/null)"; then
    COUNT="$(printf '%s' "$MODELS" | grep -o '"name"' | wc -l | tr -d ' ')"
    ok "ollama" "$OLLAMA_URL up, $COUNT models"
  else
    warn "ollama" "$OLLAMA_URL not responding"
  fi
fi

# --- core systemd user units -----------------------------------------------------------------
if have systemctl; then
  for unit in $CORE_UNITS; do
    state="$(systemctl --user is-active "$unit" 2>/dev/null || true)"
    case "$state" in
      active) ok "unit:$unit" "active" ;;
      "") skip "unit:$unit" "systemd --user unavailable" ;;
      *) fail "unit:$unit" "$state" ;;
    esac
  done
fi

# --- exposure: what is bound to all interfaces besides sshd? -----------------------------------
if have ss; then
  WIDE="$(ss -ltnu 2>/dev/null | awk 'NR > 1 && ($5 ~ /^(0\.0\.0\.0|\*|\[::\]):/) {n = split($5, a, ":"); if (a[n] != "22") print a[n]}' | sort -un | tr '\n' ' ')"
  if [ -z "$WIDE" ]; then
    ok "wide_open_ports" "nothing besides sshd is bound to all interfaces"
  else
    warn "wide_open_ports" "ports bound to all interfaces: $WIDE (bind gateways to 127.0.0.1 or the Tailscale IP)"
  fi
fi

echo
echo "summary: fails=$FAILS warns=$WARNS"
if [ "$STRICT" = 1 ] && [ "$FAILS" -gt 0 ]; then
  exit 1
fi
exit 0
