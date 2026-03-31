"""Reversibles Mapping – Original ↔ Fake, lokal gespeichert."""

from __future__ import annotations

import json
from pathlib import Path


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
            data = json.loads(self.path.read_text())
            self._forward = data.get("forward", {})
            self._reverse = data.get("reverse", {})
            self._type_counters = data.get("counters", {})
        except (json.JSONDecodeError, KeyError):
            pass

    def _save(self) -> None:
        """Speichert das Mapping auf Disk."""
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "forward": self._forward,
                    "reverse": self._reverse,
                    "counters": self._type_counters,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

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
