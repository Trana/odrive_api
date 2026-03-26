# PRD: ODrive Robot API

## Document Control
- Product: ODrive Robot API
- Repo: `odrive_api`
- Last updated: 2026-03-25
- Status: Active

## Problem Statement
ODrive settings are currently managed through ad-hoc scripts. We need a robot-hosted API so external tools can safely query and update ODrive settings using the existing CAN client behavior as the baseline.

## Goals
- Provide robot-side HTTP endpoints for ODrive settings operations.
- Reuse existing `ODriveClient` behavior for SDO/CANSimple operations.
- Ensure safe serialized CAN access to avoid response races.
- Keep API contracts explicit and versioned under `/api/v1/odrive/*`.
- Deploy cleanly on Ubuntu robot hosts.

## Non-Goals (V1)
- Full auth/RBAC system.
- Fleet orchestration across multiple robots.
- Real-time streaming dashboard UI.
- Advanced calibration workflows.

## Users
- Robot controls engineers updating ODrive config.
- Operators performing robot bring-up checks.
- Integration services that require programmatic config access.

## V1 Functional Scope
- health and node discovery surfaces
- settings read by endpoint paths
- settings write by endpoint path-value map
- save configuration and reboot operations

## V1 Plan (Phased)
1. Phase 1: Service skeleton
- shared ODrive client lifecycle
- startup/shutdown hooks
- serialized access lock
- environment-based config

2. Phase 2: API contract
- `GET /api/health`
- `GET /api/v1/odrive/nodes`
- `GET /api/v1/odrive/nodes/{node_id}/settings?paths=...`
- `POST /api/v1/odrive/nodes/{node_id}/settings`
- `POST /api/v1/odrive/nodes/{node_id}/save`
- `POST /api/v1/odrive/nodes/{node_id}/reboot`

3. Phase 3: Safety and validation
- allowlisted node IDs
- endpoint existence/type checks
- write/read-back safeguards

4. Phase 4: Error model + logging
- consistent HTTP error mapping
- structured request logging
- machine-readable error codes

5. Phase 5: Testing
- unit tests for validation and service logic
- integration tests with mocked CAN
- hardware smoke test checklist

6. Phase 6: Robot deployment
- single-worker runtime
- systemd unit
- LAN binding + token gate

## Success Metrics
- Query/update/save/reboot operations succeed on robot.
- API remains stable under concurrent request load without CAN race faults.
- V1 test plan passes in CI/local plus robot smoke checks.
