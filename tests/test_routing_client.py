from __future__ import annotations

import requests
import pytest

from config import RoutingSettings
from models import Location
from routing_client import NoRouteError, OSRMRoutingClient, RateLimitError, RoutingCache, RoutingError


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def locations():
    return [
        Location("START", "Start", "", 8.475, 124.645),
        Location("A", "A", "", 8.48, 124.63),
    ]


def client(tmp_path):
    return OSRMRoutingClient(
        RoutingSettings(base_url="https://example.test", retry_count=0, request_delay_seconds=0),
        RoutingCache(tmp_path / "cache.sqlite3"),
    )


def test_successful_table_response_parsed(tmp_path, monkeypatch):
    c = client(tmp_path)
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return FakeResponse(200, {"code": "Ok", "distances": [[0, 1200], [1300, 0]], "durations": [[0, 300], [330, 0]]})

    monkeypatch.setattr(c.session, "get", fake_get)
    matrix, cache_hit = c.table(locations())
    assert not cache_hit
    assert matrix[("START", "A")].distance_km == 1.2
    assert matrix[("A", "START")].duration_minutes == 5.5
    matrix2, cache_hit2 = c.table(locations())
    assert cache_hit2
    assert calls["count"] == 1
    assert matrix2[("START", "A")].from_cache


def test_http_error_handled(tmp_path, monkeypatch):
    c = client(tmp_path)
    monkeypatch.setattr(c.session, "get", lambda *a, **k: FakeResponse(400, {}))
    with pytest.raises(RoutingError):
        c.table(locations())


def test_timeout_handled(tmp_path, monkeypatch):
    c = client(tmp_path)

    def raise_timeout(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(c.session, "get", raise_timeout)
    with pytest.raises(RoutingError):
        c.table(locations())


def test_invalid_schema_handled(tmp_path, monkeypatch):
    c = client(tmp_path)
    monkeypatch.setattr(c.session, "get", lambda *a, **k: FakeResponse(200, {"code": "Ok"}))
    with pytest.raises(RoutingError):
        c.table(locations())


def test_no_route_response_handled(tmp_path, monkeypatch):
    c = client(tmp_path)
    monkeypatch.setattr(c.session, "get", lambda *a, **k: FakeResponse(200, {"code": "NoRoute"}))
    with pytest.raises(NoRouteError):
        c.table(locations())


def test_rate_limit_response_handled(tmp_path, monkeypatch):
    c = client(tmp_path)
    monkeypatch.setattr(c.session, "get", lambda *a, **k: FakeResponse(429, {}))
    with pytest.raises(RateLimitError):
        c.table(locations())
