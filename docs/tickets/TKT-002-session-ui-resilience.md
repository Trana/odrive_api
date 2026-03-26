# TKT-002: Phase 2 API Contract

## Summary
Implement first public v1 ODrive endpoint surface for node listing, settings read/write, save, and reboot operations.

## Milestone
- M2: API Contract (Phase 2)

## Scope
- In scope:
  - `/api/v1/odrive/*` route handlers
  - request/response models
  - OpenAPI contract documentation
- Out of scope:
  - advanced safety controls and full error taxonomy

## File Ownership
- Primary files:
  - `src/odrive_api/main.py`
  - `src/odrive_api/models.py`
  - `src/odrive_api/services/odrive_service.py`
- Test files:
  - `tests/test_api.py`
- Docs updates:
  - `docs/PRD.md`
  - `docs/EXECUTION_LOG.md`

## Contracts
- routes versioned under `/api/v1/odrive`
- payloads remain backward compatible or version bump required

## Acceptance Criteria
- [x] endpoints for list/read/write/save/reboot implemented
- [x] OpenAPI models generated and documented
- [x] integration tests cover happy-path request flows
