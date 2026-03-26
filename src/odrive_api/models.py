from __future__ import annotations

from typing import Any

from pydantic import BaseModel


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


class ReadSettingsResponse(BaseModel):
    node_id: int
    values: dict[str, Any]


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
