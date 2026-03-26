from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from odrive_api.config import ODriveApiSettings
from odrive_api.main import create_app
from odrive_api.services.odrive_service import ODriveService


class MockBus:
    def __init__(self) -> None:
        self.shutdown_called = False

    def shutdown(self) -> None:
        self.shutdown_called = True


class MockClient:
    def __init__(self, bus, endpoints, meta):
        self.bus = bus
        self.endpoints = endpoints
        self.meta = meta
        self.state: dict[str, object] = {
            "axis0.controller.config.pos_gain": 20.0,
            "axis0.controller.config.vel_limit": 10.0,
            "axis0.controller.config.enable_sensorless_mode": False,
        }
        self.saved_nodes: list[int] = []
        self.rebooted_nodes: list[int] = []

    def read_many(self, node_id: int, paths: list[str], timeout_s: float = 0.25):
        return {path: self.state[path] for path in paths}

    def write_many(self, node_id: int, values: dict[str, object]):
        self.state.update(values)

    def save_configuration(self, node_id: int):
        self.saved_nodes.append(node_id)

    def reboot(self, node_id: int):
        self.rebooted_nodes.append(node_id)


def _write_endpoints(tmp_path: Path) -> Path:
    endpoints_path = tmp_path / "flat_endpoints.json"
    endpoints_path.write_text(
        """
{
  "endpoints": {
    "axis0.controller.config.pos_gain": {"id": 1, "type": "float"},
    "axis0.controller.config.vel_limit": {"id": 2, "type": "float"},
    "axis0.controller.config.enable_sensorless_mode": {"id": 3, "type": "bool"},
    "save_configuration": {"id": 4, "type": "function"},
    "reboot": {"id": 5, "type": "function"}
  }
}
""".strip(),
        encoding="utf-8",
    )
    return endpoints_path


def _build_app(tmp_path: Path):
    endpoints_path = _write_endpoints(tmp_path)
    client_holder: dict[str, MockClient] = {}
    bus_holder: dict[str, MockBus] = {}

    def bus_factory(_iface: str, _bustype: str):
        bus = MockBus()
        bus_holder["bus"] = bus
        return bus

    def client_factory(bus, endpoints, meta):
        client = MockClient(bus, endpoints, meta)
        client_holder["client"] = client
        return client

    settings = ODriveApiSettings(
        can_iface="can0",
        can_bustype="socketcan",
        endpoints_json=endpoints_path,
        allowed_node_ids=(11, 12),
        request_timeout_s=0.25,
        max_paths_per_request=64,
        max_write_items=32,
        float_abs_tol=1e-5,
        float_rel_tol=1e-5,
        api_token=None,
    )
    service = ODriveService(settings, bus_factory=bus_factory, client_factory=client_factory)
    app = create_app(settings=settings, service=service)
    return app, client_holder, bus_holder


def test_integration_happy_path_with_mocked_can(tmp_path: Path):
    app, client_holder, bus_holder = _build_app(tmp_path)

    with TestClient(app) as client:
        nodes_response = client.get("/api/v1/odrive/nodes")
        assert nodes_response.status_code == 200
        assert nodes_response.json() == {"nodes": [11, 12]}

        write_response = client.post(
            "/api/v1/odrive/nodes/11/settings",
            json={
                "values": {
                    "axis0.controller.config.pos_gain": 35.0,
                    "axis0.controller.config.enable_sensorless_mode": True,
                },
                "verify_readback": True,
            },
        )
        assert write_response.status_code == 200
        write_payload = write_response.json()
        assert write_payload["verified"] is True
        assert write_payload["readback_values"]["axis0.controller.config.pos_gain"] == 35.0
        assert write_payload["readback_values"]["axis0.controller.config.enable_sensorless_mode"] is True

        read_response = client.get(
            "/api/v1/odrive/nodes/11/settings",
            params={"paths": "axis0.controller.config.pos_gain,axis0.controller.config.enable_sensorless_mode"},
        )
        assert read_response.status_code == 200
        values = read_response.json()["values"]
        assert values["axis0.controller.config.pos_gain"] == 35.0
        assert values["axis0.controller.config.enable_sensorless_mode"] is True

        save_response = client.post("/api/v1/odrive/nodes/11/save")
        reboot_response = client.post("/api/v1/odrive/nodes/11/reboot")
        assert save_response.status_code == 200
        assert reboot_response.status_code == 200

    mock_client = client_holder["client"]
    assert mock_client.saved_nodes == [11]
    assert mock_client.rebooted_nodes == [11]
    assert bus_holder["bus"].shutdown_called is True


def test_integration_unknown_endpoint_error_code(tmp_path: Path):
    app, _, _ = _build_app(tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/odrive/nodes/11/settings",
            json={"values": {"axis0.controller.config.unknown": 1.0}},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ODRIVE_UNKNOWN_ENDPOINT"


def test_integration_disallowed_node_error_code(tmp_path: Path):
    app, _, _ = _build_app(tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/odrive/nodes/99/settings",
            json={"values": {"axis0.controller.config.pos_gain": 30.0}},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ODRIVE_NODE_NOT_ALLOWED"


def test_integration_max_paths_limit_error_code(tmp_path: Path):
    endpoints_path = _write_endpoints(tmp_path)

    settings = ODriveApiSettings(
        can_iface="can0",
        can_bustype="socketcan",
        endpoints_json=endpoints_path,
        allowed_node_ids=(11,),
        request_timeout_s=0.25,
        max_paths_per_request=1,
        max_write_items=32,
        float_abs_tol=1e-5,
        float_rel_tol=1e-5,
        api_token=None,
    )
    service = ODriveService(settings, bus_factory=lambda _a, _b: MockBus(), client_factory=MockClient)
    app = create_app(settings=settings, service=service)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/odrive/nodes/11/settings",
            params={"paths": "axis0.controller.config.pos_gain,axis0.controller.config.vel_limit"},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ODRIVE_INVALID_REQUEST"
