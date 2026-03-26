from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
from time import perf_counter
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from odrive_api.config import ODriveApiSettings
from odrive_api.models import (
    HealthResponse,
    NodeActionResponse,
    NodesResponse,
    ReadSettingsResponse,
    WriteSettingsRequest,
    WriteSettingsResponse,
)
from odrive_api.services.odrive_service import ODriveService, ReadbackMismatchError


logger = logging.getLogger("odrive_api")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_paths(paths: str) -> list[str]:
    parsed = [item.strip() for item in str(paths).split(",") if item.strip()]
    if not parsed:
        raise ValueError("Query parameter 'paths' must include at least one endpoint path")
    return parsed


def _error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _raise_api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=_error_detail(code, message))


def _extract_api_token(authorization_header: str | None, x_api_key_header: str | None) -> str | None:
    if x_api_key_header:
        token = x_api_key_header.strip()
        return token or None

    if not authorization_header:
        return None

    raw = authorization_header.strip()
    bearer_prefix = "bearer "
    if raw.lower().startswith(bearer_prefix):
        token = raw[len(bearer_prefix) :].strip()
        return token or None
    return None


def _log_operation(
    operation: str,
    *,
    success: bool,
    status_code: int,
    start_s: float,
    node_id: int | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "event": "odrive_api_operation",
        "operation": operation,
        "success": success,
        "status_code": status_code,
        "duration_ms": round((perf_counter() - start_s) * 1000.0, 3),
    }
    if node_id is not None:
        payload["node_id"] = int(node_id)
    if error_code is not None:
        payload["error_code"] = error_code
    if error_message is not None:
        payload["error_message"] = error_message
    payload.update(fields)

    level = logging.INFO
    if not success and status_code >= 500:
        level = logging.ERROR
    elif not success:
        level = logging.WARNING

    logger.log(level, json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _authorize_or_raise(
    *,
    expected_token: str | None,
    operation: str,
    start_s: float,
    authorization_header: str | None,
    x_api_key_header: str | None,
    node_id: int | None = None,
) -> None:
    if expected_token is None:
        return

    provided_token = _extract_api_token(authorization_header, x_api_key_header)
    if provided_token is None:
        message = "Missing API token"
        _log_operation(
            operation,
            success=False,
            status_code=401,
            start_s=start_s,
            node_id=node_id,
            error_code="ODRIVE_AUTH_REQUIRED",
            error_message=message,
        )
        raise _raise_api_error(401, "ODRIVE_AUTH_REQUIRED", message)

    if provided_token != expected_token:
        message = "Invalid API token"
        _log_operation(
            operation,
            success=False,
            status_code=403,
            start_s=start_s,
            node_id=node_id,
            error_code="ODRIVE_AUTH_INVALID",
            error_message=message,
        )
        raise _raise_api_error(403, "ODRIVE_AUTH_INVALID", message)


def create_app(settings: ODriveApiSettings | None = None, service: ODriveService | None = None) -> FastAPI:
    resolved_settings = settings or ODriveApiSettings.from_env()
    resolved_service = service or ODriveService(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved_service.start()
        app.state.odrive_service = resolved_service
        try:
            yield
        finally:
            resolved_service.stop()

    app = FastAPI(title="odrive-api", version="0.1.0", lifespan=lifespan)
    if resolved_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_allowed_origins),
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
            allow_credentials=False,
        )

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "service": "odrive-api",
            "status": "ok" if resolved_service.started else "degraded",
            "timestamp": _utcnow_iso(),
        }

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        snapshot = resolved_service.snapshot()
        return HealthResponse(
            service="odrive-api",
            status="ok" if snapshot["started"] else "degraded",
            started=bool(snapshot["started"]),
            can_iface=str(snapshot["can_iface"]),
            can_bustype=str(snapshot["can_bustype"]),
            endpoints_json=str(snapshot["endpoints_json"]),
            allowed_node_ids=list(snapshot["allowed_node_ids"]),
        )

    @app.get("/api/v1/odrive/nodes", response_model=NodesResponse)
    def list_nodes(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> NodesResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="list_nodes",
            start_s=started,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        try:
            payload = NodesResponse(nodes=resolved_service.list_nodes())
        except RuntimeError as err:
            message = str(err)
            _log_operation(
                "list_nodes",
                success=False,
                status_code=503,
                start_s=started,
                error_code="ODRIVE_SERVICE_UNAVAILABLE",
                error_message=message,
            )
            raise _raise_api_error(503, "ODRIVE_SERVICE_UNAVAILABLE", message) from err
        except Exception as err:
            message = f"Failed to list nodes: {err}"
            _log_operation(
                "list_nodes",
                success=False,
                status_code=500,
                start_s=started,
                error_code="ODRIVE_INTERNAL_ERROR",
                error_message=message,
            )
            raise _raise_api_error(500, "ODRIVE_INTERNAL_ERROR", message) from err

        _log_operation("list_nodes", success=True, status_code=200, start_s=started, node_count=len(payload.nodes))
        return payload

    @app.get("/api/v1/odrive/nodes/{node_id}/settings", response_model=ReadSettingsResponse)
    def read_settings(
        node_id: int,
        paths: str = Query(..., description="Comma-separated endpoint paths"),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> ReadSettingsResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="read_settings",
            start_s=started,
            node_id=node_id,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        try:
            parsed_paths = _parse_paths(paths)
            values = resolved_service.read_many(node_id=node_id, paths=parsed_paths)
        except ValueError as err:
            message = str(err)
            _log_operation(
                "read_settings",
                success=False,
                status_code=400,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_INVALID_REQUEST",
                error_message=message,
            )
            raise _raise_api_error(400, "ODRIVE_INVALID_REQUEST", message) from err
        except PermissionError as err:
            message = str(err)
            _log_operation(
                "read_settings",
                success=False,
                status_code=403,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_NODE_NOT_ALLOWED",
                error_message=message,
            )
            raise _raise_api_error(403, "ODRIVE_NODE_NOT_ALLOWED", message) from err
        except KeyError as err:
            message = str(err)
            _log_operation(
                "read_settings",
                success=False,
                status_code=400,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_UNKNOWN_ENDPOINT",
                error_message=message,
            )
            raise _raise_api_error(400, "ODRIVE_UNKNOWN_ENDPOINT", message) from err
        except TimeoutError as err:
            message = str(err)
            _log_operation(
                "read_settings",
                success=False,
                status_code=504,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_READ_TIMEOUT",
                error_message=message,
            )
            raise _raise_api_error(504, "ODRIVE_READ_TIMEOUT", message) from err
        except RuntimeError as err:
            message = str(err)
            _log_operation(
                "read_settings",
                success=False,
                status_code=503,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_SERVICE_UNAVAILABLE",
                error_message=message,
            )
            raise _raise_api_error(503, "ODRIVE_SERVICE_UNAVAILABLE", message) from err
        except Exception as err:
            message = f"Failed to read settings: {err}"
            _log_operation(
                "read_settings",
                success=False,
                status_code=500,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_INTERNAL_ERROR",
                error_message=message,
            )
            raise _raise_api_error(500, "ODRIVE_INTERNAL_ERROR", message) from err

        _log_operation(
            "read_settings",
            success=True,
            status_code=200,
            start_s=started,
            node_id=node_id,
            path_count=len(parsed_paths),
        )
        return ReadSettingsResponse(node_id=node_id, values=values)

    @app.post("/api/v1/odrive/nodes/{node_id}/settings", response_model=WriteSettingsResponse)
    def write_settings(
        node_id: int,
        request: WriteSettingsRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> WriteSettingsResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="write_settings",
            start_s=started,
            node_id=node_id,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        if not request.values:
            message = "Request body 'values' must include at least one entry"
            _log_operation(
                "write_settings",
                success=False,
                status_code=400,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_INVALID_REQUEST",
                error_message=message,
            )
            raise _raise_api_error(400, "ODRIVE_INVALID_REQUEST", message)

        try:
            readback_values = resolved_service.write_many(
                node_id=node_id,
                values=request.values,
                verify_readback=bool(request.verify_readback),
                readback_timeout_s=request.readback_timeout_s,
            )
        except PermissionError as err:
            message = str(err)
            _log_operation(
                "write_settings",
                success=False,
                status_code=403,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_NODE_NOT_ALLOWED",
                error_message=message,
                verify_readback=bool(request.verify_readback),
            )
            raise _raise_api_error(403, "ODRIVE_NODE_NOT_ALLOWED", message) from err
        except ReadbackMismatchError as err:
            message = str(err)
            _log_operation(
                "write_settings",
                success=False,
                status_code=409,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_READBACK_MISMATCH",
                error_message=message,
                verify_readback=bool(request.verify_readback),
            )
            raise _raise_api_error(409, "ODRIVE_READBACK_MISMATCH", message) from err
        except TimeoutError as err:
            message = str(err)
            _log_operation(
                "write_settings",
                success=False,
                status_code=504,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_WRITE_TIMEOUT",
                error_message=message,
                verify_readback=bool(request.verify_readback),
            )
            raise _raise_api_error(504, "ODRIVE_WRITE_TIMEOUT", message) from err
        except KeyError as err:
            message = str(err)
            _log_operation(
                "write_settings",
                success=False,
                status_code=400,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_UNKNOWN_ENDPOINT",
                error_message=message,
                verify_readback=bool(request.verify_readback),
            )
            raise _raise_api_error(400, "ODRIVE_UNKNOWN_ENDPOINT", message) from err
        except (TypeError, ValueError) as err:
            message = f"Invalid setting value: {err}"
            _log_operation(
                "write_settings",
                success=False,
                status_code=400,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_INVALID_VALUE",
                error_message=message,
                verify_readback=bool(request.verify_readback),
            )
            raise _raise_api_error(400, "ODRIVE_INVALID_VALUE", message) from err
        except RuntimeError as err:
            message = str(err)
            _log_operation(
                "write_settings",
                success=False,
                status_code=503,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_SERVICE_UNAVAILABLE",
                error_message=message,
                verify_readback=bool(request.verify_readback),
            )
            raise _raise_api_error(503, "ODRIVE_SERVICE_UNAVAILABLE", message) from err
        except Exception as err:
            message = f"Failed to write settings: {err}"
            _log_operation(
                "write_settings",
                success=False,
                status_code=500,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_INTERNAL_ERROR",
                error_message=message,
                verify_readback=bool(request.verify_readback),
            )
            raise _raise_api_error(500, "ODRIVE_INTERNAL_ERROR", message) from err

        _log_operation(
            "write_settings",
            success=True,
            status_code=200,
            start_s=started,
            node_id=node_id,
            write_count=len(request.values),
            verify_readback=bool(request.verify_readback),
        )
        return WriteSettingsResponse(
            node_id=node_id,
            written=list(request.values.keys()),
            verified=bool(request.verify_readback),
            readback_values=readback_values,
        )

    @app.post("/api/v1/odrive/nodes/{node_id}/save", response_model=NodeActionResponse)
    def save_configuration(
        node_id: int,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> NodeActionResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="save_configuration",
            start_s=started,
            node_id=node_id,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        try:
            resolved_service.save_configuration(node_id=node_id)
        except PermissionError as err:
            message = str(err)
            _log_operation(
                "save_configuration",
                success=False,
                status_code=403,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_NODE_NOT_ALLOWED",
                error_message=message,
            )
            raise _raise_api_error(403, "ODRIVE_NODE_NOT_ALLOWED", message) from err
        except RuntimeError as err:
            message = str(err)
            _log_operation(
                "save_configuration",
                success=False,
                status_code=503,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_SERVICE_UNAVAILABLE",
                error_message=message,
            )
            raise _raise_api_error(503, "ODRIVE_SERVICE_UNAVAILABLE", message) from err
        except Exception as err:
            message = f"Failed to save settings: {err}"
            _log_operation(
                "save_configuration",
                success=False,
                status_code=500,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_INTERNAL_ERROR",
                error_message=message,
            )
            raise _raise_api_error(500, "ODRIVE_INTERNAL_ERROR", message) from err

        _log_operation("save_configuration", success=True, status_code=200, start_s=started, node_id=node_id)
        return NodeActionResponse(node_id=node_id, action="save", status="ok")

    @app.post("/api/v1/odrive/nodes/{node_id}/reboot", response_model=NodeActionResponse)
    def reboot(
        node_id: int,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> NodeActionResponse:
        started = perf_counter()
        _authorize_or_raise(
            expected_token=resolved_settings.api_token,
            operation="reboot",
            start_s=started,
            node_id=node_id,
            authorization_header=authorization,
            x_api_key_header=x_api_key,
        )
        try:
            resolved_service.reboot(node_id=node_id)
        except PermissionError as err:
            message = str(err)
            _log_operation(
                "reboot",
                success=False,
                status_code=403,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_NODE_NOT_ALLOWED",
                error_message=message,
            )
            raise _raise_api_error(403, "ODRIVE_NODE_NOT_ALLOWED", message) from err
        except RuntimeError as err:
            message = str(err)
            _log_operation(
                "reboot",
                success=False,
                status_code=503,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_SERVICE_UNAVAILABLE",
                error_message=message,
            )
            raise _raise_api_error(503, "ODRIVE_SERVICE_UNAVAILABLE", message) from err
        except Exception as err:
            message = f"Failed to reboot node: {err}"
            _log_operation(
                "reboot",
                success=False,
                status_code=500,
                start_s=started,
                node_id=node_id,
                error_code="ODRIVE_INTERNAL_ERROR",
                error_message=message,
            )
            raise _raise_api_error(500, "ODRIVE_INTERNAL_ERROR", message) from err

        _log_operation("reboot", success=True, status_code=200, start_s=started, node_id=node_id)
        return NodeActionResponse(node_id=node_id, action="reboot", status="ok")

    return app


app = create_app()
