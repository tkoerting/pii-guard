"""Tests für den Docker-Codepfad in pii_guard.hook."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pii_guard.hook import _is_docker_mode, _process_via_docker


class TestIsDockerMode:
    def test_default_is_false(self):
        config = {"docker": {"enabled": False}}
        assert _is_docker_mode(config) is False

    def test_config_enabled(self):
        config = {"docker": {"enabled": True}}
        assert _is_docker_mode(config) is True

    def test_env_overrides_config(self, monkeypatch):
        monkeypatch.setenv("PII_GUARD_DOCKER", "1")
        config = {"docker": {"enabled": False}}
        assert _is_docker_mode(config) is True

    def test_env_false(self, monkeypatch):
        monkeypatch.setenv("PII_GUARD_DOCKER", "false")
        config = {"docker": {"enabled": True}}
        assert _is_docker_mode(config) is False

    def test_no_docker_section(self):
        config = {}
        assert _is_docker_mode(config) is False


class _MockDaemonHandler(BaseHTTPRequestHandler):
    """Simuliert den PII Guard Docker-Daemon."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        response = {"decision": "allow", "prompt": "FAKE: " + body.get("prompt", "")}
        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture()
def mock_daemon():
    """Startet einen Mock-Docker-Daemon."""
    server = HTTPServer(("127.0.0.1", 0), _MockDaemonHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()


class TestProcessViaDocker:
    def test_sends_to_daemon(self, mock_daemon):
        config = {"docker": {"host": "127.0.0.1", "port": mock_daemon}, "on_error": "allow"}
        result = _process_via_docker("Max Mueller", config)
        assert result["decision"] == "allow"
        assert "FAKE:" in result["prompt"]

    def test_fallback_allow_on_unreachable(self):
        config = {"docker": {"host": "127.0.0.1", "port": 19999}, "on_error": "allow"}
        result = _process_via_docker("Max Mueller", config)
        assert result["decision"] == "allow"

    def test_fallback_block_on_unreachable(self):
        config = {"docker": {"host": "127.0.0.1", "port": 19999}, "on_error": "block"}
        result = _process_via_docker("Max Mueller", config)
        assert result["decision"] == "block"
        assert "nicht erreichbar" in result["reason"]
