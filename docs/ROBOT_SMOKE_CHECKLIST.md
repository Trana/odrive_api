# Robot Smoke Checklist (Phase 5)

This checklist is for first-on-robot validation of ODrive API behavior after deploy.

## Preconditions
- API process running on robot (`uvicorn ... --workers 1`).
- `can0` up and ODrive nodes powered.
- `ODRIVE_API_ALLOWED_NODE_IDS` includes test nodes.
- Network path to API reachable.

## 1. Health and Node Discovery
```bash
curl -sS http://<robot-ip>:8100/api/health | jq .
curl -sS http://<robot-ip>:8100/api/v1/odrive/nodes | jq .
```
Expected
- `status` is `ok`
- expected node IDs listed

## 2. Read Known Settings
```bash
curl -sS "http://<robot-ip>:8100/api/v1/odrive/nodes/<node_id>/settings?paths=axis0.controller.config.pos_gain,axis0.controller.config.vel_limit" | jq .
```
Expected
- HTTP 200
- both fields present under `values`

## 3. Write + Readback Verify
Use a safe temporary value within known bounds.
```bash
curl -sS -X POST "http://<robot-ip>:8100/api/v1/odrive/nodes/<node_id>/settings" \
  -H "content-type: application/json" \
  -d '{
    "values": {"axis0.controller.config.pos_gain": 30.0},
    "verify_readback": true,
    "readback_timeout_s": 0.5
  }' | jq .
```
Expected
- HTTP 200
- `verified: true`
- `readback_values.axis0.controller.config.pos_gain == 30.0`

## 4. Save Configuration
```bash
curl -sS -X POST "http://<robot-ip>:8100/api/v1/odrive/nodes/<node_id>/save" | jq .
```
Expected
- HTTP 200
- `{"action":"save","status":"ok"}`

## 5. Reboot Command (Optional During Maintenance Window)
```bash
curl -sS -X POST "http://<robot-ip>:8100/api/v1/odrive/nodes/<node_id>/reboot" | jq .
```
Expected
- HTTP 200
- `{"action":"reboot","status":"ok"}`

## 6. Negative Contract Checks
Disallowed node
```bash
curl -sS -X POST "http://<robot-ip>:8100/api/v1/odrive/nodes/999/settings" \
  -H "content-type: application/json" \
  -d '{"values": {"axis0.controller.config.pos_gain": 30.0}}' | jq .
```
Expected
- HTTP 403
- `detail.code == "ODRIVE_NODE_NOT_ALLOWED"`

Unknown endpoint
```bash
curl -sS -X POST "http://<robot-ip>:8100/api/v1/odrive/nodes/<node_id>/settings" \
  -H "content-type: application/json" \
  -d '{"values": {"axis0.controller.config.unknown": 1}}' | jq .
```
Expected
- HTTP 400
- `detail.code == "ODRIVE_UNKNOWN_ENDPOINT"`

## 7. Rollback Value
Restore temporary write values back to known-good baseline and re-verify with a read call.

## 8. Evidence to Capture
- command logs with timestamp
- response payloads for each checklist section
- API logs containing `event=odrive_api_operation` entries
