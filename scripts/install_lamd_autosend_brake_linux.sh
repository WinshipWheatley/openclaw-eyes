#!/usr/bin/env bash
set -euo pipefail

apply=0
if [[ "${1:-}" == "--apply" ]]; then
  apply=1
elif [[ $# -ne 0 ]]; then
  echo "usage: $0 [--apply]" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install_root=/usr/local/libexec/openclaw-authority
state_root=/var/lib/openclaw-authority
run_root=/run/openclaw-authority
unit_path=/etc/systemd/system/openclaw-lamd-autosend-brake.service
openclaw_uid="$(id -u openclaw)"
openclaw_gid="$(id -g openclaw)"

if [[ $apply -ne 1 ]]; then
  echo "PLAN ONLY: install the root brake broker, initialize clear state, and enable its system service."
  echo "No files, state, services, sends, money, or ledgers were changed."
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "--apply requires an operator-authenticated root shell." >&2
  exit 3
fi

install -d -o root -g root -m 0755 "$install_root"
install -d -o root -g root -m 0700 "$state_root"
install -d -o root -g root -m 0755 "$run_root"
install -o root -g root -m 0755 "$repo_root/lamd_autosend_brake.py" "$install_root/lamd_autosend_brake.py"
sed \
  -e "s/@OPENCLAW_UID@/$openclaw_uid/g" \
  -e "s/@OPENCLAW_GID@/$openclaw_gid/g" \
  "$repo_root/systemd/system/openclaw-lamd-autosend-brake.service.in" > "$unit_path.tmp"
chown root:root "$unit_path.tmp"
chmod 0644 "$unit_path.tmp"
mv "$unit_path.tmp" "$unit_path"
/usr/bin/python3 "$install_root/lamd_autosend_brake.py" init \
  --reason "operator-authorized LAMD autonomous-send brake installation"
systemctl daemon-reload
systemctl enable --now openclaw-lamd-autosend-brake.service
systemctl --no-pager --full status openclaw-lamd-autosend-brake.service
