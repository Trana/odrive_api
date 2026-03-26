# Runbook: ODrive API

## Local Development
```bash
cd /home/trana/Development/odrive_api
python -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
uvicorn odrive_api.main:app --host 127.0.0.1 --port 8100 --reload
```

## Production-like Robot Run
```bash
cd /home/trana/Development/odrive_api
source .venv/bin/activate
uvicorn odrive_api.main:app --host 0.0.0.0 --port 8100 --workers 1
```

## Production Service Install (`systemd`)
Prerequisites
- repository available at `/opt/odrive_api` (or set `ODRIVE_API_APP_DIR`)
- virtualenv created and dependencies installed in `${ODRIVE_API_VENV}`
- run install as root

Install
```bash
cd /opt/odrive_api
sudo ODRIVE_API_APP_DIR=/opt/odrive_api \
  ODRIVE_API_SERVICE_USER=ubuntu \
  ODRIVE_API_SERVICE_GROUP=ubuntu \
  ./scripts/install_systemd_service.sh
```

Configure env file
```bash
sudoedit /etc/default/odrive-api
```

Start and verify
```bash
sudo systemctl restart odrive-api
sudo systemctl status odrive-api
sudo journalctl -u odrive-api -f
```

Uninstall
```bash
cd /opt/odrive_api
sudo ./scripts/uninstall_systemd_service.sh
```

## Required Environment Variables (override defaults as needed)
- `ODRIVE_API_CAN_IFACE=can0`
- `ODRIVE_API_CAN_BUSTYPE=socketcan`
- `ODRIVE_API_ENDPOINTS_JSON=/abs/path/to/flat_endpoints.json`
- `ODRIVE_API_ALLOWED_NODE_IDS=11,12,13,21,22,23,31,32,33,41,42,43`
- `ODRIVE_API_REQUEST_TIMEOUT_S=0.25`
- `ODRIVE_API_MAX_PATHS_PER_REQUEST=64`
- `ODRIVE_API_MAX_WRITE_ITEMS=32`
- `ODRIVE_API_FLOAT_ABS_TOL=1e-5`
- `ODRIVE_API_FLOAT_REL_TOL=1e-5`
- `ODRIVE_API_TOKEN=<optional-strong-token>`
- `ODRIVE_API_CORS_ALLOWED_ORIGINS=*` (CSV list; set empty to disable CORS middleware)

Service/runtime envs used by `scripts/run_uvicorn.sh`:
- `ODRIVE_API_APP_DIR=/opt/odrive_api`
- `ODRIVE_API_VENV=/opt/odrive_api/.venv`
- `ODRIVE_API_BIND_HOST=0.0.0.0`
- `ODRIVE_API_BIND_PORT=8100`
- `ODRIVE_API_WORKERS=1` (forced to 1 by wrapper script)

## Health Endpoints
- `GET /`
- `GET /api/health`

## Robot Smoke Validation
- Run the full hardware checklist in `docs/ROBOT_SMOKE_CHECKLIST.md` after deployment updates.

## Rollback Procedure
1. Deploy previous known-good `odrive_api` revision to `/opt/odrive_api`.
2. Restore previous `/etc/default/odrive-api` if changed.
3. Restart service:
```bash
sudo systemctl restart odrive-api
sudo systemctl status odrive-api
```
4. Re-run the critical subset of `docs/ROBOT_SMOKE_CHECKLIST.md` (health, nodes, read/write verify).

## Quick Troubleshooting
- API fails at startup with endpoints error:
  - confirm `ODRIVE_API_ENDPOINTS_JSON` exists and is readable
- API fails opening CAN bus:
  - verify `can0` is up and permissions are correct on robot
- Service starts but no hardware response:
  - verify ODrive node IDs and wiring/termination
- API request returns errors:
  - inspect `detail.code` and `detail.message` in the HTTP response body
  - check structured operation logs for matching `error_code` and `duration_ms`
