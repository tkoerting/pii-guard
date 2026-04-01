"""Tests für pii_guard.config – Config-Loader und Validierung."""

from __future__ import annotations

import pytest

from pii_guard.config import ConfigError, _validate_config, find_config_path, load_config


@pytest.fixture()
def config_file(tmp_path, monkeypatch):
    """Erzeugt eine temporäre Config-Datei und wechselt ins Verzeichnis."""
    monkeypatch.chdir(tmp_path)
    return tmp_path / ".pii-guard.yaml"


class TestLoadConfig:
    def test_default_config_without_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config["version"] == 1
        assert "de" in config["engine"]["languages"]

    def test_load_from_explicit_path(self, config_file):
        config_file.write_text(
            "version: 1\nengine:\n  confidence_threshold: 0.9\n"
            "rules:\n  - types: [PERSON]\n    action: auto_mask\n"
        )
        config = load_config(config_file)
        assert config["engine"]["confidence_threshold"] == 0.9
        # Defaults bleiben erhalten
        assert "languages" in config["engine"]

    def test_merge_preserves_defaults(self, config_file):
        config_file.write_text(
            "rules:\n  - types: [PERSON]\n    action: auto_mask\n"
        )
        config = load_config(config_file)
        assert config["mapping"]["enabled"] is True

    def test_find_config_path_finds_yaml(self, config_file):
        config_file.write_text("version: 1\nrules: []\n")
        result = find_config_path()
        assert result is not None
        assert result.name == ".pii-guard.yaml"

    def test_find_config_path_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert find_config_path() is None


class TestValidation:
    def test_valid_default_config(self):
        config = load_config()
        # Sollte keine Exception werfen
        _validate_config(config)

    def test_invalid_action(self):
        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [{"types": ["PERSON"], "action": "delete"}],
            "substitution": {"method": "type_preserving"},
        }
        with pytest.raises(ConfigError, match="delete.*ungültig"):
            _validate_config(config)

    def test_invalid_threshold_too_high(self):
        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 1.5},
            "rules": [],
            "substitution": {"method": "type_preserving"},
        }
        with pytest.raises(ConfigError, match="confidence_threshold"):
            _validate_config(config)

    def test_invalid_threshold_string(self):
        config = {
            "engine": {"languages": ["de"], "confidence_threshold": "high"},
            "rules": [],
            "substitution": {"method": "type_preserving"},
        }
        with pytest.raises(ConfigError, match="confidence_threshold"):
            _validate_config(config)

    def test_invalid_languages_not_list(self):
        config = {
            "engine": {"languages": "de", "confidence_threshold": 0.7},
            "rules": [],
            "substitution": {"method": "type_preserving"},
        }
        with pytest.raises(ConfigError, match="languages"):
            _validate_config(config)

    def test_empty_types_in_rule(self):
        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [{"types": [], "action": "block"}],
            "substitution": {"method": "type_preserving"},
        }
        with pytest.raises(ConfigError, match="nicht-leere Liste"):
            _validate_config(config)

    def test_invalid_substitution_method(self):
        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [],
            "substitution": {"method": "unknown"},
        }
        with pytest.raises(ConfigError, match="unknown.*ungültig"):
            _validate_config(config)

    def test_invalid_docker_port(self):
        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [],
            "substitution": {"method": "type_preserving"},
            "docker": {"port": 99999},
        }
        with pytest.raises(ConfigError, match="docker.port"):
            _validate_config(config)

    def test_invalid_on_error(self):
        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [],
            "substitution": {"method": "type_preserving"},
            "on_error": "ignore",
        }
        with pytest.raises(ConfigError, match="on_error"):
            _validate_config(config)

    def test_valid_docker_config(self):
        config = {
            "engine": {"languages": ["de"], "confidence_threshold": 0.7},
            "rules": [],
            "substitution": {"method": "type_preserving"},
            "docker": {"enabled": True, "port": 7437, "host": "127.0.0.1"},
            "on_error": "block",
        }
        _validate_config(config)  # Kein Fehler
