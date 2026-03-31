"""Audit-Logger – lückenloser Nachweis aller PII-Funde (ISO 27001 A.8.15)."""

from __future__ import annotations

import csv
import getpass
import hashlib
import io
import json
import logging
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pii_guard
from pii_guard.detector import Finding

log = logging.getLogger("pii_guard.audit")

_IS_WINDOWS = sys.platform == "win32"


def _config_hash(config: dict) -> str:
    """SHA256 über die aktive Config (erkennt Threshold-Änderungen)."""
    raw = json.dumps(config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _context_hash(text: str, start: int, end: int) -> str:
    """SHA256 über anonymisierten Prompt-Ausschnitt (±20 Zeichen um den Fund)."""
    if not text or start >= len(text):
        return ""
    context_start = max(0, start - 20)
    context_end = min(len(text), end + 20)
    snippet = text[context_start:context_end]
    return hashlib.sha256(snippet.encode()).hexdigest()[:16]


def _set_restrictive_permissions(path: Path) -> None:
    """Setzt restriktive Dateiberechtigungen (chmod 600 auf Unix)."""
    if not _IS_WINDOWS:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _rotate_if_needed(log_path: Path, audit_config: dict) -> None:
    """Rotiert das Audit-Log wenn max_size_mb überschritten ist und löscht alte Logs."""
    if not log_path.exists():
        return

    # Größenbasierte Rotation
    max_size = audit_config.get("max_size_mb", 0)
    if max_size > 0:
        size_mb = log_path.stat().st_size / (1024 * 1024)
        if size_mb >= max_size:
            # Bestehende Rotationen hochzählen
            for i in range(9, 0, -1):
                older = log_path.with_suffix(f".log.{i}")
                newer = log_path.with_suffix(f".log.{i - 1}") if i > 1 else log_path
                if newer.exists():
                    try:
                        os.replace(str(newer), str(older))
                    except OSError:
                        pass
            log.info("Audit-Log rotiert: %s (%.1f MB)", log_path, size_mb)

    # Altersbasierte Bereinigung
    keep_days = audit_config.get("keep_days", 365)
    if keep_days > 0:
        cutoff = datetime.now(timezone.utc).timestamp() - (keep_days * 86400)
        for rotated in sorted(log_path.parent.glob(log_path.stem + ".log.*")):
            try:
                if rotated.stat().st_mtime < cutoff:
                    rotated.unlink()
                    log.info("Altes Audit-Log gelöscht: %s", rotated)
            except OSError:
                pass


def log_findings(
    findings: list[Finding],
    config: dict,
    *,
    session_id: str | None = None,
    prompt: str = "",
) -> None:
    """Loggt eine Liste von PII-Funden ins Audit-Log (15 Felder, ISO 27001 A.8.15)."""
    audit_config = config.get("audit", {})
    if not audit_config.get("enabled", True):
        return

    log_path = Path(audit_config.get("path", ".pii-guard/audit.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _rotate_if_needed(log_path, audit_config)
    is_new_file = not log_path.exists()
    timestamp = datetime.now(timezone.utc).isoformat()
    sid = session_id or str(uuid4())
    cfg_hash = _config_hash(config)
    method = config.get("substitution", {}).get("method", "type_preserving")
    masking_technique = "SUBSTITUTION" if method == "type_preserving" else "PLACEHOLDER"

    try:
        user_id = getpass.getuser()
    except Exception:
        user_id = "unknown"

    system_id = socket.gethostname()

    action_map = {"auto_mask": "MASK", "block": "BLOCK", "warn": "WARN"}

    with log_path.open("a", encoding="utf-8", newline="") as f:
        for finding in findings:
            event_type = f"PII_{action_map.get(finding.action, 'DETECTED')}"

            entry = {
                "timestamp": timestamp,
                "event_id": str(uuid4()),
                "event_type": event_type,
                "session_id": sid,
                "user_id": user_id,
                "system_id": system_id,
                "pii_type": finding.entity_type,
                "pii_count": 1,
                "confidence_score": round(finding.score, 2),
                "action_taken": action_map.get(finding.action, finding.action),
                "masking_technique": masking_technique if finding.action == "auto_mask" else "NONE",
                "outcome": "SUCCESS",
                "context_hash": _context_hash(prompt, finding.start, finding.end) if prompt else "",
                "tool_version": pii_guard.__version__,
                "config_hash": cfg_hash,
                "preview": finding.masked_preview,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if is_new_file:
        _set_restrictive_permissions(log_path)


def log_event(
    event_type: str,
    config: dict,
    *,
    session_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Loggt ein einzelnes Event ins Audit-Log (z.B. EFFECTIVENESS_TEST, PROMPT_ALLOWED)."""
    audit_config = config.get("audit", {})
    if not audit_config.get("enabled", True):
        return

    log_path = Path(audit_config.get("path", ".pii-guard/audit.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        user_id = getpass.getuser()
    except Exception:
        user_id = "unknown"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": str(uuid4()),
        "event_type": event_type,
        "session_id": session_id or str(uuid4()),
        "user_id": user_id,
        "system_id": socket.gethostname(),
        "pii_type": "",
        "pii_count": 0,
        "confidence_score": 0.0,
        "action_taken": "",
        "masking_technique": "NONE",
        "outcome": "SUCCESS",
        "context_hash": "",
        "tool_version": pii_guard.__version__,
        "config_hash": _config_hash(config),
    }
    if details:
        entry.update(details)

    with log_path.open("a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_log_entries(
    log_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """Liest Log-Einträge mit optionalem Datumsfilter."""
    if not log_path.exists():
        return []

    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "")
            if from_date and ts < from_date:
                continue
            if to_date and ts > to_date:
                continue
            entries.append(entry)
        except json.JSONDecodeError:
            continue
    return entries


def export_csv(config: dict, from_date: str | None = None, to_date: str | None = None) -> str:
    """Exportiert das Audit-Log als CSV-String."""
    audit_config = config.get("audit", {})
    log_path = Path(audit_config.get("path", ".pii-guard/audit.log"))

    if not log_path.exists():
        return "Kein Audit-Log vorhanden."

    entries = _read_log_entries(log_path, from_date, to_date)

    if not entries:
        return "Keine Einträge im angegebenen Zeitraum."

    fieldnames = [
        "timestamp", "event_id", "event_type", "session_id", "user_id",
        "system_id", "pii_type", "pii_count", "confidence_score",
        "action_taken", "masking_technique", "outcome", "context_hash",
        "tool_version", "config_hash",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(entries)
    return output.getvalue()


def generate_commit_summary(config: dict) -> str:
    """Generiert eine einzeilige Zusammenfassung für Git-Commits."""
    audit_config = config.get("audit", {})
    log_path = Path(audit_config.get("path", ".pii-guard/audit.log"))

    entries = _read_log_entries(log_path)
    if not entries:
        return ""

    actions: dict[str, int] = {}
    for entry in entries:
        action = entry.get("action_taken") or entry.get("action", "unknown")
        actions[action] = actions.get(action, 0) + 1

    parts = [f"{count}x {action}" for action, count in sorted(actions.items())]
    return f"PII Guard: {', '.join(parts)}"
