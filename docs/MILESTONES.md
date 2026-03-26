# Milestones: ODrive Robot API

## M1: Service Skeleton (Phase 1)
Status: Complete
- create app scaffold and package layout
- add shared ODrive client service lifecycle
- add serialized CAN access lock
- add env-driven configuration

## M2: API Contract (Phase 2)
Status: Complete
- implement v1 read/write/save/reboot routes
- add OpenAPI models for request/response shapes

## M3: Safety and Validation (Phase 3)
Status: Complete
- enforce node allowlist and endpoint existence
- enforce type-safe writes and optional readback verify

## M4: Errors and Observability (Phase 4)
Status: Complete
- stable error schema and code mapping
- structured operation logs and durations

## M5: Test Matrix (Phase 5)
Status: Complete
- unit + integration tests
- robot smoke test checklist

## M6: Robot Deployment (Phase 6)
Status: Complete
- systemd service
- single-worker production runbook
- network exposure + token strategy
