#!/usr/bin/env bash
set -euo pipefail

# Uninstalls odrive-api service unit from systemd.
# Requires root privileges.

SYSTEMD_UNIT_PATH="/etc/systemd/system/odrive-api.service"

if systemctl is-active --quiet odrive-api; then
  systemctl stop odrive-api
fi

if systemctl is-enabled --quiet odrive-api; then
  systemctl disable odrive-api
fi

if [[ -f "${SYSTEMD_UNIT_PATH}" ]]; then
  rm -f "${SYSTEMD_UNIT_PATH}"
fi

systemctl daemon-reload

echo "Removed odrive-api.service"
