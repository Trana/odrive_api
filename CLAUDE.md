# CLAUDE.md

Model-specific guidance for Claude. Keep product/process source of truth in model-neutral docs.

## Source of Truth
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/MILESTONES.md`
- [Active issue tracking](AGENTS.md#source-of-truth)
- `docs/EXECUTION_LOG.md`

## Execution Rules
- Use the assigned issue for scope, acceptance criteria and file ownership.
- Prefer minimal diffs and explicit acceptance-criteria checks.
- Add or update tests for changed behavior.
- Append evidence to `docs/EXECUTION_LOG.md`.

## Agent Roles
- Planner uses `prompts/planner.md`.
- Worker uses `prompts/worker.md`.
- Reviewer uses `prompts/reviewer.md`.

## Notes
- API runs on Ubuntu robot hosts and communicates over SocketCAN.
- Preserve deterministic CAN transaction behavior by serializing access.
