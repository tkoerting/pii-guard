"""Tests für pii_guard.substitutor – Typerhaltende Substitution."""

from __future__ import annotations

import pytest

from pii_guard.detector import Finding
from pii_guard.mapper import SessionMapper
from pii_guard.substitutor import substitute_pii, _generate_fake


@pytest.fixture()
def mapper_config(tmp_path):
    return {
        "mapping": {
            "enabled": True,
            "path": str(tmp_path / "map.json"),
            "auto_cleanup": True,
        }
    }


@pytest.fixture()
def config(mapper_config):
    return {
        "substitution": {"method": "type_preserving"},
        **mapper_config,
    }


def _finding(entity_type, start, end, text, action="auto_mask"):
    return Finding(
        entity_type=entity_type,
        start=start,
        end=end,
        score=0.9,
        text=text,
        action=action,
        masked_preview=text[:3] + "***",
    )


class TestGenerateFake:
    def test_person_returns_string(self):
        result = _generate_fake("PERSON")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_email_contains_at(self):
        result = _generate_fake("EMAIL_ADDRESS")
        assert "@" in result

    def test_unknown_type_returns_redacted(self):
        result = _generate_fake("UNKNOWN_TYPE")
        assert "REDACTED" in result

    def test_all_known_types(self):
        known = [
            "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION",
            "ADDRESS", "DATE_OF_BIRTH", "IBAN_CODE", "CREDIT_CARD",
            "IP_ADDRESS", "ORGANIZATION",
        ]
        for t in known:
            result = _generate_fake(t)
            assert isinstance(result, str) and len(result) > 0, f"{t} liefert leeres Ergebnis"


class TestSubstitutePii:
    def test_single_substitution(self, config):
        text = "Max Mueller arbeitet hier"
        findings = [_finding("PERSON", 0, 11, "Max Mueller")]
        mapper = SessionMapper(config)

        result = substitute_pii(text, findings, mapper, config)
        assert "Max Mueller" not in result
        assert result.endswith(" arbeitet hier")

    def test_multiple_substitutions_preserve_order(self, config):
        text = "Max Mueller (max@firma.de) ist da"
        findings = [
            _finding("PERSON", 0, 11, "Max Mueller"),
            _finding("EMAIL_ADDRESS", 13, 26, "max@firma.de"),
        ]
        mapper = SessionMapper(config)
        result = substitute_pii(text, findings, mapper, config)

        assert "Max Mueller" not in result
        assert "max@firma.de" not in result
        assert "ist da" in result

    def test_deterministic_within_session(self, config):
        findings = [_finding("PERSON", 0, 11, "Max Mueller")]
        mapper = SessionMapper(config)

        r1 = substitute_pii("Max Mueller x", findings, mapper, config)
        r2 = substitute_pii("Max Mueller y", findings, mapper, config)
        # Gleicher Originalwert -> gleicher Fake
        fake_name = r1.split(" x")[0]
        assert r2.startswith(fake_name)

    def test_warn_findings_not_substituted(self, config):
        text = "Firma GmbH ist Kunde"
        findings = [_finding("ORGANIZATION", 0, 10, "Firma GmbH", action="warn")]
        mapper = SessionMapper(config)
        result = substitute_pii(text, findings, mapper, config)
        assert result == text  # Unverändert

    def test_placeholder_method(self, config, tmp_path):
        config["substitution"]["method"] = "placeholder"
        text = "Max Mueller arbeitet hier"
        findings = [_finding("PERSON", 0, 11, "Max Mueller")]
        mapper = SessionMapper(config)
        result = substitute_pii(text, findings, mapper, config)
        assert "[PERSON_1]" in result

    def test_mapper_stores_mapping(self, config):
        text = "Max Mueller arbeitet hier"
        findings = [_finding("PERSON", 0, 11, "Max Mueller")]
        mapper = SessionMapper(config)
        substitute_pii(text, findings, mapper, config)
        assert mapper.get_fake("Max Mueller") is not None
        assert len(mapper) == 1
