# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""YAML-Config Loader für PII Guard."""

from __future__ import annotations

import copy
import logging
import sys
from pathlib import Path

import yaml

log = logging.getLogger("pii_guard.config")


def _user_config_dir() -> Path:
    """Gibt das plattformspezifische Config-Verzeichnis zurück.

    Windows: %APPDATA%/pii-guard
    Mac/Linux: ~/.config/pii-guard
    """
    if sys.platform == "win32":
        appdata = Path.home() / "AppData" / "Roaming" / "pii-guard"
        return appdata
    return Path.home() / ".config" / "pii-guard"


# Suchpfade für Config (erste gefundene gewinnt)
_CONFIG_SEARCH_PATHS = [
    Path(".pii-guard.yaml"),                          # Projekt-Root
    Path(".pii-guard.yml"),                           # Alternative Extension
    _user_config_dir() / "config.yaml",               # User-Default (plattformabhängig)
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
        "detail_level": "standard",
    },
    "mapping": {
        "enabled": True,
        "path": ".pii-guard/session-map.json",
        "auto_cleanup": False,
    },
    "docker": {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 4141,
    },
    "on_error": "allow",
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
    if not isinstance(languages, list) or not all(isinstance(lang, str) for lang in languages):
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

    # Docker
    docker = config.get("docker", {})
    docker_port = docker.get("port", 4141)
    if not isinstance(docker_port, int) or docker_port < 1 or docker_port > 65535:
        raise ConfigError(f"docker.port '{docker_port}' ist ungültig (1-65535)")

    # Audit
    detail_level = config.get("audit", {}).get("detail_level", "standard")
    if detail_level not in {"standard", "detailed"}:
        raise ConfigError(
            f"audit.detail_level '{detail_level}' ist ungültig. "
            f"Erlaubt: standard, detailed"
        )

    # on_error
    on_error = config.get("on_error", "allow")
    if on_error not in {"allow", "block"}:
        raise ConfigError(f"on_error '{on_error}' ist ungültig. Erlaubt: allow, block")


def _deep_merge(base: dict, override: dict) -> None:
    """Merged override rekursiv in base. Verändert base in-place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


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
        return copy.deepcopy(_DEFAULT_CONFIG)

    with config_path.open(encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    # Merge: User-Config überschreibt Defaults (rekursiv für verschachtelte Dicts)
    merged = copy.deepcopy(_DEFAULT_CONFIG)
    _deep_merge(merged, user_config)

    _validate_config(merged)
    return merged
