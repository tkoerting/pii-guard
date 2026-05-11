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
│   ├── detector.py          # Presidio-Wrapper (PII-Erkennung, nur de)
│   ├── recognizers.py       # Custom Recognizer (Phone, IP, API Key, Password)
│   ├── substitutor.py       # Typerhaltende Substitution (Faker, Locale aus Config)
│   ├── mapper.py            # Reversibles Mapping (atomares Schreiben, Windows-kompatibel)
│   ├── overrides.py         # Begründete Freigaben (audit-trail-fähig)
│   ├── audit.py             # ISO 27001 Audit-Logger (15 Felder, Rotation, Reports)
│   ├── config.py            # YAML-Config Loader (Deep-Merge, Validierung, Plattform-Pfade)
│   ├── server.py            # Docker HTTP-Server + Web-UI (Dashboard, Test, Reports, Overrides)
│   ├── proxy.py             # Transparenter API-Proxy mit bidirektionalem PII-Mapping
│   └── cli.py               # CLI: init, test, status, audit-*, docker, pause/resume, allow/revoke
├── piiguard/                # Deploy-Paket (für Docker-only Setup ohne Python)
│   ├── pii-guard-hook.sh    # Bash-Hook (curl + jq, ersetzt hook.py im Docker-Modus)
│   ├── pii-guard-statusline.sh  # Claude Code Statusleiste
│   ├── .pii-guard.yaml      # Sample-Config für Docker-Setup
│   ├── docker_install.sh    # Docker-Installation (Ubuntu/WSL2)
│   └── azure_login.sh       # ACR Login
├── scripts/
│   └── build_local_docker_image.sh  # Lokaler Docker-Build
├── tests/                   # 92 Tests (pytest, alle gemockt)
├── .pii-guard.yaml          # Beispiel-Config
├── Dockerfile               # Multi-Stage Build (spaCy eingebacken)
├── docker-compose.yml       # Docker-Daemon Setup (Port 4141)
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
- `ThreadingHTTPServer` mit API + Web-UI
- API: POST /process, GET /health
- Web-UI: GET / (Dashboard), GET /test, GET /report, GET /export, GET /overrides
- Web-UI: POST /test, POST /overrides/add, POST /overrides/remove, POST /toggle
- HTML-Escaping gegen XSS (`_h()`)
- Pause/Resume über Flag-Datei (`.pii-guard/disabled`)
- `threading.Lock` um `process_prompt()` (Thread-Safety)
- Engine-Warmup beim Start (spaCy vorladen)

### proxy.py
- Transparenter API-Proxy (Port 7438) zwischen Claude Code und Anthropic API
- PII-Maskierung in Request-Messages via `substitute_pii()`
- Reverse-Mapping in API-Antworten via `mapper.reverse_map()`
- SSE-Buffering: `stream: true` upstream (umgeht 20MB-Limit), Non-Stream downstream
- `_buffer_sse_stream()` sammelt SSE-Events und baut Non-Stream-Response
- Gzip-Dekomprimierung als Fallback
- Aktivierung: `ANTHROPIC_BASE_URL=http://localhost:7438`

### cli.py
- `pii-guard init [--with-gitleaks]` – Projekt initialisieren
- `pii-guard test "Text"` – PII-Erkennung testen
- `pii-guard status` – Config und Audit-Log anzeigen
- `pii-guard on/off` – Hook in Claude Code Settings aktivieren/deaktivieren
- `pii-guard pause/resume` – Filterung unterbrechen/fortsetzen (Hook bleibt aktiv)
- `pii-guard allow "Begriff" --reason "..."` – Begründete Freigabe
- `pii-guard revoke "Begriff"` – Freigabe widerrufen
- `pii-guard overrides` – Aktive Freigaben anzeigen
- `pii-guard audit-export` – CSV-Export
- `pii-guard audit-report [--format markdown|csv]` – Compliance-Report
- `pii-guard audit-test [--export csv]` – Wirksamkeitstest (PASS/FAIL)
- `pii-guard docker start|stop|status` – Docker-Daemon verwalten
- `pii-guard proxy start` – API-Proxy starten

## Konventionen

- Python 3.11+
- Packaging: pyproject.toml (hatchling)
- Tests: pytest (92 Tests, alle gemockt)
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
- spacy + de_core_news_lg
- faker
- pyyaml
- click (CLI)

## Ports

- **4141** – PII Guard Server (Docker, Web-UI + API)
- **7438** – PII Guard Proxy (transparenter API-Proxy)

## Offene Entscheidungen

- [ ] Web-UI Auth/CSRF (#21) – niedrige Prio solange localhost-only
- [ ] Streaming zum Client (#7) – aktuell nur upstream-seitig
- [ ] Hook-Mechanismus für Cursor / Copilot (Claude Code ist fertig)
- [ ] Config-Hierarchie: Gruppen-Config -> Firmen-Config -> Projekt-Config
- [ ] Policy-Templates (`pii-guard init --with-policy`)


<!-- EPO:START -->

## Gelernte Regeln (EPO -- nicht manuell editieren)

- Immer echte Umlaute verwenden (ä, ö, ü, ß) statt Umschreibungen (ae, oe, ue, ss) — nicht nur in Dokumenten, sondern auch in Freitext-Antworten an den User.
- Gedankenstriche korrekt setzen: Halbgeviertstrich (–) mit Leerzeichen statt doppeltem Bindestrich (--)
- Logos und Bilder immer als PNG-Datei referenzieren, niemals als Base64 in HTML einbetten
- Ehrlich und offen schreiben – Grenzen und Risiken benennen statt Marketing-Echo-Kammer
- Bei Feature-Ideen Pushback geben: Löst das ein echtes Problem? Gibt es das schon? Ist der Aufwand verhältnismäßig?
- Bei IP-relevanten Themen (Patente, Schutzrechte, Veröffentlichungen): IMMER zuerst prüfen ob eine Veröffentlichung die Neuheit gefährden könnte. Erst schützen, dann veröffentlichen.
- Keine Zitate erfinden oder realen Personen in den Mund legen, auch nicht wenn es narrativ perfekt passt. Wenn eine Brücke fehlt, lieber eigenen Gedanken formulieren oder eine echte Quelle sauber zitieren – auch wenn das weniger elegant ist. Regel: Narrativ gut ≠ wahr. Fabrication zerstört Vertrauen, und das ist in Blogposts existenziell.
- Thomas mag Harari sehr. Bei Gelegenheit Buchempfehlung auf der-koerting.de einbauen.
- Vor WordPress-Publikation: Post im Light UND Dark Mode durchklicken, alle interaktiven Elemente (Buttons, Hover, Selected-States) prüfen. Auf der-koerting.de funktioniert Dark Mode via body.dark-mode Klasse (JS-Toggle) UND prefers-color-scheme Media Query — beide Selektoren nötig. Qualitätscheck nicht auf den User abwälzen.
- Bei Compliance-, Risiko-, DSGVO- oder Sicherheitsargumenten zuerst Reality-Check durchführen bevor die Dramatik übernommen wird. Konkret prüfen: Was fließt tatsächlich? Welches reale Szenario würde den Schaden auslösen? Gilt das für den konkreten Use Case? Dramatik ist ein Warnsignal, kein Argument. Experten-Autorität (Markus, Auditor, Berater) entbindet nicht von der eigenen Prüfung. Nicht jede neue Information kippt die Gesamtempfehlung.
- Session-Hygiene: Bei längeren Sessions aktiv Warnsignale erkennen und ansprechen – Themen-Sprünge, >80k Kontext, Wiederholungen, widersprüchliche Aussagen, längere/hedgigere Antworten. Empfehle Cut und neue Session aktiv, auch wenn der User nicht danach fragt. Thomas will das – nicht erst warten bis er selbst merkt dass es unscharf wird.
- In GitHub Issues, Kommentaren und PR-Beschreibungen IMMER SHA-Permalinks verwenden (blob/<sha>/...), nie blob/main-Links. blob/main bricht bei Umbenennungen und File-Moves. Bei Bulk-Erstellung von Issues: aktuellen SHA von main holen und in URLs einbauen.
- Jeden Link in Promo-Content mit UTM-Parametern versehen. Keine nackten URLs mehr.
- Bei jedem neün Blogpost proaktiv WhatsApp-Story-Slides anbieten. Thomas findet das Format "sehr geil".
- Keine Trennstriche (wp:separator, hr-Elemente) in Blogposts auf der-körting.de einbaün.
- Große Zahlen in Datenstücken IMMER durch greifbare Vergleiche visualisieren. Keine KI-Bilder, keine Stock-Fotos — die Bilder entstehen im Kopf des Lesers, durch die Daten.
- Bei jedem neün Datenstück auf opendataminded.de die sitemap.xml im data-stories Repo erweitern.
- ## Regel: SEO/GEO ist kein Nachgang, sondern Teil des Posts
- Thomas schreibt direkt und nüchtern. Emotionale Texte müssen authentisch klingen – kein Pathos, kein Kitsch, keine Floskeln wie „ich will mit dir alt werden".
- Bei HA iframe-Card Dashboards immer `allow_open_top_navigation: true` und `aspect_ratio: "100%"` setzen.
- Immer echte Umlaute verwenden (ä, ö, ü, ß) — nicht nur in Markdown/Docs, sondern auch in Freitext-Antworten an den User.
- Thomas Körting ist NICHT Geschäftsführer von b-imtec. Thomas Veit ist Geschäftsführer.
- Gesammelte Regeln für Kommunikation an T-Systems:
- Wenn der Preis steigt (v2.0 → v2.1: +20%), nie defensiv oder entschuldigend kommunizieren.
- Persönliche/lokale Dateien wie CLAUDE.md, memory.md, pitch.md dürfen ins private tkörting-Repo gepusht werden, aber NICHT ins b-imtec-gmbh Repo. Das b-imtec-Repo ist fürs Team – dort gehören nur Dateien rein, die für alle relevant sind.
- Megasoft kann im formellen Angebot an T-Systems **keine Minus-Positionen** abbilden (keine Rabattzeilen, keine „nicht berechneten Eigenleistungen" als Abzug). Der T-Systems-Bestellprozess erlaubt nur bestellbare Positiv-Positionen.
- Write-Back / Datenkorrekturen im BI-Kontext ist KEIN Alleinstellungsmerkmal gegen Digital Fül. Das bestehende Tool kann das bereits.
- Thomas Veit (09.04.2026) zur Risikoanalyse der Angebotsbewertung: „Wenn wir nur Null-Risiko-Projekte anbieten wollen, haben wir kein Business-Modell mehr. Aber die Formulierungen müssen wir auf jeden Fall übernehmen, das reduziert unser Risiko erheblich."
- Logos IMMER als PNG-Datei einbinden (relativer Pfad), NIEMALS als Base64 in HTML einbetten.
- Denis hat am 21.04.2026 unsere interne Briefing-Mail (SMA-Zahlen, Preisanpassungsklauseln) 1:1 an Haberkorn weitergeleitet – inklusive Formulierungen in dritter Person über Haberkorn.

<!-- EPO:END -->
