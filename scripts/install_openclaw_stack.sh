#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: scripts/install_openclaw_stack.sh [--dry-run] [--apply] [--enable] [--start] [--request-response-only] [--ancillary-repair-only]

Modes:
  no args     Report what would happen. No files are written and no services are changed.
  --dry-run   Report what would happen. Cannot be combined with mutation flags.
  --apply     Render/install repo-owned units and run systemctl --user daemon-reload only.
  --enable    Enable only repo-owned OpenClaw units rendered by this script. Requires --apply.
  --start     Enable/start openclaw-stack.target, or only openclaw-request-response.service with --request-response-only. Requires --apply and --enable.
  --request-response-only
              Limit render/enable/start to the Mission Control request-response bridge.
  --ancillary-repair-only
              Render only the three known ancillary units with Python placeholders.
              This repair slice refuses --enable and --start.

Unknown or ambiguous flag combinations fail closed.
USAGE
}

apply_changes=0
enable_units=0
start_target=0
dry_run=0
request_response_only=0
ancillary_repair_only=0

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
        --enable)
            enable_units=1
            ;;
        --start)
            start_target=1
            ;;
        --request-response-only)
            request_response_only=1
            ;;
        --ancillary-repair-only)
            ancillary_repair_only=1
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

if (( dry_run && (apply_changes || enable_units || start_target) )); then
    printf 'ERROR: --dry-run cannot be combined with --apply, --enable, or --start.\n' >&2
    usage >&2
    exit 2
fi

if (( ancillary_repair_only && request_response_only )); then
    printf 'ERROR: --ancillary-repair-only cannot be combined with --request-response-only.\n' >&2
    usage >&2
    exit 2
fi

if (( ancillary_repair_only && (enable_units || start_target) )); then
    printf 'ERROR: --ancillary-repair-only cannot be combined with --enable or --start.\n' >&2
    usage >&2
    exit 2
fi

if (( enable_units && ! apply_changes )); then
    printf 'ERROR: --enable requires --apply.\n' >&2
    usage >&2
    exit 2
fi

if (( start_target && (! apply_changes || ! enable_units) )); then
    printf 'ERROR: --start requires --apply and --enable.\n' >&2
    usage >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_DIR="${REPO_ROOT}/systemd/user"
USER_UNIT_DIR="${HOME}/.config/systemd/user"
TARGET_NAME="openclaw-stack.target"
REQUEST_RESPONSE_SERVICE_NAME="openclaw-request-response.service"
PYTHON_BIN="${REPO_ROOT}/chief_env/bin/python"
ANCILLARY_REPAIR_UNIT_NAMES=(
    "guardian-approval-notifier.service"
    "self-knowledge-crawl.service"
    "openclaw-read-model-auto-refresh.service"
)

repo_owned_unit_names=()
repo_owned_service_names=()

collect_template() {
    local template="$1"
    local unit_name
    if [[ ! -e "${template}" ]]; then
        return
    fi
    unit_name="$(basename "${template}" .in)"
    repo_owned_unit_names+=("${unit_name}")
    if [[ "${unit_name}" == *.service && "${unit_name}" != "hermes-gateway.service" ]]; then
        repo_owned_service_names+=("${unit_name}")
    fi
}

if (( request_response_only )); then
    collect_template "${TEMPLATE_DIR}/${REQUEST_RESPONSE_SERVICE_NAME}.in"
elif (( ancillary_repair_only )); then
    for unit_name in "${ANCILLARY_REPAIR_UNIT_NAMES[@]}"; do
        collect_template "${TEMPLATE_DIR}/${unit_name}.in"
    done
else
    for template in "${TEMPLATE_DIR}"/*.in; do
        collect_template "${template}"
    done
fi

print_units() {
    local heading="$1"
    shift
    local unit

    printf '%s\n' "${heading}"
    if (($# == 0)); then
        printf '  none\n'
        return
    fi
    for unit in "$@"; do
        printf '  %s\n' "${unit}"
    done
}

report_plan() {
    printf 'OpenClaw stack installer dry run from %s\n' "${REPO_ROOT}"
    printf 'No files will be written and no service commands will be run.\n'
    print_units 'Repo-owned units that --apply would render/install:' "${repo_owned_unit_names[@]}"
    printf 'With --apply: would render/install those units into %s and run systemctl --user daemon-reload.\n' "${USER_UNIT_DIR}"
    if (( ancillary_repair_only )); then
        printf 'With --apply --ancillary-repair-only: would render only the named ancillary units; enable/start are refused.\n'
    else
        print_units 'Repo-owned non-Hermes services that --apply --enable would enable:' "${repo_owned_service_names[@]}"
        if (( request_response_only )); then
            printf 'With --apply --enable --start --request-response-only: would enable/start only %s.\n' "${REQUEST_RESPONSE_SERVICE_NAME}"
        else
            printf 'With --apply --enable --start: would enable/start only %s.\n' "${TARGET_NAME}"
        fi
    fi
    printf 'Hermes gateway remains managed by scripts/install_hermes_gateway_service.sh and is not enabled here.\n'
}

if (( dry_run )); then
    report_plan
    exit 0
fi

if ((${#repo_owned_unit_names[@]} == 0)); then
    printf 'ERROR: no repo-owned unit templates found in %s\n' "${TEMPLATE_DIR}" >&2
    exit 1
fi

render_unit() {
    local template_path="$1"
    local unit_name
    local rendered_path
    unit_name="$(basename "${template_path}" .in)"
    rendered_path="$(mktemp "${USER_UNIT_DIR}/.${unit_name}.XXXXXX")"
    sed \
        -e "s|@REPO_ROOT@|${REPO_ROOT}|g" \
        -e "s|@PYTHON@|${PYTHON_BIN}|g" \
        "${template_path}" > "${rendered_path}"
    if grep -Eq '@[A-Z][A-Z0-9_]*@' "${rendered_path}"; then
        printf 'ERROR: unresolved template placeholder in %s\n' "${template_path}" >&2
        rm -f "${rendered_path}"
        return 1
    fi
    chmod 0644 "${rendered_path}"
    mv -f "${rendered_path}" "${USER_UNIT_DIR}/${unit_name}"
    printf 'Installed repo-owned unit: %s\n' "${unit_name}"
}

printf 'Applying OpenClaw stack installer from %s\n' "${REPO_ROOT}"
mkdir -p "${USER_UNIT_DIR}"

if (( request_response_only )); then
    render_unit "${TEMPLATE_DIR}/${REQUEST_RESPONSE_SERVICE_NAME}.in"
elif (( ancillary_repair_only )); then
    for unit_name in "${ANCILLARY_REPAIR_UNIT_NAMES[@]}"; do
        render_unit "${TEMPLATE_DIR}/${unit_name}.in"
    done
else
    for template in "${TEMPLATE_DIR}"/*.in; do
        if [[ ! -e "${template}" ]]; then
            continue
        fi
        render_unit "${template}"
    done
fi

systemctl --user daemon-reload
printf 'Ran systemctl --user daemon-reload after rendering repo-owned units.\n'

if (( enable_units )); then
    print_units 'Enabling repo-owned non-Hermes OpenClaw services:' "${repo_owned_service_names[@]}"
    for service_name in "${repo_owned_service_names[@]}"; do
        systemctl --user enable "${service_name}"
        printf 'Enabled repo-owned service: %s\n' "${service_name}"
    done
else
    printf 'Did not enable services; pass --enable with --apply to enable repo-owned non-Hermes OpenClaw services.\n'
fi

if (( start_target )); then
    if (( request_response_only )); then
        systemctl --user enable --now "${REQUEST_RESPONSE_SERVICE_NAME}"
        printf 'Enabled and started only %s.\n' "${REQUEST_RESPONSE_SERVICE_NAME}"
    else
        systemctl --user enable --now "${TARGET_NAME}"
        printf 'Enabled and started only %s.\n' "${TARGET_NAME}"
    fi
else
    if (( request_response_only )); then
        printf 'Did not start %s; pass --start with --apply --enable --request-response-only to start the bridge.\n' "${REQUEST_RESPONSE_SERVICE_NAME}"
    else
        printf 'Did not start %s; pass --start with --apply --enable to start the target.\n' "${TARGET_NAME}"
    fi
fi

printf 'OpenClaw stack installer finished with explicit apply=%s enable=%s start=%s request_response_only=%s ancillary_repair_only=%s.\n' "${apply_changes}" "${enable_units}" "${start_target}" "${request_response_only}" "${ancillary_repair_only}"
