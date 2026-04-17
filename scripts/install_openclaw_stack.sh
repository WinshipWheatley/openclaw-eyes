#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_DIR="${REPO_ROOT}/systemd/user"
USER_UNIT_DIR="${HOME}/.config/systemd/user"
TARGET_NAME="openclaw-stack.target"

render_unit() {
    local template_path="$1"
    local unit_name
    unit_name="$(basename "${template_path}" .in)"
    sed "s|@REPO_ROOT@|${REPO_ROOT}|g" "${template_path}" > "${USER_UNIT_DIR}/${unit_name}"
    echo "installed ${unit_name}"
}

echo "Installing OpenClaw user units from ${REPO_ROOT}"
mkdir -p "${USER_UNIT_DIR}"

for template in "${TEMPLATE_DIR}"/*.in; do
    render_unit "${template}"
done

systemctl --user daemon-reload
systemctl --user enable --now "${TARGET_NAME}"

if command -v loginctl >/dev/null 2>&1; then
    linger_state="$(loginctl show-user "$(id -un)" -p Linger 2>/dev/null | cut -d= -f2 || true)"
    if [[ "${linger_state}" != "yes" && "${linger_state}" != "Yes" ]]; then
        echo "NOTE: linger is not enabled for $(id -un)."
        echo "Run as root once: loginctl enable-linger $(id -un)"
    fi
fi

echo "OpenClaw stack installed and enabled."
