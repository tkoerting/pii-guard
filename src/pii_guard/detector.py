"""PII-Erkennung mit Microsoft Presidio."""

from __future__ import annotations

from dataclasses import dataclass

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider


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
    """Erstellt oder gibt die Presidio AnalyzerEngine zurück."""
    global _engine
    if _engine is not None:
        return _engine

    engine_config = config.get("engine", {})
    spacy_model = engine_config.get("spacy_model", "de_core_news_lg")

    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [
            {"lang_code": "de", "model_name": spacy_model},
            {"lang_code": "en", "model_name": "en_core_web_lg"},
        ],
    }

    provider = NlpEngineProvider(nlp_configuration=nlp_config)
    nlp_engine = provider.create_engine()

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=nlp_engine)

    _engine = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)
    return _engine


def _mask_preview(text: str) -> str:
    """Erstellt einen anonymisierten Preview für das Audit-Log."""
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
    languages = engine_config.get("languages", ["de", "en"])
    threshold = engine_config.get("confidence_threshold", 0.7)
    rules = config.get("rules", [])
    allow_list = config.get("allow_list", [])

    findings = []

    for lang in languages:
        results = engine.analyze(
            text=text,
            language=lang,
            score_threshold=threshold,
        )

        for result in results:
            original_text = text[result.start:result.end]

            # Allow-List prüfen
            if original_text in allow_list or original_text.lower() in [
                a.lower() for a in allow_list
            ]:
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

    # Deduplizieren (gleiche Stelle, verschiedene Sprachen)
    seen = set()
    unique = []
    for f in findings:
        key = (f.start, f.end, f.entity_type)
        if key not in seen:
            seen.add(key)
            unique.append(f)

    # Überlappende Spans auflösen: bei Overlap den längsten Fund behalten
    unique.sort(key=lambda f: (f.start, -(f.end - f.start)))
    resolved = []
    max_end = -1
    for f in unique:
        if f.start >= max_end:
            resolved.append(f)
            max_end = f.end
        elif f.end > max_end:
            # Teilweise überlappend – längerer Fund gewinnt (bereits vorne sortiert)
            pass
        # Komplett enthalten – überspringen

    return resolved
