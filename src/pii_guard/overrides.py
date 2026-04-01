# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""Auditierte Override-Verwaltung für PII Guard.

Ermöglicht das begründete Freigeben von Begriffen, die PII Guard
fälschlich blockiert hat. Jede Freigabe wird mit Begründung,
Ersteller und Zeitstempel gespeichert.

Datei: .pii-guard/overrides.json
Format: Liste von Override-Einträgen
"""

from __future__ import annotations

import getpass
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("pii_guard.overrides")

_IS_WINDOWS = sys.platform == "win32"


def _overrides_path(config: dict) -> Path:
    """Pfad zur Override-Datei."""
    guard_dir = Path(config.get("audit", {}).get("path", ".pii-guard/audit.log")).parent
    return guard_dir / "overrides.json"


def load_overrides(config: dict) -> list[dict]:
    """Lädt alle aktiven Overrides."""
    path = _overrides_path(config)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Override-Datei nicht lesbar: %s", e)
        return []


def get_override_terms(config: dict) -> set[str]:
    """Gibt alle freigegebenen Begriffe als Set zurück (für Allow-List-Check)."""
    overrides = load_overrides(config)
    terms = set()
    for entry in overrides:
        term = entry.get("term", "")
        if term:
            terms.add(term)
            terms.add(term.lower())
    return terms


def add_override(
    term: str,
    reason: str,
    config: dict,
    *,
    who: str | None = None,
    entity_type: str | None = None,
) -> dict:
    """Fügt einen neuen Override hinzu.

    Returns:
        Der erstellte Override-Eintrag.
    """
    overrides = load_overrides(config)

    # Prüfe ob der Begriff bereits freigegeben ist
    existing = [o for o in overrides if o.get("term", "").lower() == term.lower()]
    if existing:
        raise ValueError(f"Begriff '{term}' ist bereits freigegeben "
                         f"(von {existing[0].get('added_by')}, "
                         f"{existing[0].get('timestamp', '?')})")

    entry = {
        "term": term,
        "reason": reason,
        "entity_type": entity_type,
        "added_by": who or getpass.getuser(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": (
            os.environ.get("COMPUTERNAME", "unknown")
            if _IS_WINDOWS else os.uname().nodename
        ),
    }

    overrides.append(entry)
    _save_overrides(overrides, config)

    log.info("Override hinzugefügt: '%s' von %s – %s", term, entry["added_by"], reason)
    return entry


def remove_override(term: str, config: dict) -> dict | None:
    """Entfernt einen Override. Gibt den entfernten Eintrag zurück."""
    overrides = load_overrides(config)
    remaining = []
    removed = None

    for entry in overrides:
        if entry.get("term", "").lower() == term.lower():
            removed = entry
        else:
            remaining.append(entry)

    if removed:
        _save_overrides(remaining, config)
        log.info("Override entfernt: '%s'", term)

    return removed


def list_overrides(config: dict) -> list[dict]:
    """Gibt alle Overrides zurück (für CLI-Anzeige)."""
    return load_overrides(config)


def _save_overrides(overrides: list[dict], config: dict) -> None:
    """Speichert Overrides atomar."""
    path = _overrides_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(overrides, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(str(tmp_path), str(path))

    # Restriktive Berechtigungen (enthält potenziell sensible Begründungen)
    if not _IS_WINDOWS:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
