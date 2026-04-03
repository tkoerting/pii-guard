# PII Guard – Setup-Anleitung

PII Guard filtert personenbezogene Daten aus Prompts bevor sie an die LLM-API gehen. Alles läuft lokal.

## Voraussetzungen

- WSL2 Aktivierung (Windows)
- Docker
- Azure CLI (`az`) mit Zugriff auf die b-imtec Subscription

## 1. Vorbereitungen

Verzeichnis **piiguard** an einen von Dir gewählten Ort kopieren, z. B. `C:\piiguard` oder `~/piiguard`.

### WSL2 installieren (Windows):

```powershell (als Administrator)
wsl --install -d Ubuntu-24.04
```

### Docker inkl. `curl` und `jq` auf Deinem System installieren.
Nach Aufruf der shell bash/wsl in das Verzeichnis **piiguard** wechseln.

```bash / wsl (unter Windows im Startmenue)
chmod +x ./docker_install.sh
./docker_install.sh
```
Erscheint ein "Hello World" ist docker erfolgreich installiert.

## 2. Docker-Image holen und Container starten

```bash / wsl
./azure_login

docker compose up -d
```

Prüfen ob er läuft:

```bash
curl http://localhost:4141/health
```

## 3. Projekt einrichten

Im Projektverzeichnis `.pii-guard.yaml` anlegen, oder Datei aus dem pii-guard Verzeichnis kopieren:

```yaml
version: 1
engine:
  languages: ["de", "en"]
  confidence_threshold: 0.7
rules:
  - types: [PASSWORD, API_KEY, CREDIT_CARD, IBAN_CODE]
    action: block
  - types: [PERSON, EMAIL_ADDRESS, PHONE_NUMBER]
    action: auto_mask
  - types: [ORGANIZATION]
    action: warn
allow_list: []
audit:
  enabled: true
  path: .pii-guard/audit.log
docker:
  enabled: true
  host: 127.0.0.1
  port: 4141
```

`.pii-guard/` Verzeichnis erstellen:

```bash / wsl
mkdir -p .pii-guard
echo "session-map.json" > .pii-guard/.gitignore
```

## 4. Hook registrieren

Hook-Script ausführbar machen:

```bash
chmod +x /pfad/zu/piiguard/pii-guard-hook.sh
```

In `~/.claude/settings.json` eintragen (Pfad anpassen):

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

## 5. Fertig

PII Guard ist aktiv. Web-UI aufrufen:

```
http://localhost:4141
```

## Web-UI

| Seite | URL | Was es tut |
|-------|-----|-----------|
| Status | `http://localhost:4141` | Übersicht, Audit-Statistiken |
| Testen | `http://localhost:4141/test` | PII-Erkennung ausprobieren |
| Audit-Report | `http://localhost:4141/report` | Compliance-Report mit Datumsfilter |
| CSV-Export | `http://localhost:4141/export` | Audit-Log herunterladen |
| Overrides | `http://localhost:4141/overrides` | Begriffe freigeben und widerrufen |

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

Allow-List in `.pii-guard.yaml` pflegen für Begriffe die nie maskiert werden sollen (z.B. eigene Firmennamen). Oder über die Web-UI unter Overrides.

## Update

```bash
docker pull piiguard.azurecr.io/pii-guard:latest
docker compose down && docker compose up -d
```

## Probleme?

- **Hook-Timeout**: Container muss laufen (`docker ps | grep pii-guard`)
- **False Positive**: Web-UI öffnen → Overrides → Begriff freigeben
- **Nervt gerade**: Hook-Script temporär aus `settings.json` entfernen oder `/pii-toggle`
