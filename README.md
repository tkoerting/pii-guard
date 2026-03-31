# PII Guard

**Lokaler Datenschutz-Filter für KI-Coding-Tools.**

PII Guard verhindert, dass personenbezogene Daten (PII) in Prompts an Claude Code, Cursor oder andere KI-Assistenten gelangen. Auditsicher nach ISO 27001, lokal, Open Source.

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
| **1 – Prompt** | PII Guard (Claude Code Hook) | PII in Prompts (Namen, E-Mails, Kundendaten) | Beim Prompt |
| **2 – Dateien** | .claudeignore | Ganze Dateien (.env, credentials) | Beim Datei-Read |

---

## Installation

### Variante A: Lokale Installation (pip)

```bash
# 1. Installieren
pip install pii-guard

# 2. spaCy-Modelle herunterladen (einmalig, ~1 GB)
python -m spacy download de_core_news_lg
python -m spacy download en_core_web_lg

# 3. Projekt initialisieren
cd /dein/projekt
pii-guard init

# 4. Claude Code Hook registrieren
#    Füge in die Claude Code settings.json ein:
#    Windows: %USERPROFILE%\.claude\settings.json
#    Mac/Linux: ~/.claude/settings.json
```

```json
{
  "hooks": {
    "user_prompt_submit": [
      {
        "command": "python -m pii_guard.hook",
        "timeout": 5000
      }
    ]
  }
}
```

```bash
# 5. Testen
pii-guard test "Max Müller arbeitet bei Firma XY"
```

### Variante B: Docker (empfohlen für Teams)

Keine lokale Python-Installation nötig. spaCy-Modelle sind im Image enthalten.

```bash
# 1. Projekt initialisieren
cd /dein/projekt
pii-guard init

# 2. Docker-Daemon starten (baut das Image beim ersten Mal)
pii-guard docker start --build

# 3. Docker-Modus in .pii-guard.yaml aktivieren
```

```yaml
docker:
  enabled: true
  host: 127.0.0.1
  port: 7437
```

```bash
# 4. Claude Code Hook registrieren (wie bei Variante A)

# 5. Status prüfen
pii-guard docker status
```

Docker-Befehle:

| Befehl | Beschreibung |
|--------|-------------|
| `pii-guard docker start` | Daemon starten |
| `pii-guard docker start --build` | Image neu bauen und starten |
| `pii-guard docker stop` | Daemon stoppen |
| `pii-guard docker status` | Status und Health-Check |

### Systemanforderungen

- Python 3.11+ (Variante A) oder Docker Desktop (Variante B)
- Windows, macOS oder Linux
- ~1.5 GB Speicher für spaCy-Modelle (lokal) bzw. ~2 GB Docker-Image

---

## Konfiguration

Die Regeln liegen im Projekt-Repo (`.pii-guard.yaml`) – zentral versioniert, lokal ausgeführt.

```yaml
version: 1

engine:
  languages: ["de", "en"]
  confidence_threshold: 0.7

rules:
  # Harte Secrets – immer blocken
  - types: [PASSWORD, API_KEY, CREDIT_CARD, IBAN_CODE]
    action: block

  # Personenbezogene Daten – automatisch maskieren
  - types: [PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION]
    action: auto_mask

  # Firmennamen – warnen, User entscheidet
  - types: [ORGANIZATION]
    action: warn

allow_list:
  - "b-imtec"
  - "Microsoft"

audit:
  enabled: true
  path: .pii-guard/audit.log
  max_size_mb: 10
  keep_days: 365

# Docker (optional)
# docker:
#   enabled: true
#   port: 7437

# Verhalten bei Fehlern
# on_error: allow  # allow | block
```

### Config-Pfade

| Plattform | User-Config |
|-----------|-------------|
| Windows | `%APPDATA%\pii-guard\config.yaml` |
| Mac/Linux | `~/.config/pii-guard/config.yaml` |
| Projekt | `.pii-guard.yaml` (Vorrang) |

---

## Modi

| Modus | Verhalten | Einsatz |
|-------|-----------|---------|
| `block` | Prompt wird nicht abgeschickt | Passwörter, API-Keys, IBANs |
| `auto_mask` | Automatisch durch Fake-Daten ersetzen | Namen, E-Mails, Adressen |
| `warn` | Hinweis anzeigen, Prompt geht durch | Firmennamen, unklare Fälle |

## Typerhaltende Substitution

Statt `[PERSON_1]` generiert PII Guard semantisch passende Fake-Daten:

| Original | Naiv | PII Guard |
|----------|------|-----------|
| Max Müller | [PERSON_1] | Hans Schmidt |
| max@firma.de | [EMAIL_1] | hs@beispiel.de |
| München | [CITY_1] | Freiburg |
| DE89 3704 0044 0532 0130 00 | [IBAN_1] | DE12 5001 0517 0648 4898 90 |

Die KI bekommt gültige Daten im richtigen Format – und liefert korrekte Ergebnisse.

---

## CLI-Befehle

| Befehl | Beschreibung |
|--------|-------------|
| `pii-guard init` | Projekt initialisieren (Config + Guard-Verzeichnis) |
| `pii-guard init --with-gitleaks` | Zusätzlich Gitleaks Pre-Commit Hook |
| `pii-guard test "Text"` | PII-Erkennung testen (Trockenlauf) |
| `pii-guard status` | Config, Regeln und Audit-Log anzeigen |
| `pii-guard audit-export` | Audit-Log als CSV exportieren |
| `pii-guard audit-report` | Compliance-Report generieren (Markdown/CSV) |
| `pii-guard audit-test` | Wirksamkeitstest mit PASS/FAIL |
| `pii-guard docker start` | Docker-Daemon starten |
| `pii-guard docker stop` | Docker-Daemon stoppen |
| `pii-guard docker status` | Docker-Status prüfen |

---

## Audit und Compliance (ISO 27001)

PII Guard liefert was ein Auditor sehen will.

### Audit-Log (15 Felder, ISO 27002:2022 Clause 8.15)

Jeder PII-Fund wird mit 15 Feldern protokolliert:

```json
{
  "timestamp": "2026-03-31T14:22:01.123Z",
  "event_id": "a3f2...",
  "event_type": "PII_MASK",
  "session_id": "b4c1...",
  "user_id": "tkoerting",
  "system_id": "macbook-tk",
  "pii_type": "PERSON",
  "pii_count": 1,
  "confidence_score": 0.95,
  "action_taken": "MASK",
  "masking_technique": "SUBSTITUTION",
  "outcome": "SUCCESS",
  "context_hash": "8a3f...",
  "tool_version": "0.1.0",
  "config_hash": "c2d4..."
}
```

### Compliance-Report

```bash
# Markdown-Report für den Auditor
pii-guard audit-report --from 2026-01-01 --to 2026-03-31

# CSV-Export für Excel
pii-guard audit-report --from 2026-01-01 --format csv --output report.csv
```

Der Report enthält:
- Zusammenfassung (Zeitraum, Anzahl PII-Funde)
- Aufschlüsselung nach PII-Typ und Aktion
- Confidence-Statistik (Durchschnitt, Min, Max)
- Allow-List-Übersicht
- Exceptions (Fehler)
- Wirksamkeitstests (letzter Testlauf)

### Wirksamkeitstest

```bash
pii-guard audit-test
```

Führt vordefinierte Testfälle durch:
- **Positive Tests**: PII-Typen die erkannt werden müssen (Namen, E-Mails, Telefon, IBAN)
- **Negative Tests**: Texte ohne PII die NICHT maskiert werden dürfen ("Max Pool", "Adam Optimizer")
- **PASS/FAIL** pro Typ mit konfigurierbarem Schwellenwert
- Schreibt sich selbst ins Audit-Log (`EFFECTIVENESS_TEST`)
- CSV-Export: `pii-guard audit-test --export testprotokoll.csv`

### Adressierte ISO 27001 Controls

| Control | Beschreibung | Umsetzung |
|---------|-------------|-----------|
| A.8.11 | Data Masking | Typerhaltende Substitution, Config als Policy |
| A.8.12 | Data Leakage Prevention | Hook blockiert/maskiert PII vor API-Call |
| A.8.15 | Logging | 15-Felder Audit-Log, CSV-Export, Log-Rotation |
| A.8.16 | Monitoring | Compliance-Report, Wirksamkeitstests |
| A.5.34 | PII Protection | Automatische Erkennung, Allow-List, Audit-Trail |

### DSGVO Art. 32

| Anforderung | Umsetzung |
|-------------|-----------|
| a) Pseudonymisierung | Typerhaltende Substitution |
| b) Vertraulichkeit | Lokale Verarbeitung, kein Cloud-Abfluss |
| c) Wiederherstellung | Reverse-Mapping |
| d) Wirksamkeitsprüfung | audit-test, Compliance-Report |

---

## Architektur

### Lokaler Modus

```
Prompt → hook.py → Presidio (PII-Erkennung) → Faker (Substitution) → API
                    ↓                           ↓
                 Audit-Log                   Mapping (lokal)
                    ↓                           ↓
Antwort ← ──────────────────── Reverse-Mapping ←── API-Response
```

### Docker-Modus

```
Host (dünn, nur stdlib)              Docker Container
-----------------------              ----------------
hook.py                              server.py (:7437)
  liest stdin JSON                     Presidio + spaCy
  docker.enabled?                      Faker + Mapping
  JA → POST localhost:7437            Audit-Log
  NEIN → lokale Verarbeitung          (Volume-Mount)
```

Der Hook prüft die Config: Wenn `docker.enabled: true`, wird der Prompt per HTTP an den Container geschickt (3s Timeout). Falls der Container nicht erreichbar ist, greift der `on_error`-Fallback (`allow` oder `block`).

### Module

| Modul | Zweck |
|-------|-------|
| `hook.py` | Claude Code Hook (stdin/stdout JSON), Docker-Route |
| `detector.py` | Presidio-Wrapper, PII-Erkennung (de/en), Overlap-Auflösung |
| `substitutor.py` | Faker-basierte typerhaltende Substitution (11 Entity-Typen) |
| `mapper.py` | Bidirektionales Mapping Original <-> Fake, atomares Schreiben |
| `audit.py` | 15-Felder JSONL-Logging, Log-Rotation, CSV-Export, Reports |
| `config.py` | YAML-Loader, Deep-Merge, Validierung, Plattform-Pfade |
| `server.py` | HTTP-Server für Docker-Backend (ThreadingHTTPServer) |
| `cli.py` | Click-CLI: init, test, status, audit-export, audit-report, audit-test, docker |

---

## Tests

```bash
# Alle Tests ausführen
python -m pytest tests/ -v

# Mit Coverage
python -m pytest tests/ --cov=pii_guard
```

93 Tests in 9 Dateien:

| Testdatei | Tests | Abdeckung |
|-----------|-------|-----------|
| test_audit.py | 20 | 15-Felder-Log, Rotation, Events, CSV-Export, Report |
| test_config.py | 14 | Loading, Merge, Validierung (Docker, on_error) |
| test_detector.py | 8 | Preview, Action-Mapping, Overlap, Allow-List |
| test_substitutor.py | 9 | Fake-Generierung, Substitution, Determinismus |
| test_mapper.py | 11 | Store, Persistenz, Reverse-Mapping, Cleanup |
| test_hook.py | 5 | allow/block/warn/mask/mixed Decisions |
| test_hook_docker.py | 8 | Docker-Mode-Erkennung, HTTP-Call, Fallback |
| test_server.py | 5 | Health-Endpoint, Process-Endpoint, 404 |
| test_integration.py | 8 | Komplette Pipeline, Reverse-Mapping, Audit |

Alle Tests mocken die Presidio-Engine – kein spaCy-Modell nötig für die Testsuite.

---

## Entwicklung

```bash
# Repository klonen
git clone https://github.com/tkoerting/pii-guard.git
cd pii-guard

# Dev-Abhängigkeiten installieren
pip install -e ".[dev]"

# spaCy-Modelle (für Live-Tests mit pii-guard test)
python -m spacy download de_core_news_lg
python -m spacy download en_core_web_lg

# Tests
python -m pytest tests/ -v

# Linting
ruff check src/ tests/
```

### Projektstruktur

```
pii-guard/
├── src/pii_guard/
│   ├── __init__.py          # Version, Logging-Setup
│   ├── hook.py              # Claude Code Hook, Docker-Route
│   ├── detector.py          # Presidio PII-Erkennung
│   ├── substitutor.py       # Faker Substitution
│   ├── mapper.py            # Reversibles Mapping
│   ├── audit.py             # ISO 27001 Audit-Logger
│   ├── config.py            # YAML-Config Loader
│   ├── server.py            # Docker HTTP-Server
│   └── cli.py               # CLI (Click)
├── tests/                   # 93 Tests (pytest)
├── .pii-guard.yaml          # Beispiel-Config
├── Dockerfile               # Multi-Stage Build
├── docker-compose.yml       # Docker-Daemon Setup
├── pyproject.toml           # Packaging (hatchling)
└── README.md
```

---

## Fehlerverhalten

| Situation | Verhalten |
|-----------|-----------|
| Presidio-Fehler | Prompt wird durchgelassen (on_error: allow) |
| Docker-Container nicht erreichbar | Fallback: allow oder block (konfigurierbar) |
| Ungültige Config | Fehler beim Laden, PII Guard startet nicht |
| Beschädigte Mapping-Datei | Warnung im Log, leeres Mapping |
| Audit-Log voll | Automatische Rotation (max_size_mb) |

Das Fallback-Verhalten ist konfigurierbar:

```yaml
on_error: allow   # Prompt durchlassen bei Fehler (Default)
on_error: block   # Prompt blocken bei Fehler (sicherheitskritische Umgebungen)
```

---

## Gitleaks-Integration (Schicht 0)

```bash
pii-guard init --with-gitleaks
```

Erstellt automatisch `.pre-commit-config.yaml` für Secret-Scanning bei Git-Commits.

---

## Roadmap

### v0.2.0 (aktuell)
- Kernmodule: Erkennung, Substitution, Mapping, Audit
- ISO 27001 Audit-Log (15 Felder)
- Compliance-Report und Wirksamkeitstests
- Docker-Backend als Option
- Windows/Mac/Linux Support

### v0.3.0 (geplant)
- Policy-Templates (`pii-guard init --with-policy`)
- Reverse-Mapping CLI (`pii-guard unmap`)
- Config-Hierarchie für Teams (Gruppen-Config -> Firmen-Config -> Projekt-Config)
- Onboarding-Guide und Compliance-Brief

---

## Tech-Stack

| Komponente | Technologie | Lizenz |
|------------|-------------|--------|
| PII-Erkennung | Microsoft Presidio + spaCy (de/en) | MIT |
| Fake-Daten | Faker (konfigurierbare Locale) | MIT |
| Claude Code Hook | user_prompt_submit (nativ) | -- |
| Docker-Server | Python stdlib http.server | -- |
| Secret-Scanning | Gitleaks | MIT |
| Config | YAML (PyYAML) | MIT |
| CLI | Click | BSD |
| Audit-Log | JSONL + CSV-Export | -- |

## Lizenz

MIT

## Autor

Thomas Körting / b-imtec GmbH
