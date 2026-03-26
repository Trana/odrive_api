# Tests Directory

This repository keeps unit and integration tests under `tests/`.

Current baseline coverage focuses on:
- settings/env parsing
- phase 1 service lifecycle and locking behavior scaffolding
- API contract and error code mappings
- mocked-CAN integration flows (`test_integration_mocked_can.py`)
- optional token auth behavior for `/api/v1/odrive/*` routes

Hardware validation is documented separately in:
- `docs/ROBOT_SMOKE_CHECKLIST.md`
