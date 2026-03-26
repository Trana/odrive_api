# TKT-001: Phase 1 Service Skeleton

## Summary
Implement the initial ODrive API process skeleton with startup/shutdown lifecycle, shared client, lock-based serialization, and environment-based configuration.

## Milestone
- M1: Service Skeleton (Phase 1)

## Scope
- In scope:
  - service bootstrap and lifecycle wiring
  - settings loader from env
  - shared ODrive client ownership
  - serialized operation primitive
- Out of scope:
  - full v1 read/write route contract
  - strict validation and error code mapping

## File Ownership
- Primary files:
  - `src/odrive_api/main.py`
  - `src/odrive_api/config.py`
  - `src/odrive_api/services/odrive_service.py`
  - `src/odrive_api/odrive_client.py`
- Test files:
  - `tests/test_config.py`
  - `tests/test_service.py`
- Docs updates:
  - `docs/ARCHITECTURE.md`
  - `docs/EXECUTION_LOG.md`

## Contracts
- service exposes one process-local ODrive client instance
- service startup requires accessible endpoints JSON and CAN runtime support

## Acceptance Criteria
- [x] FastAPI app boots with lifecycle-managed service.
- [x] ODrive service owns exactly one active bus/client instance.
- [x] Service provides lock-serialized call path for CAN operations.
- [x] Env vars configure CAN iface, endpoints path, allowlisted node IDs.

## Test Plan
- Unit/Component:
  - env parsing and node list parsing tests
  - service startup/shutdown behavior with fake bus/client
- E2E/Integration:
  - N/A for phase 1
- Manual validation:
  - health endpoint reflects service startup state

## Risks and Rollback
- Risks:
  - startup dependency on hardware can fail in non-robot environments
- Rollback strategy:
  - keep app factory and service injection paths for test doubles

## Definition of Done
- [x] Acceptance criteria met.
- [x] Tests added/updated and passing.
- [x] Docs updated (`ARCHITECTURE`, ADR if needed, `EXECUTION_LOG`).
