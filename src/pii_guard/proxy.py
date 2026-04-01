# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""Transparenter API-Proxy mit bidirektionalem PII-Mapping.

Läuft lokal zwischen Claude Code und der Anthropic API.
Maskiert PII im Prompt, leitet weiter, mappt die Antwort zurück.

Starten: python -m pii_guard.proxy [--port 7438]
Nutzen:  ANTHROPIC_BASE_URL=http://localhost:7438 claude

Architektur:
  Claude Code → localhost:7438 → PII Guard Proxy → api.anthropic.com
       ↑                              ↓
       └── Antwort (PII zurückgemappt) ←── Antwort (mit Fake-Daten)
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pii_guard
from pii_guard.audit import log_event, log_findings
from pii_guard.config import load_config
from pii_guard.detector import detect_pii
from pii_guard.mapper import SessionMapper
from pii_guard.substitutor import substitute_pii

log = logging.getLogger("pii_guard.proxy")

_lock = threading.Lock()

# Anthropic API Basis-URL
_ANTHROPIC_API = "https://api.anthropic.com"

# Header die NICHT weitergeleitet werden
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade", "host",
}


class ProxyHandler(BaseHTTPRequestHandler):
    """Transparenter Proxy mit PII-Maskierung."""

    config: dict = {}

    def do_POST(self) -> None:
        """POST-Requests an die Anthropic API weiterleiten."""
        if self.path == "/health":
            self._handle_health()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            data = json.loads(body) if body else {}

            # Streaming deaktivieren (Proxy mappt die komplette Antwort)
            data["stream"] = False

            # PII in Messages maskieren
            session_id = str(uuid4())
            mapper = SessionMapper(self.config)
            data = self._mask_messages(data, mapper, session_id)

            # Request an Anthropic API weiterleiten
            upstream_body = json.dumps(data).encode("utf-8")
            upstream_url = f"{_ANTHROPIC_API}{self.path}"

            headers = {}
            for key, value in self.headers.items():
                if key.lower() not in _HOP_BY_HOP:
                    headers[key] = value
            headers["Content-Length"] = str(len(upstream_body))
            headers["Host"] = urlparse(_ANTHROPIC_API).netloc

            req = urllib.request.Request(
                upstream_url,
                data=upstream_body,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=300) as resp:
                response_body = resp.read()
                response_data = json.loads(response_body)

                # PII in der Antwort zurückmappen
                response_data = self._unmap_response(
                    response_data, mapper,
                )

                # Antwort an Claude Code senden
                result_body = json.dumps(
                    response_data, ensure_ascii=False,
                ).encode("utf-8")

                self.send_response(resp.status)
                for key, value in resp.headers.items():
                    if key.lower() not in _HOP_BY_HOP:
                        self.send_header(key, value)
                self.send_header(
                    "Content-Length", str(len(result_body)),
                )
                self.end_headers()
                self.wfile.write(result_body)

        except urllib.error.HTTPError as e:
            # API-Fehler durchreichen
            error_body = e.read()
            self.send_response(e.code)
            self.send_header(
                "Content-Type", "application/json",
            )
            self.send_header(
                "Content-Length", str(len(error_body)),
            )
            self.end_headers()
            self.wfile.write(error_body)

        except Exception as e:
            log.error("Proxy-Fehler: %s", e, exc_info=True)
            error = json.dumps(
                {"error": f"PII Guard Proxy: {e}"},
            ).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(error)))
            self.end_headers()
            self.wfile.write(error)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._handle_health()
        else:
            self.send_error(404)

    def _mask_messages(
        self,
        data: dict,
        mapper: SessionMapper,
        session_id: str,
    ) -> dict:
        """Maskiert PII in allen Messages des API-Requests."""
        messages = data.get("messages", [])
        total_findings = 0

        for msg in messages:
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "")
            if isinstance(content, str):
                masked, count = self._mask_text(
                    content, mapper, session_id,
                )
                msg["content"] = masked
                total_findings += count
            elif isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        masked, count = self._mask_text(
                            block["text"], mapper, session_id,
                        )
                        block["text"] = masked
                        total_findings += count

        # System-Prompt maskieren
        system = data.get("system", "")
        if isinstance(system, str) and system:
            masked, count = self._mask_text(
                system, mapper, session_id,
            )
            data["system"] = masked
            total_findings += count

        if total_findings == 0:
            log_event(
                "PROMPT_ALLOWED", self.config,
                session_id=session_id,
                details={"pii_count": 0, "mode": "proxy"},
            )

        return data

    def _mask_text(
        self,
        text: str,
        mapper: SessionMapper,
        session_id: str,
    ) -> tuple[str, int]:
        """Maskiert PII in einem Text-String. Gibt (masked, count) zurück."""
        with _lock:
            findings = detect_pii(text, self.config)

        if not findings:
            return text, 0

        # Nur auto_mask Findings substituieren, block-Findings loggen
        masks = [
            f for f in findings
            if f.action in ("auto_mask", "block")
        ]

        log_findings(
            findings, self.config,
            session_id=session_id, prompt=text,
        )

        if masks:
            masked = substitute_pii(text, masks, mapper, self.config)
            log.info(
                "PII maskiert: %d Findings in %d Zeichen",
                len(masks), len(text),
            )
            return masked, len(masks)

        return text, 0

    def _unmap_response(
        self,
        data: dict,
        mapper: SessionMapper,
    ) -> dict:
        """Mappt Fake-Daten in der API-Antwort auf Originale zurück."""
        content = data.get("content", [])

        for block in content:
            if block.get("type") == "text":
                block["text"] = mapper.reverse_map(block["text"])

        return data

    def _handle_health(self) -> None:
        body = json.dumps({
            "status": "ok",
            "mode": "proxy",
            "version": pii_guard.__version__,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header(
            "Content-Type", "application/json; charset=utf-8",
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        log.debug(fmt, *args)


def run_proxy(
    host: str = "127.0.0.1",
    port: int = 7438,
    config_path: str | None = None,
    api_base: str | None = None,
) -> None:
    """Startet den PII Guard Proxy-Server."""
    global _ANTHROPIC_API

    if api_base:
        _ANTHROPIC_API = api_base.rstrip("/")

    config = load_config(Path(config_path) if config_path else None)
    ProxyHandler.config = config

    # Engine-Warmup
    log.info("Engine-Warmup startet...")
    from pii_guard.detector import _get_engine
    _get_engine(config)
    log.info("Engine-Warmup abgeschlossen")

    server = HTTPServer((host, port), ProxyHandler)
    server.daemon_threads = True
    log.info(
        "PII Guard Proxy gestartet auf %s:%d -> %s",
        host, port, _ANTHROPIC_API,
    )
    log.info("Nutze: ANTHROPIC_BASE_URL=http://%s:%d", host, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Proxy wird beendet")
        server.shutdown()


def main() -> None:
    """Entry point: python -m pii_guard.proxy"""
    import argparse

    parser = argparse.ArgumentParser(
        description="PII Guard Proxy – transparentes PII-Mapping",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Bind-Adresse (Default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=7438,
        help="Port (Default: 7438)",
    )
    parser.add_argument(
        "--config", dest="config_path",
        help="Pfad zur Config-Datei",
    )
    parser.add_argument(
        "--api-base", default=None,
        help="Anthropic API URL (Default: https://api.anthropic.com)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    run_proxy(
        host=args.host,
        port=args.port,
        config_path=args.config_path,
        api_base=args.api_base,
    )


if __name__ == "__main__":
    main()
