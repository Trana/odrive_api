from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


DEFAULT_ALLOWED_NODE_IDS = (11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43)


@dataclass(frozen=True)
class ODriveApiSettings:
    can_iface: str
    can_bustype: str
    endpoints_json: Path
    allowed_node_ids: tuple[int, ...]
    request_timeout_s: float
    max_paths_per_request: int
    max_write_items: int
    float_abs_tol: float
    float_rel_tol: float
    api_token: str | None
    cors_allowed_origins: tuple[str, ...] = ("*",)

    @classmethod
    def from_env(cls) -> "ODriveApiSettings":
        can_iface = os.getenv("ODRIVE_API_CAN_IFACE", "can0").strip() or "can0"
        can_bustype = os.getenv("ODRIVE_API_CAN_BUSTYPE", "socketcan").strip() or "socketcan"
        endpoints_json_raw = os.getenv("ODRIVE_API_ENDPOINTS_JSON", "flat_endpoints.json").strip()
        endpoints_json = Path(endpoints_json_raw)
        allowed_node_ids = _parse_node_ids(os.getenv("ODRIVE_API_ALLOWED_NODE_IDS", ""))
        request_timeout_s = float(os.getenv("ODRIVE_API_REQUEST_TIMEOUT_S", "0.25"))
        max_paths_per_request = int(os.getenv("ODRIVE_API_MAX_PATHS_PER_REQUEST", "64"))
        max_write_items = int(os.getenv("ODRIVE_API_MAX_WRITE_ITEMS", "32"))
        float_abs_tol = float(os.getenv("ODRIVE_API_FLOAT_ABS_TOL", "1e-5"))
        float_rel_tol = float(os.getenv("ODRIVE_API_FLOAT_REL_TOL", "1e-5"))
        api_token_raw = os.getenv("ODRIVE_API_TOKEN", "").strip()
        api_token = api_token_raw or None
        cors_allowed_origins = _parse_cors_allowed_origins(os.getenv("ODRIVE_API_CORS_ALLOWED_ORIGINS", "*"))

        if max_paths_per_request <= 0:
            raise ValueError("ODRIVE_API_MAX_PATHS_PER_REQUEST must be > 0")
        if max_write_items <= 0:
            raise ValueError("ODRIVE_API_MAX_WRITE_ITEMS must be > 0")
        if request_timeout_s <= 0:
            raise ValueError("ODRIVE_API_REQUEST_TIMEOUT_S must be > 0")
        if float_abs_tol < 0:
            raise ValueError("ODRIVE_API_FLOAT_ABS_TOL must be >= 0")
        if float_rel_tol < 0:
            raise ValueError("ODRIVE_API_FLOAT_REL_TOL must be >= 0")

        return cls(
            can_iface=can_iface,
            can_bustype=can_bustype,
            endpoints_json=endpoints_json,
            allowed_node_ids=allowed_node_ids,
            request_timeout_s=request_timeout_s,
            max_paths_per_request=max_paths_per_request,
            max_write_items=max_write_items,
            float_abs_tol=float_abs_tol,
            float_rel_tol=float_rel_tol,
            api_token=api_token,
            cors_allowed_origins=cors_allowed_origins,
        )

    def is_node_allowed(self, node_id: int) -> bool:
        return int(node_id) in self.allowed_node_ids


def _parse_node_ids(raw: str) -> tuple[int, ...]:
    raw = raw.strip()
    if not raw:
        return tuple(DEFAULT_ALLOWED_NODE_IDS)

    parsed: list[int] = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        node_id = int(value)
        if node_id < 0:
            raise ValueError("ODRIVE_API_ALLOWED_NODE_IDS must contain non-negative ints")
        parsed.append(node_id)

    if not parsed:
        raise ValueError("ODRIVE_API_ALLOWED_NODE_IDS must not be empty")
    return tuple(parsed)


def _parse_cors_allowed_origins(raw: str) -> tuple[str, ...]:
    normalized = str(raw or "").strip()
    if not normalized:
        return tuple()

    parsed: list[str] = []
    for part in normalized.split(","):
        origin = part.strip()
        if not origin:
            continue
        if origin not in parsed:
            parsed.append(origin)
    return tuple(parsed)
