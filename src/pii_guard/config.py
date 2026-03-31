"""YAML-Config Loader für PII Guard."""

from __future__ import annotations

from pathlib import Path

import yaml


# Suchpfade für Config (erste gefundene gewinnt)
_CONFIG_SEARCH_PATHS = [
    Path(".pii-guard.yaml"),                          # Projekt-Root
    Path(".pii-guard.yml"),                           # Alternative Extension
    Path.home() / ".config" / "pii-guard" / "config.yaml",  # User-Default
]

_DEFAULT_CONFIG = {
    "version": 1,
    "engine": {
        "languages": ["de", "en"],
        "confidence_threshold": 0.7,
        "spacy_model": "de_core_news_lg",
    },
    "substitution": {
        "method": "type_preserving",
        "locale": "de_DE",
        "deterministic": True,
    },
    "rules": [
        {"types": ["PASSWORD", "API_KEY", "CREDIT_CARD", "CRYPTO"], "action": "block"},
        {"types": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"], "action": "auto_mask"},
        {"types": ["ORGANIZATION"], "action": "warn"},
    ],
    "allow_list": [],
    "audit": {
        "enabled": True,
        "path": ".pii-guard/audit.log",
        "format": "jsonl",
        "commit_summary": True,
    },
    "mapping": {
        "enabled": True,
        "path": ".pii-guard/session-map.json",
        "auto_cleanup": True,
    },
}


def find_config_path() -> Path | None:
    """Findet die Config-Datei im Suchpfad."""
    for path in _CONFIG_SEARCH_PATHS:
        if path.exists():
            return path
    return None


def load_config(path: Path | None = None) -> dict:
    """Lädt die PII Guard Konfiguration.

    Sucht in folgender Reihenfolge:
    1. Explizit übergebener Pfad
    2. .pii-guard.yaml im aktuellen Verzeichnis
    3. ~/.config/pii-guard/config.yaml
    4. Default-Config
    """
    config_path = path or find_config_path()

    if config_path is None:
        return _DEFAULT_CONFIG.copy()

    with config_path.open(encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    # Merge: User-Config überschreibt Defaults
    merged = _DEFAULT_CONFIG.copy()
    for key, value in user_config.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    return merged
