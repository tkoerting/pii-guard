# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""Eigene Presidio-Recognizer für deutsche PII-Formate."""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer


class GermanPhoneRecognizer(PatternRecognizer):
    """Erkennt deutsche Telefonnummern in verschiedenen Formaten.

    Unterstützte Formate:
    - Mobil: 0171-1234567, 0171/1234567, 0171 1234567
    - Festnetz: 030 12345678, 030-12345678, (030) 12345678
    - International: +49 171 1234567, +49 (0) 171 1234567
    - Mit Vorwahl in Klammern: (0171) 1234567
    """

    PATTERNS = [
        # +49 Formate (international)
        Pattern(
            "DE_PHONE_INTL",
            r"\+49\s*\(?\s*0?\s*\)?\s*\d{2,4}[\s/\-]?\d{4,8}",
            0.7,
        ),
        # 0-Vorwahl Formate (national)
        Pattern(
            "DE_PHONE_NATIONAL",
            r"\(?\b0\d{2,4}\)?[\s/\-]\d{4,8}\b",
            0.7,
        ),
    ]

    CONTEXT = [
        "telefon", "tel", "fon", "handy", "mobil", "anruf",
        "anrufen", "ruf", "erreichbar", "nummer", "rufnummer",
        "phone", "call", "mobile", "fax",
    ]

    def __init__(self, supported_language: str = "de") -> None:
        super().__init__(
            supported_entity="PHONE_NUMBER",
            supported_language=supported_language,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
