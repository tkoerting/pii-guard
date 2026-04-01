# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""PII-Erkennung mit Microsoft Presidio."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
)

from pii_guard.recognizers import (
    ApiKeyRecognizer,
    GermanPhoneRecognizer,
    PasswordRecognizer,
    StandaloneIpRecognizer,
)

log = logging.getLogger("pii_guard.detector")

# Zusätzliche Recognizer, die von load_predefined_recognizers()
# nicht geladen werden oder deutsche Formate nicht abdecken.
_EXTRA_RECOGNIZER_CLASSES = [
    CreditCardRecognizer,
    GermanPhoneRecognizer,
    StandaloneIpRecognizer,
    ApiKeyRecognizer,
    PasswordRecognizer,
]

# NER-basierte Entity-Typen (SpacyRecognizer). Diese unterliegen
# strengeren Validierungsregeln als Pattern-basierte Erkennungen,
# da spaCy-NER auf deutschem Text häufig False Positives liefert
# (Tippfehler, Großbuchstaben, einzelne Wörter).
_NER_ENTITY_TYPES = {"PERSON", "LOCATION", "ORGANIZATION", "NRP"}

# Mindestlänge für NER-basierte Findings (Zeichen).
# Einzelwörter wie "Danke", "Ah", "Dir", "SELECT" sind fast nie echte PII.
_NER_MIN_LENGTH = 5

# Technische Fachbegriffe die wie Personennamen aussehen.
# Werden case-insensitive gegen NER-Findings geprüft.
_TECH_TERMS = {
    "adam optimizer", "adam optimiser",
    "max pooling", "max pooling layer", "max pool",
    "xavier initialization", "xavier init",
    "gaussian mixture", "gaussian mixture model",
    "monte carlo", "monte carlo simulation",
    "naive bayes", "naive bayes classifier",
    "random forest", "random forest classifier",
    "markov chain", "markov chain monte carlo",
    "fischer information", "fisher information",
    "pascal case", "camel case",
    "max iterations", "max iter",
    "max retries", "max retry",
    "adam smith",  # Oekonom, nicht Person im Prompt-Kontext
}

# Mindestanzahl Wörter für PERSON- und LOCATION-Entities.
# Echte Personennamen bestehen aus Vor- + Nachname.
# Einzelwort-Orte ("Berlin") werden bewusst durchgelassen — sie sind
# selten schützenswert und erzeugen zu viele False Positives.
_NER_MIN_WORDS = {
    "PERSON": 2,
    "LOCATION": 2,
    "ORGANIZATION": 2,
}


@dataclass
class Finding:
    """Ein erkannter PII-Fund."""
    entity_type: str
    start: int
    end: int
    score: float
    text: str
    action: str  # block, auto_mask, warn
    masked_preview: str  # Anonymisierter Auszug fürs Log

    @property
    def is_blocked(self) -> bool:
        return self.action == "block"


# Singleton – Engine nur einmal initialisieren
_engine: AnalyzerEngine | None = None


def _get_engine(config: dict) -> AnalyzerEngine:
    """Erstellt oder gibt die Presidio AnalyzerEngine zurück.

    Strategie: Nur das deutsche spaCy-Modell für NER laden.
    Pattern-basierte Recognizer (Email, IBAN, IP, Phone, CreditCard)
    werden explizit für Deutsch registriert, da Presidio diese nur
    für Englisch mitbringt. So vermeiden wir False Positives durch
    das englische NER-Modell auf deutschem Text.
    """
    global _engine
    if _engine is not None:
        return _engine

    engine_config = config.get("engine", {})
    spacy_model_de = engine_config.get("spacy_model", "de_core_news_lg")

    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [
            {"lang_code": "de", "model_name": spacy_model_de},
        ],
    }

    provider = NlpEngineProvider(nlp_configuration=nlp_config)
    nlp_engine = provider.create_engine()

    registry = RecognizerRegistry(supported_languages=["de"])
    registry.load_predefined_recognizers(
        nlp_engine=nlp_engine, languages=["de"],
    )

    # Zusätzliche Recognizer, die nicht in den Defaults enthalten sind
    for recognizer_cls in _EXTRA_RECOGNIZER_CLASSES:
        registry.add_recognizer(
            recognizer_cls(supported_language="de"),
        )

    _engine = AnalyzerEngine(
        nlp_engine=nlp_engine,
        registry=registry,
        supported_languages=["de"],
    )
    log.info("Presidio AnalyzerEngine initialisiert (de: %s)", spacy_model_de)
    return _engine


def _has_inner_uppercase(text: str) -> bool:
    """Prüft ob ein Wort BinnenMajuskeln hat (z.B. 'bleibDas').

    Ausnahmen:
    - Vollständig großgeschriebene Wörter (AG, GmbH, CEO) → OK
    - Großbuchstabe nach Bindestrich (Schmidt-Weber) → OK
    """
    for word in text.split():
        if len(word) <= 1:
            continue
        # Komplett uppercase → Abkürzung, kein BinnenMajuskel
        if word.isupper():
            continue
        # Bindestrich-Teile einzeln prüfen (Doppelnamen)
        for part in word.split("-"):
            if len(part) > 1 and not part.isupper():
                if any(c.isupper() for c in part[1:]):
                    return True
    return False


def _mask_preview(text: str) -> str:
    """Erstellt einen anonymisierten Preview für das Audit-Log."""
    if not text:
        return "***"
    if len(text) <= 3:
        return text[0] + "***"
    return text[:3] + "***"


def _get_action_for_type(entity_type: str, rules: list[dict]) -> str:
    """Bestimmt die Aktion für einen PII-Typ aus den Config-Regeln."""
    for rule in rules:
        if entity_type in rule.get("types", []):
            return rule.get("action", "warn")
    return "warn"  # Default: warnen


def detect_pii(text: str, config: dict) -> list[Finding]:
    """Erkennt PII in einem Text und gibt Findings zurück."""
    engine = _get_engine(config)
    engine_config = config.get("engine", {})
    threshold = engine_config.get("confidence_threshold", 0.7)
    rules = config.get("rules", [])
    allow_list = config.get("allow_list", [])

    allow_set = set(allow_list)
    allow_lower = {a.lower() for a in allow_list}

    # Dynamische Overrides laden (begründete Freigaben)
    from pii_guard.overrides import get_override_terms
    override_terms = get_override_terms(config)
    allow_set.update(override_terms)
    allow_lower.update(t.lower() for t in override_terms)

    results = engine.analyze(
        text=text,
        language="de",
        score_threshold=threshold,
    )

    findings = []
    for result in results:
        original_text = text[result.start:result.end]

        # Allow-List + Overrides prüfen
        if original_text in allow_set or original_text.lower() in allow_lower:
            continue

        # NER-basierte Findings strenger validieren
        recognizer = result.recognition_metadata.get("recognizer_name", "")
        if recognizer == "SpacyRecognizer" or result.entity_type in _NER_ENTITY_TYPES:
            stripped = original_text.strip()
            # Zu kurze NER-Findings verwerfen
            if len(stripped) < _NER_MIN_LENGTH:
                log.debug("NER-Finding verworfen (zu kurz): %r", stripped)
                continue
            # Mindestwortzahl pro Entity-Typ prüfen
            min_words = _NER_MIN_WORDS.get(result.entity_type, 0)
            words = stripped.split()
            if min_words and len(words) < min_words:
                log.debug("NER-Finding verworfen (zu wenige Wörter): %s %r",
                          result.entity_type, stripped)
                continue
            # Kurzwörter (< 3 Zeichen) sind verdächtig: "Ah", "Oh", "Na"
            # sind Interjektionen, keine Namen. Ausnahmen: Abkürzungen
            # (komplett uppercase wie "AG") und Titel ("Dr.", "St.")
            short_words = [
                w for w in words
                if len(w) < 3
                and not w.isupper()
                and not (w.endswith(".") and w[0].isupper())
            ]
            if short_words:
                log.debug("NER-Finding verworfen (Kurzwort %r): %s %r",
                          short_words, result.entity_type, stripped)
                continue
            # Technische Fachbegriffe ausschließen
            if stripped.lower() in _TECH_TERMS:
                log.debug(
                    "NER-Finding verworfen (Technik-Term): %r",
                    stripped,
                )
                continue
            # Wörter mit BinnenMajuskeln (z.B. "bleibDas") sind
            # Tippfehler/zusammengeklebte Wörter, keine Eigennamen
            if _has_inner_uppercase(stripped):
                log.debug("NER-Finding verworfen (BinnenMajuskel): %r", stripped)
                continue

        action = _get_action_for_type(result.entity_type, rules)

        findings.append(
            Finding(
                entity_type=result.entity_type,
                start=result.start,
                end=result.end,
                score=result.score,
                text=original_text,
                action=action,
                masked_preview=_mask_preview(original_text),
            )
        )

    # Überlappende Spans auflösen: Pattern-Recognizer (höherer Score)
    # gewinnen über NER. Bei gleichem Score: längster Fund gewinnt.
    findings.sort(key=lambda f: (f.start, -f.score, -(f.end - f.start)))
    resolved = []
    max_end = -1
    for f in findings:
        if f.start >= max_end:
            resolved.append(f)
            max_end = f.end
        elif f.end > max_end:
            pass

    return resolved
