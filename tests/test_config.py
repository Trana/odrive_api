import pytest

from odrive_api.config import ODriveApiSettings


def test_settings_from_env_defaults(monkeypatch):
    monkeypatch.delenv("ODRIVE_API_CAN_IFACE", raising=False)
    monkeypatch.delenv("ODRIVE_API_CAN_BUSTYPE", raising=False)
    monkeypatch.delenv("ODRIVE_API_ENDPOINTS_JSON", raising=False)
    monkeypatch.delenv("ODRIVE_API_ALLOWED_NODE_IDS", raising=False)
    monkeypatch.delenv("ODRIVE_API_REQUEST_TIMEOUT_S", raising=False)
    monkeypatch.delenv("ODRIVE_API_MAX_PATHS_PER_REQUEST", raising=False)
    monkeypatch.delenv("ODRIVE_API_MAX_WRITE_ITEMS", raising=False)
    monkeypatch.delenv("ODRIVE_API_FLOAT_ABS_TOL", raising=False)
    monkeypatch.delenv("ODRIVE_API_FLOAT_REL_TOL", raising=False)
    monkeypatch.delenv("ODRIVE_API_TOKEN", raising=False)
    monkeypatch.delenv("ODRIVE_API_CORS_ALLOWED_ORIGINS", raising=False)

    settings = ODriveApiSettings.from_env()

    assert settings.can_iface == "can0"
    assert settings.can_bustype == "socketcan"
    assert str(settings.endpoints_json) == "flat_endpoints.json"
    assert 11 in settings.allowed_node_ids
    assert settings.request_timeout_s == 0.25
    assert settings.max_paths_per_request == 64
    assert settings.max_write_items == 32
    assert settings.float_abs_tol == 1e-5
    assert settings.float_rel_tol == 1e-5
    assert settings.api_token is None
    assert settings.cors_allowed_origins == ("*",)


def test_settings_from_env_custom(monkeypatch):
    monkeypatch.setenv("ODRIVE_API_CAN_IFACE", "can9")
    monkeypatch.setenv("ODRIVE_API_CAN_BUSTYPE", "socketcan")
    monkeypatch.setenv("ODRIVE_API_ENDPOINTS_JSON", "/tmp/endpoints.json")
    monkeypatch.setenv("ODRIVE_API_ALLOWED_NODE_IDS", "7,8,9")
    monkeypatch.setenv("ODRIVE_API_REQUEST_TIMEOUT_S", "1.75")
    monkeypatch.setenv("ODRIVE_API_MAX_PATHS_PER_REQUEST", "99")
    monkeypatch.setenv("ODRIVE_API_MAX_WRITE_ITEMS", "12")
    monkeypatch.setenv("ODRIVE_API_FLOAT_ABS_TOL", "0.0001")
    monkeypatch.setenv("ODRIVE_API_FLOAT_REL_TOL", "0.0002")
    monkeypatch.setenv("ODRIVE_API_TOKEN", "supersecret")
    monkeypatch.setenv("ODRIVE_API_CORS_ALLOWED_ORIGINS", "https://ui.local,http://127.0.0.1:3000")

    settings = ODriveApiSettings.from_env()

    assert settings.can_iface == "can9"
    assert settings.allowed_node_ids == (7, 8, 9)
    assert settings.is_node_allowed(8)
    assert not settings.is_node_allowed(11)
    assert settings.request_timeout_s == 1.75
    assert settings.max_paths_per_request == 99
    assert settings.max_write_items == 12
    assert settings.float_abs_tol == 0.0001
    assert settings.float_rel_tol == 0.0002
    assert settings.api_token == "supersecret"
    assert settings.cors_allowed_origins == ("https://ui.local", "http://127.0.0.1:3000")


def test_settings_disable_cors_with_empty_env(monkeypatch):
    monkeypatch.setenv("ODRIVE_API_CORS_ALLOWED_ORIGINS", "")
    settings = ODriveApiSettings.from_env()
    assert settings.cors_allowed_origins == ()


def test_settings_invalid_limits_raise(monkeypatch):
    monkeypatch.setenv("ODRIVE_API_MAX_PATHS_PER_REQUEST", "0")
    with pytest.raises(ValueError):
        ODriveApiSettings.from_env()

    monkeypatch.setenv("ODRIVE_API_MAX_PATHS_PER_REQUEST", "64")
    monkeypatch.setenv("ODRIVE_API_MAX_WRITE_ITEMS", "0")
    with pytest.raises(ValueError):
        ODriveApiSettings.from_env()

    monkeypatch.setenv("ODRIVE_API_MAX_WRITE_ITEMS", "32")
    monkeypatch.setenv("ODRIVE_API_REQUEST_TIMEOUT_S", "0")
    with pytest.raises(ValueError):
        ODriveApiSettings.from_env()
