# PII Guard

**Lokaler Datenschutz-Filter für KI-Coding-Tools.**

PII Guard verhindert, dass personenbezogene Daten (PII) in Prompts an Claude Code, Cursor oder andere KI-Assistenten gelangen. Auditsicher nach ISO 27001, lokal, Open Source.

```
Du tippst:   "Optimiere die Query für Kunde Max Müller (max@firma.de)"
PII Guard:   Blockiert – PERSON 'Max***', EMAIL 'max***' erkannt.
Du passt an: "Optimiere die Query für den Kunden"
```

Harte Secrets (Passwörter, IBANs, API-Keys) werden immer blockiert. Personennamen und E-Mails können per `/allow` mit Begründung freigegeben werden.

## Drei Schutzschichten

| Schicht | Tool | Schützt vor | Wann |
|---------|------|-------------|------|
| **0 – Git** | Gitleaks (pre-commit) | Secrets im Code (API-Keys, Passwörter) | Beim Commit |
| **1 – Prompt** | PII Guard (Claude Code Hook) | PII in Prompts (Namen, E-Mails, Kundendaten) | Beim Prompt |
| **2 – Dateien** | .claudeignore | Ganze Dateien (.env, credentials) | Beim Datei-Read |

---

## Installation

### Variante A: Docker + pip (empfohlen für Teams)

```bash
# 1. Docker-Image holen (Azure Container Registry)
az login
az acr login --name piiguard
docker pull piiguard.azurecr.io/pii-guard:latest

# 2. Container starten
docker run -d -p 4141:4141 --restart=unless-stopped --name pii-guard piiguard.azurecr.io/pii-guard:latest

# 3. CLI installieren
pip install git+https://github.com/b-imtec-gmbh/pii-guard.git

# 4. Projekt einrichten (Config + Skills + Hook)
cd /dein/projekt
pii-guard init
```

Dann in `.pii-guard.yaml` den Docker-Modus aktivieren:

```yaml
docker:
  enabled: true
  host: 127.0.0.1
  port: 4141
```

### Variante B: Lokale Installation (ohne Docker)

```bash
# 1. Installieren
pip install git+https://github.com/b-imtec-gmbh/pii-guard.git

# 2. spaCy-Modell herunterladen (einmalig, ~500 MB)
python -m spacy download de_core_news_lg

# 3. Projekt einrichten
cd /dein/projekt
pii-guard init
```

### Was `pii-guard init` macht

- `.pii-guard.yaml` anlegen (Regeln, Schwellenwerte, Allow-List)
- `.pii-guard/` Verzeichnis erstellen
- Claude Code Hook registrieren (Hinweis)
- Claude Code Skills installieren (`/allow`, `/revoke`, `/pii-toggle`, `/pii-status`)

### Claude Code Hook registrieren

In `~/.claude/settings.json` (Mac/Linux) bzw. `%USERPROFILE%\.claude\settings.json` (Windows):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -m pii_guard.hook",
            "timeout": 15000
          }
        ]
      }
    ]
  }
}
```

Oder einfach: `pii-guard on`

### Systemanforderungen

- Python 3.11+
- Docker Desktop (Variante A) oder ~500 MB für spaCy-Modell (Variante B)
- Windows, macOS oder Linux

---

## Konfiguration

Die Regeln liegen im Projekt-Repo (`.pii-guard.yaml`) – zentral versioniert, lokal ausgeführt.

```yaml
version: 1

engine:
  languages: ["de"]
  confidence_threshold: 0.7
  spacy_model: de_core_news_lg

rules:
  # Harte Secrets – immer blocken
  - types: [PASSWORD, API_KEY, CREDIT_CARD, IBAN_CODE, CRYPTO, AWS_ACCESS_KEY, AZURE_CONNECTION_STRING]
    action: block

  # Personenbezogene Daten – blocken
  - types: [PERSON, EMAIL_ADDRESS, PHONE_NUMBER, DATE_OF_BIRTH, LOCATION, ADDRESS]
    action: auto_mask

  # Firmennamen – warnen, Prompt geht durch
  - types: [ORGANIZATION]
    action: warn

  # IP-Adressen – warnen
  - types: [IP_ADDRESS]
    action: warn

allow_list:
  - "b-imtec"
  - "b-imtec GmbH"
  - "Microsoft"
  - "Anthropic"

audit:
  enabled: true
  path: .pii-guard/audit.log
  max_size_mb: 10
  keep_days: 365

# Docker (optional)
# docker:
#   enabled: true
#   port: 4141
```

---

## Modi

| Modus | Verhalten | Einsatz |
|-------|-----------|---------|
| `block` | Prompt wird blockiert | Passwörter, API-Keys, IBANs, Kreditkarten |
| `auto_mask` | Prompt wird blockiert mit PII-Hinweis | Namen, E-Mails, Telefonnummern |
| `warn` | Hinweis anzeigen, Prompt geht durch | Firmennamen, IP-Adressen |

Hinweis: Claude Code unterstützt keine Prompt-Modifikation durch Hooks. Daher blockiert PII Guard bei `auto_mask`-Findings und zeigt an, welche PII erkannt wurde. Der User kann den Prompt anpassen oder den Begriff per `/allow` freigeben.

---

## CLI-Befehle

| Befehl | Beschreibung |
|--------|-------------|
| `pii-guard init` | Projekt initialisieren (Config + Skills + Hook) |
| `pii-guard init --with-gitleaks` | Zusätzlich Gitleaks Pre-Commit Hook |
| `pii-guard on` | PII Guard Hook aktivieren |
| `pii-guard off` | PII Guard Hook deaktivieren |
| `pii-guard test "Text"` | PII-Erkennung testen (Trockenlauf) |
| `pii-guard status` | Config, Regeln und Audit-Log anzeigen |
| `pii-guard allow "Begriff" --reason "..."` | Begriff begründet freigeben |
| `pii-guard revoke "Begriff"` | Freigabe widerrufen |
| `pii-guard overrides` | Aktive Freigaben anzeigen |
| `pii-guard audit-export` | Audit-Log als CSV exportieren |
| `pii-guard audit-report` | Compliance-Report generieren |
| `pii-guard audit-test` | Wirksamkeitstest mit PASS/FAIL |
| `pii-guard docker start` | Docker-Daemon starten |
| `pii-guard docker stop` | Docker-Daemon stoppen |
| `pii-guard docker status` | Docker-Status prüfen |

## Claude Code Skills

| Skill | Beschreibung |
|-------|-------------|
| `/pii-toggle` | PII Guard ein-/ausschalten |
| `/pii-status` | Status und aktive Overrides anzeigen |
| `/allow "Begriff" Begründung` | Begriff begründet freigeben |
| `/revoke Begriff` | Freigabe widerrufen |

---

## Overrides (begründete Freigaben)

Wenn PII Guard einen Begriff fälschlich blockiert, kann er begründet freigegeben werden:

```bash
pii-guard allow "Max Müller" --reason "Fiktiver Testname in der Dokumentation" --who "Thomas Körting"
```

Oder direkt in Claude Code: `/allow "Max Müller" Fiktiver Testname in der Dokumentation`

Jede Freigabe wird auditiert:
- **Wer** hat freigegeben
- **Wann** wurde freigegeben
- **Warum** (Begründung ist Pflicht)
- **Was** (PII-Typ, Begriff)

Overrides gelten nur projektspezifisch (`.pii-guard/overrides.json`).

---

## Audit und Compliance (ISO 27001)

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
  "action_taken": "BLOCK",
  "masking_technique": "SUBSTITUTION",
  "outcome": "SUCCESS",
  "context_hash": "8a3f...",
  "tool_version": "0.1.0",
  "config_hash": "c2d4..."
}
```

Event-Typen: `PII_MASK`, `PII_BLOCK`, `PII_WARN`, `PROMPT_ALLOWED`, `EFFECTIVENESS_TEST`, `OVERRIDE_ADDED`, `OVERRIDE_REMOVED`

### Compliance-Report

```bash
pii-guard audit-report --from 2026-01-01 --to 2026-03-31
pii-guard audit-report --format csv --output report.csv
```

### Wirksamkeitstest

```bash
pii-guard audit-test
```

### Adressierte ISO 27001 Controls

| Control | Beschreibung | Umsetzung |
|---------|-------------|-----------|
| A.8.11 | Data Masking | PII-Erkennung und Blocking, Config als Policy |
| A.8.12 | Data Leakage Prevention | Hook blockiert PII vor API-Call |
| A.8.15 | Logging | 15-Felder Audit-Log, CSV-Export, Log-Rotation |
| A.8.16 | Monitoring | Compliance-Report, Wirksamkeitstests |
| A.5.34 | PII Protection | Automatische Erkennung, Allow-List, Audit-Trail |

---

## Architektur

### Lokaler Modus

```
Prompt → hook.py → Presidio (PII-Erkennung) → Block/Warn/Allow → Audit-Log
```

### Docker-Modus

```
Prompt → hook.py → HTTP POST localhost:4141 → Container (Presidio+spaCy) → Ergebnis
```

### Module

| Modul | Zweck |
|-------|-------|
| `hook.py` | Claude Code Hook (stdin/stdout JSON), Docker-Route |
| `detector.py` | Presidio-Wrapper, PII-Erkennung (de), NER-Validierungsfilter |
| `recognizers.py` | Eigene Recognizer: deutsche Telefonnummern, IPv4 |
| `substitutor.py` | Faker-basierte typerhaltende Substitution (11 Entity-Typen) |
| `mapper.py` | Bidirektionales Mapping Original <-> Fake, atomares Schreiben |
| `overrides.py` | Auditierte Override-Verwaltung (begründete Freigaben) |
| `audit.py` | 15-Felder JSONL-Logging, Log-Rotation, CSV-Export, Reports |
| `config.py` | YAML-Loader, Deep-Merge, Validierung, Plattform-Pfade |
| `server.py` | HTTP-Server für Docker-Backend (ThreadingHTTPServer) |
| `cli.py` | Click-CLI mit allen Befehlen und Skill-Installation |

---

## Entwicklung

```bash
# Repository klonen
git clone https://github.com/b-imtec-gmbh/pii-guard.git
cd pii-guard

# Dev-Abhängigkeiten installieren
pip install -e ".[dev]"

# spaCy-Modell (für Live-Tests)
python -m spacy download de_core_news_lg

# Tests
python -m pytest tests/ -v

# Linting
ruff check src/ tests/
```

### Workflow (Parallele Entwicklung)

```
1. Feature-Branch erstellen    git checkout -b feature/mein-feature
2. Arbeiten + committen        git commit -m "..."
3. Pushen                      git push -u origin feature/mein-feature
4. Pull Request erstellen      gh pr create
5. Review durch Kollegen
6. CI grün → Squash and Merge
```

Kein direkter Push auf `main`. Änderungen nur über Pull Requests mit Review.

### Projektstruktur

```
pii-guard/
├── src/pii_guard/
│   ├── __init__.py          # Version, Logging-Setup
│   ├── hook.py              # Claude Code Hook, Docker-Route
│   ├── detector.py          # Presidio PII-Erkennung + NER-Filter
│   ├── recognizers.py       # Deutsche Telefonnummern, IPv4
│   ├── substitutor.py       # Faker Substitution
│   ├── mapper.py            # Reversibles Mapping
│   ├── overrides.py         # Begründete Freigaben
│   ├── audit.py             # ISO 27001 Audit-Logger
│   ├── config.py            # YAML-Config Loader
│   ├── server.py            # Docker HTTP-Server
│   └── cli.py               # CLI (Click) + Skill-Installation
├── tests/                   # 92 Tests (pytest)
├── docs/
│   ├── SETUP.md             # Team Setup-Anleitung
│   └── test-report-*.md     # QA-Testberichte
├── .github/
│   ├── workflows/ci.yml     # CI: pytest + ruff
│   ├── CODEOWNERS           # Review-Pflicht
│   └── pull_request_template.md
├── .pii-guard.yaml          # Beispiel-Config
├── Dockerfile               # Multi-Stage Build
├── docker-compose.yml       # Docker-Daemon (ACR-Image)
├── pyproject.toml           # Packaging (hatchling)
└── README.md
```

---

## Docker

### Azure Container Registry

Das Docker-Image liegt auf der b-imtec ACR:

```
Registry:  piiguard.azurecr.io
Image:     piiguard.azurecr.io/pii-guard:latest
```

### Image aktualisieren

```bash
docker pull piiguard.azurecr.io/pii-guard:latest
docker stop pii-guard && docker rm pii-guard
docker run -d -p 4141:4141 --restart=unless-stopped --name pii-guard piiguard.azurecr.io/pii-guard:latest
```

### Neues Image bauen und pushen (nur mit AcrPush-Berechtigung)

```bash
az acr login --name piiguard
docker build --platform linux/amd64 -t piiguard.azurecr.io/pii-guard:latest .
docker push piiguard.azurecr.io/pii-guard:latest
```

---

## Fehlerverhalten

| Situation | Verhalten |
|-----------|-----------|
| Presidio-Fehler | Prompt wird durchgelassen (on_error: allow) |
| Docker-Container nicht erreichbar | Fallback: allow oder block (konfigurierbar) |
| Hook-Timeout | Prompt wird durchgelassen |

```yaml
on_error: allow   # Prompt durchlassen bei Fehler (Default)
on_error: block   # Prompt blocken bei Fehler (sicherheitskritische Umgebungen)
```

---

## Lizenz

MIT

## Autor

Thomas Körting / b-imtec GmbH
