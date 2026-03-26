from __future__ import annotations

from collections.abc import Callable
from math import isclose
import threading
from pathlib import Path
from typing import Any

from odrive_api.config import ODriveApiSettings
from odrive_api.odrive_client import Endpoint, ODriveClient, load_endpoints


BusFactory = Callable[[str, str], Any]
ClientFactory = Callable[[Any, dict[str, Any], dict[str, Any]], ODriveClient]


_INT_RANGES: dict[str, tuple[int, int]] = {
    "uint8": (0, 2**8 - 1),
    "int8": (-(2**7), 2**7 - 1),
    "uint16": (0, 2**16 - 1),
    "int16": (-(2**15), 2**15 - 1),
    "uint32": (0, 2**32 - 1),
    "int32": (-(2**31), 2**31 - 1),
    "uint64": (0, 2**64 - 1),
    "int64": (-(2**63), 2**63 - 1),
}


class ReadbackMismatchError(ValueError):
    """Raised when write verification readback does not match requested values."""


class ODriveService:
    """Owns ODrive client lifecycle and provides serialized access."""

    def __init__(
        self,
        settings: ODriveApiSettings,
        *,
        bus_factory: BusFactory | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.settings = settings
        self._bus_factory = bus_factory or create_socketcan_bus
        self._client_factory = client_factory or ODriveClient

        self._lock = threading.Lock()
        self._bus: Any | None = None
        self._client: ODriveClient | None = None

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    @property
    def started(self) -> bool:
        return self._client is not None and self._bus is not None

    def _require_client(self) -> ODriveClient:
        if not self.started or self._client is None:
            raise RuntimeError("ODrive service is not started")
        return self._client

    def start(self) -> None:
        if self.started:
            return

        endpoints_path = Path(self.settings.endpoints_json)
        if not endpoints_path.exists():
            raise FileNotFoundError(f"Endpoints JSON not found: {endpoints_path}")

        endpoints, meta = load_endpoints(endpoints_path)
        bus = self._bus_factory(self.settings.can_iface, self.settings.can_bustype)
        client = self._client_factory(bus, endpoints, meta)

        self._bus = bus
        self._client = client

    def stop(self) -> None:
        bus = self._bus
        self._client = None
        self._bus = None

        if bus is not None:
            shutdown = getattr(bus, "shutdown", None)
            if callable(shutdown):
                shutdown()

    def ensure_node_allowed(self, node_id: int) -> None:
        if not self.settings.is_node_allowed(node_id):
            raise PermissionError(f"Node {node_id} is not in ODRIVE_API_ALLOWED_NODE_IDS")

    def run_serialized(self, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._require_client()
        with self._lock:
            return operation(*args, **kwargs)

    def _validate_paths(self, paths: list[str], *, max_count: int) -> list[str]:
        client = self._require_client()

        if len(paths) == 0:
            raise ValueError("At least one path must be provided")
        if len(paths) > max_count:
            raise ValueError(f"Too many paths requested ({len(paths)} > {max_count})")

        unknown = [path for path in paths if path not in client.endpoints]
        if unknown:
            raise KeyError(f"Unknown endpoint path(s): {', '.join(unknown)}")

        return paths

    def _coerce_value(self, path: str, endpoint: Endpoint, value: Any) -> Any:
        endpoint_type = endpoint.typ

        if endpoint_type == "function":
            raise ValueError(f"Endpoint {path} is a function endpoint and cannot be set via settings write")

        if endpoint_type == "bool":
            if isinstance(value, bool):
                return value
            raise TypeError(f"Endpoint {path} expects bool")

        if endpoint_type == "float":
            if isinstance(value, bool):
                raise TypeError(f"Endpoint {path} expects float")
            if isinstance(value, (int, float)):
                return float(value)
            raise TypeError(f"Endpoint {path} expects float")

        if endpoint_type in _INT_RANGES:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"Endpoint {path} expects integer type {endpoint_type}")
            lo, hi = _INT_RANGES[endpoint_type]
            if value < lo or value > hi:
                raise ValueError(f"Endpoint {path} value {value} out of range for {endpoint_type}")
            return int(value)

        raise ValueError(f"Unsupported endpoint type for {path}: {endpoint_type}")

    def _prepare_write_values(self, values: dict[str, Any]) -> dict[str, Any]:
        client = self._require_client()

        if not values:
            raise ValueError("At least one endpoint value must be provided")
        if len(values) > self.settings.max_write_items:
            raise ValueError(f"Too many write items ({len(values)} > {self.settings.max_write_items})")

        unknown = [path for path in values if path not in client.endpoints]
        if unknown:
            raise KeyError(f"Unknown endpoint path(s): {', '.join(unknown)}")

        coerced: dict[str, Any] = {}
        for path, value in values.items():
            endpoint = client.endpoints[path]
            coerced[path] = self._coerce_value(path, endpoint, value)
        return coerced

    def _values_equal(self, endpoint: Endpoint, expected: Any, actual: Any) -> bool:
        if endpoint.typ == "float":
            return isclose(
                float(expected),
                float(actual),
                rel_tol=self.settings.float_rel_tol,
                abs_tol=self.settings.float_abs_tol,
            )
        return expected == actual

    def list_nodes(self) -> list[int]:
        return list(self.settings.allowed_node_ids)

    def read_many(self, node_id: int, paths: list[str], timeout_s: float | None = None) -> dict[str, Any]:
        self.ensure_node_allowed(node_id)
        validated_paths = self._validate_paths(paths, max_count=self.settings.max_paths_per_request)
        timeout = self.settings.request_timeout_s if timeout_s is None else float(timeout_s)
        client = self._require_client()
        return self.run_serialized(client.read_many, node_id, validated_paths, timeout_s=timeout)

    def write_many(
        self,
        node_id: int,
        values: dict[str, Any],
        *,
        verify_readback: bool = False,
        readback_timeout_s: float | None = None,
    ) -> dict[str, Any] | None:
        self.ensure_node_allowed(node_id)
        client = self._require_client()
        coerced_values = self._prepare_write_values(values)

        self.run_serialized(client.write_many, node_id, coerced_values)

        if not verify_readback:
            return None

        timeout = self.settings.request_timeout_s if readback_timeout_s is None else float(readback_timeout_s)
        readback = self.run_serialized(client.read_many, node_id, list(coerced_values.keys()), timeout_s=timeout)

        mismatches: list[str] = []
        for path, expected_value in coerced_values.items():
            endpoint = client.endpoints[path]
            actual_value = readback.get(path)
            if not self._values_equal(endpoint, expected_value, actual_value):
                mismatches.append(f"{path}: expected={expected_value} actual={actual_value}")

        if mismatches:
            raise ReadbackMismatchError("Readback verification failed: " + "; ".join(mismatches))

        return readback

    def save_configuration(self, node_id: int) -> None:
        self.ensure_node_allowed(node_id)
        client = self._require_client()
        self.run_serialized(client.save_configuration, node_id)

    def reboot(self, node_id: int) -> None:
        self.ensure_node_allowed(node_id)
        client = self._require_client()
        self.run_serialized(client.reboot, node_id)

    def snapshot(self) -> dict[str, Any]:
        return {
            "started": self.started,
            "can_iface": self.settings.can_iface,
            "can_bustype": self.settings.can_bustype,
            "endpoints_json": str(self.settings.endpoints_json),
            "allowed_node_ids": list(self.settings.allowed_node_ids),
            "max_paths_per_request": self.settings.max_paths_per_request,
            "max_write_items": self.settings.max_write_items,
        }


def create_socketcan_bus(can_iface: str, can_bustype: str) -> Any:
    try:
        import can  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("python-can is required to start ODrive service") from exc

    class _SocketCanBusAdapter:
        def __init__(self, inner_bus: Any):
            self._inner_bus = inner_bus

        def recv(self, timeout: float | None = None) -> Any:
            return self._inner_bus.recv(timeout=timeout)

        def send(self, message: Any) -> None:
            self._inner_bus.send(message)

        def message_factory(self, *, arbitration_id: int, data: bytes, is_extended_id: bool) -> Any:
            return can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=is_extended_id)

        def shutdown(self) -> None:
            self._inner_bus.shutdown()

    bus = can.interface.Bus(can_iface, bustype=can_bustype)
    return _SocketCanBusAdapter(bus)
