"""Integrationstests – komplette Pipeline ohne Presidio.

Testet das Zusammenspiel aller Module mit gemocktem Presidio-Backend.
"""


from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pii_guard.hook import process_prompt


@pytest.fixture()
def config(tmp_path):
    return {
        "version": 1,
        "engine": {
            "languages": ["de"],
            "confidence_threshold": 0.7,
            "spacy_model": "de_core_news_lg",
        },
        "rules": [
            {"types": ["PASSWORD", "API_KEY", "CREDIT_CARD"], "action": "block"},
            {"types": ["IBAN_CODE"], "action": "block"},
            {"types": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"], "action": "auto_mask"},
            {"types": ["LOCATION"], "action": "auto_mask"},
            {"types": ["ORGANIZATION"], "action": "warn"},
        ],
        "allow_list": ["b-imtec", "Microsoft"],
        "substitution": {"method": "type_preserving", "locale": "de_DE", "deterministic": True},
        "mapping": {
            "enabled": True,
            "path": str(tmp_path / "session-map.json"),
            "auto_cleanup": True,
        },
        "audit": {"enabled": True, "path": str(tmp_path / "audit.log")},
    }


def _mock_presidio_results(*specs):
    """Erzeugt Mock-Presidio-Results aus (type, start, end, score) Tuples."""
    results = []
    for entity_type, start, end, score in specs:
        m = MagicMock()
        m.entity_type = entity_type
        m.start = start
        m.end = end
        m.score = score
        results.append(m)
    return results


class TestFullPipeline:
    @patch("pii_guard.detector._get_engine")
    def test_auto_mask_blocks_person_and_email(self, mock_engine, config):
        """auto_mask Findings blocken den Prompt (neue Strategie)."""
        text = "Max Mueller (max@firma.de) braucht Hilfe"
        mock_engine.return_value.analyze.return_value = _mock_presidio_results(
            ("PERSON", 0, 11, 0.95),
            ("EMAIL_ADDRESS", 13, 26, 0.92),
        )

        result = process_prompt(text, config)

        assert result["decision"] == "block"
        assert "reason" in result
        assert "prompt" not in result

    @patch("pii_guard.detector._get_engine")
    def test_block_on_hard_secrets(self, mock_engine, config):
        text = "Passwort: geheim123, User: Max Mueller"
        mock_engine.return_value.analyze.return_value = _mock_presidio_results(
            ("PASSWORD", 10, 19, 0.99),
            ("PERSON", 27, 38, 0.90),
        )

        result = process_prompt(text, config)
        assert result["decision"] == "block"
        assert "prompt" not in result

    @patch("pii_guard.detector._get_engine")
    def test_warn_with_system_message(self, mock_engine, config):
        text = "SAP AG hat angerufen"
        mock_engine.return_value.analyze.return_value = _mock_presidio_results(
            ("ORGANIZATION", 0, 6, 0.85),
        )

        result = process_prompt(text, config)
        assert result["decision"] == "allow"
        assert "systemMessage" in result
        assert "prompt" not in result

    @patch("pii_guard.detector._get_engine")
    def test_mask_plus_warn_blocks(self, mock_engine, config):
        """Bei gemischten Findings (auto_mask + warn) wird geblockt."""
        text = "Max Mueller arbeitet bei SAP AG"
        mock_engine.return_value.analyze.return_value = _mock_presidio_results(
            ("PERSON", 0, 11, 0.95),
            ("ORGANIZATION", 25, 31, 0.80),
        )

        result = process_prompt(text, config)
        assert result["decision"] == "block"
        assert "reason" in result

    @patch("pii_guard.detector._get_engine")
    def test_no_pii_passes_through(self, mock_engine, config):
        mock_engine.return_value.analyze.return_value = []
        result = process_prompt("Hallo Welt", config)
        assert result == {"decision": "allow"}

    @patch("pii_guard.detector._get_engine")
    def test_allow_list_prevents_detection(self, mock_engine, config):
        mock_engine.return_value.analyze.return_value = _mock_presidio_results(
            ("ORGANIZATION", 0, 7, 0.9),
        )
        # "b-imtec" ist in der Allow-List
        result = process_prompt("b-imtec macht gute Arbeit", config)
        assert result["decision"] == "allow"
        assert "systemMessage" not in result
        assert "prompt" not in result


class TestAuditTrail:
    @patch("pii_guard.detector._get_engine")
    def test_audit_log_written(self, mock_engine, config):
        from pathlib import Path

        mock_engine.return_value.analyze.return_value = _mock_presidio_results(
            ("PERSON", 0, 11, 0.95),
        )
        process_prompt("Max Mueller hier", config)

        log_path = Path(config["audit"]["path"])
        assert log_path.exists()
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["pii_type"] == "PERSON"
        assert "event_id" in entry
        assert "session_id" in entry
        assert entry["tool_version"] == "0.1.0"
