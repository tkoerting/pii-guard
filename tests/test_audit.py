"""Tests für pii_guard.audit – Audit-Logger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pii_guard.audit import log_findings, export_csv, generate_commit_summary
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
        }
    }


class TestLogFindings:
    def test_creates_log_file(self, audit_config):
        log_findings([_make_finding()], audit_config)
        path = Path(audit_config["audit"]["path"])
        assert path.exists()

    def test_writes_jsonl(self, audit_config):
        log_findings([_make_finding(), _make_finding("EMAIL_ADDRESS")], audit_config)
        path = Path(audit_config["audit"]["path"])
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2
        entry = json.loads(lines[0])
        assert entry["entity_type"] == "PERSON"
        assert entry["action"] == "auto_mask"
        assert "timestamp" in entry

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


class TestExportCsv:
    def test_export_contains_header(self, audit_config):
        log_findings([_make_finding()], audit_config)
        csv = export_csv(audit_config)
        assert "entity_type" in csv
        assert "PERSON" in csv

    def test_export_empty_log(self, audit_config):
        result = export_csv(audit_config)
        assert "Kein Audit-Log" in result

    def test_export_with_date_filter(self, audit_config):
        log_findings([_make_finding()], audit_config)
        # Zukunftsdatum filtert alles raus
        result = export_csv(audit_config, from_date="2099-01-01")
        assert "Keine Eintr" in result


class TestCommitSummary:
    def test_summary_with_findings(self, audit_config):
        log_findings([_make_finding(action="auto_mask"), _make_finding(action="block")], audit_config)
        summary = generate_commit_summary(audit_config)
        assert "PII Guard:" in summary
        assert "auto_mask" in summary
        assert "block" in summary

    def test_summary_no_log(self, audit_config):
        assert generate_commit_summary(audit_config) == ""
