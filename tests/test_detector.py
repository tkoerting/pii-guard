"""Tests für pii_guard.detector – PII-Erkennung.

Presidio-abhängige Tests werden übersprungen wenn die Engine nicht verfügbar ist.
Für die reine Logik (Overlap, Allow-List, Action-Mapping) werden Mocks verwendet.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from pii_guard.detector import (
    Finding,
    detect_pii,
    _mask_preview,
    _get_action_for_type,
)


class TestMaskPreview:
    def test_short_text(self):
        assert _mask_preview("AB") == "A***"

    def test_normal_text(self):
        assert _mask_preview("MaxMueller") == "Max***"

    def test_exact_three(self):
        # "Max" hat len=3 -> Bedingung len<=3 greift -> text[0] + "***"
        assert _mask_preview("Max") == "M***"


class TestGetActionForType:
    def test_known_type(self):
        rules = [{"types": ["PERSON", "EMAIL_ADDRESS"], "action": "auto_mask"}]
        assert _get_action_for_type("PERSON", rules) == "auto_mask"

    def test_unknown_type_defaults_to_warn(self):
        rules = [{"types": ["PERSON"], "action": "auto_mask"}]
        assert _get_action_for_type("UNKNOWN_TYPE", rules) == "warn"

    def test_first_matching_rule_wins(self):
        rules = [
            {"types": ["PERSON"], "action": "block"},
            {"types": ["PERSON"], "action": "auto_mask"},
        ]
        assert _get_action_for_type("PERSON", rules) == "block"


class TestOverlapResolution:
    """Testet die Overlap-Auflösung mit gemocktem Presidio."""

    @patch("pii_guard.detector._get_engine")
    def test_overlapping_findings_keep_longest(self, mock_engine):
        """Bei überlappenden Spans wird der längste behalten."""
        mock_result_email = MagicMock()
        mock_result_email.entity_type = "EMAIL_ADDRESS"
        mock_result_email.start = 0
        mock_result_email.end = 22
        mock_result_email.score = 0.9

        mock_result_person = MagicMock()
        mock_result_person.entity_type = "PERSON"
        mock_result_person.start = 0
        mock_result_person.end = 10
        mock_result_person.score = 0.85

        mock_engine.return_value.analyze.return_value = [mock_result_email, mock_result_person]

        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [{"types": ["EMAIL_ADDRESS", "PERSON"], "action": "auto_mask"}],
            "allow_list": [],
        }
        findings = detect_pii("john.smith@example.com ist hier", config)

        # Nur der längere Fund (EMAIL) soll übrig bleiben
        assert len(findings) == 1
        assert findings[0].entity_type == "EMAIL_ADDRESS"

    @patch("pii_guard.detector._get_engine")
    def test_non_overlapping_findings_kept(self, mock_engine):
        """Nicht-überlappende Findings bleiben alle erhalten."""
        mock_r1 = MagicMock(entity_type="PERSON", start=0, end=10, score=0.9)
        mock_r2 = MagicMock(entity_type="LOCATION", start=20, end=30, score=0.8)
        mock_engine.return_value.analyze.return_value = [mock_r1, mock_r2]

        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [{"types": ["PERSON", "LOCATION"], "action": "auto_mask"}],
            "allow_list": [],
        }
        findings = detect_pii("Max Mueller wohnt in Freiburg xyz", config)
        assert len(findings) == 2


class TestAllowList:
    @patch("pii_guard.detector._get_engine")
    def test_allow_list_filters(self, mock_engine):
        mock_r = MagicMock(entity_type="ORGANIZATION", start=0, end=7, score=0.9)
        mock_engine.return_value.analyze.return_value = [mock_r]

        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [{"types": ["ORGANIZATION"], "action": "warn"}],
            "allow_list": ["b-imtec"],
        }
        findings = detect_pii("b-imtec macht Software", config)
        assert len(findings) == 0

    @patch("pii_guard.detector._get_engine")
    def test_allow_list_case_insensitive(self, mock_engine):
        mock_r = MagicMock(entity_type="ORGANIZATION", start=0, end=9, score=0.9)
        mock_engine.return_value.analyze.return_value = [mock_r]

        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [{"types": ["ORGANIZATION"], "action": "warn"}],
            "allow_list": ["Microsoft"],
        }
        findings = detect_pii("microsoft ist gross", config)
        assert len(findings) == 0
