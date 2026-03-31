#!/usr/bin/env bash
# vscode_cleanup.sh — Kill stale VS Code server processes and clear lock files.
# Run on the PC (openclaw@DESKTOP-HP) before a recovery VS Code launch.
# Safe to run while no VS Code session is active. Will disrupt an active session.

set -euo pipefail

echo "[vscode_cleanup] Stopping stale VS Code server processes..."

# Kill vscode-server processes (the remote server components)
if pgrep -f "vscode-server" > /dev/null 2>&1; then
    pkill -f "vscode-server" || true
    sleep 1
    # Force-kill anything that survived
    pkill -9 -f "vscode-server" 2>/dev/null || true
    echo "[vscode_cleanup] VS Code server processes killed."
else
    echo "[vscode_cleanup] No VS Code server processes found."
fi

# Kill any orphaned node processes from VS Code extensions
if pgrep -f "\.vscode-server.*node" > /dev/null 2>&1; then
    pkill -f "\.vscode-server.*node" || true
    echo "[vscode_cleanup] Orphaned VS Code node processes killed."
fi

# Clear IPC socket files (stale sockets prevent reconnection)
SOCK_DIR="$HOME/.vscode-server/data/User/workspaceStorage"
if [ -d "$SOCK_DIR" ]; then
    find "$SOCK_DIR" -name "*.sock" -delete 2>/dev/null || true
    echo "[vscode_cleanup] Cleared stale socket files."
fi

# Clear lock files from workspace storage
find "$HOME/.vscode-server/data/" -name "*.lock" -delete 2>/dev/null || true
echo "[vscode_cleanup] Cleared lock files."

echo "[vscode_cleanup] Done. PC is ready for a fresh VS Code connection."
