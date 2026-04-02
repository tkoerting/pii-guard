# PII Guard – Setup-Anleitung

PII Guard filtert personenbezogene Daten aus Prompts bevor sie an die LLM-API gehen. Alles läuft lokal.

## Voraussetzungen

- WSL2 Aktivierung (Windows)
- Docker 
- Python 3.11+
- Azure CLI (`az`) mit Zugriff auf die b-imtec Subscription

## 1. Vorbereitungen
- Installiere Docker auf Deinem System
Kopiere das Verzeichnis **piiguard** und den Inhalt an einen von Dir gewählten Ort auf Deiner Festplatte z. B. C:\ oder ~/

## 2. Docker-Image holen

```bash / Terminal


az login
az acr login --name piiguard
docker pull piiguard.azurecr.io/pii-guard:latest
```

## 3. Container starten

```bash / Terminal
docker run -d -p 7437:7437 --restart=unless-stopped --name pii-guard piiguard.azurecr.io/pii-guard:latest
```

Prüfen ob er läuft:

```bash
curl http://localhost:7437/health
```

## 3. PII Guard CLI installieren

```bash
pip install git+https://github.com/tkoerting/pii-guard.git
```

## 4. Projekt einrichten

Im Projektverzeichnis:

```bash
pii-guard init
```

Das erledigt:
- `.pii-guard.yaml` anlegen (Regeln, Schwellenwerte, Allow-List)
- `.pii-guard/` Verzeichnis erstellen
- Claude Code Skills installieren (`/allow`, `/revoke`, `/pii-toggle`, `/pii-status`)

## 5. Docker-Modus aktivieren

In der `.pii-guard.yaml` im Projekt:

```yaml
docker:
  enabled: true
  host: 127.0.0.1
  port: 7437
```

## 6. Fertig

PII Guard ist aktiv. Teste mit:

```bash
pii-guard test "Max Müller hat angerufen"
```

## Befehle

| Befehl | Was es tut |
|--------|-----------|
| `pii-guard on` | Hook aktivieren |
| `pii-guard off` | Hook deaktivieren |
| `pii-guard test "Text"` | PII-Erkennung testen |
| `pii-guard status` | Config und Audit-Log anzeigen |
| `pii-guard allow "Begriff" --reason "..."` | Begriff freigeben |
| `pii-guard revoke "Begriff"` | Freigabe widerrufen |
| `pii-guard overrides` | Aktive Freigaben anzeigen |

## Claude Code Skills

| Skill | Was es tut |
|-------|-----------|
| `/pii-toggle` | PII Guard ein-/ausschalten |
| `/pii-status` | Status und Overrides anzeigen |
| `/allow "Begriff" Begründung` | Begriff freigeben |
| `/revoke Begriff` | Freigabe widerrufen |

## Was wird erkannt?

| PII-Typ | Aktion | Beispiel |
|---------|--------|---------|
| Passwörter, API-Keys, IBANs, Kreditkarten | Blockiert | `DE89370400440532013000` |
| Personennamen, E-Mails, Telefonnummern | Blockiert | `Max Müller`, `max@firma.de` |
| Firmennamen | Warnung | `Siemens AG` |
| IP-Adressen | Warnung | `192.168.1.100` |

Allow-List in `.pii-guard.yaml` pflegen für Begriffe die nie maskiert werden sollen (z.B. eigene Firmennamen).

## Update

```bash
docker pull piiguard.azurecr.io/pii-guard:latest
docker stop pii-guard && docker rm pii-guard
docker run -d -p 7437:7437 --restart=unless-stopped --name pii-guard piiguard.azurecr.io/pii-guard:latest
```

## Probleme?

- **Hook-Timeout**: Container muss laufen (`docker ps | grep pii-guard`)
- **False Positive**: `/allow "Begriff" Begründung warum es kein PII ist`
- **Nervt gerade**: `pii-guard off` oder `/pii-toggle`
