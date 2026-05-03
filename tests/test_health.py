"""Smoke test for app.health.start_health_server."""
import json
import socket
import time
import urllib.request

from app.health import start_health_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_health_endpoint_returns_ok():
    port = _free_port()
    server, _thread = start_health_server(port=port)
    try:
        # daemon thread already serving — give it a tick
        deadline = time.time() + 2.0
        last_err = None
        while time.time() < deadline:
            try:
                resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.0)
                break
            except Exception as e:  # connection refused before server is ready
                last_err = e
                time.sleep(0.05)
        else:
            raise AssertionError(f"Health server never came up: {last_err}")

        assert resp.status == 200
        body = json.loads(resp.read().decode())
        assert body == {"status": "ok"}
    finally:
        server.shutdown()
        server.server_close()


def test_health_endpoint_returns_404_on_unknown_path():
    port = _free_port()
    server, _thread = start_health_server(port=port)
    try:
        time.sleep(0.05)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=1.0)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
        server.server_close()
