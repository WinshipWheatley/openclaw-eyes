#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: scripts/install_hermes_gateway_service.sh [--restart]

Render only systemd/user/hermes-gateway.service.in to:
  $HOME/.config/systemd/user/hermes-gateway.service

Default: install and daemon-reload only. This does not enable, start, or restart
services. Pass --restart to restart only hermes-gateway.service after the
installed unit verifies.
USAGE
}

restart_service=0
while (($#)); do
    case "$1" in
        --restart)
            restart_service=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'ERROR: unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_PATH="${REPO_ROOT}/systemd/user/hermes-gateway.service.in"
UNIT_NAME="hermes-gateway.service"
USER_UNIT_DIR="${HOME}/.config/systemd/user"
INSTALLED_UNIT="${USER_UNIT_DIR}/${UNIT_NAME}"

REQUIRED_FLAGS=(
    "Environment=HERMES_OPENCLAW_MODE=gateway"
    "Environment=HERMES_OPENCLAW_GATEWAY=1"
    "Environment=HERMES_OPENCLAW_DISABLE_EXTERNAL_FALLBACK=1"
)

render_template() {
    local replacement="${REPO_ROOT}"
    replacement="${replacement//\\/\\\\}"
    replacement="${replacement//&/\\&}"
    sed "s|@REPO_ROOT@|${replacement}|g" "${TEMPLATE_PATH}"
}

verify_required_flags() {
    local unit_path="$1"
    local flag

    for flag in "${REQUIRED_FLAGS[@]}"; do
        if ! grep -Fq "${flag}" "${unit_path}"; then
            printf 'ERROR: installed %s is missing required flag: %s\n' "${UNIT_NAME}" "${flag}" >&2
            return 1
        fi
    done
}

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
    printf 'ERROR: missing template: %s\n' "${TEMPLATE_PATH}" >&2
    exit 1
fi

mkdir -p "${USER_UNIT_DIR}"

tmp_unit="$(mktemp "${USER_UNIT_DIR}/${UNIT_NAME}.tmp.XXXXXX")"
cleanup() {
    rm -f "${tmp_unit}"
}
trap cleanup EXIT

render_template > "${tmp_unit}"
mv "${tmp_unit}" "${INSTALLED_UNIT}"
trap - EXIT

systemctl --user daemon-reload
verify_required_flags "${INSTALLED_UNIT}"

printf 'Installed %s from %s\n' "${INSTALLED_UNIT}" "${TEMPLATE_PATH}"
printf 'Verified OpenClaw Hermes gateway env flags.\n'

if (( restart_service )); then
    printf 'Restarting only %s...\n' "${UNIT_NAME}"
    systemctl --user restart "${UNIT_NAME}"
    printf 'Restarted %s.\n' "${UNIT_NAME}"
else
    printf 'Next step after review:\n'
    printf '  systemctl --user restart %s\n' "${UNIT_NAME}"
fi