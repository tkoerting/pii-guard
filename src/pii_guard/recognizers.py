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


class StandaloneIpRecognizer(PatternRecognizer):
    """Erkennt IPv4-Adressen auch ohne Kontextwörter.

    Presidios eingebauter IpRecognizer vergibt nur Score 0.6 ohne
    Kontextwörter wie 'IP' oder 'address'. Dieser Recognizer nutzt
    einen höheren Base-Score, da eine valide IPv4-Adresse in einem
    Prompt fast immer echte PII ist.
    """

    PATTERNS = [
        Pattern(
            "IPV4",
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
            0.7,
        ),
    ]

    CONTEXT = [
        "ip", "adresse", "address", "server", "host", "netzwerk",
        "network", "subnet", "gateway", "dns", "ping",
    ]

    def __init__(self, supported_language: str = "de") -> None:
        super().__init__(
            supported_entity="IP_ADDRESS",
            supported_language=supported_language,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )


class ApiKeyRecognizer(PatternRecognizer):
    """Erkennt API Keys und Secrets verschiedener Anbieter.

    Unterstützte Formate:
    - OpenAI: sk-proj-..., sk-...
    - AWS Access Key: AKIA...
    - Azure Connection String: DefaultEndpointsProtocol=...
    - Generic: api_key=..., API_KEY=..., token=...
    """

    PATTERNS = [
        # OpenAI API Keys
        Pattern(
            "OPENAI_KEY",
            r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}",
            0.9,
        ),
        # AWS Access Key IDs
        Pattern(
            "AWS_ACCESS_KEY",
            r"AKIA[0-9A-Z]{16}",
            0.95,
        ),
        # AWS Secret Keys (40 Zeichen Base64)
        Pattern(
            "AWS_SECRET_KEY",
            r"(?:aws_secret_access_key|SECRET_ACCESS_KEY)"
            r"\s*[=:]\s*[A-Za-z0-9/+=]{40}",
            0.9,
        ),
        # Azure Connection Strings
        Pattern(
            "AZURE_CONN_STRING",
            r"DefaultEndpointsProtocol=https?;[^\s]{20,}",
            0.95,
        ),
        # Azure Storage Account Keys
        Pattern(
            "AZURE_STORAGE_KEY",
            r"AccountKey=[A-Za-z0-9/+=]{44,}",
            0.9,
        ),
        # Generic API Key Zuweisungen
        Pattern(
            "GENERIC_API_KEY",
            r"(?i)(?:api[_-]?key|api[_-]?secret|access[_-]?token"
            r"|auth[_-]?token|bearer)\s*[=:]\s*['\"]?"
            r"[A-Za-z0-9_\-./+=]{20,}",
            0.8,
        ),
    ]

    CONTEXT = [
        "key", "secret", "token", "credential", "api",
        "password", "passwd", "pwd",
    ]

    def __init__(self, supported_language: str = "de") -> None:
        super().__init__(
            supported_entity="API_KEY",
            supported_language=supported_language,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )


class PasswordRecognizer(PatternRecognizer):
    """Erkennt Passwort-Zuweisungen in Code und Config.

    Erkennt Muster wie password=..., pwd=..., passwd=...
    Nicht: das Wort "Passwort" allein (zu viele False Positives).
    """

    PATTERNS = [
        Pattern(
            "PASSWORD_ASSIGNMENT",
            r"(?i)(?:password|passwort|passwd|pwd|kennwort)"
            r"\s*[=:]\s*['\"]?[^\s'\"]{4,}",
            0.85,
        ),
    ]

    CONTEXT = [
        "password", "passwort", "login", "auth",
        "credential", "secret", "kennwort",
    ]

    def __init__(self, supported_language: str = "de") -> None:
        super().__init__(
            supported_entity="PASSWORD",
            supported_language=supported_language,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
