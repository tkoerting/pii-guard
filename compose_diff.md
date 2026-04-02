# Änderungen im Branch `compose`

## Bugfixes

### Port 7437 → 4141 (Produktionsstandard)
- `src/pii_guard/config.py` – Default-Port in Config und Validierung
- `src/pii_guard/hook.py` – Fallback-Port im Docker-HTTP-Call
- `Dockerfile` – `EXPOSE` und Healthcheck-URL
- `.pii-guard.yaml` – Kommentar-Beispiel

---

## Neue Features

### PII Guard pausieren / fortsetzen
- `src/pii_guard/cli.py` – neue Befehle `pii-guard pause` und `pii-guard resume`
  - Erstellt/entfernt eine Disable-Flag-Datei (`.pii-guard/disabled`)
  - Schreibt `GUARD_PAUSE` / `GUARD_RESUME` ins Audit-Log
- `src/pii_guard/server.py` – Toggle-Button im Web-UI (`POST /toggle`)
- Claude Code Skill `pii-pause` in `cli.py` eingebettet (Markdown-Skill-Definition)

### Web-UI (vollständig neu)
`src/pii_guard/server.py` wurde von einer reinen API zu einem vollständigen Web-Dashboard erweitert:

| Endpoint | Funktion |
|---|---|
| `GET /` | Status-Dashboard mit Statistiken und Pause/Resume-Toggle |
| `GET /test` | Formular zum manuellen Testen der PII-Erkennung |
| `GET /report` | Audit-Report mit Datumsfilter und Konfidenz-Statistik |
| `GET /export` | Audit-Log als CSV herunterladen |
| `GET /overrides` | Allow-List und dynamische Overrides verwalten |
| `POST /overrides/add` | Override hinzufügen (Term, Begründung, PII-Typ) |
| `POST /overrides/remove` | Override widerrufen |

### Status-Dashboard: Letzte 10 Log-Einträge
- Neue Tabelle unterhalb der Zusammenfassung (Zeitpunkt, Event-Typ, PII-Typ, Aktion, Vorschau)
- Neuester Eintrag zuerst

### Lokalzeit-Anzeige im Web-UI
- Zeitstempel werden client-seitig im Browser in die lokale Zeitzone umgewandelt (`data-utc`-Attribut + JavaScript)
- Funktioniert unabhängig von der Container-Zeitzone (UTC)
- `src/pii_guard/audit.py` – neue Hilfsfunktion `utc_to_local()` (wird zusätzlich in der CLI genutzt)

---

## Infrastruktur

### Neues Verzeichnis `piiguard/` (Laufzeitumgebung)
Deployment-Artefakte ausgelagert aus dem Repo-Root:

| Datei | Inhalt |
|---|---|
| `piiguard/docker-compose.yml` | Produktions-Compose mit `read_only`, `tmpfs`, `no-new-privileges` |
| `piiguard/docker_install.sh` | Docker-Installationsskript für Ubuntu |
| `piiguard/pii-guard-hook.sh` | Shell-Hook für Claude Code (Docker-Modus, kein Python nötig) |
| `piiguard/azure_login.sh` | Azure Container Registry Login |

### Neues Skript `scripts/build_local_docker_image.sh`
Build-Skript für das lokale Docker-Image `pii-guard:local`.

### Dockerfile: Redundanz beseitigt
- Base-Image `python:3.11-slim` nur noch einmal als `ARG BASE` definiert, beide Stages referenzieren `$BASE`

### `.gitignore`
- `piiguard/.pii-guard.yaml` und `piiguard/azure_login.sh` ausgeschlossen (Secrets)

---

## Dokumentation

- `README.md` – vollständig überarbeitet (Quickstart, Docker-Setup, Web-UI, CLI-Referenz)
- `docs/SETUP.md` – erweiterter Setup-Guide inkl. Shell-Hook und Docker-Compose
- `docs/DECISIONS.md` – Architekturentscheidungen aktualisiert
- `docs/TEAM-ONBOARDING.md` – Onboarding-Schritte angepasst
- `docs/architecture-arc42.md` – arc42-Dokumentation auf aktuellen Stand gebracht
- `docs/chat-python-vs-docker-2026-04-02.md` – neu: Entscheidungsdokumentation Python-lokal vs. Docker
