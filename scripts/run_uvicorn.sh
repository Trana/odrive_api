#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${ODRIVE_API_APP_DIR:-/opt/odrive_api}"
VENV_DIR="${ODRIVE_API_VENV:-${APP_DIR}/.venv}"
BIND_HOST="${ODRIVE_API_BIND_HOST:-0.0.0.0}"
BIND_PORT="${ODRIVE_API_BIND_PORT:-8100}"
WORKERS="${ODRIVE_API_WORKERS:-1}"

if [[ "${WORKERS}" != "1" ]]; then
  echo "ODRIVE_API_WORKERS=${WORKERS} requested; forcing workers=1 for CAN safety" >&2
  WORKERS="1"
fi

if [[ ! -x "${VENV_DIR}/bin/uvicorn" ]]; then
  echo "uvicorn not found at ${VENV_DIR}/bin/uvicorn" >&2
  exit 1
fi

cd "${APP_DIR}"
exec "${VENV_DIR}/bin/uvicorn" odrive_api.main:app \
  --host "${BIND_HOST}" \
  --port "${BIND_PORT}" \
  --workers "${WORKERS}"
