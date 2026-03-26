#!/usr/bin/env bash
set -euo pipefail

# Installs odrive-api service into systemd using a templated unit.
# Requires root privileges for writes to /etc/systemd/system and /etc/default.

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_PATH="${REPO_DIR}/deploy/systemd/odrive-api.service.template"
ENV_EXAMPLE_PATH="${REPO_DIR}/deploy/systemd/odrive-api.env.example"

APP_DIR="${ODRIVE_API_APP_DIR:-/opt/odrive_api}"
SERVICE_USER="${ODRIVE_API_SERVICE_USER:-$(id -un)}"
SERVICE_GROUP="${ODRIVE_API_SERVICE_GROUP:-$(id -gn)}"
SYSTEMD_UNIT_PATH="/etc/systemd/system/odrive-api.service"
ENV_FILE_PATH="/etc/default/odrive-api"

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "Missing template: ${TEMPLATE_PATH}" >&2
  exit 1
fi

TMP_UNIT="$(mktemp)"
sed \
  -e "s|__ODRIVE_API_APP_DIR__|${APP_DIR}|g" \
  -e "s|__ODRIVE_API_USER__|${SERVICE_USER}|g" \
  -e "s|__ODRIVE_API_GROUP__|${SERVICE_GROUP}|g" \
  "${TEMPLATE_PATH}" > "${TMP_UNIT}"

echo "Installing systemd unit to ${SYSTEMD_UNIT_PATH}"
install -m 0644 "${TMP_UNIT}" "${SYSTEMD_UNIT_PATH}"
rm -f "${TMP_UNIT}"

if [[ ! -f "${ENV_FILE_PATH}" ]]; then
  echo "Creating ${ENV_FILE_PATH} from example"
  install -m 0644 "${ENV_EXAMPLE_PATH}" "${ENV_FILE_PATH}"
else
  echo "Keeping existing ${ENV_FILE_PATH}"
fi

systemctl daemon-reload
systemctl enable odrive-api

echo "Installed odrive-api.service"
echo "Next steps:"
echo "  1) Edit ${ENV_FILE_PATH}"
echo "  2) systemctl restart odrive-api"
echo "  3) systemctl status odrive-api"
