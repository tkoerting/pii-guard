"""Tests für pii_guard.mapper – SessionMapper."""

from __future__ import annotations

import json

import pytest

from pii_guard.mapper import SessionMapper


@pytest.fixture()
def mapper_config(tmp_path):
    """Config mit temporärem Mapping-Pfad."""
    return {
        "mapping": {
            "enabled": True,
            "path": str(tmp_path / "session-map.json"),
            "auto_cleanup": True,
        }
    }


@pytest.fixture()
def mapper(mapper_config):
    return SessionMapper(mapper_config)


class TestStore:
    def test_store_and_lookup(self, mapper):
        mapper.store("Max Mueller", "Hans Schmidt", "PERSON")
        assert mapper.get_fake("Max Mueller") == "Hans Schmidt"
        assert mapper.get_original("Hans Schmidt") == "Max Mueller"

    def test_store_multiple(self, mapper):
        mapper.store("Max", "Hans", "PERSON")
        mapper.store("max@firma.de", "hans@beispiel.de", "EMAIL_ADDRESS")
        assert len(mapper) == 2

    def test_lookup_missing_returns_none(self, mapper):
        assert mapper.get_fake("unbekannt") is None
        assert mapper.get_original("unbekannt") is None


class TestPersistence:
    def test_save_and_reload(self, mapper_config):
        m1 = SessionMapper(mapper_config)
        m1.store("Original", "Fake", "PERSON")

        m2 = SessionMapper(mapper_config)
        assert m2.get_fake("Original") == "Fake"
        assert m2.get_original("Fake") == "Original"

    def test_atomic_write_creates_valid_json(self, mapper_config, mapper):
        mapper.store("A", "B", "PERSON")
        path = mapper_config["mapping"]["path"]
        data = json.loads(open(path).read())
        assert "forward" in data
        assert "reverse" in data
        assert data["forward"]["A"] == "B"

    def test_cleanup_removes_file(self, mapper_config, mapper):
        from pathlib import Path

        mapper.store("A", "B", "PERSON")
        assert Path(mapper_config["mapping"]["path"]).exists()
        mapper.cleanup()
        assert not Path(mapper_config["mapping"]["path"]).exists()


class TestReverseMap:
    def test_simple_reverse(self, mapper):
        mapper.store("Max Mueller", "Hans Schmidt", "PERSON")
        result = mapper.reverse_map("Antwort fuer Hans Schmidt: ok")
        assert result == "Antwort fuer Max Mueller: ok"

    def test_multiple_reverse(self, mapper):
        mapper.store("Max", "Hans", "PERSON")
        mapper.store("max@firma.de", "hans@beispiel.de", "EMAIL_ADDRESS")
        result = mapper.reverse_map("Hans (hans@beispiel.de) hat geantwortet")
        assert result == "Max (max@firma.de) hat geantwortet"

    def test_no_mapping_returns_unchanged(self, mapper):
        text = "Keine Fakes hier"
        assert mapper.reverse_map(text) == text


class TestNextIndex:
    def test_incrementing(self, mapper):
        assert mapper.next_index("PERSON") == 1
        assert mapper.next_index("PERSON") == 2
        assert mapper.next_index("EMAIL_ADDRESS") == 1


class TestDisabled:
    def test_disabled_mapper_no_file(self, tmp_path):
        config = {
            "mapping": {
                "enabled": False,
                "path": str(tmp_path / "should-not-exist.json"),
            }
        }
        m = SessionMapper(config)
        m.store("A", "B", "PERSON")
        from pathlib import Path

        assert not Path(config["mapping"]["path"]).exists()
