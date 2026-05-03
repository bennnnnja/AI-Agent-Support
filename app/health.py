"""Minimal HTTP health endpoint for liveness probes (Docker/k8s).

Runs in a daemon thread alongside the main event loop. No external deps
beyond stdlib. Always returns 200 — the agent is alive as long as the
Python process is up.
"""
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — required name
        if self.path in ("/health", "/healthz", "/"):
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
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
