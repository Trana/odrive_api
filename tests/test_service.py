from pathlib import Path

import pytest

from odrive_api.config import ODriveApiSettings
from odrive_api.services.odrive_service import ODriveService, ReadbackMismatchError


class FakeBus:
    def __init__(self):
        self.shutdown_called = False

    def shutdown(self):
        self.shutdown_called = True


class FakeClient:
    def __init__(self, bus, endpoints, meta):
        self.bus = bus
        self.endpoints = endpoints
        self.meta = meta
        self.writes = []
        self.saved = []
        self.rebooted = []
        self.readback_override = None

    def read_many(self, node_id: int, paths: list[str], timeout_s: float = 0.25):
        if self.readback_override is not None:
            return {path: self.readback_override.get(path) for path in paths}

        values = {}
        for path in paths:
            if self.writes:
                for _node_id, payload in reversed(self.writes):
                    if path in payload:
                        values[path] = payload[path]
                        break
                else:
                    values[path] = None
            else:
                values[path] = None
        return values

    def write_many(self, node_id: int, values: dict[str, object]):
        self.writes.append((node_id, values))

    def save_configuration(self, node_id: int):
        self.saved.append(node_id)

    def reboot(self, node_id: int):
        self.rebooted.append(node_id)


def _settings(endpoints_path: Path, *, node_ids=(11, 12)) -> ODriveApiSettings:
    return ODriveApiSettings(
        can_iface="can0",
        can_bustype="socketcan",
        endpoints_json=endpoints_path,
        allowed_node_ids=tuple(node_ids),
        request_timeout_s=0.25,
        max_paths_per_request=64,
        max_write_items=32,
        float_abs_tol=1e-5,
        float_rel_tol=1e-5,
        api_token=None,
    )


def _endpoints_file(tmp_path: Path) -> Path:
    endpoints_path = tmp_path / "flat_endpoints.json"
    endpoints_path.write_text(
        """
{
  "endpoints": {
    "axis0.controller.config.pos_gain": {"id": 1, "type": "float"},
    "axis0.controller.config.vel_limit": {"id": 2, "type": "float"},
    "axis0.controller.config.control_mode": {"id": 3, "type": "int32"},
    "axis0.controller.config.enable_sensorless_mode": {"id": 4, "type": "bool"},
    "save_configuration": {"id": 5, "type": "function"},
    "reboot": {"id": 6, "type": "function"}
  }
}
""".strip(),
        encoding="utf-8",
    )
    return endpoints_path


def test_service_start_stop(tmp_path: Path):
    endpoints_path = _endpoints_file(tmp_path)
    bus = FakeBus()

    def bus_factory(_iface: str, _bustype: str):
        return bus

    service = ODriveService(_settings(endpoints_path), bus_factory=bus_factory, client_factory=FakeClient)

    assert not service.started
    service.start()
    assert service.started
    service.stop()
    assert not service.started
    assert bus.shutdown_called


def test_service_ensure_node_allowed(tmp_path: Path):
    endpoints_path = _endpoints_file(tmp_path)
    service = ODriveService(_settings(endpoints_path), bus_factory=lambda _a, _b: FakeBus(), client_factory=FakeClient)

    service.ensure_node_allowed(11)

    with pytest.raises(PermissionError):
        service.ensure_node_allowed(13)


def test_run_serialized_requires_started(tmp_path: Path):
    endpoints_path = _endpoints_file(tmp_path)
    service = ODriveService(_settings(endpoints_path), bus_factory=lambda _a, _b: FakeBus(), client_factory=FakeClient)

    with pytest.raises(RuntimeError):
        service.run_serialized(lambda: None)


def test_list_nodes_returns_settings_allowlist(tmp_path: Path):
    endpoints_path = _endpoints_file(tmp_path)
    service = ODriveService(_settings(endpoints_path, node_ids=(7, 8, 9)), bus_factory=lambda _a, _b: FakeBus(), client_factory=FakeClient)

    assert service.list_nodes() == [7, 8, 9]


def test_read_many_validates_paths_and_count(tmp_path: Path):
    endpoints_path = _endpoints_file(tmp_path)
    settings = _settings(endpoints_path)
    settings = ODriveApiSettings(
        can_iface=settings.can_iface,
        can_bustype=settings.can_bustype,
        endpoints_json=settings.endpoints_json,
        allowed_node_ids=settings.allowed_node_ids,
        request_timeout_s=settings.request_timeout_s,
        max_paths_per_request=1,
        max_write_items=settings.max_write_items,
        float_abs_tol=settings.float_abs_tol,
        float_rel_tol=settings.float_rel_tol,
        api_token=settings.api_token,
    )
    service = ODriveService(settings, bus_factory=lambda _a, _b: FakeBus(), client_factory=FakeClient)
    service.start()

    with pytest.raises(ValueError):
        service.read_many(11, ["axis0.controller.config.pos_gain", "axis0.controller.config.vel_limit"])

    with pytest.raises(KeyError):
        service.read_many(11, ["unknown.path"])


def test_write_many_coerces_types_and_can_verify_readback(tmp_path: Path):
    endpoints_path = _endpoints_file(tmp_path)
    service = ODriveService(_settings(endpoints_path), bus_factory=lambda _a, _b: FakeBus(), client_factory=FakeClient)
    service.start()

    readback = service.write_many(
        11,
        {
            "axis0.controller.config.pos_gain": 30,
            "axis0.controller.config.control_mode": 3,
            "axis0.controller.config.enable_sensorless_mode": True,
        },
        verify_readback=True,
    )

    assert isinstance(readback, dict)
    assert readback["axis0.controller.config.pos_gain"] == 30.0


def test_write_many_rejects_invalid_types_ranges_and_function_path(tmp_path: Path):
    endpoints_path = _endpoints_file(tmp_path)
    service = ODriveService(_settings(endpoints_path), bus_factory=lambda _a, _b: FakeBus(), client_factory=FakeClient)
    service.start()

    with pytest.raises(TypeError):
        service.write_many(11, {"axis0.controller.config.pos_gain": "bad"})

    with pytest.raises(ValueError):
        service.write_many(11, {"axis0.controller.config.control_mode": 2**40})

    with pytest.raises(ValueError):
        service.write_many(11, {"save_configuration": 1})


def test_write_many_readback_mismatch_raises(tmp_path: Path):
    endpoints_path = _endpoints_file(tmp_path)
    service = ODriveService(_settings(endpoints_path), bus_factory=lambda _a, _b: FakeBus(), client_factory=FakeClient)
    service.start()

    client = service._require_client()  # internal test-only access
    client.readback_override = {"axis0.controller.config.pos_gain": 99.0}

    with pytest.raises(ReadbackMismatchError):
        service.write_many(
            11,
            {"axis0.controller.config.pos_gain": 30.0},
            verify_readback=True,
        )
