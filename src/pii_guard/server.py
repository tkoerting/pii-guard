"""HTTP API Server für Docker-basiertes PII Guard Backend.

Läuft als Daemon im Container, empfängt Prompts per HTTP und gibt
Hook-Entscheidungen zurück. Nutzt process_prompt() aus hook.py.

Starten: python -m pii_guard.server [--port 7437] [--config /pfad/config.yaml]
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import pii_guard
from pii_guard.config import load_config
from pii_guard.hook import process_prompt

log = logging.getLogger("pii_guard.server")

_lock = threading.Lock()


class PiiGuardHandler(BaseHTTPRequestHandler):
    """HTTP Handler für PII Guard API."""

    config: dict = {}

    def do_POST(self) -> None:
        if self.path == "/process":
            self._handle_process()
        else:
            self.send_error(404)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._handle_health()
        else:
            self.send_error(404)

    def _handle_process(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self.send_error(400, "Content-Length fehlt oder ist 0")
                return
            body = self.rfile.read(length)
            data = json.loads(body)
            prompt = data.get("prompt", "")

            if not prompt:
                self._send_json({"decision": "allow"})
                return

            with _lock:
                result = process_prompt(prompt, self.config)

            self._send_json(result)

        except Exception as e:
            log.error("Fehler bei /process: %s", e)
            self._send_json({"decision": "allow"}, status=500)

    def _handle_health(self) -> None:
        self._send_json({
            "status": "ok",
            "version": pii_guard.__version__,
        })

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Umleitung des HTTP-Logs auf Python logging."""
        log.debug(format, *args)


def run_server(
    host: str = "0.0.0.0",
    port: int = 7437,
    config_path: str | None = None,
) -> None:
    """Startet den PII Guard HTTP-Server."""
    config = load_config(Path(config_path) if config_path else None)
    PiiGuardHandler.config = config

    # Engine-Warmup: spaCy-Modell vorladen damit der erste Request schnell ist
    log.info("Engine-Warmup startet...")
    from pii_guard.detector import _get_engine
    _get_engine(config)
    log.info("Engine-Warmup abgeschlossen")

    server = HTTPServer((host, port), PiiGuardHandler)
    server.daemon_threads = True
    log.info("PII Guard Server gestartet auf %s:%d", host, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Server wird beendet")
        server.shutdown()


def main() -> None:
    """Entry point: python -m pii_guard.server"""
    import argparse

    parser = argparse.ArgumentParser(description="PII Guard HTTP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind-Adresse (Default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7437, help="Port (Default: 7437)")
    parser.add_argument("--config", dest="config_path", help="Pfad zur Config-Datei")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    run_server(host=args.host, port=args.port, config_path=args.config_path)


if __name__ == "__main__":
    main()
