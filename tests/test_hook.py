"""Tests für pii_guard.hook – Claude Code Hook."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pii_guard.hook import process_prompt
from pii_guard.detector import Finding


def _finding(entity_type="PERSON", action="auto_mask", text="Max Mueller", start=0, end=11):
    return Finding(
        entity_type=entity_type,
        start=start,
        end=end,
        score=0.95,
        text=text,
        action=action,
        masked_preview=text[:3] + "***",
    )


@pytest.fixture()
def config(tmp_path):
    return {
        "engine": {"languages": ["de"], "confidence_threshold": 0.7},
        "rules": [
            {"types": ["PASSWORD"], "action": "block"},
            {"types": ["PERSON", "EMAIL_ADDRESS"], "action": "auto_mask"},
            {"types": ["ORGANIZATION"], "action": "warn"},
        ],
        "substitution": {"method": "type_preserving"},
        "mapping": {
            "enabled": True,
            "path": str(tmp_path / "map.json"),
            "auto_cleanup": True,
        },
        "audit": {"enabled": False},
    }


class TestProcessPrompt:
    @patch("pii_guard.detector.detect_pii", return_value=[])
    def test_no_findings_allows(self, mock_detect, config):
        result = process_prompt("Hallo Welt", config)
        assert result["decision"] == "allow"
        assert "prompt" not in result

    @patch("pii_guard.detector.detect_pii")
    def test_block_decision(self, mock_detect, config):
        mock_detect.return_value = [_finding("PASSWORD", "block", "geheim123")]
        result = process_prompt("Passwort: geheim123", config)
        assert result["decision"] == "block"
        assert "reason" in result

    @patch("pii_guard.detector.detect_pii")
    def test_auto_mask_blocks(self, mock_detect, config):
        """auto_mask Findings blocken den Prompt (keine Substitution mehr)."""
        mock_detect.return_value = [_finding("PERSON", "auto_mask")]
        result = process_prompt("Max Mueller arbeitet hier", config)
        assert result["decision"] == "block"
        assert "reason" in result
        assert "Personenbezogene Daten" in result["reason"]

    @patch("pii_guard.detector.detect_pii")
    def test_warn_includes_system_message(self, mock_detect, config):
        mock_detect.return_value = [_finding("ORGANIZATION", "warn", "Firma GmbH")]
        result = process_prompt("Kunde: Firma GmbH", config)
        assert result["decision"] == "allow"
        assert "systemMessage" in result
        assert "Hinweis" in result["systemMessage"]

    @patch("pii_guard.detector.detect_pii")
    def test_mixed_warn_and_mask_blocks(self, mock_detect, config):
        """Bei gemischten Findings (auto_mask + warn) wird geblockt."""
        mock_detect.return_value = [
            _finding("PERSON", "auto_mask", "Max Mueller", 0, 11),
            _finding("ORGANIZATION", "warn", "Firma GmbH", 16, 26),
        ]
        result = process_prompt("Max Mueller bei Firma GmbH", config)
        assert result["decision"] == "block"
        assert "reason" in result
        assert "Warnung" in result["reason"] or "erkannt" in result["reason"]
