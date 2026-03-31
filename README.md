# PII Guard

**Lokaler Datenschutz-Filter für KI-Coding-Tools.**

PII Guard verhindert, dass personenbezogene Daten (PII) in Prompts an Claude Code, Cursor oder andere KI-Assistenten gelangen. Auditsicher, lokal, Open Source.

## Was es tut

```
Du tippst:   "Optimiere die Query für Kunde Max Müller (max@firma.de)"
Claude sieht: "Optimiere die Query für Kunde Hans Schmidt (hs@beispiel.de)"
Du siehst:    Die Antwort mit den echten Daten (lokal zurückgemappt)
```

Kein Platzhalter-Chaos. Typerhaltende Substitution – die KI merkt nichts.

## Drei Schutzschichten

| Schicht | Tool | Schützt vor | Wann |
|---------|------|-------------|------|
| **0 – Git** | Gitleaks (pre-commit) | Secrets im Code (API-Keys, Passwörter) | Beim Commit |
| **1 – Prompt** | PII Guard (Claude Code hook) | PII in Prompts (Namen, E-Mails, Kundendaten) | Beim Prompt |
| **2 – Dateien** | .claudeignore | Ganze Dateien (.env, credentials) | Beim Datei-Read |

## Quick Start

```bash
# 1. Installieren
pip install pii-guard

# 2. Claude Code Hook aktivieren
pii-guard init

# 3. Fertig – der Guard läuft automatisch bei jedem Prompt
```

## Konfiguration

Die Regeln liegen im Projekt-Repo (`.pii-guard.yaml`) – zentral versioniert, lokal ausgeführt.

```yaml
# .pii-guard.yaml
version: 1

# Erkennungs-Engine
engine:
  language: ["de", "en"]
  confidence_threshold: 0.7

# Was passiert wenn PII erkannt wird
rules:
  # Harte Secrets – immer blocken
  - type: [PASSWORD, API_KEY, CREDIT_CARD, IBAN]
    action: block

  # Personenbezogene Daten – automatisch maskieren
  - type: [PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION]
    action: auto_mask
    method: type_preserving  # Fake-Daten statt Platzhalter

  # Firmendaten – warnen, User entscheidet
  - type: [ORGANIZATION]
    action: warn

# Audit-Log
audit:
  enabled: true
  path: .pii-guard/audit.log
  commit_summary: true  # Summary wird bei git commit angehängt
```

## Modi

| Modus | Verhalten | Einsatz |
|-------|-----------|---------|
| `warn` | PII anzeigen, User entscheidet | Firmennamen, unklare Fälle |
| `auto_mask` | Automatisch durch Fake-Daten ersetzen | Namen, E-Mails, Adressen |
| `block` | Prompt wird nicht abgeschickt | Passwörter, API-Keys, IBANs |

## Typerhaltende Substitution

Statt `[PERSON_1]` generiert PII Guard semantisch passende Fake-Daten:

| Original | Naiv | PII Guard |
|----------|------|-----------|
| Max Müller | [PERSON_1] | Hans Schmidt |
| max@firma.de | [EMAIL_1] | hs@beispiel.de |
| Hüfingen | [CITY_1] | Freiburg |
| DE89 3704 0044 0532 0130 00 | [IBAN_1] | DE12 5001 0517 0648 4898 90 |

Die KI bekommt gültige Daten im richtigen Format – und liefert korrekte Ergebnisse.

## Reversibles Mapping

Das Mapping wird lokal gespeichert (`.pii-guard/session-map.json`). Wenn die KI-Antwort zurückkommt, werden die Fake-Daten wieder durch die echten ersetzt. Das Mapping verlässt nie den Rechner.

## Audit-Log

Jeder PII-Fund wird geloggt:

```
2026-03-31 14:23:01 | MASK   | PERSON | "Max M***" → "Hans Schmidt" | session:a3f2
2026-03-31 14:23:01 | MASK   | EMAIL  | "m***@firma.de" → "hs@beispiel.de" | session:a3f2
2026-03-31 14:25:17 | BLOCK  | IBAN   | "DE89 3***" | session:a3f2
```

Exportierbar als CSV für den Auditor. Lokal gespeichert, optional als Summary im Git-Commit.

## Architektur

```
┌─────────────────────────────────────────────────┐
│  Entwickler-Rechner (alles lokal)               │
│                                                 │
│  ┌──────────┐    ┌───────────┐    ┌──────────┐  │
│  │ Prompt   │───>│ PII Guard │───>│ Anthropic│  │
│  │ (User)   │    │           │    │ API      │  │
│  └──────────┘    │ ┌───────┐ │    └────┬─────┘  │
│                  │ │Presidio│ │         │        │
│                  │ │(NER)   │ │    ┌────┴─────┐  │
│                  │ └───────┘ │    │ Antwort   │  │
│                  │ ┌───────┐ │    │ (Fake-    │  │
│                  │ │Mapping│◄├────┤  Daten)   │  │
│                  │ │(lokal) │ │    └──────────┘  │
│                  │ └───────┘ │                   │
│                  │ ┌───────┐ │    ┌──────────┐  │
│                  │ │Audit  │─├───>│ Log-File │  │
│                  │ │Logger │ │    └──────────┘  │
│                  │ └───────┘ │                   │
│                  └───────────┘                   │
└─────────────────────────────────────────────────┘

Regeln (.pii-guard.yaml) kommen aus dem Git-Repo = zentral versioniert
Ausführung + Mapping + Logs = lokal auf dem Rechner
```

## Gitleaks-Integration (Schicht 0)

PII Guard empfiehlt Gitleaks als Pre-Commit Hook für Secret-Scanning:

```bash
# Gitleaks aktivieren
pii-guard init --with-gitleaks
```

Das erstellt automatisch die `.pre-commit-config.yaml` und `.gitleaks.toml`.

## Für Audits

PII Guard liefert was ISO 27001 verlangt:

- **Dokumentierte Policy**: `.pii-guard.yaml` im Repo (versioniert, nachvollziehbar)
- **Technischer Control**: Hook greift automatisch vor jedem API-Call
- **Audit-Trail**: Lückenloser Log aller PII-Funde und Aktionen
- **Minimierungsprinzip**: Nur maskierte Daten verlassen den Rechner
- **Kein neuer Datenverarbeiter**: Alles läuft lokal, keine Cloud

## Tech-Stack

| Komponente | Technologie | Lizenz |
|------------|-------------|--------|
| PII-Erkennung | Microsoft Presidio + spaCy (de/en) | MIT |
| Fake-Daten | Faker | MIT |
| Claude Code Hook | user_prompt_submit (nativ) | – |
| Secret-Scanning | Gitleaks | MIT |
| Config | YAML | – |
| Audit-Log | Python logging → CSV-Export | – |

## Lizenz

MIT

## Status

In Entwicklung. MVP geplant.
