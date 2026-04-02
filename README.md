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

Vollständige Schritt-für-Schritt-Anleitung: [docs/SETUP.md](docs/SETUP.md)

### Kurzversion

```bash
# 1. Repository klonen oder piiguard/-Verzeichnis kopieren
cd ~/mydocker/piiguard

# 2. Docker-Image lokal bauen
docker build -t pii-guard:local /pfad/zu/pii-guard

# 3. Container starten
docker compose up -d

# 4. Prüfen
curl http://localhost:4141/health

# 5. Hook-Script ausführbar machen
chmod +x pii-guard-hook.sh
```

Hook in `~/.claude/settings.json` registrieren:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/pfad/zu/piiguard/pii-guard-hook.sh",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

### Systemanforderungen

- Docker
- `curl` und `jq` (für das Hook-Script)
- Windows (WSL2), macOS oder Linux
- Kein lokales Python erforderlich

### Lokale Installation (ohne Docker)

Für Entwicklung oder wenn Docker nicht verfügbar ist:

```bash
pip install -e .
python -m spacy download de_core_news_lg
cd /dein/projekt
pii-guard init
```

Hook-Eintrag für die lokale Variante:

```json
{
  "type": "command",
  "command": "python3 -m pii_guard.hook",
  "timeout": 15000
}
```

---

## Konfiguration

Die Regeln liegen im Projekt-Repo (`.pii-guard.yaml`) – zentral versioniert, lokal ausgeführt.

```yaml
version: 1

engine:
  languages: ["de", "en"]
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

docker:
  enabled: true
  host: 127.0.0.1
  port: 4141
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

Alle Befehle werden per `docker exec` im Container ausgeführt:

```bash
docker exec pii-guard pii-guard <befehl>
```

| Befehl | Beschreibung |
|--------|-------------|
| `init` | Projekt initialisieren (Config + Skills + Hook) |
| `init --with-gitleaks` | Zusätzlich Gitleaks Pre-Commit Hook |
| `on` | PII Guard Hook in Claude Code settings.json aktivieren |
| `off` | PII Guard Hook aus Claude Code settings.json entfernen |
| `pause` | Filterung pausieren (Hook bleibt registriert) |
| `resume` | Filterung nach Pause fortsetzen |
| `test "Text"` | PII-Erkennung testen (Trockenlauf) |
| `status` | Config, Regeln und Audit-Log anzeigen |
| `allow "Begriff" --reason "..."` | Begriff begründet freigeben |
| `revoke "Begriff"` | Freigabe widerrufen |
| `overrides` | Aktive Freigaben anzeigen |
| `audit-export` | Audit-Log als CSV exportieren |
| `audit-report` | Compliance-Report generieren |
| `audit-test` | Wirksamkeitstest mit PASS/FAIL |
| `docker start` | Docker-Daemon starten (lokale Installation) |
| `docker stop` | Docker-Daemon stoppen (lokale Installation) |
| `docker status` | Docker-Status prüfen (lokale Installation) |

---

## Filterung pausieren und fortsetzen

PII Guard kann vorübergehend pausiert werden, ohne den Hook zu entfernen. Während der Pause werden Prompts ungefiltert weitergeleitet.

Vier gleichwertige Wege:

```bash
# CLI (via Docker)
docker exec pii-guard pii-guard pause
docker exec pii-guard pii-guard resume

# Direkt (Terminal)
touch ~/mydocker/piiguard/.pii-guard/disabled
rm ~/mydocker/piiguard/.pii-guard/disabled
```

Oder über die Web-UI (`http://localhost:4141`) bzw. den Claude Code Skill `/pii-pause`.

Der Zustand ist persistent und wird in der Claude Code Statusleiste angezeigt.

---

## Web-UI

Erreichbar unter `http://localhost:4141`

| Seite | URL | Funktion |
|-------|-----|---------|
| Status | `/` | Übersicht, Audit-Statistiken, Pause-Toggle |
| Testen | `/test` | PII-Erkennung ausprobieren |
| Audit-Report | `/report` | Compliance-Report mit Datumsfilter |
| CSV-Export | `/export` | Audit-Log herunterladen |
| Overrides | `/overrides` | Begriffe freigeben und widerrufen |

Die Status-Seite zeigt den aktuellen Zustand (aktiv/pausiert) und ermöglicht das Umschalten per Knopfdruck.

---

## Claude Code Skills

| Skill | Beschreibung |
|-------|-------------|
| `/pii-pause` | Filterung pausieren oder fortsetzen |
| `/pii-status` | Status und aktive Overrides anzeigen |
| `/allow "Begriff" Begründung` | Begriff begründet freigeben |
| `/revoke Begriff` | Freigabe widerrufen |

---

## Claude Code Statusleiste

PII Guard zeigt seinen Zustand in der Claude Code Statusleiste:

| Anzeige | Bedeutung |
|---------|---------|
| `PII aktiv` | Hook registriert und Container healthy |
| `PII: pausiert` | Filterung manuell pausiert |
| `PII: kein Container` | Hook aktiv, Container nicht erreichbar |
| `PII: inaktiv` | Hook nicht in settings.json registriert |

Konfiguration in `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash /pfad/zu/piiguard/pii-guard-statusline.sh"
  }
}
```

---

## Overrides (begründete Freigaben)

Wenn PII Guard einen Begriff fälschlich blockiert, kann er begründet freigegeben werden:

```bash
docker exec pii-guard pii-guard allow "Max Müller" \
  --reason "Fiktiver Testname in der Dokumentation" \
  --who "Thomas Körting"
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

Jeder PII-Fund wird mit 15 Feldern protokolliert. Zeitstempel werden als UTC gespeichert und in der Anzeige in Lokalzeit umgewandelt.

```json
{
  "timestamp": "2026-04-02T17:55:46.437000+00:00",
  "event_id": "a3f2...",
  "event_type": "PII_MASK",
  "session_id": "b4c1...",
  "user_id": "tkoerting",
  "system_id": "myhost",
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
docker exec pii-guard pii-guard audit-report --from 2026-01-01 --to 2026-03-31
docker exec pii-guard pii-guard audit-report --format csv --output report.csv
```

Oder im Browser: `http://localhost:4141/report`

### Wirksamkeitstest

```bash
docker exec pii-guard pii-guard audit-test
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

### Docker-Modus (empfohlen)

```
Prompt → pii-guard-hook.sh → HTTP POST localhost:4141 → Container (Presidio+spaCy) → Ergebnis
```

### Lokaler Modus

```
Prompt → hook.py → Presidio (PII-Erkennung) → Block/Warn/Allow → Audit-Log
```

### Module

| Modul | Zweck |
|-------|-------|
| `hook.py` | Claude Code Hook (stdin/stdout JSON), Docker-Route |
| `detector.py` | Presidio-Wrapper, PII-Erkennung (de/en), NER-Validierungsfilter |
| `recognizers.py` | Eigene Recognizer: deutsche Telefonnummern, IPv4 |
| `substitutor.py` | Faker-basierte typerhaltende Substitution (11 Entity-Typen) |
| `mapper.py` | Bidirektionales Mapping Original ↔ Fake, atomares Schreiben |
| `overrides.py` | Auditierte Override-Verwaltung (begründete Freigaben) |
| `audit.py` | 15-Felder JSONL-Logging, UTC-Speicherung, Log-Rotation, CSV-Export |
| `config.py` | YAML-Loader, Deep-Merge, Validierung, Plattform-Pfade |
| `server.py` | HTTP-Server für Docker-Backend, Web-UI (ThreadingHTTPServer) |
| `cli.py` | Click-CLI mit allen Befehlen und Skill-Installation |

---

## Projektstruktur

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
│   ├── server.py            # Docker HTTP-Server + Web-UI
│   └── cli.py               # CLI (Click) + Skill-Installation
├── tests/                   # pytest
├── docs/
│   ├── SETUP.md             # Team Setup-Anleitung
│   └── ...
├── piiguard/                # Deployment-Verzeichnis (Docker Compose)
│   ├── docker-compose.yml
│   ├── pii-guard-hook.sh    # Hook-Script (kein lokales Python nötig)
│   └── pii-guard-statusline.sh  # Claude Code Statusleiste
├── scripts/
│   └── build_local_docker_image.sh
├── .pii-guard.yaml          # Beispiel-Config
├── Dockerfile               # Multi-Stage Build
├── pyproject.toml           # Packaging (hatchling)
└── README.md
```

---

## Docker

### Lokales Image bauen

```bash
cd /pfad/zu/pii-guard
docker build -t pii-guard:local .
```

Oder mit dem mitgelieferten Script:

```bash
./scripts/build_local_docker_image.sh
```

### Azure Container Registry (Team-Deployment)

```bash
# Image holen
az acr login --name piiguard
docker pull piiguard.azurecr.io/pii-guard:latest

# Neues Image bauen und pushen (nur mit AcrPush-Berechtigung)
docker build --platform linux/amd64 -t piiguard.azurecr.io/pii-guard:latest .
docker push piiguard.azurecr.io/pii-guard:latest
```

### Container aktualisieren

```bash
docker compose down && docker compose up -d
```

---

## Fehlerverhalten

| Situation | Verhalten |
|-----------|-----------|
| Presidio-Fehler | Prompt wird durchgelassen (on_error: allow) |
| Docker-Container nicht erreichbar | Fallback: allow oder block (konfigurierbar) |
| Hook-Timeout | Prompt wird durchgelassen |
| `jq` oder `curl` fehlen | Prompt wird durchgelassen, Hinweis auf stderr |

```yaml
on_error: allow   # Prompt durchlassen bei Fehler (Default)
on_error: block   # Prompt blocken bei Fehler (sicherheitskritische Umgebungen)
```

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

Kein direkter Push auf `main`. Änderungen nur über Pull Requests mit Review.

---

## Lizenz

MIT

## Autor

Thomas Körting / b-imtec GmbH
