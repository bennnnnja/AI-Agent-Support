"""Smoke tests for app.health.start_health_server with real Redis ping."""
import json
import socket
import time
import urllib.request
import urllib.error
from unittest.mock import patch, MagicMock

from app.health import start_health_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_serving(port: int, deadline_seconds: float = 2.0) -> None:
    deadline = time.time() + deadline_seconds
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            s.close()
            return
        except OSError as e:
            last_err = e
            time.sleep(0.02)
    raise AssertionError(f"Health server never came up on :{port}: {last_err}")


def test_health_endpoint_returns_ok_when_redis_pings():
    fake_client = MagicMock()
    fake_client.ping.return_value = True
    with patch("app.services.redis_consumer.get_redis_client", return_value=fake_client):
        port = _free_port()
        server, _thread = start_health_server(port=port)
        try:
            _wait_until_serving(port)
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.0)
            assert resp.status == 200
            body = json.loads(resp.read().decode())
            assert body["status"] == "ok"
            assert body["redis"] == "ok"
        finally:
            server.shutdown()
            server.server_close()


def test_health_endpoint_returns_503_when_redis_down():
    fake_client = MagicMock()
    fake_client.ping.side_effect = ConnectionError("redis unreachable")
    with patch("app.services.redis_consumer.get_redis_client", return_value=fake_client):
        port = _free_port()
        server, _thread = start_health_server(port=port)
        try:
            _wait_until_serving(port)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.0)
                raise AssertionError("expected 503")
            except urllib.error.HTTPError as e:
                assert e.code == 503
                body = json.loads(e.read().decode())
                assert body["status"] == "degraded"
                assert "ConnectionError" in body["redis"]
        finally:
            server.shutdown()
            server.server_close()


def test_health_endpoint_returns_404_on_unknown_path():
    fake_client = MagicMock()
    fake_client.ping.return_value = True
    with patch("app.services.redis_consumer.get_redis_client", return_value=fake_client):
        port = _free_port()
        server, _thread = start_health_server(port=port)
        try:
            _wait_until_serving(port)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=1.0)
                raise AssertionError("expected 404")
            except urllib.error.HTTPError as e:
                assert e.code == 404
        finally:
            server.shutdown()
            server.server_close()
