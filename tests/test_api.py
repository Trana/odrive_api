import pytest
from pathlib import Path

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from odrive_api.config import ODriveApiSettings
from odrive_api.main import create_app
from odrive_api.services.odrive_service import ReadbackMismatchError


class FakeService:
    def __init__(self):
        self.started = False
        self.nodes = [11, 12]
        self.read_values = {"axis0.controller.config.pos_gain": 20.0}
        self.writes = []
        self.saved = []
        self.rebooted = []
        self.raise_on_read = None
        self.raise_on_write = None
        self.raise_on_save = None
        self.raise_on_reboot = None

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def snapshot(self):
        return {
            "started": self.started,
            "can_iface": "can0",
            "can_bustype": "socketcan",
            "endpoints_json": "flat_endpoints.json",
            "allowed_node_ids": [11, 12],
        }

    def list_nodes(self):
        return list(self.nodes)

    def read_many(self, node_id: int, paths: list[str], timeout_s=None):
        if self.raise_on_read is not None:
            raise self.raise_on_read
        return {path: self.read_values.get(path, None) for path in paths}

    def write_many(self, node_id: int, values: dict[str, object], verify_readback=False, readback_timeout_s=None):
        if self.raise_on_write is not None:
            raise self.raise_on_write
        self.writes.append((node_id, values, verify_readback, readback_timeout_s))
        return None

    def save_configuration(self, node_id: int):
        if self.raise_on_save is not None:
            raise self.raise_on_save
        self.saved.append(node_id)

    def reboot(self, node_id: int):
        if self.raise_on_reboot is not None:
            raise self.raise_on_reboot
        self.rebooted.append(node_id)


def test_health_endpoint_uses_service_snapshot():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "odrive-api"
    assert payload["status"] == "ok"
    assert payload["started"] is True
    assert payload["allowed_node_ids"] == [11, 12]


def test_nodes_endpoint_returns_allowlist():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/odrive/nodes")

    assert response.status_code == 200
    assert response.json() == {"nodes": [11, 12]}


def test_cors_preflight_allows_browser_origin_for_odrive_routes():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/odrive/nodes",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


def test_read_settings_endpoint():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/odrive/nodes/11/settings",
            params={"paths": "axis0.controller.config.pos_gain,axis0.controller.config.vel_gain"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["node_id"] == 11
    assert "axis0.controller.config.pos_gain" in payload["values"]
    assert "axis0.controller.config.vel_gain" in payload["values"]


def test_read_settings_requires_non_empty_paths():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/odrive/nodes/11/settings", params={"paths": ",,, "})

    assert response.status_code == 400


def test_read_settings_maps_permission_error():
    service = FakeService()
    service.raise_on_read = PermissionError("Node blocked")
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/odrive/nodes/99/settings", params={"paths": "axis0.controller.config.pos_gain"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ODRIVE_NODE_NOT_ALLOWED"
    assert response.json()["detail"]["message"] == "Node blocked"


def test_read_settings_maps_timeout_error():
    service = FakeService()
    service.raise_on_read = TimeoutError("read timeout")
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/odrive/nodes/11/settings", params={"paths": "axis0.controller.config.pos_gain"})

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "ODRIVE_READ_TIMEOUT"


def test_write_settings_endpoint():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/odrive/nodes/11/settings",
            json={"values": {"axis0.controller.config.pos_gain": 30.0}},
        )

    assert response.status_code == 200
    assert response.json() == {
        "node_id": 11,
        "written": ["axis0.controller.config.pos_gain"],
        "verified": False,
        "readback_values": None,
    }
    assert len(service.writes) == 1


def test_write_settings_rejects_empty_payload():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post("/api/v1/odrive/nodes/11/settings", json={"values": {}})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ODRIVE_INVALID_REQUEST"


def test_write_settings_maps_readback_mismatch_to_409():
    service = FakeService()
    service.raise_on_write = ReadbackMismatchError("mismatch")
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/odrive/nodes/11/settings",
            json={
                "values": {"axis0.controller.config.pos_gain": 30.0},
                "verify_readback": True,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ODRIVE_READBACK_MISMATCH"


def test_write_settings_maps_timeout_to_504():
    service = FakeService()
    service.raise_on_write = TimeoutError("timeout")
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/odrive/nodes/11/settings",
            json={
                "values": {"axis0.controller.config.pos_gain": 30.0},
                "verify_readback": True,
            },
        )

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "ODRIVE_WRITE_TIMEOUT"


def test_write_settings_maps_invalid_value_to_400():
    service = FakeService()
    service.raise_on_write = ValueError("bad value")
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/odrive/nodes/11/settings",
            json={"values": {"axis0.controller.config.pos_gain": "bad"}},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ODRIVE_INVALID_VALUE"


def test_save_endpoint():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post("/api/v1/odrive/nodes/11/save")

    assert response.status_code == 200
    assert response.json() == {"node_id": 11, "action": "save", "status": "ok"}
    assert service.saved == [11]


def test_reboot_endpoint():
    service = FakeService()
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post("/api/v1/odrive/nodes/11/reboot")

    assert response.status_code == 200
    assert response.json() == {"node_id": 11, "action": "reboot", "status": "ok"}
    assert service.rebooted == [11]


def test_write_settings_with_readback_verification():
    service = FakeService()

    def _write_many(node_id: int, values: dict[str, object], verify_readback=False, readback_timeout_s=None):
        assert verify_readback is True
        assert readback_timeout_s == 0.5
        return {"axis0.controller.config.pos_gain": 30.0}

    service.write_many = _write_many  # type: ignore[method-assign]
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/odrive/nodes/11/settings",
            json={
                "values": {"axis0.controller.config.pos_gain": 30.0},
                "verify_readback": True,
                "readback_timeout_s": 0.5,
            },
        )

    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert response.json()["readback_values"] == {"axis0.controller.config.pos_gain": 30.0}


def test_auth_required_when_token_configured():
    service = FakeService()
    settings = ODriveApiSettings(
        can_iface="can0",
        can_bustype="socketcan",
        endpoints_json=Path("flat_endpoints.json"),
        allowed_node_ids=(11, 12),
        request_timeout_s=0.25,
        max_paths_per_request=64,
        max_write_items=32,
        float_abs_tol=1e-5,
        float_rel_tol=1e-5,
        api_token="secret-token",
    )
    app = create_app(settings=settings, service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/odrive/nodes")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "ODRIVE_AUTH_REQUIRED"


def test_auth_invalid_token():
    service = FakeService()
    settings = ODriveApiSettings(
        can_iface="can0",
        can_bustype="socketcan",
        endpoints_json=Path("flat_endpoints.json"),
        allowed_node_ids=(11, 12),
        request_timeout_s=0.25,
        max_paths_per_request=64,
        max_write_items=32,
        float_abs_tol=1e-5,
        float_rel_tol=1e-5,
        api_token="secret-token",
    )
    app = create_app(settings=settings, service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/odrive/nodes", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ODRIVE_AUTH_INVALID"


def test_auth_valid_bearer_token():
    service = FakeService()
    settings = ODriveApiSettings(
        can_iface="can0",
        can_bustype="socketcan",
        endpoints_json=Path("flat_endpoints.json"),
        allowed_node_ids=(11, 12),
        request_timeout_s=0.25,
        max_paths_per_request=64,
        max_write_items=32,
        float_abs_tol=1e-5,
        float_rel_tol=1e-5,
        api_token="secret-token",
    )
    app = create_app(settings=settings, service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/odrive/nodes", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
