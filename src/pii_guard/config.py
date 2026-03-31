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


_VALID_ACTIONS = {"block", "auto_mask", "warn"}
_VALID_METHODS = {"type_preserving", "placeholder"}


class ConfigError(ValueError):
    """Fehler in der PII Guard Konfiguration."""


def _validate_config(config: dict) -> None:
    """Validiert die Konfiguration und wirft ConfigError bei Fehlern."""
    # Engine
    engine = config.get("engine", {})
    languages = engine.get("languages", [])
    if not isinstance(languages, list) or not all(isinstance(l, str) for l in languages):
        raise ConfigError("engine.languages muss eine Liste von Strings sein")

    threshold = engine.get("confidence_threshold", 0.7)
    if not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
        raise ConfigError("engine.confidence_threshold muss zwischen 0.0 und 1.0 liegen")

    # Rules
    for i, rule in enumerate(config.get("rules", [])):
        action = rule.get("action")
        if action not in _VALID_ACTIONS:
            raise ConfigError(
                f"rules[{i}].action '{action}' ist ungültig. "
                f"Erlaubt: {', '.join(sorted(_VALID_ACTIONS))}"
            )
        types = rule.get("types", [])
        if not isinstance(types, list) or not types:
            raise ConfigError(f"rules[{i}].types muss eine nicht-leere Liste sein")

    # Substitution
    method = config.get("substitution", {}).get("method", "type_preserving")
    if method not in _VALID_METHODS:
        raise ConfigError(
            f"substitution.method '{method}' ist ungültig. "
            f"Erlaubt: {', '.join(sorted(_VALID_METHODS))}"
        )


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

    _validate_config(merged)
    return merged
