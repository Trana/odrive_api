# Architecture: ODrive Robot API

## Purpose
Define runtime topology, module boundaries, and contract constraints for the ODrive API implementation.

## System Context
- This repository hosts a FastAPI backend that runs on the robot.
- It wraps ODrive CAN interactions based on `/home/trana/Development/ros2/ros_odrive/odrive_config_setter/ODriveClient.py`.
- Consumers interact over HTTP while the service talks to ODrive over SocketCAN.

## Runtime Topology
- API process: FastAPI + Uvicorn
- CAN interface: SocketCAN (`can0` by default)
- ODrive protocol: SDO + CANSimple via `python-can`
- Deployment target: Ubuntu on real robot

## Phase Mapping
- Phase 1 (implemented): lifecycle service + lock + env config.
- Phase 2: API endpoint surface.
- Phase 3: strict validation guardrails.
- Phase 4: error/logging model.
- Phase 5: testing matrix.
- Phase 6: production deployment hardening.

## Core Components
- `odrive_api.config.ODriveApiSettings`
  - loads and validates env settings (`CAN_IFACE`, endpoints JSON path, allowlisted node IDs)
- `odrive_api.odrive_client.ODriveClient`
  - CAN protocol methods for endpoint read/write + save/reboot
- `odrive_api.services.odrive_service.ODriveService`
  - owns one bus/client instance per process
  - serializes operations with process-local lock
  - manages startup/shutdown lifecycle
- `odrive_api.main`
  - FastAPI app factory and lifespan wiring

## Concurrency Model
- API may receive concurrent requests.
- ODrive CAN request/reply flow is serialized by a single lock to avoid cross-request frame mixups.
- Production worker count must stay at 1 for v1 (`uvicorn --workers 1`).

## Configuration Contract
Environment variables (v1):
- `ODRIVE_API_CAN_IFACE` (default: `can0`)
- `ODRIVE_API_CAN_BUSTYPE` (default: `socketcan`)
- `ODRIVE_API_ENDPOINTS_JSON` (default: `flat_endpoints.json`)
- `ODRIVE_API_ALLOWED_NODE_IDS` (CSV ints)
- `ODRIVE_API_REQUEST_TIMEOUT_S` (float)
- `ODRIVE_API_MAX_PATHS_PER_REQUEST` (default: `64`)
- `ODRIVE_API_MAX_WRITE_ITEMS` (default: `32`)
- `ODRIVE_API_FLOAT_ABS_TOL` (default: `1e-5`)
- `ODRIVE_API_FLOAT_REL_TOL` (default: `1e-5`)
- `ODRIVE_API_CORS_ALLOWED_ORIGINS` (default: `*`; CSV origins, empty disables CORS middleware)

## Failure Modes
- missing/invalid endpoints JSON path -> startup failure
- missing python-can dependency -> startup failure
- CAN bus bring-up failure -> startup failure
- request timeout -> mapped API timeout error (Phase 4)
- endpoint unknown / wrong type / out-of-range values -> request validation error (Phase 3)
- write-readback mismatch when enabled -> conflict response (Phase 3)

## Error and Logging Contract
- API errors return `detail.code` and `detail.message`.
- Codes are stable per failure class (`ODRIVE_INVALID_REQUEST`, `ODRIVE_UNKNOWN_ENDPOINT`, `ODRIVE_INVALID_VALUE`, `ODRIVE_READ_TIMEOUT`, `ODRIVE_WRITE_TIMEOUT`, `ODRIVE_READBACK_MISMATCH`, `ODRIVE_NODE_NOT_ALLOWED`, `ODRIVE_SERVICE_UNAVAILABLE`, `ODRIVE_INTERNAL_ERROR`, `ODRIVE_AUTH_REQUIRED`, `ODRIVE_AUTH_INVALID`).
- Each ODrive route emits a structured JSON log record with:
  - operation name
  - node id (if applicable)
  - success/failure
  - status code
  - duration in milliseconds
  - error code/message (on failure)

## Deployment Model (Phase 6)
- Service supervision uses `systemd` with auto-restart and boot startup.
- Runtime wrapper script enforces `uvicorn --workers 1` regardless of env overrides.
- Unit template and env example are shipped in `deploy/systemd/`.
- Install/uninstall helpers are shipped in `scripts/install_systemd_service.sh` and `scripts/uninstall_systemd_service.sh`.
- Optional token gate for `/api/v1/odrive/*` routes is controlled by `ODRIVE_API_TOKEN`.

## Ownership and Tickets
- Phase 1 ownership: service/config/bootstrap internals.
- Later phases extend route handlers and validation models while preserving serialized service behavior.

## Testing Strategy
- Unit tests cover configuration parsing, lifecycle handling, safety validation, and readback verification.
- Integration tests run real FastAPI routes with real service lifecycle using mocked CAN bus/client adapters.
- Hardware smoke validation is manual and tracked via `docs/ROBOT_SMOKE_CHECKLIST.md`.
