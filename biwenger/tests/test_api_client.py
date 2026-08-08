"""Tests del cliente HTTP (offline, con httpx.MockTransport). Sin red real."""

from __future__ import annotations

import time

import httpx
import pytest

from biwenger.api.client import BiwengerAPIError, BiwengerClient, DiskCache
from biwenger.config import Settings


def make_settings(tmp_path, **overrides) -> Settings:
    base = dict(
        email="a@b.com",
        password="secret",
        user_id="42",
        league_id="99",
        version="1.2.3",
        min_request_interval=0.0,
        cache_ttl=0,
        max_retries=3,
        database_url=f"sqlite:///{tmp_path}/t.db",
    )
    base.update(overrides)
    return Settings(**base)


def client_with(tmp_path, handler, **overrides) -> BiwengerClient:
    settings = make_settings(tmp_path, **overrides)
    return BiwengerClient(
        settings,
        transport=httpx.MockTransport(handler),
        cache=DiskCache(tmp_path / ".cache", settings.cache_ttl),
    )


def test_headers_include_captured_values(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json={"data": {"players": {}}})

    with client_with(tmp_path, handler) as client:
        client.get_competition_data("sofascore")

    assert captured["x-user"] == "42"
    assert captured["x-league"] == "99"
    assert captured["x-version"] == "1.2.3"


def test_get_json_returns_parsed_body(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    with client_with(tmp_path, handler) as client:
        assert client.get_json("https://x/y", use_cache=False) == {"hello": "world"}


def test_retry_on_500_then_success(tmp_path):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="boom")
        return httpx.Response(200, json={"ok": True})

    # min de espera del backoff es 2s; forzamos que tenacity no duerma de verdad
    with client_with(tmp_path, handler, max_retries=5) as client:
        # parcheamos time.sleep para no ralentizar el test
        import biwenger.api.client as mod

        orig = mod.time.sleep
        mod.time.sleep = lambda *_: None
        try:
            data = client.get_json("https://x/y", use_cache=False)
        finally:
            mod.time.sleep = orig
    assert data == {"ok": True}
    assert calls["n"] == 3


def test_4xx_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")

    with client_with(tmp_path, handler) as client:
        with pytest.raises(BiwengerAPIError):
            client.get_json("https://x/y", use_cache=False)


def test_401_raises_helpful_error(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    with client_with(tmp_path, handler) as client:
        with pytest.raises(BiwengerAPIError, match="401"):
            client.get_json("https://x/y", use_cache=False)


def test_login_stores_token(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/auth/login")
        return httpx.Response(200, json={"token": "TOK123"})

    with client_with(tmp_path, handler) as client:
        token = client.login()
    assert token == "TOK123"


def test_login_missing_credentials_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, json={})

    with client_with(tmp_path, handler, email="", password="") as client:
        with pytest.raises(BiwengerAPIError, match="credenciales"):
            client.login()


def test_cache_hit_avoids_second_request(tmp_path):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"v": calls["n"]})

    # ttl grande para que la caché sea válida
    with client_with(tmp_path, handler, cache_ttl=3600) as client:
        first = client.get_json("https://x/cacheme", use_cache=True)
        second = client.get_json("https://x/cacheme", use_cache=True)
    assert first == second == {"v": 1}
    assert calls["n"] == 1  # el segundo salió de caché


def test_throttle_enforces_interval(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with client_with(tmp_path, handler, min_request_interval=0.15) as client:
        start = time.time()
        client.get_json("https://x/1", use_cache=False)
        client.get_json("https://x/2", use_cache=False)
        elapsed = time.time() - start
    assert elapsed >= 0.15
