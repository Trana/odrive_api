from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    service: str
    status: str
    started: bool
    can_iface: str
    can_bustype: str
    endpoints_json: str
    allowed_node_ids: list[int]


class NodesResponse(BaseModel):
    nodes: list[int]


class EndpointCatalogItem(BaseModel):
    path: str
    id: int
    type: str
    readable: bool
    writable: bool
    inputs: list[dict[str, Any]] | None = None
    outputs: list[dict[str, Any]] | None = None


class EndpointCatalogResponse(BaseModel):
    endpoints: list[EndpointCatalogItem]


class ReadSettingsResponse(BaseModel):
    node_id: int
    values: dict[str, Any]


class ResponseTimeRequest(BaseModel):
    samples: int = Field(default=20, ge=1, le=100)
    interval_ms: float = Field(default=50.0, ge=10.0, le=1000.0)
    timeout_ms: float = Field(default=100.0, ge=1.0, le=1000.0)


class ResponseTimeResponse(BaseModel):
    node_id: int
    probe: str
    command_id: int
    sent: int
    received: int
    timeouts: int
    interval_ms: float
    timeout_ms: float
    min_ms: float | None
    median_ms: float | None
    p95_ms: float | None
    max_ms: float | None
    samples_ms: list[float | None]


class WriteSettingsRequest(BaseModel):
    values: dict[str, Any]
    verify_readback: bool = False
    readback_timeout_s: float | None = None


class WriteSettingsResponse(BaseModel):
    node_id: int
    written: list[str]
    verified: bool = False
    readback_values: dict[str, Any] | None = None


class NodeActionResponse(BaseModel):
    node_id: int
    action: str
    status: str
