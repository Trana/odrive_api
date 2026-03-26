# ADR-001: External ODrive Client Baseline Boundary

## Status
Accepted

## Context
Existing ODrive CAN behavior exists in `ros_odrive` and is actively used. Rewriting protocol logic from scratch increases risk.

## Decision
- Treat the existing ODrive client behavior as the baseline contract.
- Implement API service as a wrapper around equivalent client semantics.
- Keep protocol behavior changes explicit and reviewed via tickets/ADRs.

## Consequences
- Pros:
  - lower migration risk
  - easier parity checks with current tooling
- Cons:
  - inherited protocol assumptions require careful validation
