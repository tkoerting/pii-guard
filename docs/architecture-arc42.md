# PII Guard – Architekturdokumentation (arc42)

**Version**: 0.2.0
**Datum**: 2026-04-01
**Autor**: Thomas Körting / b-imtec GmbH

---

## 1. Einführung und Ziele

### 1.1 Aufgabenstellung

PII Guard ist ein lokaler Datenschutz-Filter für KI-Coding-Tools. Er erkennt personenbezogene Daten (PII) in Prompts und maskiert sie durch typerhaltende Fake-Daten, bevor sie an die LLM-API gesendet werden.

### 1.2 Qualitätsziele

| Priorität | Qualitätsziel | Beschreibung |
|-----------|--------------|-------------|
| 1 | Datenschutz | Keine echten PII verlassen den Rechner des Entwicklers |
| 2 | Transparenz | Jede PII-Erkennung und -Aktion wird auditiert (ISO 27001) |
| 3 | Unsichtbarkeit | Der Workflow des Entwicklers wird nicht gestört |
| 4 | Portabilität | Läuft auf Windows, macOS und Linux |
| 5 | Erweiterbarkeit | Neue PII-Typen und KI-Tools integrierbar |

### 1.3 Stakeholder

| Rolle | Erwartung |
|-------|-----------|
| Entwickler | PII Guard darf den Workflow nicht verlangsamen oder stören |
| IT-Leiter | Einfaches Deployment, zentrale Config, Audit-Reports |
| Datenschutzbeauftragter | Nachweisbare technische Maßnahme nach DSGVO Art. 32 |
| ISO 27001 Auditor | Lückenloser Audit-Trail, Wirksamkeitsnachweise |
| Collana IT Gruppe | Einheitlicher Standard über alle Mitgliedsfirmen |

---

## 2. Randbedingungen

### 2.1 Technische Randbedingungen

| Randbedingung | Begründung |
|---------------|-----------|
| Python 3.11+ | Presidio und spaCy erfordern Python 3.11+ |
| 5 Sekunden Hook-Timeout | Claude Code gibt dem Hook maximal 5s |
| Lokale Verarbeitung | Kein Cloud-Dienst, kein neuer Datenverarbeiter |
| Windows-Kompatibilität | b-imtec und Collana arbeiten überwiegend auf Windows |

### 2.2 Organisatorische Randbedingungen

| Randbedingung | Begründung |
|---------------|-----------|
| Open Source (MIT) | Transparenz, keine Lizenzkosten, Collana-Gruppeneinsatz |
| ISO 27001 konform | Audit-Trail muss den Controls A.8.11, A.8.12, A.8.15 genügen |
| Kein zusätzlicher AVV | Alles lokal = kein Auftragsverarbeitungsvertrag nötig |

### 2.3 Konventionen

- Sprache Code: Englisch
- Sprache Dokumentation: Deutsch
- Packaging: pyproject.toml (hatchling)
- Tests: pytest (alle Presidio-Aufrufe gemockt)
- Linting: ruff
- Logging: Python `logging` Modul (stderr, stdout ist für Hook-JSON reserviert)
- Echte Umlaute (ä, ö, ü, ß), Halbgeviertstriche (–)

---

## 3. Kontextabgrenzung

### 3.1 Fachlicher Kontext

```
                    ┌──────────────────────────────────────────────┐
                    │              Entwickler-Rechner               │
                    │                                              │
  Entwickler ──────>│  KI-Tool (Claude Code / Cursor / Copilot)   │
                    │       │                                      │
                    │       v                                      │
                    │  ┌─────────────┐                             │
                    │  │  PII Guard  │──── Audit-Log (.jsonl)      │
                    │  │  (Hook)     │──── Mapping (.json)         │
                    │  └──────┬──────┘                             │
                    │         │ maskierter Prompt                  │
                    │         v                                    │
                    │  ┌─────────────┐                             │
                    │  │  LLM-API    │ (Anthropic / OpenAI / ...)  │
                    │  └──────┬──────┘                             │
                    │         │ Antwort (mit Fake-Daten)           │
                    │         v                                    │
                    │  Reverse-Mapping (lokal) ──> echte Daten     │
                    └──────────────────────────────────────────────┘
```

### 3.2 Technischer Kontext

| Schnittstelle | Technologie | Beschreibung |
|--------------|-------------|-------------|
| Claude Code Hook | stdin/stdout JSON | `user_prompt_submit` Event |
| Docker-API | HTTP POST localhost:7437 | Alternativ zum lokalen Hook |
| Presidio | Python API | NER-basierte PII-Erkennung |
| spaCy | Python API | NLP-Modelle (de_core_news_lg, en_core_web_lg) |
| Faker | Python API | Typerhaltende Fake-Daten-Generierung |
| Dateisystem | JSONL, JSON, YAML | Audit-Log, Mapping, Config |

---

## 4. Lösungsstrategie

### 4.1 Kernentscheidungen

| Entscheidung | Begründung |
|-------------|-----------|
| Hook-basiert (kein Proxy) | Nativer Claude Code Mechanismus, kein zusätzlicher Prozess |
| Typerhaltende Substitution | Fake-Daten im gleichen Format ermöglichen korrekte KI-Antworten |
| Lokale Verarbeitung | Kein Cloud-Abfluss, kein AVV, DSGVO-konform |
| Docker als Option | Eliminiert Installationsprobleme, einfaches Team-Deployment |
| 15-Felder Audit-Log | ISO 27002:2022 Clause 8.15 konform |

### 4.2 Architekturmuster

- **Pipeline-Architektur**: Detect -> Classify -> Substitute -> Audit (linear, deterministisch)
- **Singleton**: Presidio-Engine wird einmal initialisiert und wiederverwendet
- **Strategy**: Substitutionsmethode konfigurierbar (type_preserving / placeholder)
- **Lazy Loading**: Schwere Imports erst bei Bedarf (Docker-Modus bleibt dünn)

---

## 5. Bausteinsicht

### 5.1 Ebene 1 – Gesamtsystem

```
┌────────────────────────────────────────────────────────────────┐
│                         PII Guard                              │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  hook.py  │─>│detector.py│─>│substitutor│─>│ mapper.py│      │
│  │(Einstieg) │  │(Erkennung)│  │   .py     │  │(Mapping) │      │
│  └─────┬─────┘  └──────────┘  └──────────┘  └──────────┘      │
│        │                                                       │
│        v                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
│  │ audit.py │  │ config.py│  │ server.py │                     │
│  │(Logging) │  │(Config)  │  │(Docker)   │                     │
│  └──────────┘  └──────────┘  └──────────┘                     │
│                                                                │
│  ┌──────────┐                                                  │
│  │  cli.py  │ (Benutzerschnittstelle)                         │
│  └──────────┘                                                  │
└────────────────────────────────────────────────────────────────┘
```

### 5.2 Ebene 2 – Module im Detail

#### hook.py (Einstiegspunkt)
- **Verantwortung**: Entgegennahme des Prompts, Routing (lokal vs. Docker), Rückgabe der Entscheidung
- **Schnittstellen**: stdin/stdout (JSON), config.py, detector.py, substitutor.py, mapper.py, audit.py
- **Besonderheit**: Lazy Imports – schwere Abhängigkeiten werden erst in `process_prompt()` geladen

#### detector.py (PII-Erkennung)
- **Verantwortung**: PII im Text erkennen, Findings mit Typ, Position, Score und Aktion zurückgeben
- **Schnittstellen**: Presidio AnalyzerEngine, spaCy NLP-Modelle
- **Besonderheit**: Singleton-Engine, Overlap-Auflösung (längster Span gewinnt), Allow-List als Set

#### substitutor.py (Substitution)
- **Verantwortung**: Erkannte PII durch typerhaltende Fake-Daten ersetzen
- **Schnittstellen**: Faker, mapper.py
- **Besonderheit**: Backward-Index-Processing, Locale aus Config, deterministisch pro Session (PID-Seed)

#### mapper.py (Mapping)
- **Verantwortung**: Bidirektionales Mapping Original <-> Fake, Reverse-Mapping für KI-Antworten
- **Schnittstellen**: Dateisystem (.pii-guard/session-map.json)
- **Besonderheit**: Atomares Schreiben (os.replace + Windows-Fallback), konsistente Line-Endings

#### audit.py (Audit-Logger)
- **Verantwortung**: Protokollierung aller PII-Funde und Events (15 Felder, ISO 27001)
- **Schnittstellen**: Dateisystem (.pii-guard/audit.log), config.py
- **Besonderheit**: Log-Rotation (max_size_mb + keep_days), chmod 600 auf Unix, CSV-Export, Compliance-Reports

#### config.py (Konfiguration)
- **Verantwortung**: Config laden, mergen, validieren
- **Schnittstellen**: Dateisystem (.pii-guard.yaml, User-Config), alle Module
- **Besonderheit**: Deep-Merge, plattformspezifische Pfade, copy.deepcopy für Thread-Safety

#### server.py (Docker-Backend)
- **Verantwortung**: HTTP-API für Docker-Modus
- **Schnittstellen**: HTTP (POST /process, GET /health), hook.py
- **Besonderheit**: ThreadingHTTPServer, threading.Lock, Engine-Warmup beim Start

#### cli.py (CLI)
- **Verantwortung**: Benutzerschnittstelle für alle Operationen
- **Schnittstellen**: Alle Module, Docker (subprocess)
- **Befehle**: init, test, status, audit-export, audit-report, audit-test, docker start/stop/status

---

## 6. Laufzeitsicht

### 6.1 Prompt-Verarbeitung (lokaler Modus)

```
Entwickler           Claude Code          hook.py        detector.py     substitutor.py    audit.py
    │                     │                  │                │                │              │
    │── Prompt ──────────>│                  │                │                │              │
    │                     │── stdin JSON ───>│                │                │              │
    │                     │                  │── detect_pii ─>│                │              │
    │                     │                  │                │── Presidio ───>│              │
    │                     │                  │                │<── Findings ───│              │
    │                     │                  │── substitute ──────────────────>│              │
    │                     │                  │                                 │── Faker ────>│
    │                     │                  │<── maskierter Text ─────────────│              │
    │                     │                  │── log_findings ────────────────────────────────>│
    │                     │                  │                                                │
    │                     │<── stdout JSON ──│                                                │
    │                     │   {decision,     │                                                │
    │                     │    prompt}       │                                                │
    │<── Antwort ─────────│                  │                                                │
```

### 6.2 Prompt-Verarbeitung (Docker-Modus)

```
Entwickler           Claude Code          hook.py              server.py (Container)
    │                     │                  │                        │
    │── Prompt ──────────>│                  │                        │
    │                     │── stdin JSON ───>│                        │
    │                     │                  │── HTTP POST /process ─>│
    │                     │                  │   (3s Timeout)         │── process_prompt()
    │                     │                  │                        │   (mit Lock)
    │                     │                  │<── JSON Response ──────│
    │                     │<── stdout JSON ──│                        │
    │<── Antwort ─────────│                  │                        │
```

### 6.3 Fehlerfall (Docker nicht erreichbar)

```
hook.py                                    Ergebnis
    │
    │── HTTP POST /process ──> Timeout (3s)
    │
    │── Prüfe on_error Config
    │   ├── "allow" ──> {decision: "allow"} (Prompt geht durch)
    │   └── "block" ──> {decision: "block"} (Prompt wird gestoppt)
```

---

## 7. Verteilungssicht

### 7.1 Lokaler Modus

```
┌──────────────────────────────────────────────┐
│             Entwickler-Rechner               │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ Python 3.11+ Environment              │  │
│  │  ├── pii-guard (pip install)          │  │
│  │  ├── presidio-analyzer                │  │
│  │  ├── spacy + de_core_news_lg (~500MB) │  │
│  │  └── faker                            │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ Projekt-Verzeichnis                   │  │
│  │  ├── .pii-guard.yaml (Config, im Repo)│  │
│  │  └── .pii-guard/                      │  │
│  │       ├── session-map.json (lokal)    │  │
│  │       └── audit.log (lokal)           │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### 7.2 Docker-Modus

```
┌──────────────────────────────────────────────┐
│             Entwickler-Rechner               │
│                                              │
│  ┌─────────────────────┐  ┌───────────────┐ │
│  │ Host (dünn)         │  │ Docker        │ │
│  │  └── hook.py        │  │ Container     │ │
│  │     (nur stdlib)    │  │  ├── Presidio │ │
│  │                     │  │  ├── spaCy    │ │
│  │   HTTP POST ───────────>│  ├── Faker   │ │
│  │   localhost:7437    │  │  └── server.py│ │
│  └─────────────────────┘  └───────┬───────┘ │
│                                   │         │
│  ┌────────────────────────────────┘         │
│  │ Volume-Mounts:                           │
│  │  .pii-guard.yaml ──> /app/data/ (ro)    │
│  │  .pii-guard/ ──────> /app/data/ (rw)    │
│  └──────────────────────────────────────────│
└──────────────────────────────────────────────┘
```

### 7.3 Docker-Container Details

| Eigenschaft | Wert |
|------------|------|
| Base Image | python:3.11-slim |
| Größe | ~2 GB (inkl. spaCy-Modelle) |
| Port | 127.0.0.1:7437 (nur lokal) |
| Restart | unless-stopped |
| Security | read_only, no-new-privileges, tmpfs /tmp |
| Healthcheck | GET /health (10s Intervall, 30s Start-Period) |

---

## 8. Querschnittliche Konzepte

### 8.1 PII-Erkennung

```
Text ──> Presidio (NER) ──> Findings (Typ, Position, Score)
                              │
                              v
                         Deduplizierung (gleiche Stelle, verschiedene Sprachen)
                              │
                              v
                         Overlap-Auflösung (längster Span gewinnt)
                              │
                              v
                         Allow-List-Filter (case-insensitive)
                              │
                              v
                         Aktion zuweisen (Rules aus Config)
```

Unterstützte PII-Typen:

| Typ | Beispiel | Default-Aktion |
|-----|---------|----------------|
| PASSWORD | geheim123 | block |
| API_KEY | sk-abc123... | block |
| CREDIT_CARD | 4111 1111 1111 1111 | block |
| IBAN_CODE | DE89 3704 0044... | block |
| PERSON | Max Müller | auto_mask |
| EMAIL_ADDRESS | max@firma.de | auto_mask |
| PHONE_NUMBER | +49 170 1234567 | auto_mask |
| LOCATION | München | auto_mask |
| ADDRESS | Hauptstr. 1, München | auto_mask |
| DATE_OF_BIRTH | 15.03.1985 | auto_mask |
| ORGANIZATION | SAP AG | warn |
| IP_ADDRESS | 192.168.1.1 | warn |

### 8.2 Typerhaltende Substitution

| PII-Typ | Faker-Generator | Beispiel |
|---------|----------------|---------|
| PERSON | fake.name() | Hans Schmidt |
| EMAIL_ADDRESS | fake.email() | hs@beispiel.de |
| PHONE_NUMBER | fake.phone_number() | +49 30 12345678 |
| LOCATION | fake.city() | Freiburg |
| ADDRESS | fake.address() | Berliner Str. 42, Hamburg |
| IBAN_CODE | fake.iban() | DE12 5001 0517... |

Prinzip: Backward-Index-Processing. Findings werden von hinten nach vorne ersetzt, damit die Indizes der vorhergehenden Findings nicht verschoben werden.

### 8.3 Audit-Trail (ISO 27001)

Jeder PII-Fund wird mit 15 Feldern protokolliert:

| Feld | Quelle | Zweck |
|------|--------|-------|
| timestamp | datetime.now(UTC) | Wann |
| event_id | uuid4() | Eindeutige Referenz |
| event_type | PII_MASK / PII_BLOCK / PII_WARN / PROMPT_ALLOWED | Was passiert ist |
| session_id | uuid4() pro Hook-Aufruf | Zusammenhang |
| user_id | getpass.getuser() | Wer |
| system_id | socket.gethostname() | Wo |
| pii_type | Presidio Entity-Typ | Welche PII |
| pii_count | Anzahl pro Finding | Wie viele |
| confidence_score | Presidio Score | Wie sicher |
| action_taken | MASK / BLOCK / WARN | Welche Aktion |
| masking_technique | SUBSTITUTION / PLACEHOLDER / NONE | Wie maskiert |
| outcome | SUCCESS / FAILURE | Ergebnis |
| context_hash | SHA256 (±20 Zeichen) | Nachvollziehbarkeit |
| tool_version | pii_guard.__version__ | Welche Version |
| config_hash | SHA256 der Config | Welche Regeln |

Adressierte ISO 27001 Controls: A.8.11 (Data Masking), A.8.12 (DLP), A.8.15 (Logging), A.5.34 (PII Protection).

### 8.4 Konfiguration

Drei-Ebenen-Modell (für v0.3.0 geplant, aktuell zwei Ebenen):

```
Gruppen-Config   (v0.3.0)   ~/.config/pii-guard/group.yaml
Firmen-Config               ~/.config/pii-guard/config.yaml  (oder %APPDATA%)
Projekt-Config              .pii-guard.yaml
```

Merge-Logik: Deep-Merge, Projekt überschreibt Firma überschreibt Gruppe. Geplant für v0.3.0: Strengen-Rangfolge (`block > auto_mask > warn`) für Sicherheits-Settings.

### 8.5 Fehlerbehandlung

| Situation | Strategie |
|-----------|----------|
| Presidio-Fehler | Fallback: `on_error` (allow oder block) |
| Docker nicht erreichbar | Fallback: `on_error` (3s Timeout) |
| Ungültige Config | ConfigError, PII Guard startet nicht |
| Beschädigtes Mapping | Warning, leeres Mapping, weiterarbeiten |
| Audit-Log voll | Rotation (max_size_mb), alte Logs löschen (keep_days) |
| Atomares Schreiben fehlgeschlagen | Windows-Fallback (direktes Schreiben) |

Grundprinzip: Im Zweifel den Prompt durchlassen (on_error: allow), aber immer loggen.

### 8.6 Plattform-Kompatibilität

| Thema | Windows | macOS / Linux |
|-------|---------|---------------|
| Config-Pfad | %APPDATA%\pii-guard | ~/.config/pii-guard |
| Dateiberechtigungen | ACLs (nicht gesetzt) | chmod 600 |
| Atomares Schreiben | os.replace + Fallback | os.replace |
| Line-Endings | \n (forciert) | \n |
| Docker | Docker Desktop | Docker / Podman |

---

## 9. Architekturentscheidungen

Siehe [docs/DECISIONS.md](DECISIONS.md) für die vollständige Entscheidungshistorie mit Begründungen, Alternativen und Entscheidern.

Wichtigste Entscheidungen:
- E1: Lokale Architektur (kein Cloud-Proxy)
- E3: Typerhaltende Substitution statt Platzhalter
- E5: Docker als optionales Backend
- E6: ISO 27001 Audit-Funktion (15 Felder)
- E7: Windows-Kompatibilität als Pflicht

---

## 10. Qualitätsanforderungen

### 10.1 Qualitätsbaum

```
Qualität
├── Datenschutz
│   ├── Keine PII an API (Funktional)
│   ├── Mapping bleibt lokal (Sicherheit)
│   └── Audit-Trail vollständig (Nachweisbarkeit)
├── Performance
│   ├── Hook-Timeout < 5s (Responsiveness)
│   └── Docker-Warmup einmalig (Startup)
├── Portabilität
│   ├── Windows + macOS + Linux
│   └── pip + Docker
└── Wartbarkeit
    ├── 93 Tests (Testbarkeit)
    ├── Modulare Architektur (Änderbarkeit)
    └── Konfigurierbar ohne Code-Änderung
```

### 10.2 Qualitätsszenarien

| Szenario | Qualitätsziel | Erwartung |
|----------|--------------|-----------|
| Entwickler tippt Prompt mit Kundennamen | Datenschutz | Name wird durch Fake-Name ersetzt, Audit-Eintrag geschrieben |
| Entwickler tippt Prompt mit IBAN | Datenschutz | Prompt wird geblockt, nicht gesendet |
| Auditor fordert Log der letzten 12 Monate | Nachweisbarkeit | CSV-Export mit 15 Feldern, filterbar nach Zeitraum |
| Docker-Container stürzt ab | Verfügbarkeit | Fallback auf allow/block (konfigurierbar), Warning im Log |
| Neuer Mitarbeiter installiert PII Guard | Portabilität | `pii-guard docker start --build` funktioniert auf Windows |
| Config-Threshold wird geändert | Nachvollziehbarkeit | config_hash im Audit-Log ändert sich |

---

## 11. Risiken und technische Schulden

| Risiko | Wahrscheinlichkeit | Auswirkung | Maßnahme |
|--------|-------------------|-----------|----------|
| False Negatives (PII nicht erkannt) | Mittel | Hoch | Wirksamkeitstests (audit-test), Confidence-Threshold konfigurierbar |
| False Positives (Nicht-PII maskiert) | Niedrig | Niedrig | Allow-List, False-Positive-Tests in audit-test |
| Presidio-Engine nicht thread-safe | Niedrig | Mittel | threading.Lock in server.py |
| Reverse-Mapping Kollision | Niedrig | Niedrig | Longest-Match-First Strategie |
| spaCy-Modell veraltet | Mittel | Niedrig | Modellversion in Dockerfile pinnen |

### Technische Schulden

| Schuld | Priorität | Geplant |
|--------|-----------|---------|
| Reverse-Mapping nicht als Hook verdrahtet | Mittel | v0.3.0 |
| Config-Hierarchie (Gruppe -> Firma -> Projekt) fehlt | Mittel | v0.3.0 |
| Keine CLI-Tests mit CliRunner | Niedrig | v0.3.0 |
| Keine Live-Tests mit echtem Presidio | Niedrig | CI/CD |
| Singleton-Engine ohne Config-Change-Detection | Niedrig | Backlog |

---

## 12. Glossar

| Begriff | Erklärung |
|---------|----------|
| PII | Personally Identifiable Information – personenbezogene Daten |
| NER | Named Entity Recognition – Erkennung benannter Entitäten in Text |
| Hook | Skript das von Claude Code vor/nach einem Event aufgerufen wird |
| Typerhaltende Substitution | Ersetzung von PII durch Fake-Daten im gleichen Datentyp |
| Reverse-Mapping | Rückübersetzung von Fake-Daten in Originale |
| Presidio | Open-Source PII-Erkennungs-Engine von Microsoft |
| spaCy | NLP-Framework, liefert die Sprachmodelle für Presidio |
| Faker | Python-Library zur Generierung realistischer Fake-Daten |
| JSONL | JSON Lines – ein JSON-Objekt pro Zeile, Append-only |
| Allow-List | Liste von Begriffen die nie als PII erkannt werden sollen |
| Confidence Score | Wahrscheinlichkeit (0.0–1.0) dass ein Fund tatsächlich PII ist |
| Deep-Merge | Rekursives Zusammenführen verschachtelter Config-Dicts |
