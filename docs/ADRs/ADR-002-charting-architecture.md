# ADR-002: FastAPI with Single-Worker CAN Runtime

## Status
Accepted

## Context
ODrive SDO operations are request/reply interactions that can race when parallelized unsafely across workers/threads.

## Decision
- Use FastAPI for API surface and OpenAPI tooling.
- Run one process worker in production (`--workers 1`).
- Serialize all CAN interactions with a process-local lock.

## Consequences
- Pros:
  - deterministic CAN transaction ordering
  - straightforward startup/deployment model
- Cons:
  - lower max throughput (acceptable for config-oriented API)
