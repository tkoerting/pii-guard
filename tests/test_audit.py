"""Tests für pii_guard.audit – Audit-Logger (15-Felder, ISO 27001 A.8.15)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pii_guard.audit import log_findings, log_event, export_csv, generate_commit_summary
from pii_guard.audit import _rotate_if_needed, _read_log_entries
from pii_guard.detector import Finding


def _make_finding(entity_type="PERSON", action="auto_mask", score=0.9):
    return Finding(
        entity_type=entity_type,
        start=0,
        end=10,
        score=score,
        text="Max Mueller",
        action=action,
        masked_preview="Max***",
    )


@pytest.fixture()
def audit_config(tmp_path):
    return {
        "audit": {
            "enabled": True,
            "path": str(tmp_path / "audit.log"),
        },
        "substitution": {"method": "type_preserving"},
    }


class TestLogFindings:
    def test_creates_log_file(self, audit_config):
        log_findings([_make_finding()], audit_config)
        path = Path(audit_config["audit"]["path"])
        assert path.exists()

    def test_writes_15_fields(self, audit_config):
        log_findings(
            [_make_finding(), _make_finding("EMAIL_ADDRESS")],
            audit_config,
            session_id="test-session",
            prompt="Max Mueller hat max@firma.de",
        )
        path = Path(audit_config["audit"]["path"])
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2

        entry = json.loads(lines[0])
        # Alle 15 Pflichtfelder + preview
        assert "timestamp" in entry
        assert "event_id" in entry
        assert "event_type" in entry
        assert entry["session_id"] == "test-session"
        assert "user_id" in entry
        assert "system_id" in entry
        assert entry["pii_type"] == "PERSON"
        assert entry["pii_count"] == 1
        assert entry["confidence_score"] == 0.9
        assert entry["action_taken"] == "MASK"
        assert entry["masking_technique"] == "SUBSTITUTION"
        assert entry["outcome"] == "SUCCESS"
        assert "context_hash" in entry
        assert "tool_version" in entry
        assert "config_hash" in entry
        assert entry["preview"] == "Max***"

    def test_event_types_correct(self, audit_config):
        log_findings(
            [
                _make_finding(action="auto_mask"),
                _make_finding(action="block"),
                _make_finding(action="warn"),
            ],
            audit_config,
        )
        path = Path(audit_config["audit"]["path"])
        entries = [json.loads(line) for line in path.read_text().strip().splitlines()]
        assert entries[0]["event_type"] == "PII_MASK"
        assert entries[1]["event_type"] == "PII_BLOCK"
        assert entries[2]["event_type"] == "PII_WARN"

    def test_appends_to_existing(self, audit_config):
        log_findings([_make_finding()], audit_config)
        log_findings([_make_finding()], audit_config)
        path = Path(audit_config["audit"]["path"])
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_disabled_writes_nothing(self, tmp_path):
        config = {"audit": {"enabled": False, "path": str(tmp_path / "nope.log")}}
        log_findings([_make_finding()], config)
        assert not Path(config["audit"]["path"]).exists()

    def test_masking_technique_placeholder(self, audit_config):
        audit_config["substitution"] = {"method": "placeholder"}
        log_findings([_make_finding()], audit_config)
        path = Path(audit_config["audit"]["path"])
        entry = json.loads(path.read_text().strip().splitlines()[0])
        assert entry["masking_technique"] == "PLACEHOLDER"

    def test_warn_masking_technique_none(self, audit_config):
        log_findings([_make_finding(action="warn")], audit_config)
        path = Path(audit_config["audit"]["path"])
        entry = json.loads(path.read_text().strip().splitlines()[0])
        assert entry["masking_technique"] == "NONE"


class TestLogEvent:
    def test_effectiveness_test_event(self, audit_config):
        log_event("EFFECTIVENESS_TEST", audit_config, details={"outcome": "SUCCESS"})
        path = Path(audit_config["audit"]["path"])
        entry = json.loads(path.read_text().strip())
        assert entry["event_type"] == "EFFECTIVENESS_TEST"
        assert entry["outcome"] == "SUCCESS"
        assert "tool_version" in entry

    def test_custom_session_id(self, audit_config):
        log_event("PROMPT_ALLOWED", audit_config, session_id="my-session")
        path = Path(audit_config["audit"]["path"])
        entry = json.loads(path.read_text().strip())
        assert entry["session_id"] == "my-session"


class TestLogRotation:
    def test_rotation_on_size(self, tmp_path):
        log_path = tmp_path / "audit.log"
        content = "x" * (2 * 1024 * 1024)
        log_path.write_text(content)
        audit_config = {"max_size_mb": 1}

        _rotate_if_needed(log_path, audit_config)

        # Originaldatei wurde nach .1 verschoben
        assert (tmp_path / "audit.log.1").exists()
        assert (tmp_path / "audit.log.1").read_text() == content
        # Originaldatei ist jetzt weg (wurde renamed)
        assert not log_path.exists()

    def test_no_rotation_under_limit(self, tmp_path):
        log_path = tmp_path / "audit.log"
        log_path.write_text("small")
        audit_config = {"max_size_mb": 10}

        _rotate_if_needed(log_path, audit_config)
        assert not (tmp_path / "audit.log.1").exists()

    def test_multiple_rotations(self, tmp_path):
        log_path = tmp_path / "audit.log"
        audit_config = {"max_size_mb": 1}

        # Erste Rotation
        log_path.write_text("a" * (2 * 1024 * 1024))
        _rotate_if_needed(log_path, audit_config)
        assert (tmp_path / "audit.log.1").exists()

        # Zweite Rotation – .1 wird zu .2
        log_path.write_text("b" * (2 * 1024 * 1024))
        _rotate_if_needed(log_path, audit_config)
        assert (tmp_path / "audit.log.2").exists()


class TestExportCsv:
    def test_export_contains_15_field_header(self, audit_config):
        log_findings([_make_finding()], audit_config)
        csv = export_csv(audit_config)
        assert "event_id" in csv
        assert "config_hash" in csv
        assert "PERSON" in csv

    def test_export_empty_log(self, audit_config):
        result = export_csv(audit_config)
        assert "Kein Audit-Log" in result

    def test_export_with_date_filter(self, audit_config):
        log_findings([_make_finding()], audit_config)
        result = export_csv(audit_config, from_date="2099-01-01")
        assert "Keine Eintr" in result

    def test_export_with_to_date(self, audit_config):
        log_findings([_make_finding()], audit_config)
        result = export_csv(audit_config, to_date="2000-01-01")
        assert "Keine Eintr" in result


class TestCommitSummary:
    def test_summary_with_findings(self, audit_config):
        log_findings(
            [_make_finding(action="auto_mask"), _make_finding(action="block")],
            audit_config,
        )
        summary = generate_commit_summary(audit_config)
        assert "PII Guard:" in summary
        assert "MASK" in summary
        assert "BLOCK" in summary

    def test_summary_no_log(self, audit_config):
        assert generate_commit_summary(audit_config) == ""


class TestReadLogEntries:
    def test_reads_entries(self, audit_config):
        log_findings([_make_finding()], audit_config)
        log_path = Path(audit_config["audit"]["path"])
        entries = _read_log_entries(log_path)
        assert len(entries) == 1
        assert entries[0]["pii_type"] == "PERSON"

    def test_date_filter(self, audit_config):
        log_findings([_make_finding()], audit_config)
        log_path = Path(audit_config["audit"]["path"])
        assert len(_read_log_entries(log_path, from_date="2099-01-01")) == 0
        assert len(_read_log_entries(log_path, to_date="2000-01-01")) == 0
        assert len(_read_log_entries(log_path)) == 1
