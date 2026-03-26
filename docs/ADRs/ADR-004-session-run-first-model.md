# ADR-004: Serialized Service Access Model

## Status
Accepted

## Context
The service must support concurrent HTTP access while preserving correctness of CAN frame matching.

## Decision
- Keep one shared bus/client instance per API process.
- Use a lock to serialize all client operations.
- Expose service lifecycle via FastAPI startup/shutdown hooks.

## Consequences
- Pros:
  - avoids cross-request reply confusion
  - clean ownership and lifecycle boundaries
- Cons:
  - concurrent callers queue behind lock
