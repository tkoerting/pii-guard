"""Typerhaltende Substitution – Fake-Daten statt Platzhalter."""

from __future__ import annotations

import os

from faker import Faker

from pii_guard.detector import Finding
from pii_guard.mapper import SessionMapper


fake = Faker("de_DE")
# Deterministisch pro Session: PID + Prozessstart als Seed.
# So bekommt jede Session andere Fakes, aber innerhalb einer Session bleibt es stabil.
Faker.seed(os.getpid())


# Mapping: Presidio Entity Type → Faker-Generator
_GENERATORS: dict[str, callable] = {
    "PERSON": lambda: fake.name(),
    "EMAIL_ADDRESS": lambda: fake.email(),
    "PHONE_NUMBER": lambda: fake.phone_number(),
    "LOCATION": lambda: fake.city(),
    "ADDRESS": lambda: fake.address().replace("\n", ", "),
    "DATE_OF_BIRTH": lambda: fake.date_of_birth().isoformat(),
    "IBAN_CODE": lambda: fake.iban(),
    "CREDIT_CARD": lambda: fake.credit_card_number(),
    "IP_ADDRESS": lambda: fake.ipv4(),
    "ORGANIZATION": lambda: fake.company(),
}


def _generate_fake(entity_type: str) -> str:
    """Generiert einen typerhaltenden Fake-Wert."""
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
