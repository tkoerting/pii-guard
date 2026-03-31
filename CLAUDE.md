# PII Guard

Lokaler Datenschutz-Filter für KI-Coding-Tools (Claude Code, Cursor, Copilot).

## Zweck

PII Guard fängt Prompts ab bevor sie an die LLM-API gehen und maskiert personenbezogene Daten durch typerhaltende Substitution. Auditsicher, lokal, Open Source.

## Architektur

```
Prompt → Hook (user_prompt_submit) → Presidio (PII-Erkennung) → Faker (Substitution) → API
Antwort ← Reverse-Mapping (lokal) ← API-Response
```

Alles läuft lokal. Keine Cloud, kein Proxy, kein zusätzlicher Datenverarbeiter.

## Projektstruktur

```
pii-guard/
├── src/
│   └── pii_guard/
│       ├── __init__.py
│       ├── hook.py           # Claude Code Hook (user_prompt_submit)
│       ├── detector.py       # Presidio-Wrapper (PII-Erkennung)
│       ├── substitutor.py    # Typerhaltende Substitution (Faker)
│       ├── mapper.py         # Reversibles Mapping (lokal)
│       ├── audit.py          # Audit-Logger (CSV-Export)
│       ├── config.py         # YAML-Config Loader
│       └── cli.py            # CLI: init, test, audit-export
├── tests/
│   ├── test_detector.py
│   ├── test_substitutor.py
│   ├── test_mapper.py
│   └── test_integration.py
├── .pii-guard.yaml           # Beispiel-Config
├── .gitleaks.toml             # Gitleaks Secret-Patterns
├── .pre-commit-config.yaml   # Pre-Commit Hooks
├── pyproject.toml             # Packaging
├── README.md
└── CLAUDE.md
```

## Kernmodule

### hook.py
- Implementiert den `user_prompt_submit` Hook für Claude Code
- Empfängt den Prompt als JSON auf stdin
- Gibt `{"decision": "allow"}` oder `{"decision": "block", "reason": "..."}` zurück
- Bei `auto_mask`: Modifiziert den Prompt und gibt `{"decision": "allow", "prompt": "..."}` zurück

### detector.py
- Wrapper um Microsoft Presidio AnalyzerEngine
- Lädt spaCy-Modell `de_core_news_lg` für Deutsch
- Konfigurierbar: Welche PII-Typen, Confidence-Threshold
- Gibt Liste von `DetectorResult` zurück (Typ, Start, Ende, Score)

### substitutor.py
- Typerhaltende Substitution mit Faker (Locale: de_DE)
- PERSON → deutscher Fake-Name
- EMAIL → gültige Fake-Email passend zum Fake-Namen
- PHONE → deutsche Fake-Telefonnummer
- LOCATION → deutsche Fake-Stadt
- IBAN → gültige Fake-IBAN
- Deterministisch pro Session (gleicher Input → gleicher Output)

### mapper.py
- Speichert Mapping Original ↔ Fake in `.pii-guard/session-map.json`
- Reverse-Mapping für KI-Antworten
- Session-basiert (neues Mapping pro Session)
- Mapping verlässt nie den Rechner

### audit.py
- Loggt jeden PII-Fund: Zeitstempel, Typ, Aktion, anonymisierter Auszug
- Format: Strukturiertes Log (JSON Lines)
- CSV-Export für Auditor: `pii-guard audit-export --from 2026-01-01`
- Optional: Commit-Summary generieren

### config.py
- Lädt `.pii-guard.yaml` aus dem Projekt-Root
- Fallback auf User-Default (`~/.config/pii-guard/config.yaml`)
- Validiert Config gegen Schema

### cli.py
- `pii-guard init` – Hook installieren, Config anlegen
- `pii-guard init --with-gitleaks` – Zusätzlich Gitleaks Pre-Commit Hook
- `pii-guard test "Max Müller arbeitet bei Firma XY"` – Trockenlauf
- `pii-guard audit-export` – Audit-Log als CSV exportieren
- `pii-guard status` – Zeigt aktive Config und Hook-Status

## Konventionen

- Python 3.11+
- Packaging: pyproject.toml (kein setup.py)
- Tests: pytest
- Linting: ruff
- Type Hints: ja
- Sprache Code: Englisch
- Sprache Doku: Deutsch
- Keine Emojis in Code oder Doku

## Abhängigkeiten

- presidio-analyzer
- presidio-anonymizer
- spacy + de_core_news_lg
- faker
- pyyaml
- click (CLI)

## Offene Entscheidungen

- [ ] Hook-Mechanismus für Cursor / Copilot (Claude Code ist Prio 1)
- [ ] Reverse-Mapping in KI-Antworten: automatisch oder manuell?
- [ ] Audit-Log Rotation / Größenbegrenzung
- [ ] Soll das Mapping zwischen Sessions persistieren?
