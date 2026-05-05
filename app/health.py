"""Minimal HTTP health endpoint for liveness/readiness probes (Docker/k8s).

Runs in a daemon thread alongside the main event loop. No external deps
beyond stdlib + redis. Returns 200 only when Redis is reachable — that
is the agent's single hard dependency. Loss of Redis means the agent
cannot consume events, so k8s/Docker should restart the container.
"""
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


def _check_redis() -> tuple[bool, str]:
    try:
        from app.services.redis_consumer import get_redis_client
        client = get_redis_client()
        client.ping()
        return True, "ok"
    except Exception as e:
        # Truncate to keep response body small and avoid leaking creds in URL
        return False, type(e).__name__ + ": " + str(e)[:120]


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — required name
        if self.path in ("/health", "/healthz", "/"):
            ok, redis_detail = _check_redis()
            payload = {
                "status": "ok" if ok else "degraded",
                "redis": redis_detail,
            }
            body = json.dumps(payload).encode()
            status = 200 if ok else 503
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args, **kwargs):  # silence default access log
        return


def start_health_server(port: int | None = None) -> tuple[HTTPServer, threading.Thread]:
    """Start health HTTP server in a daemon thread. Returns (server, thread)."""
    if port is None:
        port = int(os.environ.get("HEALTH_PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, name="health", daemon=True)
    thread.start()
    logger.info("[HEALTH] Listening on :%d", port)
    return server, thread
