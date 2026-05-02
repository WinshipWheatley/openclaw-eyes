#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: scripts/install_hermes_gateway_service.sh [--dry-run] [--apply] [--restart]

Render only systemd/user/hermes-gateway.service.in to:
  $HOME/.config/systemd/user/hermes-gateway.service

Modes:
  no args     Report what would happen. No files are written and no services are changed.
  --dry-run   Report what would happen. Cannot be combined with mutation flags.
  --apply     Render/install only hermes-gateway.service, daemon-reload, and verify flags.
  --restart   Restart only hermes-gateway.service after verification. Requires --apply.

No enable/start behavior is available from this Hermes-only installer. Unknown
or ambiguous flag combinations fail closed.
USAGE
}

apply_changes=0
restart_service=0
dry_run=0

if (($# == 0)); then
    dry_run=1
fi

while (($#)); do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        --apply)
            apply_changes=1
            ;;
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

if (( dry_run && (apply_changes || restart_service) )); then
    printf 'ERROR: --dry-run cannot be combined with --apply or --restart.\n' >&2
    usage >&2
    exit 2
fi

if (( restart_service && ! apply_changes )); then
    printf 'ERROR: --restart requires --apply.\n' >&2
    usage >&2
    exit 2
fi

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

report_plan() {
    printf 'Hermes gateway installer dry run from %s\n' "${REPO_ROOT}"
    printf 'No files will be written and no service commands will be run.\n'
    printf 'With --apply: would render only %s to %s, run systemctl --user daemon-reload, and verify required gateway flags.\n' "${TEMPLATE_PATH}" "${INSTALLED_UNIT}"
    printf 'With --apply --restart: would restart only %s after successful verification.\n' "${UNIT_NAME}"
    printf 'This installer does not enable services, start services, or broaden Hermes beyond gateway sidecar mode.\n'
}

if (( dry_run )); then
    report_plan
    exit 0
fi

if (( ! apply_changes )); then
    printf 'ERROR: --apply is required for Hermes gateway installer mutation.\n' >&2
    usage >&2
    exit 2
fi

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
printf 'Ran systemctl --user daemon-reload after rendering only %s.\n' "${UNIT_NAME}"

if (( restart_service )); then
    printf 'Restarting only %s...\n' "${UNIT_NAME}"
    systemctl --user restart "${UNIT_NAME}"
    printf 'Restarted %s.\n' "${UNIT_NAME}"
else
    printf 'Did not restart %s; pass --restart with --apply to restart only this unit after verification.\n' "${UNIT_NAME}"
fi

printf 'Hermes gateway installer finished with explicit apply=%s restart=%s.\n' "${apply_changes}" "${restart_service}"