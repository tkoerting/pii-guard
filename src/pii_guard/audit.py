"""Audit-Logger – lückenloser Nachweis aller PII-Funde."""

from __future__ import annotations

import json
import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from pii_guard.detector import Finding


def log_findings(findings: list[Finding], config: dict) -> None:
    """Loggt eine Liste von PII-Funden ins Audit-Log."""
    audit_config = config.get("audit", {})
    if not audit_config.get("enabled", True):
        return

    log_path = Path(audit_config.get("path", ".pii-guard/audit.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()

    with log_path.open("a", encoding="utf-8") as f:
        for finding in findings:
            entry = {
                "timestamp": timestamp,
                "entity_type": finding.entity_type,
                "action": finding.action,
                "score": round(finding.score, 2),
                "preview": finding.masked_preview,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def export_csv(config: dict, from_date: str | None = None) -> str:
    """Exportiert das Audit-Log als CSV-String."""
    audit_config = config.get("audit", {})
    log_path = Path(audit_config.get("path", ".pii-guard/audit.log"))

    if not log_path.exists():
        return "Kein Audit-Log vorhanden."

    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if from_date and entry["timestamp"] < from_date:
                continue
            entries.append(entry)
        except json.JSONDecodeError:
            continue

    if not entries:
        return "Keine Einträge im angegebenen Zeitraum."

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["timestamp", "entity_type", "action", "score", "preview"],
    )
    writer.writeheader()
    writer.writerows(entries)
    return output.getvalue()


def generate_commit_summary(config: dict) -> str:
    """Generiert eine einzeilige Zusammenfassung für Git-Commits."""
    audit_config = config.get("audit", {})
    log_path = Path(audit_config.get("path", ".pii-guard/audit.log"))

    if not log_path.exists():
        return ""

    # Zähle Funde seit letztem Commit (vereinfacht: alle)
    actions: dict[str, int] = {}
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
            action = entry.get("action", "unknown")
            actions[action] = actions.get(action, 0) + 1
        except json.JSONDecodeError:
            continue

    if not actions:
        return ""

    parts = [f"{count}x {action}" for action, count in sorted(actions.items())]
    return f"PII Guard: {', '.join(parts)}"
