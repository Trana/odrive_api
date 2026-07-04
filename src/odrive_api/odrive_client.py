from __future__ import annotations

import json
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OPCODE_READ = 0x00
OPCODE_WRITE = 0x01
GET_VERSION_CMD_ID = 0x00
GET_VERSION_PAYLOAD_SIZE = 8

FORMAT_LOOKUP = {
    "bool": "?",
    "uint8": "B",
    "int8": "b",
    "uint16": "H",
    "int16": "h",
    "uint32": "I",
    "int32": "i",
    "uint64": "Q",
    "int64": "q",
    "float": "f",
}


@dataclass(frozen=True)
class Endpoint:
    id: int
    typ: str


def load_endpoints(path: Path) -> tuple[dict[str, Endpoint], dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)

    raw_endpoints = data["endpoints"]
    endpoints = {name: Endpoint(id=value["id"], typ=value["type"]) for name, value in raw_endpoints.items()}
    return endpoints, data


class ODriveClient:
    """Light wrapper for ODrive SDO operations over python-can."""

    def __init__(self, bus: Any, endpoints: dict[str, Endpoint], endpoint_meta: dict[str, Any]):
        self.bus = bus
        self.endpoints = endpoints
        self.endpoint_meta = endpoint_meta

    def _flush_rx(self) -> None:
        while self.bus.recv(timeout=0) is not None:
            pass

    def _endpoint(self, path: str) -> Endpoint:
        endpoint = self.endpoints.get(path)
        if endpoint is None:
            raise KeyError(f"Endpoint not found: {path}")
        return endpoint

    def sdo_read(self, node_id: int, path: str, timeout_s: float = 0.25) -> Any:
        endpoint = self._endpoint(path)
        fmt = FORMAT_LOOKUP[endpoint.typ]

        self._flush_rx()
        self.bus.send(
            self.bus.message_factory(
                arbitration_id=(node_id << 5) | 0x04,
                data=struct.pack("<BHB", OPCODE_READ, endpoint.id, 0),
                is_extended_id=False,
            )
        )

        start = time.time()
        while True:
            message = self.bus.recv(timeout=0.02)
            if message is None:
                if (time.time() - start) > timeout_s:
                    raise TimeoutError(f"Timeout reading {path} from node {node_id}")
                continue
            if message.arbitration_id == ((node_id << 5) | 0x05):
                _, _, _, value = struct.unpack_from("<BHB" + fmt, message.data)
                return value

    def sdo_write(self, node_id: int, path: str, value: Any = None) -> None:
        endpoint = self._endpoint(path)

        if endpoint.typ == "function":
            data = struct.pack("<BHB", OPCODE_WRITE, endpoint.id, 0)
        else:
            fmt = FORMAT_LOOKUP[endpoint.typ]
            data = struct.pack("<BHB" + fmt, OPCODE_WRITE, endpoint.id, 0, value)

        self.bus.send(
            self.bus.message_factory(
                arbitration_id=(node_id << 5) | 0x04,
                data=data,
                is_extended_id=False,
            )
        )

    def measure_response_time(
        self,
        node_id: int,
        *,
        sample_count: int,
        interval_s: float,
        timeout_s: float,
    ) -> list[float | None]:
        response_id = (node_id << 5) | GET_VERSION_CMD_ID
        samples_ms: list[float | None] = []

        for sample_index in range(sample_count):
            self._flush_rx()
            request = self.bus.message_factory(
                arbitration_id=response_id,
                data=b"",
                is_extended_id=False,
                is_remote_frame=True,
                dlc=GET_VERSION_PAYLOAD_SIZE,
            )
            started = time.perf_counter()
            self.bus.send(request)
            deadline = started + timeout_s
            measured_ms: float | None = None

            while True:
                remaining_s = deadline - time.perf_counter()
                if remaining_s <= 0:
                    break
                message = self.bus.recv(timeout=min(0.02, remaining_s))
                if message is None:
                    continue
                if (
                    message.arbitration_id == response_id
                    and not getattr(message, "is_remote_frame", False)
                    and len(message.data) >= GET_VERSION_PAYLOAD_SIZE
                ):
                    measured_ms = (time.perf_counter() - started) * 1000.0
                    break

            samples_ms.append(measured_ms)
            if sample_index + 1 < sample_count and interval_s > 0:
                time.sleep(interval_s)

        return samples_ms

    def read_many(self, node_id: int, paths: list[str], timeout_s: float = 0.25) -> dict[str, Any]:
        return {path: self.sdo_read(node_id, path, timeout_s=timeout_s) for path in paths}

    def write_many(self, node_id: int, values: dict[str, Any]) -> None:
        for path, value in values.items():
            self.sdo_write(node_id, path, value)

    def save_configuration(self, node_id: int) -> None:
        self.sdo_write(node_id, "save_configuration")

    def reboot(self, node_id: int) -> None:
        self.sdo_write(node_id, "reboot")
