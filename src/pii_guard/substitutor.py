# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""Typerhaltende Substitution – Fake-Daten statt Platzhalter."""

from __future__ import annotations

import logging
import os

from faker import Faker

from pii_guard.detector import Finding
from pii_guard.mapper import SessionMapper

log = logging.getLogger("pii_guard.substitutor")

# Faker-Instanz und Generatoren werden lazy pro Config initialisiert
_fake: Faker | None = None
_fake_locale: str | None = None
_GENERATORS: dict[str, object] = {}


def _init_faker(locale: str) -> None:
    """Initialisiert Faker mit der konfigurierten Locale."""
    global _fake, _fake_locale, _GENERATORS
    if _fake is not None and _fake_locale == locale:
        return
    _fake = Faker(locale)
    _fake_locale = locale
    Faker.seed(os.getpid())
    _GENERATORS = {
        "PERSON": lambda: _fake.name(),
        "EMAIL_ADDRESS": lambda: _fake.email(),
        "PHONE_NUMBER": lambda: _fake.phone_number(),
        "LOCATION": lambda: _fake.city(),
        "ADDRESS": lambda: _fake.address().replace("\n", ", "),
        "DATE_OF_BIRTH": lambda: _fake.date_of_birth().isoformat(),
        "IBAN_CODE": lambda: _fake.iban(),
        "CREDIT_CARD": lambda: _fake.credit_card_number(),
        "IP_ADDRESS": lambda: _fake.ipv4(),
        "ORGANIZATION": lambda: _fake.company(),
    }
    log.info("Faker initialisiert mit Locale: %s", locale)


def _generate_fake(entity_type: str) -> str:
    """Generiert einen typerhaltenden Fake-Wert."""
    if not _GENERATORS:
        _init_faker("de_DE")
    generator = _GENERATORS.get(entity_type)
    if generator:
        return generator()
    return f"[{entity_type}_REDACTED]"


def substitute_pii(
    text: str,
    findings: list[Finding],
    mapper: SessionMapper,
    config: dict,
) -> str:
    """Ersetzt PII im Text durch typerhaltende Fake-Daten.

    Arbeitet von hinten nach vorne um die Indizes nicht zu verschieben.
    """
    locale = config.get("substitution", {}).get("locale", "de_DE")
    _init_faker(locale)

    method = config.get("substitution", {}).get("method", "type_preserving")

    # Sortiere Findings von hinten nach vorne
    sorted_findings = sorted(findings, key=lambda f: f.start, reverse=True)

    result = text
    for finding in sorted_findings:
        if finding.action != "auto_mask":
            continue

        # Prüfe ob wir für diesen Originalwert schon einen Fake haben
        existing = mapper.get_fake(finding.text)
        if existing:
            fake_value = existing
        else:
            if method == "type_preserving":
                fake_value = _generate_fake(finding.entity_type)
            else:
                fake_value = f"[{finding.entity_type}_{mapper.next_index(finding.entity_type)}]"

            mapper.store(finding.text, fake_value, finding.entity_type)

        result = result[:finding.start] + fake_value + result[finding.end:]

    return result
