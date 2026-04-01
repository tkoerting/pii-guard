"""Tests für pii_guard.server – HTTP API Server."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from unittest.mock import patch

import pytest

from pii_guard.server import PiiGuardHandler


@pytest.fixture()
def server_config(tmp_path):
    return {
        "version": 1,
        "engine": {"languages": ["de"], "confidence_threshold": 0.7},
        "rules": [
            {"types": ["PERSON"], "action": "auto_mask"},
        ],
        "substitution": {"method": "type_preserving", "locale": "de_DE"},
        "allow_list": [],
        "mapping": {
            "enabled": True,
            "path": str(tmp_path / "map.json"),
            "auto_cleanup": True,
        },
        "audit": {"enabled": False},
    }


@pytest.fixture()
def test_server(server_config):
    """Startet einen Test-Server auf einem freien Port."""
    PiiGuardHandler.config = server_config
    server = HTTPServer(("127.0.0.1", 0), PiiGuardHandler)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}"

    server.shutdown()


class TestHealthEndpoint:
    def test_health_returns_ok(self, test_server):
        with urllib.request.urlopen(f"{test_server}/health") as resp:
            data = json.loads(resp.read())
            assert data["status"] == "ok"
            assert "version" in data

    def test_health_returns_json(self, test_server):
        with urllib.request.urlopen(f"{test_server}/health") as resp:
            assert "application/json" in resp.headers["Content-Type"]


class TestProcessEndpoint:
    @patch("pii_guard.hook.process_prompt")
    def test_process_empty_prompt(self, mock_process, test_server):
        payload = json.dumps({"prompt": ""}).encode()
        req = urllib.request.Request(
            f"{test_server}/process",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            assert data["decision"] == "allow"
        mock_process.assert_not_called()

    @patch(
        "pii_guard.server.process_prompt",
        return_value={"decision": "allow", "prompt": "Fake Name"},
    )
    def test_process_returns_result(self, mock_process, test_server):
        payload = json.dumps({"prompt": "Max Mueller"}).encode()
        req = urllib.request.Request(
            f"{test_server}/process",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            assert data["decision"] == "allow"
            assert data["prompt"] == "Fake Name"

    def test_404_on_unknown_path(self, test_server):
        req = urllib.request.Request(f"{test_server}/unknown")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 404


class TestProcessEndpointPost:
    def test_get_on_process_returns_404(self, test_server):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{test_server}/process")
        assert exc_info.value.code == 404
