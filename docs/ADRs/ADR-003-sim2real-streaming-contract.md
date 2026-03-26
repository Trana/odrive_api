# ADR-003: Contract-First ODrive Endpoint Surface

## Status
Accepted

## Context
Unsafe or ambiguous settings APIs can damage robot behavior and make operational debugging difficult.

## Decision
- Define explicit versioned routes under `/api/v1/odrive/*`.
- Keep request/response models typed and documented in OpenAPI.
- Add validation phases before expanding API scope.

## Consequences
- Pros:
  - predictable client integration
  - easier regression detection and testing
- Cons:
  - requires up-front contract curation
