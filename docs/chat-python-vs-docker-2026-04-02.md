# Diskussion: Python lokal vs. Docker-only Setup

**Datum:** 2026-04-02  
**Thema:** Ist Python lokal notwendig wenn PII Guard im Docker-Container läuft?

---

## Frage: Ist Python wirklich notwendig beim Docker-Betrieb?

**Analyse:**

Im Docker-Modus macht `hook.py` lokal nur drei Dinge:
1. JSON von stdin lesen
2. HTTP POST an `localhost:7437` senden
3. Ergebnis zurückgeben

Presidio, spaCy, Faker – alles läuft im Container.

**Python ist lokal trotzdem nötig für:**

| Komponente | Warum Python? | Ersetzbar? |
|---|---|---|
| `hook.py` (Docker-Pfad) | Hook-Befehl ist `python3 -m pii_guard.hook` | Ja – z.B. durch Shell-Script mit `curl` |
| `config.py` | YAML laden, Pfade auflösen | Ja – Shell-Script kann ENV-Variablen lesen |
| `audit.py` | Lokale JSONL-Logs schreiben | Nur wenn man lokale Logs will |
| `cli.py` | `pii-guard init/test/status/...` | Nötig für Setup und Verwaltung |

**Fazit:**
- Für die PII-Erkennung selbst ist Python lokal nicht nötig – das macht der Container
- Für den Hook-Einstiegspunkt und das CLI schon
- Theoretisch könnte man den Hook-Teil durch ein minimales Shell-Script ersetzen, aber das CLI würde dabei wegfallen

---

## Frage: Kann das Audit im Docker-Container laufen und in ein lokales Verzeichnis schreiben?

**Antwort:** Ja – und das ist bereits so umgesetzt.

Der Ablauf im Docker-Modus:
1. `hook.py` sendet nur den Prompt per HTTP an den Container
2. `server.py` im Container ruft `process_prompt()` auf
3. `process_prompt()` ruft `log_findings()` / `audit.py` auf – das Logging passiert also schon im Container

Das `docker-compose.yml` mapped das bereits korrekt:

```yaml
volumes:
  - ./.pii-guard.yaml:/app/data/.pii-guard.yaml:ro   # Config (read-only)
  - ./.pii-guard:/app/data/.pii-guard                # Audit-Log (schreibbar)
```

Das `.pii-guard/`-Verzeichnis im Projektordner wird in den Container gemountet. Der Container schreibt `audit.log` dort hinein, und der User sieht die Datei lokal.

**Was das für Python-Bedarf bedeutet:**

Im Docker-Modus braucht Python lokal nur noch für:
- Den Hook-Einstiegspunkt (`python3 -m pii_guard.hook`) – aber dort passiert nur JSON lesen + HTTP POST
- Das CLI (`pii-guard status`, `pii-guard audit-export` etc.)

---

## Frage: Wäre es möglich das durch eine Website zu ersetzen die im Docker-Container läuft?

**Was in eine Web-UI im Container kann:**

| CLI-Befehl | Web-UI möglich? |
|---|---|
| `pii-guard status` | Ja – Dashboard-Seite |
| `pii-guard test "text"` | Ja – Formular mit Ergebnis |
| `pii-guard audit-report` | Ja – gerenderte Report-Seite |
| `pii-guard audit-export` | Ja – CSV-Download-Button |
| `pii-guard audit-test` | Ja – Trigger + Ergebnisanzeige |
| `pii-guard allow/revoke/overrides` | Ja – schreibt ins gemountete `.pii-guard/` |

**Was lokal bleiben muss:**

| Aufgabe | Warum lokal? |
|---|---|
| `pii-guard init` | Schreibt `.pii-guard.yaml`, `~/.claude/settings.json` – lokal |
| `pii-guard on/off` | Modifiziert `~/.claude/settings.json` – lokal |
| Hook-Einstiegspunkt | Claude Code ruft `python3 -m pii_guard.hook` auf – Prozess muss lokal laufen |

Der Hook lässt sich auf ein minimales Shell-Script reduzieren (kein Python nötig).

---

## Frage: Was sind die Vorteile?

**Einfacheres Onboarding**
Kein `pip install`, kein virtualenv, keine spaCy-Modelle lokal laden. Neue Teammitglieder brauchen nur Docker starten – fertig.

**Keine Versionskonflikte**
Python-Version, Presidio-Version, spaCy-Modell – alles ist im Container eingefroren. Kein "bei mir funktioniert's nicht".

**Windows-Nutzer profitieren am meisten**
Python auf Windows ist traditionell schmerzhaft (PATH, virtualenv, encoding-Probleme). Das fällt komplett weg.

**Zentrale Verwaltung**
Overrides, Audit-Reports, Status – alles über eine URL im Browser statt Terminal-Befehle. Auch für nicht-technische Teammitglieder zugänglich (z.B. Compliance-Verantwortliche die den Audit-Report sehen wollen).

**Updates sind einfacher**
Ein `docker pull` aktualisiert alles – Presidio, spaCy-Modelle, Web-UI, Audit-Logik. Kein `pip install --upgrade` bei jedem Nutzer.

**Nachteile:**
- Web-UI ist Aufwand (muss gebaut, getestet und gepflegt werden)
- Hook-Script ist weniger portabel (Bash + jq funktioniert in WSL2, aber nicht nativ auf Windows)
- Container muss laufen (ist er gestoppt, gibt es keinen lokalen Fallback mehr)

---

## Frage: Was ist jq?

`jq` ist ein schlankes Kommandozeilen-Tool zum Parsen und Verarbeiten von JSON – quasi `sed`/`awk` für JSON.

```bash
echo '{"decision":"block","reason":"PII erkannt"}' | jq -r '.decision'
# Ausgabe: block
```

**Verfügbarkeit:**
- Linux: meist vorinstalliert, sonst `apt install jq`
- Mac: `brew install jq`
- Windows/WSL: `apt install jq`

---

## Frage: Wie würde der Hook auf Linux laufen?

In WSL2 läuft der Hook genauso wie auf nativem Linux – kein Unterschied.

**Hook-Registrierung in `~/.claude/settings.json`:**

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/home/user/.local/bin/pii-guard-hook.sh",
        "timeout": 5000
      }]
    }]
  }
}
```

**Hook-Script (`pii-guard-hook.sh`):**

```bash
#!/bin/bash
INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""')

if [ -z "$PROMPT" ]; then
  echo '{"decision":"allow"}'
  exit 0
fi

RESULT=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": $(echo "$PROMPT" | jq -R -s '.')}" \
  http://127.0.0.1:7437/process)

DECISION=$(echo "$RESULT" | jq -r '.decision // "allow"')

if [ "$DECISION" = "block" ]; then
  echo "$RESULT" | jq -r '.reason // "PII Guard: Prompt blockiert."' >&2
  exit 2
fi

echo "$RESULT"
```

**Abhängigkeiten lokal (WSL2):** nur `docker` + `jq` (`apt install jq`)

---

## Ergebnis: Neue Ziel-Architektur

| Lokal benötigt | Aktuell | Ziel |
|---|---|---|
| Python 3.11+ | ja | nein |
| Docker | ja | ja |
| WSL2 (Windows) | ja | ja |
| `jq` | nein | ja (`apt install jq`) |

**Nächste mögliche Schritte:**
1. Hook-Script (Bash + jq, ersetzt `hook.py` lokal)
2. Web-UI im Container (ersetzt CLI-Befehle für Status, Reports, Overrides)
3. Setup-Anleitung ohne Python (ersetzt `pii-guard init`)
