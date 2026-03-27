# odrive_api

FastAPI backend for robot-side ODrive configuration management.

## Purpose
- expose HTTP endpoints to query and update ODrive settings
- reuse and wrap ODrive CAN client behavior from `ros_odrive`
- run directly on the real Ubuntu robot

## Project Workflow Docs
Canonical planning/execution docs:
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/MILESTONES.md`
- `docs/tickets/`
- `docs/EXECUTION_LOG.md`
- `docs/RUNBOOK.md`

## Stack
- Python 3.10+
- FastAPI
- Uvicorn
- python-can

## Current Implementation Status
- Phase 1 complete:
  - service lifecycle bootstrap (startup/shutdown)
  - shared ODrive client + CAN bus instance
  - serialized CAN access lock
  - environment-driven configuration

## Quick Start
```bash
cd /home/trana/Development/odrive_api
python -m venv .venv
source .venv/bin/activate
pip install ".[dev]"
uvicorn odrive_api.main:app --host 127.0.0.1 --port 8100 --reload
```

## OpenAPI + Swagger
- OpenAPI JSON: `http://127.0.0.1:8100/openapi.json`
- Swagger UI: `http://127.0.0.1:8100/docs`

## API (Phase 2)
- `GET /api/health`
- `GET /api/v1/odrive/nodes`
- `GET /api/v1/odrive/endpoints`
- `GET /api/v1/odrive/nodes/{node_id}/settings?paths=axis0.controller.config.pos_gain,axis0.controller.config.vel_gain`
- `POST /api/v1/odrive/nodes/{node_id}/settings`
- `POST /api/v1/odrive/nodes/{node_id}/save`
- `POST /api/v1/odrive/nodes/{node_id}/reboot`

Write payload now supports optional readback verification:
```json
{
  "values": {
    "axis0.controller.config.pos_gain": 30.0
  },
  "verify_readback": true,
  "readback_timeout_s": 0.5
}
```

Error responses follow a stable machine-readable shape:
```json
{
  "detail": {
    "code": "ODRIVE_INVALID_VALUE",
    "message": "Invalid setting value: ..."
  }
}
```

## Notes
- For real robot runtime, use a single worker process (`--workers 1`) to avoid CAN/SDO race conditions.
- Configure env vars documented in `docs/RUNBOOK.md`.
- Browser clients can be enabled via `ODRIVE_API_CORS_ALLOWED_ORIGINS` (default `*`).
- For managed robot deployment, use the shipped systemd artifacts:
  - `deploy/systemd/odrive-api.service.template`
  - `deploy/systemd/odrive-api.env.example`
  - `scripts/install_systemd_service.sh`
  - `scripts/uninstall_systemd_service.sh`
