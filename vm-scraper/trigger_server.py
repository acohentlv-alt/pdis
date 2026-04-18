"""
Minimal HTTP trigger daemon for the PDIS Yad2 VM scraper.
Binds 0.0.0.0:8787.

Endpoints:
  POST /trigger  — start the Yad2 scraper subprocess
  GET  /status   — {"running": bool}

Auth: Bearer token from TRIGGER_SECRET env var.
Rate limit: 10-minute cooldown between successful triggers (in-memory).
All requests logged to /var/log/pdis-yad2-manual.log.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import os
import subprocess
import sys
import threading
import time

# ── Config ────────────────────────────────────────────────────────────────────

PORT = 8787
SCRAPER_SCRIPT = "/opt/pdis-yad2-scraper/run_yad2.py"
LOG_FILE = "/var/log/pdis-yad2-manual.log"
COOLDOWN_SECONDS = 600  # 10 minutes

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("trigger_server")

# ── Global state ──────────────────────────────────────────────────────────────

_lock = threading.Lock()
_subprocess: "subprocess.Popen | None" = None
_last_trigger_time: float = 0.0  # epoch seconds of last accepted trigger


def _is_running() -> bool:
    global _subprocess
    with _lock:
        if _subprocess is None:
            return False
        if _subprocess.poll() is None:
            return True
        _subprocess = None
        return False


def _start_subprocess() -> None:
    global _subprocess, _last_trigger_time
    python = sys.executable
    with open(LOG_FILE, "a") as log_fh:
        proc = subprocess.Popen(
            [python, SCRAPER_SCRIPT],
            stdout=log_fh,
            stderr=log_fh,
            env=os.environ.copy(),
        )
    with _lock:
        _subprocess = proc
        _last_trigger_time = time.time()
    log.info(f"subprocess started pid={proc.pid}")


def _run_in_thread() -> None:
    """Wrapper run in a daemon thread so POST /trigger returns immediately."""
    try:
        _start_subprocess()
    except Exception as exc:
        log.error(f"failed to start subprocess: {exc}")


# ── Auth ──────────────────────────────────────────────────────────────────────

TRIGGER_SECRET = os.environ.get("TRIGGER_SECRET", "")


def _check_auth(handler: "BaseHTTPRequestHandler") -> bool:
    auth = handler.headers.get("Authorization", "")
    if not TRIGGER_SECRET:
        log.warning("TRIGGER_SECRET not set — rejecting all requests")
        return False
    return auth == f"Bearer {TRIGGER_SECRET}"


# ── Handler ───────────────────────────────────────────────────────────────────

class TriggerHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # silence default access log
        pass

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _log_request(self, auth_ok: bool, result_status: int, note: str = "") -> None:
        client_ip = self.client_address[0]
        log.info(
            f"request ip={client_ip} path={self.path} method={self.command} "
            f"auth_ok={auth_ok} result={result_status}{' ' + note if note else ''}"
        )

    def do_GET(self):
        if self.path != "/status":
            self._log_request(False, 404, "wrong path")
            self._send_json(404, {"error": "not found"})
            return
        running = _is_running()
        self._log_request(True, 200)
        self._send_json(200, {"running": running})

    def do_POST(self):
        if self.path != "/trigger":
            self._log_request(False, 404, "wrong path")
            self._send_json(404, {"error": "not found"})
            return

        auth_ok = _check_auth(self)
        if not auth_ok:
            self._log_request(False, 403, "bad bearer")
            self._send_json(403, {"error": "forbidden"})
            return

        if _is_running():
            self._log_request(True, 409, "already_running")
            self._send_json(409, {"error": "already_running"})
            return

        with _lock:
            elapsed = time.time() - _last_trigger_time
        if elapsed < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - elapsed)
            self._log_request(True, 429, f"rate_limited cooldown_remaining={remaining}s")
            self._send_json(429, {"error": "rate_limited", "retry_after_seconds": remaining})
            return

        t = threading.Thread(target=_run_in_thread, daemon=True)
        t.start()

        self._log_request(True, 202, "started")
        self._send_json(202, {"status": "started"})


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TRIGGER_SECRET:
        log.warning("WARNING: TRIGGER_SECRET env var not set — all POST /trigger requests will be rejected")

    server = HTTPServer(("0.0.0.0", PORT), TriggerHandler)
    log.info(f"PDIS Yad2 trigger server listening on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
