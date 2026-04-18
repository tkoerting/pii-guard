# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""Reversibles Mapping – Original ↔ Fake, lokal gespeichert."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

log = logging.getLogger("pii_guard.mapper")
_IS_WINDOWS = sys.platform == "win32"


class SessionMapper:
    """Verwaltet das Mapping zwischen Original- und Fake-Daten.

    Das Mapping existiert nur lokal und wird pro Session erstellt.
    Es verlässt nie den Rechner.
    """

    def __init__(self, config: dict) -> None:
        mapping_config = config.get("mapping", {})
        self.enabled = mapping_config.get("enabled", True)
        self.path = Path(mapping_config.get("path", ".pii-guard/session-map.json"))
        self.auto_cleanup = mapping_config.get("auto_cleanup", True)

        self._forward: dict[str, str] = {}   # original → fake
        self._reverse: dict[str, str] = {}   # fake → original
        self._type_counters: dict[str, int] = {}

        if self.enabled and self.path.exists():
            self._load()

    def _load(self) -> None:
        """Lädt bestehendes Mapping von Disk."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._forward = data.get("forward", {})
            self._reverse = data.get("reverse", {})
            self._type_counters = data.get("counters", {})
        except (json.JSONDecodeError, KeyError):
            log.warning("Mapping-Datei beschädigt, starte mit leerem Mapping: %s", self.path)

    def _save(self) -> None:
        """Speichert das Mapping atomar auf Disk (write-then-rename)."""
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(
            {
                "forward": self._forward,
                "reverse": self._reverse,
                "counters": self._type_counters,
            },
            ensure_ascii=False,
            indent=2,
        )
        # Atomares Schreiben: temp-Datei im selben Verzeichnis, dann rename.
        # os.replace() funktioniert auf allen Plattformen (inkl. Windows seit Python 3.3).
        # Auf Windows schlägt es nur fehl wenn eine andere Anwendung die Zieldatei offen hält.
        fd, tmp_path = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(data)
            os.replace(tmp_path, str(self.path))
        except OSError as e:
            # Fallback für Windows: wenn Zieldatei gelockt ist, direkt schreiben
            Path(tmp_path).unlink(missing_ok=True)
            if _IS_WINDOWS:
                log.warning("Atomares Schreiben fehlgeschlagen, Fallback: %s", e)
                self.path.write_text(data, encoding="utf-8", newline="\n")
            else:
                log.error("Atomares Schreiben fehlgeschlagen: %s", e)
                raise

    def get_fake(self, original: str) -> str | None:
        """Gibt den Fake-Wert für ein Original zurück, falls vorhanden."""
        return self._forward.get(original)

    def get_original(self, fake: str) -> str | None:
        """Gibt den Originalwert für einen Fake zurück (Reverse-Mapping)."""
        return self._reverse.get(fake)

    def store(self, original: str, fake: str, entity_type: str) -> None:
        """Speichert ein neues Mapping."""
        self._forward[original] = fake
        self._reverse[fake] = original
        self._save()

    def next_index(self, entity_type: str) -> int:
        """Gibt den nächsten Index für Platzhalter zurück."""
        current = self._type_counters.get(entity_type, 0) + 1
        self._type_counters[entity_type] = current
        self._save()
        return current

    def reverse_map(self, text: str) -> str:
        """Ersetzt alle Fake-Werte im Text durch ihre Originale."""
        result = text
        # Längste Fake-Werte zuerst ersetzen (verhindert Teilersetzungen)
        for fake, original in sorted(
            self._reverse.items(), key=lambda x: len(x[0]), reverse=True
        ):
            result = result.replace(fake, original)
        return result

    def cleanup(self) -> None:
        """Löscht das Mapping von Disk."""
        if self.path.exists():
            self.path.unlink()

    def __len__(self) -> int:
        return len(self._forward)
