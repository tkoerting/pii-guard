# PII Guard

Lokaler Datenschutz-Filter für KI-Coding-Tools (Claude Code, Cursor, Copilot).

## Zweck

PII Guard fängt Prompts ab bevor sie an die LLM-API gehen und maskiert personenbezogene Daten durch typerhaltende Substitution. Auditsicher nach ISO 27001, lokal, Open Source.

## Architektur

### Lokaler Modus
```
Prompt → hook.py → Presidio (PII-Erkennung) → Faker (Substitution) → API
Antwort ← Reverse-Mapping (lokal) ← API-Response
```

### Docker-Modus
```
Prompt → hook.py → HTTP POST localhost:4141 → Container (Presidio+spaCy) → Antwort
```

Alles läuft lokal. Keine Cloud, kein Proxy, kein zusätzlicher Datenverarbeiter.

## Projektstruktur

```
pii-guard/
├── src/pii_guard/
│   ├── __init__.py          # Version, Logging-Setup
│   ├── hook.py              # Claude Code Hook + Docker-Route
│   ├── detector.py          # Presidio-Wrapper (PII-Erkennung, de/en)
│   ├── substitutor.py       # Typerhaltende Substitution (Faker, Locale aus Config)
│   ├── mapper.py            # Reversibles Mapping (atomares Schreiben, Windows-kompatibel)
│   ├── audit.py             # ISO 27001 Audit-Logger (15 Felder, Rotation, Reports)
│   ├── config.py            # YAML-Config Loader (Deep-Merge, Validierung, Plattform-Pfade)
│   ├── server.py            # Docker HTTP-Server (ThreadingHTTPServer)
│   └── cli.py               # CLI: init, test, status, audit-*, docker
├── tests/                   # 93 Tests (pytest, alle gemockt)
│   ├── test_detector.py
│   ├── test_substitutor.py
│   ├── test_mapper.py
│   ├── test_hook.py
│   ├── test_hook_docker.py
│   ├── test_audit.py
│   ├── test_config.py
│   ├── test_server.py
│   └── test_integration.py
├── .pii-guard.yaml          # Beispiel-Config
├── Dockerfile               # Multi-Stage Build (spaCy eingebacken)
├── docker-compose.yml       # Docker-Daemon Setup
├── .dockerignore
├── pyproject.toml           # Packaging (hatchling)
├── README.md
└── CLAUDE.md
```

## Kernmodule

### hook.py
- Implementiert den `user_prompt_submit` Hook für Claude Code
- Empfängt den Prompt als JSON auf stdin
- Prüft Docker-Modus (Env `PII_GUARD_DOCKER` > Config `docker.enabled`)
- Docker: HTTP POST an localhost:4141 (3s Timeout, on_error Fallback)
- Lokal: Lazy Imports (Presidio/spaCy erst bei Bedarf)
- Session-ID (UUID) wird durch die Pipeline gereicht
- PROMPT_ALLOWED Event bei 0 Findings

### detector.py
- Wrapper um Microsoft Presidio AnalyzerEngine (Singleton)
- spaCy-Modelle konfigurierbar (de + en)
- Overlap-Auflösung: bei überlappenden Spans gewinnt der längste Fund
- Allow-List als Set (Performance-optimiert)
- Guard für leeren String in `_mask_preview()`

### substitutor.py
- Typerhaltende Substitution mit Faker (11 Entity-Typen)
- Locale aus Config (`substitution.locale`, Default: de_DE)
- Lazy Faker-Initialisierung, deterministisch pro Session (PID-Seed)
- Backward-Index-Processing (verhindert Index-Verschiebung)

### mapper.py
- Bidirektionales Mapping Original <-> Fake
- Atomares Schreiben (os.replace + Windows-Fallback)
- Konsistente Line-Endings (`\n` auf allen Plattformen)
- Session-basiert, auto_cleanup konfigurierbar

### audit.py
- 15-Felder JSONL-Log (ISO 27002:2022 Clause 8.15)
- Event-Typen: PII_MASK, PII_BLOCK, PII_WARN, PROMPT_ALLOWED, EFFECTIVENESS_TEST
- Log-Rotation: max_size_mb + keep_days (Default: 365)
- chmod 600 auf Unix (Plattform-Weiche)
- CSV-Export, Compliance-Reports, Commit-Summary
- `log_event()` für nicht-Finding-Events

### config.py
- Lädt `.pii-guard.yaml` mit Deep-Merge gegen Defaults
- Plattformspezifische Pfade (Windows: %APPDATA%, Mac/Linux: ~/.config)
- Validierung: actions, threshold, method, docker.port, on_error
- `copy.deepcopy` für Thread-Safety

### server.py
- `ThreadingHTTPServer` mit POST /process und GET /health
- `threading.Lock` um `process_prompt()` (Thread-Safety)
- Engine-Warmup beim Start (spaCy vorladen)
- 400 Bad Request bei fehlendem Content-Length

### cli.py
- `pii-guard init [--with-gitleaks]` – Projekt initialisieren
- `pii-guard test "Text"` – PII-Erkennung testen
- `pii-guard status` – Config und Audit-Log anzeigen
- `pii-guard audit-export` – CSV-Export
- `pii-guard audit-report [--format markdown|csv]` – Compliance-Report
- `pii-guard audit-test [--export csv]` – Wirksamkeitstest (PASS/FAIL)
- `pii-guard docker start|stop|status` – Docker-Daemon verwalten

## Konventionen

- Python 3.11+
- Packaging: pyproject.toml (hatchling)
- Tests: pytest (93 Tests, alle gemockt)
- Linting: ruff
- Logging: `logging.getLogger("pii_guard.modul")` in allen Modulen
- Type Hints: ja
- Sprache Code: Englisch
- Sprache Doku: Deutsch
- Keine Emojis in Code oder Doku
- Echte Umlaute (ä, ö, ü, ß), keine Umschreibungen
- Windows-Kompatibilität bei allen Datei-Operationen

## Abhängigkeiten

- presidio-analyzer + presidio-anonymizer
- spacy + de_core_news_lg + en_core_web_lg
- faker
- pyyaml
- click (CLI)

## Offene Entscheidungen (v0.3.0)

- [ ] Hook-Mechanismus für Cursor / Copilot (Claude Code ist fertig)
- [ ] Reverse-Mapping: automatisch (Hook) oder manuell (CLI `pii-guard unmap`)
- [ ] Config-Hierarchie: Gruppen-Config -> Firmen-Config -> Projekt-Config
- [ ] Policy-Templates (`pii-guard init --with-policy`)
